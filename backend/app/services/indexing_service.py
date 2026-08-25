"""Test Indexing Service.

Orchestrates:
1. Fetching files from GitHub repos (via GitHubService)
2. Parsing with dual pipelines (Gherkin + Playwright)
3. Generating Gemini embeddings
4. Upserting into test_cases with pgvector
5. Incremental updates via commit SHA diff
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

import google.generativeai as genai

from app.config import get_settings
from app.models.github import GitHubRepo, TestCase
from app.models.connections import GitHubConnection
from app.services.github_service import GitHubService
from app.services.parsers import (
    parse_gherkin, scenarios_to_index_items,
    parse_playwright, tests_to_index_items,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".feature": "gherkin",
    ".gherkin": "gherkin",
    ".spec.ts": "playwright_spec",
    ".spec.js": "playwright_spec",
    ".spec.tsx": "playwright_spec",
    ".spec.jsx": "playwright_spec",
    ".test.ts": "playwright_spec",
    ".test.js": "playwright_spec",
    ".test.tsx": "playwright_spec",
    ".test.jsx": "playwright_spec",
}


def _detect_type(path: str) -> Optional[str]:
    path_lower = path.lower()
    for ext, t in SUPPORTED_EXTENSIONS.items():
        if path_lower.endswith(ext):
            return t
    if any(folder in path_lower for folder in ["/features/", "/specs/", "/tests/", "/e2e/"]):
        if path_lower.endswith(".feature"):
            return "gherkin"
        if path_lower.endswith((".ts", ".js", ".tsx", ".jsx")):
            return "playwright_spec"
    return None


class IndexingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gh_svc = GitHubService(db)
        settings = get_settings()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._embed_model = settings.GEMINI_EMBEDDING_MODEL

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def index_repo(
        self, user_id: UUID, connection_id: UUID, repo_id: UUID
    ) -> dict:
        """Full or incremental index of a GitHub repo. Returns indexing stats."""
        conn = await self._get_connection(connection_id, user_id)
        repo = await self._get_repo(repo_id)

        # Fetch current HEAD SHA
        head_sha = await self.gh_svc.get_default_branch_sha(conn, repo.full_name)

        # Check existing indexed test cases count in DB
        res = await self.db.execute(
            select(func.count(TestCase.id)).where(
                TestCase.repo_id == repo.id, TestCase.is_active.is_(True)
            )
        )
        tc_count = res.scalar() or 0

        # Skip if already up to date AND test cases exist in DB
        if repo.last_indexed_commit == head_sha and tc_count > 0:
            return {"status": "up_to_date", "repo": repo.full_name, "sha": head_sha}

        # Fetch full tree
        tree = await self.gh_svc.list_tree(conn, repo.full_name, sha=head_sha)
        test_files = [
            item for item in tree
            if item.get("type") == "blob" and _detect_type(item.get("path", ""))
        ]

        stats = {"indexed": 0, "skipped": 0, "errors": 0}

        for file_item in test_files:
            path = file_item["path"]
            file_sha = file_item.get("sha", "")
            test_type = _detect_type(path)

            try:
                content = await self.gh_svc.get_file_content(conn, repo.full_name, path, head_sha)
                items = self._parse_file(content, path, test_type, head_sha)

                for item in items:
                    await self._upsert_test_case(repo.id, item)
                    stats["indexed"] += 1

            except Exception as e:
                logger.warning(f"Failed to index {path}: {e}")
                stats["errors"] += 1

        # Mark inactive test cases from old commits
        await self._deactivate_stale(repo.id, head_sha)

        # Update repo's last indexed commit
        repo.last_indexed_commit = head_sha
        repo.last_synced_at = datetime.now(timezone.utc)
        await self.db.commit()

        return {"status": "indexed", "repo": repo.full_name, "sha": head_sha, **stats}

    async def get_indexed_stats(self, repo_id: UUID) -> dict:
        from sqlalchemy import func
        result = await self.db.execute(
            select(TestCase.test_type, TestCase.id)
            .where(TestCase.repo_id == repo_id, TestCase.is_active.is_(True))
        )
        rows = result.all()
        return {
            "total": len(rows),
            "gherkin": sum(1 for r in rows if r[0] == "gherkin"),
            "playwright_spec": sum(1 for r in rows if r[0] == "playwright_spec"),
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _parse_file(self, content: str, path: str, test_type: str, commit_sha: str) -> list:
        if test_type == "gherkin":
            feature = parse_gherkin(content)
            return scenarios_to_index_items(feature, path, commit_sha)
        elif test_type == "playwright_spec":
            tests = parse_playwright(content)
            return tests_to_index_items(tests, path, commit_sha)
        return []

    async def _upsert_test_case(self, repo_id: UUID, item: dict) -> None:
        # Generate embedding
        embed_text = item.pop("embed_text", item["raw_content"])[:2000]
        try:
            result = genai.embed_content(
                model=self._embed_model,
                content=embed_text,
                task_type="retrieval_document",
                output_dimensionality=768,
            )
            embedding = result["embedding"]
        except Exception as e:
            logger.warning(f"Embedding failed for '{item['title']}': {e}")
            embedding = None

        # Check if exists
        existing = await self.db.execute(
            select(TestCase).where(
                and_(
                    TestCase.repo_id == repo_id,
                    TestCase.file_path == item["file_path"],
                    TestCase.title == item["title"],
                )
            )
        )
        tc = existing.scalar_one_or_none()
        if tc is None:
            tc = TestCase(repo_id=repo_id)
            self.db.add(tc)

        tc.file_path = item["file_path"]
        tc.test_type = item["test_type"]
        tc.feature_name = item.get("feature_name")
        tc.title = item["title"]
        tc.description = item.get("description")
        tc.steps = item.get("steps")
        tc.tags = item.get("tags", [])
        tc.raw_content = item["raw_content"]
        tc.embedding = embedding
        tc.commit_sha = item["commit_sha"]
        tc.is_active = True

        await self.db.flush()

    async def _deactivate_stale(self, repo_id: UUID, current_sha: str) -> None:
        """Mark test cases from previous commits as inactive."""
        result = await self.db.execute(
            select(TestCase).where(
                and_(TestCase.repo_id == repo_id, TestCase.commit_sha != current_sha)
            )
        )
        for tc in result.scalars().all():
            tc.is_active = False
        await self.db.flush()

    async def _get_connection(self, connection_id: UUID, user_id: UUID) -> GitHubConnection:
        result = await self.db.execute(
            select(GitHubConnection).where(
                GitHubConnection.id == connection_id,
                GitHubConnection.user_id == user_id,
                GitHubConnection.is_active.is_(True),
            )
        )
        conn = result.scalar_one_or_none()
        if not conn:
            raise ValueError("GitHub connection not found")
        return conn

    async def _get_repo(self, repo_id: UUID) -> GitHubRepo:
        result = await self.db.execute(select(GitHubRepo).where(GitHubRepo.id == repo_id))
        repo = result.scalar_one_or_none()
        if not repo:
            raise ValueError("Repo not found")
        return repo
