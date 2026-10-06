from typing import Optional
from ipaddress import ip_address, ip_network
from fastapi import Depends, HTTPException, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.auth_service import AuthService
from app.services.api_key_service import ApiKeyService
from app.models.entities import RouterApiKey, AdminUser

async def get_current_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> str:
    # Check Authorization Bearer header or cookie
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = AuthService.verify_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    admin = (await db.execute(select(AdminUser).where(
        AdminUser.username == username,
        AdminUser.is_active == True,
    ))).scalar_one_or_none()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account is inactive or no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username

def _check_key_ip(request, key):
    if not key.ip_restrictions:
        return
    try:
        peer = ip_address(request.client.host) if request.client else None
        allowed = peer is not None and any(peer in ip_network(value, strict=False) for value in key.ip_restrictions)
    except ValueError:
        allowed = False
    if not allowed:
        raise HTTPException(status_code=403, detail="Client IP is not allowed by this API key")


async def _admin_simulation_key(request, db):
    value = request.headers.get("X-Router-Key-Id")
    if value is None:
        return None
    if not value.isascii() or not value.isdigit() or int(value) <= 0:
        raise HTTPException(status_code=400, detail="Router key ID must be a positive integer")
    key = await ApiKeyService.get_key(db, int(value))
    if key is None:
        raise HTTPException(status_code=404, detail="Router key does not exist")
    if not key.enabled:
        raise HTTPException(status_code=403, detail="Router key is disabled")
    _check_key_ip(request, key)
    return key


async def get_router_key_dep(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    db: AsyncSession = Depends(get_db),
) -> Optional[RouterApiKey]:
    if not authorization and not x_api_key:
        # Check if admin is logged in (allows admin to test via playground without creating an API key)
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            cookie_admin = AuthService.verify_access_token(cookie_token)
            if cookie_admin:
                active_admin = (await db.execute(select(AdminUser).where(
                    AdminUser.username == cookie_admin,
                    AdminUser.is_active == True,
                ))).scalar_one_or_none()
                if active_admin:
                    return await _admin_simulation_key(request, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer sk-router-...",
        )

    if authorization:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header must start with Bearer",
            )
        raw_token = authorization[7:].strip()
    else:
        raw_token = (x_api_key or "").strip()

    # Admin JWTs are accepted only through the Bearer header.
    admin_user = AuthService.verify_access_token(raw_token) if authorization else None
    if admin_user:
        active_admin = (await db.execute(select(AdminUser).where(
            AdminUser.username == admin_user,
            AdminUser.is_active == True,
        ))).scalar_one_or_none()
        if not active_admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin account is inactive")
        return await _admin_simulation_key(request, db)

    # Check Router API key
    valid, key_obj, err_msg = await ApiKeyService.authenticate_key(db, raw_token)
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err_msg)

    _check_key_ip(request, key_obj)
    return key_obj


async def get_inference_key_dep(request: Request, router_key=Depends(get_router_key_dep)):
    try:
        yield router_key
    finally:
        reservation = getattr(request.state, "key_reservation", None)
        if reservation is not None:
            reservation.finish(getattr(request.state, "key_actual_tokens", None))
