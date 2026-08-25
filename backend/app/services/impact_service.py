"""Impact Analysis Service — Phase 3 (read-only suggestions).

Flow per story:
1. Ensure story has an embedding (generate if missing)
2. Vector similarity search → top-N candidate test cases
3. Gemini LLM reasoning → Impacted / Not Impacted / Coverage Gap
4. Persist results to impact_analysis_runs + test_change_proposals
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import google.generativeai as genai
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.jira import Story
from app.models.github import GitHubRepo, TestCase
from app.models.analysis import ImpactAnalysisRun, TestChangeProposal

logger = logging.getLogger(__name__)

TOP_K = 15          # vector candidates per story
MIN_SIMILARITY = 0.3  # cosine similarity threshold


class ImpactService:
    def __init__(self, db: AsyncSession):
        self.db = db
        settings = get_settings()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self._embed_model = settings.GEMINI_EMBEDDING_MODEL

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #

    async def run_impact_analysis(
        self,
        user_id: UUID,
        story_ids: list[UUID],
        repo_ids: list[UUID],
    ) -> ImpactAnalysisRun:
        """Create an analysis run, perform analysis, persist proposals."""
        run = ImpactAnalysisRun(
            user_id=user_id,
            status="running",
            story_ids=[str(s) for s in story_ids],
            repo_ids=[str(r) for r in repo_ids],
        )
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)

        try:
            results = await self._analyse(run.id, story_ids, repo_ids, user_id)
            run.results = results
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.progress_pct = 100
        except Exception as e:
            logger.exception(f"Impact analysis run {run.id} failed: {e}")
            run.status = "failed"
            run.error_message = str(e)

        await self.db.flush()
        return run

    async def get_run(self, run_id: UUID, user_id: UUID) -> Optional[ImpactAnalysisRun]:
        result = await self.db.execute(
            select(ImpactAnalysisRun).where(
                ImpactAnalysisRun.id == run_id,
                ImpactAnalysisRun.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_runs(self, user_id: UUID) -> list[ImpactAnalysisRun]:
        result = await self.db.execute(
            select(ImpactAnalysisRun)
            .where(ImpactAnalysisRun.user_id == user_id)
            .order_by(ImpactAnalysisRun.created_at.desc())
            .limit(20)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    # Core analysis
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Core analysis
    # ------------------------------------------------------------------ #

    async def _analyse(
        self,
        run_id: UUID,
        story_ids: list[UUID],
        repo_ids: list[UUID],
        user_id: UUID,
    ) -> dict:
        all_results = []

        for story_id in story_ids:
            # Load story
            s_result = await self.db.execute(select(Story).where(Story.id == story_id))
            story = s_result.scalar_one_or_none()
            if not story:
                continue

            # Always construct full combined text: Title + Description + Acceptance Criteria
            story_text = (
                f"Title: {story.summary}\n"
                f"Description: {story.description_text or story.description or ''}\n"
                f"Acceptance Criteria: {story.acceptance_criteria or ''}"
            )
            logger.info(f"[Impact Analysis] Generating embedding for Story '{story.jira_issue_key}' ({story.summary[:40]}...)")
            story.embedding = await self._embed(story_text)
            await self.db.flush()

            # Vector search across selected repos — returns list of (TestCase, similarity_score)
            candidates_with_scores = await self._vector_search(story.embedding, repo_ids)

            if not candidates_with_scores:
                all_results.append({
                    "story_id": str(story_id),
                    "story_key": story.jira_issue_key,
                    "story_summary": story.summary,
                    "impacted": [],
                    "missing_coverage": [],
                    "unaffected": [],
                    "gaps": [{
                        "scenario": f"No indexed test cases found in selected repos for {story.jira_issue_key}.",
                        "suggested_filename": f"tests/{story.jira_issue_key.lower()}_spec.ts",
                        "suggested_test": "// Proposed test stub for new feature domain"
                    }],
                })
                continue

            # LLM reasoning 2nd-pass with standardized two-level taxonomy
            reasoning = await self._gemini_impact_reasoning(story, candidates_with_scores)

            verdicts = reasoning.get("verdicts", [])
            not_covered = reasoning.get("not_covered", {"is_not_covered": False})

            # Helper bucket collections for backward compatibility & UI rendering
            impacted = []
            missing_coverage = []
            unaffected = []
            gaps = []

            if not_covered.get("is_not_covered"):
                pf = not_covered.get("proposed_file") or {}
                gaps.append({
                    "scenario": not_covered.get("rationale") or f"No existing coverage for {story.jira_issue_key}",
                    "suggested_filename": pf.get("suggested_filename", f"features/{story.jira_issue_key.lower()}_spec.feature"),
                    "suggested_test": pf.get("suggested_content", "# Draft test suite")
                })
                # Persist proposal for NOT_COVERED
                proposal = TestChangeProposal(
                    run_id=run_id,
                    story_id=story.id,
                    test_case_id=None,
                    proposal_type="create",
                    original_content=None,
                    proposed_content=pf.get("suggested_content", ""),
                    rationale=not_covered.get("rationale", ""),
                    confidence=0.95,
                    approval_status="pending",
                )
                self.db.add(proposal)

            for v in verdicts:
                tc = next((c for c, _ in candidates_with_scores if c.file_path == v.get("file_path") or c.title == v.get("test_title")), None)
                verdict_type = v.get("verdict")
                sub_tag = v.get("sub_tag")
                prop_change = v.get("proposed_change") or {}

                if verdict_type == "IMPACTED":
                    if sub_tag == "NEEDS_UPDATE":
                        impacted.append({
                            "test_title": v.get("test_title"),
                            "file_path": v.get("file_path"),
                            "rationale": v.get("rationale"),
                            "confidence": v.get("confidence", 0.9),
                            "sub_tag": "NEEDS_UPDATE",
                            "suggested_change": prop_change.get("updated_scenario", ""),
                            "original_scenario": prop_change.get("original_scenario", ""),
                            "file_raw_content": tc.raw_content if tc else "",
                        })
                        proposal = TestChangeProposal(
                            run_id=run_id,
                            story_id=story.id,
                            test_case_id=tc.id if tc else None,
                            proposal_type="modify",
                            original_content=prop_change.get("original_scenario") or (tc.raw_content if tc else None),
                            proposed_content=prop_change.get("updated_scenario", ""),
                            rationale=v.get("rationale", ""),
                            confidence=v.get("confidence", 0.9),
                            approval_status="pending",
                        )
                        self.db.add(proposal)

                    elif sub_tag == "NEEDS_EXTENSION":
                        missing_coverage.append({
                            "test_title": v.get("test_title"),
                            "file_path": v.get("file_path"),
                            "rationale": v.get("rationale"),
                            "confidence": v.get("confidence", 0.9),
                            "sub_tag": "NEEDS_EXTENSION",
                            "suggested_scenarios": [prop_change.get("new_scenarios", "")],
                            "file_raw_content": tc.raw_content if tc else "",
                        })
                        proposal = TestChangeProposal(
                            run_id=run_id,
                            story_id=story.id,
                            test_case_id=tc.id if tc else None,
                            proposal_type="add_scenario",
                            original_content=tc.raw_content if tc else None,
                            proposed_content=prop_change.get("new_scenarios", ""),
                            rationale=v.get("rationale", ""),
                            confidence=v.get("confidence", 0.9),
                            approval_status="pending",
                        )
                        self.db.add(proposal)

                elif verdict_type == "NOT_IMPACTED":
                    unaffected.append({
                        "test_title": v.get("test_title"),
                        "file_path": v.get("file_path"),
                        "rationale": v.get("rationale"),
                        "confidence": v.get("confidence", 1.0),
                    })

            await self.db.flush()

            all_results.append({
                "story_id": str(story_id),
                "story_key": story.jira_issue_key,
                "story_summary": story.summary,
                "verdicts": verdicts,
                "not_covered": not_covered,
                "impacted": impacted,
                "missing_coverage": missing_coverage,
                "unaffected": unaffected,
                "gaps": gaps,
            })

        return {"stories": all_results}

    async def _vector_search(self, embedding: list[float], repo_ids: list[UUID]) -> list[tuple[TestCase, float]]:
        """Cosine similarity search via pgvector. Returns list of (TestCase, similarity_score)."""
        if not embedding:
            return []
        repo_id_strs = [str(r) for r in repo_ids]
        query = text("""
            SELECT id, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM test_cases
            WHERE repo_id = ANY(:repo_ids)
              AND is_active = true
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :k
        """)
        result = await self.db.execute(query, {
            "repo_ids": repo_id_strs,
            "embedding": str(embedding),
            "k": TOP_K,
        })
        rows = result.fetchall()
        if not rows:
            return []

        id_to_score = {row[0]: float(row[1]) for row in rows}
        tc_result = await self.db.execute(select(TestCase).where(TestCase.id.in_(list(id_to_score.keys()))))
        tcs = list(tc_result.scalars().all())

        candidates_with_scores = []
        for tc in tcs:
            score = id_to_score.get(tc.id, 0.0)
            candidates_with_scores.append((tc, score))
            logger.info(
                f"[Vector Search Match] Story Candidate -> File: '{tc.file_path}' | Title: '{tc.title}' | Cosine Similarity Score: {score:.4f}"
            )

        candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
        return candidates_with_scores

    async def _gemini_impact_reasoning(
        self, story: Story, candidates_with_scores: list[tuple[TestCase, float]]
    ) -> dict:
        candidates_text = "\n".join(
            f"{i+1}. [File: {tc.file_path}] [Title: {tc.title}] [Type: {tc.test_type}] [Vector Similarity: {score:.4f}]\n"
            f"   Full Scenario/File Content:\n{tc.raw_content}\n"
            for i, (tc, score) in enumerate(candidates_with_scores)
        )

        prompt = f"""You are a Lead QA Architect performing strict Test Impact Analysis for a user story using a standardized two-level verdict taxonomy.

