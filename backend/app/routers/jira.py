"""JIRA router — connection management, project sync, story fetching, write-back."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.core.dependencies import CurrentUser, DBSession
from app.schemas.jira import (
    JiraConnectionCreate,
    JiraConnectionOut,
    JiraProjectOut,
    StoryListResponse,
    StoryOut,
)
from app.services.jira_service import JiraService

router = APIRouter(prefix="/jira", tags=["JIRA"])


# ---- Connections ----

@router.post("/connections", response_model=JiraConnectionOut, status_code=201)
async def create_jira_connection(
    payload: JiraConnectionCreate, current_user: CurrentUser, db: DBSession
):
    try:
        conn = await JiraService(db).create_connection(current_user.id, payload)
        return JiraConnectionOut.model_validate(conn)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections", response_model=List[JiraConnectionOut])
async def list_jira_connections(current_user: CurrentUser, db: DBSession):
    conns = await JiraService(db).list_connections(current_user.id)
    return [JiraConnectionOut.model_validate(c) for c in conns]


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_jira_connection(connection_id: UUID, current_user: CurrentUser, db: DBSession):
    await JiraService(db).delete_connection(current_user.id, connection_id)


# ---- Projects ----

@router.post("/connections/{connection_id}/sync-projects", response_model=List[JiraProjectOut])
async def sync_projects(connection_id: UUID, current_user: CurrentUser, db: DBSession):
    try:
        projects = await JiraService(db).sync_projects(current_user.id, connection_id)
        return [JiraProjectOut.model_validate(p) for p in projects]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections/{connection_id}/projects", response_model=List[JiraProjectOut])
async def get_projects(connection_id: UUID, current_user: CurrentUser, db: DBSession):
    projects = await JiraService(db).get_projects(current_user.id, connection_id)
    return [JiraProjectOut.model_validate(p) for p in projects]


# ---- Stories ----

@router.post(
    "/connections/{connection_id}/projects/{project_key}/sync-stories",
    response_model=List[StoryOut],
)
async def sync_stories(
    connection_id: UUID,
    project_key: str,
    current_user: CurrentUser,
    db: DBSession,
    sprint: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=100),
):
    try:
        stories = await JiraService(db).sync_stories(
            current_user.id, connection_id, project_key, sprint, assignee, status, page, page_size
        )
        return [StoryOut.model_validate(s) for s in stories]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stories/{story_id}", response_model=StoryOut)
async def get_story(story_id: UUID, current_user: CurrentUser, db: DBSession):
    story = await JiraService(db).get_story(current_user.id, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return StoryOut.model_validate(story)


from pydantic import BaseModel

class PushImpactToJiraRequest(BaseModel):
    connection_id: UUID
    issue_key: str
    impact_summary: str
    proposed_content: str

@router.post("/stories/push-impact")
async def push_impact_to_jira(
    payload: PushImpactToJiraRequest, current_user: CurrentUser, db: DBSession
):
    """Push test impact analysis findings & proposed modifications directly to the JIRA ticket as an official comment."""
    comment_body = (
        f"🤖 **AI Test Impact Analysis Update**\n\n"
        f"**Rationale:**\n{payload.impact_summary}\n\n"
        f"**Proposed Test Suite Modification / Addition:**\n\n"
        f"```gherkin\n{payload.proposed_content}\n```"
    )
    try:
        comment_id = await JiraService(db).add_comment(
            user_id=current_user.id,
            connection_id=payload.connection_id,
            issue_key=payload.issue_key,
            comment_body=comment_body,
        )
        return {"status": "success", "comment_id": comment_id, "issue_key": payload.issue_key}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

