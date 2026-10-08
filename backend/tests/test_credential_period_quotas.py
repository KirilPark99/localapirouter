"""Synthetic provider-budget regressions; execute with the isolated runner."""
import asyncio
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.core.errors import RouterException
from app.models.entities import Provider, CredentialPeriodQuotaCounter, CredentialPeriodQuotaReservation
from app.schemas.entities import CredentialCreate, CredentialUpdate, PeriodQuotaRule
from app.services.credential_service import CredentialService
from app.services.quota_service import QuotaService
from app.services.log_service import request_log_context
from test_period_quotas import create as create_router, admit, usage as router_usage, model, request, rule


async def create(*rules):
    async with AsyncSessionLocal() as db:
        provider = Provider(name='fixture', slug='fixture-' + uuid.uuid4().hex,
                            adapter_type='openai', base_url='https://fixture.invalid')
        db.add(provider)
        await db.commit()
        read = await CredentialService.create_credential(db, CredentialCreate(
            provider_id=provider.id, name='fixture', api_key='synthetic-' + uuid.uuid4().hex,
            quota_rules=list(rules), rpm_limit=7, tpm_limit=8, max_concurrency=9, notes='keep'))
        return await CredentialService.get_credential(db, read.id)


async def usage(credential):
    async with AsyncSessionLocal() as db:
        current = await CredentialService.get_credential(db, credential.id)
        return await QuotaService.usage(db, current)


async def reserve(credential, req=None, mdl=None):
    return await QuotaService.reserve_dispatch(None, mdl or model(), req or request(), credential=credential)


@pytest.mark.parametrize('rules', [
    [{'scope':'profile','model':'route/test','requests':1}],
    [{'scope':'model','model':'fixture/*','requests':1}],
    [{'requests':1}, {'requests':2}],
    [{'usd':float('nan')}], [{'requests':True}],
    [{'period':'interval','requests':1,'start':'2026-01-01','end':'2027-01-01'}],
])
def test_validation(rules):
    with pytest.raises(ValidationError):
        CredentialUpdate(quota_rules=rules)


@pytest.mark.asyncio
async def test_credential_only_key_and_model_meter_physical_dispatches():
    credential = await create(rule(requests=3), rule(scope='model', model='fixture/model', requests=1))
    assert [r['used']['requests'] for r in await usage(credential)] == [0, 0]
    ticket, _ = await reserve(credential)
    await ticket.finish({'prompt_tokens':2, 'completion_tokens':3}, success=True)
    with pytest.raises(RouterException):
        await reserve(credential)
    other = model(); other.canonical_slug = 'fixture/other'
    ticket, _ = await reserve(credential, mdl=other)
    await ticket.finish()  # unknown usage still counts a physical dispatch
    assert [r['used']['requests'] for r in await usage(credential)] == [2, 1]
    ticket, _ = await reserve(credential, mdl=other)
    await ticket.finish(dispatched=False)
    assert [r['used']['requests'] for r in await usage(credential)] == [2, 1]


