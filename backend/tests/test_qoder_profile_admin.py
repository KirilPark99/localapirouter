"""Qoder account CRUD/rotation boundary with synthetic DB, no native login."""
import json
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from app.api.admin import modules
from app.api.deps import get_current_admin
from app.core.crypto import encrypt_secret, decrypt_secret
from app.core.database import AsyncSessionLocal
from app.models.entities import Provider, ProviderCredential, Proxy
from app.modules.base import ModuleManifest
from app.modules.loader import LoadedModule, ModuleLoader
from app.services.credential_service import CredentialService


@pytest.mark.asyncio
async def test_qoder_profiles_require_actual_auth_and_keep_pat_encrypted(monkeypatch):
    manifest = ModuleManifest.model_validate_json((Path(__file__).parents[1] / 'modules/qoder/manifest.json').read_text())
    monkeypatch.setattr(ModuleLoader, '_modules', {'qoder': LoadedModule(manifest=manifest)})
    async with AsyncSessionLocal() as db:
        provider = Provider(name='Qoder fixture', slug='module_qoder', adapter_type='custom_module',
            base_url='module://qoder', configuration={'module_id': 'qoder'})
        db.add(provider)
        await db.commit()
        provider_id = provider.id
    app = FastAPI()
    app.include_router(modules.router, prefix='/api/admin')
    app.dependency_overrides[get_current_admin] = lambda: 'fixture-owner'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://fixture') as client:
        base = '/api/admin/modules/qoder/profiles'
        empty = await client.post(base, json={'name': 'empty account', 'fields': {'api_key': '', 'personal_access_token': ''}})
        assert empty.status_code == 422, 'An empty form is not an added Qoder account'
        created = await client.post(base, json={'name': 'PAT fixture', 'fields': {'personal_access_token': 'qoder_fixture_pat_not_live', 'api_key': 'qoder_fixture_pat_not_live'}})
        assert created.status_code == 201
        profile_id = created.json()['id']
        listed = await client.get(base)
        assert 'qoder_fixture_pat_not_live' not in listed.text
        async with AsyncSessionLocal() as db:
            cred = await db.get(ProviderCredential, profile_id)
            assert json.loads(decrypt_secret(cred.encrypted_api_key))['personal_access_token'] == 'qoder_fixture_pat_not_live'
            assert cred.provider_id == provider_id and not cred.metadata_json
        rejected = await client.put(base + '/' + str(profile_id), json={'fields': {'personal_access_token': '', 'api_key': '', 'auth_json': ''}})
        assert rejected.status_code == 422
        async with AsyncSessionLocal() as db:
            proxy = Proxy(name='Qoder edit egress fixture', scheme='http', host='fixture.invalid', port=8080, enabled=True)
            db.add(proxy)
            await db.commit()
            proxy_id = proxy.id
        assert (await client.put(base + '/' + str(profile_id), json={'proxy_id': proxy_id})).status_code == 422
        async with AsyncSessionLocal() as db:
            assert (await db.get(ProviderCredential, profile_id)).proxy_id is None
            await db.delete(await db.get(Proxy, proxy_id))
            await db.commit()
        assert (await client.delete(base + '/' + str(profile_id))).status_code == 200


