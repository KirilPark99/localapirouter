from datetime import datetime, timezone, timedelta
from typing import Optional
import jwt
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import AdminUser
from app.core.config import settings

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt(12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        payload = {
            "sub": subject,
            "iat": now,
            "exp": expire,
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def verify_access_token(token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            return payload.get("sub")
        except Exception:
            return None

    @classmethod
    async def init_admin_user(cls, db: AsyncSession):
        """Ensure initial admin user exists."""
        result = await db.execute(select(AdminUser).where(AdminUser.username == settings.ADMIN_USERNAME))
        admin = result.scalar_one_or_none()
        if not admin:
            new_admin = AdminUser(
                username=settings.ADMIN_USERNAME,
                password_hash=cls.hash_password(settings.ADMIN_PASSWORD),
                is_active=True,
            )
            db.add(new_admin)
            await db.commit()

    @classmethod
    async def authenticate_admin(cls, db: AsyncSession, username: str, password: str) -> Optional[AdminUser]:
        result = await db.execute(select(AdminUser).where(AdminUser.username == username))
        admin = result.scalar_one_or_none()
        if not admin or not admin.is_active:
            return None
        if not cls.verify_password(password, admin.password_hash):
            return None
        return admin

    @classmethod
    async def change_password(cls, db: AsyncSession, username: str, new_password: str) -> bool:
        result = await db.execute(select(AdminUser).where(AdminUser.username == username))
        admin = result.scalar_one_or_none()
        if not admin:
            return False
        admin.password_hash = cls.hash_password(new_password)
        await db.commit()
        return True
