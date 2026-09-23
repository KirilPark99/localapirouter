from typing import Optional
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
                    return None
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
        sim_key_id = request.headers.get("X-Router-Key-Id")
        if sim_key_id and sim_key_id.isdigit():
            sim_key = (await db.execute(select(RouterApiKey).where(RouterApiKey.id == int(sim_key_id)))).scalar_one_or_none()
            if sim_key:
                return sim_key
        return None

    # Check Router API key
    valid, key_obj, err_msg = await ApiKeyService.authenticate_key(db, raw_token)
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err_msg)

    return key_obj
