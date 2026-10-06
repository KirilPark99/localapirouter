from typing import List, Optional
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.log_service import LogService
from app.schemas.entities import RequestLogRead, LogsSummaryResponse, LogDateFilter

router = APIRouter(prefix="/logs", tags=["Admin Logs"])

@router.get("/summary", response_model=LogsSummaryResponse)
async def get_logs_summary(
    start_date: Optional[LogDateFilter] = None,
    end_date: Optional[LogDateFilter] = None,
    mode: Optional[str] = None,
    status: Optional[str] = None,
    status_code: Optional[int] = None,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
    router_key_id: Optional[int] = None,
    has_error: Optional[bool] = None,
    has_fallback: Optional[bool] = None,
    min_latency: Optional[float] = None,
    is_stream: Optional[bool] = None,
    search: Optional[str] = None,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await LogService.get_logs_summary(
        db,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        status=status,
        status_code=status_code,
        provider_id=provider_id,
        model=model,
        router_key_id=router_key_id,
        has_error=has_error,
        has_fallback=has_fallback,
        min_latency=min_latency,
        is_stream=is_stream,
        search=search,
    )

@router.get("", response_model=List[RequestLogRead])
async def list_logs(
    response: Response,
    limit: int = 50,
    offset: int = 0,
    start_date: Optional[LogDateFilter] = None,
    end_date: Optional[LogDateFilter] = None,
    mode: Optional[str] = None,
    status: Optional[str] = None,
    status_code: Optional[int] = None,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
    router_key_id: Optional[int] = None,
    has_error: Optional[bool] = None,
    has_fallback: Optional[bool] = None,
    min_latency: Optional[float] = None,
    is_stream: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    total = await LogService.count_logs(
        db,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        status=status,
        status_code=status_code,
        provider_id=provider_id,
        model=model,
        router_key_id=router_key_id,
        has_error=has_error,
        has_fallback=has_fallback,
        min_latency=min_latency,
        is_stream=is_stream,
        search=search,
    )
    response.headers["X-Total-Count"] = str(total)
    return await LogService.list_logs(
        db,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        status=status,
        status_code=status_code,
        provider_id=provider_id,
        model=model,
        router_key_id=router_key_id,
        has_error=has_error,
        has_fallback=has_fallback,
        min_latency=min_latency,
        is_stream=is_stream,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
