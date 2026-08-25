"""Auth & Connection Service — user registration, login, token management."""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, payload: RegisterRequest) -> User:
        # Check duplicate email
        result = await self.db.execute(select(User).where(User.email == payload.email))
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")

        user = User(
            email=payload.email,
            name=payload.name,
            password_hash=hash_password(payload.password),
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def login(self, payload: LoginRequest) -> TokenResponse:
        result = await self.db.execute(
            select(User).where(User.email == payload.email, User.is_active.is_(True))
        )
        user = result.scalar_one_or_none()

        if not user or not user.password_hash:
            raise ValueError("Invalid email or password")
        if not verify_password(payload.password, user.password_hash):
            raise ValueError("Invalid email or password")

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise ValueError("Invalid refresh token")

        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")

        user_id = payload.get("sub")
        result = await self.db.execute(
            select(User).where(User.id == UUID(user_id), User.is_active.is_(True))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
