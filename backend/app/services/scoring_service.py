"""Scoring Service — orchestrates INVEST scoring + story rewriting.

Separates AI orchestration from the raw AI provider so the router stays thin.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jira import Story, StoryScoreHistory
from app.models.connections import JiraConnection
from app.services.ai_service import get_ai_provider
from app.services.jira_service import JiraService

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai = get_ai_provider()

    async def score_story(self, story_id: UUID, user_id: UUID) -> StoryScoreHistory:
        """Run INVEST + Gherkin scoring on a single story and persist results."""
        # Load story
        result = await self.db.execute(select(Story).where(Story.id == story_id))
        story = result.scalar_one_or_none()
        if not story:
            raise ValueError(f"Story {story_id} not found")

        # Call Gemini scoring
        score_data = await self.ai.score_story(
            summary=story.summary,
            description=story.description_text or "",
            ac=story.acceptance_criteria or "",
        )

        # Call Gemini rewrite
        rewrite_data = await self.ai.rewrite_story(
            summary=story.summary,
            description=story.description_text or "",
            ac=story.acceptance_criteria or "",
            gaps=score_data.get("gaps", []),
        )

        # Persist score history
        history = StoryScoreHistory(
            story_id=story.id,
            user_id=user_id,
            overall_score=score_data["overall_score"],
            invest_scores=score_data["invest_scores"],
            ac_score=score_data.get("ac_score"),
            gaps=score_data.get("gaps", []),
            proposed_summary=rewrite_data.get("proposed_summary"),
            proposed_description=rewrite_data.get("proposed_description"),
            proposed_ac=rewrite_data.get("proposed_ac"),
            approval_status="pending",
        )
        self.db.add(history)

        # Update story's latest score
        story.latest_score = score_data["overall_score"]

        await self.db.flush()
        await self.db.refresh(history)
        history.story = story
        return history

    async def approve_score(
        self,
        score_id: UUID,
        user_id: UUID,
        connection_id: UUID,
        edited_summary: str | None,
        edited_description: str | None,
        edited_ac: str | None,
    ) -> dict:
        """Apply approved changes to JIRA and mark the score history as approved."""
        result = await self.db.execute(
            select(StoryScoreHistory).where(StoryScoreHistory.id == score_id)
        )
        history = result.scalar_one_or_none()
        if not history:
            raise ValueError("Score record not found")
        if history.approval_status != "pending":
            raise ValueError(f"Score is already {history.approval_status}")

        # Use edited values if supplied, else fall back to AI proposed
        final_summary = edited_summary or history.proposed_summary
        final_description = edited_description or history.proposed_description
        final_ac = edited_ac or history.proposed_ac

        # Load story for JIRA key
        story_result = await self.db.execute(
            select(Story).where(Story.id == history.story_id)
        )
        story = story_result.scalar_one()

        # Update local story cache so future re-evaluations operate on the latest text
        story.summary = final_summary
        story.description_text = final_description
        story.acceptance_criteria = final_ac

        # Write back to JIRA
        jira_svc = JiraService(self.db)
        await jira_svc.update_issue(
            user_id=user_id,
            connection_id=connection_id,
            issue_key=story.jira_issue_key,
            summary=final_summary,
            description_text=final_description,
            acceptance_criteria=final_ac,
        )

        # Add audit comment to JIRA issue
        comment_body = (
            f"✅ **AI-Assisted Story Quality Update**\n\n"
            f"This story was reviewed and updated using the AI QA Platform INVEST scoring engine.\n\n"
            f"**INVEST Score:** {history.overall_score:.0f}/100\n"
            f"**Approved by:** User {user_id}\n"
            f"**Timestamp:** {datetime.now(timezone.utc).isoformat()}\n\n"
            f"*Original story preserved in JIRA history.*"
        )
        comment_id = await jira_svc.add_comment(
            user_id=user_id,
            connection_id=connection_id,
            issue_key=story.jira_issue_key,
            comment_body=comment_body,
        )

        # Mark history as approved
        history.approval_status = "approved"
        history.approved_at = datetime.now(timezone.utc)
        history.approved_by = user_id
        history.jira_comment_id = comment_id

        await self.db.flush()

        return {
            "score_id": str(score_id),
            "jira_issue_key": story.jira_issue_key,
            "status": "approved",
            "jira_comment_id": comment_id,
        }

    async def reject_score(self, score_id: UUID, user_id: UUID) -> dict:
        result = await self.db.execute(
            select(StoryScoreHistory).where(StoryScoreHistory.id == score_id)
        )
        history = result.scalar_one_or_none()
        if not history:
            raise ValueError("Score record not found")
        history.approval_status = "rejected"
        history.approved_at = datetime.now(timezone.utc)
        history.approved_by = user_id
        await self.db.flush()
        return {"score_id": str(score_id), "status": "rejected"}

    async def get_score_history(self, story_id: UUID) -> list[StoryScoreHistory]:
        result = await self.db.execute(
            select(StoryScoreHistory)
            .options(selectinload(StoryScoreHistory.story))
            .where(StoryScoreHistory.story_id == story_id)
            .order_by(StoryScoreHistory.created_at.desc())
        )
        return list(result.scalars().all())
