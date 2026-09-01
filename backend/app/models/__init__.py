"""Model registry — import all models so SQLAlchemy can discover them."""
from app.models.user import User
from app.models.connections import JiraConnection, GitHubConnection
from app.models.jira import JiraProject, Story, StoryScoreHistory
from app.models.github import GitHubRepo, TestCase
from app.models.analysis import (
    ImpactAnalysisRun,
    TestChangeProposal,
    PlaywrightRun,
    StoryGenerationProposal,
    AuditLog,
    RootCauseRun,
)

__all__ = [
    "User",
    "JiraConnection",
    "GitHubConnection",
    "JiraProject",
    "Story",
    "StoryScoreHistory",
    "GitHubRepo",
    "TestCase",
    "ImpactAnalysisRun",
    "TestChangeProposal",
    "PlaywrightRun",
    "StoryGenerationProposal",
    "AuditLog",
    "RootCauseRun",
]
