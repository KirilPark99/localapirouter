"""Synthetic, isolated regressions for portable encrypted configuration backups."""
import json
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.database import Base
from app.core.crypto import encrypt_secret, decrypt_secret, compute_fingerprint
from app.models.entities import (Provider, ProviderCredential, Proxy, DiscoveredModel,
                                 CredentialModelPreference)
from app.services.backup_service import BackupService, encrypt_payload, decrypt_payload

PASSPHRASE = 'synthetic-backup-passphrase'
AUTH = {'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh',
        'auth_json': '{"tokens":{"id_token":"synthetic-id"}}',
        'cookies': 'synthetic-cookie', 'future_field': {'opaque': 'synthetic-value'}}
RULES = [{'scope': 'model', 'model': 'synthetic/model', 'period': 'day', 'requests': 7}]
METADATA = {'model_limits': {'synthetic/model': {'rpm': 4}}, 'future_setting': {'on': True}}


def envelope(**changes):
    data = {'version': 1, 'type': 'myairouter_backup', 'providers': [], 'credentials': [], 'proxies': []}
    data.update(changes)
    return encrypt_payload(data, PASSPHRASE)


@asynccontextmanager
async def private_db():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            yield db
    finally:
        await engine.dispose()


async def seed(db, keyless=False):
    proxy = Proxy(name='synthetic proxy', host='fixture.invalid', port=8080, scheme='socks5h',
                  encrypted_username=encrypt_secret('synthetic-user'),
                  encrypted_password=encrypt_secret('synthetic-password'), enabled=False,
                  country='Synthetic', country_code='XX')
    provider = Provider(name='synthetic module', slug='module-synthetic', adapter_type='custom_module',
                        base_url='module://synthetic', enabled=False, notes='provider note',
                        auth_type='none' if keyless else 'bearer',
                        configuration={'module_id': 'synthetic', 'future': {'on': True}, 'folders': ['A']},
                        extra_headers={'X-Synthetic': 'setting'})
    db.add_all([proxy, provider])
    await db.flush()
    raw = 'no-key' if keyless else json.dumps(AUTH)
    credential = ProviderCredential(provider_id=provider.id, name='synthetic profile',
        encrypted_api_key=encrypt_secret(raw), key_fingerprint=compute_fingerprint('legacy-module-' + uuid.uuid4().hex),
        masked_key='synthetic', enabled=False, group_name='Group', priority=3, weight=4,
        rpm_limit=11, tpm_limit=22, max_concurrency=2, quota_rules=RULES, notes='credential note',
        proxy_id=proxy.id, metadata_json={**METADATA, **({} if keyless else AUTH),
        '_source': 'file', '_file_path': 'unrelated/profile.yaml', '_file_profile_key': 'machine:key'})
    db.add(credential)
    await db.flush()
    model = DiscoveredModel(provider_id=provider.id, credential_id=credential.id,
        provider_model_id='model', display_name='Synthetic model', canonical_slug='synthetic/model')
    db.add(model)
    await db.flush()
    db.add(CredentialModelPreference(credential_id=credential.id, model_id=model.id, priority_order=3))
    await db.commit()
    return provider, credential, proxy


@pytest.mark.asyncio
@pytest.mark.parametrize('changes', [{'version': 999}, {'version': True}, {'type': 'other'},
    {'providers': {}}, {'credentials': [{'name': 'orphan', 'provider_slug': 'missing', 'api_key': 'synthetic'}]},
    {'credentials': [{'name': 'badshape', 'api_key': 17}]}])
async def test_invalid_backup_rejected_before_any_write(changes):
    async with private_db() as db:
        with pytest.raises(ValueError):
            await BackupService.preview_import(db, envelope(**changes), PASSPHRASE)
        with pytest.raises(ValueError):
            await BackupService.import_data(db, envelope(**changes), PASSPHRASE, auto_discover_models=False)
        assert await db.scalar(select(func.count(ProviderCredential.id))) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['fresh', 'skip', 'update'])