@pytest.mark.asyncio
async def test_qoder_rotated_auth_callback_is_narrow_and_fail_closed():
    async with AsyncSessionLocal() as db:
        provider = (await db.scalars(select(Provider).where(Provider.slug == 'module_qoder'))).one()
        fields = {'personal_access_token': 'qoder_fixture_rotation_not_live'}
        cred = ProviderCredential(provider_id=provider.id, name='rotation fixture',
            encrypted_api_key=encrypt_secret(json.dumps(fields)), key_fingerprint=uuid.uuid4().hex, masked_key='fixture')
        db.add(cred)
        await db.commit()
        configuration = CredentialService.module_runtime_configuration(provider, cred)
        callback = configuration.get('persist_credentials')
        assert callable(callback), 'Native browser credential refresh must survive the ephemeral CLI directory'
        original = decrypt_secret(cred.encrypted_api_key)
    for malformed in ({}, {'access_token': 'fixture'}, {'auth_json': '{}'}, {'auth_json': '{}', 'api_key': 'fixture'}):
        with pytest.raises(ValueError):
            await callback(malformed)
    async with AsyncSessionLocal() as db:
        stored = await db.get(ProviderCredential, cred.id)
        assert decrypt_secret(stored.encrypted_api_key) == original
        await db.delete(stored)
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize('scenario', ['save', 'reauth', 'cancel', 'failure', 'foreign_url'])
async def test_qoder_native_login_owner_save_cancel_and_safe_errors(monkeypatch, tmp_path, scenario):
    import asyncio
    import os
    import sys
    from app.services import module_oauth
    from modules.qoder import handler as native

    executable = tmp_path / 'fixture-qodercli'
    executable.write_text('#!' + sys.executable + '\n' + '''
import os, pathlib, sys, time
root = pathlib.Path(os.environ['QODER_CONFIG_DIR'])
if 'login' not in sys.argv:
    import json
    auth = root / '.auth'
    assert (auth / 'user').read_text() in ('opaque-native-fixture', 'rotated-native-fixture')
    assert (auth / 'machine_id').read_text() == '0123456789abcdef0123456789abcdef'
    (auth / 'user').write_text('rotated-native-fixture')
    if '--list-models' in sys.argv:
        print('MODEL\\nAuto')
    else:
        assert sys.argv[sys.argv.index('--model') + 1] == 'Auto'
        print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': 'fixture-native-completion'}))
    sys.exit(0)
if os.environ['QODER_FAKE_SCENARIO'] == 'foreign_url':
    print('https://evil.invalid/device/selectAccounts?nonce=fixture', flush=True)
    sys.exit(1)
print('https://qoder.com/device/selectAccounts?nonce=fixture&challenge=fixture&challenge_method=S256', flush=True)
if os.environ['QODER_FAKE_SCENARIO'] == 'failure':
    print('PRIVATE_NATIVE_FAILURE_DO_NOT_EXPOSE', file=sys.stderr, flush=True)
    sys.exit(1)
while not (root.parent / 'release').exists():
    time.sleep(.01)
auth = root / '.auth'
auth.mkdir(parents=True, exist_ok=True)
(auth / 'machine_id').write_text('0123456789abcdef0123456789abcdef')
(auth / 'user').write_text('opaque-native-fixture')
os.chmod(auth / 'machine_id', 0o600)
os.chmod(auth / 'user', 0o600)
''')
    executable.chmod(0o700)
    envs, roots = [], []
    original_environment = native.native_environment
    def environment(root, fields, proxy_url):
        env = original_environment(root, fields, proxy_url)
        assert env['CI'] and env['BROWSER'] == 'www-browser'
        assert 'QODER_PERSONAL_ACCESS_TOKEN' not in env
        env['QODER_FAKE_SCENARIO'] = scenario
        envs.append(env)
        roots.append(root)
        return env
    monkeypatch.setenv('QODER_PERSONAL_ACCESS_TOKEN', 'must-not-inherit-host-account')
    monkeypatch.setattr(native, 'native_environment', environment)

    manifest = ModuleManifest.model_validate_json((Path(__file__).parents[1] / 'modules/qoder/manifest.json').read_text())
    monkeypatch.setattr(ModuleLoader, '_modules', {'qoder': LoadedModule(manifest=manifest)})
    async with AsyncSessionLocal() as db:
        provider = await db.scalar(select(Provider).where(Provider.slug == 'module_qoder'))
        if provider is None:
            provider = Provider(name='Qoder fixture', slug='module_qoder', adapter_type='custom_module',
                base_url='module://qoder', configuration={'module_id': 'qoder'})
            db.add(provider)
            await db.commit()
        existing_id = None
        if scenario == 'reauth':
            legacy = ProviderCredential(provider_id=provider.id, name='legacy Qoder fixture',
                encrypted_api_key=encrypt_secret(json.dumps({'api_key': 'fixture-old-api-key', 'api_base': 'https://fixture.invalid/v1'})),
                key_fingerprint=uuid.uuid4().hex, masked_key='fixture')
            db.add(legacy)
            await db.commit()
            existing_id = legacy.id
    app = FastAPI()
    app.include_router(modules.router, prefix='/api/admin')
    app.dependency_overrides[get_current_admin] = lambda: 'fixture-owner'
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://fixture') as client:
            base = '/api/admin/modules/qoder/oauth'
            started = await client.post(base + '/start', json={'cli_path': str(executable)})
            if scenario == 'foreign_url':
                assert started.status_code == 503 and not module_oauth.sessions
                assert all(not root.exists() for root in roots)
                return
            assert started.status_code == 200, started.text
            assert started.json()['auth_url'].startswith('https://qoder.com/device/selectAccounts?')
            assert started.json()['expires_in'] <= 300 and started.json()['loopback'] is False
            sid = started.json()['session_id']
            target = base + '/' + sid
            session = module_oauth.sessions[sid]
            if scenario not in ('failure',):
                assert (await client.post(target + '/save', json={'name': 'native'})).status_code == 409
            app.dependency_overrides[get_current_admin] = lambda: 'other-owner'
            assert (await client.get(target)).status_code == 404
            app.dependency_overrides[get_current_admin] = lambda: 'fixture-owner'
            assert (await client.get(target.replace('/qoder/', '/codex_cli/'))).status_code == 404
            assert (await client.post(target + '/callback', json={'callback_url': 'http://localhost/fake'})).status_code == 400
            if scenario == 'cancel':
                assert (await client.delete(target)).status_code == 200
                assert session.native_task.done() and not roots[0].exists()
                assert (await client.get(target)).status_code == 404
                assert not session.tokens
                return
            if scenario in ('save', 'reauth'):
                (roots[0] / 'release').touch()
            await asyncio.wait_for(asyncio.shield(session.native_task), 5)
            status = await client.get(target)
            assert 'PRIVATE_NATIVE_FAILURE_DO_NOT_EXPOSE' not in status.text
            assert 'opaque-native-fixture' not in status.text
            assert not roots[0].exists(), 'Temporary native credentials must be erased before publishing authorized'
            if scenario == 'failure':
                assert status.json()['status'] == 'error'
                assert (await client.post(target + '/save', json={'name': 'native'})).status_code == 409
                return
            assert status.json()['status'] == 'authorized'
            saved = await client.post(target + '/save', json={'name': 'native', 'notes': 'fixture-notes', 'rpm_limit': 5,
                **({'profile_id': existing_id} if existing_id else {})})
            assert saved.status_code == 200, saved.text
            cid = saved.json()['id']
            assert existing_id is None or cid == existing_id
            async with AsyncSessionLocal() as db:
                cred = await CredentialService.get_credential(db, cid)
                assert cred is not None
                fields = json.loads(decrypt_secret(cred.encrypted_api_key))
                account = native.normalize_auth(fields)
                assert account and fields['auth_json']
                assert cred.notes == 'fixture-notes' and cred.rpm_limit == 5 and not cred.metadata_json
                runtime = CredentialService.module_runtime_configuration(cred.provider, cred)
                original = decrypt_secret(cred.encrypted_api_key)
            from app.adapters.module_adapter import CustomModuleAdapter
            from app.schemas.chat import ChatCompletionRequest, ChatMessage
            adapter = native.QoderAdapter()
            monkeypatch.setattr(ModuleLoader, '_adapters', {'qoder': adapter})
            bridge = CustomModuleAdapter()
            try:
                models = await bridge.list_models('module://qoder', original, {}, runtime)
                assert [m.provider_model_id for m in models] == ['Auto']
                result = await bridge.chat_completions('module://qoder', original, 'Auto',
                    ChatCompletionRequest(model='module_qoder/Auto', messages=[ChatMessage(role='user', content='fixture')]), {}, runtime)
                assert result.choices[0].message.content == 'fixture-native-completion'
                async with AsyncSessionLocal() as db:
                    refreshed = await db.get(ProviderCredential, cid)
                    stored = json.loads(decrypt_secret(refreshed.encrypted_api_key))
                    assert stored['auth_json'] != fields['auth_json']
                    assert stored['qoder_egress_pin'] == fields['qoder_egress_pin']
                    assert not refreshed.metadata_json
            finally:
                await adapter.close()
            assert (await client.get(target)).status_code == 404
            listed = await client.get('/api/admin/modules/qoder/profiles')
            assert fields['auth_json'] not in listed.text
            assert (await client.delete('/api/admin/modules/qoder/profiles/' + str(cid))).status_code == 200
    finally:
        await module_oauth.close_all()

