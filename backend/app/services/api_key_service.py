import hashlib
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select, update, or_
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
            permissions=getattr(data, "permissions", ["direct", "routes", "fusion", "judge"]),
            allowed_models=getattr(data, "allowed_models", ["*"]),
            allowed_routes=getattr(data, "allowed_routes", ["*"]),
            allowed_fusions=getattr(data, "allowed_fusions", ["*"]),
            allowed_judges=getattr(data, "allowed_judges", ["*"]),
            rate_limit_rpm=getattr(data, "rate_limit_rpm", None),
            rate_limit_tpm=getattr(data, "rate_limit_tpm", None),
            request_limit=getattr(data, "request_limit", None),
            total_requests=0,
            expiration_date=getattr(data, "expiration_date", None),
            ip_restrictions=getattr(data, "ip_restrictions", []),
            notes=getattr(data, "notes", None),
        )
        key_obj.quota_rules = cls._prepare_rules(getattr(data, "quota_rules", []) or [], [])
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

        if "quota_rules" in data.model_fields_set:
            from app.services.quota_service import lock_key
            k = await lock_key(db, key_id)
            k.quota_rules = cls._prepare_rules(data.quota_rules or [], k.quota_rules or [])
        if data.name is not None:
            k.name = data.name
        if data.enabled is not None:
            k.enabled = data.enabled
        if "notes" in data.model_fields_set:
            raw_notes = data.notes
            k.notes = raw_notes.strip() if (raw_notes and isinstance(raw_notes, str) and raw_notes.strip()) else None
        if data.permissions is not None:
            k.permissions = data.permissions
        if data.allowed_models is not None:
            k.allowed_models = data.allowed_models
        if data.allowed_routes is not None:
            k.allowed_routes = data.allowed_routes
        if data.allowed_fusions is not None:
            k.allowed_fusions = data.allowed_fusions
        if data.allowed_judges is not None:
            k.allowed_judges = data.allowed_judges
        if "rate_limit_rpm" in data.model_fields_set:
            k.rate_limit_rpm = data.rate_limit_rpm
        if "rate_limit_tpm" in data.model_fields_set:
            k.rate_limit_tpm = data.rate_limit_tpm
        if "request_limit" in data.model_fields_set:
            k.request_limit = data.request_limit
        if "expiration_date" in data.model_fields_set:
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

        if key_obj.request_limit is not None and key_obj.total_requests >= key_obj.request_limit:
            return False, None, "API Key request limit reached"

        return True, key_obj, "OK"

    @classmethod
    async def admit_inference(cls, db: AsyncSession, key: RouterApiKey, requested_model=None):
        from app.core.errors import RouterException, ErrorCategory
        from app.services.quota_service import QuotaService
        from app.services.log_service import request_telemetry
        now = datetime.now(timezone.utc)
        result = await db.execute(update(RouterApiKey).where(
            RouterApiKey.id == key.id, RouterApiKey.enabled == True,
            or_(RouterApiKey.expiration_date.is_(None), RouterApiKey.expiration_date > now),
            or_(RouterApiKey.request_limit.is_(None), RouterApiKey.total_requests < RouterApiKey.request_limit),
        ).values(total_requests=RouterApiKey.total_requests + 1, last_used_at=now).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            await db.rollback()
            raise RouterException("API key inference quota reached or key is no longer active", ErrorCategory.RATE_LIMIT, status_code=429)
        direct_rules = []
        try:
            current = await db.scalar(select(RouterApiKey).where(RouterApiKey.id == key.id).execution_options(populate_existing=True))
            if current.quota_rules:
                direct_rules = await QuotaService.admit(db, current, requested_model)
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
        details = request_telemetry.get()
        if details is not None:
            details['router_key_id'] = key.id
            details['quota_direct_pending'] = direct_rules
            if requested_model is not None:
                details['requested_model'] = requested_model

    @staticmethod
    def _restore_credential_rules(rules, existing):
        from pydantic import TypeAdapter
        from app.schemas.entities import CredentialQuotaRules
        validated = TypeAdapter(CredentialQuotaRules).validate_python(rules)
        known = [r for r in existing if r.get('id')]
        identity = ('scope', 'model', 'period', 'duration_seconds', 'anchor', 'start', 'end')
        restored = []
        for rule in validated:
            value = rule.model_dump(mode='json')
            old = next((r for r in known if all(r.get(k) == value.get(k) for k in identity)), None)
            restored.append(rule.model_copy(update={'id': old['id'] if old else None}))
        return ApiKeyService._prepare_rules(restored, known)

    @staticmethod
    def _prepare_rules(rules, existing):
        import uuid
        from fastapi import HTTPException
        known = {r['id']: r for r in existing}
        result = []
        identity_fields = ('scope', 'model', 'period', 'duration_seconds', 'anchor', 'start', 'end')
        for rule in rules:
            value = rule.model_dump(mode='json')
            if value['id']:
                old = known.get(value['id'])
                if not old:
                    raise HTTPException(422, 'Quota rule ID does not belong to this key')
                if any(old.get(f) != value.get(f) for f in identity_fields):
                    raise HTTPException(422, 'Existing quota scope/window is immutable; remove and add a rule to change it')
            else:
                value['id'] = uuid.uuid4().hex
            result.append(value)
        return result

    @staticmethod
    def _build_read(k: RouterApiKey) -> RouterApiKeyRead:
        return RouterApiKeyRead(
            id=k.id,
            quota_rules=k.quota_rules or [],
            name=k.name,
            key_prefix=k.key_prefix,
            masked_key=k.masked_key,
            enabled=k.enabled,
            permissions=k.permissions,
            allowed_models=k.allowed_models,
            allowed_routes=k.allowed_routes,
            allowed_fusions=k.allowed_fusions,
            allowed_judges=k.allowed_judges if k.allowed_judges is not None else ["*"],
            rate_limit_rpm=k.rate_limit_rpm,
            rate_limit_tpm=k.rate_limit_tpm,
            request_limit=k.request_limit,
            total_requests=k.total_requests,
            expiration_date=k.expiration_date,
            ip_restrictions=k.ip_restrictions,
            last_used_at=k.last_used_at,
            notes=k.notes,
            created_at=k.created_at,
        )

    @classmethod
    async def get_key(cls, db: AsyncSession, key_id: int) -> Optional[RouterApiKey]:
        result = await db.execute(select(RouterApiKey).where(RouterApiKey.id == key_id))
        return result.scalar_one_or_none()

    @classmethod
    async def update_key_notes(cls, db: AsyncSession, key_id: int, notes: Optional[str]) -> Optional[str]:
        result = await db.execute(select(RouterApiKey).where(RouterApiKey.id == key_id))
        k = result.scalar_one_or_none()
        if not k:
            return None
        clean_notes = notes.strip() if notes and isinstance(notes, str) and notes.strip() else None
        k.notes = clean_notes
        await db.commit()
        await db.refresh(k)
        return k.notes
