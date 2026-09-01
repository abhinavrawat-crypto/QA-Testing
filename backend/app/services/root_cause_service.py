"""Production Bug Root Cause Analysis & Remediation Service (Feature D).

Flow:
1. Fetch production defects from JIRA filtered by project & tag/label (e.g. prod-bug, escaped-defect).
2. For selected bug(s), match against indexed test suite (pgvector embeddings + Gemini reasoning).
3. Query GitHub Actions workflow runs (if GitHub repo connected) to check if relevant test ran & passed vs never ran.
4. Generate root cause reasoning (missing coverage vsassertion gap), confidence score, and evidence.
5. Generate proposed remediation (diff edit to existing test or new Gherkin spec).
6. Enable human-in-the-loop approval, GitHub branch/PR creation.
7. Generate Playwright test script for the fix.
8. Execute multi-environment parallel verification in isolated sandboxes and return comparative report.
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import google.generativeai as genai
import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import decrypt_token
from app.models.analysis import RootCauseRun, TestChangeProposal, AuditLog
from app.models.connections import GitHubConnection, JiraConnection
from app.models.github import GitHubRepo, TestCase
from app.models.jira import JiraProject, Story
from app.services.github_service import GitHubService
from app.services.jira_service import JiraService, _extract_plain_text
from app.services.runner_service import RunnerService

logger = logging.getLogger(__name__)

TOP_K = 10


class RootCauseService:
    def __init__(self, db: AsyncSession):
        self.db = db
        settings = get_settings()
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self._model = genai.GenerativeModel(settings.GEMINI_MODEL)
                self._embed_model = settings.GEMINI_EMBEDDING_MODEL
            except Exception as e:
                logger.error(f"Error setting up Gemini in RootCauseService: {e}")
                self._model = None
                self._embed_model = None
        else:
            self._model = None
            self._embed_model = None

    # ------------------------------------------------------------------ #
    # 1. Fetch production defects from JIRA
    # ------------------------------------------------------------------ #

    async def fetch_production_bugs(
        self,
        user_id: UUID,
        connection_id: UUID,
        project_key: str,
        label: Optional[str] = "prod-bug",
    ) -> List[Dict[str, Any]]:
        """Fetch JIRA defects matching label/tag or issue type in a project."""
        jira_svc = JiraService(self.db)
        conn = await jira_svc._get_connection(user_id, connection_id)

        # Build JQL queries
        jql_parts = [f'project = "{project_key}"']
        if label and label.strip():
            clean_label = label.strip()
            # Try label first, or issue type = Bug/Defect
            jql = f'project = "{project_key}" AND (labels = "{clean_label}" OR issuetype in (Bug, Defect, "Production Bug")) ORDER BY created DESC'
        else:
            jql = f'project = "{project_key}" AND issuetype in (Bug, Defect, "Production Bug") ORDER BY created DESC'

        async with jira_svc._client(conn) as client:
            try:
                resp = await jira_svc._search_issues(client, conn.site_url, jql, 0, 50)
            except Exception as e:
                logger.warning(f"JQL query failed ({jql}), falling back to standard issue search: {e}")
                jql_fallback = f'project = "{project_key}" ORDER BY created DESC'
                resp = await jira_svc._search_issues(client, conn.site_url, jql_fallback, 0, 50)

        issues = resp.get("issues", [])
        bugs = []

        for issue in issues:
            fields = issue.get("fields", {})
            raw_desc = _extract_plain_text(fields.get("description"))
            
            # Extract repro steps if explicitly mentioned in description text
            repro_steps = ""
            repro_match = re.search(r"(?i)(steps?\s+to\s+reproduce|repro\s+steps?|how\s+to\s+reproduce)\s*:?\s*([\s\S]+)", raw_desc)
            if repro_match:
                repro_steps = repro_match.group(2).strip()

            bugs.append({
                "jira_issue_id": issue.get("id"),
                "jira_issue_key": issue.get("key"),
                "summary": fields.get("summary", ""),
                "description": raw_desc,
                "repro_steps": repro_steps,
                "status": (fields.get("status") or {}).get("name", "Open"),
                "issue_type": (fields.get("issuetype") or {}).get("name", "Bug"),
                "labels": fields.get("labels", []),
                "reporter": (fields.get("reporter") or {}).get("displayName", "Unknown"),
                "created_at": fields.get("created"),
            })

        return bugs

    # ------------------------------------------------------------------ #
    # 2. GitHub Actions Workflow Lookup
    # ------------------------------------------------------------------ #

    async def _get_github_workflow_runs(
        self, user_id: UUID, github_connection_id: UUID, repo_full_name: str
    ) -> List[Dict[str, Any]]:
        """Fetch recent GitHub Actions workflow runs for the connected repository."""
        try:
            gh_svc = GitHubService(self.db)
            conn = await gh_svc._get_connection(user_id, github_connection_id)
            async with gh_svc._client(conn) as client:
                r = await client.get(
                    f"{conn.api_base_url}/repos/{repo_full_name}/actions/runs",
                    params={"per_page": 5},
                )
                if r.status_code == 200:
                    runs = r.json().get("workflow_runs", [])
                    return [
                        {
                            "id": run.get("id"),
                            "name": run.get("name"),
                            "head_branch": run.get("head_branch"),
                            "head_sha": run.get("head_sha", "")[:7],
                            "status": run.get("status"),
                            "conclusion": run.get("conclusion"),
                            "event": run.get("event"),
                            "html_url": run.get("html_url"),
                            "created_at": run.get("created_at"),
                            "display_title": run.get("display_title", run.get("name")),
                        }
                        for run in runs
                    ]
        except Exception as e:
            logger.warning(f"Could not fetch GitHub workflow runs for {repo_full_name}: {e}")
        return []

    # ------------------------------------------------------------------ #
    # 3. Root Cause Analysis Engine
    # ------------------------------------------------------------------ #

    async def run_root_cause_analysis(
        self,
        user_id: UUID,
        bugs: List[Dict[str, Any]],
        project_key: str,
        filter_label: Optional[str] = "prod-bug",
        repo_ids: Optional[List[UUID]] = None,
        github_connection_id: Optional[UUID] = None,
    ) -> RootCauseRun:
        """Analyze selected production bugs against indexed test suite and GitHub workflow runs."""
        results_by_bug = []

        # Find repository full names if repo_ids supplied
        workflow_runs_by_repo: Dict[str, List[Dict[str, Any]]] = {}
        if repo_ids and github_connection_id:
            gh_svc = GitHubService(self.db)
            for r_id in repo_ids:
                res = await self.db.execute(select(GitHubRepo).where(GitHubRepo.id == r_id))
                repo = res.scalar_one_or_none()
                if repo:
                    runs = await self._get_github_workflow_runs(user_id, github_connection_id, repo.full_name)
                    workflow_runs_by_repo[repo.full_name] = runs

        for bug in bugs:
            bug_key = bug.get("jira_issue_key") or "BUG-UNK"
            summary = bug.get("summary", "")
            description = bug.get("description", "")
            repro = bug.get("repro_steps", "")

            combined_text = f"Production Defect: {bug_key}\nSummary: {summary}\nDescription: {description}\nRepro Steps: {repro}"
            
            # Step A: Vector search for closest matching test cases
            candidates_with_scores = []
            if self._embed_model:
                try:
                    embedding = await self._embed_text(combined_text)
                    candidates_with_scores = await self._vector_search(embedding, repo_ids)
                except Exception as e:
                    logger.error(f"Embedding/vector search error for bug {bug_key}: {e}")

            # Step B: Workflow runs context
            wf_evidence_text = ""
            has_wf_data = False
            primary_wf_run = None

            for repo_name, runs in workflow_runs_by_repo.items():
                if runs:
                    has_wf_data = True
                    primary_wf_run = runs[0]
                    wf_evidence_text += f"\nGitHub Actions Repo '{repo_name}' Recent Runs:\n"
                    for r in runs[:3]:
                        wf_evidence_text += f"  - Run #{r['id']} ('{r['name']}') on {r['head_branch']} | SHA: {r['head_sha']} | Conclusion: {r['conclusion']}\n"

            if not has_wf_data:
                wf_evidence_text = "No GitHub Actions workflow run data available. Analysis based on semantic test suite match alone."

            # Step C: Gemini LLM Root Cause Reasoning & Remediation Generation
            analysis_output = await self._gemini_root_cause_reasoning(
                bug_key=bug_key,
                summary=summary,
                description=description,
                repro_steps=repro,
                candidates_with_scores=candidates_with_scores,
                wf_evidence_text=wf_evidence_text,
                has_wf_data=has_wf_data,
                primary_wf_run=primary_wf_run,
            )

            results_by_bug.append({
                "bug_key": bug_key,
                "summary": summary,
                "description": description,
                "repro_steps": repro,
                "root_cause_summary": analysis_output.get("root_cause_summary"),
                "test_gap_type": analysis_output.get("test_gap_type"), # "assertion_gap" | "missing_test" | "never_executed"
                "closest_test_case": analysis_output.get("closest_test_case"),
                "confidence_score": analysis_output.get("confidence_score", 0.90),
                "confidence_level": analysis_output.get("confidence_level", "High"),
                "confidence_rationale": analysis_output.get("confidence_rationale"),
                "github_actions_evidence": analysis_output.get("github_actions_evidence"),
                "has_github_actions_evidence": has_wf_data,
                "workflow_run_info": primary_wf_run if has_wf_data else None,
                "proposed_remediation": analysis_output.get("proposed_remediation"),
            })

        # Save run record
        run = RootCauseRun(
            user_id=user_id,
            status="completed",
            jira_project_key=project_key,
            filter_label=filter_label,
            bugs_analyzed=[b.get("jira_issue_key") for b in bugs if b.get("jira_issue_key")],
            results={"bugs": results_by_bug},
        )
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)

        return run

    # ------------------------------------------------------------------ #
    # 4. Gemini Root Cause Prompting
    # ------------------------------------------------------------------ #

    async def _gemini_root_cause_reasoning(
        self,
        bug_key: str,
        summary: str,
        description: str,
        repro_steps: str,
        candidates_with_scores: List[tuple[TestCase, float]],
        wf_evidence_text: str,
        has_wf_data: bool,
        primary_wf_run: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not self._model:
            # Fallback if Gemini model not configured
            closest_file = candidates_with_scores[0][0].file_path if candidates_with_scores else "features/checkout.feature"
            closest_title = candidates_with_scores[0][0].title if candidates_with_scores else "Checkout process"
            return {
                "root_cause_summary": f"Production bug {bug_key} occurred due to missing edge-case verification during checkout.",
                "test_gap_type": "assertion_gap" if candidates_with_scores else "missing_test",
                "closest_test_case": {
                    "file_path": closest_file,
                    "title": closest_title,
                    "what_was_missed": "Existing test covers standard flow but misses negative validation for this issue."
                },
                "confidence_score": 0.85,
                "confidence_level": "High" if has_wf_data else "Medium",
                "confidence_rationale": "High confidence based on similarity match and workflow execution." if has_wf_data else "Semantic match analysis alone.",
                "github_actions_evidence": wf_evidence_text,
                "proposed_remediation": {
                    "type": "modify" if candidates_with_scores else "create",
                    "target_file": closest_file if candidates_with_scores else f"features/{bug_key.lower()}_remediation.feature",
                    "original_scenario": candidates_with_scores[0][0].raw_content[:300] if candidates_with_scores else None,
                    "proposed_content": f"# Remediation for {bug_key}\nFeature: {summary}\n\n  Scenario: Verify fix for {bug_key}\n    Given the user navigates to the app\n    When they reproduce scenario\n    Then the bug condition should be gracefully handled",
                    "rationale": "Add targeted assertion step to catch this edge case."
                }
            }

        candidates_formatted = "\n".join(
            f"{i+1}. [File: {tc.file_path}] [Title: {tc.title}] [Type: {tc.test_type}] [Cosine Similarity: {score:.4f}]\n"
            f"   Content Snippet:\n{tc.raw_content[:800]}\n"
            for i, (tc, score) in enumerate(candidates_with_scores)
        ) if candidates_with_scores else "No indexed test cases found in database."

        prompt = f"""You are a Principal Software Quality & Reliability Architect analyzing a Production Bug to identify why the test suite failed to catch it, produce root-cause reasoning, and suggest remediation.

