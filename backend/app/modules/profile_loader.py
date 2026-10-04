import os
import json
import logging
import uuid
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

import yaml
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_secret, compute_fingerprint, mask_secret
from app.core.circuit_breaker import CredentialStatus
from app.models.entities import Provider, ProviderCredential, Proxy

logger = logging.getLogger("app.modules.profile_loader")

# Project root: directory containing 'backend'
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_profiles_dir() -> Path:
    """
    Get the directory where external module profiles are stored.
    Defaults to `<PROJECT_ROOT>/profiles/`, or the env var `PROFILES_DIR`.
    Ensures the directory exists.
    """
    custom = os.environ.get("PROFILES_DIR")
    if custom and custom.strip():
        p = Path(custom.strip()).resolve()
    else:
        p = PROJECT_ROOT / "profiles"

    p.mkdir(parents=True, exist_ok=True)
    return p


class DiskProfileData(BaseModel):
    module_id: str
    name: str
    enabled: bool = True
    priority: int = 1
    weight: int = 1
    proxy_id: Optional[int] = None
    proxy_name: Optional[str] = None
    proxy_url: Optional[str] = None
    notes: Optional[str] = None
    fields: Dict[str, Any] = Field(default_factory=dict)
    file_path: str = ""
    file_key: str = ""


def _parse_profile_dict(raw: Dict[str, Any], default_module_id: str, default_name: str, file_rel: str) -> Optional[DiskProfileData]:
    if not isinstance(raw, dict):
        return None

    module_id = str(raw.get("module") or raw.get("module_id") or default_module_id).strip()
    if not module_id:
        return None

    name = str(raw.get("name") or default_name).strip()
    enabled = bool(raw.get("enabled", True))
    priority = int(raw.get("priority", 1))
    weight = int(raw.get("weight", 1))

    proxy_id = raw.get("proxy_id")
    if proxy_id is not None:
        try:
            proxy_id = int(proxy_id)
        except (ValueError, TypeError):
            proxy_id = None

    proxy_name = raw.get("proxy_name")
    proxy_url = raw.get("proxy_url")
    raw_notes = raw.get("notes")
    notes = raw_notes.strip() if raw_notes and isinstance(raw_notes, str) and raw_notes.strip() else None

    # Fields can be nested under `fields` or placed at top-level
    raw_fields = raw.get("fields")
    fields: Dict[str, Any] = {}
    if isinstance(raw_fields, dict):
        fields.update(raw_fields)

    # Also capture any extra top-level keys that look like credential tokens
    reserved_keys = {
        "module", "module_id", "name", "enabled", "priority", "weight",
        "proxy_id", "proxy_name", "proxy_url", "notes", "fields", "source", "description"
    }
    for k, v in raw.items():
        if k not in reserved_keys and k not in fields:
            fields[k] = v

    file_key = f"{module_id}:{name}"

    return DiskProfileData(
        module_id=module_id,
        name=name,
        enabled=enabled,
        priority=priority,
        weight=weight,
        proxy_id=proxy_id,
        proxy_name=proxy_name,
        proxy_url=proxy_url,
        notes=notes,
        fields=fields,
        file_path=file_rel,
        file_key=file_key,
    )


def scan_disk_profiles(profiles_dir: Optional[Path] = None) -> List[DiskProfileData]:
    """
    Recursively scans the profiles directory for .json, .yaml, and .yml profile definitions.
    Skips:
      - Files / folders starting with '.' or '_'
      - Example templates ending with .example.json, .example.yaml, etc.
      - Documentation files (.md, .txt)
    """
    target_dir = profiles_dir or get_profiles_dir()
    if not target_dir.exists():
        return []

    discovered: List[DiskProfileData] = []

    for path in sorted(target_dir.rglob("*")):
        if not path.is_file():
            continue

        # Skip hidden or private files/dirs
        rel_parts = path.relative_to(target_dir).parts
        if any(part.startswith(".") or part.startswith("_") for part in rel_parts):
            continue

        # Skip examples and docs
        filename = path.name.lower()
        if ".example." in filename or filename.endswith(".md") or filename.endswith(".txt"):
            continue

        suffix = path.suffix.lower()
        if suffix not in (".json", ".yaml", ".yml"):
            continue

        try:
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                continue

            if suffix == ".json":
                data = json.loads(content)
            else:
                data = yaml.safe_load(content)

            # Determine default module ID and profile name from folder / filename
            rel_path = path.relative_to(target_dir)
            rel_str = str(rel_path)

            if len(rel_parts) > 1:
                default_mod = rel_parts[0]
                default_name = path.stem.replace("_", " ").title()
            else:
                default_mod = path.stem
                default_name = f"{default_mod.title()} File Profile"

            if isinstance(data, list):
                for idx, item in enumerate(data):
                    if isinstance(item, dict):
                        item_name = item.get("name") or f"{default_name} #{idx + 1}"
                        prof = _parse_profile_dict(item, default_mod, item_name, rel_str)
                        if prof:
                            discovered.append(prof)
            elif isinstance(data, dict):
                prof = _parse_profile_dict(data, default_mod, default_name, rel_str)
                if prof:
                    discovered.append(prof)

        except Exception as e:
            logger.error(f"Error parsing profile file '{path}': {e}")

    return discovered


