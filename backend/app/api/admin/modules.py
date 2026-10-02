import json
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.modules.loader import ModuleLoader, LoadedModule
from app.models.entities import Provider, ProviderCredential, Proxy, DiscoveredModel
from app.core.crypto import encrypt_secret, decrypt_secret, compute_fingerprint, mask_secret
from app.services.credential_service import CredentialService
from app.services.model_discovery_service import ModelDiscoveryService
from app.core.circuit_breaker import CredentialStatus

router = APIRouter(prefix="/modules", tags=["Modules Management"], dependencies=[Depends(get_current_admin)])


class ModuleProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    proxy_id: Optional[int] = None
    priority: int = 1
    weight: int = 1
    fields: Dict[str, Any] = Field(default_factory=dict)


class ModuleProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    proxy_id: Optional[int] = None
    priority: Optional[int] = None
    weight: Optional[int] = None
    enabled: Optional[bool] = None
    fields: Optional[Dict[str, Any]] = None


@router.get("", response_model=List[Dict[str, Any]])
async def list_modules(db: AsyncSession = Depends(get_db)):
    """
    List all discovered custom modules in `backend/modules/`, their status,
    and the number of created profiles and discovered models.
    """
    # Ensure modules are scanned and DB providers synced
    if not ModuleLoader._modules:
        ModuleLoader.scan_modules()
    await ModuleLoader.sync_with_db(db)

    results = []
    for mod_id, loaded in ModuleLoader._modules.items():
        provider_slug = f"module_{loaded.manifest.id}"
        prov = (await db.execute(select(Provider).where(Provider.slug == provider_slug))).scalar_one_or_none()

        profiles_count = 0
        models_count = 0
        provider_id = None

        if prov:
            provider_id = prov.id
            profiles_count = (await db.scalar(
                select(func.count(ProviderCredential.id)).where(ProviderCredential.provider_id == prov.id)
            )) or 0
            models_count = (await db.scalar(
                select(func.count(DiscoveredModel.id)).where(DiscoveredModel.provider_id == prov.id)
            )) or 0

        mod_dict = loaded.model_dump()
        mod_dict["profiles_count"] = profiles_count
        mod_dict["models_count"] = models_count
        mod_dict["provider_id"] = provider_id
        results.append(mod_dict)

    return results


@router.post("/reload")
async def reload_modules(db: AsyncSession = Depends(get_db)):
    """
    Rescan the `backend/modules/` directory, reload Python handlers, and synchronize with the database.
    """
    result = await ModuleLoader.reload_and_sync(db)
    return result