USER STORY:
Key: {story.jira_issue_key}
Summary: {story.summary}
Description: {story.description_text or story.description or 'N/A'}
Acceptance Criteria: {story.acceptance_criteria or 'N/A'}

CANDIDATE TEST CASES (Retrieved from Repository):
{candidates_text}

===========================================================
TAXONOMY SPECIFICATION
===========================================================

LEVEL 1 — Top-Level Verdict per Candidate Test File/Scenario (Mutually Exclusive):

1. "NOT_IMPACTED"
   - The test case has no meaningful relationship to the story, OR it ALREADY fully covers all requirements described in the story without needing any scenario edits or additions.
   - sub_tag MUST be null. proposed_change MUST be null.

2. "IMPACTED"
   - The test case's file IS the correct functional domain for this story, AND something about it needs to change or be added.
   - MUST carry exactly one Level 2 sub-tag:

     a. "NEEDS_UPDATE":
        - An existing scenario in the file encodes an assumption that this story's acceptance criteria CONTRADICTS or CHANGES (e.g. an existing scenario assumes single-value behavior such as applying a single promo code, and the story introduces multi-value behavior such as stacking multiple promo codes).
        - To determine this, ask yourself: "Does any existing scenario make an assumption that this story's acceptance criteria contradicts or changes?" If YES, classify as NEEDS_UPDATE.
        - Show the specific existing scenario text modified (original_scenario vs updated_scenario).

     b. "NEEDS_EXTENSION":
        - The file is the correct functional domain, but has ZERO scenarios covering this new sub-behavior the story introduces. All existing scenarios in the file remain valid and untouched.
        - Classify as NEEDS_EXTENSION if the story describes new behavior with no contradicting existing scenario.
        - Provide new scenario(s) to append (new_scenarios).

