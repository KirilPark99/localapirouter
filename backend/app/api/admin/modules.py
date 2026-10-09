import json
import uuid
from typing import Annotated, Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
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
from app.core.circuit_breaker import CredentialStatus, circuit_breaker
from app.services import module_oauth
from app.services.proxy_service import ProxyService
from app.schemas.entities import CredentialUpdate, CredentialQuotaRules
from app.services.api_key_service import ApiKeyService

router = APIRouter(prefix="/modules", tags=["Modules Management"], dependencies=[Depends(get_current_admin)])


class ModuleProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    group_name: Optional[str] = None
    rpm_limit: Optional[int] = Field(None, ge=1)
    tpm_limit: Optional[int] = Field(None, ge=1)
    max_concurrency: Optional[int] = Field(None, ge=1)
    quota_rules: CredentialQuotaRules = Field(default_factory=list)
    proxy_id: Optional[int] = Field(None, ge=1)
    priority: int = 1
    weight: int = 1
    fields: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class ModuleProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    group_name: Optional[str] = None
    rpm_limit: Optional[int] = Field(None, ge=1)
    tpm_limit: Optional[int] = Field(None, ge=1)
    max_concurrency: Optional[int] = Field(None, ge=1)
    quota_rules: Optional[CredentialQuotaRules] = None
    proxy_id: Optional[int] = Field(None, ge=1)
    priority: Optional[int] = None
    weight: Optional[int] = None
    enabled: Optional[bool] = None
    fields: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


@router.get("", response_model=List[Dict[str, Any]])
async def list_modules(db: AsyncSession = Depends(get_db)):
    """
    List all discovered custom modules in `backend/modules/`, their status,
    and the number of created profiles and discovered models.
    """
    # Reading the list must not import files or overwrite saved profiles.
    if not ModuleLoader._modules:
        ModuleLoader.scan_modules()

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
        mod_dict["notes"] = prov.notes if prov else None
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
        mod_dict["notes"] = prov.notes
        mod_dict["profiles_count"] = (await db.scalar(
            select(func.count(ProviderCredential.id)).where(ProviderCredential.provider_id == prov.id)
        )) or 0
        mod_dict["models_count"] = (await db.scalar(
            select(func.count(DiscoveredModel.id)).where(DiscoveredModel.provider_id == prov.id)
        )) or 0
    else:
        mod_dict["notes"] = None
    return mod_dict


class ModuleNotesUpdate(BaseModel):
    notes: Optional[str] = None


