"""Settings router — view and update system configurations (e.g., Gemini API Key)."""
import os
import re
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.core.dependencies import CurrentUser
from app.services.ai_service import reload_ai_provider

router = APIRouter(prefix="/settings", tags=["Settings"])


class UpdateSettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None


class SettingsStatusResponse(BaseModel):
    gemini_api_key_configured: bool
    gemini_api_key_masked: str
    gemini_model: str


@router.get("", response_model=SettingsStatusResponse)
async def get_settings_status(current_user: CurrentUser):
    settings = get_settings()
    key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    is_configured = bool(key and key.strip())
    masked = f"{key[:6]}...{key[-4:]}" if is_configured and len(key) > 10 else ("Configured" if is_configured else "")

    return SettingsStatusResponse(
        gemini_api_key_configured=is_configured,
        gemini_api_key_masked=masked,
        gemini_model=settings.GEMINI_MODEL,
    )


@router.post("", response_model=SettingsStatusResponse)
async def update_settings(payload: UpdateSettingsRequest, current_user: CurrentUser):
    env_path = "/home/rawatabhinav93/ai_test_platform/.env"
    env_updated = False

    if payload.gemini_api_key is not None:
        new_key = payload.gemini_api_key.strip()
        os.environ["GEMINI_API_KEY"] = new_key
        env_updated = True

    if payload.gemini_model is not None and payload.gemini_model.strip():
        new_model = payload.gemini_model.strip()
        os.environ["GEMINI_MODEL"] = new_model
        env_updated = True

    if env_updated:
        try:
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if payload.gemini_api_key is not None:
                    new_key = payload.gemini_api_key.strip()
                    if "GEMINI_API_KEY=" in content:
                        content = re.sub(r"GEMINI_API_KEY=.*", f"GEMINI_API_KEY={new_key}", content)
                    else:
                        content += f"\nGEMINI_API_KEY={new_key}\n"

                if payload.gemini_model is not None and payload.gemini_model.strip():
                    new_model = payload.gemini_model.strip()
                    if "GEMINI_MODEL=" in content:
                        content = re.sub(r"GEMINI_MODEL=.*", f"GEMINI_MODEL={new_model}", content)
                    else:
                        content += f"\nGEMINI_MODEL={new_model}\n"

                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception:
            pass

        # Clear lru_cache and reload provider
        get_settings.cache_clear()
        reload_ai_provider()

    return await get_settings_status(current_user=current_user)
