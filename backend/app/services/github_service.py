"""GitHub Integration Service — wraps GitHub REST/GraphQL API.

Supports github.com AND GitHub Enterprise Server (GHES) via configurable API base URLs.
All tokens are Fernet-encrypted at rest.
"""
import base64
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.security import decrypt_token, encrypt_token
from app.models.connections import GitHubConnection
from app.models.github import GitHubRepo
from app.schemas.github import GitHubConnectionCreate

logger = logging.getLogger(__name__)


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


class GitHubService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ #
    #  Connection management
    # ------------------------------------------------------------------ #

    async def create_connection(
        self, user_id: UUID, payload: GitHubConnectionCreate
    ) -> GitHubConnection:
        username = await self._fetch_username(payload.api_base_url, payload.token)
        encrypted = encrypt_token(payload.token)

        conn = GitHubConnection(
            user_id=user_id,
            api_base_url=payload.api_base_url.rstrip("/"),
            connection_name=payload.connection_name,
            auth_type=payload.auth_type,
            encrypted_token=encrypted,
            github_username=username,
        )
        self.db.add(conn)
        await self.db.flush()
        await self.db.refresh(conn)
        return conn

    async def list_connections(self, user_id: UUID) -> List[GitHubConnection]:
        result = await self.db.execute(
            select(GitHubConnection).where(
                GitHubConnection.user_id == user_id, GitHubConnection.is_active.is_(True)
            )
        )
        return list(result.scalars().all())

    async def delete_connection(self, user_id: UUID, connection_id: UUID) -> None:
        result = await self.db.execute(
            select(GitHubConnection).where(
                GitHubConnection.id == connection_id, GitHubConnection.user_id == user_id
            )
        )
        conn = result.scalar_one_or_none()
        if conn:
            conn.is_active = False

    # ------------------------------------------------------------------ #
    #  Repo sync
    # ------------------------------------------------------------------ #

    async def sync_repos(self, user_id: UUID, connection_id: UUID) -> List[GitHubRepo]:
        """Fetch all accessible repos and cache them in DB."""
        conn = await self._get_connection(user_id, connection_id)
        async with self._client(conn) as client:
            repos_data = await self._fetch_all_repos(client, conn.api_base_url)

        cached = []
        for r in repos_data:
            result = await self.db.execute(
                select(GitHubRepo).where(
                    GitHubRepo.connection_id == conn.id,
                    GitHubRepo.full_name == r["full_name"],
                )
            )
            repo = result.scalar_one_or_none()
            if repo is None:
                repo = GitHubRepo(connection_id=conn.id, full_name=r["full_name"])
            repo.name = r["name"]
            repo.clone_url = r.get("clone_url")
            repo.html_url = r.get("html_url")
            repo.default_branch = r.get("default_branch", "main")
            repo.is_private = r.get("private", False)
            repo.last_synced_at = datetime.now(timezone.utc)
            if repo.id is None:
                self.db.add(repo)
            cached.append(repo)

        await self.db.flush()
        return cached

    async def get_repos(self, user_id: UUID, connection_id: UUID) -> List[GitHubRepo]:
        conn = await self._get_connection(user_id, connection_id)
        result = await self.db.execute(
            select(GitHubRepo).where(GitHubRepo.connection_id == conn.id)
        )
        return list(result.scalars().all())

    async def toggle_repo_selection(
        self, user_id: UUID, connection_id: UUID, repo_id: UUID, selected: bool
    ) -> GitHubRepo:
        conn = await self._get_connection(user_id, connection_id)
        result = await self.db.execute(
            select(GitHubRepo).where(GitHubRepo.id == repo_id, GitHubRepo.connection_id == conn.id)
        )
        repo = result.scalar_one_or_none()
        if not repo:
            raise ValueError("Repo not found")
        repo.is_selected = selected
        return repo

    # ------------------------------------------------------------------ #
    #  File / Tree operations
    # ------------------------------------------------------------------ #

    async def get_file_content(
        self, conn: GitHubConnection, full_name: str, path: str, ref: str = "HEAD"
    ) -> str:
        """Fetch a file's content from GitHub and decode from base64."""
        async with self._client(conn) as client:
            r = await client.get(
                f"{conn.api_base_url}/repos/{full_name}/contents/{path}",
                params={"ref": ref},
            )
            r.raise_for_status()
            data = r.json()
            if data.get("encoding") == "base64":
                return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return data.get("content", "")

    async def list_tree(
        self, conn: GitHubConnection, full_name: str, sha: str = "HEAD", recursive: bool = True
    ) -> List[Dict]:
        """Return repository tree (list of files with paths and shas)."""
        async with self._client(conn) as client:
            r = await client.get(
                f"{conn.api_base_url}/repos/{full_name}/git/trees/{sha}",
                params={"recursive": "1" if recursive else "0"},
            )
            r.raise_for_status()
            return r.json().get("tree", [])

    async def get_default_branch_sha(self, conn: GitHubConnection, full_name: str) -> str:
        async with self._client(conn) as client:
            r = await client.get(f"{conn.api_base_url}/repos/{full_name}")
            r.raise_for_status()
            default_branch = r.json().get("default_branch", "main")
            r2 = await client.get(
                f"{conn.api_base_url}/repos/{full_name}/git/ref/heads/{default_branch}"
            )
            r2.raise_for_status()
            return r2.json()["object"]["sha"]

    # ------------------------------------------------------------------ #
    #  Branch / PR operations
    # ------------------------------------------------------------------ #

    async def create_branch(
        self,
        user_id: UUID,
        connection_id: UUID,
        full_name: str,
        branch_name: str,
        from_sha: str,
    ) -> str:
        conn = await self._get_connection(user_id, connection_id)
        async with self._client(conn) as client:
            r = await client.post(
                f"{conn.api_base_url}/repos/{full_name}/git/refs",
                json={"ref": f"refs/heads/{branch_name}", "sha": from_sha},
            )
            r.raise_for_status()
        return branch_name

    async def commit_file(
        self,
        user_id: UUID,
        connection_id: UUID,
        full_name: str,
        branch_name: str,
        file_path: str,
        content: str,
        commit_message: str,
        existing_sha: Optional[str] = None,
    ) -> str:
        """Create or update a file on a branch. Returns the new commit SHA."""
        conn = await self._get_connection(user_id, connection_id)
        payload: Dict[str, Any] = {
            "message": commit_message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch_name,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        async with self._client(conn) as client:
            r = await client.put(
                f"{conn.api_base_url}/repos/{full_name}/contents/{file_path}",
                json=payload,
            )
            r.raise_for_status()
        return r.json()["commit"]["sha"]

    async def create_pull_request(
        self,
        user_id: UUID,
        connection_id: UUID,
        full_name: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        """Open a Pull Request via GitHub REST API."""
        conn = await self._get_connection(user_id, connection_id)
        async with self._client(conn) as client:
            r = await client.post(
                f"{conn.api_base_url}/repos/{full_name}/pulls",
                json={
                    "title": title,
                    "body": body,
                    "head": head_branch,
                    "base": base_branch,
                },
            )
            r.raise_for_status()
        data = r.json()
        return {"pr_number": data["number"], "url": data["html_url"], "state": data["state"]}

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    async def _get_connection(self, user_id: UUID, connection_id: UUID) -> GitHubConnection:
        result = await self.db.execute(
            select(GitHubConnection).where(
                GitHubConnection.id == connection_id,
                GitHubConnection.user_id == user_id,
                GitHubConnection.is_active.is_(True),
            )
        )
        conn = result.scalar_one_or_none()
        if conn is None:
            raise ValueError("GitHub connection not found")
        return conn

    def _client(self, conn: GitHubConnection) -> httpx.AsyncClient:
        token = decrypt_token(conn.encrypted_token)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        return httpx.AsyncClient(headers=headers, timeout=30)

    @retry(**RETRY_SETTINGS)
    async def _fetch_username(self, api_base_url: str, token: str) -> str:
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=15,
        ) as client:
            r = await client.get(f"{api_base_url.rstrip('/')}/user")
            r.raise_for_status()
            return r.json().get("login", "")

    @retry(**RETRY_SETTINGS)
    async def _fetch_all_repos(
        self, client: httpx.AsyncClient, api_base_url: str
    ) -> List[Dict]:
        all_repos = []
        page = 1
        while True:
            r = await client.get(
                f"{api_base_url}/user/repos",
                params={"per_page": 100, "page": page, "sort": "updated"},
            )
            if r.status_code == 401:
                raise ValueError("GitHub Personal Access Token is invalid or expired (401 Bad Credentials). Please update your GitHub token under Settings.")
            if r.status_code == 403:
                raise ValueError("GitHub API access forbidden (403). Please check your token permissions.")
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            all_repos.extend(batch)
            page += 1
        return all_repos
