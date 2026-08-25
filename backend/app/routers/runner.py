"""Test Runner Router — Sandboxed Playwright execution endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.dependencies import CurrentUser, DBSession
from app.services.runner_service import RunnerService

router = APIRouter(prefix="/runner", tags=["Test Runner"])


class ExecuteTestRequest(BaseModel):
    script_code: str
    target_url: Optional[str] = None
    env_vars: Optional[dict[str, str]] = None
    headed: Optional[bool] = False
    timeout_seconds: Optional[int] = 60


@router.post("/execute")
async def execute_test(
    payload: ExecuteTestRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Trigger sandboxed or live execution of a Playwright test script."""
    svc = RunnerService(db)
    try:
        run = await svc.execute_playwright_script(
            user_id=current_user.id,
            script_code=payload.script_code,
            target_url=payload.target_url,
            env_vars=payload.env_vars,
            headed=payload.headed or False,
            timeout_seconds=payload.timeout_seconds or 60,
        )
        logs_list = run.logs.split("\n") if isinstance(run.logs, str) and run.logs else (run.logs or [])
        return {
            "run_id": str(run.id),
            "status": run.status,
            "logs": logs_list,
            "created_at": run.created_at,
            "completed_at": run.completed_at,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}")
async def get_run_details(run_id: UUID, current_user: CurrentUser, db: DBSession):
    svc = RunnerService(db)
    run = await svc.get_run(run_id, current_user.id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    logs_list = run.logs.split("\n") if isinstance(run.logs, str) and run.logs else (run.logs or [])
    return {
        "run_id": str(run.id),
        "status": run.status,
        "logs": logs_list,
        "error_message": run.error_message,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }
