from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.cache.response_cache import ResponseCacheService

router = APIRouter(prefix="/cache", tags=["Admin Cache"])


@router.get("/stats")
async def get_cache_stats(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    stats = await ResponseCacheService.get_metrics(db)
    return stats


@router.post("/clear")
async def clear_cache(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    try:
        return await ResponseCacheService.clear_cache(db)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Response cache clear failed; try again") from exc
