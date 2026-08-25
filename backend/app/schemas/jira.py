"""Pydantic schemas for JIRA connections, projects, and stories."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, HttpUrl


# ---- Connections ----

class JiraConnectionCreate(BaseModel):
    site_url: str
    site_name: str
    auth_type: str  # "oauth" | "pat"
    token: str      # plaintext — will be encrypted in service layer
    email: Optional[str] = None  # required for PAT auth


class JiraConnectionOut(BaseModel):
    id: UUID
    site_url: str
    site_name: str
    auth_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Projects ----

class JiraProjectOut(BaseModel):
    id: UUID
    connection_id: UUID
    project_key: str
    name: str
    project_type: Optional[str] = None
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    is_selected: bool
    last_synced_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Stories ----

class StoryOut(BaseModel):
    id: UUID
    project_id: UUID
    jira_issue_key: str
    summary: str
    description_text: Optional[str] = None
    status: Optional[str] = None
    issue_type: Optional[str] = None
    assignee: Optional[str] = None
    sprint: Optional[str] = None
    epic_key: Optional[str] = None
    story_points: Optional[float] = None
    labels: Optional[List[str]] = None
    acceptance_criteria: Optional[str] = None
    latest_score: Optional[float] = None
    cached_at: datetime

    model_config = {"from_attributes": True}


class StoryListResponse(BaseModel):
    stories: List[StoryOut]
    total: int
    page: int
    page_size: int
