"""Run via the supplied run_module_offline.py; synthetic DB, no app lifecycle."""
import asyncio
import importlib
from pathlib import Path
import os

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.admin import modules
from app.api.deps import get_current_admin
from app.core.database import AsyncSessionLocal, engine, get_db
from app.models.entities import AppSetting, Provider, ProviderCredential


@pytest.mark.asyncio
async def test_module_groups_persistent_atomic_contract(monkeypatch):
    assert Path(engine.url.database).resolve().parent == Path(os.environ['TMPDIR']).resolve()
    assert AsyncSessionLocal.kw['bind'] is engine

    def forbidden(*args, **kwargs):
        raise AssertionError('Module startup, discovery and profile synchronization forbidden')

    monkeypatch.setattr(modules.ModuleLoader, 'scan_modules', forbidden)
    monkeypatch.setattr(modules.ModuleLoader, 'sync_with_db', forbidden)
    monkeypatch.setattr(modules.ModuleLoader, 'reload_and_sync', forbidden)
    monkeypatch.setattr(modules.ModuleLoader, '_modules', {'alpha': object(), 'beta': object()})

    async with AsyncSessionLocal() as db:
        provider = Provider(name='Synthetic', slug='module_alpha', adapter_type='custom_module',
                            base_url='module://alpha', configuration={'manifest': {'id': 'alpha'}}, notes='keep')
        db.add(provider)
        await db.flush()
        db.add(ProviderCredential(provider_id=provider.id, name='Synthetic profile', group_name='profile-only',
                                  encrypted_api_key='synthetic-opaque-ciphertext', key_fingerprint='synthetic',
                                  masked_key='masked', metadata_json={'keep': True}, rpm_limit=7))
        db.add(AppSetting(key='unrelated-setting', value_json={'keep': True}))
        await db.commit()

    async def snapshot():
        async with AsyncSessionLocal() as db:
            return [list((await db.execute(select(table.__table__))).mappings())
                    for table in (Provider, ProviderCredential)]

    before = await snapshot()

    def app(session_factory=AsyncSessionLocal):
        application = FastAPI()
        application.include_router(modules.router, prefix='/api/admin')
        application.dependency_overrides[get_current_admin] = lambda: 'synthetic-admin'

        async def database():
            async with session_factory() as db:
                yield db
        application.dependency_overrides[get_db] = database
        return application

    path = '/api/admin/modules/groups'
    application = app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url='http://fixture') as client:
        empty = {'groups': [], 'assignments': {}, 'revision': 0}
        assert (await client.get(path)).json() == empty  # Static route must precede /{module_id}.
        async with AsyncSessionLocal() as db:
            assert await db.scalar(select(AppSetting).where(AppSetting.key == 'module_groups')) is None

        # Authentication remains mandatory for both routes without touching real admin accounts.
        def denied():
            raise HTTPException(401, 'Synthetic unauthenticated request')
        application.dependency_overrides[get_current_admin] = denied
        assert (await client.get(path)).status_code == 401
        assert (await client.put(path, json=empty)).status_code == 401
        application.dependency_overrides[get_current_admin] = lambda: 'synthetic-admin'

        payload = {'groups': ['  Empty  ', ' Work '], 'assignments': {'alpha': ' Work '}, 'revision': 0}
        responses = await asyncio.gather(*(client.put(path, json=payload) for _ in range(2)))
        assert sorted(response.status_code for response in responses) == [200, 409]
        response = next(response for response in responses if response.status_code == 200)
        state = {'groups': ['Empty', 'Work'], 'assignments': {'alpha': 'Work'}, 'revision': 1}
        assert response.status_code == 200 and response.json() == state
        assert (await client.get(path)).json() == state
        async with AsyncSessionLocal() as db:
            assert (await db.scalar(select(AppSetting).where(AppSetting.key == 'module_groups'))).value_json == state
        assert (await client.put(path, json=empty)).status_code == 409

        bad_payloads = [
            {**state, 'groups': [' ']}, {**state, 'groups': ['x' * 101]},
            {**state, 'groups': ['Work', ' Work ']}, {**state, 'groups': [' Без ГрУпПы ']},
            {**state, 'assignments': {'alpha': 'Missing'}},
            {**state, 'assignments': {'unknown': 'Work'}},
            {**state, 'groups': [1]}, {**state, 'assignments': {'alpha': 1}},
            {**state, 'groups': 'Work'}, {**state, 'assignments': []},
            {**state, 'revision': True}, {**state, 'revision': '1'}, {**state, 'revision': -1},
            {**state, 'extra': True}, {'groups': [], 'assignments': {}},
        ]
        for payload in bad_payloads:
            assert (await client.put(path, json=payload)).status_code == 422, payload
            assert (await client.get(path)).json() == state

        # A rescan can temporarily lose modules; only previously saved IDs may survive.
        monkeypatch.setattr(modules.ModuleLoader, '_modules', {})
        assert (await client.get(path)).json() == state
        state = {**state, 'groups': ['Empty', 'Renamed'], 'assignments': {'alpha': 'Renamed'}}
        response = await client.put(path, json=state)
        assert response.status_code == 200
        state = response.json()
        assert state['revision'] == 2
        assert (await client.put(path, json={**state, 'assignments': {'alpha': 'Renamed', 'beta': 'Empty'}})).status_code == 422
        monkeypatch.setattr(modules.ModuleLoader, '_modules', {'alpha': object(), 'beta': object()})
        response = await client.put(path, json={**state, 'assignments': {'alpha': 'Empty', 'beta': 'Renamed'}})
        assert response.status_code == 200
        state = response.json()
        assert state['revision'] == 3

        # Concurrent editors: exactly one succeeds; no lost update or duplicate setting.
        responses = await asyncio.gather(*(client.put(path, json=state) for _ in range(2)))
        assert sorted(response.status_code for response in responses) == [200, 409]
        state = next(response.json() for response in responses if response.status_code == 200)
        assert state['revision'] == 4
        response = await client.put(path, json={'groups': ['Empty'], 'assignments': {}, 'revision': 4})
        assert response.status_code == 200
        state = response.json()
        assert state == {'groups': ['Empty'], 'assignments': {}, 'revision': 5}
        assert (await client.get(path)).json() == state
        assert await snapshot() == before  # Every provider/profile/credential column, including timestamps.
        async with AsyncSessionLocal() as db:
            assert (await db.scalar(select(AppSetting).where(AppSetting.key == 'unrelated-setting'))).value_json == {'keep': True}

    # Simulated restart: new router/lock, app and DB connections; no lifecycle or live reload.
    await engine.dispose()
    importlib.reload(modules)
    monkeypatch.setattr(modules.ModuleLoader, '_modules', {})
    fresh_engine = create_async_engine(str(engine.url))
    fresh_sessions = async_sessionmaker(fresh_engine, expire_on_commit=False)
    try:
        async with fresh_sessions() as db:
            # Synthetic stand-in for the configuration overwrite done by loader sync.
            provider = await db.scalar(select(Provider).where(Provider.slug == 'module_alpha'))
            provider.configuration = {'manifest': {'id': 'alpha', 'changed': True}}
            await db.commit()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app(fresh_sessions)), base_url='http://fixture') as client:
            assert (await client.get(path)).json() == state
            response = await client.put(path, json={'groups': [], 'assignments': {}, 'revision': 5})
            assert response.status_code == 200
            assert response.json() == {'groups': [], 'assignments': {}, 'revision': 6}
            assert (await client.get(path)).json() == response.json()
    finally:
        await fresh_engine.dispose()