@router.get("/{module_id}", response_model=Dict[str, Any])
async def get_module(module_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get detailed information about a single module.
    """
    loaded = ModuleLoader.get_module(module_id)
    if not loaded:
        raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found")

    provider_slug = f"module_{loaded.manifest.id}"
    prov = (await db.execute(select(Provider).where(Provider.slug == provider_slug))).scalar_one_or_none()

    mod_dict = loaded.model_dump()
    if prov:
        mod_dict["provider_id"] = prov.id
        mod_dict["profiles_count"] = (await db.scalar(
            select(func.count(ProviderCredential.id)).where(ProviderCredential.provider_id == prov.id)
        )) or 0
        mod_dict["models_count"] = (await db.scalar(
            select(func.count(DiscoveredModel.id)).where(DiscoveredModel.provider_id == prov.id)
        )) or 0
    return mod_dict


@router.get("/{module_id}/profiles", response_model=List[Dict[str, Any]])
async def list_module_profiles(module_id: str, db: AsyncSession = Depends(get_db)):
    """
    List all configured profiles (credentials) for a specific module.
    """
    loaded = ModuleLoader.get_module(module_id)
    if not loaded:
        raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found")

    provider_slug = f"module_{loaded.manifest.id}"
    prov = (await db.execute(select(Provider).where(Provider.slug == provider_slug))).scalar_one_or_none()
    if not prov:
        return []

    query = (
        select(ProviderCredential)
        .where(ProviderCredential.provider_id == prov.id)
        .options(selectinload(ProviderCredential.proxy))
        .order_by(ProviderCredential.id.desc())
    )
    result = await db.execute(query)
    credentials = result.scalars().all()

    output = []
    # Build safe masked view of fields
    for c in credentials:
        proxy_info = None
        if c.proxy:
            proxy_info = {
                "id": c.proxy.id,
                "name": c.proxy.name,
                "scheme": c.proxy.scheme,
                "host": c.proxy.host,
                "port": c.proxy.port,
                "country": c.proxy.country,
                "country_code": c.proxy.country_code,
            }

        # Decrypt custom fields to mask them for display
        raw_fields = {}
        if c.encrypted_api_key:
            try:
                decrypted = decrypt_secret(c.encrypted_api_key)
                if decrypted.startswith("{") and decrypted.endswith("}"):
                    raw_fields = json.loads(decrypted)
                elif decrypted != "no-key":
                    raw_fields["api_key"] = decrypted
            except Exception:
                pass

        # Mask password/secret fields based on manifest
        masked_fields = {}
        field_specs = {f.key: f for f in loaded.manifest.fields}
        for k, v in raw_fields.items():
            spec = field_specs.get(k)
            if spec and spec.type == "password":
                masked_fields[k] = mask_secret(str(v))
            else:
                masked_fields[k] = v

        output.append({
            "id": c.id,
            "provider_id": c.provider_id,
            "module_id": module_id,
            "name": c.name,
            "enabled": c.enabled,
            "status": c.status,
            "priority": c.priority,
            "weight": c.weight,
            "proxy_id": c.proxy_id,
            "proxy": proxy_info,
            "fields": masked_fields,
            "last_checked_at": c.last_checked_at.isoformat() if c.last_checked_at else None,
            "last_success_at": c.last_success_at.isoformat() if c.last_success_at else None,
            "last_error": c.last_error,
            "consecutive_failures": c.consecutive_failures,
        })

    return output


@router.post("/{module_id}/profiles", status_code=status.HTTP_201_CREATED)
async def create_module_profile(
    module_id: str,
    data: ModuleProfileCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new credential / profile for a custom module.
    """
    loaded = ModuleLoader.get_module(module_id)
    if not loaded:
        raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found")
    if loaded.status != "ready":
        raise HTTPException(status_code=400, detail=f"Module '{module_id}' is not in ready state: {loaded.error}")

    # Validate required fields
    for field_spec in loaded.manifest.fields:
        if field_spec.required and field_spec.key not in data.fields:
            raise HTTPException(
                status_code=422,
                detail=f"Field '{field_spec.label}' ({field_spec.key}) is required by module '{loaded.manifest.name}'",
            )

    provider_slug = f"module_{loaded.manifest.id}"
    prov = (await db.execute(select(Provider).where(Provider.slug == provider_slug))).scalar_one_or_none()
    if not prov:
        await ModuleLoader.sync_with_db(db)
        prov = (await db.execute(select(Provider).where(Provider.slug == provider_slug))).scalar_one_or_none()
        if not prov:
            raise HTTPException(status_code=500, detail=f"Failed to find or create Provider record for module '{module_id}'")

    # Check proxy if specified
    if data.proxy_id:
        proxy_obj = (await db.execute(select(Proxy).where(Proxy.id == data.proxy_id))).scalar_one_or_none()
        if not proxy_obj:
            raise HTTPException(status_code=404, detail=f"Proxy with ID {data.proxy_id} not found")

    # Serialize and encrypt all credential fields
    serialized_fields = json.dumps(data.fields)
    encrypted_key = encrypt_secret(serialized_fields)
    fingerprint = compute_fingerprint(f"{module_id}_{serialized_fields}_{uuid.uuid4().hex[:8]}")

    # Mask primary field for display
    masked = "(Module Profile)"
    if "api_key" in data.fields:
        masked = mask_secret(str(data.fields["api_key"]))
    elif "user_token" in data.fields:
        masked = mask_secret(str(data.fields["user_token"]))
    elif data.fields:
        first_val = list(data.fields.values())[0]
        masked = mask_secret(str(first_val))

    cred = ProviderCredential(
        provider_id=prov.id,
        name=data.name,
        encrypted_api_key=encrypted_key,
        key_fingerprint=fingerprint,
        masked_key=masked,
        enabled=True,
        proxy_id=data.proxy_id,
        status=CredentialStatus.HEALTHY,
        priority=data.priority,
        weight=data.weight,
        consecutive_failures=0,
        metadata_json=data.fields,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)

    return {
        "id": cred.id,
        "module_id": module_id,
        "name": cred.name,
        "enabled": cred.enabled,
        "status": cred.status,
        "proxy_id": cred.proxy_id,
        "priority": cred.priority,
        "weight": cred.weight,
    }


@router.put("/{module_id}/profiles/{profile_id}")
async def update_module_profile(
    module_id: str,
    profile_id: int,
    data: ModuleProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update an existing profile for a module.
    """
    cred = (await db.execute(
        select(ProviderCredential).where(ProviderCredential.id == profile_id)
    )).scalar_one_or_none()

    if not cred:
        raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

    if data.name is not None:
        cred.name = data.name
    if data.priority is not None:
        cred.priority = data.priority
    if data.weight is not None:
        cred.weight = data.weight
    if data.enabled is not None:
        cred.enabled = data.enabled
    if "proxy_id" in data.model_fields_set:
        cred.proxy_id = data.proxy_id

    # If new fields were submitted, merge and re-encrypt
    if data.fields is not None:
        current_fields = {}
        if cred.encrypted_api_key:
            try:
                decrypted = decrypt_secret(cred.encrypted_api_key)
                if decrypted.startswith("{") and decrypted.endswith("}"):
                    current_fields = json.loads(decrypted)
            except Exception:
                pass
        current_fields.update(data.fields)
        serialized_fields = json.dumps(current_fields)
        cred.encrypted_api_key = encrypt_secret(serialized_fields)
        cred.metadata_json = current_fields

    await db.commit()
    await db.refresh(cred)

    return {
        "id": cred.id,
        "module_id": module_id,
        "name": cred.name,
        "enabled": cred.enabled,
        "status": cred.status,
        "proxy_id": cred.proxy_id,
        "priority": cred.priority,
        "weight": cred.weight,
    }


@router.delete("/{module_id}/profiles/{profile_id}")
async def delete_module_profile(
    module_id: str,
    profile_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a module profile.
    """
    cred = (await db.execute(
        select(ProviderCredential).where(ProviderCredential.id == profile_id)
    )).scalar_one_or_none()

    if not cred:
        raise HTTPException(status_code=404, detail=f"Profile with ID {profile_id} not found")

    await db.delete(cred)
    await db.commit()
    return {"success": True, "message": f"Profile {profile_id} deleted"}


@router.post("/{module_id}/profiles/{profile_id}/test")
async def test_module_profile(
    module_id: str,
    profile_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute live credential and proxy validation test for this module profile.
    """
    result = await CredentialService.test_credential(db, profile_id)
    return result


@router.post("/{module_id}/profiles/{profile_id}/sync-models")
async def sync_module_models(
    module_id: str,
    profile_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch live models from this module profile and store them in the catalog.
    """
    result = await ModelDiscoveryService.fetch_models_from_provider(db, profile_id)
    return result
