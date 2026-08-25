"""Indexing router — trigger repo indexing, get stats."""
from uuid import UUID
from fastapi import APIRouter, HTTPException
from app.core.dependencies import CurrentUser, DBSession
from app.services.indexing_service import IndexingService

router = APIRouter(prefix="/indexing", tags=["Indexing"])


@router.post("/repos/{connection_id}/{repo_id}")
async def index_repo(
    connection_id: UUID,
    repo_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Trigger full or incremental indexing of a GitHub repo."""
    try:
        result = await IndexingService(db).index_repo(
            user_id=current_user.id,
            connection_id=connection_id,
            repo_id=repo_id,
        )
        await db.commit()
        return result
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/repos/{repo_id}/stats")
async def get_index_stats(repo_id: UUID, current_user: CurrentUser, db: DBSession):
    """Get count of indexed test cases for a repo."""
    return await IndexingService(db).get_indexed_stats(repo_id)
