from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.deps import get_current_admin
from app.services.auth_service import AuthService
from app.schemas.entities import LoginRequest, TokenResponse, AdminUserRead
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Admin Auth"])

@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
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
