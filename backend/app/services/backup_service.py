import json
import base64
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app.models.entities import Provider, ProviderCredential, Proxy
from app.schemas.entities import ProviderCreate, CredentialCreate, ProxyCreate
from pydantic import ValidationError
from app.core.crypto import encrypt_secret, decrypt_secret, compute_fingerprint, mask_secret

MIN_BACKUP_PASSPHRASE_LENGTH = 12


def _require_passphrase(passphrase: Optional[str]) -> str:
    value = (passphrase or "").strip()
    if len(value) < MIN_BACKUP_PASSPHRASE_LENGTH:
        raise ValueError(
            f"Backup passphrase must contain at least {MIN_BACKUP_PASSPHRASE_LENGTH} characters"
        )
    return value


def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    """Derives a 32-byte urlsafe base64 Fernet key from a passphrase and salt using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_payload(data_dict: dict, passphrase: str) -> dict:
    """Encrypts a backup dictionary into an encrypted envelope."""
    passphrase = _require_passphrase(passphrase)
    salt = os.urandom(16)
    key = _derive_fernet_key(passphrase, salt)
    fernet = Fernet(key)
    raw_json = json.dumps(data_dict, ensure_ascii=False, default=str).encode("utf-8")
    token = fernet.encrypt(raw_json)
    return {
        "version": 1,
        "type": "myairouter_backup",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "encrypted": True,
        "salt": base64.b64encode(salt).decode("ascii"),
        "ciphertext": token.decode("ascii"),
    }


def decrypt_payload(envelope: dict, passphrase: Optional[str] = None) -> dict:
    """Decrypts an encrypted backup payload."""
    if not isinstance(envelope, dict):
        raise ValueError("Invalid backup data format (JSON object expected)")

    if envelope.get("encrypted") is True:
        passphrase = _require_passphrase(passphrase)
        salt_b64 = envelope.get("salt")
        ciphertext = envelope.get("ciphertext")
        if not salt_b64 or not ciphertext:
            raise ValueError("Corrupted encrypted backup file structure")
        try:
            salt = base64.b64decode(salt_b64)
            key = _derive_fernet_key(passphrase, salt)
            fernet = Fernet(key)
            decrypted_bytes = fernet.decrypt(ciphertext.encode("ascii"))
            return json.loads(decrypted_bytes.decode("utf-8"))
        except Exception as e:
            raise ValueError("Incorrect passphrase or corrupted encrypted backup file")

    raise ValueError("Unencrypted backup files are not accepted")


class BackupService:
    @classmethod
    async def _validated_payload(cls, db: AsyncSession, envelope: dict, passphrase: Optional[str]) -> dict:
        def check_header(value):
            if not isinstance(value, dict) or value.get("type") != "myairouter_backup" or type(value.get("version")) is not int or value["version"] != 1:
                raise ValueError("Unsupported backup type or version")
        check_header(envelope)
        data = decrypt_payload(envelope, passphrase)
        check_header(data)
        for field, schema in (("providers", ProviderCreate), ("credentials", CredentialCreate), ("proxies", ProxyCreate)):
            entries = data.get(field, [])
            if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
                raise ValueError(f"Backup {field} must be an array of objects")
            normalized = []
            for item in entries:
                try:
                    values = {**item, "provider_id": 1} if field == "credentials" else item
                    checked = schema.model_validate(values)
                except ValidationError:
                    raise ValueError(f"Invalid backup {field} structure") from None
                # Preserve backup-only references/metadata, but use the existing API types.
                normalized.append({**item, **checked.model_dump(exclude_unset=True)})
            data[field] = normalized
        slugs = [p["slug"] for p in data["providers"]]
        if any(not slug or slug != slug.strip() for slug in slugs) or len(slugs) != len(set(slugs)):
            raise ValueError("Backup provider slugs must be nonempty and unique")
        for credential in data["credentials"]:
            slug, name = credential.get("provider_slug"), credential.get("provider_name")
            if slug is not None and not isinstance(slug, str) or name is not None and not isinstance(name, str):
                raise ValueError("Invalid credential provider reference")
            if slug:
                known = slug in slugs or await db.scalar(select(Provider.id).where(Provider.slug == slug)) is not None
            elif name:
                count = sum(p["name"] == name for p in data["providers"])
                existing = list((await db.scalars(select(Provider.id).where(Provider.name == name))).all()) if not count else []
                known = count == 1 or not count and len(existing) == 1
            else:
                known = False
            if not known:
                raise ValueError("Credential references an unknown or ambiguous provider")
            if not isinstance(credential.get("metadata_json", {}), dict):
                raise ValueError("Credential metadata must be an object")
            reference = credential.get("proxy_ref")
            if reference is not None:
                try:
                    credential["proxy_ref"] = ProxyCreate.model_validate(reference).model_dump()
                except ValidationError:
                    raise ValueError("Invalid credential proxy reference") from None
        return data

    @classmethod
    async def export_data(
        cls,
        db: AsyncSession,
        provider_ids: Optional[List[int]] = None,
        include_proxies: bool = True,
        *,
        passphrase: str,
    ) -> Dict[str, Any]:
        """
        Exports providers, credentials (with decrypted API keys for cross-server portability),
        and optionally proxies.
        """
        # 1. Fetch Providers
        query = select(Provider).options(
            selectinload(Provider.credentials).selectinload(ProviderCredential.proxy)
        ).order_by(Provider.id.asc())

        if provider_ids:
            query = query.where(Provider.id.in_(provider_ids))

        res = await db.execute(query)
        providers = res.scalars().all()

        exported_providers: List[Dict[str, Any]] = []
        exported_credentials: List[Dict[str, Any]] = []
        proxies_map: Dict[int, Proxy] = {}

        for prov in providers:
            exported_providers.append({
                "name": prov.name,
                "slug": prov.slug,
                "adapter_type": prov.adapter_type,
                "base_url": prov.base_url,
                "models_endpoint": prov.models_endpoint,
                "chat_endpoint": prov.chat_endpoint,
                "responses_endpoint": prov.responses_endpoint,
                "enabled": prov.enabled,
                "auth_type": prov.auth_type,
                "auth_header": prov.auth_header,
                "extra_headers": prov.extra_headers or {},
                "configuration": prov.configuration or {},
            })

            for cred in prov.credentials:
                # Decrypt raw secret for cross-instance migration
                raw_key = ""
                if cred.encrypted_api_key:
                    try:
                        raw_key = decrypt_secret(cred.encrypted_api_key)
                    except Exception:
                        raw_key = ""

                cred_dict: Dict[str, Any] = {
                    "name": cred.name,
                    "provider_slug": prov.slug,
                    "provider_name": prov.name,
                    "api_key": raw_key,
                    "group_name": cred.group_name,
                    "enabled": cred.enabled,
                    "priority": cred.priority,
                    "weight": cred.weight,
                    "rpm_limit": cred.rpm_limit,
                    "tpm_limit": cred.tpm_limit,
                    "max_concurrency": cred.max_concurrency,
                    "metadata_json": cred.metadata_json or {},
                }

                if cred.proxy:
                    proxies_map[cred.proxy.id] = cred.proxy
                    cred_dict["proxy_ref"] = {
                        "name": cred.proxy.name,
                        "host": cred.proxy.host,
                        "port": cred.proxy.port,
                        "scheme": cred.proxy.scheme,
                    }
                else:
                    cred_dict["proxy_ref"] = None

                exported_credentials.append(cred_dict)

        # 2. Fetch Proxies if requested
        exported_proxies: List[Dict[str, Any]] = []
        if include_proxies:
            all_proxies_res = await db.execute(select(Proxy).order_by(Proxy.id.asc()))
            all_proxies = all_proxies_res.scalars().all()
            for prx in all_proxies:
                user = ""
                pwd = ""
                if prx.encrypted_username:
                    try:
                        user = decrypt_secret(prx.encrypted_username)
                    except Exception:
                        user = ""
                if prx.encrypted_password:
                    try:
                        pwd = decrypt_secret(prx.encrypted_password)
                    except Exception:
                        pwd = ""

                exported_proxies.append({
                    "name": prx.name,
                    "scheme": prx.scheme,
                    "host": prx.host,
                    "port": prx.port,
                    "username": user,
                    "password": pwd,
                    "enabled": prx.enabled,
                    "country": prx.country,
                    "country_code": prx.country_code,
                })

        # Collect distinct groups
        groups_set = set()
        for c in exported_credentials:
            if c.get("group_name"):
                groups_set.add(c["group_name"])

        payload_data = {
            "version": 1,
            "type": "myairouter_backup",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "providers_count": len(exported_providers),
                "credentials_count": len(exported_credentials),
                "proxies_count": len(exported_proxies),
                "groups": sorted(list(groups_set)),
            },
            "providers": exported_providers,
            "credentials": exported_credentials,
            "proxies": exported_proxies,
        }

        return encrypt_payload(payload_data, passphrase)

    @classmethod
    async def preview_import(
        cls,
        db: AsyncSession,
        raw_payload: dict,
        passphrase: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validates backup content and analyzes what will be created vs updated on this server.
        """
        data = await cls._validated_payload(db, raw_payload, passphrase)

        providers_list = data.get("providers", [])
        credentials_list = data.get("credentials", [])
        proxies_list = data.get("proxies", [])

        # Check existing providers in target DB
        slugs_in_backup = [p.get("slug") for p in providers_list if p.get("slug")]
        existing_prov_res = await db.execute(
            select(Provider).where(Provider.slug.in_(slugs_in_backup))
        )
        existing_provs = {p.slug: p for p in existing_prov_res.scalars().all()}

        # Check existing credentials in target DB
        existing_keys_count = 0
        providers_summary = []

        for p_data in providers_list:
            slug = p_data.get("slug", "")
            name = p_data.get("name", slug)
            keys_for_p = [c for c in credentials_list if c.get("provider_slug") == slug or not c.get("provider_slug") and c.get("provider_name") == name]
            exists = slug in existing_provs
            
            # Check duplicates among keys
            target_prov = existing_provs.get(slug)
            p_existing_keys = 0
            if target_prov:
                for c in keys_for_p:
                    raw_k = c.get("api_key", "").strip()
                    if raw_k and raw_k != "no-key":
                        fp = compute_fingerprint(raw_k)
                        dup_res = await db.execute(
                            select(ProviderCredential.id).where(
                                ProviderCredential.provider_id == target_prov.id,
                                ProviderCredential.key_fingerprint == fp,
                            )
                        )
                        if dup_res.scalar_one_or_none():
                            p_existing_keys += 1
                            existing_keys_count += 1

            providers_summary.append({
                "name": name,
                "slug": slug,
                "adapter_type": p_data.get("adapter_type", "generic_openai"),
                "base_url": p_data.get("base_url", ""),
                "keys_count": len(keys_for_p),
                "existing_keys_count": p_existing_keys,
                "exists_in_target": exists,
            })

        groups = sorted(list(set(
            c.get("group_name") for c in credentials_list if c.get("group_name")
        )))

        return {
            "valid": True,
            "exported_at": data.get("exported_at"),
            "total_providers": len(providers_list),
            "new_providers": sum(1 for p in providers_summary if not p["exists_in_target"]),
            "existing_providers": sum(1 for p in providers_summary if p["exists_in_target"]),
            "total_credentials": len(credentials_list),
            "existing_credentials": existing_keys_count,
            "new_credentials": len(credentials_list) - existing_keys_count,
            "total_proxies": len(proxies_list),
            "groups": groups,
            "providers_summary": providers_summary,
        }

    @classmethod
    async def import_data(
        cls,
        db: AsyncSession,
        raw_payload: dict,
        passphrase: Optional[str] = None,
        update_existing_providers: bool = True,
        skip_duplicate_credentials: bool = True,
        auto_discover_models: bool = True,
    ) -> Dict[str, Any]:
        """
        Imports providers and credentials into target server database.
        Re-encrypts all secrets with target server's secret master key.
        """
        data = await cls._validated_payload(db, raw_payload, passphrase)

        providers_list = data.get("providers", [])
        credentials_list = data.get("credentials", [])
        proxies_list = data.get("proxies", [])

        stats = {
            "success": True,
            "imported_providers": 0,
            "updated_providers": 0,
            "skipped_providers": 0,
            "imported_credentials": 0,
            "updated_credentials": 0,
            "skipped_credentials": 0,
            "imported_proxies": 0,
            "errors": [],
            "new_credential_ids": [],
        }

        # 1. Import Proxies
        proxy_id_map: Dict[Tuple[str, int], int] = {}
        proxy_name_map: Dict[str, int] = {}

        for prx_data in proxies_list:
            try:
                host = prx_data.get("host", "").strip()
                port = int(prx_data.get("port", 8080))
                name = prx_data.get("name", f"Proxy {host}:{port}")
                scheme = prx_data.get("scheme", "http")

                # Check if exists by host + port
                existing_prx_res = await db.execute(
                    select(Proxy).where(Proxy.host == host, Proxy.port == port)
                )
                existing_prx = existing_prx_res.scalar_one_or_none()

                if existing_prx:
                    proxy_id_map[(host, port)] = existing_prx.id
                    proxy_name_map[name] = existing_prx.id
                else:
                    enc_user = encrypt_secret(prx_data.get("username", "")) if prx_data.get("username") else None
                    enc_pwd = encrypt_secret(prx_data.get("password", "")) if prx_data.get("password") else None
                    new_prx = Proxy(
                        name=name,
                        scheme=scheme,
                        host=host,
                        port=port,
                        encrypted_username=enc_user,
                        encrypted_password=enc_pwd,
                        enabled=prx_data.get("enabled", True),
                        country=prx_data.get("country"),
                        country_code=prx_data.get("country_code"),
                        status="UNTESTED",
                    )
                    db.add(new_prx)
                    await db.flush()
                    proxy_id_map[(host, port)] = new_prx.id
                    proxy_name_map[name] = new_prx.id
                    stats["imported_proxies"] += 1
            except Exception as e:
                stats["errors"].append(f"Error importing proxy {prx_data.get('name')}: {type(e).__name__}")

        # 2. Import Providers
        provider_slug_map: Dict[str, int] = {}
        provider_name_map: Dict[str, int] = {}

        for p_data in providers_list:
            slug = p_data.get("slug", "").strip()
            name = p_data.get("name", slug).strip()
            if not slug:
                continue

            try:
                existing_p_res = await db.execute(
                    select(Provider).where(Provider.slug == slug)
                )
                existing_p = existing_p_res.scalar_one_or_none()

                if existing_p:
                    if update_existing_providers:
                        existing_p.name = name
                        existing_p.adapter_type = p_data.get("adapter_type", existing_p.adapter_type)
                        existing_p.base_url = p_data.get("base_url", existing_p.base_url)
                        existing_p.models_endpoint = p_data.get("models_endpoint", existing_p.models_endpoint)
                        existing_p.chat_endpoint = p_data.get("chat_endpoint", existing_p.chat_endpoint)
                        existing_p.responses_endpoint = p_data.get("responses_endpoint", existing_p.responses_endpoint)
                        existing_p.auth_type = p_data.get("auth_type", existing_p.auth_type)
                        existing_p.auth_header = p_data.get("auth_header", existing_p.auth_header)
                        existing_p.extra_headers = p_data.get("extra_headers", existing_p.extra_headers or {})

                        # Merge configuration (preserve existing folders and add new ones)
                        curr_cfg = existing_p.configuration or {}
                        new_cfg = p_data.get("configuration") or {}
                        merged_folders = list(set(
                            (curr_cfg.get("folders") or []) + (new_cfg.get("folders") or [])
                        ))
                        merged_cfg = {**curr_cfg, **new_cfg}
                        if merged_folders:
                            merged_cfg["folders"] = merged_folders
                        existing_p.configuration = merged_cfg

                        stats["updated_providers"] += 1
                    else:
                        stats["skipped_providers"] += 1

                    provider_slug_map[slug] = existing_p.id
                    provider_name_map[name] = existing_p.id
                else:
                    new_p = Provider(
                        name=name,
                        slug=slug,
                        adapter_type=p_data.get("adapter_type", "generic_openai"),
                        base_url=p_data.get("base_url", "https://api.openai.com/v1"),
                        models_endpoint=p_data.get("models_endpoint", "/models"),
                        chat_endpoint=p_data.get("chat_endpoint", "/chat/completions"),
                        responses_endpoint=p_data.get("responses_endpoint"),
                        enabled=p_data.get("enabled", True),
                        auth_type=p_data.get("auth_type", "bearer"),
                        auth_header=p_data.get("auth_header", "Authorization"),
                        extra_headers=p_data.get("extra_headers", {}),
                        configuration=p_data.get("configuration", {}),
                    )
                    db.add(new_p)
                    await db.flush()
                    provider_slug_map[slug] = new_p.id
                    provider_name_map[name] = new_p.id
                    stats["imported_providers"] += 1
            except Exception as e:
                stats["errors"].append(f"Error importing provider {name} ({slug}): {type(e).__name__}")

        # 3. Import Credentials
        for cred_data in credentials_list:
            try:
                p_slug = cred_data.get("provider_slug", "")
                p_name = cred_data.get("provider_name", "")
                target_pid = provider_slug_map.get(p_slug) if p_slug else provider_name_map.get(p_name)

                if not target_pid:
                    # Fallback lookup in DB
                    find_prov = await db.execute(
                        select(Provider.id).where(Provider.slug == p_slug if p_slug else Provider.name == p_name)
                    )
                    target_pid = find_prov.scalar_one_or_none()

                if not target_pid:
                    stats["errors"].append(f"Provider for key '{cred_data.get('name')}' not found (slug: {p_slug})")
                    continue

                raw_key = (cred_data.get("api_key") or "").strip()
                from app.services.credential_service import CredentialService
                target_provider = await db.get(Provider, target_pid)
                is_keyless = CredentialService._is_keyless(target_provider, raw_key)

                if not is_keyless:
                    fingerprint = compute_fingerprint(raw_key)
                    encrypted_key = encrypt_secret(raw_key)
                    masked = mask_secret(raw_key)
                else:
                    raw_key = "no-key"
                    fingerprint = f"keyless_{target_pid}_{uuid.uuid4().hex[:12]}"
                    encrypted_key = encrypt_secret("no-key")
                    masked = "(Keyless / No Auth)"

                # Check duplicate by target_pid + fingerprint
                dup_res = await db.execute(
                    select(ProviderCredential).where(
                        ProviderCredential.provider_id == target_pid,
                        ProviderCredential.key_fingerprint == fingerprint,
                    )
                )
                existing_cred = dup_res.scalar_one_or_none()

                if existing_cred:
                    if skip_duplicate_credentials:
                        stats["skipped_credentials"] += 1
                        continue
                    else:
                        # Update group or limits
                        if cred_data.get("group_name"):
                            existing_cred.group_name = cred_data["group_name"].strip()
                        existing_cred.priority = cred_data.get("priority", existing_cred.priority)
                        existing_cred.weight = cred_data.get("weight", existing_cred.weight)
                        existing_cred.rpm_limit = cred_data.get("rpm_limit", existing_cred.rpm_limit)
                        existing_cred.tpm_limit = cred_data.get("tpm_limit", existing_cred.tpm_limit)
                        existing_cred.max_concurrency = cred_data.get("max_concurrency", existing_cred.max_concurrency)
                        stats["updated_credentials"] += 1
                        continue

                # Resolve proxy
                resolved_prx_id = None
                prx_ref = cred_data.get("proxy_ref")
                if prx_ref and isinstance(prx_ref, dict):
                    h = prx_ref.get("host", "").strip()
                    p = int(prx_ref.get("port", 8080))
                    n = prx_ref.get("name", "")
                    resolved_prx_id = proxy_id_map.get((h, p)) or proxy_name_map.get(n)

                group = cred_data.get("group_name")
                new_cred = ProviderCredential(
                    provider_id=target_pid,
                    name=cred_data.get("name", "Imported Key"),
                    group_name=group.strip() if group and group.strip() else None,
                    encrypted_api_key=encrypted_key,
                    key_fingerprint=fingerprint,
                    masked_key=masked,
                    enabled=cred_data.get("enabled", True),
                    proxy_id=resolved_prx_id,
                    status="HEALTHY",
                    priority=cred_data.get("priority", 1),
                    weight=cred_data.get("weight", 1),
                    rpm_limit=cred_data.get("rpm_limit"),
                    tpm_limit=cred_data.get("tpm_limit"),
                    max_concurrency=cred_data.get("max_concurrency"),
                    consecutive_failures=0,
                    metadata_json=cred_data.get("metadata_json") or {},
                )
                db.add(new_cred)
                await db.flush()
                stats["imported_credentials"] += 1
                stats["new_credential_ids"].append(new_cred.id)

            except Exception as e:
                stats["errors"].append(f"Error importing key '{cred_data.get('name')}': {type(e).__name__}")

        if stats["errors"]:
            await db.rollback()
            stats["success"] = False
            for field in stats:
                if field.startswith(("imported_", "updated_")):
                    stats[field] = 0
            stats["new_credential_ids"] = []
            stats["discovery_triggered"] = False
            return stats
        await db.commit()

        # 4. Auto-discover models if requested
        if auto_discover_models and stats["new_credential_ids"]:
            try:
                from app.services.model_discovery_service import ModelDiscoveryService
                for cid in stats["new_credential_ids"]:
                    try:
                        await ModelDiscoveryService.fetch_models_for_credential(db, cid)
                    except Exception as exc:
                        stats["errors"].append(f"Model discovery failed for imported credential: {type(exc).__name__}")
                        await db.rollback()
                stats["discovery_triggered"] = True
            except Exception as exc:
                stats["errors"].append(f"Model discovery unavailable: {type(exc).__name__}")
                stats["discovery_triggered"] = False
        else:
            stats["discovery_triggered"] = False

        stats["success"] = not stats["errors"]
        stats["partial"] = bool(stats["errors"] and stats["new_credential_ids"])
        return stats
