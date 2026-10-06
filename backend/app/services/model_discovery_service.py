import re
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.entities import DiscoveredModel, Provider, ProviderCredential
from app.schemas.entities import DiscoveredModelRead, DiscoveredModelUpdate, ModelRatingInfo
from app.core.crypto import decrypt_secret
from app.adapters.factory import get_adapter
from app.services.proxy_service import ProxyService
from app.services.credential_service import CredentialService
from app.services.model_ratings_service import ModelRatingsService
from app.services.model_limits_service import ModelLimitsService
from app.core.errors import RouterException

class ModelDiscoveryService:
    @classmethod
    def _validate_reasoning_effort(cls, val: Optional[str]) -> Optional[str]:
        if val is None:
            return None
        val = str(val).strip()
        if not val or val.lower() in ("default", "reset", "clear", "none_default"):
            return None
        if re.search(r"\d", val):
            raise ValueError("Reasoning effort cannot contain numbers, only words allowed")
        if not re.match(r"^[a-zA-Zа-яА-Я_-]+$", val):
            raise ValueError("Reasoning effort must contain only letters (a-z)")
        return val.lower()

    @staticmethod
    def compute_canonical_slug(provider_slug: str, provider_model_id: str) -> str:
        clean_model = provider_model_id.strip()
        if clean_model.startswith(f"{provider_slug}/"):
            return clean_model
        return f"{provider_slug}/{clean_model}"

    @classmethod
    async def fetch_models_for_credential(
        cls,
        db: AsyncSession,
        credential_id: int,
        new_models_out: Optional[List[str]] = None,
    ) -> List[DiscoveredModelRead]:
        result = await db.execute(
            select(ProviderCredential)
            .where(ProviderCredential.id == credential_id)
            .options(
                selectinload(ProviderCredential.provider),
                selectinload(ProviderCredential.proxy),
            )
        )
        cred = result.scalar_one_or_none()
        if not cred:
            raise ValueError(f"Credential {credential_id} not found")

        provider = cred.provider
        if not cred.enabled or not provider.enabled:
            raise ValueError("Credential or provider is disabled")
        api_key = decrypt_secret(cred.encrypted_api_key)
        proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
        adapter = get_adapter(provider.adapter_type)

        # Call adapter list_models
        discovered_data = await adapter.list_models(
            base_url=provider.base_url,
            api_key=api_key,
            extra_headers=provider.extra_headers,
            configuration=CredentialService.module_runtime_configuration(provider, cred),
            proxy_url=proxy_url,
        )

        now = datetime.now(timezone.utc)
        found_model_ids = {m.provider_model_id for m in discovered_data}

        # Query existing models for this provider (models belong to the provider)
        existing_result = await db.execute(
            select(DiscoveredModel).where(
                DiscoveredModel.provider_id == provider.id,
            )
        )
        existing_models = {m.provider_model_id: m for m in existing_result.scalars().all()}

        # Upsert models
        for item in discovered_data:
            canonical_slug = cls.compute_canonical_slug(provider.slug, item.provider_model_id)
            if item.provider_model_id in existing_models:
                # Update existing model without creating duplicate
                m = existing_models[item.provider_model_id]
                m.display_name = item.display_name
                m.capabilities = item.capabilities
                m.supported_endpoints = item.supported_endpoints
                if m.context_length is None and item.context_length is not None:
                    m.context_length = item.context_length
                m.max_output_tokens = item.max_output_tokens or m.max_output_tokens
                m.available = True
                m.discovered_at = now
            else:
                # Insert new model
                low_id = item.provider_model_id.lower()
                auto_type = "jev" if ("jev" in low_id or "typesafe" in low_id) and ("router" not in low_id) else "openai"
                new_model = DiscoveredModel(
                    provider_id=provider.id,
                    credential_id=credential_id,
                    provider_model_id=item.provider_model_id,
                    display_name=item.display_name,
                    canonical_slug=canonical_slug,
                    capabilities=item.capabilities,
                    supported_endpoints=item.supported_endpoints,
                    context_length=item.context_length,
                    max_output_tokens=item.max_output_tokens,
                    input_price_per_1m=0.0,
                    output_price_per_1m=0.0,
                    model_type=auto_type,
                    enabled=True,
                    available=True,
                    is_visible=True,
                    discovered_at=now,
                )
                db.add(new_model)
                existing_models[item.provider_model_id] = new_model
                if new_models_out is not None:
                    new_models_out.append(canonical_slug)

        # For models not in upstream response anymore, mark available = False
        for mid, m in existing_models.items():
            if mid not in found_model_ids:
                m.available = False

        await db.commit()
        return await cls.list_models(db, provider_id=provider.id, credential_id=credential_id)

    @classmethod
    async def fetch_all_models(cls, db: AsyncSession) -> dict:
        result = await db.execute(
            select(ProviderCredential).where(
                ProviderCredential.enabled == True,
                ProviderCredential.provider.has(Provider.enabled == True),
            )
        )
        creds = result.scalars().all()
        summary = {
            "total_credentials": len(creds),
            "success": 0,
            "failed": 0,
            "errors": {},
            "new_models_count": 0,
            "new_models": [],
        }
        new_models: List[str] = []
        for c in creds:
            try:
                await cls.fetch_models_for_credential(db, c.id, new_models_out=new_models)
                summary["success"] += 1
            except Exception as e:
                summary["failed"] += 1
                summary["errors"][c.name] = str(e)
        summary["new_models_count"] = len(new_models)
        summary["new_models"] = new_models
        return summary

    @classmethod
    async def fetch_models_for_provider(cls, db: AsyncSession, provider_id: int) -> dict:
        result = await db.execute(
            select(ProviderCredential).where(
                ProviderCredential.provider_id == provider_id,
                ProviderCredential.enabled == True,
            )
        )
        creds = result.scalars().all()
        if not creds:
            raise ValueError(f"No enabled credentials found for provider ID {provider_id}")

        summary = {
            "total_credentials": len(creds),
            "success": 0,
            "failed": 0,
            "errors": {},
            "new_models_count": 0,
            "new_models": [],
        }
        new_models: List[str] = []
        for c in creds:
            try:
                await cls.fetch_models_for_credential(db, c.id, new_models_out=new_models)
                summary["success"] += 1
            except Exception as e:
                summary["failed"] += 1
                summary["errors"][c.name] = str(e)
        summary["new_models_count"] = len(new_models)
        summary["new_models"] = new_models
        return summary

    @classmethod
    async def batch_update_models(
        cls,
        db: AsyncSession,
        model_ids: List[int],
        enabled: Optional[bool] = None,
        is_visible: Optional[bool] = None,
        context_length: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
        set_reasoning_effort: bool = False,
        temperature: Optional[float] = None,
        set_temperature: bool = False,
        model_type: Optional[str] = None,
        set_model_type: bool = False,
    ) -> int:
        if not model_ids:
            return 0
        values = {}
        if enabled is not None:
            values["enabled"] = enabled
        if is_visible is not None:
            values["is_visible"] = is_visible
        if context_length is not None:
            values["context_length"] = context_length if context_length > 0 else None
        if set_reasoning_effort:
            values["reasoning_effort"] = cls._validate_reasoning_effort(reasoning_effort)
        if set_temperature:
            values["temperature"] = temperature if (temperature is not None and 0.0 <= temperature <= 2.0) else None
        if set_model_type and model_type:
            values["model_type"] = model_type.lower().strip()
        if values:
            await db.execute(
                update(DiscoveredModel)
                .where(DiscoveredModel.id.in_(model_ids))
                .values(**values)
            )
            await db.commit()
            return len(model_ids)
        return 0

    @classmethod
    async def set_visible_only(cls, db: AsyncSession, model_ids: List[int]) -> int:
        from sqlalchemy import case
        if model_ids:
            await db.execute(
                update(DiscoveredModel).values(
                    is_visible=case((DiscoveredModel.id.in_(model_ids), True), else_=False)
                )
            )
        else:
            await db.execute(update(DiscoveredModel).values(is_visible=False))
        await db.commit()
        return len(model_ids)

    @classmethod
    async def set_all_visibility(
        cls, db: AsyncSession, is_visible: bool, provider_id: Optional[int] = None
    ) -> int:
        stmt = update(DiscoveredModel).values(is_visible=is_visible)
        if provider_id is not None:
            stmt = stmt.where(DiscoveredModel.provider_id == provider_id)
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount or 0

    @classmethod
    async def add_model_manually(
        cls,
        db: AsyncSession,
        provider_id: int,
        credential_id: Optional[int],
        provider_model_id: str,
        display_name: str,
        context_length: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
        model_type: Optional[str] = None,
    ) -> DiscoveredModelRead:
        p_res = await db.execute(select(Provider).where(Provider.id == provider_id))
        provider = p_res.scalar_one_or_none()
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")

        if credential_id is not None:
            credential = await db.get(ProviderCredential, credential_id)
            if credential is None or credential.provider_id != provider_id:
                raise ValueError("Credential does not belong to the selected provider")
        canonical_slug = cls.compute_canonical_slug(provider.slug, provider_model_id)
        now = datetime.now(timezone.utc)

        clean_mid = provider_model_id.lower()
        if model_type:
            resolved_type = model_type.lower().strip()
        elif ("jev" in clean_mid or "typesafe" in clean_mid) and ("router" not in clean_mid):
            resolved_type = "jev"
        else:
            resolved_type = "openai"

        endpoints = ["/chat/completions"]
        if resolved_type == "jev":
            endpoints.append("/v1/systemone")

        model = DiscoveredModel(
            provider_id=provider_id,
            credential_id=credential_id,
            provider_model_id=provider_model_id.strip(),
            display_name=display_name.strip() or provider_model_id.strip(),
            canonical_slug=canonical_slug,
            capabilities={
                "chat": True,
                "streaming": True,
                "tools": "unknown",
                "vision": "unknown",
                "audio_input": "unknown",
                "audio_output": "unknown",
                "embeddings": "unknown",
                "structured_output": "unknown",
                "reasoning": "unknown",
                "system_one": resolved_type == "jev",
            },
            supported_endpoints=endpoints,
            context_length=context_length,
            max_output_tokens=max_output_tokens,
            input_price_per_1m=0.0,
            output_price_per_1m=0.0,
            model_type=resolved_type,
            enabled=True,
            available=True,
            discovered_at=now,
        )
        db.add(model)
        await db.commit()
        await db.refresh(model)
        return await cls.get_model_read(db, model.id)

    @classmethod
    def _to_model_read(cls, m: DiscoveredModel) -> DiscoveredModelRead:
        rating_data = ModelRatingsService.find_rating(
            provider_model_id=m.provider_model_id,
            canonical_slug=m.canonical_slug,
            display_name=m.display_name,
        )
        rating = ModelRatingInfo(**rating_data) if rating_data else None
        limits = ModelLimitsService.compute_model_limits_fast(m, m.credential)

        return DiscoveredModelRead(
            id=m.id,
            provider_id=m.provider_id,
            provider_name=m.provider.name if m.provider else "",
            credential_id=m.credential_id,
            credential_name=m.credential.name if m.credential else None,
            provider_model_id=m.provider_model_id,
            display_name=m.display_name,
            canonical_slug=m.canonical_slug,
            capabilities=m.capabilities,
            supported_endpoints=m.supported_endpoints,
            context_length=m.context_length,
            max_output_tokens=m.max_output_tokens,
            input_price_per_1m=m.input_price_per_1m,
            output_price_per_1m=m.output_price_per_1m,
            enabled=m.enabled,
            available=m.available,
            is_visible=getattr(m, "is_visible", True),
            reasoning_effort=getattr(m, "reasoning_effort", None),
            temperature=getattr(m, "temperature", None),
            model_type=getattr(m, "model_type", "openai") or "openai",
            discovered_at=m.discovered_at,
            created_at=getattr(m, "created_at", None),
            rating=rating,
            limits=limits,
        )

    @classmethod
    async def list_models(
        cls,
        db: AsyncSession,
        provider_id: Optional[int] = None,
        credential_id: Optional[int] = None,
        only_enabled: bool = False,
    ) -> List[DiscoveredModelRead]:
        query = select(DiscoveredModel).options(
            selectinload(DiscoveredModel.provider),
            selectinload(DiscoveredModel.credential),
        )
        if provider_id is not None:
            query = query.where(DiscoveredModel.provider_id == provider_id)
        if credential_id is not None:
            query = query.where(DiscoveredModel.credential_id == credential_id)
        if only_enabled:
            query = query.where(DiscoveredModel.enabled == True, DiscoveredModel.available == True)

        query = query.order_by(DiscoveredModel.canonical_slug.asc())
        result = await db.execute(query)
        models = result.scalars().all()

        return [cls._to_model_read(m) for m in models]

    @classmethod
    async def get_model_read(cls, db: AsyncSession, model_id: int) -> Optional[DiscoveredModelRead]:
        result = await db.execute(
            select(DiscoveredModel)
            .where(DiscoveredModel.id == model_id)
            .options(
                selectinload(DiscoveredModel.provider),
                selectinload(DiscoveredModel.credential),
            )
        )
        m = result.scalar_one_or_none()
        if not m:
            return None
        return cls._to_model_read(m)

    @classmethod
    async def update_model(
        cls, db: AsyncSession, model_id: int, data: DiscoveredModelUpdate
    ) -> Optional[DiscoveredModelRead]:
        result = await db.execute(select(DiscoveredModel).where(DiscoveredModel.id == model_id))
        m = result.scalar_one_or_none()
        if not m:
            return None

        if data.enabled is not None:
            m.enabled = data.enabled
        if data.is_visible is not None:
            m.is_visible = data.is_visible
        if data.display_name is not None:
            m.display_name = data.display_name
        if "input_price_per_1m" in data.model_fields_set:
            m.input_price_per_1m = data.input_price_per_1m
        if "output_price_per_1m" in data.model_fields_set:
            m.output_price_per_1m = data.output_price_per_1m
        if "context_length" in data.model_fields_set:
            m.context_length = data.context_length if (data.context_length is not None and data.context_length > 0) else None
        if "reasoning_effort" in data.model_fields_set:
            m.reasoning_effort = cls._validate_reasoning_effort(data.reasoning_effort)
        if "temperature" in data.model_fields_set:
            m.temperature = data.temperature if (data.temperature is not None and 0.0 <= data.temperature <= 2.0) else None
        if "model_type" in data.model_fields_set and data.model_type is not None:
            m.model_type = data.model_type.lower().strip()

        await db.commit()
        return await cls.get_model_read(db, model_id)

    @classmethod
    async def delete_model(cls, db: AsyncSession, model_id: int) -> bool:
        result = await db.execute(select(DiscoveredModel).where(DiscoveredModel.id == model_id))
        m = result.scalar_one_or_none()
        if not m:
            return False
        await db.delete(m)
        await db.commit()
        return True
