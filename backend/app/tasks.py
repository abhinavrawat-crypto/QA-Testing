"""Background Celery tasks (stubs for Phase 1 — expanded in later phases)."""
import logging
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.sync_jira_stories")
def sync_jira_stories_task(self, user_id: str, connection_id: str, project_key: str):
    """Async background sync of JIRA stories (runs outside request cycle)."""
    import asyncio
    from app.database import get_db_context
    from app.services.jira_service import JiraService
    from uuid import UUID

    async def _run():
        async with get_db_context() as db:
            svc = JiraService(db)
            await svc.sync_stories(UUID(user_id), UUID(connection_id), project_key)

    asyncio.run(_run())
    return {"status": "done"}


@celery_app.task(bind=True, name="tasks.sync_github_repos")
def sync_github_repos_task(self, user_id: str, connection_id: str):
    """Async background sync of GitHub repos."""
    import asyncio
    from app.database import get_db_context
    from app.services.github_service import GitHubService
    from uuid import UUID

    async def _run():
        async with get_db_context() as db:
            svc = GitHubService(db)
            await svc.sync_repos(UUID(user_id), UUID(connection_id))

    asyncio.run(_run())
    return {"status": "done"}
