"""JIRA Integration Service — wraps JIRA REST API v3.

Handles multiple JIRA sites per user, with exponential backoff retries.
All tokens are encrypted at rest; decrypted only when making API requests.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.security import decrypt_token, encrypt_token
from app.models.connections import JiraConnection
from app.models.jira import JiraProject, Story
from app.schemas.jira import JiraConnectionCreate

logger = logging.getLogger(__name__)

JIRA_API_VERSION = "rest/api/3"


def _is_transient_error(exception: Exception) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exception, (httpx.RequestError, httpx.TimeoutException)):
        return True
    return False


RETRY_SETTINGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)


def _extract_plain_text(adf: Any) -> str:
    """Recursively extract plain text from JIRA's Atlassian Document Format (ADF)."""
    if adf is None:
        return ""
    if isinstance(adf, str):
        return adf
    if isinstance(adf, dict):
        node_type = adf.get("type")
        if node_type == "text":
            return adf.get("text", "")
        parts = []
        for child in adf.get("content", []):
            parts.append(_extract_plain_text(child))
        return " ".join(p for p in parts if p)
    if isinstance(adf, list):
        return " ".join(_extract_plain_text(i) for i in adf)
    return ""


def split_description_and_ac(text: str, existing_ac: str = None) -> tuple[str, str]:
    """Separate description text from embedded Acceptance Criteria if present."""
    if not text:
        return "", existing_ac or ""

    pattern = r"(?i)(acceptance criteria\s*(?:\([^)]*\))?\s*:?|ac\s*:)"
    match = re.search(pattern, text)
    if match:
        desc_part = text[:match.start()].strip()
        ac_part = existing_ac if (existing_ac and len(existing_ac.strip()) > 0) else text[match.start():].strip()
        return desc_part, ac_part
    return text.strip(), existing_ac or ""