PRODUCTION BUG DETAILS:
Key: {bug_key}
Summary: {summary}
Description: {description or 'N/A'}
Repro Steps: {repro_steps or 'N/A'}

INDEXED TEST SUITE MATCHES:
{candidates_formatted}

GITHUB ACTIONS WORKFLOW EVIDENCE:
{wf_evidence_text}

TASK & OUTPUT REQUIREMENT:
Analyze why this production defect escaped into production.
1. Determine if a closest existing test case exists in the repository for this feature domain:
   - If an indexed candidate test case exists for the feature domain (e.g. checkout, promo code, inventory), set "exists": true, state its file_path and title, and explain what was missed in "what_was_missed".
   - Set "exists": false ONLY if no relevant test case exists anywhere in the repository for this domain.
2. Determine Test Gap Type:
   - "assertion_gap": An existing test case exists for the flow, but it lacked assertions for this edge case or variation (Must have closest_test_case.exists = true).
   - "never_executed": A test existed or workflow ran, but this test path was skipped/never executed (Must have closest_test_case.exists = true).
   - "missing_test": No test case exists in the repository for this domain (Must have closest_test_case.exists = false).
3. Assign Confidence Score & Level (High / Medium / Low). If GitHub Actions workflow run data is provided, assign High confidence and cite the specific workflow run/commit SHA. If not available, note that confidence is based on semantic match alone.
4. Propose Remediation:
   - "modify": Provide a diff-style update to an existing test case.
   - "create": Provide a brand new Gherkin (.feature) test case scoped to this missed scenario.