@pytest.mark.parametrize('keyless', [False, True])
async def test_complete_roundtrip_legacy_module_fingerprint(mode, keyless):
    async with private_db() as source, private_db() as target:
        provider, credential, proxy = await seed(source, keyless)
        backup = await BackupService.export_data(source, passphrase=PASSPHRASE)
        payload = decrypt_payload(backup, PASSPHRASE)
        exported = payload['credentials'][0]
        assert exported['quota_rules'] == RULES and exported['notes'] == credential.notes
        assert exported['metadata_json'] == METADATA
        assert payload['providers'][0]['notes'] == provider.notes
        if not keyless:
            # JSON ordering/spacing is not credential identity.
            exported['api_key'] = json.dumps(AUTH, sort_keys=True, separators=(',', ':'))
        backup = encrypt_payload(payload, PASSPHRASE)
        db = target if mode == 'fresh' else source
        if mode != 'fresh':
            preview = await BackupService.preview_import(db, backup, PASSPHRASE)
            assert preview['existing_credentials'] == 1 and preview['new_credentials'] == 0
        if mode == 'update':
            provider.enabled = True
            provider.notes = 'old'
            credential.enabled = True
            credential.group_name = 'old'
            credential.notes = 'old'
            credential.metadata_json = {'old': True}
            credential.quota_rules = []
            credential.proxy_id = None
            proxy.enabled = True
            proxy.encrypted_password = encrypt_secret('old-synthetic-password')
            await db.commit()
        stats = await BackupService.import_data(db, backup, PASSPHRASE,
            skip_duplicate_credentials=mode != 'update', auto_discover_models=False)
        assert stats['success'] and not stats['errors']
        assert stats[{'fresh': 'imported_credentials', 'skip': 'skipped_credentials', 'update': 'updated_credentials'}[mode]] == 1
        assert await db.scalar(select(func.count(ProviderCredential.id))) == 1
        actual = await db.scalar(select(ProviderCredential))
        await db.refresh(actual)
        actual_provider = await db.get(Provider, actual.provider_id)
        assert actual_provider.enabled is False and actual_provider.notes == 'provider note'
        for field, value in payload['providers'][0].items():
            assert getattr(actual_provider, field) == value
        assert await db.scalar(select(func.count(Provider.id))) == 1
        assert await db.scalar(select(func.count(Proxy.id))) == 1
        assert await db.scalar(select(func.count(DiscoveredModel.id))) == 1
        assert actual.enabled is False and actual.group_name == 'Group'
        assert [{k: rule[k] for k in expected} for rule, expected in zip(actual.quota_rules, RULES)] == RULES
        assert actual.notes == 'credential note' and len(actual.quota_rules) == len(RULES)
        if mode != 'skip':
            from app.services.quota_service import QuotaService
            usage = await QuotaService.usage(db, actual)
            assert len(usage[0]['rule_id']) == 32 and usage[0]['remaining']['requests'] == 7
        assert (actual.priority, actual.weight, actual.rpm_limit, actual.tpm_limit, actual.max_concurrency) == (3, 4, 11, 22, 2)
        if mode != 'skip':
            assert actual.metadata_json == METADATA
        else:
            assert actual.metadata_json['_source'] == 'file'  # explicit skip leaves row untouched
        raw = decrypt_secret(actual.encrypted_api_key)
        assert raw == 'no-key' if keyless else json.loads(raw) == AUTH
        restored_proxy = await db.get(Proxy, actual.proxy_id)
        assert restored_proxy.enabled is False
        assert decrypt_secret(restored_proxy.encrypted_password) == 'synthetic-password'
        preferences = list((await db.scalars(select(CredentialModelPreference).where(CredentialModelPreference.credential_id == actual.id))).all())
        assert len(preferences) == 1 and preferences[0].priority_order == 3
        model = await db.get(DiscoveredModel, preferences[0].model_id)
        assert model.canonical_slug == 'synthetic/model'
        # Second import is idempotent, including imported raw fingerprints.
        again = await BackupService.import_data(db, backup, PASSPHRASE, auto_discover_models=False)
        assert again['skipped_credentials'] == 1 and again['imported_credentials'] == 0


@pytest.mark.asyncio
async def test_without_proxies_has_no_dangling_reference():
    async with private_db() as source, private_db() as target:
        await seed(source)
        backup = await BackupService.export_data(source, include_proxies=False, passphrase=PASSPHRASE)
        data = decrypt_payload(backup, PASSPHRASE)
        assert data['proxies'] == [] and data['credentials'][0]['proxy_ref'] is None
        stats = await BackupService.import_data(target, backup, PASSPHRASE, auto_discover_models=False)
        assert stats['success']
        assert (await target.scalar(select(ProviderCredential))).proxy_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['encrypted_api_key', 'encrypted_username', 'encrypted_password'])
async def test_export_fails_closed_on_corrupt_secret(field):
    async with private_db() as db:
        _, credential, proxy = await seed(db)
        setattr(credential if field == 'encrypted_api_key' else proxy, field, 'invalid-synthetic-ciphertext')
        await db.commit()
        with pytest.raises(ValueError, match='decrypt'):
            await BackupService.export_data(db, passphrase=PASSPHRASE)


