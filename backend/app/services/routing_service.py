from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.entities import RoutingProfile, RoutingCandidate, Provider, ProviderCredential, DiscoveredModel
from app.schemas.entities import (
    RoutingProfileCreate,
    RoutingProfileUpdate,
    RoutingProfileRead,
    RoutingCandidateRead,
)

class RoutingService:
    @classmethod
    async def list_profiles(cls, db: AsyncSession) -> List[RoutingProfileRead]:
        query = select(RoutingProfile).options(
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.target_profile),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.provider),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.credential),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.model),
        ).order_by(RoutingProfile.id.asc())

        result = await db.execute(query)
        profiles = result.scalars().all()
        return [cls._build_read(p) for p in profiles]

    @classmethod
    async def get_profile_by_slug(cls, db: AsyncSession, slug: str) -> Optional[RoutingProfile]:
        clean_slug = slug.removeprefix("route/").strip()
        query = select(RoutingProfile).where(RoutingProfile.slug == clean_slug).options(
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.target_profile),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.provider),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.credential).selectinload(ProviderCredential.proxy),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.model),
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def get_profile(cls, db: AsyncSession, profile_id: int) -> Optional[RoutingProfileRead]:
        query = select(RoutingProfile).where(RoutingProfile.id == profile_id).options(
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.target_profile),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.provider),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.credential),
            selectinload(RoutingProfile.candidates).selectinload(RoutingCandidate.model),
        )
        result = await db.execute(query)
        p = result.scalar_one_or_none()
        return cls._build_read(p) if p else None

    @classmethod
    async def create_profile(cls, db: AsyncSession, data: RoutingProfileCreate) -> RoutingProfileRead:
        clean_slug = data.slug.removeprefix("route/").strip()
        profile = RoutingProfile(
            name=data.name,
            slug=clean_slug,
            description=data.description,
            strategy=data.strategy,
            retry_count=data.retry_count,
            timeout_seconds=data.timeout_seconds,
            fallback_conditions=data.fallback_conditions,
            thinking_effort=data.thinking_effort,
            context_length=data.context_length if (data.context_length is not None and data.context_length > 0) else None,
            temperature=data.temperature,
            randomize_candidates=data.randomize_candidates,
            randomize_keys=data.randomize_keys,
            enabled=data.enabled,
        )
        db.add(profile)
        await db.flush()

        for idx, c in enumerate(data.candidates):
            cand_type = getattr(c, "candidate_type", "model") or "model"
            if c.target_profile_id is not None:
                cand_type = "profile"
            if cand_type == "profile":
                if c.target_profile_id == profile.id:
                    raise ValueError("A profile cannot contain itself as a fallback candidate.")
                cand = RoutingCandidate(
                    profile_id=profile.id,
                    candidate_type="profile",
                    target_profile_id=c.target_profile_id,
                    provider_id=None,
                    credential_id=None,
                    model_id=None,
                    thinking_effort=c.thinking_effort,
                    temperature=c.temperature,
                    priority_order=idx if c.priority_order == 0 else c.priority_order,
                    is_active=c.is_active,
                )
            else:
                raw_cg = getattr(c, "credential_group", None)
                eff_prov_id = c.provider_id
                if not eff_prov_id and c.model_id:
                    m_res = await db.execute(select(DiscoveredModel.provider_id).where(DiscoveredModel.id == c.model_id))
                    eff_prov_id = m_res.scalar_one_or_none()
                cand = RoutingCandidate(
                    profile_id=profile.id,
                    candidate_type="model",
                    target_profile_id=None,
                    provider_id=eff_prov_id,
                    credential_id=c.credential_id,
                    credential_group=(raw_cg.strip() if raw_cg and raw_cg.strip() else None),
                    model_id=c.model_id,
                    thinking_effort=c.thinking_effort,
                    temperature=c.temperature,
                    priority_order=idx if c.priority_order == 0 else c.priority_order,
                    is_active=c.is_active,
                )
            db.add(cand)

        await db.commit()
        return await cls.get_profile(db, profile.id)

    @classmethod
    async def update_profile(cls, db: AsyncSession, profile_id: int, data: RoutingProfileUpdate) -> Optional[RoutingProfileRead]:
        result = await db.execute(select(RoutingProfile).where(RoutingProfile.id == profile_id))
        p = result.scalar_one_or_none()
        if not p:
            return None

        if data.name is not None:
            p.name = data.name
        if data.slug is not None:
            p.slug = data.slug.removeprefix("route/").strip()
        if data.description is not None:
            p.description = data.description
        if data.strategy is not None:
            p.strategy = data.strategy
        if data.retry_count is not None:
            p.retry_count = data.retry_count
        if data.timeout_seconds is not None:
            p.timeout_seconds = data.timeout_seconds
        if data.fallback_conditions is not None:
            p.fallback_conditions = data.fallback_conditions
        if data.thinking_effort is not None:
            p.thinking_effort = data.thinking_effort
        if "context_length" in data.model_fields_set:
            p.context_length = data.context_length if (data.context_length is not None and data.context_length > 0) else None
        if "temperature" in data.model_fields_set:
            p.temperature = data.temperature
        if data.randomize_candidates is not None:
            p.randomize_candidates = data.randomize_candidates
        if data.randomize_keys is not None:
            p.randomize_keys = data.randomize_keys
        if data.enabled is not None:
            p.enabled = data.enabled

        if data.candidates is not None:
            # Replace candidates
            await db.execute(delete(RoutingCandidate).where(RoutingCandidate.profile_id == profile_id))
            for idx, c in enumerate(data.candidates):
                cand_type = getattr(c, "candidate_type", "model") or "model"
                if c.target_profile_id is not None:
                    cand_type = "profile"
                if cand_type == "profile":
                    if c.target_profile_id == profile_id:
                        raise ValueError("A profile cannot contain itself as a fallback candidate.")
                    cand = RoutingCandidate(
                        profile_id=profile_id,
                        candidate_type="profile",
                        target_profile_id=c.target_profile_id,
                        provider_id=None,
                        credential_id=None,
                        model_id=None,
                        thinking_effort=c.thinking_effort,
                        temperature=c.temperature,
                        priority_order=idx,
                        is_active=c.is_active,
                    )
                else:
                    raw_cg = getattr(c, "credential_group", None)
                    eff_prov_id = c.provider_id
                    if not eff_prov_id and c.model_id:
                        m_res = await db.execute(select(DiscoveredModel.provider_id).where(DiscoveredModel.id == c.model_id))
                        eff_prov_id = m_res.scalar_one_or_none()
                    cand = RoutingCandidate(
                        profile_id=profile_id,
                        candidate_type="model",
                        target_profile_id=None,
                        provider_id=eff_prov_id,
                        credential_id=c.credential_id,
                        credential_group=(raw_cg.strip() if raw_cg and raw_cg.strip() else None),
                        model_id=c.model_id,
                        thinking_effort=c.thinking_effort,
                        temperature=c.temperature,
                        priority_order=idx,
                        is_active=c.is_active,
                    )
                db.add(cand)

        await db.commit()
        return await cls.get_profile(db, profile_id)

    @classmethod
    async def delete_profile(cls, db: AsyncSession, profile_id: int) -> bool:
        result = await db.execute(select(RoutingProfile).where(RoutingProfile.id == profile_id))
        p = result.scalar_one_or_none()
        if not p:
            return False
        await db.delete(p)
        await db.commit()
        return True

    @staticmethod
    def _build_read(p: RoutingProfile) -> RoutingProfileRead:
        candidates_read = []
        for c in sorted(p.candidates, key=lambda x: x.priority_order):
            cand_type = getattr(c, "candidate_type", "model") or "model"
            if cand_type == "profile" or c.target_profile_id is not None:
                candidates_read.append(
                    RoutingCandidateRead(
                        id=c.id,
                        candidate_type="profile",
                        target_profile_id=c.target_profile_id,
                        target_profile_name=c.target_profile.name if c.target_profile else f"Profile #{c.target_profile_id}",
                        target_profile_slug=c.target_profile.slug if c.target_profile else f"profile-{c.target_profile_id}",
                        provider_id=None,
                        provider_name=None,
                        credential_id=None,
                        credential_name=None,
                        credential_group=None,
                        model_id=None,
                        model_name=None,
                        canonical_slug=f"route/{c.target_profile.slug}" if c.target_profile else f"route/profile-{c.target_profile_id}",
                        thinking_effort=c.thinking_effort,
                        temperature=getattr(c, "temperature", None),
                        priority_order=c.priority_order,
                        is_active=c.is_active,
                    )
                )
            else:
                credential_name = c.credential.name if c.credential else (
                    f"Group: {c.credential_group} (Fallback)" if c.credential_group else ("All keys (Fallback)" if c.credential_id is None else f"Key #{c.credential_id}")
                )
                candidates_read.append(
                    RoutingCandidateRead(
                        id=c.id,
                        candidate_type="model",
                        target_profile_id=None,
                        target_profile_name=None,
                        target_profile_slug=None,
                        provider_id=c.provider_id,
                        provider_name=c.provider.name if c.provider else "Unknown",
                        credential_id=c.credential_id,
                        credential_name=credential_name,
                        credential_group=c.credential_group,
                        model_id=c.model_id,
                        model_name=c.model.display_name if c.model else "Unknown",
                        canonical_slug=c.model.canonical_slug if c.model else "unknown",
                        thinking_effort=c.thinking_effort,
                        temperature=getattr(c, "temperature", None),
                        priority_order=c.priority_order,
                        is_active=c.is_active,
                    )
                )
        return RoutingProfileRead(
            id=p.id,
            name=p.name,
            slug=p.slug,
            description=p.description,
            strategy=p.strategy,
            retry_count=p.retry_count,
            timeout_seconds=p.timeout_seconds,
            fallback_conditions=p.fallback_conditions,
            thinking_effort=p.thinking_effort,
            context_length=p.context_length,
            temperature=getattr(p, "temperature", None),
            randomize_candidates=getattr(p, "randomize_candidates", False) or False,
            randomize_keys=getattr(p, "randomize_keys", False) or False,
            enabled=p.enabled,
            candidates=candidates_read,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