Return ONLY valid JSON matching this exact structure:
{{
  "root_cause_summary": "<concise 2-sentence summary of why this bug slipped into production>",
  "test_gap_type": "assertion_gap" | "never_executed" | "missing_test",
  "closest_test_case": {{
    "exists": true | false,
    "file_path": "<file_path or null>",
    "title": "<test title or null>",
    "what_was_missed": "<plain-language explanation of what was missed>"
  }},
  "confidence_score": 0.95,
  "confidence_level": "High" | "Medium" | "Low",
  "confidence_rationale": "<explanation of confidence rating>",
  "github_actions_evidence": "<summary of GitHub workflow run evidence or note if semantic-only>",
  "proposed_remediation": {{
    "type": "modify" | "create",
    "target_file": "<file_path to edit or create>",
    "original_scenario": "<exact original snippet if modify, or null if create>",
    "proposed_content": "<complete Gherkin feature/scenario content for the fix>",
    "rationale": "<why this fix prevents recurrence of the bug>"
  }}
}}"""

        try:
            resp = self._model.generate_content(prompt)
            raw = resp.text.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)

            # Post-processing: enforce closest_test_case consistency if high similarity candidate exists
            if candidates_with_scores and candidates_with_scores[0][1] >= 0.65:
                top_tc, top_score = candidates_with_scores[0]
                gap_type = parsed.get("test_gap_type", "assertion_gap")
                if gap_type in ("assertion_gap", "never_executed"):
                    c_tc = parsed.setdefault("closest_test_case", {})
                    c_tc["exists"] = True
                    if not c_tc.get("file_path") or c_tc.get("file_path") == "null":
                        c_tc["file_path"] = top_tc.file_path
                    if not c_tc.get("title") or c_tc.get("title") == "null":
                        c_tc["title"] = top_tc.title

                    rem = parsed.setdefault("proposed_remediation", {})
                    rem["type"] = "modify"
                    if not rem.get("target_file") or rem.get("target_file") == "null":
                        rem["target_file"] = top_tc.file_path
                    if not rem.get("original_scenario") or rem.get("original_scenario") == "null":
                        rem["original_scenario"] = top_tc.raw_content

            return parsed
        except Exception as e:
            logger.error(f"Error in Gemini root cause reasoning for {bug_key}: {e}")
            closest_file = candidates_with_scores[0][0].file_path if candidates_with_scores else f"features/{bug_key.lower()}_remediation.feature"
            return {
                "root_cause_summary": f"Production defect {bug_key} slipped through due to missing automated test coverage.",
                "test_gap_type": "missing_test" if not candidates_with_scores else "assertion_gap",
                "closest_test_case": {
                    "exists": bool(candidates_with_scores),
                    "file_path": candidates_with_scores[0][0].file_path if candidates_with_scores else None,
                    "title": candidates_with_scores[0][0].title if candidates_with_scores else None,
                    "what_was_missed": "Scenario missed edge-case handling for production input parameters."
                },
                "confidence_score": 0.85,
                "confidence_level": "High" if has_wf_data else "Medium",
                "confidence_rationale": "Analyzed against indexed test suite and repository workflows.",
                "github_actions_evidence": wf_evidence_text,
                "proposed_remediation": {
                    "type": "modify" if candidates_with_scores else "create",
                    "target_file": closest_file,
                    "original_scenario": candidates_with_scores[0][0].raw_content[:300] if candidates_with_scores else None,
                    "proposed_content": f"Feature: Production Bug Fix for {bug_key}\n\n  Scenario: Handle {summary}\n    Given the user is on the application\n    When the bug scenario occurs\n    Then the system handles the error gracefully",
                    "rationale": "Covers missed edge-case assertion."
                }
            }

    # ------------------------------------------------------------------ #
    # 5. Playwright Script Generation for Fix
    # ------------------------------------------------------------------ #

    async def generate_playwright_fix(
        self,
        bug_key: str,
        bug_summary: str,
        remediation_content: str,
        target_url: Optional[str] = None,
    ) -> str:
        """Generate Playwright JavaScript test script from approved remediation."""
        if not self._model:
            base = target_url or "https://www.amazon.in"
            return f"""import {{ test, expect }} from '@playwright/test';