@pytest.mark.asyncio
async def test_invalid_partial_import_rolls_back_and_valid_import_works():
    providers = [{'slug': 'synthetic', 'name': 'synthetic', 'adapter_type': 'openai', 'base_url': 'https://fixture.invalid'}]
    async with private_db() as db:
        bad = envelope(providers=providers, credentials=[
            {'name': 'first', 'provider_slug': 'synthetic', 'api_key': 'synthetic-valid'},
            {'name': 'invalid', 'provider_slug': 'synthetic', 'api_key': ''}])
        stats = await BackupService.import_data(db, bad, PASSPHRASE, auto_discover_models=False)
        assert not stats['success'] and stats['errors'] and not stats['imported_credentials']
        assert await db.scalar(select(func.count(Provider.id))) == 0
        assert await db.scalar(select(func.count(ProviderCredential.id))) == 0
        good = envelope(providers=providers, credentials=[{'name': 'valid', 'provider_slug': 'synthetic', 'api_key': 'synthetic-valid'}])
        stats = await BackupService.import_data(db, good, PASSPHRASE, auto_discover_models=False)
        assert stats['success'] and stats['imported_credentials'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('enabled', {}), ('metadata_json', []),
    ('quota_rules', [{'scope': 'key', 'requests': -1}]), ('model_preferences', [{'canonical_slug': 7}]),
    ('proxy_ref', {'name': 'missing', 'host': 'missing.invalid', 'port': 12})])
async def test_backup_only_fields_validated_before_write(field, value):
    async with private_db() as source, private_db() as target:
        await seed(source)
        data = decrypt_payload(await BackupService.export_data(source, passphrase=PASSPHRASE), PASSPHRASE)
        data['credentials'][0][field] = value
        with pytest.raises(ValueError):
            await BackupService.import_data(target, encrypt_payload(data, PASSPHRASE), PASSPHRASE, auto_discover_models=False)
        assert await target.scalar(select(func.count(Provider.id))) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('shared_model', [False, True])
async def test_update_clears_settings_and_reuses_provider_model(shared_model):
    async with private_db() as db:
        provider, credential, _ = await seed(db)
        model = await db.scalar(select(DiscoveredModel))
        if shared_model:
            model.credential_id = None
            await db.commit()
        data = decrypt_payload(await BackupService.export_data(db, passphrase=PASSPHRASE), PASSPHRASE)
        data['credentials'][0].update(group_name=None, notes=None, rpm_limit=None, tpm_limit=None,
            max_concurrency=None, quota_rules=[], proxy_ref=None, metadata_json={'future_setting': {'new': True}})
        stats = await BackupService.import_data(db, encrypt_payload(data, PASSPHRASE), PASSPHRASE,
            skip_duplicate_credentials=False, update_existing_providers=False, auto_discover_models=False)
        assert stats['success'] and stats['updated_credentials'] == 1 and stats['skipped_providers'] == 1
        await db.refresh(credential)
        assert credential.group_name is None and credential.notes is None and credential.proxy_id is None
        assert credential.rpm_limit is None and credential.tpm_limit is None and credential.max_concurrency is None
        assert credential.quota_rules == []
        assert credential.metadata_json == {'future_setting': {'new': True}, '_source':'file',
            '_file_path':'unrelated/profile.yaml', '_file_profile_key':'machine:key', '_file_db_owned':True}
        assert await db.scalar(select(func.count(DiscoveredModel.id))) == 1
        assert await db.scalar(select(func.count(CredentialModelPreference.id))) == 1


@pytest.mark.asyncio
async def test_fingerprint_is_not_proof_of_duplicate_and_no_auth_keeps_json():
    async with private_db() as db:
        provider, credential, _ = await seed(db)
        provider.auth_type = 'none'
        await db.commit()
        data = decrypt_payload(await BackupService.export_data(db, passphrase=PASSPHRASE), PASSPHRASE)
        different = {**AUTH, 'access_token': 'synthetic-other-access'}
        data['credentials'][0]['api_key'] = json.dumps(different)
        credential.key_fingerprint = compute_fingerprint(json.dumps(different))
        await db.commit()
        backup = encrypt_payload(data, PASSPHRASE)
        preview = await BackupService.preview_import(db, backup, PASSPHRASE)
        assert preview['new_credentials'] == 1
        stats = await BackupService.import_data(db, backup, PASSPHRASE, auto_discover_models=False)
        assert stats['success'] and stats['imported_credentials'] == 1
        imported = await db.get(ProviderCredential, stats['new_credential_ids'][0])
        assert json.loads(decrypt_secret(imported.encrypted_api_key)) == different
        assert json.loads(decrypt_secret(credential.encrypted_api_key)) == AUTH
        exported = decrypt_payload(await BackupService.export_data(db, passphrase=PASSPHRASE), PASSPHRASE)
        assert len(exported['credentials']) == 2


