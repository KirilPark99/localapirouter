import json
import base64
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app.models.entities import Provider, ProviderCredential, Proxy, DiscoveredModel, CredentialModelPreference
from app.schemas.entities import ProviderCreate, CredentialCreate, ProxyCreate
from pydantic import ValidationError
from app.core.crypto import encrypt_secret, decrypt_secret, compute_fingerprint, mask_secret

MIN_BACKUP_PASSPHRASE_LENGTH = 12
CREDENTIAL_SETTINGS = ('name', 'group_name', 'enabled', 'priority', 'weight', 'rpm_limit',
                       'tpm_limit', 'max_concurrency', 'quota_rules', 'notes', 'metadata_json')


def _require_passphrase(passphrase: Optional[str]) -> str:
    value = (passphrase or "").strip()
    if len(value) < MIN_BACKUP_PASSPHRASE_LENGTH:
        raise ValueError(f"Backup passphrase must contain at least {MIN_BACKUP_PASSPHRASE_LENGTH} characters")
    return value


def _derive_fernet_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_payload(data_dict: dict, passphrase: str) -> dict:
    """Encrypt the portable configuration, including its plaintext migration secrets."""
    passphrase = _require_passphrase(passphrase)
    salt = os.urandom(16)
    token = Fernet(_derive_fernet_key(passphrase, salt)).encrypt(
        json.dumps(data_dict, ensure_ascii=False, default=str).encode("utf-8"))
    return {'version': 1, 'type': 'myairouter_backup',
            'exported_at': datetime.now(timezone.utc).isoformat(), 'encrypted': True,
            'salt': base64.b64encode(salt).decode('ascii'), 'ciphertext': token.decode('ascii')}


def decrypt_payload(envelope: dict, passphrase: Optional[str] = None) -> dict:
    if not isinstance(envelope, dict):
        raise ValueError("Invalid backup data format (JSON object expected)")
    if envelope.get('encrypted') is not True:
        raise ValueError("Unencrypted backup files are not accepted")
    passphrase = _require_passphrase(passphrase)
    try:
        salt = base64.b64decode(envelope['salt'], validate=True)
        if len(salt) != 16:
            raise ValueError("Invalid backup salt")
        decrypted = Fernet(_derive_fernet_key(passphrase, salt)).decrypt(envelope['ciphertext'].encode('ascii'))
        return json.loads(decrypted.decode('utf-8'))
    except Exception:
        raise ValueError("Incorrect passphrase or corrupted encrypted backup file") from None


def _decrypt(encrypted):
    try:
        return decrypt_secret(encrypted)
    except Exception:
        raise ValueError("Cannot decrypt stored backup secret") from None


def _canonical_secret(raw):
    raw = raw.strip()
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    # Only structured module credentials are canonicalized, not JSON scalar API keys.
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) if isinstance(value, dict) else raw


def _portable_metadata(metadata, raw):
    try:
        fields = json.loads(raw)
    except ValueError:
        fields = {}
    secret_keys = {'api_key', 'apiKey', 'key', 'password', 'token', 'token_v2', 'user_token',
                   'access_token', 'refresh_token', 'id_token', 'auth_json', 'cookie', 'cookies', 'local_storage'}
    if isinstance(fields, dict):
        secret_keys.update(fields)

    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()
                    if k not in secret_keys and not k.startswith('_file_')
                    and not (k == '_source' and v == 'file')}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    # Unknown configuration/metadata fields survive; credential copies and local ownership do not.
    return clean(metadata)


def _proxy_key(value):
    return value['scheme'], value['host'].strip(), value['port']


