"""Analysis router — INVEST scoring, approval, and write-back."""
import asyncio
from typing import List
from uuid import UUID
from pydantic import BaseModel

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.dependencies import CurrentUser, DBSession
from app.schemas.analysis import (
    ApproveScoreRequest,
    ApproveScoreResponse,
    ScoreRequest,
    ScoreResult,
)
from app.services.scoring_service import ScoringService

router = APIRouter(prefix="/analysis", tags=["Analysis"])


# ---- Score one or more stories ----
@router.post("/score", response_model=List[ScoreResult])
async def score_stories(
    payload: ScoreRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Score one or more JIRA stories against INVEST + Gherkin AC rubric.
    Returns AI scoring and proposed rewrite for each story.
    Scores are persisted with approval_status='pending'.
    """
    svc = ScoringService(db)
    results = []
    errors = []

    for story_id in payload.story_ids:
        try:
            history = await svc.score_story(story_id=story_id, user_id=current_user.id)
            results.append(history)
        except Exception as e:
            errors.append({"story_id": str(story_id), "error": str(e)})

    if errors and not results:
        raise HTTPException(status_code=422, detail={"scoring_errors": errors})

    return [
        ScoreResult(
            id=str(h.id),
            story_id=str(h.story_id),
            jira_issue_key=_get_issue_key(h),
            summary=_get_summary(h),
            original_description=_get_description(h),
            original_ac=_get_ac(h),
            overall_score=float(h.overall_score),
            invest_scores=h.invest_scores,
            ac_score=float(h.ac_score) if h.ac_score else None,
            gaps=h.gaps or [],
            proposed_summary=h.proposed_summary or "",
            proposed_description=h.proposed_description or "",
            proposed_ac=h.proposed_ac or "",
            approval_status=h.approval_status,
            created_at=h.created_at,
        )
        for h in results
    ]


def _get_issue_key(h) -> str:
    try:
        return h.story.jira_issue_key
    except Exception:
        return ""


def _get_summary(h) -> str:
    try:
        return h.story.summary
    except Exception:
        return ""


def _split_desc_ac(h) -> tuple[str, str]:
    try:
        raw_desc = h.story.description_text or ""
        raw_ac = h.story.acceptance_criteria or ""
        from app.services.jira_service import split_description_and_ac
        return split_description_and_ac(raw_desc, raw_ac)
    except Exception:
        return "", ""


def _get_description(h) -> str:
    desc, _ = _split_desc_ac(h)
    return desc


def _get_ac(h) -> str:
    _, ac = _split_desc_ac(h)
    return ac


# ---- Get score history for a story ----
@router.get("/score/story/{story_id}", response_model=List[ScoreResult])
async def get_score_history(story_id: UUID, current_user: CurrentUser, db: DBSession):
    svc = ScoringService(db)
    history_list = await svc.get_score_history(story_id)
    return [
        ScoreResult(
            id=str(h.id),
            story_id=str(h.story_id),
            jira_issue_key=_get_issue_key(h),
            summary=_get_summary(h),
            original_description=_get_description(h),
            original_ac=_get_ac(h),
            overall_score=float(h.overall_score),
            invest_scores=h.invest_scores,
            ac_score=float(h.ac_score) if h.ac_score else None,
            gaps=h.gaps or [],
            proposed_summary=h.proposed_summary or "",
            proposed_description=h.proposed_description or "",
            proposed_ac=h.proposed_ac or "",
            approval_status=h.approval_status,
            created_at=h.created_at,
        )
        for h in history_list
    ]


# ---- Approve a score and write back to JIRA ----
@router.post("/score/{score_id}/approve", response_model=ApproveScoreResponse)
async def approve_score(
    score_id: UUID,
    payload: ApproveScoreRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Approve an AI score and write the (optionally edited) story back to JIRA.
    Adds an audit comment to the JIRA issue.
    """
    svc = ScoringService(db)
    try:
        result = await svc.approve_score(
            score_id=score_id,
            user_id=current_user.id,
            connection_id=payload.connection_id,
            edited_summary=payload.edited_summary,
            edited_description=payload.edited_description,
            edited_ac=payload.edited_ac,
        )
        return ApproveScoreResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"JIRA write-back failed: {e}")


# ---- Reject a score ----
@router.post("/score/{score_id}/reject")
async def reject_score(score_id: UUID, current_user: CurrentUser, db: DBSession):
    svc = ScoringService(db)
    try:
        return await svc.reject_score(score_id=score_id, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==============================================================
# Impact Analysis (Phase 3)
# ==============================================================
from app.services.impact_service import ImpactService  # noqa: E402


class ImpactRequest(BaseModel):
    story_ids: List[UUID]
    repo_ids: List[UUID]


@router.post("/impact")
async def run_impact_analysis(
    payload: ImpactRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Run impact analysis: vector-search test cases relevant to each story,
    then use Gemini to classify Impacted / Unaffected / Gap.
    Returns the full analysis run with embedded results.
    """
    svc = ImpactService(db)
    try:
        run = await svc.run_impact_analysis(
            user_id=current_user.id,
            story_ids=payload.story_ids,
            repo_ids=payload.repo_ids,
        )
        return {
            "run_id": str(run.id),
            "status": run.status,
            "results": run.results,
            "error": run.error_message,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/{run_id}")
async def get_impact_run(run_id: UUID, current_user: CurrentUser, db: DBSession):
    svc = ImpactService(db)
    run = await svc.get_run(run_id, current_user.id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": str(run.id),
        "status": run.status,
        "results": run.results,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }


@router.get("/impact")
async def list_impact_runs(current_user: CurrentUser, db: DBSession):
    svc = ImpactService(db)
    runs = await svc.list_runs(current_user.id)
    return [
        {
            "run_id": str(r.id),
            "status": r.status,
            "story_count": len(r.story_ids),
            "created_at": r.created_at,
            "completed_at": r.completed_at,
        }
        for r in runs
    ]

