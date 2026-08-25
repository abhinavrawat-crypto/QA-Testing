"""Application configuration using Pydantic Settings (v2)."""
from functools import lru_cache
from typing import List
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "AI QA Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "info"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Security
    SECRET_KEY: str
    ENCRYPTION_KEY: str  # Fernet key for encrypting stored tokens
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # JIRA OAuth
    JIRA_CLIENT_ID: str = ""
    JIRA_CLIENT_SECRET: str = ""
    JIRA_REDIRECT_URI: str = "http://localhost:8000/api/auth/jira/callback"

    # GitHub OAuth
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:8000/api/auth/github/callback"

    # Docker / Sandbox
    DOCKER_HOST: str = "unix:///var/run/docker.sock"
    PLAYWRIGHT_IMAGE: str = "mcr.microsoft.com/playwright:v1.45.0-noble"
    SANDBOX_TIMEOUT_SECONDS: int = 300
    SANDBOX_MEMORY_LIMIT: str = "512m"
    SANDBOX_CPU_LIMIT: float = 1.0

    # Storage
    STORAGE_BACKEND: str = "local"
    ARTIFACTS_BASE_PATH: str = "/tmp/aiqa_artifacts"


@lru_cache
def get_settings() -> Settings:
    return Settings()
