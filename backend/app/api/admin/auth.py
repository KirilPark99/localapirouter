from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.auth_service import AuthService
from app.services.oidc_service import OidcService
from app.security.registry import GuardrailRegistry
from app.schemas.entities import LoginRequest, TokenResponse, AdminUserRead
from app.core.config import settings
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Admin Auth"])


@router.get("/config")
async def get_auth_config(db: AsyncSession = Depends(get_db)):
    """Public endpoint returning dashboard authentication capabilities."""
    cfg = await GuardrailRegistry.get_security_config(db)
    oidc_enabled = cfg.get("oidc_enabled", False)
    disable_pw = cfg.get("oidc_disable_password_login", False)

    return {
        "oidc_enabled": oidc_enabled,
        "oidc_disable_password_login": disable_pw,
        "password_login_allowed": not (oidc_enabled and disable_pw),
    }


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    cfg = await GuardrailRegistry.get_security_config(db)
    if cfg.get("oidc_enabled") and cfg.get("oidc_disable_password_login"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password login is disabled by administrator. Please log in via SSO (OIDC).",
        )

    admin = await AuthService.authenticate_admin(db, data.username, data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = AuthService.create_access_token(admin.username)
    # Set secure HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return TokenResponse(access_token=token, username=admin.username)


@router.get("/oidc/login")
async def oidc_login(request: Request, db: AsyncSession = Depends(get_db)):
    """Initiate OIDC authorization flow."""
    redirect_uri = str(request.url_for("oidc_callback"))
    # In case request is behind a proxy or HTTPS terminator
    if "x-forwarded-proto" in request.headers and request.headers["x-forwarded-proto"] == "https":
        redirect_uri = redirect_uri.replace("http://", "https://")

    auth_url = await OidcService.get_authorization_url(db, redirect_uri=redirect_uri)
    if not auth_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC Single Sign-On is not configured or disabled.",
        )

    if request.headers.get("accept") == "application/json":
        return {"authorization_url": auth_url}

    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/oidc/callback")
async def oidc_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Handle callback from OIDC identity provider."""
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OIDC error returned by provider: {error}",
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code from identity provider",
        )

    redirect_uri = str(request.url_for("oidc_callback"))
    if "x-forwarded-proto" in request.headers and request.headers["x-forwarded-proto"] == "https":
        redirect_uri = redirect_uri.replace("http://", "https://")

    try:
        user_data = await OidcService.exchange_code(db, code=code, redirect_uri=redirect_uri)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {e}",
        )

    token = user_data["access_token"]
    username = user_data["username"]

    # Redirect to home / dashboard with cookie set
    redirect_resp = RedirectResponse(url="/", status_code=302)
    redirect_resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return redirect_resp


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(username: str = Depends(get_current_admin)):
    return {"username": username, "authenticated": True}


@router.post("/change-password")
async def change_password(
    payload: dict,
    username: str = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    new_password = payload.get("new_password", "")
    if len(new_password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")
    success = await AuthService.change_password(db, username, new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Could not update password")
    return {"message": "Password changed successfully"}
