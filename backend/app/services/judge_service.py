import time
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.entities import (
    JudgeProfile,
    JudgeCandidate,
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
)
from app.schemas.entities import (
    JudgeProfileCreate,
    JudgeProfileUpdate,
    JudgeProfileRead,
    JudgeCandidateRead,
    JudgeCandidateInput,
    JudgeTestResponse,
)

class JudgeService:
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
    async def _validate_candidate_ref(
        db: AsyncSession,
        cand: JudgeCandidateInput,
    ) -> None:
        if cand.candidate_type == "profile":
            if not cand.target_profile_id:
                raise ValueError("target_profile_id is required when candidate_type is 'profile'")
            rp = await db.get(RoutingProfile, cand.target_profile_id)
            if not rp:
                raise ValueError(f"Target routing profile {cand.target_profile_id} not found")
        else:
            if not cand.provider_id or not cand.model_id:
                raise ValueError("provider_id and model_id are required when candidate_type is 'model'")
            provider = await db.get(Provider, cand.provider_id)
            if not provider:
                raise ValueError(f"Provider {cand.provider_id} not found")
            model = await db.get(DiscoveredModel, cand.model_id)
            if not model or model.provider_id != cand.provider_id:
                raise ValueError(f"Model {cand.model_id} does not belong to provider {cand.provider_id}")
            if cand.credential_id:
                credential = await db.get(ProviderCredential, cand.credential_id)
                if not credential or credential.provider_id != cand.provider_id:
                    raise ValueError(f"Credential {cand.credential_id} does not belong to provider {cand.provider_id}")

    @classmethod
    async def list_profiles(cls, db: AsyncSession) -> List[JudgeProfileRead]:
        query = select(JudgeProfile).options(
            selectinload(JudgeProfile.judge_routing_profile),
            selectinload(JudgeProfile.judge_provider),
            selectinload(JudgeProfile.judge_credential),
            selectinload(JudgeProfile.judge_model),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.target_profile),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.provider),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.credential),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.model),
        ).order_by(JudgeProfile.id.asc())

        result = await db.execute(query)
        profiles = result.scalars().all()
        return [cls._build_read(p) for p in profiles]

    @classmethod
    async def get_profile(cls, db: AsyncSession, profile_id: int) -> Optional[JudgeProfileRead]:
        query = select(JudgeProfile).where(JudgeProfile.id == profile_id).options(
            selectinload(JudgeProfile.judge_routing_profile),
            selectinload(JudgeProfile.judge_provider),
            selectinload(JudgeProfile.judge_credential),
            selectinload(JudgeProfile.judge_model),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.target_profile),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.provider),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.credential),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.model),
        )
        result = await db.execute(query)
        profile = result.scalar_one_or_none()
        return cls._build_read(profile) if profile else None

    @classmethod
    async def get_profile_by_slug(cls, db: AsyncSession, slug: str) -> Optional[JudgeProfile]:
        clean_slug = slug.removeprefix("judge/").removeprefix("smart/").strip()
        query = select(JudgeProfile).where(JudgeProfile.slug == clean_slug).options(
            selectinload(JudgeProfile.judge_routing_profile),
            selectinload(JudgeProfile.judge_provider),
            selectinload(JudgeProfile.judge_credential).selectinload(ProviderCredential.proxy),
            selectinload(JudgeProfile.judge_model),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.target_profile),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.provider),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.credential).selectinload(ProviderCredential.proxy),
            selectinload(JudgeProfile.candidates).selectinload(JudgeCandidate.model),
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def create_profile(cls, db: AsyncSession, data: JudgeProfileCreate) -> JudgeProfileRead:
        clean_slug = data.slug.removeprefix("judge/").removeprefix("smart/").strip()
        # Verify unique slug
        existing = await db.execute(select(JudgeProfile).where(JudgeProfile.slug == clean_slug))
        if existing.scalar_one_or_none():
            raise ValueError(f"Judge profile slug '{clean_slug}' already exists")

        await cls._validate_judge_refs(
            db=db,
            judge_type=data.judge_type,
            judge_routing_profile_id=data.judge_routing_profile_id,
            judge_provider_id=data.judge_provider_id,
            judge_credential_id=data.judge_credential_id,
            judge_model_id=data.judge_model_id,
        )

        for cand in data.candidates:
            await cls._validate_candidate_ref(db, cand)

        profile = JudgeProfile(
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
            judge_thinking_effort=data.judge_thinking_effort if data.judge_type == "model" else None,
            judge_temperature=data.judge_temperature,
            system_prompt=data.system_prompt,
            fallback_candidate_id=data.fallback_candidate_id,
            fallback_strongest_on_overflow=data.fallback_strongest_on_overflow,
            context_length=data.context_length,
            timeout_seconds=data.timeout_seconds,
            enabled=data.enabled,
        )
        db.add(profile)
        await db.flush()

        for idx, cand in enumerate(data.candidates):
            candidate_obj = JudgeCandidate(
                profile_id=profile.id,
                candidate_type=cand.candidate_type,
                target_profile_id=cand.target_profile_id if cand.candidate_type == "profile" else None,
                provider_id=cand.provider_id if cand.candidate_type == "model" else None,
                credential_id=cand.credential_id if cand.candidate_type == "model" else None,
                credential_group=cand.credential_group if cand.candidate_type == "model" else None,
                model_id=cand.model_id if cand.candidate_type == "model" else None,
                thinking_effort=cand.thinking_effort if cand.candidate_type == "model" else None,
                temperature=cand.temperature,
                priority_order=cand.priority_order if cand.priority_order is not None else idx,
                label=cand.label or f"Candidate {chr(65 + idx)}",
                task_types=cand.task_types or [],
                complexity_level=cand.complexity_level or "all",
                description=cand.description,
                is_active=cand.is_active,
            )
            db.add(candidate_obj)

        await db.commit()
        return await cls.get_profile(db, profile.id)  # type: ignore

    @classmethod
    async def update_profile(
        cls, db: AsyncSession, profile_id: int, data: JudgeProfileUpdate
    ) -> Optional[JudgeProfileRead]:
        profile = await db.get(JudgeProfile, profile_id)
        if not profile:
            return None

        effective = lambda field: getattr(data, field) if field in data.model_fields_set else getattr(profile, field)
        await cls._validate_judge_refs(db, effective('judge_type'), effective('judge_routing_profile_id'),
                                      effective('judge_provider_id'), effective('judge_credential_id'), effective('judge_model_id'))
        if data.candidates is not None:
            for candidate in data.candidates:
                await cls._validate_candidate_ref(db, candidate)

        clean_slug = data.slug.removeprefix("judge/").removeprefix("smart/").strip() if data.slug else None
        if clean_slug and clean_slug != profile.slug:
            existing = await db.execute(
                select(JudgeProfile).where(JudgeProfile.slug == clean_slug, JudgeProfile.id != profile_id)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Judge profile slug '{clean_slug}' already exists")
            profile.slug = clean_slug

        if data.name is not None:
            profile.name = data.name
        if "description" in data.model_fields_set:
            profile.description = data.description
        if data.strategy is not None:
            profile.strategy = data.strategy
        if data.judge_type is not None:
            profile.judge_type = data.judge_type
        if "judge_routing_profile_id" in data.model_fields_set:
            profile.judge_routing_profile_id = data.judge_routing_profile_id
        if "judge_provider_id" in data.model_fields_set:
            profile.judge_provider_id = data.judge_provider_id
        if "judge_credential_id" in data.model_fields_set:
            profile.judge_credential_id = data.judge_credential_id
        if "judge_credential_group" in data.model_fields_set:
            profile.judge_credential_group = data.judge_credential_group
        if "judge_model_id" in data.model_fields_set:
            profile.judge_model_id = data.judge_model_id
        if "judge_thinking_effort" in data.model_fields_set:
            profile.judge_thinking_effort = data.judge_thinking_effort
        if "judge_temperature" in data.model_fields_set:
            profile.judge_temperature = data.judge_temperature
        if "system_prompt" in data.model_fields_set:
            profile.system_prompt = data.system_prompt
        if "fallback_candidate_id" in data.model_fields_set:
            profile.fallback_candidate_id = data.fallback_candidate_id
        if data.fallback_strongest_on_overflow is not None:
            profile.fallback_strongest_on_overflow = data.fallback_strongest_on_overflow
        if "context_length" in data.model_fields_set:
            profile.context_length = data.context_length
        if data.timeout_seconds is not None:
            profile.timeout_seconds = data.timeout_seconds
        if data.enabled is not None:
            profile.enabled = data.enabled

        eff_judge_type = profile.judge_type
        await cls._validate_judge_refs(
            db=db,
            judge_type=eff_judge_type,
            judge_routing_profile_id=profile.judge_routing_profile_id,
            judge_provider_id=profile.judge_provider_id,
            judge_credential_id=profile.judge_credential_id,
            judge_model_id=profile.judge_model_id,
        )

        if data.candidates is not None:
            for cand in data.candidates:
                await cls._validate_candidate_ref(db, cand)

            await db.execute(delete(JudgeCandidate).where(JudgeCandidate.profile_id == profile_id))
            for idx, cand in enumerate(data.candidates):
                candidate_obj = JudgeCandidate(
                    profile_id=profile.id,
                    candidate_type=cand.candidate_type,
                    target_profile_id=cand.target_profile_id if cand.candidate_type == "profile" else None,
                    provider_id=cand.provider_id if cand.candidate_type == "model" else None,
                    credential_id=cand.credential_id if cand.candidate_type == "model" else None,
                    credential_group=cand.credential_group if cand.candidate_type == "model" else None,
                    model_id=cand.model_id if cand.candidate_type == "model" else None,
                    thinking_effort=cand.thinking_effort if cand.candidate_type == "model" else None,
                    temperature=cand.temperature,
                    priority_order=cand.priority_order if cand.priority_order is not None else idx,
                    label=cand.label or f"Candidate {chr(65 + idx)}",
                    task_types=cand.task_types or [],
                    complexity_level=cand.complexity_level or "all",
                    description=cand.description,
                    is_active=cand.is_active,
                )
                db.add(candidate_obj)

        await db.commit()
        return await cls.get_profile(db, profile.id)

    @classmethod
    async def delete_profile(cls, db: AsyncSession, profile_id: int) -> bool:
        profile = await db.get(JudgeProfile, profile_id)
        if not profile:
            return False
        await db.delete(profile)
        await db.commit()
        return True

    @classmethod
    def _build_read(cls, p: JudgeProfile) -> JudgeProfileRead:
        candidates_read = []
        for c in sorted(p.candidates or [], key=lambda x: x.priority_order):
            target_profile_name = c.target_profile.name if c.target_profile else None
            target_profile_slug = c.target_profile.slug if c.target_profile else None
            provider_name = c.provider.name if c.provider else None
            credential_name = c.credential.name if c.credential else None
            model_name = c.model.display_name or c.model.provider_model_id if c.model else None
            canonical_slug = c.model.canonical_slug if c.model else None

            candidates_read.append(
                JudgeCandidateRead(
                    id=c.id,
                    candidate_type=c.candidate_type,
                    target_profile_id=c.target_profile_id,
                    target_profile_name=target_profile_name,
                    target_profile_slug=target_profile_slug,
                    provider_id=c.provider_id,
                    provider_name=provider_name,
                    credential_id=c.credential_id,
                    credential_name=credential_name,
                    credential_group=c.credential_group,
                    model_id=c.model_id,
                    model_name=model_name,
                    canonical_slug=canonical_slug,
                    thinking_effort=c.thinking_effort,
                    temperature=c.temperature,
                    priority_order=c.priority_order,
                    label=c.label,
                    task_types=c.task_types or [],
                    complexity_level=c.complexity_level or "all",
                    description=c.description,
                    is_active=c.is_active,
                )
            )

        j_rp_name = p.judge_routing_profile.name if p.judge_routing_profile else None
        j_rp_slug = p.judge_routing_profile.slug if p.judge_routing_profile else None
        j_prov_name = p.judge_provider.name if p.judge_provider else None
        j_cred_name = p.judge_credential.name if p.judge_credential else None
        j_mod_name = p.judge_model.display_name or p.judge_model.provider_model_id if p.judge_model else None
        j_canon_slug = p.judge_model.canonical_slug if p.judge_model else None
        j_model_type = getattr(p.judge_model, "model_type", "openai") if p.judge_model else None

        return JudgeProfileRead(
            id=p.id,
            name=p.name,
            slug=p.slug,
            description=p.description,
            strategy=p.strategy,
            judge_type=p.judge_type,
            judge_routing_profile_id=p.judge_routing_profile_id,
            judge_routing_profile_name=j_rp_name,
            judge_routing_profile_slug=j_rp_slug,
            judge_provider_id=p.judge_provider_id,
            judge_provider_name=j_prov_name,
            judge_credential_id=p.judge_credential_id,
            judge_credential_name=j_cred_name,
            judge_credential_group=p.judge_credential_group,
            judge_model_id=p.judge_model_id,
            judge_model_name=j_mod_name,
            judge_canonical_slug=j_canon_slug,
            judge_model_type=j_model_type,
            judge_thinking_effort=p.judge_thinking_effort,
            judge_temperature=p.judge_temperature,
            system_prompt=p.system_prompt,
            fallback_candidate_id=p.fallback_candidate_id,
            fallback_strongest_on_overflow=bool(p.fallback_strongest_on_overflow),
            context_length=p.context_length,
            timeout_seconds=p.timeout_seconds,
            enabled=p.enabled,
            candidates=candidates_read,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )

    @classmethod
    async def test_judge_evaluation(
        cls, db: AsyncSession, profile_id: int, prompt: str
    ) -> JudgeTestResponse:
        from app.judge.engine import JudgeEngine
        return await JudgeEngine.test_evaluation(db, profile_id, prompt)
