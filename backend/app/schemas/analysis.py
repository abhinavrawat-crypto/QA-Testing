"""Pydantic schemas for AI analysis — scoring, rewrites, approvals."""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class InvestScores(BaseModel):
    independent: float = Field(ge=0, le=100)
    negotiable: float = Field(ge=0, le=100)
    valuable: float = Field(ge=0, le=100)
    estimable: float = Field(ge=0, le=100)
    small: float = Field(ge=0, le=100)
    testable: float = Field(ge=0, le=100)


class ScoreRequest(BaseModel):
    story_ids: List[UUID]
    connection_id: Optional[UUID] = None  # Optional JIRA connection ID


class ScoreResult(BaseModel):
    id: UUID
    story_id: UUID
    jira_issue_key: str
    summary: str
    original_description: Optional[str] = ""
    original_ac: Optional[str] = ""
    overall_score: float
    invest_scores: InvestScores
    ac_score: Optional[float] = None
    gaps: List[str] = []
    proposed_summary: str
    proposed_description: str
    proposed_ac: str
    approval_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ApproveScoreRequest(BaseModel):
    connection_id: UUID
    edited_summary: Optional[str] = None
    edited_description: Optional[str] = None
    edited_ac: Optional[str] = None


class ApproveScoreResponse(BaseModel):
    score_id: UUID
    jira_issue_key: str
    status: str
    jira_comment_id: Optional[str] = None
