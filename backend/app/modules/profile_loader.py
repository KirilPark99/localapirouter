import os
import json
import logging
import hashlib
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

import yaml
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_secret, decrypt_secret, compute_fingerprint, mask_secret
from app.core.circuit_breaker import CredentialStatus
from app.models.entities import Provider, ProviderCredential, Proxy, DiscoveredModel, CredentialModelPreference
from app.schemas.entities import CredentialQuotaRules

logger = logging.getLogger("app.modules.profile_loader")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_profiles_dir() -> Path:
    custom = os.environ.get("PROFILES_DIR")
    p = Path(custom.strip()).resolve() if custom and custom.strip() else PROJECT_ROOT / "profiles"
    p.mkdir(parents=True, exist_ok=True)
    return p


class DiskProfileData(BaseModel):
    module_id: str = Field(pattern=r"^[\w-]+$")
    name: str = Field(min_length=1)
    enabled: bool = True
    priority: int = Field(default=1, ge=1)
    weight: int = Field(default=1, ge=1)
    group_name: Optional[str] = None
    rpm_limit: Optional[int] = Field(default=None, ge=1)
    tpm_limit: Optional[int] = Field(default=None, ge=1)
    max_concurrency: Optional[int] = Field(default=None, ge=1)
    quota_rules: CredentialQuotaRules = Field(default_factory=list)
    model_preferences: List[str] = Field(default_factory=list)
    proxy_id: Optional[int] = Field(default=None, ge=1)
    proxy_ref: Optional[Dict[str, Any]] = None
    proxy_name: Optional[str] = None
    proxy_url: Optional[str] = None
    notes: Optional[str] = None
    fields: Dict[str, Any] = Field(default_factory=dict)
    file_path: str = ""
    file_key: str = ""
    file_hash: str = ""


def _parse_profile_dict(raw: Dict[str, Any], default_module_id: str, default_name: str, file_rel: str) -> DiskProfileData:
    if not isinstance(raw, dict):
        raise ValueError("Profile must be an object")
    module_id = str(raw.get("module") or raw.get("module_id") or default_module_id).strip()
    name = str(raw.get("name") or default_name).strip()
    reserved = set(DiskProfileData.model_fields) | {"module", "source", "description"}
    fields = raw.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("Profile fields must be an object")
    fields = {**{k: v for k, v in raw.items() if k not in reserved}, **fields}
    values = {k: raw[k] for k in DiskProfileData.model_fields if k in raw and k not in ("module_id", "name", "fields", "file_path", "file_key", "file_hash")}
    return DiskProfileData(**values, module_id=module_id, name=name, fields=fields,
                           file_path=file_rel, file_key=f"{module_id}:{name}")


def scan_disk_profiles(profiles_dir: Optional[Path] = None, errors: Optional[List[str]] = None) -> List[DiskProfileData]:
    target_dir = profiles_dir if profiles_dir is not None else get_profiles_dir()
    discovered = []
    try:
        paths = sorted(target_dir.rglob("*"))
        for path in paths:
            rel = path.relative_to(target_dir)
            if any(part.startswith((".", "_")) for part in rel.parts) or ".example." in path.name.lower():
                continue
            suffix = path.suffix.lower()
            if suffix not in (".json", ".yaml", ".yml") or not path.is_file():
                continue
            try:
                source = path.read_bytes()
                data = json.loads(source) if suffix == ".json" else yaml.safe_load(source.decode("utf-8"))
                default_mod = rel.parts[0] if len(rel.parts) > 1 else path.stem
                default_name = path.stem.replace("_", " ").title() if len(rel.parts) > 1 else f"{default_mod.title()} File Profile"
                items = data if isinstance(data, list) else [data]
                parsed = []
                for idx, item in enumerate(items):
                    name = f"{default_name} #{idx + 1}" if isinstance(data, list) else default_name
                    prof = _parse_profile_dict(item, default_mod, name, str(rel))
                    prof.file_hash = hashlib.sha256(source).hexdigest()
                    parsed.append(prof)
                discovered.extend(parsed)
            except Exception as exc:
                # Do not expose validation input values (which can contain secrets).
                msg = f"Error parsing profile file '{rel}': {type(exc).__name__}"
                logger.error(msg)
                if errors is not None:
                    errors.append(msg)
    except OSError as exc:
        msg = f"Error scanning profiles directory: {type(exc).__name__}"
        logger.error(msg)
        if errors is not None:
            errors.append(msg)
    duplicates = {key for key, count in Counter(p.file_key for p in discovered).items() if count > 1}
    for key in sorted(duplicates):
        msg = f"Duplicate profile key '{key}' in source files"
        logger.error(msg)
        if errors is not None:
            errors.append(msg)
    return [p for p in discovered if p.file_key not in duplicates]


