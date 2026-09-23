from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.proxy_service import ProxyService
from app.schemas.entities import (
    ProxyCreate,
    ProxyUpdate,
    ProxyRead,
    ProxyTestResult,
    ProxyParseRequest,
    ProxyParseResult,
)

router = APIRouter(prefix="/proxies", tags=["Admin Proxies"])

@router.get("/server-ip")
async def get_server_ip(
    username: str = Depends(get_current_admin),
):
    ip = await ProxyService.get_server_ip()
    return {"server_ip": ip}

@router.post("/parse", response_model=ProxyParseResult)
async def parse_proxy_string(
    data: ProxyParseRequest,
    username: str = Depends(get_current_admin),
):
    result = ProxyService.parse_raw_proxy(data.raw)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to parse proxy format. Supported formats: host:port:user:pass, socks5://user:pass@host:port, user:pass@host:port, host:port")
    return result

@router.post("/test-raw", response_model=ProxyTestResult)
async def test_raw_proxy(
    data: ProxyCreate,
    username: str = Depends(get_current_admin),
):
    return await ProxyService.test_raw_proxy(data)

@router.post("/test-all")
async def test_all_proxies(
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    proxies = await ProxyService.list_proxies(db)
    results = {}
    for p in proxies:
        res = await ProxyService.test_proxy(db, p.id)
        results[p.id] = res.model_dump()
    return {"results": results, "total": len(proxies)}

@router.get("", response_model=List[ProxyRead])
async def list_proxies(
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ProxyService.list_proxies(db)

@router.post("", response_model=ProxyRead, status_code=status.HTTP_201_CREATED)
async def create_proxy(
    data: ProxyCreate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ProxyService.create_proxy(db, data)

@router.put("/{proxy_id}", response_model=ProxyRead)
async def update_proxy(
    proxy_id: int,
    data: ProxyUpdate,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    updated = await ProxyService.update_proxy(db, proxy_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return updated

@router.delete("/{proxy_id}")
async def delete_proxy(
    proxy_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    success = await ProxyService.delete_proxy(db, proxy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return {"message": "Proxy deleted"}

@router.post("/{proxy_id}/test", response_model=ProxyTestResult)
async def test_proxy(
    proxy_id: int,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await ProxyService.test_proxy(db, proxy_id)
