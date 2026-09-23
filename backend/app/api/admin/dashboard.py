from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.log_service import LogService
from app.schemas.entities import DashboardStats, DetailedAnalyticsResponse

router = APIRouter(prefix="/dashboard", tags=["Admin Dashboard"])

@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await LogService.get_dashboard_stats(db)

@router.get("/detailed-stats", response_model=DetailedAnalyticsResponse)
async def get_detailed_stats(
    period: str = "all",
    granularity: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    filter_type: Optional[str] = None,
    filter_value: Optional[str] = None,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await LogService.get_detailed_analytics(
        db,
        period=period,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        filter_type=filter_type,
        filter_value=filter_value,
    )