def _profile_hash(profile: DiskProfileData) -> str:
    # One shared file may contain several accounts; edits to a sibling are not this account's edits.
    value = profile.model_dump(mode="json", exclude={"file_path", "file_key", "file_hash"})
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _profile_metadata(cred, fields, module_id):
    """Remove old sync's plaintext field copies, retaining unrelated metadata."""
    from app.modules.loader import ModuleLoader
    decrypted = decrypt_secret(cred.encrypted_api_key)
    stored = json.loads(decrypted) if decrypted.strip().startswith("{") else {}
    keys = set(fields) | set(stored) | {"api_key", "apiKey", "cookie", "cookies", "storage_state", "auth_json", "access_token", "refresh_token", "id_token", "token", "token_v2", "user_token", "key"}
    loaded = ModuleLoader.get_module(module_id)
    if loaded:
        keys.update(f.key for f in loaded.manifest.fields)
    return {k: v for k, v in (cred.metadata_json or {}).items() if k not in keys}


def mark_profile_db_owned(cred) -> None:
    """Called before committing DB mutations; unchanged files must not undo them."""
    meta = cred.metadata_json if isinstance(cred.metadata_json, dict) else {}
    module_id = meta.get("_file_profile_key", "").split(":", 1)[0]
    cleaned = _profile_metadata(cred, {}, module_id)
    if meta.get("_source") == "file":
        cleaned["_file_db_owned"] = True
    cred.metadata_json = cleaned


