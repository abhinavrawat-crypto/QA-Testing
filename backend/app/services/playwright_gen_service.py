"""Playwright Code Generation and PR Automation Service.

Uses Gemini to generate production-ready TypeScript/JavaScript Playwright test scripts from JIRA stories and test gap proposals.
Interfaces with GitHubService to branch, commit, and create Pull Requests.
"""
import logging
import re
from typing import Dict, Any, Optional
from uuid import UUID

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.models.jira import Story
from app.models.github import TestCase, GitHubRepo
from app.models.connections import GitHubConnection
from app.services.github_service import GitHubService

logger = logging.getLogger(__name__)


class PlaywrightGenService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gh_svc = GitHubService(db)
        settings = get_settings()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)

    async def generate_playwright_test(
        self,
        story_id: UUID,
        original_test_content: Optional[str] = None,
        scenario_description: Optional[str] = None,
        target_file_path: Optional[str] = None,
        language: str = "typescript",
        target_url: Optional[str] = None,
    ) -> Dict[str, str]:
        """Generate Playwright test code for a story change or coverage gap."""
        result = await self.db.execute(select(Story).where(Story.id == story_id))
        story = result.scalar_one_or_none()
        if not story:
            raise ValueError("Story not found")

        ext = ".spec.ts" if language == "typescript" else ".spec.js"
        lang_str = "TypeScript" if language == "typescript" else "JavaScript"
        
        target_domain_context = ""
        if target_url:
            target_domain_context = f"\nTARGET APPLICATION DOMAIN: {target_url}\n"

        prompt = f"""You are a Principal Test Automation Engineer specializing in Playwright ({lang_str}).

JIRA REQUIREMENT:
Issue Key: {story.jira_issue_key}
Summary: {story.summary}
Description: {story.description_text or "N/A"}
Acceptance Criteria:
{story.acceptance_criteria or "N/A"}
{target_domain_context}
CONTEXT:
Target File: {target_file_path or f"tests/generated{ext}"}
New / Modified / Extension Scenarios to Cover:
{scenario_description or "Implement end-to-end automated test matching story acceptance criteria."}

EXISTING FILE CONTENT & SCENARIOS (IF ANY):
{original_test_content or "// New test file suite"}

CRITICAL INSTRUCTIONS FOR COMPLETE FUNCTIONAL SCRIPT GENERATION:
1. Generate a COMPLETE, standalone, and 100% executable Playwright {lang_str} test file (`@playwright/test`).
2. DO NOT output partial code snippets, missing functions, or placeholder TODO comments.
3. ABSOLUTELY NO HARDCODED DUMMY/FAKE DOMAINS:
   - NEVER hardcode fake external URLs like `https://www.e-commerce-demo.com` or `https://example.com`.
   - Always use relative paths for page navigation (e.g., `page.goto('/account/payments')` or `page.goto('/')`) relying on Playwright's `baseURL` config.
4. DYNAMIC DOMAIN-AWARE LOCATORS & REGIONAL CONVENTIONS:
   - Dynamically analyze the target application domain provided in `TARGET APPLICATION DOMAIN` (if specified).
   - Tailor locators, HTML attributes (`id`, `name`, `class`, `type`, ARIA roles), and DOM selectors specifically for the target domain's real-world structure.
   - Prefer simple, resilient, high-clarity locators (e.g. `page.locator('a, label, span').filter({{ hasText: /Sony/i }}).first()`). Avoid over-constrained, deeply nested selector chains.
   - Dynamically infer currency symbols (e.g. ₹ for `.in`, $ for `.com`, € for `.eu`), regional price scales (e.g. ₹500–₹5000 for `.in` vs $20–$200 for `.com`), and domain-specific UI patterns directly from the target domain URL.
   - NEVER rely on generic fake test IDs (such as `[data-testid="search-results"]` or `[data-testid="product-price"]`) unless they represent standard HTML or real-world targets.
5. ASYNCHRONOUS SYNCHRONIZATION & DEFENSIVE FILTER HANDLING:
   - Always wait for DOM/navigation completion or element visibility after clicks/searches (e.g. `await expect(results.first()).toBeVisible()` or `await page.waitForLoadState('domcontentloaded')`).
   - For dynamic or optional UI refinements (e.g., sidebar brand checkboxes, price sliders, category filters), check visibility defensively before clicking: `if (await filterLocator.first().isVisible()) {{ await filterLocator.first().click(); }}`. Avoid hard-failing assertions (`toBeVisible()`) on optional sidebar facets.
   - Perform defensive checks before iterating lists: verify `if (await items.count() > 0)` before running element loops to prevent index out of range errors.
6. PLAYWRIGHT STRICT MODE COMPLIANCE:
   - When using multi-selectors or element lists, ALWAYS append `.first()` (e.g., `await searchButton.first().click()`) to resolve Playwright strict mode violations when multiple elements match.
   - For search input forms, prefer `await searchInput.press('Enter')` or `await searchButton.first().click()` for 100% reliable submission.
7. INCORPORATE ALL EXISTING SCENARIOS:
   - For an EXTENSION: Keep ALL existing test cases in the file intact AND append the new extension test case(s) recommended for issue `{story.jira_issue_key}` within the same `test.describe` suite.
   - For an UPDATE: Modify/update the target existing test scenario to reflect the new requirements while retaining all other existing test cases in the file intact.
   - For a NEW FILE: Generate full runnable test cases for all proposed scenarios.
8. Use proper `test.describe(...)`, `test(...)`, and explicit `await expect(...)` assertions.
9. Include header documentation comments referencing JIRA Issue `{story.jira_issue_key}`.

Return ONLY a JSON object with this exact format:
{{
  "file_path": "<target relative file path>",
  "generated_code": "<FULL COMPLETE standalone Playwright test spec code>",
  "explanation": "<short summary of locator choices and test setup>"
}}
"""

        resp = self._model.generate_content(prompt)
        raw = resp.text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        
        try:
            import json
            data = json.loads(raw)
            return data
        except Exception as e:
            logger.error(f"Failed to parse Playwright code generation response: {e}\nRaw: {raw}")
            return {
                "file_path": target_file_path or "tests/generated.spec.ts",
                "generated_code": f"// Generated for {story.jira_issue_key}\nimport {{ test, expect }} from '@playwright/test';\n\ntest('{story.summary}', async ({{ page }}) => {{\n  // TODO: Implement scenario\n}});\n",
                "explanation": "Fallback template generated due to formatting error."
            }

    async def create_pull_request_for_test(
        self,
        user_id: UUID,
        connection_id: UUID,
        repo_full_name: str,
        file_path: str,
        file_content: str,
        jira_issue_key: str,
        branch_prefix: str = "aiqa/test-update",
        draft: bool = False,
        custom_pr_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Human-approved step: Creates a branch, commits test code, and opens a GitHub PR."""
        conn = await self.gh_svc._get_connection(user_id, connection_id)
        default_sha = await self.gh_svc.get_default_branch_sha(conn, repo_full_name)
        
        # Get default branch name
        async with self.gh_svc._client(conn) as client:
            r = await client.get(f"{conn.api_base_url}/repos/{repo_full_name}")
            r.raise_for_status()
            base_branch = r.json().get("default_branch", "main")

        # Create unique branch name
        sanitized_key = re.sub(r"[^a-zA-Z0-9_-]", "-", jira_issue_key.lower())
        import time
        branch_name = f"{branch_prefix}/{sanitized_key}-{int(time.time())}"

        # 1. Create branch
        await self.gh_svc.create_branch(
            user_id=user_id,
            connection_id=connection_id,
            full_name=repo_full_name,
            branch_name=branch_name,
            from_sha=default_sha,
        )

        # 2. Check if file already exists on branch to supply existing sha
        existing_sha = None
        try:
            async with self.gh_svc._client(conn) as client:
                res = await client.get(
                    f"{conn.api_base_url}/repos/{repo_full_name}/contents/{file_path}",
                    params={"ref": branch_name},
                )
                if res.status_code == 200:
                    existing_sha = res.json().get("sha")
        except Exception:
            pass

        # 3. Commit file
        commit_msg = f"test(aiqa): Automated test update for {jira_issue_key}\n\nGenerated by AI QA Platform."
        await self.gh_svc.commit_file(
            user_id=user_id,
            connection_id=connection_id,
            full_name=repo_full_name,
            branch_name=branch_name,
            file_path=file_path,
            content=file_content,
            commit_message=commit_msg,
            existing_sha=existing_sha,
        )

        # 4. Open Pull Request
        pr_title = custom_pr_title or f"test({jira_issue_key}): Automated Playwright test updates"
        pr_body = (
            f"## 🤖 AI QA Platform — Automated Test PR\n\n"
            f"**JIRA Issue:** `{jira_issue_key}`\n"
            f"**Target File:** `{file_path}`\n\n"
            f"### Summary of Changes\n"
            f"- Generated or updated automated Playwright spec for issue acceptance criteria.\n"
            f"- Reviewed and approved by user.\n\n"
            f"```ts\n"
            f"{file_content[:500]}\n"
            f"// ... (see full file diff)\n"
            f"```\n\n"
            f"*Please run automated CI test suite before merging.*"
        )

        pr_info = await self.gh_svc.create_pull_request(
            user_id=user_id,
            connection_id=connection_id,
            full_name=repo_full_name,
            head_branch=branch_name,
            base_branch=base_branch,
            title=pr_title,
            body=pr_body,
            draft=draft,
        )

        return pr_info
