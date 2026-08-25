"""Story Discovery Router (Feature C)."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.dependencies import CurrentUser, DBSession
from app.services.discovery_service import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["Discovery"])


class DiscoverRequest(BaseModel):
    repo_ids: List[UUID]
    similarity_threshold: float = 0.5


class CreateJiraStoryRequest(BaseModel):
    connection_id: UUID
    project_key: str
    summary: str
    description: str
    acceptance_criteria: str
    issue_type: str = "Story"


@router.post("/unmatched")
async def discover_unmatched_tests(
    payload: DiscoverRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Find test cases in selected repos that have no matching JIRA user story."""
    svc = DiscoveryService(db)
    try:
        results = await svc.discover_unmatched_tests(
            user_id=current_user.id,
            repo_ids=payload.repo_ids,
            similarity_threshold=payload.similarity_threshold or 0.5,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-jira-story")
async def create_jira_story(
    payload: CreateJiraStoryRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Human-in-the-loop step: create an approved AI-drafted story directly in JIRA."""
    svc = DiscoveryService(db)
    try:
        res = await svc.create_story_in_jira(
            user_id=current_user.id,
            connection_id=payload.connection_id,
            project_key=payload.project_key,
            summary=payload.summary,
            description=payload.description,
            acceptance_criteria=payload.acceptance_criteria,
            issue_type=payload.issue_type or "Story",
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
