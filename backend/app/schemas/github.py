"""Pydantic schemas for GitHub connections, repos, and test cases."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel


class GitHubConnectionCreate(BaseModel):
    api_base_url: str = "https://api.github.com"
    connection_name: str
    auth_type: str        # "oauth" | "pat"
    token: str            # plaintext PAT or OAuth token — encrypted in service layer


class GitHubConnectionOut(BaseModel):
    id: UUID
    api_base_url: str
    connection_name: str
    auth_type: str
    github_username: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class GitHubRepoOut(BaseModel):
    id: UUID
    connection_id: UUID
    full_name: str
    name: str
    html_url: Optional[str] = None
    default_branch: str
    is_private: bool
    is_selected: bool
    last_indexed_commit: Optional[str] = None
    last_synced_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TestCaseOut(BaseModel):
    id: UUID
    repo_id: UUID
    file_path: str
    test_type: str
    feature_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    commit_sha: str
    created_at: datetime

    model_config = {"from_attributes": True}