3. "NOT_COVERED" (Story-Level Absence):
   - No candidate test case anywhere in the repository touches this story's domain at all (e.g., story is about product reviews and no file in the repo relates to product reviews).
   - If no candidate file matches the domain, set "not_covered" with is_not_covered: true and propose a brand-new test file.

===========================================================
OUTPUT JSON SCHEMA
===========================================================

Return ONLY valid JSON matching this exact structure:
{{
  "verdicts": [
    {{
      "file_path": "<file_path>",
      "test_title": "<exact title of candidate test case>",
      "verdict": "IMPACTED" | "NOT_IMPACTED",
      "sub_tag": "NEEDS_UPDATE" | "NEEDS_EXTENSION" | null,
      "rationale": "<detailed architectural rationale>",
      "confidence": 0.95,
      "proposed_change": {{
        "type": "edit_scenario" | "add_scenario",
        "target_scenario_title": "<scenario title being edited or appended to>",
        "original_scenario": "<exact existing scenario text before modification (for edit_scenario)>",
        "updated_scenario": "<complete proposed modified scenario text (for edit_scenario)>",
        "new_scenarios": "<proposed new Gherkin scenario(s) to append (for add_scenario)>"
      }}
    }}
  ],
  "not_covered": {{
    "is_not_covered": false | true,
    "story_domain": "<domain name if not covered, e.g. Product Reviews and Ratings>",
    "rationale": "<why no existing test file covers this domain>",
    "proposed_file": {{
      "suggested_filename": "features/amazon_product_reviews.feature",
      "suggested_content": "Feature: Product Reviews and Star Ratings\n\n  Scenario: Verified buyer submits a valid review\n    Given..."
    }}
  }}
}}