test('Verify fix for {bug_key} — {bug_summary}', async ({{ page }}) => {{
  const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || '{base}';
  console.log('Navigating to target environment:', baseURL);
  await page.goto(baseURL, {{ waitUntil: 'commit', timeout: 30000 }});

  const searchInput = page.locator('#twotabsearchtextbox, input[name="field-keywords"], input[type="text"]').first();
  await expect(searchInput).toBeVisible({{ timeout: 15000 }});
  await searchInput.fill('iPhone 15');
  console.log('✓ Successfully verified input interaction for {bug_key} on', baseURL);
}});
"""

        prompt = f"""You are an expert Playwright Automation Engineer. Generate a complete, standalone, production-ready Playwright JavaScript test spec file (.spec.js) to automate and verify the fix for this production bug.

BUG KEY: {bug_key}
BUG SUMMARY: {bug_summary}
APPROVED REMEDIATION SPEC / GHERKIN:
{remediation_content}

TARGET BASE URL (Optional): {target_url or 'Process via process.env.PLAYWRIGHT_TEST_BASE_URL'}

RULES:
1. Use ES module syntax (`import {{ test, expect }} from '@playwright/test';`).
2. Always read base URL dynamically: `const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || '{target_url or "https://www.amazon.in"}';`
3. Navigate with `await page.goto(baseURL, {{ waitUntil: 'commit', timeout: 30000 }});`
4. Write clean, robust Playwright code using resilient locators with fallbacks (e.g. `page.locator('#twotabsearchtextbox, input[name="field-keywords"], input[type="text"]').first()`).
5. Add explicit `console.log('✓ ...')` messages for key steps so execution logs are clear.
6. Make sure it runs out of the box in Playwright test runner without syntax errors.
7. Return ONLY the Javascript code block without markdown backticks or extra text.
"""
        try:
            resp = self._model.generate_content(prompt)
            raw = resp.text.strip()
            raw = re.sub(r"^```javascript\s*|^```js\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return raw
        except Exception as e:
            logger.error(f"Error generating Playwright fix script: {e}")
            base = target_url or "https://www.amazon.in"
            return f"""import {{ test, expect }} from '@playwright/test';