class BackupService:
    @classmethod
    async def _duplicate(cls, db, provider_id, raw):
        candidates = (await db.scalars(select(ProviderCredential).where(
            ProviderCredential.provider_id == provider_id).order_by(ProviderCredential.id))).all()
        canonical = _canonical_secret(raw)
        # ponytail: scan a provider's profiles; index canonical fingerprints if this becomes large.
        decrypted = [(candidate, _canonical_secret(_decrypt(candidate.encrypted_api_key))) for candidate in candidates]
        return next((candidate for candidate, secret in decrypted if secret == canonical), None)

    @classmethod
    async def _validated_payload(cls, db: AsyncSession, envelope: dict, passphrase: Optional[str]) -> dict:
        def check_header(value):
            if (not isinstance(value, dict) or value.get('type') != 'myairouter_backup'
                    or type(value.get('version')) is not int or value['version'] != 1):
                raise ValueError("Unsupported backup type or version")
        check_header(envelope)
        data = decrypt_payload(envelope, passphrase)
        check_header(data)
        for field, schema in (('providers', ProviderCreate), ('credentials', CredentialCreate), ('proxies', ProxyCreate)):
            entries = data.get(field, [])
            if not isinstance(entries, list) or any(not isinstance(item, dict) for item in entries):
                raise ValueError(f"Backup {field} must be an array of objects")
            normalized = []
            for item in entries:
                try:
                    checked = schema.model_validate({**item, 'provider_id': 1} if field == 'credentials' else item)
                except ValidationError:
                    raise ValueError(f"Invalid backup {field} structure") from None
                # Retain unknown fields in JSON containers and backup-only references, not ORM kwargs.
                normalized.append({**item, **checked.model_dump(mode='json', exclude_unset=True)})
            data[field] = normalized
        slugs = [p['slug'] for p in data['providers']]
        if any(not s or s != s.strip() for s in slugs) or len(slugs) != len(set(slugs)):
            raise ValueError("Backup provider slugs must be nonempty and unique")
        for proxy in data['proxies']:
            proxy.setdefault('scheme', 'http')
            if not proxy['host'].strip() or not 1 <= proxy['port'] <= 65535:
                raise ValueError("Invalid backup proxy address")
        for credential in data['credentials']:
            slug, name = credential.get('provider_slug'), credential.get('provider_name')
            if slug is not None and not isinstance(slug, str) or name is not None and not isinstance(name, str):
                raise ValueError("Invalid credential provider reference")
            if slug:
                known = slug in slugs or await db.scalar(select(Provider.id).where(Provider.slug == slug)) is not None
            elif name:
                count = sum(p['name'] == name for p in data['providers'])
                existing = list((await db.scalars(select(Provider.id).where(Provider.name == name))).all()) if not count else []
                known = count == 1 or not count and len(existing) == 1
                if count == 1:
                    credential['provider_slug'] = next(p['slug'] for p in data['providers'] if p['name'] == name)
            else:
                known = False
            if not known:
                raise ValueError("Credential references an unknown or ambiguous provider")
            if 'enabled' in credential and type(credential['enabled']) is not bool:
                raise ValueError("Credential enabled must be a boolean")
            metadata = credential.get('metadata_json', {})
            if not isinstance(metadata, dict):
                raise ValueError("Credential metadata must be an object")
            credential['metadata_json'] = _portable_metadata(metadata, credential['api_key'])
            reference = credential.get('proxy_ref')
            if reference is not None:
                try:
                    reference = ProxyCreate.model_validate(reference).model_dump(mode='json')
                except ValidationError:
                    raise ValueError("Invalid credential proxy reference") from None
                if not any(_proxy_key(p) == _proxy_key(reference) for p in data['proxies']):
                    raise ValueError("Credential references a proxy missing from the backup")
                credential['proxy_ref'] = reference
            preferences = credential.get('model_preferences', [])
            if not isinstance(preferences, list):
                raise ValueError("Model preferences must be an array")
            refs = []
            for pref in preferences:
                if (not isinstance(pref, dict) or any(not isinstance(pref.get(k), str) or not pref[k].strip()
                        for k in ('canonical_slug', 'provider_model_id', 'display_name'))
                        or type(pref.get('priority_order', 0)) is not int):
                    raise ValueError("Invalid portable model preference")
                refs.append((pref['canonical_slug'], pref['provider_model_id']))
            if len(refs) != len(set(refs)):
                raise ValueError("Duplicate model preference")
        return data

    @classmethod
    async def export_data(cls, db: AsyncSession, provider_ids: Optional[List[int]] = None,
                          include_proxies: bool = True, *, passphrase: str) -> Dict[str, Any]:
        _require_passphrase(passphrase)
        query = select(Provider).options(
            selectinload(Provider.credentials).selectinload(ProviderCredential.proxy),
            selectinload(Provider.credentials).selectinload(ProviderCredential.model_preferences)
            .selectinload(CredentialModelPreference.model)).order_by(Provider.id).execution_options(populate_existing=True)
        if provider_ids:
            query = query.where(Provider.id.in_(provider_ids))
        providers, credentials, proxies = [], [], []
        for provider in (await db.scalars(query)).all():
            providers.append({field: getattr(provider, field) for field in ProviderCreate.model_fields})
            for credential in provider.credentials:
                raw = _decrypt(credential.encrypted_api_key)
                item = {field: getattr(credential, field) for field in CREDENTIAL_SETTINGS}
                item.update(provider_slug=provider.slug, provider_name=provider.name, api_key=raw,
                            metadata_json=_portable_metadata(credential.metadata_json or {}, raw),
                            proxy_ref=None,
                            model_preferences=[{'canonical_slug': pref.model.canonical_slug,
                                'provider_model_id': pref.model.provider_model_id,
                                'display_name': pref.model.display_name, 'priority_order': pref.priority_order}
                                for pref in credential.model_preferences])
                if include_proxies and credential.proxy:
                    item['proxy_ref'] = {field: getattr(credential.proxy, field) for field in ('name', 'scheme', 'host', 'port')}
                credentials.append(item)
        if include_proxies:
            for proxy in (await db.scalars(select(Proxy).order_by(Proxy.id))).all():
                item = {field: getattr(proxy, field) for field in ProxyCreate.model_fields if field not in ('username', 'password')}
                item.update(username=_decrypt(proxy.encrypted_username), password=_decrypt(proxy.encrypted_password))
                proxies.append(item)
        return encrypt_payload({'version': 1, 'type': 'myairouter_backup',
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'metadata': {'providers_count': len(providers), 'credentials_count': len(credentials),
                         'proxies_count': len(proxies), 'groups': sorted({c['group_name'] for c in credentials if c['group_name']})},
            'providers': providers, 'credentials': credentials, 'proxies': proxies}, passphrase)

    @classmethod
    async def preview_import(cls, db: AsyncSession, raw_payload: dict,
                             passphrase: Optional[str] = None) -> Dict[str, Any]:
        data = await cls._validated_payload(db, raw_payload, passphrase)
        summary, existing_count = [], 0
        for provider in data['providers']:
            target = await db.scalar(select(Provider).where(Provider.slug == provider['slug']))
            credentials = [c for c in data['credentials'] if c.get('provider_slug') == provider['slug']
                           or not c.get('provider_slug') and c.get('provider_name') == provider['name']]
            count = 0
            if target:
                for credential in credentials:
                    if await cls._duplicate(db, target.id, credential['api_key']):
                        count += 1
            existing_count += count
            summary.append({'name': provider['name'], 'slug': provider['slug'],
                            'adapter_type': provider['adapter_type'], 'base_url': provider['base_url'],
                            'keys_count': len(credentials), 'existing_keys_count': count,
                            'exists_in_target': target is not None})
        # Legacy backups may refer to providers already in the target but not in the backup.
        for credential in data['credentials']:
            if any(credential.get('provider_slug') == p['slug'] or not credential.get('provider_slug')
                   and credential.get('provider_name') == p['name'] for p in data['providers']):
                continue
            target = await db.scalar(select(Provider).where(Provider.slug == credential['provider_slug']
                if credential.get('provider_slug') else Provider.name == credential['provider_name']))
            if await cls._duplicate(db, target.id, credential['api_key']):
                existing_count += 1
        return {'valid': True, 'exported_at': data.get('exported_at'),
                'total_providers': len(summary), 'new_providers': sum(not p['exists_in_target'] for p in summary),
                'existing_providers': sum(p['exists_in_target'] for p in summary),
                'total_credentials': len(data['credentials']), 'existing_credentials': existing_count,
                'new_credentials': len(data['credentials']) - existing_count, 'total_proxies': len(data['proxies']),
                'groups': sorted({c['group_name'] for c in data['credentials'] if c.get('group_name')}),
                'providers_summary': summary}

    @classmethod
    async def import_data(cls, db: AsyncSession, raw_payload: dict, passphrase: Optional[str] = None,
                          update_existing_providers: bool = True, skip_duplicate_credentials: bool = True,
                          auto_discover_models: bool = True) -> Dict[str, Any]:
        data = await cls._validated_payload(db, raw_payload, passphrase)
        stats = {'success': True, 'imported_providers': 0, 'updated_providers': 0, 'skipped_providers': 0,
                 'imported_credentials': 0, 'updated_credentials': 0, 'skipped_credentials': 0,
                 'imported_proxies': 0, 'errors': [], 'new_credential_ids': []}
        from app.services.credential_service import CredentialService
        try:
            # Encrypt every migration secret before the first write; errors abort the entire import.
            encrypted_proxies = [(encrypt_secret(p.get('username') or ''), encrypt_secret(p.get('password') or ''))
                                 for p in data['proxies']]
            # Validate keyless policy and decrypt target credentials before the first write.
            encrypted_keys = []
            for item in data['credentials']:
                target = await db.scalar(select(Provider).where(Provider.slug == item['provider_slug']
                    if item.get('provider_slug') else Provider.name == item['provider_name']))
                incoming = next((p for p in data['providers'] if p['slug'] == item.get('provider_slug')
                    or not item.get('provider_slug') and p['name'] == item.get('provider_name')), None)
                effective = target
                if incoming is not None and (target is None or update_existing_providers):
                    effective = Provider(**ProviderCreate.model_validate(incoming).model_dump())
                raw = item['api_key'].strip()
                allows_keyless = CredentialService._is_keyless(effective, raw)
                if allows_keyless and raw.lower() in ('no-key', 'none', 'empty', 'keyless', ''):
                    raw = 'no-key'
                if target is not None:
                    await cls._duplicate(db, target.id, raw)
                encrypted_keys.append((raw, encrypt_secret(raw)))
            proxy_map = {}
            for item, (username, password) in zip(data['proxies'], encrypted_proxies):
                scheme, host, port = _proxy_key(item)
                proxy = await db.scalar(select(Proxy).where(Proxy.scheme == scheme, Proxy.host == host, Proxy.port == port))
                if proxy is None:
                    proxy = Proxy(name=item['name'], scheme=scheme, host=host, port=port, status='UNTESTED')
                    db.add(proxy)
                    stats['imported_proxies'] += 1
                for field in ('name', 'enabled', 'country', 'country_code'):
                    if field in item:
                        setattr(proxy, field, item[field])
                proxy.encrypted_username, proxy.encrypted_password = username or None, password or None
                await db.flush()
                proxy_map[(scheme, host, port)] = proxy.id
            for item in data['providers']:
                provider = await db.scalar(select(Provider).where(Provider.slug == item['slug']))
                values = {k: v for k, v in item.items() if k in ProviderCreate.model_fields}
                if provider is None:
                    db.add(Provider(**values))
                    stats['imported_providers'] += 1
                elif update_existing_providers:
                    for field, value in values.items():
                        if field == 'configuration':
                            current = provider.configuration or {}
                            value = {**current, **value}
                            folders = list(dict.fromkeys((current.get('folders') or []) + (value.get('folders') or [])))
                            if folders:
                                value['folders'] = folders
                        setattr(provider, field, value)
                    stats['updated_providers'] += 1
                else:
                    stats['skipped_providers'] += 1
                await db.flush()
            for item, (raw, encrypted) in zip(data['credentials'], encrypted_keys):
                provider = await db.scalar(select(Provider).where(Provider.slug == item['provider_slug']
                    if item.get('provider_slug') else Provider.name == item['provider_name']))
                keyless = raw == 'no-key'
                credential = await cls._duplicate(db, provider.id, raw)
                if credential is not None and skip_duplicate_credentials:
                    stats['skipped_credentials'] += 1
                    continue
                new = credential is None
                if credential is None:
                    credential = ProviderCredential(provider_id=provider.id, name=item['name'],
                        encrypted_api_key=encrypted, key_fingerprint=compute_fingerprint(raw),
                        masked_key='(Keyless / No Auth)' if keyless else mask_secret(raw),
                        status='HEALTHY', consecutive_failures=0)
                    db.add(credential)
                local_source = {k: v for k, v in (credential.metadata_json or {}).items()
                    if k.startswith('_file_') or k == '_source' and v == 'file'}
                for field in CREDENTIAL_SETTINGS:
                    if field in item and field != 'quota_rules':
                        setattr(credential, field, item[field])
                if 'quota_rules' in item:
                    from app.services.api_key_service import ApiKeyService
                    credential.quota_rules = ApiKeyService._restore_credential_rules(item['quota_rules'], credential.quota_rules or [])
                if not new and local_source:
                    from app.modules.profile_loader import mark_profile_db_owned
                    credential.metadata_json = {**(credential.metadata_json or {}), **local_source}
                    mark_profile_db_owned(credential)
                if 'proxy_ref' in item:
                    credential.proxy_id = proxy_map[_proxy_key(item['proxy_ref'])] if item['proxy_ref'] else None
                await db.flush()
                if 'model_preferences' in item:
                    await db.execute(delete(CredentialModelPreference).where(CredentialModelPreference.credential_id == credential.id))
                    for preference in item['model_preferences']:
                        model = await db.scalar(select(DiscoveredModel).where(DiscoveredModel.provider_id == provider.id,
                            DiscoveredModel.canonical_slug == preference['canonical_slug'],
                            DiscoveredModel.provider_model_id == preference['provider_model_id'])
                            .order_by((DiscoveredModel.credential_id == credential.id).desc(), DiscoveredModel.id).limit(1))
                        if model is None:
                            model = DiscoveredModel(provider_id=provider.id, credential_id=credential.id,
                                provider_model_id=preference['provider_model_id'], canonical_slug=preference['canonical_slug'],
                                display_name=preference['display_name'])
                            db.add(model)
                            await db.flush()
                        db.add(CredentialModelPreference(credential_id=credential.id, model_id=model.id,
                            priority_order=preference.get('priority_order', 0)))
                stats['imported_credentials' if new else 'updated_credentials'] += 1
                if new:
                    stats['new_credential_ids'].append(credential.id)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            stats['success'] = False
            stats['errors'].append(f"Configuration import failed: {type(exc).__name__}")
            for field in stats:
                if field.startswith(('imported_', 'updated_')):
                    stats[field] = 0
            stats['new_credential_ids'] = []
            stats['discovery_triggered'] = False
            return stats
        if auto_discover_models and stats['new_credential_ids']:
            try:
                from app.services.model_discovery_service import ModelDiscoveryService
                for cid in stats['new_credential_ids']:
                    try:
                        await ModelDiscoveryService.fetch_models_for_credential(db, cid)
                    except Exception as exc:
                        stats['errors'].append(f"Model discovery failed for imported credential: {type(exc).__name__}")
                        await db.rollback()
                stats['discovery_triggered'] = True
            except Exception as exc:
                stats['errors'].append(f"Model discovery unavailable: {type(exc).__name__}")
                stats['discovery_triggered'] = False
        else:
            stats['discovery_triggered'] = False
        stats['success'] = not stats['errors']
        stats['partial'] = bool(stats['errors'] and stats['new_credential_ids'])
        return stats
