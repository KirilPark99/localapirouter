import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.entities import ProviderCredential, Provider, Proxy, CredentialModelPreference, DiscoveredModel
from app.schemas.entities import CredentialCreate, CredentialUpdate, CredentialRead, CredentialTestResult
from app.core.crypto import encrypt_secret, decrypt_secret, compute_fingerprint, mask_secret
from app.core.circuit_breaker import circuit_breaker, CredentialStatus
from app.adapters.factory import get_adapter
from app.services.proxy_service import ProxyService
from app.core.errors import RouterException

class CredentialService:
    @classmethod
    def module_runtime_configuration(cls, provider, credential):
        configuration = {**provider.adapter_configuration,
            "credential_metadata": getattr(credential, "metadata_json", {}) or {}}
        configuration["credential_id"] = credential.id
        if configuration.get("module_id") not in ("codex_cli", "grok_builder_cli"):
            return configuration

        async def persist_credentials(fields):
            import json
            from app.core.database import AsyncSessionLocal
            if (not isinstance(fields, dict) or not fields or
                any(name not in ("access_token", "refresh_token", "id_token") or not isinstance(value, str) or not value for name, value in fields.items())):
                raise ValueError("Invalid rotated CLI token fields")
            async with AsyncSessionLocal() as db:
                current = await cls.get_credential(db, credential.id)
                if current is None:
                    raise ValueError("CLI credential was deleted during refresh")
                values = json.loads(decrypt_secret(current.encrypted_api_key))
                if not isinstance(values, dict):
                    raise ValueError("CLI credentials must use encrypted JSON storage")
                values.update(fields)
                if values.get("auth_json"):
                    auth = json.loads(values["auth_json"])
                    if not isinstance(auth, dict):
                        raise ValueError("Invalid pasted CLI auth JSON")
                    if configuration["module_id"] == "codex_cli":
                        tokens = auth.get("tokens") if isinstance(auth.get("tokens"), dict) else auth
                        tokens.update(fields)
                    else:
                        for entry in auth.values():
                            if isinstance(entry, dict) and ("key" in entry or "access_token" in entry):
                                entry.update(fields)
                                if "key" in entry:
                                    entry["key"] = fields["access_token"]
                                break
                        else:
                            raise ValueError("Grok pasted auth JSON has no token entry")
                    values["auth_json"] = json.dumps(auth)
                await cls.update_credential(db, current.id, CredentialUpdate(api_key=json.dumps(values)))

        configuration["persist_credentials"] = persist_credentials
        return configuration

    @staticmethod
    def _is_keyless(provider: Provider, raw_key: str) -> bool:
        allowed = provider.auth_type == "none" or (provider.configuration or {}).get("external_auth") is True
        sentinel = raw_key.lower() in ("no-key", "none", "empty", "keyless", "")
        if sentinel and not allowed:
            raise ValueError("API Key cannot be empty/keyless for authenticated providers; explicitly select No Auth or external_auth")
        return provider.auth_type == "none" or sentinel

    @classmethod
    async def list_credentials(cls, db: AsyncSession, provider_id: Optional[int] = None) -> List[CredentialRead]:
        query = select(ProviderCredential).options(
            selectinload(ProviderCredential.provider),
            selectinload(ProviderCredential.proxy),
            selectinload(ProviderCredential.discovered_models),
        )
        if provider_id is not None:
            query = query.where(ProviderCredential.provider_id == provider_id)
        query = query.order_by(ProviderCredential.priority.asc(), ProviderCredential.id.desc())

        result = await db.execute(query)
        creds = result.scalars().all()
        return [cls._build_credential_read(c) for c in creds]

    @staticmethod
    def _build_credential_read(c: ProviderCredential) -> CredentialRead:
        cb_status = circuit_breaker.get_status(c.id)
        status = cb_status["status"] if cb_status["status"] != CredentialStatus.UNKNOWN else c.status
        if not c.enabled:
            status = CredentialStatus.DISABLED
        cooldown_until = cb_status.get("cooldown_until") or c.cooldown_until
        model_cooldowns = cb_status.get("model_cooldowns") or None

        return CredentialRead(
            id=c.id,
            quota_rules=c.quota_rules or [],
            provider_id=c.provider_id,
            provider_name=c.provider.name,
            name=c.name,
            group_name=c.group_name,
            masked_key=c.masked_key,
            key_fingerprint=c.key_fingerprint,
            enabled=c.enabled,
            proxy_id=c.proxy_id,
            proxy_name=c.proxy.name if c.proxy else None,
            status=status,
            last_checked_at=c.last_checked_at,
            last_success_at=c.last_success_at,
            last_error=c.last_error,
            consecutive_failures=c.consecutive_failures,
            cooldown_until=cooldown_until,
            model_cooldowns=model_cooldowns,
            priority=c.priority,
            weight=c.weight,
            rpm_limit=c.rpm_limit,
            tpm_limit=c.tpm_limit,
            max_concurrency=c.max_concurrency,
            notes=c.notes,
            discovered_models_count=len(c.discovered_models) if c.discovered_models else 0,
            created_at=c.created_at,
        )

    @classmethod
    async def get_credential(cls, db: AsyncSession, credential_id: int) -> Optional[ProviderCredential]:
        result = await db.execute(
            select(ProviderCredential).where(ProviderCredential.id == credential_id).options(
                selectinload(ProviderCredential.provider),
                selectinload(ProviderCredential.proxy),
                selectinload(ProviderCredential.discovered_models),
                selectinload(ProviderCredential.model_preferences).selectinload(CredentialModelPreference.model),
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    async def create_credential(cls, db: AsyncSession, data: CredentialCreate) -> CredentialRead:
        prov_res = await db.execute(select(Provider).where(Provider.id == data.provider_id))
        prov = prov_res.scalar_one_or_none()
        if not prov:
            raise ValueError(f"Provider {data.provider_id} not found")

        raw_key = (data.api_key or "").strip()
        is_keyless = cls._is_keyless(prov, raw_key)

        if not is_keyless:
            if not raw_key:
                raise ValueError("API Key cannot be empty for authenticated providers")
            if raw_key.startswith("http://") or raw_key.startswith("https://"):
                raise ValueError("The provided API key looks like a URL. Please enter your actual provider API key / secret token, not the Base URL.")
            fingerprint = compute_fingerprint(raw_key)
            encrypted_key = encrypt_secret(raw_key)
            masked = mask_secret(raw_key)

            # Check duplicate key for same provider
            dup_query = await db.execute(
                select(ProviderCredential).where(
                    ProviderCredential.provider_id == data.provider_id,
                    ProviderCredential.key_fingerprint == fingerprint,
                )
            )
            if dup_query.scalar_one_or_none():
                raise ValueError("This API Key is already registered for this provider.")
        else:
            raw_key = "no-key"
            fingerprint = f"keyless_{data.provider_id}_{uuid.uuid4().hex[:12]}"
            encrypted_key = encrypt_secret("no-key")
            masked = "(Keyless / No Auth)"

        from app.services.api_key_service import ApiKeyService
        rules = ApiKeyService._prepare_rules(getattr(data, "quota_rules", []), [])
        raw_group = getattr(data, "group_name", None)
        cred = ProviderCredential(
            provider_id=data.provider_id,
            name=data.name,
            group_name=(raw_group.strip() if raw_group and raw_group.strip() else None),
            encrypted_api_key=encrypted_key,
            key_fingerprint=fingerprint,
            masked_key=masked,
            enabled=True,
            proxy_id=data.proxy_id,
            status=CredentialStatus.HEALTHY,
            priority=data.priority,
            weight=data.weight,
            rpm_limit=data.rpm_limit,
            tpm_limit=data.tpm_limit,
            max_concurrency=data.max_concurrency,
            notes=getattr(data, "notes", None),
            consecutive_failures=0,
            metadata_json={},
            quota_rules=rules,
        )
        db.add(cred)
        await db.commit()

        # Fetch with relationships
        full_cred = await cls.get_credential(db, cred.id)
        assert full_cred is not None

        return cls._build_credential_read(full_cred)

    @classmethod
    async def close_module_profile(cls, provider, credential_id: int) -> None:
        from app.modules.loader import ModuleLoader
        module = ModuleLoader.get_adapter((provider.configuration or {}).get("module_id", ""))
        if module:
            await module.close_profile(credential_id)

    @classmethod
    async def update_credential(cls, db: AsyncSession, credential_id: int, data: CredentialUpdate) -> Optional[CredentialRead]:
        cred = await cls.get_credential(db, credential_id)
        if not cred:
            return None

        if "quota_rules" in data.model_fields_set:
            from app.services.api_key_service import ApiKeyService
            from app.services.quota_service import lock_key
            cred = await lock_key(db, credential_id, ProviderCredential)
            cred.quota_rules = ApiKeyService._prepare_rules(data.quota_rules or [], cred.quota_rules or [])
        if data.name is not None:
            cred.name = data.name
        if "group_name" in data.model_fields_set:
            raw_g = data.group_name
            cred.group_name = raw_g.strip() if (raw_g and isinstance(raw_g, str) and raw_g.strip()) else None
        if "notes" in data.model_fields_set:
            raw_notes = data.notes
            cred.notes = raw_notes.strip() if (raw_notes and isinstance(raw_notes, str) and raw_notes.strip()) else None
        if data.api_key is not None:
            clean_key = data.api_key.strip()
            if cls._is_keyless(cred.provider, clean_key):
                cred.encrypted_api_key = encrypt_secret("no-key")
                if not cred.key_fingerprint.startswith("keyless_"):
                    cred.key_fingerprint = f"keyless_{cred.provider_id}_{uuid.uuid4().hex[:12]}"
                cred.masked_key = "(Keyless / No Auth)"
            else:
                if clean_key.startswith("http://") or clean_key.startswith("https://"):
                    raise ValueError("The provided API key looks like a URL. Please enter your actual provider API key / secret token, not the Base URL.")
                cred.encrypted_api_key = encrypt_secret(clean_key)
                cred.key_fingerprint = compute_fingerprint(clean_key)
                cred.masked_key = mask_secret(clean_key)
        if "proxy_id" in data.model_fields_set:
            cred.proxy_id = data.proxy_id if (data.proxy_id and data.proxy_id > 0) else None
        if data.enabled is not None:
            cred.enabled = data.enabled
            circuit_breaker.reset(credential_id)
        if data.priority is not None:
            cred.priority = data.priority
        if data.weight is not None:
            cred.weight = data.weight
        if "rpm_limit" in data.model_fields_set:
            cred.rpm_limit = data.rpm_limit
        if "tpm_limit" in data.model_fields_set:
            cred.tpm_limit = data.tpm_limit
        if "max_concurrency" in data.model_fields_set:
            cred.max_concurrency = data.max_concurrency

        await db.commit()
        full_cred = await cls.get_credential(db, credential_id)
        assert full_cred is not None
        if data.api_key is not None or data.enabled is False or "proxy_id" in data.model_fields_set:
            await cls.close_module_profile(full_cred.provider, credential_id)
        return cls._build_credential_read(full_cred)

    @classmethod
    async def bulk_assign_proxy(
        cls, db: AsyncSession, credential_ids: List[int], proxy_id: Optional[int]
    ) -> List[CredentialRead]:
        if not credential_ids:
            return []

        clean_proxy_id = proxy_id if (proxy_id and proxy_id > 0) else None
        if clean_proxy_id:
            px_res = await db.execute(select(Proxy).where(Proxy.id == clean_proxy_id))
            if not px_res.scalar_one_or_none():
                raise ValueError(f"Proxy with ID {clean_proxy_id} not found")

        stmt = (
            update(ProviderCredential)
            .where(ProviderCredential.id.in_(credential_ids))
            .values(proxy_id=clean_proxy_id)
        )
        await db.execute(stmt)
        await db.commit()

        result = await db.execute(
            select(ProviderCredential)
            .where(ProviderCredential.id.in_(credential_ids))
            .options(
                selectinload(ProviderCredential.provider),
                selectinload(ProviderCredential.proxy),
                selectinload(ProviderCredential.discovered_models),
            )
            .order_by(ProviderCredential.id.asc())
        )
        creds = result.scalars().all()
        return [cls._build_credential_read(c) for c in creds]

    @classmethod
    async def bulk_assign_group(
        cls, db: AsyncSession, credential_ids: List[int], group_name: Optional[str]
    ) -> List[CredentialRead]:
        if not credential_ids:
            return []

        clean_group = group_name.strip() if (group_name and group_name.strip()) else None
        if clean_group and clean_group.lower() in ("no group", "none", "without group", "default", "без группы"):
            clean_group = None

        stmt = (
            update(ProviderCredential)
            .where(ProviderCredential.id.in_(credential_ids))
            .values(group_name=clean_group)
        )
        await db.execute(stmt)

        # Ensure folder name is persisted in provider configuration folders if given
        if clean_group:
            prov_ids_res = await db.execute(
                select(ProviderCredential.provider_id)
                .where(ProviderCredential.id.in_(credential_ids))
                .distinct()
            )
            for pid in prov_ids_res.scalars().all():
                prov_res = await db.execute(select(Provider).where(Provider.id == pid))
                prov = prov_res.scalar_one_or_none()
                if prov:
                    cfg = dict(prov.configuration or {})
                    folders = list(cfg.get("folders", []))
                    if clean_group not in folders:
                        folders.append(clean_group)
                        cfg["folders"] = folders
                        prov.configuration = cfg

        await db.commit()

        result = await db.execute(
            select(ProviderCredential)
            .where(ProviderCredential.id.in_(credential_ids))
            .options(
                selectinload(ProviderCredential.provider),
                selectinload(ProviderCredential.proxy),
                selectinload(ProviderCredential.discovered_models),
            )
            .order_by(ProviderCredential.id.asc())
        )
        creds = result.scalars().all()
        return [cls._build_credential_read(c) for c in creds]

    @classmethod
    async def delete_credential(cls, db: AsyncSession, credential_id: int) -> bool:
        cred = await cls.get_credential(db, credential_id)
        if not cred:
            return False
        await cls.close_module_profile(cred.provider, credential_id)
        circuit_breaker.reset(credential_id)
        await db.delete(cred)
        await db.commit()
        return True

    @classmethod
    async def test_credential(cls, db: AsyncSession, credential_id: int) -> CredentialTestResult:
        cred = await cls.get_credential(db, credential_id)
        if not cred:
            return CredentialTestResult(success=False, latency_ms=0, message="Credential not found")

        provider = cred.provider
        api_key = decrypt_secret(cred.encrypted_api_key)
        proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None

        adapter = get_adapter(provider.adapter_type)
        t0 = time.perf_counter()

        now = datetime.now(timezone.utc)
        cred.last_checked_at = now

        try:
            success, msg, models_count = await adapter.validate_credentials(
                base_url=provider.base_url,
                api_key=api_key,
                extra_headers=provider.extra_headers,
                configuration=CredentialService.module_runtime_configuration(provider, cred),
                proxy_url=proxy_url,
                timeout=15.0,
            )
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            if success:
                cred.status = CredentialStatus.HEALTHY
                cred.last_success_at = now
                cred.last_error = None
                cred.consecutive_failures = 0
                circuit_breaker.record_success(credential_id)
                await db.commit()
                return CredentialTestResult(
                    success=True,
                    latency_ms=latency_ms,
                    message=msg,
                    models_found=models_count,
                )
            else:
                cred.status = CredentialStatus.INVALID
                cred.last_error = msg
                cred.consecutive_failures += 1
                await db.commit()
                return CredentialTestResult(
                    success=False,
                    latency_ms=latency_ms,
                    message=msg,
                    models_found=0,
                )
        except RouterException as re:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            cred.last_error = re.message
            cred.consecutive_failures += 1
            circuit_breaker.record_failure(credential_id, re.category, re.retry_after, re.message)
            cb = circuit_breaker.get_status(credential_id)
            cred.status = cb["status"]
            await db.commit()
            return CredentialTestResult(
                success=False,
                latency_ms=latency_ms,
                message=re.message,
                models_found=0,
                error_category=re.category.value,
            )
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            cred.status = CredentialStatus.DEGRADED
            cred.last_error = str(e)
            cred.consecutive_failures += 1
            await db.commit()
            return CredentialTestResult(
                success=False,
                latency_ms=latency_ms,
                message=str(e),
                models_found=0,
            )

    @classmethod
    async def reset_circuit_breaker(cls, db: AsyncSession, credential_id: int):
        circuit_breaker.reset(credential_id)
        cred = await cls.get_credential(db, credential_id)
        if cred:
            cred.status = CredentialStatus.HEALTHY
            cred.consecutive_failures = 0
            cred.last_error = None
            cred.cooldown_until = None
            await db.commit()

    @classmethod
    async def set_model_preferences(cls, db: AsyncSession, credential_id: int, model_ids: List[int]):
        await db.execute(delete(CredentialModelPreference).where(CredentialModelPreference.credential_id == credential_id))
        for order, mid in enumerate(model_ids):
            pref = CredentialModelPreference(
                credential_id=credential_id,
                model_id=mid,
                priority_order=order,
            )
            db.add(pref)
        await db.commit()

    @classmethod
    async def update_credential_notes(cls, db: AsyncSession, credential_id: int, notes: Optional[str]) -> Optional[str]:
        cred = await cls.get_credential(db, credential_id)
        if not cred:
            return None
        clean_notes = notes.strip() if notes and isinstance(notes, str) and notes.strip() else None
        cred.notes = clean_notes
        await db.commit()
        await db.refresh(cred)
        return cred.notes