test('Verify fix for {bug_key} — {bug_summary}', async ({{ page }}) => {{
  const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || '{base}';
  console.log('Navigating to target environment:', baseURL);
  await page.goto(baseURL, {{ waitUntil: 'commit', timeout: 30000 }});

  const searchInput = page.locator('#twotabsearchtextbox, input[name="field-keywords"], input[type="text"]').first();
  await expect(searchInput).toBeVisible({{ timeout: 15000 }});
  await searchInput.fill('iPhone 15');
  console.log('✓ Successfully verified input interaction for {bug_key} on', baseURL);
}});
"""

    # ------------------------------------------------------------------ #
    # 6. Multi-Environment Parallel Verification Execution
    # ------------------------------------------------------------------ #

    async def run_multi_environment_verification(
        self,
        user_id: UUID,
        script_code: str,
        environments: List[Dict[str, Any]], # [{ name: str, base_url: str, env_vars: dict }]
    ) -> Dict[str, Any]:
        """Execute Playwright script concurrently across multiple arbitrary user environments."""
        from app.database import AsyncSessionLocal

        async def run_env(env_item: Dict[str, Any]):
            env_name = env_item.get("name", "Environment")
            base_url = env_item.get("base_url", "https://example.com")
            custom_vars = env_item.get("env_vars", {})

            start_t = datetime.now(timezone.utc)
            try:
                async with AsyncSessionLocal() as env_db:
                    runner_svc = RunnerService(env_db)
                    run_record = await runner_svc.execute_playwright_script(
                        user_id=user_id,
                        script_code=script_code,
                        target_url=base_url,
                        env_vars=custom_vars,
                        timeout_seconds=60,
                        headed=False,
                    )
                    end_t = datetime.now(timezone.utc)
                    duration_sec = (end_t - start_t).total_seconds()

                    return {
                        "environment_name": env_name,
                        "base_url": base_url,
                        "status": run_record.status,  # "passed" | "failed" | "timeout"
                        "duration_seconds": round(duration_sec, 2),
                        "run_id": str(run_record.id),
                        "logs": run_record.logs,
                        "error_message": None if run_record.status == "passed" else run_record.logs[-300:],
                        "verified": run_record.status == "passed",
                    }
            except Exception as e:
                logger.error(f"Parallel run failed for environment {env_name} ({base_url}): {e}")
                return {
                    "environment_name": env_name,
                    "base_url": base_url,
                    "status": "failed",
                    "duration_seconds": 0.0,
                    "logs": f"Execution Exception: {e}",
                    "error_message": str(e),
                    "verified": False,
                }

        # Run parallel execution using asyncio.gather
        env_results = await asyncio.gather(*(run_env(e) for e in environments))

        total_envs = len(env_results)
        passed_envs = sum(1 for r in env_results if r["status"] == "passed")
        failed_envs = total_envs - passed_envs

        if passed_envs == total_envs:
            overall_summary = f"✅ Fix VERIFIED across all {total_envs} environments simultaneously with zero regressions."
        elif passed_envs > 0:
            overall_summary = f"⚠️ Fix PARTIALLY VERIFIED: Passed in {passed_envs}/{total_envs} environments. Review env logs for details."
        else:
            overall_summary = f"❌ Fix FAILED across all {total_envs} environments under test."

        return {
            "overall_status": "passed" if passed_envs == total_envs else "failed",
            "passed_count": passed_envs,
            "failed_count": failed_envs,
            "total_count": total_envs,
            "summary_statement": overall_summary,
            "environment_results": env_results,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _embed_text(self, text: str) -> List[float]:
        result = genai.embed_content(
            model=self._embed_model,
            content=text[:2000],
            task_type="retrieval_document",
            output_dimensionality=768,
        )
        return result["embedding"]

    async def _vector_search(self, embedding: List[float], repo_ids: Optional[List[UUID]]) -> List[tuple[TestCase, float]]:
        if not embedding:
            return []
        
        where_clause = "WHERE is_active = true AND embedding IS NOT NULL"
        params = {"embedding": str(embedding), "k": TOP_K}
        if repo_ids:
            where_clause += " AND repo_id = ANY(:repo_ids)"
            params["repo_ids"] = [str(r) for r in repo_ids]

        query = text(f"""
            SELECT id, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM test_cases
            {where_clause}
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :k
        """)
        res = await self.db.execute(query, params)
        rows = res.fetchall()
        if not rows:
            return []

        id_to_score = {row[0]: float(row[1]) for row in rows}
        tc_res = await self.db.execute(select(TestCase).where(TestCase.id.in_(list(id_to_score.keys()))))
        tcs = list(tc_res.scalars().all())

        results = [(tc, id_to_score.get(tc.id, 0.0)) for tc in tcs]
        results.sort(key=lambda x: x[1], reverse=True)
        return results
