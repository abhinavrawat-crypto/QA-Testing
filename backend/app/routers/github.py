"""GitHub router — connection management, repo sync, selection."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.dependencies import CurrentUser, DBSession
from app.schemas.github import (
    GitHubConnectionCreate,
    GitHubConnectionOut,
    GitHubRepoOut,
)
from app.services.github_service import GitHubService

router = APIRouter(prefix="/github", tags=["GitHub"])


# ---- Connections ----

@router.post("/connections", response_model=GitHubConnectionOut, status_code=201)
async def create_github_connection(
    payload: GitHubConnectionCreate, current_user: CurrentUser, db: DBSession
):
    try:
        conn = await GitHubService(db).create_connection(current_user.id, payload)
        return GitHubConnectionOut.model_validate(conn)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections", response_model=List[GitHubConnectionOut])
async def list_github_connections(current_user: CurrentUser, db: DBSession):
    conns = await GitHubService(db).list_connections(current_user.id)
    return [GitHubConnectionOut.model_validate(c) for c in conns]


@router.delete("/connections/{connection_id}", status_code=204)
async def delete_github_connection(connection_id: UUID, current_user: CurrentUser, db: DBSession):
    await GitHubService(db).delete_connection(current_user.id, connection_id)


# ---- Repos ----

@router.post("/connections/{connection_id}/sync-repos", response_model=List[GitHubRepoOut])
async def sync_repos(connection_id: UUID, current_user: CurrentUser, db: DBSession):
    try:
        repos = await GitHubService(db).sync_repos(current_user.id, connection_id)
        return [GitHubRepoOut.model_validate(r) for r in repos]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/connections/{connection_id}/repos", response_model=List[GitHubRepoOut])
async def get_repos(connection_id: UUID, current_user: CurrentUser, db: DBSession):
    repos = await GitHubService(db).get_repos(current_user.id, connection_id)
    return [GitHubRepoOut.model_validate(r) for r in repos]


@router.patch("/connections/{connection_id}/repos/{repo_id}/select")
async def toggle_repo(
    connection_id: UUID,
    repo_id: UUID,
    body: dict,
    current_user: CurrentUser,
    db: DBSession,
):
    selected = bool(body.get("selected", True))
    try:
        repo = await GitHubService(db).toggle_repo_selection(
            current_user.id, connection_id, repo_id, selected
        )
        return GitHubRepoOut.model_validate(repo)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
