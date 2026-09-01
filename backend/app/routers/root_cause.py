"""Router for Feature D — Production Bug Root Cause Analysis & Remediation."""
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

from app.core.dependencies import CurrentUser, DBSession
from app.services.root_cause_service import RootCauseService
from app.services.github_service import GitHubService

router = APIRouter(prefix="/root-cause", tags=["Root Cause Analysis"])


# Pydantic models for request bodies

class BugItem(BaseModel):
    jira_issue_id: Optional[str] = None
    jira_issue_key: str
    summary: str
    description: Optional[str] = ""
    repro_steps: Optional[str] = ""
    status: Optional[str] = "Open"
    issue_type: Optional[str] = "Bug"
    labels: Optional[List[str]] = []
    reporter: Optional[str] = "Unknown"
    created_at: Optional[str] = None


class AnalyzeBugsRequest(BaseModel):
    bugs: List[BugItem]
    project_key: str
    filter_label: Optional[str] = "prod-bug"
    repo_ids: Optional[List[UUID]] = []
    github_connection_id: Optional[UUID] = None


class CreatePRRequest(BaseModel):
    github_connection_id: UUID
    repo_full_name: str
    branch_name: str
    file_path: str
    content: str
    title: str
    body: str


class GenerateScriptRequest(BaseModel):
    bug_key: str
    bug_summary: str
    remediation_content: str
    target_url: Optional[str] = None


class EnvironmentItem(BaseModel):
    name: str
    base_url: str
    env_vars: Optional[Dict[str, str]] = {}


class MultiEnvVerifyRequest(BaseModel):
    script_code: str
    environments: List[EnvironmentItem]


# Router Endpoints

@router.get("/bugs")
async def fetch_production_bugs(
    connection_id: UUID,
    project_key: str,
    label: Optional[str] = "prod-bug",
    current_user: CurrentUser = None,
    db: DBSession = None,
):
    """Fetch production defects from JIRA filtered by project and label/tag."""
    svc = RootCauseService(db)
    try:
        bugs = await svc.fetch_production_bugs(
            user_id=current_user.id,
            connection_id=connection_id,
            project_key=project_key,
            label=label,
        )
        return bugs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch production defects from JIRA: {e}")


@router.post("/analyze")
async def analyze_production_bugs(
    payload: AnalyzeBugsRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Perform root cause analysis on selected production defects.
    Matches bugs against pgvector indexed test cases and GitHub Actions workflow runs.
    """
    svc = RootCauseService(db)
    try:
        bugs_dicts = [b.model_dump() for b in payload.bugs]
        run = await svc.run_root_cause_analysis(
            user_id=current_user.id,
            bugs=bugs_dicts,
            project_key=payload.project_key,
            filter_label=payload.filter_label,
            repo_ids=payload.repo_ids,
            github_connection_id=payload.github_connection_id,
        )
        return {
            "run_id": str(run.id),
            "status": run.status,
            "results": run.results,
            "created_at": run.created_at,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Root cause analysis failed: {e}")


@router.post("/create-pr")
async def create_remediation_pr(
    payload: CreatePRRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Create a new GitHub branch, commit approved remediation spec, and open PR."""
    gh_svc = GitHubService(db)
    try:
        # Get base branch sha
        conn = await gh_svc._get_connection(current_user.id, payload.github_connection_id)
        from_sha = await gh_svc.get_default_branch_sha(conn, payload.repo_full_name)

        # Create branch
        await gh_svc.create_branch(
            user_id=current_user.id,
            connection_id=payload.github_connection_id,
            full_name=payload.repo_full_name,
            branch_name=payload.branch_name,
            from_sha=from_sha,
        )

        # Commit file
        commit_sha = await gh_svc.commit_file(
            user_id=current_user.id,
            connection_id=payload.github_connection_id,
            full_name=payload.repo_full_name,
            branch_name=payload.branch_name,
            file_path=payload.file_path,
            content=payload.content,
            commit_message=f"fix(qualityai): {payload.title}",
        )

        # Create PR
        pr_result = await gh_svc.create_pull_request(
            user_id=current_user.id,
            connection_id=payload.github_connection_id,
            full_name=payload.repo_full_name,
            head_branch=payload.branch_name,
            base_branch="main",
            title=payload.title,
            body=payload.body,
        )

        return {
            "status": "success",
            "branch_name": payload.branch_name,
            "commit_sha": commit_sha,
            "pr_number": pr_result.get("pr_number"),
            "pr_url": pr_result.get("url"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create GitHub PR: {e}")


@router.post("/generate-script")
async def generate_playwright_fix_script(
    payload: GenerateScriptRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Generate Playwright JavaScript test script for an approved remediation spec."""
    svc = RootCauseService(db)
    try:
        script = await svc.generate_playwright_fix(
            bug_key=payload.bug_key,
            bug_summary=payload.bug_summary,
            remediation_content=payload.remediation_content,
            target_url=payload.target_url,
        )
        return {"script_code": script}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Playwright script: {e}")


@router.post("/multi-env-verify")
async def verify_across_environments(
    payload: MultiEnvVerifyRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Execute Playwright script concurrently in isolated sandboxed runs across multiple environments.
    Produces side-by-side comparison report.
    """
    svc = RootCauseService(db)
    try:
        env_dicts = [e.model_dump() for e in payload.environments]
        report = await svc.run_multi_environment_verification(
            user_id=current_user.id,
            script_code=payload.script_code,
            environments=env_dicts,
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-environment execution failed: {e}")
