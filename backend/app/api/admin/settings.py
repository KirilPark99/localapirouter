from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.core.config import settings

router = APIRouter(prefix="/settings", tags=["Admin Settings"])

@router.get("")
async def get_settings(username: str = Depends(get_current_admin)):
    return {
        "log_request_content": settings.LOG_REQUEST_CONTENT,
        "default_timeout_seconds": settings.DEFAULT_TIMEOUT_SECONDS,
        "fusion_timeout_seconds": settings.FUSION_TIMEOUT_SECONDS,
        "max_fallback_attempts": settings.MAX_FALLBACK_ATTEMPTS,
        "database_url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL,
        "master_key_configured": bool(settings.ROUTER_MASTER_KEY),
    }

@router.post("")
async def update_settings(payload: dict, username: str = Depends(get_current_admin)):
    if "log_request_content" in payload:
        settings.LOG_REQUEST_CONTENT = bool(payload["log_request_content"])
    return {"message": "Settings updated", "log_request_content": settings.LOG_REQUEST_CONTENT}