async def sync_profiles_from_disk(db: AsyncSession, profiles_dir: Optional[Path] = None) -> Dict[str, Any]:
    from app.modules.loader import ModuleLoader
    from app.services.api_key_service import ApiKeyService

    if not ModuleLoader._modules:
        ModuleLoader.scan_modules()
    target_dir = profiles_dir if profiles_dir is not None else get_profiles_dir()
    errors: List[str] = []
    disk_profiles = scan_disk_profiles(target_dir, errors)
    created_count = updated_count = orphaned_count = 0
    seen_file_keys = {p.file_key for p in disk_profiles}
    path_counts = Counter(p.file_path for p in disk_profiles)

    for p in disk_profiles:
        try:
            # One bad profile must not partially mutate itself or poison the session.
            async with db.begin_nested():
                if p.module_id == "lingling" and (p.proxy_id is not None or p.fields.get("proxy_ids")):
                    raise ValueError("Lingling disk profiles require portable proxy references, not numeric IDs")
                loaded = ModuleLoader.get_module(p.module_id)
                if not loaded or loaded.status != "ready":
                    raise ValueError(f"Module '{p.module_id}' is not ready")
                prov = await db.scalar(select(Provider).where(Provider.slug == f"module_{p.module_id}"))
                if not prov:
                    raise ValueError(f"Provider for '{p.module_id}' not found")
                existing = (await db.scalars(select(ProviderCredential).where(ProviderCredential.provider_id == prov.id))).all()
                target = next((c for c in existing if (c.metadata_json or {}).get("_file_profile_key") == p.file_key), None)
                if target is None and path_counts[p.file_path] == 1:
                    same_path = [c for c in existing if (c.metadata_json or {}).get("_file_path") == p.file_path
                                 and (c.metadata_json or {}).get("_file_root", str(target_dir.resolve())) == str(target_dir.resolve())]
                    if len(same_path) == 1:
                        target = same_path[0]
                if target is None:
                    target = next((c for c in existing if c.name == p.name), None)
                if target and (target.metadata_json or {}).get("_file_db_owned"):
                    old_hash = target.metadata_json.get("_file_hash")
                    if (not old_hash or old_hash == p.file_hash or
                            target.metadata_json.get("_file_profile_hash") == _profile_hash(p)):
                        target.metadata_json = {**_profile_metadata(target, p.fields, p.module_id),
                            "_file_hash": p.file_hash, "_file_profile_hash": _profile_hash(p)}
                        continue

                proxy_id = p.proxy_id
                if p.module_id == "lingling" and p.proxy_ref is not None:
                    from app.services.proxy_service import ProxyService
                    resolved = await ProxyService.import_pool_fields(db, {"proxy_refs": [p.proxy_ref]})
                    proxy_id = resolved["proxy_ids"][0]
                if proxy_id is not None and await db.get(Proxy, proxy_id) is None:
                    raise ValueError("Profile proxy not found")
                if proxy_id is None and (p.proxy_name or p.proxy_url):
                    proxy = await db.scalar(select(Proxy).where(Proxy.name == p.proxy_name)) if p.proxy_name else None
                    if proxy is None and p.proxy_url:
                        proxy = await db.scalar(select(Proxy).where(Proxy.host.contains(p.proxy_url)))
                    if proxy is None:
                        raise ValueError("Profile proxy not found")
                    proxy_id = proxy.id

                models = []
                if len(set(p.model_preferences)) != len(p.model_preferences):
                    raise ValueError("Duplicate model preferences")
                for slug in p.model_preferences:
                    model = await db.scalar(select(DiscoveredModel).where(DiscoveredModel.provider_id == prov.id, DiscoveredModel.canonical_slug == slug).order_by(DiscoveredModel.id))
                    if model is None:
                        raise ValueError(f"Model preference '{slug}' not found for module")
                    models.append(model)

                # Rule IDs belong to the destination credential, not the export DB.
                old_rules = target.quota_rules or [] if target else []
                prepared = (ApiKeyService._restore_credential_rules(p.quota_rules, old_rules)
                            if "quota_rules" in p.model_fields_set or target is None else old_rules)
                fields = p.fields
                if p.module_id == "lingling" and ("proxy_ids" in fields or "proxy_refs" in fields):
                    from app.services.proxy_service import ProxyService
                    fields = await ProxyService.import_pool_fields(db, fields)
                serialized = json.dumps(fields)
                masked = next((fields[k] for k in ("api_key", "token_v2", "user_token", "apiKey", "cookie") if fields.get(k)), next(iter(fields.values()), None))
                metadata = _profile_metadata(target, p.fields, p.module_id) if target else {}
                metadata.update(_source="file", _file_path=p.file_path, _file_profile_key=p.file_key,
                                _file_hash=p.file_hash, _file_profile_hash=_profile_hash(p),
                                _file_db_owned=False, _file_root=str(target_dir.resolve()))
                values = dict(name=p.name, encrypted_api_key=encrypt_secret(serialized),
                              key_fingerprint=compute_fingerprint(f"{p.module_id}_{p.name}_{serialized}"),
                              masked_key=mask_secret(str(masked)) if masked is not None else "(File Profile)",
                              enabled=p.enabled, priority=p.priority, weight=p.weight, proxy_id=proxy_id,
                              notes=p.notes, group_name=p.group_name, rpm_limit=p.rpm_limit, tpm_limit=p.tpm_limit,
                              max_concurrency=p.max_concurrency, quota_rules=prepared, metadata_json=metadata)
                if target:
                    # Old profile files predate these optional controls; absence is not a reset.
                    for key in ("notes", "proxy_id", "group_name", "rpm_limit", "tpm_limit", "max_concurrency"):
                        if key not in p.model_fields_set and not (key == "proxy_id" and
                                ((p.module_id == "lingling" and "proxy_ref" in p.model_fields_set) or p.proxy_name or p.proxy_url)):
                            values.pop(key)
                    for key, value in values.items():
                        setattr(target, key, value)
                    if not p.enabled:
                        target.status = CredentialStatus.DISABLED
                    elif target.status == CredentialStatus.DISABLED:
                        target.status = CredentialStatus.HEALTHY
                else:
                    target = ProviderCredential(provider_id=prov.id, **values,
                        status=CredentialStatus.HEALTHY if p.enabled else CredentialStatus.DISABLED, consecutive_failures=0)
                    db.add(target)
                await db.flush()
                if "model_preferences" in p.model_fields_set or target not in existing:
                    await db.execute(delete(CredentialModelPreference).where(CredentialModelPreference.credential_id == target.id))
                    db.add_all([CredentialModelPreference(credential_id=target.id, model_id=m.id, priority_order=i) for i, m in enumerate(models)])
                await db.flush()
            if target in existing:
                updated_count += 1
            else:
                created_count += 1
        except Exception as exc:
            msg = f"Failed to sync profile '{p.name}': {type(exc).__name__}"
            logger.error(msg)
            errors.append(msg)

    # A failed scan/import is not evidence of deletion. Only complete scans prune.
    if not errors:
        for c in (await db.scalars(select(ProviderCredential))).all():
            meta = c.metadata_json or {}
            if meta.get("_file_root") and meta["_file_root"] != str(target_dir.resolve()):
                continue
            if meta.get("_source") == "file" and meta.get("_file_profile_key") not in seen_file_keys:
                if c.enabled:
                    c.enabled = False
                    c.status = CredentialStatus.DISABLED
                    c.last_error = "Profile file no longer exists in profiles directory"
                    orphaned_count += 1
    await db.commit()
    return {"total_scanned": len(disk_profiles), "created": created_count, "updated": updated_count,
            "orphaned_disabled": orphaned_count, "errors": errors, "profiles_dir": str(target_dir)}