@pytest.mark.asyncio
async def test_provider_name_reference_uses_backup_slug_not_unrelated_target():
    async with private_db() as db:
        unrelated = Provider(name='same name', slug='unrelated', adapter_type='openai', base_url='https://fixture.invalid')
        db.add(unrelated)
        await db.commit()
        backup = envelope(providers=[{'name': 'same name', 'slug': 'incoming', 'adapter_type': 'openai',
            'base_url': 'https://fixture.invalid'}], credentials=[{'name': 'synthetic',
            'provider_name': 'same name', 'api_key': 'synthetic-valid'}])
        stats = await BackupService.import_data(db, backup, PASSPHRASE, auto_discover_models=False)
        assert stats['success'] and stats['imported_credentials'] == 1
        credential = await db.get(ProviderCredential, stats['new_credential_ids'][0])
        assert (await db.get(Provider, credential.provider_id)).slug == 'incoming'


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['encrypt', 'decrypt', 'flush'])
async def test_secret_or_write_failure_is_atomic(monkeypatch, failure):
    from app.services import backup_service
    async with private_db() as source, private_db() as target:
        await seed(source)
        backup = await BackupService.export_data(source, passphrase=PASSPHRASE)
        if failure == 'decrypt':
            _, credential, _ = await seed(target)
            credential.encrypted_api_key = 'invalid-synthetic-ciphertext'
            await target.commit()
        before = [await target.scalar(select(func.count(model.id))) for model in (Provider, ProviderCredential, Proxy)]
        if failure == 'encrypt':
            original = backup_service.encrypt_secret
            calls = 0
            def fail_later(raw):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise ValueError('synthetic failure')
                return original(raw)
            monkeypatch.setattr(backup_service, 'encrypt_secret', fail_later)
        elif failure == 'flush':
            original = target.flush
            calls = 0
            async def fail_flush(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise ValueError('synthetic failure')
                return await original(*args, **kwargs)
            monkeypatch.setattr(target, 'flush', fail_flush)
        stats = await BackupService.import_data(target, backup, PASSPHRASE, auto_discover_models=False)
        assert not stats['success'] and stats['errors'] and stats['new_credential_ids'] == []
        assert stats['imported_credentials'] == stats['imported_providers'] == stats['imported_proxies'] == 0
        after = [await target.scalar(select(func.count(model.id))) for model in (Provider, ProviderCredential, Proxy)]
        assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize('corruption', ['wrong_passphrase', 'tamper', 'plaintext'])
async def test_envelope_failure_never_writes(corruption):
    async with private_db() as source, private_db() as target:
        await seed(source)
        backup = await BackupService.export_data(source, passphrase=PASSPHRASE)
        password = PASSPHRASE
        if corruption == 'wrong_passphrase':
            password = 'wrong-synthetic-passphrase'
        elif corruption == 'tamper':
            backup['ciphertext'] = 'invalid-synthetic-ciphertext'
        else:
            backup = decrypt_payload(backup, PASSPHRASE)
        with pytest.raises(ValueError):
            await BackupService.import_data(target, backup, password, auto_discover_models=False)
        assert await target.scalar(select(func.count(Provider.id))) == 0


@pytest.mark.asyncio
async def test_legacy_existing_provider_name_reference_and_quota_dates():
    async with private_db() as db:
        provider, credential, _ = await seed(db)
        data = decrypt_payload(await BackupService.export_data(db, passphrase=PASSPHRASE), PASSPHRASE)
        data['providers'] = []
        item = data['credentials'][0]
        del item['provider_slug']
        item['quota_rules'] = [{'id': 'a' * 32, 'scope': 'key', 'requests': 3,
            'period': 'custom', 'duration_seconds': 60, 'anchor': '2026-10-09T00:00:00Z'}]
        backup = encrypt_payload(data, PASSPHRASE)
        preview = await BackupService.preview_import(db, backup, PASSPHRASE)
        assert preview['existing_credentials'] == 1 and preview['new_credentials'] == 0
        stats = await BackupService.import_data(db, backup, PASSPHRASE,
            skip_duplicate_credentials=False, auto_discover_models=False)
        assert stats['success'] and stats['updated_credentials'] == 1
        await db.refresh(credential)
        assert len(credential.quota_rules[0]['id']) == 32 and credential.quota_rules[0]['id'] != 'a' * 32
        from app.services.quota_service import QuotaService
        assert (await QuotaService.usage(db, credential))[0]['remaining']['requests'] == 3
        assert credential.quota_rules[0]['anchor'] == '2026-10-09T00:00:00Z'
