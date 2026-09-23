from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.entities import (
    FusionProfile,
    FusionParticipant,
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
)
from app.schemas.entities import (
    FusionProfileCreate,
    FusionProfileUpdate,
    FusionProfileRead,
    FusionParticipantRead,
    FusionParticipantInput,
)

class FusionService:
    @staticmethod
    async def _validate_judge_refs(
        db: AsyncSession,
        judge_type: str,
        judge_routing_profile_id: Optional[int],
        judge_provider_id: Optional[int],
        judge_credential_id: Optional[int],
        judge_model_id: Optional[int],
    ) -> None:
        if judge_type == "profile":
            if not judge_routing_profile_id:
                raise ValueError("judge_routing_profile_id is required when judge_type is 'profile'")
            rp = await db.get(RoutingProfile, judge_routing_profile_id)
            if not rp:
                raise ValueError(f"Routing profile {judge_routing_profile_id} not found")
        else:
            if not judge_provider_id or not judge_model_id:
                raise ValueError("judge_provider_id and judge_model_id are required when judge_type is 'model'")
            provider = await db.get(Provider, judge_provider_id)
            if not provider:
                raise ValueError(f"Judge provider {judge_provider_id} not found")
            model = await db.get(DiscoveredModel, judge_model_id)
            if not model or model.provider_id != judge_provider_id:
                raise ValueError(f"Judge model {judge_model_id} does not belong to provider {judge_provider_id}")
            if judge_credential_id:
                credential = await db.get(ProviderCredential, judge_credential_id)
                if not credential or credential.provider_id != judge_provider_id:
                    raise ValueError(f"Judge credential {judge_credential_id} does not belong to provider {judge_provider_id}")

    @staticmethod
    async def _validate_participant_ref(
        db: AsyncSession,
        part: FusionParticipantInput,
    ) -> None:
        if part.participant_type == "profile":
            if not part.target_profile_id:
                raise ValueError("target_profile_id is required when participant_type is 'profile'")
            rp = await db.get(RoutingProfile, part.target_profile_id)
            if not rp:
                raise ValueError(f"Target routing profile {part.target_profile_id} not found")
        else:
            if not part.provider_id or not part.model_id:
                raise ValueError("provider_id and model_id are required when participant_type is 'model'")
            provider = await db.get(Provider, part.provider_id)
            if not provider:
                raise ValueError(f"Provider {part.provider_id} not found")
            model = await db.get(DiscoveredModel, part.model_id)
            if not model or model.provider_id != part.provider_id:
                raise ValueError(f"Model {part.model_id} does not belong to provider {part.provider_id}")
            if part.credential_id:
                credential = await db.get(ProviderCredential, part.credential_id)
                if not credential or credential.provider_id != part.provider_id:
                    raise ValueError(f"Credential {part.credential_id} does not belong to provider {part.provider_id}")

    @classmethod
    async def list_profiles(cls, db: AsyncSession) -> List[FusionProfileRead]:
        query = select(FusionProfile).options(
            selectinload(FusionProfile.judge_routing_profile),
            selectinload(FusionProfile.judge_provider),
            selectinload(FusionProfile.judge_credential),
            selectinload(FusionProfile.judge_model),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.target_profile),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.provider),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.credential),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.model),
        ).order_by(FusionProfile.id.asc())

        result = await db.execute(query)
        profiles = result.scalars().all()
        return [cls._build_read(p) for p in profiles]

    @classmethod
    async def get_profile_by_slug(cls, db: AsyncSession, slug: str) -> Optional[FusionProfile]:
        clean_slug = slug.removeprefix("fusion/").strip()
        query = select(FusionProfile).where(FusionProfile.slug == clean_slug).options(
            selectinload(FusionProfile.judge_routing_profile),
            selectinload(FusionProfile.judge_provider),
            selectinload(FusionProfile.judge_credential).selectinload(ProviderCredential.proxy),
            selectinload(FusionProfile.judge_model),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.target_profile),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.provider),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.credential).selectinload(ProviderCredential.proxy),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.model),
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def get_profile(cls, db: AsyncSession, profile_id: int) -> Optional[FusionProfileRead]:
        query = select(FusionProfile).where(FusionProfile.id == profile_id).options(
            selectinload(FusionProfile.judge_routing_profile),
            selectinload(FusionProfile.judge_provider),
            selectinload(FusionProfile.judge_credential),
            selectinload(FusionProfile.judge_model),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.target_profile),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.provider),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.credential),
            selectinload(FusionProfile.participants).selectinload(FusionParticipant.model),
        )
        result = await db.execute(query)
        p = result.scalar_one_or_none()
        return cls._build_read(p) if p else None

    @classmethod
    async def create_profile(cls, db: AsyncSession, data: FusionProfileCreate) -> FusionProfileRead:
        clean_slug = data.slug.removeprefix("fusion/").strip()
        existing = await db.execute(select(FusionProfile.id).where(FusionProfile.slug == clean_slug))
        if existing.scalar_one_or_none():
            raise ValueError(f"Fusion profile with slug '{clean_slug}' already exists")

        await cls._validate_judge_refs(
            db,
            judge_type=data.judge_type,
            judge_routing_profile_id=data.judge_routing_profile_id,
            judge_provider_id=data.judge_provider_id,
            judge_credential_id=data.judge_credential_id,
            judge_model_id=data.judge_model_id,
        )
        for participant in data.participants:
            await cls._validate_participant_ref(db, participant)

        profile = FusionProfile(
            name=data.name,
            slug=clean_slug,
            description=data.description,
            strategy=data.strategy,
            judge_type=data.judge_type,
            judge_routing_profile_id=data.judge_routing_profile_id if data.judge_type == "profile" else None,
            judge_provider_id=data.judge_provider_id if data.judge_type == "model" else None,
            judge_credential_id=data.judge_credential_id if data.judge_type == "model" else None,
            judge_credential_group=data.judge_credential_group if data.judge_type == "model" else None,
            judge_model_id=data.judge_model_id if data.judge_type == "model" else None,
            judge_thinking_effort=data.judge_thinking_effort,
            judge_temperature=data.judge_temperature,
            temperature=data.temperature,
            system_prompt=data.system_prompt,
            min_successful_candidates=data.min_successful_candidates,
            max_parallelism=data.max_parallelism,
            timeout_seconds=data.timeout_seconds,
            enabled=data.enabled,
        )
        db.add(profile)
        await db.flush()

        for idx, part in enumerate(data.participants):
            p_obj = FusionParticipant(
                profile_id=profile.id,
                participant_type=part.participant_type,
                target_profile_id=part.target_profile_id if part.participant_type == "profile" else None,
                provider_id=part.provider_id if part.participant_type == "model" else None,
                credential_id=part.credential_id if part.participant_type == "model" else None,
                credential_group=part.credential_group if part.participant_type == "model" else None,
                model_id=part.model_id if part.participant_type == "model" else None,
                thinking_effort=part.thinking_effort,
                temperature=part.temperature,
                priority_order=idx if part.priority_order == 0 else part.priority_order,
                label=part.label or f"Candidate {chr(65 + idx)}",
                is_active=part.is_active,
            )
            db.add(p_obj)

        await db.commit()
        return await cls.get_profile(db, profile.id)

    @classmethod
    async def update_profile(cls, db: AsyncSession, profile_id: int, data: FusionProfileUpdate) -> Optional[FusionProfileRead]:
        result = await db.execute(select(FusionProfile).where(FusionProfile.id == profile_id))
        p = result.scalar_one_or_none()
        if not p:
            return None

        judge_type = data.judge_type if data.judge_type is not None else p.judge_type
        judge_routing_profile_id = (
            data.judge_routing_profile_id
            if "judge_routing_profile_id" in data.model_fields_set
            else p.judge_routing_profile_id
        )
        judge_provider_id = (
            data.judge_provider_id
            if "judge_provider_id" in data.model_fields_set
            else p.judge_provider_id
        )
        judge_credential_id = (
            data.judge_credential_id
            if "judge_credential_id" in data.model_fields_set
            else p.judge_credential_id
        )
        judge_model_id = (
            data.judge_model_id
            if "judge_model_id" in data.model_fields_set
            else p.judge_model_id
        )

        await cls._validate_judge_refs(
            db,
            judge_type=judge_type,
            judge_routing_profile_id=judge_routing_profile_id,
            judge_provider_id=judge_provider_id,
            judge_credential_id=judge_credential_id,
            judge_model_id=judge_model_id,
        )

        if data.participants is not None:
            for participant in data.participants:
                await cls._validate_participant_ref(db, participant)

        if data.name is not None:
            p.name = data.name
        if data.slug is not None:
            p.slug = data.slug.removeprefix("fusion/").strip()
        if data.description is not None:
            p.description = data.description
        if data.strategy is not None:
            p.strategy = data.strategy
        if data.judge_type is not None:
            p.judge_type = data.judge_type
        if "judge_routing_profile_id" in data.model_fields_set:
            p.judge_routing_profile_id = data.judge_routing_profile_id
        if "judge_provider_id" in data.model_fields_set:
            p.judge_provider_id = data.judge_provider_id
        if "judge_credential_id" in data.model_fields_set:
            p.judge_credential_id = data.judge_credential_id
        if "judge_credential_group" in data.model_fields_set:
            p.judge_credential_group = data.judge_credential_group
        if "judge_model_id" in data.model_fields_set:
            p.judge_model_id = data.judge_model_id
        if "judge_thinking_effort" in data.model_fields_set:
            p.judge_thinking_effort = data.judge_thinking_effort
        if "judge_temperature" in data.model_fields_set:
            p.judge_temperature = data.judge_temperature
        if "temperature" in data.model_fields_set:
            p.temperature = data.temperature
        if data.system_prompt is not None:
            p.system_prompt = data.system_prompt
        if data.min_successful_candidates is not None:
            p.min_successful_candidates = data.min_successful_candidates
        if data.max_parallelism is not None:
            p.max_parallelism = data.max_parallelism
        if data.timeout_seconds is not None:
            p.timeout_seconds = data.timeout_seconds
        if data.enabled is not None:
            p.enabled = data.enabled

        if data.participants is not None:
            await db.execute(delete(FusionParticipant).where(FusionParticipant.profile_id == profile_id))
            for idx, part in enumerate(data.participants):
                p_obj = FusionParticipant(
                    profile_id=profile_id,
                    participant_type=part.participant_type,
                    target_profile_id=part.target_profile_id if part.participant_type == "profile" else None,
                    provider_id=part.provider_id if part.participant_type == "model" else None,
                    credential_id=part.credential_id if part.participant_type == "model" else None,
                    credential_group=part.credential_group if part.participant_type == "model" else None,
                    model_id=part.model_id if part.participant_type == "model" else None,
                    thinking_effort=part.thinking_effort,
                    temperature=part.temperature,
                    priority_order=idx if part.priority_order == 0 else part.priority_order,
                    label=part.label or f"Candidate {chr(65 + idx)}",
                    is_active=part.is_active,
                )
                db.add(p_obj)

        await db.commit()
        return await cls.get_profile(db, profile_id)

    @classmethod
    async def delete_profile(cls, db: AsyncSession, profile_id: int) -> bool:
        result = await db.execute(select(FusionProfile).where(FusionProfile.id == profile_id))
        p = result.scalar_one_or_none()
        if not p:
            return False
        await db.delete(p)
        await db.commit()
        return True

    @staticmethod
    def _build_read(p: FusionProfile) -> FusionProfileRead:
        participants_read = []
        for part in sorted(p.participants, key=lambda x: getattr(x, "priority_order", 0)):
            is_profile = (part.participant_type == "profile") or (part.target_profile_id is not None)
            if is_profile and part.target_profile:
                p_read = FusionParticipantRead(
                    id=part.id,
                    participant_type="profile",
                    target_profile_id=part.target_profile_id,
                    target_profile_name=part.target_profile.name,
                    target_profile_slug=part.target_profile.slug,
                    provider_id=None,
                    provider_name="Fallback Route",
                    credential_id=None,
                    credential_name="Route Fallback Chain",
                    credential_group=None,
                    model_id=None,
                    model_name=part.target_profile.name,
                    canonical_slug=f"route/{part.target_profile.slug}",
                    thinking_effort=getattr(part, "thinking_effort", None),
                    temperature=getattr(part, "temperature", None),
                    priority_order=getattr(part, "priority_order", 0),
                    label=part.label,
                    is_active=part.is_active,
                )
            else:
                cred_name = part.credential.name if part.credential else "All keys (Auto)"
                if part.credential_group:
                    cred_name = f"{cred_name} [{part.credential_group}]"
                p_read = FusionParticipantRead(
                    id=part.id,
                    participant_type="model",
                    target_profile_id=None,
                    target_profile_name=None,
                    target_profile_slug=None,
                    provider_id=part.provider_id,
                    provider_name=part.provider.name if part.provider else "Unknown",
                    credential_id=part.credential_id,
                    credential_name=cred_name,
                    credential_group=part.credential_group,
                    model_id=part.model_id,
                    model_name=part.model.display_name if part.model else "Unknown",
                    canonical_slug=part.model.canonical_slug if part.model else "unknown",
                    thinking_effort=getattr(part, "thinking_effort", None),
                    temperature=getattr(part, "temperature", None),
                    priority_order=getattr(part, "priority_order", 0),
                    label=part.label,
                    is_active=part.is_active,
                )
            participants_read.append(p_read)

        judge_is_profile = (p.judge_type == "profile") or (p.judge_routing_profile_id is not None)
        if judge_is_profile and p.judge_routing_profile:
            judge_prov_name = "Fallback Route"
            judge_m_name = p.judge_routing_profile.name
            judge_c_name = "Route Fallback Chain"
        else:
            judge_prov_name = p.judge_provider.name if p.judge_provider else "Unknown"
            judge_m_name = p.judge_model.display_name if p.judge_model else "Unknown"
            judge_c_name = p.judge_credential.name if p.judge_credential else (
                f"Group: {p.judge_credential_group}" if getattr(p, "judge_credential_group", None) else "Auto"
            )

        return FusionProfileRead(
            id=p.id,
            name=p.name,
            slug=p.slug,
            description=p.description,
            strategy=p.strategy,
            judge_type="profile" if judge_is_profile else "model",
            judge_routing_profile_id=p.judge_routing_profile_id,
            judge_routing_profile_name=p.judge_routing_profile.name if p.judge_routing_profile else None,
            judge_routing_profile_slug=p.judge_routing_profile.slug if p.judge_routing_profile else None,
            judge_provider_id=p.judge_provider_id,
            judge_provider_name=judge_prov_name,
            judge_credential_id=p.judge_credential_id,
            judge_credential_name=judge_c_name,
            judge_credential_group=getattr(p, "judge_credential_group", None),
            judge_model_id=p.judge_model_id,
            judge_model_name=judge_m_name,
            judge_thinking_effort=getattr(p, "judge_thinking_effort", None),
            judge_temperature=getattr(p, "judge_temperature", None),
            temperature=getattr(p, "temperature", None),
            system_prompt=p.system_prompt,
            min_successful_candidates=p.min_successful_candidates,
            max_parallelism=p.max_parallelism,
            timeout_seconds=p.timeout_seconds,
            enabled=p.enabled,
            participants=participants_read,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