async def export_profile_to_file(db: AsyncSession, credential_id: int, module_id: str,
                                 format_ext: str = "json", target_profiles_dir: Optional[Path] = None) -> Dict[str, Any]:
    cred = await db.get(ProviderCredential, credential_id)
    if not cred:
        raise ValueError(f"Credential {credential_id} not found")
    provider = await db.get(Provider, cred.provider_id)
    if not re.fullmatch(r"[\w-]+", module_id) or (provider.configuration or {}).get("module_id") != module_id:
        raise ValueError("Profile does not belong to this module")
    ext = format_ext.lower()
    if ext not in ("json", "yaml", "yml"):
        raise ValueError("Export format must be json or yaml")
    ext = "yaml" if ext == "yml" else ext
    # No plaintext metadata fallback, and no successful empty export on failure.
    decrypted = decrypt_secret(cred.encrypted_api_key)
    if not decrypted:
        raise ValueError("Profile credentials are empty")
    fields = json.loads(decrypted) if decrypted.strip().startswith(("{", "[")) else {"api_key": decrypted}
    if not isinstance(fields, dict):
        raise ValueError("Profile credentials must be an object")
    if module_id == "lingling" and ("proxy_ids" in fields or "proxy_refs" in fields):
        from app.services.proxy_service import ProxyService
        fields = await ProxyService.export_pool_fields(db, fields)
    prefs = (await db.execute(select(DiscoveredModel.canonical_slug).join(CredentialModelPreference,
        CredentialModelPreference.model_id == DiscoveredModel.id).where(CredentialModelPreference.credential_id == cred.id)
        .order_by(CredentialModelPreference.priority_order, CredentialModelPreference.id))).scalars().all()
    payload = {"module": module_id, "fields": fields, "model_preferences": list(prefs)}
    for key in ("name", "enabled", "priority", "weight", "notes", "proxy_id", "group_name",
                "rpm_limit", "tpm_limit", "max_concurrency", "quota_rules"):
        payload[key] = getattr(cred, key)
    if module_id == "lingling":
        from app.services.proxy_service import ProxyService
        proxy_id = payload.pop("proxy_id")
        refs = await ProxyService.export_pool_fields(db, {"transport_mode": "proxy", "proxy_ids": [proxy_id] if proxy_id is not None else []})
        payload["proxy_ref"] = refs["proxy_refs"][0] if refs["proxy_refs"] else None
    # Validate the complete payload before publishing anything.
    profile = _parse_profile_dict(payload, module_id, cred.name, "")
    base_dir = target_profiles_dir if target_profiles_dir is not None else get_profiles_dir()
    profile_dir = base_dir / module_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w-]+", "_", cred.name).strip("_").lower() or "profile"
    file_path = profile_dir / f"{safe_name}.{ext}"
    metadata = _profile_metadata(cred, fields, module_id)
    document = payload
    replace_hash = None
    if (metadata.get("_source") == "file" and metadata.get("_file_path") and
            metadata.get("_file_root", str(base_dir.resolve())) == str(base_dir.resolve())):
        linked = base_dir / metadata["_file_path"]
        if linked.parent.resolve() != profile_dir.resolve():
            raise ValueError("Linked profile path is outside this module directory")
        if linked.exists():
            source = linked.read_bytes()
            replace_hash = metadata.get("_file_hash")
            if not replace_hash or hashlib.sha256(source).hexdigest() != replace_hash:
                raise ValueError("Profile source changed on disk; synchronize it before exporting")
            linked_ext = "yaml" if linked.suffix.lower() in (".yaml", ".yml") else "json"
            if linked_ext != ext:
                raise ValueError("Use the linked profile's existing format or another export directory")
            document = json.loads(source) if ext == "json" else yaml.safe_load(source.decode("utf-8"))
            if isinstance(document, list):
                matches = [i for i, entry in enumerate(document) if _parse_profile_dict(
                    entry, module_id, "", metadata["_file_path"]).file_key == metadata.get("_file_profile_key")]
                if len(matches) != 1:
                    raise ValueError("Linked profile is missing or ambiguous in its source file")
                document[matches[0]] = payload
                keys = [_parse_profile_dict(entry, module_id, "", "").file_key for entry in document]
                if len(keys) != len(set(keys)):
                    raise ValueError("Profile name conflicts with another account in the source file")
            else:
                document = payload
            file_path = linked
    content = (json.dumps(document, indent=2, ensure_ascii=False) + "\n" if ext == "json" else
               yaml.safe_dump(document, allow_unicode=True, sort_keys=False)).encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".profile-", dir=profile_dir)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if replace_hash is not None:
            if hashlib.sha256(file_path.read_bytes()).hexdigest() != replace_hash:
                raise ValueError("Profile source changed during export; no file was replaced")
            os.replace(temporary, file_path)
        else:
            # New exports never replace an unrelated or concurrently created file.
            suffix = 0
            while True:
                try:
                    os.link(temporary, file_path)
                    break
                except FileExistsError:
                    suffix += 1
                    file_path = profile_dir / f"{safe_name}-{cred.id}-{suffix}.{ext}"
    finally:
        Path(temporary).unlink(missing_ok=True)
    cred.metadata_json = {**metadata, "_source": "file",
                         "_file_path": str(file_path.relative_to(base_dir)),
                         "_file_profile_key": f"{module_id}:{cred.name}",
                         "_file_hash": hashlib.sha256(content).hexdigest(),
                         "_file_profile_hash": _profile_hash(profile), "_file_db_owned": True,
                         "_file_root": str(base_dir.resolve())}
    await db.commit()
    return {"success": True, "file_path": str(file_path), "relative_path": str(file_path.relative_to(base_dir))}
