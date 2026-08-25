"""Story Discovery Engine (Feature C).

Finds test cases in GitHub repos that lack matching JIRA stories.
Uses pgvector semantic similarity to match test cases against existing JIRA stories.
For unmatched test cases, uses Gemini to draft INVEST-compliant JIRA user stories with Gherkin AC.
Provides human-in-the-loop approval to create issues directly in JIRA.
"""
import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional
from uuid import UUID

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.config import get_settings
from app.models.github import TestCase
from app.models.jira import Story, JiraProject
from app.services.jira_service import JiraService

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.5  # Cosine distance cutoff for "matched" story


class DiscoveryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        settings = get_settings()
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model = genai.GenerativeModel(settings.GEMINI_MODEL)
        self._embed_model = settings.GEMINI_EMBEDDING_MODEL

    async def discover_unmatched_tests(
        self,
        user_id: UUID,
        repo_ids: List[UUID],
        similarity_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Find active test cases across repos and search for matching JIRA stories."""
        # Load active test cases
        result = await self.db.execute(
            select(TestCase).where(
                TestCase.repo_id.in_(repo_ids),
                TestCase.is_active.is_(True),
            )
        )
        test_cases = list(result.scalars().all())

        # Ensure all test cases have embeddings first, concurrently
        embedding_tasks = []
        tc_to_embed = []
        for tc in test_cases:
            if tc.embedding is None:
                tc_to_embed.append(tc)
                embedding_tasks.append(self._embed(f"{tc.title} {tc.raw_content}"))
        
        if embedding_tasks:
            embeddings = await asyncio.gather(*embedding_tasks)
            for tc, emb in zip(tc_to_embed, embeddings):
                tc.embedding = emb
            await self.db.flush()

        discovered_results = []
        discovered_draft_tasks = []
        unmatched_tcs = []

        for tc in test_cases:
            # Vector search for nearest JIRA stories
            nearest_stories = await self._find_nearest_stories(tc.embedding)

            matched_story = None
            highest_similarity = 0.0

            if nearest_stories:
                top_story, dist = nearest_stories[0]
                similarity = 1.0 - dist
                if similarity >= similarity_threshold:
                    matched_story = top_story
                    highest_similarity = similarity

            if matched_story:
                discovered_results.append({
                    "test_case_id": str(tc.id),
                    "test_title": tc.title,
                    "file_path": tc.file_path,
                    "test_type": tc.test_type,
                    "status": "matched",
                    "matched_story_key": matched_story.jira_issue_key,
                    "matched_story_summary": matched_story.summary,
                    "similarity_score": round(highest_similarity, 2),
                    "draft_story": None,
                })
            else:
                unmatched_tcs.append((tc, round(highest_similarity, 2) if nearest_stories else 0.0))
                discovered_draft_tasks.append(self._draft_jira_story(tc))

        # Concurrently generate AI draft stories for unmatched tests
        if discovered_draft_tasks:
            drafts = await asyncio.gather(*discovered_draft_tasks)
            for (tc, similarity_score), draft in zip(unmatched_tcs, drafts):
                discovered_results.append({
                    "test_case_id": str(tc.id),
                    "test_title": tc.title,
                    "file_path": tc.file_path,
                    "test_type": tc.test_type,
                    "status": "unmatched",
                    "matched_story_key": None,
                    "matched_story_summary": None,
                    "similarity_score": similarity_score,
                    "draft_story": draft,
                })

        return discovered_results

    async def create_story_in_jira(
        self,
        user_id: UUID,
        connection_id: UUID,
        project_key: str,
        summary: str,
        description: str,
        acceptance_criteria: str,
        issue_type: str = "Story",
    ) -> Dict[str, Any]:
        """Human-in-the-loop step: Create approved draft story directly in JIRA."""
        jira_svc = JiraService(self.db)
        
        issue_data = await jira_svc.create_issue(
            user_id=user_id,
            connection_id=connection_id,
            project_key=project_key,
            summary=summary,
            description=description,
            ac=acceptance_criteria,
            issue_type=issue_type,
        )

        # Sync the newly created issue to local Story database cache for vector discovery
        proj_result = await self.db.execute(
            select(JiraProject).where(
                JiraProject.connection_id == connection_id,
                JiraProject.project_key == project_key,
            )
        )
        project = proj_result.scalars().first()

        if project and issue_data.get("key"):
            new_story = Story(
                project_id=project.id,
                jira_issue_id=issue_data.get("id") or issue_data.get("key"),
                jira_issue_key=issue_data.get("key"),
                summary=summary,
                description_text=description,
                acceptance_criteria=acceptance_criteria,
                issue_type=issue_type,
                status="To Do",
            )
            # Embed content
            story_content = f"{summary} {description} {acceptance_criteria}"
            new_story.embedding = await self._embed(story_content)
            self.db.add(new_story)
            await self.db.commit()

        return issue_data

    async def _find_nearest_stories(self, embedding: List[float]) -> List[tuple[Story, float]]:
        if not embedding:
            return []
        query = text("""
            SELECT id, embedding <=> CAST(:embedding AS vector) as dist
            FROM stories
            WHERE embedding IS NOT NULL
            ORDER BY dist ASC
            LIMIT 3
        """)
        result = await self.db.execute(query, {"embedding": str(embedding)})
        rows = result.fetchall()
        if not rows:
            return []
        
        story_ids = [r[0] for r in rows]
        dist_map = {r[0]: r[1] for r in rows}
        
        s_result = await self.db.execute(select(Story).where(Story.id.in_(story_ids)))
        stories = s_result.scalars().all()
        return [(s, dist_map[s.id]) for s in stories]

    async def _draft_jira_story(self, tc: TestCase) -> Dict[str, str]:
        prompt = f"""You are a Product Owner creating a formal JIRA User Story for an automated test case that currently has no documented requirement.

TEST CASE TITLE: {tc.title}
FILE PATH: {tc.file_path}
TEST CONTENT:
{tc.raw_content[:1500]}

Generate a high-quality INVEST-compliant user story.
Return ONLY valid JSON with this exact structure:
{{
  "summary": "<concise As a / I want / So that user story title>",
  "description": "<detailed description stating user role, intent, context, and business value>",
  "acceptance_criteria": "<Gherkin Given/When/Then acceptance criteria covering happy path and edge cases>"
}}
"""
        resp = await asyncio.to_thread(self._model.generate_content, prompt)
        raw = resp.text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        try:
            return json.loads(raw)
        except Exception:
            return {
                "summary": f"User Story for {tc.title}",
                "description": f"Automated test case `{tc.file_path}` was identified without a matching JIRA story.",
                "acceptance_criteria": f"Given test `{tc.title}` is executed\nWhen action completes\nThen expected assertions must pass.",
            }

    async def _embed(self, text_content: str) -> List[float]:
        res = await asyncio.to_thread(
            genai.embed_content,
            model=self._embed_model,
            content=text_content[:2000],
            task_type="retrieval_document",
            output_dimensionality=768,
        )
        return res["embedding"]
