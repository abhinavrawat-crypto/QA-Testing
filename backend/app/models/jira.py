"""SQLAlchemy models for JIRA projects and stories."""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JiraProject(Base):
    __tablename__ = "jira_projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jira_connections.id", ondelete="CASCADE"), nullable=False
    )
    project_key: Mapped[str] = mapped_column(String(50), nullable=False)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    connection: Mapped["JiraConnection"] = relationship("JiraConnection", back_populates="projects")  # noqa: F821
    stories: Mapped[list["Story"]] = relationship("Story", back_populates="project")

    def __repr__(self) -> str:
        return f"<JiraProject key={self.project_key} name={self.name}>"


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jira_projects.id", ondelete="CASCADE"), nullable=False
    )
    jira_issue_id: Mapped[str] = mapped_column(String(100), nullable=False)
    jira_issue_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # JIRA ADF JSON
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issue_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reporter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    epic_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    story_points: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    labels: Mapped[list | None] = mapped_column(JSON, default=list)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    embedding: Mapped[list | None] = mapped_column(Vector(768), nullable=True)
    jira_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    jira_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project: Mapped["JiraProject"] = relationship("JiraProject", back_populates="stories")
    score_history: Mapped[list["StoryScoreHistory"]] = relationship(
        "StoryScoreHistory", back_populates="story", order_by="StoryScoreHistory.created_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Story key={self.jira_issue_key} summary={self.summary[:40]}>"


class StoryScoreHistory(Base):
    __tablename__ = "story_score_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    invest_scores: Mapped[dict] = mapped_column(JSON, nullable=False)
    ac_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    proposed_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_ac: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    jira_comment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    story: Mapped["Story"] = relationship("Story", back_populates="score_history")
