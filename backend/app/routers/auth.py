"""Auth router — register, login, refresh, me."""
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.core.dependencies import CurrentUser, DBSession
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, db: DBSession):
    try:
        svc = AuthService(db)
        user = await svc.register(payload)
        tokens = await svc.login(LoginRequest(email=payload.email, password=payload.password))
        return tokens
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DBSession):
    try:
        return await AuthService(db).login(payload)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: dict, db: DBSession):
    token = body.get("refresh_token", "")
    if not token:
        raise HTTPException(status_code=400, detail="refresh_token is required")
    try:
        return await AuthService(db).refresh(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser):
    return UserOut(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        has_jira_connection=len(current_user.jira_connections) > 0,
        has_github_connection=len(current_user.github_connections) > 0,
    )
