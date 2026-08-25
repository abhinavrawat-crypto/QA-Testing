"""SQLAlchemy models for JIRA and GitHub connections."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JiraConnection(Base):
    __tablename__ = "jira_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    site_url: Mapped[str] = mapped_column(String(512), nullable=False)
    site_name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "oauth" | "pat"
    encrypted_token: Mapped[str] = mapped_column(String(2048), nullable=False)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    encrypted_email: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="jira_connections")  # noqa: F821
    projects: Mapped[list["JiraProject"]] = relationship("JiraProject", back_populates="connection")  # noqa: F821

    def __repr__(self) -> str:
        return f"<JiraConnection id={self.id} site={self.site_url}>"


class GitHubConnection(Base):
    __tablename__ = "github_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    api_base_url: Mapped[str] = mapped_column(String(512), nullable=False, default="https://api.github.com")
    connection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_token: Mapped[str] = mapped_column(String(2048), nullable=False)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    github_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="github_connections")  # noqa: F821
    repos: Mapped[list["GitHubRepo"]] = relationship("GitHubRepo", back_populates="connection")  # noqa: F821

    def __repr__(self) -> str:
        return f"<GitHubConnection id={self.id} base={self.api_base_url}>"