class JiraService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ #
    #  Connection management
    # ------------------------------------------------------------------ #

    async def create_connection(
        self, user_id: UUID, payload: JiraConnectionCreate
    ) -> JiraConnection:
        """Save a new JIRA connection with encrypted credentials."""
        # Validate that the token works
        await self._validate_token(payload.site_url, payload.token, payload.auth_type, payload.email)

        encrypted = encrypt_token(payload.token)
        encrypted_email = encrypt_token(payload.email) if payload.email else None

        conn = JiraConnection(
            user_id=user_id,
            site_url=payload.site_url.rstrip("/"),
            site_name=payload.site_name,
            auth_type=payload.auth_type,
            encrypted_token=encrypted,
            encrypted_email=encrypted_email,
        )
        self.db.add(conn)
        await self.db.flush()
        await self.db.refresh(conn)
        return conn

    async def list_connections(self, user_id: UUID) -> List[JiraConnection]:
        result = await self.db.execute(
            select(JiraConnection).where(JiraConnection.user_id == user_id, JiraConnection.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def delete_connection(self, user_id: UUID, connection_id: UUID) -> None:
        result = await self.db.execute(
            select(JiraConnection).where(
                JiraConnection.id == connection_id, JiraConnection.user_id == user_id
            )
        )
        conn = result.scalar_one_or_none()
        if conn:
            conn.is_active = False

    # ------------------------------------------------------------------ #
    #  Project sync
    # ------------------------------------------------------------------ #

    async def sync_projects(self, user_id: UUID, connection_id: UUID) -> List[JiraProject]:
        """Fetch all accessible JIRA projects and cache them."""
        conn = await self._get_connection(user_id, connection_id)
        async with self._client(conn) as client:
            projects_data = await self._paginate_projects(client, conn.site_url)

        cached = []
        for p in projects_data:
            result = await self.db.execute(
                select(JiraProject).where(
                    JiraProject.connection_id == conn.id,
                    JiraProject.project_key == p["key"],
                )
            )
            proj = result.scalar_one_or_none()
            if proj is None:
                proj = JiraProject(connection_id=conn.id, project_key=p["key"], project_id=p["id"])
            proj.name = p["name"]
            proj.project_type = p.get("projectTypeKey")
            proj.description = p.get("description")
            proj.avatar_url = (p.get("avatarUrls") or {}).get("48x48")
            proj.last_synced_at = datetime.now(timezone.utc)
            if proj.id is None:
                self.db.add(proj)
            cached.append(proj)

        await self.db.flush()
        return cached

    async def get_projects(self, user_id: UUID, connection_id: UUID) -> List[JiraProject]:
        conn = await self._get_connection(user_id, connection_id)
        result = await self.db.execute(
            select(JiraProject).where(JiraProject.connection_id == conn.id)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    #  Story sync
    # ------------------------------------------------------------------ #

    async def sync_stories(
        self,
        user_id: UUID,
        connection_id: UUID,
        project_key: str,
        sprint: Optional[str] = None,
        assignee: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 0,
        page_size: int = 50,
    ) -> List[Story]:
        """Fetch stories from JIRA and upsert into local DB."""
        conn = await self._get_connection(user_id, connection_id)

        # Get project record
        proj_result = await self.db.execute(
            select(JiraProject).where(
                JiraProject.connection_id == conn.id, JiraProject.project_key == project_key
            )
        )
        project = proj_result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_key} not found — sync projects first")

        jql_parts = [f'project = "{project_key}"', 'issuetype = Story']
        if sprint:
            jql_parts.append(f'sprint = "{sprint}"')
        if assignee:
            jql_parts.append(f'assignee = "{assignee}"')
        if status:
            jql_parts.append(f'status = "{status}"')
        jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

        async with self._client(conn) as client:
            response = await self._search_issues(client, conn.site_url, jql, page * page_size, page_size)

        issues = response.get("issues", [])
        stories = []
        for issue in issues:
            story = await self._upsert_story(project, issue)
            stories.append(story)

        await self.db.flush()
        return stories

    async def get_story(self, user_id: UUID, story_id: UUID) -> Optional[Story]:
        result = await self.db.execute(
            select(Story).join(JiraProject).join(JiraConnection).where(
                Story.id == story_id, JiraConnection.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------ #
    #  Write-back to JIRA
    # ------------------------------------------------------------------ #

    async def update_issue(
        self,
        user_id: UUID,
        connection_id: UUID,
        issue_key: str,
        summary: Optional[str] = None,
        description_text: Optional[str] = None,
        acceptance_criteria: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write approved AI changes back to a JIRA issue via PUT /issue/{key}."""
        conn = await self._get_connection(user_id, connection_id)

        fields: Dict[str, Any] = {}
        if summary:
            fields["summary"] = summary
        if description_text or acceptance_criteria:
            combined = (description_text or "") + (
                f"\n\n**Acceptance Criteria:**\n{acceptance_criteria}" if acceptance_criteria else ""
            )
            fields["description"] = self._text_to_adf(combined)

        async with self._client(conn) as client:
            await client.put(
                f"{conn.site_url}/{JIRA_API_VERSION}/issue/{issue_key}",
                json={"fields": fields},
            )

        return {"status": "updated", "issue_key": issue_key}

    async def add_comment(
        self, user_id: UUID, connection_id: UUID, issue_key: str, comment_body: str
    ) -> str:
        """Add a comment to a JIRA issue (used for AI audit trail)."""
        conn = await self._get_connection(user_id, connection_id)
        async with self._client(conn) as client:
            r = await client.post(
                f"{conn.site_url}/{JIRA_API_VERSION}/issue/{issue_key}/comment",
                json={"body": self._text_to_adf(comment_body)},
            )
        return r.json().get("id", "")

    async def create_issue(
        self,
        user_id: UUID,
        connection_id: UUID,
        project_key: str,
        summary: str,
        description: str,
        ac: str,
        issue_type: str = "Story",
    ) -> Dict[str, Any]:
        """Create a new JIRA issue (Feature C write-back)."""
        conn = await self._get_connection(user_id, connection_id)
        body = description
        if ac:
            body = description + f"\n\n**Acceptance Criteria:**\n{ac}"
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": self._text_to_adf(body),
                "issuetype": {"name": issue_type},
            }
        }
        async with self._client(conn) as client:
            r = await client.post(
                f"{conn.site_url}/{JIRA_API_VERSION}/issue",
                json=payload,
            )
        data = r.json()
        return {"key": data.get("key"), "id": data.get("id"), "self": data.get("self")}

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    async def _get_connection(self, user_id: UUID, connection_id: UUID) -> JiraConnection:
        result = await self.db.execute(
            select(JiraConnection).where(
                JiraConnection.id == connection_id,
                JiraConnection.user_id == user_id,
                JiraConnection.is_active.is_(True),
            )
        )
        conn = result.scalar_one_or_none()
        if conn is None:
            raise ValueError("JIRA connection not found")
        return conn

    def _client(self, conn: JiraConnection) -> httpx.AsyncClient:
        token = decrypt_token(conn.encrypted_token)
        if conn.auth_type == "pat":
            email = decrypt_token(conn.encrypted_email) if conn.encrypted_email else ""
            import base64
            encoded = base64.b64encode(f"{email}:{token}".encode()).decode()
            headers = {"Authorization": f"Basic {encoded}", "Accept": "application/json", "Content-Type": "application/json"}
        else:
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
        return httpx.AsyncClient(headers=headers, timeout=30)

    @retry(**RETRY_SETTINGS)
    async def _validate_token(self, site_url: str, token: str, auth_type: str, email: Optional[str]) -> None:
        import base64
        if auth_type == "pat":
            encoded = base64.b64encode(f"{email}:{token}".encode()).decode()
            headers = {"Authorization": f"Basic {encoded}"}
        else:
            headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(headers=headers, timeout=15) as client:
            r = await client.get(f"{site_url.rstrip('/')}/{JIRA_API_VERSION}/myself")
            r.raise_for_status()

    @retry(**RETRY_SETTINGS)
    async def _paginate_projects(self, client: httpx.AsyncClient, site_url: str) -> List[Dict]:
        all_projects = []
        start_at = 0
        while True:
            r = await client.get(
                f"{site_url}/{JIRA_API_VERSION}/project/search",
                params={"startAt": start_at, "maxResults": 50},
            )
            r.raise_for_status()
            data = r.json()
            all_projects.extend(data.get("values", []))
            if data.get("isLast", True):
                break
            start_at += 50
        return all_projects

    @retry(**RETRY_SETTINGS)
    async def _search_issues(
        self, client: httpx.AsyncClient, site_url: str, jql: str, start_at: int, max_results: int
    ) -> Dict:
        fields = [
            "summary", "description", "status", "issuetype", "assignee", "reporter",
            "story_points", "labels", "sprint", "parent", "created", "updated",
            "customfield_10016", "customfield_10014"
        ]
        
        # 1. Primary: Jira Cloud REST API v3 /search/jql
        url_jql = f"{site_url.rstrip('/')}/{JIRA_API_VERSION}/search/jql"
        payload_jql = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields,
        }
        r = await client.post(url_jql, json=payload_jql)
        if r.status_code == 200:
            return r.json()

        # 2. Fallbacks for legacy Jira Server or Data Center
        fallback_urls = [
            f"{site_url.rstrip('/')}/{JIRA_API_VERSION}/search",
            f"{site_url.rstrip('/')}/rest/api/2/search",
        ]
        payload_legacy = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": fields,
        }
        for url in fallback_urls:
            r_fb = await client.post(url, json=payload_legacy)
            if r_fb.status_code == 200:
                return r_fb.json()

        # Format clean error message from response
        err_msg = ""
        try:
            data = r.json()
            err_msg = ", ".join(data.get("errorMessages", [])) or str(data.get("errors", ""))
        except Exception:
            err_msg = r.text[:200]
        
        raise ValueError(f"JIRA Search API Error ({r.status_code}): {err_msg or r.reason_phrase}")

    async def _upsert_story(self, project: JiraProject, issue: Dict) -> Story:
        fields = issue.get("fields", {})
        result = await self.db.execute(
            select(Story).where(
                Story.project_id == project.id, Story.jira_issue_key == issue["key"]
            )
        )
        story = result.scalar_one_or_none()
        if story is None:
            story = Story(project_id=project.id, jira_issue_id=issue["id"], jira_issue_key=issue["key"])
            self.db.add(story)

        raw_desc = _extract_plain_text(fields.get("description"))
        existing_ac = story.acceptance_criteria
        desc_clean, ac_clean = split_description_and_ac(raw_desc, existing_ac)

        story.summary = fields.get("summary", "")
        story.description = fields.get("description")
        story.description_text = desc_clean
        story.acceptance_criteria = ac_clean
        story.status = (fields.get("status") or {}).get("name")
        story.issue_type = (fields.get("issuetype") or {}).get("name")
        story.assignee = ((fields.get("assignee") or {}).get("displayName"))
        story.reporter = ((fields.get("reporter") or {}).get("displayName"))
        story.story_points = fields.get("customfield_10016") or fields.get("story_points")
        story.labels = fields.get("labels", [])
        story.cached_at = datetime.now(timezone.utc)
        return story

    @staticmethod
    def _text_to_adf(text: str) -> Dict:
        """Convert plain text to minimal JIRA ADF format."""
        paragraphs = []
        for line in text.split("\n"):
            paragraphs.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": line or " "}],
            })
        return {"type": "doc", "version": 1, "content": paragraphs}