@pytest.mark.asyncio
async def test_combined_owners_atomic_rollback_and_router_only_credits():
    credential = await create(rule(scope='model', model='fixture/model', requests=1, tokens=1000, usd=1))
    router = await create_router(rule(scope='model', model='fixture/model', requests=2, tokens=1000, usd=1))
    with request_log_context({'router_key_id':router.id, 'requested_model':'fixture/model', 'dispatches':[]}) as details:
        await admit(router)
        assert (await usage(credential))[0]['used']['requests'] == 0  # local HIT/admission isn't provider dispatch
        credits = details['quota_direct_pending'].copy()
        ticket, _ = await reserve(credential)
        assert ticket.id and not details['quota_direct_pending']
        assert (await usage(credential))[0]['used']['requests'] == 1
        assert (await router_usage(router))[0]['used']['requests'] == 1
        await asyncio.gather(*(ticket.finish(dispatched=False) for _ in range(5)))
        assert details['quota_direct_pending'] == credits
        assert (await usage(credential))[0]['used'] == {'requests':0, 'tokens':0, 'usd':0}
        ticket, _ = await reserve(credential)
        await asyncio.gather(*(ticket.finish({'prompt_tokens':10, 'completion_tokens':20}) for _ in range(5)))
        before = (await router_usage(router))[0]['used']
        assert before['tokens'] == 30
        assert (await usage(credential))[0]['used']['tokens'] == 30
        with pytest.raises(RouterException):
            await reserve(credential)  # router mutation must roll back when credential denies
        assert (await router_usage(router))[0]['used'] == before
    # Other direction: router denies after a provider still has room.
    fresh = await create(rule(requests=3))
    exhausted = await create_router(rule(scope='model',model='fixture/model',requests=1))
    with request_log_context({'router_key_id':exhausted.id, 'requested_model':'route/test'}):
        first, _ = await reserve(fresh); await first.finish()
        with pytest.raises(RouterException): await reserve(fresh)
    assert (await usage(fresh))[0]['used']['requests'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('reported', [None, {}, {'prompt_tokens':20,'total_tokens':0}, {'completion_tokens':2000}])
async def test_unknown_partial_usage_keeps_conservative_reservation(reported):
    credential = await create(rule(requests=5, tokens=5000, usd=1))
    ticket, _ = await reserve(credential)
    before = (await usage(credential))[0]['used']
    await ticket.finish(reported, success=False)
    after = (await usage(credential))[0]['used']
    assert after['requests'] == 1
    assert after['tokens'] == max(before['tokens'], (reported or {}).get('completion_tokens', 0))
    assert after['usd'] == before['usd']
    await ticket.finish(dispatched=False)
    assert (await usage(credential))[0]['used'] == after


@pytest.mark.asyncio
async def test_caps_prices_multichoice_and_no_request_mutation():
    credential = await create(rule(tokens=500, usd=.001))
    req = request(n=2, max_tokens=1000)
    ticket, effective = await reserve(credential, req)
    assert req.max_tokens == 1000 and effective is not req
    assert 0 < effective.get_effective_max_tokens() <= 50
    await ticket.finish({'input_tokens':10,'output_tokens':20}, success=True)
    assert (await usage(credential))[0]['used']['tokens'] == 30
    assert (await usage(credential))[0]['used']['usd'] == pytest.approx(.00005)
    mdl = model(); mdl.input_price_per_1m = None
    with pytest.raises(RouterException): await reserve(credential, mdl=mdl)
    mdl.input_price_per_1m = mdl.output_price_per_1m = 0
    ticket, _ = await reserve(credential, mdl=mdl); await ticket.finish(dispatched=False)
    tiny = await create(rule(tokens=1))
    with pytest.raises(RouterException): await reserve(tiny)
    assert (await usage(tiny))[0]['used']['tokens'] == 0


@pytest.mark.asyncio
async def test_concurrent_dual_owner_reservation_and_refund():
    credential = await create(rule(requests=3, tokens=2000))
    router = await create_router(rule(scope='model', model='fixture/model', requests=9, tokens=2000))
    with request_log_context({'router_key_id':router.id,'requested_model':'route/test'}):
        results = await asyncio.gather(*(reserve(credential) for _ in range(12)), return_exceptions=True)
        tickets = [r[0] for r in results if not isinstance(r, BaseException)]
        assert len(tickets) == 3
        assert all(not isinstance(r, BaseException) or isinstance(r, RouterException) for r in results)
        assert (await usage(credential))[0]['used']['requests'] == 3
        assert (await router_usage(router))[0]['used']['requests'] == 3
        await asyncio.gather(*(ticket.finish(dispatched=False) for ticket in tickets for _ in range(2)))
        assert (await usage(credential))[0]['used'] == pytest.approx({'requests':0,'tokens':0,'usd':0})
        assert (await router_usage(router))[0]['used'] == pytest.approx({'requests':0,'tokens':0,'usd':0})


@pytest.mark.asyncio
@pytest.mark.parametrize('period', ['minute','hour','day','week','month','custom','interval'])
async def test_period_reset_and_interval_inactivity(monkeypatch, period):
    from app.services import quota_service
    now = datetime(2026,10,8,0,0,0,tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return now
    monkeypatch.setattr(quota_service,'datetime',Clock)
    fields = {'duration_seconds':17,'anchor':now} if period == 'custom' else {}
    if period == 'interval': fields = {'start':now,'end':now+timedelta(seconds=17)}
    credential = await create(rule(period=period, requests=1, **fields))
    ticket, _ = await reserve(credential); await ticket.finish()
    with pytest.raises(RouterException): await reserve(credential)
    end = (await usage(credential))[0]['end']
    now = datetime.fromisoformat(end)
    if period == 'interval':
        with pytest.raises(RouterException): await reserve(credential)
        assert not (await usage(credential))[0]['active']
    else:
        ticket, _ = await reserve(credential); await ticket.finish()
        assert (await usage(credential))[0]['used']['requests'] == 1


@pytest.mark.asyncio
async def test_admin_crud_usage_preservation_and_cascades():
    from app.api.admin.credentials import router
    from app.api.deps import get_current_admin
    from app.core.database import get_db
    credential = await create()
    app = FastAPI(); app.include_router(router, prefix='/api/admin')
    app.dependency_overrides[get_current_admin] = lambda: 'synthetic'
    async def isolated_db():
        async with AsyncSessionLocal() as db: yield db
    app.dependency_overrides[get_db] = isolated_db
    path = f'/api/admin/credentials/{credential.id}'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        response = await client.put(path,json={'quota_rules':[{'requests':3,'tokens':1000,'usd':1}]})
        assert response.status_code == 200, response.text
        saved = response.json(); rules = saved['quota_rules']
        assert rules[0]['id'] and saved['rpm_limit'] == 7 and saved['notes'] == 'keep'
        assert saved['tpm_limit'] == 8 and saved['max_concurrency'] == 9
        assert (await client.get(path+'/usage')).json()[0]['remaining'] == {'requests':3,'tokens':1000,'usd':1}
        ticket, _ = await reserve(credential); await ticket.finish({'prompt_tokens':5,'completion_tokens':7})
        renamed = await client.put(path,json={'name':'renamed'})
        assert renamed.json()['quota_rules'] == rules
        assert renamed.json()['key_fingerprint'] == saved['key_fingerprint']
        rules[0]['requests'] = 4
        assert (await client.put(path,json={'quota_rules':rules})).status_code == 200
        assert (await client.get(path+'/usage')).json()[0]['used']['tokens'] == 12
        rules[0]['period'] = 'hour'
        assert (await client.put(path,json={'quota_rules':rules})).status_code == 422
        other = await create()
        assert (await client.put(f'/api/admin/credentials/{other.id}',json={'quota_rules':rules})).status_code == 422
        assert (await client.put(path,json={'quota_rules':[{'scope':'profile','model':'route/test','requests':1}]})).status_code == 422
        assert (await client.put(path,json={'quota_rules':[]})).status_code == 200
        assert (await client.put(path,json={'quota_rules':[{'requests':1,'tokens':1000,'usd':1}]})).status_code == 200
        with pytest.raises(RouterException): await reserve(credential)  # identical identity cannot reset spending
        assert (await client.delete(path)).status_code == 200
        assert (await client.get(path+'/usage')).status_code == 404
    async with AsyncSessionLocal() as db:
        for table in (CredentialPeriodQuotaCounter, CredentialPeriodQuotaReservation):
            assert await db.scalar(select(func.count()).select_from(table).where(table.key_id == credential.id)) == 0


@pytest.mark.asyncio
async def test_unlimited_disabled_nonmatching_and_deleted_owner_settlement():
    for rules in ([], [rule(requests=1,enabled=False)], [rule(scope='model',model='fixture/other',requests=1)]):
        credential = await create(*rules)
        assert (await reserve(credential))[0] is None
        async with AsyncSessionLocal() as db:
            assert await db.scalar(select(func.count()).select_from(CredentialPeriodQuotaCounter).where(CredentialPeriodQuotaCounter.key_id==credential.id)) == 0
    credential = await create(rule(requests=2,tokens=1000))
    router = await create_router(rule(tokens=1000))
    with request_log_context({'router_key_id':router.id}):
        ticket, _ = await reserve(credential)
        async with AsyncSessionLocal() as db: await CredentialService.delete_credential(db, credential.id)
        await ticket.finish(dispatched=False)
        assert (await router_usage(router))[0]['used']['tokens'] == 0


@pytest.mark.asyncio
async def test_quota_lock_and_settlement_preserve_owner_timestamps():
    credential = await create(rule(tokens=1000,requests=3))
    router = await create_router(rule(tokens=1000))
    credential_stamp, router_stamp = credential.updated_at, router.updated_at
    with request_log_context({'router_key_id':router.id}):
        ticket, _ = await reserve(credential)
        async with AsyncSessionLocal() as db:
            assert (await CredentialService.get_credential(db,credential.id)).updated_at == credential_stamp
            from app.services.api_key_service import ApiKeyService
            assert (await ApiKeyService.get_key(db,router.id)).updated_at == router_stamp
        await ticket.finish({'prompt_tokens':5,'completion_tokens':7})
        ticket, _ = await reserve(credential); await ticket.finish(dispatched=False)
    async with AsyncSessionLocal() as db:
        assert (await CredentialService.get_credential(db,credential.id)).updated_at == credential_stamp
        assert (await ApiKeyService.get_key(db,router.id)).updated_at == router_stamp


@pytest.mark.asyncio
async def test_tightest_combined_output_bounds_and_owner_metadata():
    req = request(max_tokens=50)
    prompt = len(json.dumps(req.model_dump(include={'messages','tools'}),ensure_ascii=False).encode())
    credential = await create(rule(tokens=prompt+7))
    router = await create_router(rule(tokens=prompt+11))
    with request_log_context({'router_key_id':router.id}):
        ticket, effective = await reserve(credential, req)
        assert effective.max_tokens == effective.max_completion_tokens == 7
        assert req.max_tokens == 50
        assert (await usage(credential))[0]['used']['tokens'] == prompt+7
        assert (await router_usage(router))[0]['used']['tokens'] == prompt+7
        with pytest.raises(RouterException) as denied:
            await reserve(credential, req)
        assert denied.value.raw_error == {'local_admission':True,'quota_owner':'credential','credential_id':credential.id}
        await ticket.finish(dispatched=False)
    requests_only = await create(rule(requests=1))
    ticket, _ = await reserve(requests_only); await ticket.finish()
    with pytest.raises(RouterException) as denied:
        await reserve(requests_only)
    assert denied.value.raw_error['quota_owner'] == 'credential'


@pytest.mark.asyncio
async def test_dual_owner_cancellation_waits_for_refund(monkeypatch):
    credential = await create(rule(tokens=1000))
    router = await create_router(rule(tokens=1000))
    with request_log_context({'router_key_id':router.id}):
        ticket, _ = await reserve(credential)
        original = QuotaService.settle
        entered, release = asyncio.Event(), asyncio.Event()
        async def paused(*args):
            entered.set(); await release.wait()
            return await original(*args)
        monkeypatch.setattr(QuotaService,'settle',paused)
        task = asyncio.create_task(ticket.finish(dispatched=False))
        await entered.wait(); task.cancel(); release.set()
        with pytest.raises(asyncio.CancelledError): await task
        assert (await usage(credential))[0]['used']['tokens'] == 0
        assert (await router_usage(router))[0]['used']['tokens'] == 0


@pytest.mark.asyncio
async def test_native_credential_quota_and_legacy_fixture_shape():
    from types import SimpleNamespace
    from app.schemas.jev import JevRequest
    native = JevRequest(model='fixture/model',state='Hi',questions={'a':{'type':'noul','instructions':'Yes?'}})
    credential = await create(rule(tokens=1000))
    # Legacy SimpleNamespace credentials need no new attributes; persistence is authoritative.
    legacy = SimpleNamespace(id=credential.id)
    ticket, effective = await reserve(legacy, req=native)
    assert effective is native
    await ticket.finish({'input_tokens':10,'output_tokens':20})
    assert (await usage(credential))[0]['used']['tokens'] == 30
    prompt = len(json.dumps(native.model_dump(),ensure_ascii=False).encode())
    tight = await create(rule(tokens=prompt+7))
    with pytest.raises(RouterException) as denied: await reserve(tight, req=native)
    assert denied.value.raw_error['quota_owner'] == 'credential'
    unlimited = await create()
    assert (await reserve(SimpleNamespace(id=unlimited.id)))[0] is None


@pytest.mark.asyncio
async def test_api_create_default_and_rule_roundtrip():
    from app.api.admin.credentials import router
    from app.api.deps import get_current_admin
    from app.core.database import get_db
    seed = await create()
    app = FastAPI(); app.include_router(router,prefix='/api/admin')
    app.dependency_overrides[get_current_admin] = lambda: 'synthetic'
    async def isolated_db():
        async with AsyncSessionLocal() as db: yield db
    app.dependency_overrides[get_db] = isolated_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        for rules in (None,[{'period':'hour','requests':2,'tokens':2000,'usd':1}]):
            payload = {'provider_id':seed.provider_id,'name':'fixture','api_key':'synthetic-'+uuid.uuid4().hex}
            if rules is not None: payload['quota_rules'] = rules
            response = await client.post('/api/admin/credentials',json=payload)
            assert response.status_code == 201,response.text
            saved = response.json()
            assert bool(saved['quota_rules']) == bool(rules)
            path = f"/api/admin/credentials/{saved['id']}"
            assert (await client.get(path+'/usage')).status_code == 200
            listed = (await client.get('/api/admin/credentials')).json()
            assert next(c for c in listed if c['id']==saved['id'])['quota_rules'] == saved['quota_rules']
            assert (await client.delete(path)).status_code == 200


def test_forward_migration_fresh_and_representative_upgrade_twice(monkeypatch):
    from alembic import command
    from alembic.config import Config
    from app.core.config import settings
    from app.core.database import engine
    original = Path(engine.url.database).resolve()
    assert original == Path(AsyncSessionLocal.kw['bind'].url.database).resolve()
    assert original.name.startswith('myairouter_test_')
    config = Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    for legacy in (False,True):
        path = Path(os.environ['TMPDIR'])/('myairouter_credential_migration_'+uuid.uuid4().hex+'.db')
        assert path.resolve() != original
        monkeypatch.setattr(settings,'DATABASE_URL','sqlite+aiosqlite:///'+str(path))
        before = {}
        if legacy:
            command.upgrade(config,'p9q0r1s2t3u4')
            with closing(sqlite3.connect(path)) as db:
                db.execute("INSERT INTO router_api_keys (name,key_prefix,key_hash,masked_key,enabled,permissions,allowed_models,allowed_routes,allowed_fusions,allowed_judges,total_requests,quota_rules,ip_restrictions,created_at,updated_at) VALUES ('legacy','synthetic','synthetic','synthetic',1,'[]','[]','[]','[]','[]',7,'[]','[]','2026-01-01','2026-01-01')")
                db.execute("INSERT INTO period_quota_counters VALUES (1,'identity','start',2,30,0.1)")
                db.execute("INSERT INTO period_quota_reservations VALUES ('reservation',1,'[]','{}',0)")
                db.execute("INSERT INTO providers (name,slug,adapter_type,base_url,enabled,auth_type,auth_header,extra_headers,configuration,models_endpoint,chat_endpoint,created_at,updated_at) VALUES ('fixture','fixture','openai','https://fixture.invalid',1,'bearer','Authorization','{}','{}','/models','/chat','2026-01-01','2026-01-01')")
                db.execute("INSERT INTO provider_credentials (provider_id,name,encrypted_api_key,key_fingerprint,masked_key,enabled,status,consecutive_failures,priority,weight,metadata_json,created_at,updated_at) VALUES (1,'fixture','synthetic-encrypted','synthetic','synthetic',1,'HEALTHY',0,1,1,'{}','2026-01-01','2026-01-01')")
                db.commit()
                for table in ('router_api_keys','period_quota_counters','period_quota_reservations'):
                    before[table] = db.execute('SELECT * FROM '+table).fetchall()
        command.upgrade(config,'head'); command.upgrade(config,'head')
        with closing(sqlite3.connect(path)) as db:
            assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == 'q0r1s2t3u4v5'
            for table, rows in before.items(): assert db.execute('SELECT * FROM '+table).fetchall() == rows
            if legacy:
                assert db.execute('SELECT encrypted_api_key,quota_rules FROM provider_credentials').fetchone() == ('synthetic-encrypted','[]')
                db.execute('PRAGMA foreign_keys=ON')
                db.execute("INSERT INTO credential_period_quota_counters VALUES (1,'identity','start',1,5,0.2)")
                db.execute("INSERT INTO credential_period_quota_reservations VALUES ('reservation',1,'[]','{}',0)")
                db.execute('DELETE FROM provider_credentials WHERE id=1')
                assert db.execute('SELECT count(*) FROM credential_period_quota_counters').fetchone()[0] == 0
                assert db.execute('SELECT count(*) FROM credential_period_quota_reservations').fetchone()[0] == 0
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
            db.commit()
        path.unlink()
    assert Path(engine.url.database).resolve() == original
