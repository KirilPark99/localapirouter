import hashlib
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import RouterApiKey
from app.schemas.entities import (
    RouterApiKeyCreate,
    RouterApiKeyUpdate,
    RouterApiKeyRead,
    RouterApiKeyCreated,
)
from app.core.crypto import mask_secret

class ApiKeyService:
    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()

    @classmethod
    async def list_keys(cls, db: AsyncSession) -> List[RouterApiKeyRead]:
        result = await db.execute(select(RouterApiKey).order_by(RouterApiKey.id.desc()))
        keys = result.scalars().all()
        return [cls._build_read(k) for k in keys]

    @classmethod
    async def create_key(cls, db: AsyncSession, data: RouterApiKeyCreate) -> RouterApiKeyCreated:
        raw_token = f"sk-router-{secrets.token_hex(24)}"
        key_prefix = raw_token[:14]
        key_hash = cls.hash_key(raw_token)
        masked = mask_secret(raw_token)

        key_obj = RouterApiKey(
            name=data.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            masked_key=masked,
            enabled=True,
            permissions=data.permissions,
            allowed_models=data.allowed_models,
            allowed_routes=data.allowed_routes,
            allowed_fusions=data.allowed_fusions,
            rate_limit_rpm=data.rate_limit_rpm,
            rate_limit_tpm=data.rate_limit_tpm,
            request_limit=data.request_limit,
            total_requests=0,
            expiration_date=data.expiration_date,
            ip_restrictions=data.ip_restrictions,
        )
        db.add(key_obj)
        await db.commit()
        await db.refresh(key_obj)

        read_base = cls._build_read(key_obj)
        return RouterApiKeyCreated(
            **read_base.model_dump(),
            raw_api_key=raw_token,
        )

    @classmethod
    async def update_key(cls, db: AsyncSession, key_id: int, data: RouterApiKeyUpdate) -> Optional[RouterApiKeyRead]:
        result = await db.execute(select(RouterApiKey).where(RouterApiKey.id == key_id))
        k = result.scalar_one_or_none()
        if not k:
            return None

        if data.name is not None:
            k.name = data.name
        if data.enabled is not None:
            k.enabled = data.enabled
        if data.permissions is not None:
            k.permissions = data.permissions
        if data.allowed_models is not None:
            k.allowed_models = data.allowed_models
        if data.allowed_routes is not None:
            k.allowed_routes = data.allowed_routes
        if data.allowed_fusions is not None:
            k.allowed_fusions = data.allowed_fusions
        if data.rate_limit_rpm is not None:
            k.rate_limit_rpm = data.rate_limit_rpm
        if data.rate_limit_tpm is not None:
            k.rate_limit_tpm = data.rate_limit_tpm
        if data.request_limit is not None:
            k.request_limit = data.request_limit
        if data.expiration_date is not None:
            k.expiration_date = data.expiration_date
        if data.ip_restrictions is not None:
            k.ip_restrictions = data.ip_restrictions

        await db.commit()
        await db.refresh(k)
        return cls._build_read(k)

    @classmethod
    async def delete_key(cls, db: AsyncSession, key_id: int) -> bool:
        result = await db.execute(select(RouterApiKey).where(RouterApiKey.id == key_id))
        k = result.scalar_one_or_none()
        if not k:
            return False
        await db.delete(k)
        await db.commit()
        return True

    @classmethod
    async def authenticate_key(cls, db: AsyncSession, raw_token: str) -> Tuple[bool, Optional[RouterApiKey], str]:
        """Validate an incoming Router API key from Bearer token."""
        clean_token = raw_token.strip()
        if not clean_token.startswith("sk-router-"):
            return False, None, "Invalid Router API Key format. Expected sk-router-..."

        hashed = cls.hash_key(clean_token)
        result = await db.execute(select(RouterApiKey).where(RouterApiKey.key_hash == hashed))
        key_obj = result.scalar_one_or_none()
        if not key_obj:
            return False, None, "Invalid API Key"

        if not key_obj.enabled:
            return False, None, "API Key is disabled"

        now = datetime.now(timezone.utc)
        expiration = key_obj.expiration_date
        if expiration and expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        if expiration and now > expiration:
            return False, None, "API Key has expired"

        if key_obj.request_limit and key_obj.total_requests >= key_obj.request_limit:
            return False, None, "API Key request limit reached"

        # Update last used and total requests
        key_obj.last_used_at = now
        key_obj.total_requests += 1
        await db.commit()

        return True, key_obj, "OK"

    @staticmethod
    def _build_read(k: RouterApiKey) -> RouterApiKeyRead:
        return RouterApiKeyRead(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            masked_key=k.masked_key,
            enabled=k.enabled,
            permissions=k.permissions,
            allowed_models=k.allowed_models,
            allowed_routes=k.allowed_routes,
            allowed_fusions=k.allowed_fusions,
            rate_limit_rpm=k.rate_limit_rpm,
            rate_limit_tpm=k.rate_limit_tpm,
            request_limit=k.request_limit,
            total_requests=k.total_requests,
            expiration_date=k.expiration_date,
            ip_restrictions=k.ip_restrictions,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
