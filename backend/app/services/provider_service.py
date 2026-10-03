from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.entities import Provider, ProviderCredential, DiscoveredModel
from app.schemas.entities import ProviderCreate, ProviderUpdate, ProviderRead
from app.adapters.factory import PROVIDER_PRESETS

class ProviderService:
    @classmethod
    async def seed_default_presets(cls, db: AsyncSession, force: bool = False):
        """Seed default provider presets only on initial setup if database has no providers, or if force=True."""
        if not force:
            count_res = await db.execute(select(func.count(Provider.id)))
            if (count_res.scalar() or 0) > 0:
                return

        existing_slugs_res = await db.execute(select(Provider.slug))
        existing_slugs = set(existing_slugs_res.scalars().all())
        added = False
        for p in PROVIDER_PRESETS:
            if p["slug"] not in existing_slugs:
                provider = Provider(
                    name=p["name"],
                    slug=p["slug"],
                    adapter_type=p["adapter_type"],
                    base_url=p["base_url"],
                    models_endpoint=p["models_endpoint"],
                    chat_endpoint=p["chat_endpoint"],
                    responses_endpoint=p.get("responses_endpoint"),
                    enabled=True,
                    auth_type=p["auth_type"],
                    auth_header=p["auth_header"],
                    extra_headers=p.get("extra_headers", {}),
                    configuration=p.get("configuration", {}),
                )
                db.add(provider)
                added = True
        if added:
            await db.commit()

    @classmethod
    async def list_providers(cls, db: AsyncSession) -> List[ProviderRead]:
        result = await db.execute(
            select(Provider).options(
                selectinload(Provider.credentials),
                selectinload(Provider.models),
            ).order_by(Provider.id.asc())
        )
        providers = result.scalars().all()
        return [
            ProviderRead(
                id=p.id,
                name=p.name,
                slug=p.slug,
                adapter_type=p.adapter_type,
                base_url=p.base_url,
                models_endpoint=p.models_endpoint,
                chat_endpoint=p.chat_endpoint,
                responses_endpoint=p.responses_endpoint,
                enabled=p.enabled,
                auth_type=p.auth_type,
                auth_header=p.auth_header,
                extra_headers=p.extra_headers,
                configuration=p.configuration,
                notes=p.notes,
                credentials_count=len(p.credentials),
                models_count=len(p.models),
                healthy_credentials_count=sum(1 for c in p.credentials if c.status == "HEALTHY" and c.enabled),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in providers
        ]

    @classmethod
    async def get_provider(cls, db: AsyncSession, provider_id: int) -> Optional[ProviderRead]:
        result = await db.execute(
            select(Provider).where(Provider.id == provider_id).options(
                selectinload(Provider.credentials),
                selectinload(Provider.models),
            )
        )
        p = result.scalar_one_or_none()
        if not p:
            return None
        return ProviderRead(
            id=p.id,
            name=p.name,
            slug=p.slug,
            adapter_type=p.adapter_type,
            base_url=p.base_url,
            models_endpoint=p.models_endpoint,
            chat_endpoint=p.chat_endpoint,
            responses_endpoint=p.responses_endpoint,
            enabled=p.enabled,
            auth_type=p.auth_type,
            auth_header=p.auth_header,
            extra_headers=p.extra_headers,
            configuration=p.configuration,
            notes=p.notes,
            credentials_count=len(p.credentials),
            models_count=len(p.models),
            healthy_credentials_count=sum(1 for c in p.credentials if c.status == "HEALTHY" and c.enabled),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )

    @classmethod
    async def create_provider(cls, db: AsyncSession, data: ProviderCreate) -> ProviderRead:
        provider = Provider(
            name=data.name,
            slug=data.slug,
            adapter_type=data.adapter_type,
            base_url=data.base_url,
            models_endpoint=data.models_endpoint,
            chat_endpoint=data.chat_endpoint,
            responses_endpoint=data.responses_endpoint,
            enabled=data.enabled,
            auth_type=data.auth_type,
            auth_header=data.auth_header,
            extra_headers=data.extra_headers,
            configuration=data.configuration,
            notes=data.notes.strip() if data.notes else None,
        )
        db.add(provider)
        await db.commit()
        await db.refresh(provider)

        if provider.auth_type == "none":
            from app.services.credential_service import CredentialService
            from app.schemas.entities import CredentialCreate
            from app.services.model_discovery_service import ModelDiscoveryService
            try:
                cred = await CredentialService.create_credential(
                    db,
                    CredentialCreate(
                        provider_id=provider.id,
                        name=f"{provider.name} (Keyless)",
                        api_key="no-key",
                        enabled=True,
                    ),
                )
                await ModelDiscoveryService.fetch_models_for_credential(db, cred.id)
            except Exception:
                pass

        return ProviderRead(
            id=provider.id,
            name=provider.name,
            slug=provider.slug,
            adapter_type=provider.adapter_type,
            base_url=provider.base_url,
            models_endpoint=provider.models_endpoint,
            chat_endpoint=provider.chat_endpoint,
            responses_endpoint=provider.responses_endpoint,
            enabled=provider.enabled,
            auth_type=provider.auth_type,
            auth_header=provider.auth_header,
            extra_headers=provider.extra_headers,
            configuration=provider.configuration,
            notes=provider.notes,
            credentials_count=0,
            models_count=0,
            healthy_credentials_count=0,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )

    @classmethod
    async def update_provider(cls, db: AsyncSession, provider_id: int, data: ProviderUpdate) -> Optional[ProviderRead]:
        result = await db.execute(select(Provider).where(Provider.id == provider_id))
        provider = result.scalar_one_or_none()
        if not provider:
            return None

        if data.name is not None:
            provider.name = data.name
        if data.adapter_type is not None:
            provider.adapter_type = data.adapter_type
        if data.base_url is not None:
            provider.base_url = data.base_url
        if data.models_endpoint is not None:
            provider.models_endpoint = data.models_endpoint
        if data.chat_endpoint is not None:
            provider.chat_endpoint = data.chat_endpoint
        if data.responses_endpoint is not None:
            provider.responses_endpoint = data.responses_endpoint
        if data.enabled is not None:
            provider.enabled = data.enabled
        if data.auth_type is not None:
            provider.auth_type = data.auth_type
        if data.auth_header is not None:
            provider.auth_header = data.auth_header
        if data.extra_headers is not None:
            provider.extra_headers = data.extra_headers
        if data.configuration is not None:
            provider.configuration = data.configuration
        if data.notes is not None:
            provider.notes = data.notes.strip() if data.notes else None

        await db.commit()
        return await cls.get_provider(db, provider_id)

    @classmethod
    async def update_provider_notes(cls, db: AsyncSession, provider_id: int, notes: Optional[str]) -> Optional[str]:
        result = await db.execute(select(Provider).where(Provider.id == provider_id))
        provider = result.scalar_one_or_none()
        if not provider:
            return None
        provider.notes = notes.strip() if notes else None
        await db.commit()
        await db.refresh(provider)
        return provider.notes

    @classmethod
    async def delete_provider(cls, db: AsyncSession, provider_id: int) -> bool:
        result = await db.execute(select(Provider).where(Provider.id == provider_id))
        provider = result.scalar_one_or_none()
        if not provider:
            return False
        await db.delete(provider)
        await db.commit()
        return True
