"""Subscription display is credential-scoped and independent of router admission."""
import json
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.admin.credentials import router
from app.api.deps import get_current_admin
from app.core.crypto import decrypt_secret
from app.core.database import AsyncSessionLocal
from app.core.errors import ErrorCategory, RouterException
from app.models.entities import Provider
from app.modules.base import SubscriptionLimit, SubscriptionLimits
from app.modules.loader import ModuleLoader
from app.schemas.entities import CredentialCreate
from app.services.credential_service import CredentialService


@pytest.mark.asyncio
async def test_subscription_endpoint_key_scope_and_no_local_quota_mutation(monkeypatch):
    seen = []

    async def limits(ctx):
        seen.append((ctx.credentials.copy(), ctx.extra_config['credential_id'], ctx.proxy_url))
        return SubscriptionLimits(plan=ctx.credentials['access_token'], limits=[
            SubscriptionLimit(name='Primary', used_percent=0, remaining_percent=100),
            SubscriptionLimit(name='Unknown'),
        ])

    module = type('SyntheticModule', (), {'get_subscription_limits': staticmethod(limits)})()
    monkeypatch.setattr(ModuleLoader, 'get_adapter', lambda module_id: module)
    app = FastAPI()
    app.include_router(router, prefix='/api/admin')
    app.dependency_overrides[get_current_admin] = lambda: 'fixture-admin'
    async with AsyncSessionLocal() as db:
        provider = Provider(name='fixture', slug='subscription-' + uuid.uuid4().hex,
                            adapter_type='custom_module', base_url='https://fixture.invalid',
                            configuration={'module_id': 'codex_cli'})
        db.add(provider)
        await db.commit()
        keys = []
        for number in (1, 2):
            keys.append(await CredentialService.create_credential(db, CredentialCreate(
                provider_id=provider.id, name=f'key-{number}',
                api_key=json.dumps({'access_token': f'synthetic-{number}', 'auto_detect_local': False}),
                quota_rules=[{'period': 'day', 'requests': 3}], notes='keep')))
        before = [(key.id, (await CredentialService.get_credential(db, key.id)).quota_rules) for key in keys]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        for index, key in enumerate(keys, 1):
            response = await client.get(f'/api/admin/credentials/{key.id}/subscription-limits')
            assert response.status_code == 200
            payload = response.json()
            assert payload['plan'] == f'synthetic-{index}'
            assert payload['limits'][0]['used_percent'] == 0
            assert payload['limits'][1]['used_percent'] is None
            assert payload['checked_at']
        assert (await client.get('/api/admin/credentials/999999999/subscription-limits')).status_code == 404
    assert [row[1] for row in seen] == [key.id for key in keys]
    assert [row[0]['access_token'] for row in seen] == ['synthetic-1', 'synthetic-2']
    assert all(row[2] is None for row in seen)
    async with AsyncSessionLocal() as db:
        for key_id, rules in before:
            credential = await CredentialService.get_credential(db, key_id)
            assert credential.quota_rules == rules
            assert credential.notes == 'keep'
            assert credential.last_checked_at is None
            assert credential.consecutive_failures == 0


@pytest.mark.asyncio
async def test_subscription_endpoint_auth_errors_do_not_expire_admin_or_leak_secrets(monkeypatch):
    app = FastAPI()
    app.include_router(router, prefix='/api/admin')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        response = await client.get('/api/admin/credentials/1/subscription-limits')
        assert response.status_code in (401, 403)
    app.dependency_overrides[get_current_admin] = lambda: 'fixture-admin'
    async with AsyncSessionLocal() as db:
        provider = Provider(name='fixture', slug='subscription-errors-' + uuid.uuid4().hex,
                            adapter_type='custom_module', base_url='https://fixture.invalid',
                            configuration={'module_id': 'codex_cli'})
        db.add(provider)
        await db.commit()
        key = await CredentialService.create_credential(db, CredentialCreate(
            provider_id=provider.id, name='fixture', api_key='synthetic-private-token'))
    from app.adapters.module_adapter import CustomModuleAdapter
    for error in (RouterException('synthetic-private-token', ErrorCategory.AUTH_ERROR, status_code=401),
                  ValueError('synthetic-private-token'), TimeoutError('synthetic-private-token')):
        monkeypatch.setattr(CustomModuleAdapter, 'get_subscription_limits', AsyncMock(side_effect=error))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
            response = await client.get(f'/api/admin/credentials/{key.id}/subscription-limits')
        assert response.status_code == 200
        assert response.json()['status'] == 'unavailable'
        assert response.json()['limits'] == []
        assert 'synthetic-private-token' not in response.text
    async with AsyncSessionLocal() as db:
        stored = await CredentialService.get_credential(db, key.id)
        assert decrypt_secret(stored.encrypted_api_key) == 'synthetic-private-token'
        assert stored.consecutive_failures == 0 and stored.last_error is None


@pytest.mark.asyncio
async def test_subscription_unsupported_provider_does_not_probe(monkeypatch):
    monkeypatch.setattr('app.services.credential_service.get_adapter', lambda *_: pytest.fail('must not probe'))
    async with AsyncSessionLocal() as db:
        provider = Provider(name='fixture', slug='subscription-unsupported-' + uuid.uuid4().hex,
                            adapter_type='openai', base_url='https://fixture.invalid')
        db.add(provider)
        await db.commit()
        key = await CredentialService.create_credential(db, CredentialCreate(
            provider_id=provider.id, name='fixture', api_key='synthetic-token'))
        result = await CredentialService.get_subscription_limits(db, key.id)
        assert result.status == 'unsupported' and result.limits == []