@router.put("/{module_id}/notes")
async def update_module_notes(
    module_id: str,
    data: ModuleNotesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update plain text notes for a module.
    """
    loaded = ModuleLoader.get_module(module_id)
    if not loaded:
        raise HTTPException(status_code=404, detail=f"Module '{module_id}' not found")

    provider_slug = f"module_{loaded.manifest.id}"
    prov = (await db.execute(select(Provider).where(Provider.slug == provider_slug))).scalar_one_or_none()
    if not prov:
        await ModuleLoader.sync_with_db(db)
        prov = (await db.execute(select(Provider).where(Provider.slug == provider_slug))).scalar_one_or_none()

    if not prov:
        raise HTTPException(status_code=404, detail=f"Provider record for module '{module_id}' not found")

    clean_notes = data.notes.strip() if data.notes and data.notes.strip() else None
    prov.notes = clean_notes
    await db.commit()
    await db.refresh(prov)
    return {"module_id": module_id, "notes": prov.notes}


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
            if (spec and spec.type == "password") or k in ("auth_json", "access_token", "refresh_token", "id_token", "key", "api_key", "apiKey", "user_token", "cookie", "cookies", "storage_state", "token_v2"):
                masked_fields[k] = mask_secret(str(v))
            else:
                masked_fields[k] = v

        meta = c.metadata_json if isinstance(c.metadata_json, dict) else {}
        source = meta.get("_source", "ui")
        file_path = meta.get("_file_path")

        output.append({
            "id": c.id,
            "provider_id": c.provider_id,
            "module_id": module_id,
            "name": c.name,
            "enabled": c.enabled,
            "status": c.status,
            "priority": c.priority,
            "weight": c.weight,
            "group_name": c.group_name,
            "rpm_limit": c.rpm_limit,
            "tpm_limit": c.tpm_limit,
            "max_concurrency": c.max_concurrency,
            "quota_rules": c.quota_rules or [],
            "proxy_id": c.proxy_id,
            "proxy": proxy_info,
            "fields": masked_fields,
            "source": source,
            "file_path": file_path,
            "last_checked_at": c.last_checked_at.isoformat() if c.last_checked_at else None,
            "last_success_at": c.last_success_at.isoformat() if c.last_success_at else None,
            "last_error": c.last_error,
            "consecutive_failures": c.consecutive_failures,
            "notes": c.notes,
        })

    return output


async def _validate_lingling_pool(db: AsyncSession, module_id: str, fields: dict, proxy_id: Optional[int]):
    if module_id != "lingling":
        return
    try:
        mode, policy = fields.get("transport_mode", "tor"), fields.get("proxy_policy", "balance")
        if mode not in ("tor", "proxy", "mixed") or policy not in ("balance", "priority"):
            raise ValueError("Invalid Lingling transport or pool policy")
        ids = ProxyService.validate_proxy_ids(fields.get("proxy_ids", []))
        if mode == "tor" and proxy_id is not None:
            raise ValueError("Select Proxy or Mixed transport to use a profile proxy")
        if mode != "tor":
            selected = list(dict.fromkeys(ids + ([proxy_id] if proxy_id is not None else [])))
            if not selected:
                raise ValueError("Select at least one proxy for Proxy or Mixed transport")
            await ProxyService.resolve_proxy_pool(db, selected)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


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

    await _validate_lingling_pool(db, module_id, data.fields, data.proxy_id)

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
        group_name=data.group_name.strip() if data.group_name and data.group_name.strip() else None,
        rpm_limit=data.rpm_limit,
        tpm_limit=data.tpm_limit,
        max_concurrency=data.max_concurrency,
        quota_rules=ApiKeyService._prepare_rules(data.quota_rules, []),
        encrypted_api_key=encrypted_key,
        key_fingerprint=fingerprint,
        masked_key=masked,
        enabled=True,
        proxy_id=data.proxy_id,
        status=CredentialStatus.HEALTHY,
        priority=data.priority,
        weight=data.weight,
        notes=(data.notes.strip() if data.notes and data.notes.strip() else None),
        consecutive_failures=0,
        metadata_json={},  # Credentials are stored only in encrypted_api_key.
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
        "notes": cred.notes,
    }


async def _get_module_profile(db: AsyncSession, module_id: str, profile_id: int) -> ProviderCredential:
    cred = await CredentialService.get_credential(db, profile_id)
    if not cred or cred.provider.slug != f"module_{module_id}":
        raise HTTPException(404, "Profile does not belong to this module")
    return cred


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
    cred = await _get_module_profile(db, module_id, profile_id)
    changes = data.model_dump(exclude_unset=True, exclude={"fields"})
    if "proxy_id" in changes and data.proxy_id is not None and await db.get(Proxy, data.proxy_id) is None:
        raise HTTPException(404, "Proxy not found")
    if data.fields is not None or module_id == "lingling" and "proxy_id" in changes:
        try:
            raw = decrypt_secret(cred.encrypted_api_key)
            current_fields = json.loads(raw) if raw.strip().startswith("{") else ({} if raw == "no-key" else {"api_key": raw})
            if not isinstance(current_fields, dict):
                raise ValueError("Profile fields must be a JSON object")
        except Exception:
            raise HTTPException(400, "Cannot decrypt profile fields; existing credentials were not changed") from None
        loaded = ModuleLoader.get_module(module_id)
        secret_keys = {f.key for f in loaded.manifest.fields if f.type == "password"} if loaded else set()
        secret_keys.update(("auth_json", "access_token", "refresh_token", "id_token", "key", "api_key", "apiKey", "user_token", "cookie", "cookies", "storage_state", "token_v2"))
        original_fields = current_fields.copy()
        for key, value in (data.fields or {}).items():
            if value is None:
                continue
            if key in secret_keys:
                if key in current_fields and value == mask_secret(str(current_fields[key])):
                    continue
                if isinstance(value, str) and value and value == mask_secret(value):
                    raise HTTPException(409, "Profile secret changed; reload the form before saving")
            current_fields[key] = value
        await _validate_lingling_pool(db, module_id, current_fields,
                                     data.proxy_id if "proxy_id" in changes else cred.proxy_id)
        if current_fields != original_fields:
            changes["api_key"] = json.dumps(current_fields)
    result = await CredentialService.update_credential(db, profile_id, CredentialUpdate(**changes))
    return {**result.model_dump(mode="json"), "module_id": module_id}


@router.put("/{module_id}/profiles/{profile_id}/notes")
async def update_module_profile_notes(
    module_id: str,
    profile_id: int,
    data: ModuleNotesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update plain text notes for a module profile (credential).
    """
    cred = await _get_module_profile(db, module_id, profile_id)

    clean_notes = data.notes.strip() if data.notes and data.notes.strip() else None
    notes = await CredentialService.update_credential_notes(db, profile_id, clean_notes)
    return {"profile_id": profile_id, "notes": notes}


@router.delete("/{module_id}/profiles/{profile_id}")
async def delete_module_profile(
    module_id: str,
    profile_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a module profile.
    """
    cred = await _get_module_profile(db, module_id, profile_id)

    await CredentialService.delete_credential(db, profile_id)
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
    await _get_module_profile(db, module_id, profile_id)
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
    cred = await _get_module_profile(db, module_id, profile_id)
    await ModelDiscoveryService.fetch_models_for_credential(db, profile_id)
    count = await db.scalar(select(func.count(DiscoveredModel.id)).where(
        DiscoveredModel.provider_id == cred.provider_id, DiscoveredModel.available == True)) or 0
    return {"success": True, "models_discovered": count}


@router.post("/{module_id}/profiles/{profile_id}/export")
async def export_module_profile(
    module_id: str,
    profile_id: int,
    format: str = "json",
    db: AsyncSession = Depends(get_db),
):
    """
    Export a profile to the profiles/ directory outside git.
    """
    from app.modules.profile_loader import export_profile_to_file
    await _get_module_profile(db, module_id, profile_id)
    try:
        res = await export_profile_to_file(db, profile_id, module_id, format)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Export failed: {str(e)}")


@router.post("/sync-profiles")
async def sync_all_disk_profiles(
    db: AsyncSession = Depends(get_db),
):
    """
    Manually rescan and synchronize profiles from the profiles/ directory.
    """
    from app.modules.profile_loader import sync_profiles_from_disk
    result = await sync_profiles_from_disk(db)
    return result


class BrowserOAuthStart(BaseModel):
    proxy_id: Optional[int] = Field(None, ge=1)


class BrowserOAuthCallback(BaseModel):
    callback_url: str = Field(..., min_length=1, max_length=8192)


class BrowserOAuthSave(ModuleProfileCreate):
    profile_id: Optional[int] = Field(None, ge=1)
    priority: Annotated[int, Field(ge=1, le=100)] = 1
    weight: Annotated[int, Field(ge=1, le=100)] = 1


@router.post("/{module_id}/oauth/start")
async def start_browser_oauth(module_id: str, data: BrowserOAuthStart,
                              db: AsyncSession = Depends(get_db), owner: str = Depends(get_current_admin)):
    loaded = ModuleLoader.get_module(module_id)
    if not loaded or loaded.status != "ready":
        raise HTTPException(404, "Module is unavailable")
    proxy_url = None
    if data.proxy_id is not None:
        proxy = await db.get(Proxy, data.proxy_id)
        if not proxy or not proxy.enabled:
            raise HTTPException(404, "Proxy is unavailable")
        proxy_url = ProxyService.build_proxy_url(proxy)
    return await module_oauth.start(module_id, owner, data.proxy_id, proxy_url)


@router.get("/{module_id}/oauth/{session_id}")
async def browser_oauth_status(module_id: str, session_id: str, owner: str = Depends(get_current_admin)):
    return JSONResponse(module_oauth.get_session(session_id, module_id, owner).public(),
                        headers={"Cache-Control": "no-store"})


@router.post("/{module_id}/oauth/{session_id}/callback")
async def browser_oauth_callback(module_id: str, session_id: str, data: BrowserOAuthCallback,
                                 owner: str = Depends(get_current_admin)):
    session = module_oauth.get_session(session_id, module_id, owner)
    return await module_oauth.exchange(session, data.callback_url)


@router.delete("/{module_id}/oauth/{session_id}")
async def cancel_browser_oauth(module_id: str, session_id: str, owner: str = Depends(get_current_admin)):
    module_oauth.get_session(session_id, module_id, owner)
    await module_oauth.cancel(session_id)
    return {"success": True}


@router.post("/{module_id}/oauth/{session_id}/save")
async def save_browser_oauth(module_id: str, session_id: str, data: BrowserOAuthSave,
                             db: AsyncSession = Depends(get_db), owner: str = Depends(get_current_admin)):
    session = module_oauth.get_session(session_id, module_id, owner)
    async with session.lock:
        module_oauth.get_session(session_id, module_id, owner)
        if session.status != "authorized" or not session.tokens:
            raise HTTPException(409, "Complete browser authorization before saving")
        if data.proxy_id != session.proxy_id:
            raise HTTPException(409, "Proxy changed; restart browser authorization")
        fields = {**data.fields, **session.tokens}
        if data.profile_id is not None:
            cred = (await db.execute(select(ProviderCredential).join(Provider).where(
                ProviderCredential.id == data.profile_id, Provider.slug == f"module_{module_id}"
            ))).scalar_one_or_none()
            if not cred:
                raise HTTPException(404, "Profile does not belong to this module")
            result = await update_module_profile(module_id, data.profile_id, ModuleProfileUpdate(
                **{**data.model_dump(exclude_unset=True, exclude={"profile_id", "fields"}), "fields": fields}), db)
            cred.status = CredentialStatus.HEALTHY if cred.enabled else CredentialStatus.DISABLED
            cred.consecutive_failures = 0
            cred.last_error = None
            cred.cooldown_until = None
            await db.commit()
            circuit_breaker.reset(cred.id)
            result["status"] = cred.status
        else:
            result = await create_module_profile(module_id, ModuleProfileCreate(
                **{**data.model_dump(exclude_unset=True, exclude={"profile_id", "fields"}), "fields": fields}), db)
        module_oauth.discard(session_id)
        return result

