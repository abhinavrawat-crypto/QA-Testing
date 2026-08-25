"""Code Generation & PR Automation Router."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.dependencies import CurrentUser, DBSession
from app.services.playwright_gen_service import PlaywrightGenService

router = APIRouter(prefix="/code-gen", tags=["Code Generation"])


class GenerateCodeRequest(BaseModel):
    story_id: UUID
    original_test_content: Optional[str] = None
    scenario_description: Optional[str] = None
    target_file_path: Optional[str] = None
    language: Optional[str] = "typescript"
    target_url: Optional[str] = None


class CreatePRRequest(BaseModel):
    connection_id: UUID
    repo_full_name: str
    file_path: str
    file_content: str
    jira_issue_key: str
    draft: Optional[bool] = False
    custom_pr_title: Optional[str] = None


@router.post("/generate")
async def generate_playwright_code(
    payload: GenerateCodeRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Generate Playwright test code using Gemini for a story/scenario."""
    svc = PlaywrightGenService(db)
    try:
        res = await svc.generate_playwright_test(
            story_id=payload.story_id,
            original_test_content=payload.original_test_content,
            scenario_description=payload.scenario_description,
            target_file_path=payload.target_file_path,
            language=payload.language or "typescript",
            target_url=payload.target_url,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-pr")
async def create_pull_request(
    payload: CreatePRRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Human-in-the-loop approval: create branch, commit test code, and open a GitHub PR."""
    svc = PlaywrightGenService(db)
    try:
        pr_info = await svc.create_pull_request_for_test(
            user_id=current_user.id,
            connection_id=payload.connection_id,
            repo_full_name=payload.repo_full_name,
            file_path=payload.file_path,
            file_content=payload.file_content,
            jira_issue_key=payload.jira_issue_key,
            draft=payload.draft or False,
            custom_pr_title=payload.custom_pr_title,
        )
        return pr_info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