CRITICAL CLASSIFICATION RULES:
- Enforce strict mutual exclusivity for Level 1 verdicts.
- "NEEDS_UPDATE": If an existing scenario tests a single-item/single-option behavior (such as "Apply a valid promotional code at checkout") and the story generalizes or changes that behavior to multi-item/stacking (such as "User can stack multiple promotional codes at checkout"), classify that specific existing scenario as IMPACTED with sub_tag NEEDS_UPDATE. Show the original_scenario updated to incorporate the new criteria.
- "NEEDS_EXTENSION": If an existing file matches the domain (e.g. amazon_login.feature) but has ZERO scenarios for a completely new feature (e.g. 2FA authentication), classify as IMPACTED with sub_tag NEEDS_EXTENSION. Do NOT modify any existing login scenario text; provide new scenario(s) to append.
- "NOT_IMPACTED": If existing scenarios ALREADY fully cover the story acceptance criteria without requiring any scenario edits or additions (e.g. shopping cart management operations that are already tested), classify as NOT_IMPACTED.
- "NOT_COVERED": If NO candidate test file in the repository touches the story's functional domain at all (e.g. Product Reviews & Ratings), set not_covered.is_not_covered: true and propose a brand-new test file.
"""

        logger.info(f"[LLM 2nd-Pass Reasoning] Sending Prompt to Gemini for {story.jira_issue_key}...")
        resp = self._model.generate_content(prompt)
        raw = resp.text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        
        logger.info(f"[Gemini Reasoning Response Raw Output for {story.jira_issue_key}]:\n{raw}")

        try:
            parsed = json.loads(raw)
            verdicts = parsed.get("verdicts", [])
            not_covered = parsed.get("not_covered", {"is_not_covered": False})

            # Logging detailed verdict classification per requirement 5
            for v in verdicts:
                logger.info(
                    f"[TAXONOMY VERDICT] Story: {story.jira_issue_key} | File: {v.get('file_path')} | "
                    f"Verdict: {v.get('verdict')} | Sub-Tag: {v.get('sub_tag')} | Rationale: {v.get('rationale')}"
                )
            if not_covered.get("is_not_covered"):
                logger.info(
                    f"[TAXONOMY VERDICT] Story: {story.jira_issue_key} | Verdict: NOT_COVERED | "
                    f"Domain: {not_covered.get('story_domain')} | Rationale: {not_covered.get('rationale')}"
                )

            return {
                "verdicts": verdicts,
                "not_covered": not_covered,
            }
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse Gemini response for {story.jira_issue_key}: {raw[:300]}")
            return {
                "verdicts": [],
                "not_covered": {"is_not_covered": False},
            }

    async def _embed(self, text: str) -> list[float]:
        result = genai.embed_content(
            model=self._embed_model,
            content=text[:2000],
            task_type="retrieval_document",
            output_dimensionality=768,
        )
        return result["embedding"]