async def sync_profiles_from_disk(db: AsyncSession, profiles_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Synchronizes disk profiles with the `provider_credentials` database table.
    - Matches or registers credentials under `Provider(slug=module_<module_id>)`.
    - Upserts credentials with encrypted secrets.
    - Flags deleted disk profiles as disabled.
    """
    from app.modules.loader import ModuleLoader

    if not ModuleLoader._modules:
        ModuleLoader.scan_modules()

    disk_profiles = scan_disk_profiles(profiles_dir)
    logger.info(f"Scanned {len(disk_profiles)} profile definitions from disk ({get_profiles_dir()})")

    created_count = 0
    updated_count = 0
    errors: List[str] = []
    seen_file_keys = set()

    for p in disk_profiles:
        try:
            # 1. Check if module is loaded
            module_id = p.module_id
            loaded = ModuleLoader.get_module(module_id)
            if not loaded or loaded.status != "ready":
                msg = f"Skipping profile '{p.name}': module '{module_id}' is not loaded or failed"
                logger.warning(msg)
                errors.append(msg)
                continue

            # 2. Find Provider
            provider_slug = f"module_{module_id}"
            prov = (await db.execute(select(Provider).where(Provider.slug == provider_slug))).scalar_one_or_none()
            if not prov:
                msg = f"Provider record for '{provider_slug}' not found in DB"
                logger.warning(msg)
                errors.append(msg)
                continue

            # 3. Resolve Proxy if specified by name or url
            proxy_id = p.proxy_id
            if not proxy_id and (p.proxy_name or p.proxy_url):
                if p.proxy_name:
                    px = (await db.execute(select(Proxy).where(Proxy.name == p.proxy_name))).scalar_one_or_none()
                    if px:
                        proxy_id = px.id
                if not proxy_id and p.proxy_url:
                    px = (await db.execute(select(Proxy).where(Proxy.host.contains(p.proxy_url)))).scalar_one_or_none()
                    if px:
                        proxy_id = px.id

            # 4. Serialize and encrypt fields
            serialized_fields = json.dumps(p.fields)
            encrypted_key = encrypt_secret(serialized_fields)
            fingerprint = compute_fingerprint(f"{module_id}_{p.name}_{serialized_fields}")

            # Mask primary field for display
            masked = "(File Profile)"
            for k in ("api_key", "token_v2", "user_token", "apiKey", "cookie"):
                if k in p.fields and p.fields[k]:
                    masked = mask_secret(str(p.fields[k]))
                    break
            if masked == "(File Profile)" and p.fields:
                masked = mask_secret(str(list(p.fields.values())[0]))

            metadata = dict(p.fields)
            metadata["_source"] = "file"
            metadata["_file_path"] = p.file_path
            metadata["_file_profile_key"] = p.file_key

            seen_file_keys.add(p.file_key)

            # 5. Look for existing credential with same provider_id and matching file key or name
            existing_creds = (await db.execute(
                select(ProviderCredential).where(ProviderCredential.provider_id == prov.id)
            )).scalars().all()

            target_cred: Optional[ProviderCredential] = None
            for c in existing_creds:
                meta = c.metadata_json if isinstance(c.metadata_json, dict) else {}
                if meta.get("_file_profile_key") == p.file_key or c.name == p.name:
                    target_cred = c
                    break

            if target_cred:
                # Update existing
                target_cred.name = p.name
                target_cred.encrypted_api_key = encrypted_key
                target_cred.key_fingerprint = fingerprint
                target_cred.masked_key = masked
                target_cred.enabled = p.enabled
                target_cred.priority = p.priority
                target_cred.weight = p.weight
                if p.notes:
                    target_cred.notes = p.notes
                if proxy_id:
                    target_cred.proxy_id = proxy_id
                target_cred.metadata_json = metadata
                if target_cred.status == CredentialStatus.DISABLED and p.enabled:
                    target_cred.status = CredentialStatus.HEALTHY
                updated_count += 1
                logger.info(f"Updated file-based profile '{p.name}' for module '{module_id}'")
            else:
                # Create new
                new_cred = ProviderCredential(
                    provider_id=prov.id,
                    name=p.name,
                    encrypted_api_key=encrypted_key,
                    key_fingerprint=fingerprint,
                    masked_key=masked,
                    enabled=p.enabled,
                    proxy_id=proxy_id,
                    status=CredentialStatus.HEALTHY if p.enabled else CredentialStatus.DISABLED,
                    priority=p.priority,
                    weight=p.weight,
                    notes=p.notes,
                    consecutive_failures=0,
                    metadata_json=metadata,
                )
                db.add(new_cred)
                created_count += 1
                logger.info(f"Created file-based profile '{p.name}' for module '{module_id}' from {p.file_path}")

        except Exception as e:
            err_msg = f"Failed to sync profile '{p.name}': {e}"
            logger.error(err_msg, exc_info=True)
            errors.append(err_msg)

    # 6. Flag any previous file credentials whose file was removed from disk as disabled
    all_file_creds = (await db.execute(
        select(ProviderCredential)
    )).scalars().all()

    orphaned_count = 0
    for c in all_file_creds:
        meta = c.metadata_json if isinstance(c.metadata_json, dict) else {}
        if meta.get("_source") == "file":
            f_key = meta.get("_file_profile_key")
            if f_key and f_key not in seen_file_keys:
                if c.enabled:
                    c.enabled = False
                    c.status = CredentialStatus.DISABLED
                    c.last_error = "Profile file no longer exists in profiles directory"
                    orphaned_count += 1
                    logger.info(f"Disabled orphaned file profile '{c.name}' (key: {f_key})")

    await db.commit()

    return {
        "total_scanned": len(disk_profiles),
        "created": created_count,
        "updated": updated_count,
        "orphaned_disabled": orphaned_count,
        "errors": errors,
        "profiles_dir": str(get_profiles_dir()),
    }


async def export_profile_to_file(
    db: AsyncSession,
    credential_id: int,
    module_id: str,
    format_ext: str = "json",
    target_profiles_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Exports a credential from DB to `<PROFILES_DIR>/<module_id>/<safe_name>.json` (or .yaml).
    """
    from app.core.crypto import decrypt_secret

    cred = (await db.execute(
        select(ProviderCredential).where(ProviderCredential.id == credential_id)
    )).scalar_one_or_none()

    if not cred:
        raise ValueError(f"Credential {credential_id} not found")

    # Decrypt fields
    fields: Dict[str, Any] = {}
    if cred.encrypted_api_key:
        try:
            decrypted = decrypt_secret(cred.encrypted_api_key)
            if decrypted.strip().startswith("{") and decrypted.strip().endswith("}"):
                fields = json.loads(decrypted)
            else:
                fields = {"api_key": decrypted}
        except Exception:
            if isinstance(cred.metadata_json, dict):
                fields = {k: v for k, v in cred.metadata_json.items() if not k.startswith("_")}

    if isinstance(cred.metadata_json, dict):
        for k, v in cred.metadata_json.items():
            if not k.startswith("_") and k not in fields:
                fields[k] = v

    safe_name = re.sub(r"[^\w\-_]+", "_", cred.name).strip("_").lower() or "profile"

    base_dir = target_profiles_dir or get_profiles_dir()
    profile_dir = base_dir / module_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    ext = "yaml" if format_ext.lower() in ("yaml", "yml") else "json"
    file_path = profile_dir / f"{safe_name}.{ext}"

    payload = {
        "module": module_id,
        "name": cred.name,
        "enabled": cred.enabled,
        "priority": cred.priority,
        "weight": cred.weight,
        "fields": fields,
    }
    if cred.notes:
        payload["notes"] = cred.notes
    if cred.proxy_id:
        payload["proxy_id"] = cred.proxy_id

    if ext == "json":
        file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        file_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # Update metadata in DB to link to the exported file
    if isinstance(cred.metadata_json, dict):
        cred.metadata_json["_source"] = "file"
        cred.metadata_json["_file_path"] = str(file_path.relative_to(base_dir))
        cred.metadata_json["_file_profile_key"] = f"{module_id}:{cred.name}"
        await db.commit()

    return {
        "success": True,
        "file_path": str(file_path),
        "relative_path": str(file_path.relative_to(base_dir)),
    }
