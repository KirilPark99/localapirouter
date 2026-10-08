"""Offline, synthetic quota regressions; run with the isolated Lingling runner."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.core.errors import RouterException
from app.models.entities import PeriodQuotaCounter, PeriodQuotaReservation
from app.schemas.entities import PeriodQuotaRule, RouterApiKeyCreate, RouterApiKeyUpdate
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from app.services.api_key_service import ApiKeyService
from app.services.quota_service import QuotaService, window
from app.services.log_service import request_log_context


def rule(**kw):
    return PeriodQuotaRule(**kw)


async def create(*rules, **fields):
    async with AsyncSessionLocal() as db:
        created = await ApiKeyService.create_key(db, RouterApiKeyCreate(name='quota-' + uuid.uuid4().hex, quota_rules=list(rules), **fields))
        return await ApiKeyService.get_key(db, created.id)


async def admit(key, model='fixture/model'):
    async with AsyncSessionLocal() as db:
        await ApiKeyService.admit_inference(db, key, requested_model=model)


def request(**kw):
    return ChatCompletionRequest(model='fixture/model', messages=[ChatMessage(role='user', content='Hi')], **kw)


def model(**kw):
    return SimpleNamespace(canonical_slug='fixture/model', input_price_per_1m=1., output_price_per_1m=2., max_output_tokens=50, context_length=1000, **kw)


async def reserve(key, req=None, mdl=None, requested='fixture/model'):
    with request_log_context({'router_key_id':key.id, 'requested_model':requested, 'dispatches':[]}):
        return await QuotaService.reserve_dispatch(None, mdl or model(), req or request())


async def usage(key):
    async with AsyncSessionLocal() as db:
        current = await ApiKeyService.get_key(db, key.id)
        return await QuotaService.usage(db, current)


@pytest.mark.parametrize('fields', [dict(requests=0), dict(tokens=-1), dict(usd=float('nan')), dict(usd=float('inf')), dict(usd=True), dict(requests='2'), dict(period='custom',requests=1,duration_seconds=0,anchor='2026-01-01T00:00:00Z'), dict(period='interval', requests=1,start='2026-01-01',end='2027-01-01'), dict(scope='model',model='bad*',requests=1), dict(scope='profile',model='fixture/model',requests=1)])
def test_invalid_rules(fields):
    with pytest.raises(ValidationError):
        rule(**fields)


def test_duplicate_and_calendar_windows():
    with pytest.raises(ValidationError):
        RouterApiKeyCreate(name='x',quota_rules=[rule(requests=1),rule(requests=2)])
    with pytest.raises(ValidationError):
        RouterApiKeyCreate(name='x',quota_rules=[rule(requests=1,period='minute')]*65)
    now=datetime(2026,2,28,23,59,59,tzinfo=timezone.utc)
    _,start,end=window(rule(period='month',requests=1).model_dump(mode='json'),now)
    assert start=='2026-02-01T00:00:00+00:00' and end=='2026-03-01T00:00:00+00:00'
    _,start,end=window(rule(period='week',requests=1).model_dump(mode='json'),now)
    assert datetime.fromisoformat(start).weekday()==0


@pytest.mark.parametrize('period', ['minute', 'hour', 'day', 'week', 'month', 'custom'])
def test_preset_and_custom_boundaries(period):
    now = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    fields = {'duration_seconds': 17, 'anchor': '2027-01-01T02:00:00+02:00'} if period == 'custom' else {}
    value = rule(period=period, requests=1, **fields).model_dump(mode='json')
    identity, start, end = window(value, now)
    assert datetime.fromisoformat(start) <= now < datetime.fromisoformat(end)
    next_identity, next_start, next_end = window(value, datetime.fromisoformat(end))
    assert next_identity == identity and next_start == end and next_end > end
    assert window({**value, 'requests': 99}, now)[0] == identity
    if period == 'custom':
        assert value['anchor'] == '2027-01-01T00:00:00Z'
        assert datetime.fromisoformat(end) - datetime.fromisoformat(start) == timedelta(seconds=17)


def test_interval_exact_boundaries_and_alias_identity():
    value = rule(period='interval', start='2026-10-08T02:00:00+02:00', end='2026-10-09T00:00:00Z', requests=1).model_dump(mode='json')
    start, end = (datetime.fromisoformat(value[field]) for field in ('start', 'end'))
    assert window(value, start) == window(value, end - timedelta(microseconds=1))
    for now in (start - timedelta(microseconds=1), end):
        with pytest.raises(RouterException):
            window(value, now)
    alias = rule(scope='profile', model='smart/test', requests=1)
    canonical = rule(scope='profile', model='judge/test', requests=2)
    assert window(alias.model_dump(mode='json'), start)[0] == window(canonical.model_dump(mode='json'), start)[0]
    with pytest.raises(ValidationError):
        RouterApiKeyCreate(name='x', quota_rules=[alias, canonical])


@pytest.mark.asyncio
async def test_concurrent_admission_lifetime_and_period_atomic():
    key=await create(rule(requests=3),request_limit=10)
    results=await asyncio.gather(*(admit(key) for _ in range(12)),return_exceptions=True)
    assert sum(v is None for v in results)==3
    assert all(v is None or isinstance(v,RouterException) for v in results)
    async with AsyncSessionLocal() as db:
        assert (await ApiKeyService.get_key(db,key.id)).total_requests==3
    assert (await usage(key))[0]['used']['requests']==3


@pytest.mark.asyncio
async def test_reset_custom_and_interval_fail_closed():
    now=datetime.now(timezone.utc)
    key=await create(rule(period='custom',duration_seconds=1,anchor=now,requests=1))
    await admit(key)
    with pytest.raises(RouterException): await admit(key)
    await asyncio.sleep(1.05)
    await admit(key)
    for start,end in [(now-timedelta(days=2),now-timedelta(days=1)),(now+timedelta(days=1),now+timedelta(days=2))]:
        key=await create(rule(period='interval',start=start,end=end,requests=1))
        with pytest.raises(RouterException): await admit(key)
        assert not (await usage(key))[0]['active']


@pytest.mark.asyncio
async def test_model_requests_physical_and_profile_logical():
    key=await create(rule(requests=5),rule(scope='model',model='fixture/model',requests=1),rule(scope='profile',model='route/test',requests=3))
    await admit(key,'route/test')
    ticket,_=await reserve(key,requested='route/test')
    await ticket.finish({'prompt_tokens':2,'completion_tokens':3},success=True)
    with pytest.raises(RouterException): await reserve(key,requested='route/test')
    stats=await usage(key)
    assert [u['used']['requests'] for u in stats]==[1,1,1]
    # A different actual model doesn't consume fixture/model's request budget.
    mdl=model(); mdl.canonical_slug='fixture/other'
    ticket,_=await reserve(key,mdl=mdl,requested='route/test')
    await ticket.finish(dispatched=False)
    assert [u['used']['requests'] for u in await usage(key)]==[1,1,1]


@pytest.mark.asyncio
async def test_tokens_usd_bounds_settlement_and_release():
    key=await create(rule(tokens=1000,usd=.002))
    ticket,effective=await reserve(key)
    assert 0<effective.get_effective_max_tokens()<=50
    reserved=(await usage(key))[0]['used']
    assert reserved['tokens']>50 and reserved['usd']>0
    # Latest cumulative stream usage, not addition of cumulative snapshots.
    await ticket.finish({'prompt_tokens':20,'completion_tokens':30,'total_tokens':50},success=True)
    await ticket.finish({'prompt_tokens':999,'completion_tokens':999})
    measured=(await usage(key))[0]['used']
    assert measured['tokens']==50 and measured['usd']==pytest.approx(.00008)
    ticket,_=await reserve(key)
    await asyncio.gather(ticket.finish(dispatched=False),ticket.finish(dispatched=False))
    assert (await usage(key))[0]['used']==measured
    ticket,_=await reserve(key)
    before=(await usage(key))[0]['used']
    await ticket.finish(success=False)
    assert (await usage(key))[0]['used']==before


@pytest.mark.asyncio
@pytest.mark.parametrize('reported', [
    {'prompt_tokens': 20, 'total_tokens': 0},
    {'completion_tokens': 2000},
    {'input_tokens': 20, 'total_tokens': 10},
])
async def test_partial_usage_never_refunds_unknown_tokens(reported):
    key = await create(rule(tokens=5000, usd=1))
    ticket, _ = await reserve(key)
    reserved = (await usage(key))[0]['used']
    await ticket.finish(reported)
    settled = (await usage(key))[0]['used']
    assert settled['tokens'] == max(reserved['tokens'], reported.get('completion_tokens', 0))
    assert settled['usd'] == reserved['usd']


@pytest.mark.parametrize('date', [True, 1780000000, '1780000000', '0001-01-01T00:00:00+01:00', '9999-12-31T23:59:59-01:00'])
def test_quota_dates_require_iso_timestamps(date):
    with pytest.raises(ValidationError):
        rule(period='custom', duration_seconds=60, anchor=date, requests=1)


@pytest.mark.asyncio
async def test_unknown_prices_and_unbounded_zero_price():
    key=await create(rule(usd=1))
    mdl=model(); mdl.input_price_per_1m=None
    with pytest.raises(RouterException): await reserve(key,mdl=mdl)
    mdl.input_price_per_1m=mdl.output_price_per_1m=0
    ticket,_=await reserve(key,mdl=mdl)
    await ticket.finish({'prompt_tokens':5,'completion_tokens':7})
    assert (await usage(key))[0]['used']['usd']==0
    mdl.max_output_tokens=None
    with pytest.raises(RouterException): await reserve(key,mdl=mdl)


@pytest.mark.asyncio
async def test_rule_edits_keep_spending_and_ids_owned():
    from fastapi import HTTPException
    key=await create(rule(requests=1))
    await admit(key)
    async with AsyncSessionLocal() as db:
        updated=await ApiKeyService.update_key(db,key.id,RouterApiKeyUpdate(name='renamed'))
        assert updated.quota_rules[0].id==key.quota_rules[0]['id']
        edited=updated.quota_rules[0].model_copy(update={'requests':2})
        await ApiKeyService.update_key(db,key.id,RouterApiKeyUpdate(quota_rules=[edited]))
    assert (await usage(key))[0]['used']['requests']==1
    # Removing and re-adding identical scope/window can't reset its counter via a new ID.
    async with AsyncSessionLocal() as db:
        await ApiKeyService.update_key(db,key.id,RouterApiKeyUpdate(quota_rules=[]))
        await ApiKeyService.update_key(db,key.id,RouterApiKeyUpdate(quota_rules=[rule(requests=1)]))
    with pytest.raises(RouterException): await admit(key)
    other=await create()
    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException):
            await ApiKeyService.update_key(db,other.id,RouterApiKeyUpdate(quota_rules=[edited]))
        await db.rollback()


@pytest.mark.asyncio
async def test_direct_model_cache_hit_admission_and_first_dispatch_not_doubled():
    key=await create(rule(scope='model',model='fixture/model',requests=2,tokens=1000))
    with request_log_context({'router_key_id':key.id,'requested_model':'fixture/model','dispatches':[]}):
        await admit(key)  # local HIT still consumes one model request
    assert (await usage(key))[0]['used']=={'requests':1,'tokens':0,'usd':0}
    with request_log_context({'router_key_id':key.id,'requested_model':'fixture/model','dispatches':[]}) as details:
        await admit(key)
        credits = details['quota_direct_pending'].copy()
        assert len(credits) == 1 and len(credits[0]) == 2
        ticket,_=await QuotaService.reserve_dispatch(None,model(),request())
        assert not details['quota_direct_pending']
        await ticket.finish(dispatched=False)  # local pre-dispatch abort restores only request-local credit
        assert details['quota_direct_pending'] == credits
        ticket,_=await QuotaService.reserve_dispatch(None,model(),request())
        await ticket.finish({'prompt_tokens':5,'completion_tokens':5},success=True)
        assert (await usage(key))[0]['used']['requests']==2
        with pytest.raises(RouterException):
            await QuotaService.reserve_dispatch(None,model(),request())  # real retry is another physical call
    with pytest.raises(RouterException): await admit(key)


@pytest.mark.asyncio
async def test_parallel_direct_dispatch_credit_claimed_once():
    key=await create(rule(scope='model',model='fixture/model',requests=2))
    with request_log_context({'router_key_id':key.id,'requested_model':'fixture/model','dispatches':[]}):
        await admit(key)
        results=await asyncio.gather(*(QuotaService.reserve_dispatch(None,model(),request()) for _ in range(8)),return_exceptions=True)
        tickets=[result[0] for result in results if not isinstance(result,BaseException)]
        assert len(tickets)==2
        assert (await usage(key))[0]['used']['requests']==2
        await asyncio.gather(*(ticket.finish(dispatched=False) for ticket in tickets))
        assert (await usage(key))[0]['used']['requests']==1


@pytest.mark.asyncio
async def test_direct_admission_credit_cannot_cross_period_reset(monkeypatch):
    from app.services import quota_service
    now = datetime(2026, 10, 8, 0, 0, 59, tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now
    monkeypatch.setattr(quota_service, 'datetime', Clock)
    key = await create(rule(scope='model', model='fixture/model', period='minute', requests=1))
    with request_log_context({'router_key_id':key.id,'requested_model':'fixture/model','dispatches':[]}):
        await admit(key)
        now += timedelta(seconds=1)
        ticket, _ = await QuotaService.reserve_dispatch(None, model(), request())
        await ticket.finish({'prompt_tokens':5,'completion_tokens':5})
        assert (await usage(key))[0]['used']['requests'] == 1
        with pytest.raises(RouterException):
            await QuotaService.reserve_dispatch(None, model(), request())
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(PeriodQuotaCounter).where(PeriodQuotaCounter.key_id==key.id))).all()
        assert len(rows) == 2 and all(row.requests == 1 for row in rows)


@pytest.mark.asyncio
async def test_native_decision_output_ceiling_and_normalized_usage():
    from app.schemas.jev import JevRequest
    native=JevRequest(model='fixture/model',state='Hi',questions={'a':{'type':'noul','instructions':'Yes?'}})
    key=await create(rule(tokens=1000,usd=1))
    ticket,effective=await reserve(key,req=native)
    assert effective is native
    await ticket.finish({'input_tokens':10,'output_tokens':20},success=True)
    assert (await usage(key))[0]['used']['tokens']==30
    assert (await usage(key))[0]['used']['usd']==pytest.approx(.00005)
    mdl=model(); mdl.max_output_tokens=None
    with pytest.raises(RouterException): await reserve(key,req=native,mdl=mdl)
    small=await create(rule(tokens=150))
    with pytest.raises(RouterException): await reserve(small,req=native)


@pytest.mark.asyncio
async def test_concurrent_reservations_and_cancellation(monkeypatch):
    key=await create(rule(tokens=500))
    results=await asyncio.gather(*(reserve(key) for _ in range(10)),return_exceptions=True)
    tickets=[result[0] for result in results if not isinstance(result,BaseException)]
    assert tickets and all(isinstance(result,RouterException) for result in results if isinstance(result,BaseException))
    assert (await usage(key))[0]['used']['tokens']<=500
    await asyncio.gather(*(ticket.finish(dispatched=False) for ticket in tickets))
    assert (await usage(key))[0]['used']['tokens']==0
    ticket,_=await reserve(key)
    original=QuotaService.settle
    entered,release=asyncio.Event(),asyncio.Event()
    async def paused(*args):
        entered.set()
        await release.wait()
        await original(*args)
    monkeypatch.setattr(QuotaService,'settle',paused)
    task=asyncio.create_task(ticket.finish(dispatched=False))
    await entered.wait()
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError): await task
    assert (await usage(key))[0]['used']['tokens']==0


@pytest.mark.asyncio
async def test_admin_crud_and_usage_validation():
    import httpx
    from fastapi import FastAPI
    from app.api.admin.keys import router
    from app.api.deps import get_current_admin
    from app.core.database import get_db
    app=FastAPI()
    app.include_router(router,prefix='/api/admin')
    app.dependency_overrides[get_current_admin]=lambda: 'synthetic'
    async def isolated_db():
        async with AsyncSessionLocal() as db:
            yield db
    app.dependency_overrides[get_db]=isolated_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        response=await client.post('/api/admin/keys',json={'name':'fixture-admin','quota_rules':[{'requests':3,'usd':1,'tokens':1000}]})
        assert response.status_code==201,response.text
        key_id=response.json()['id']
        rules=response.json()['quota_rules']
        assert rules[0]['id']
        response=await client.get(f'/api/admin/keys/{key_id}/usage')
        assert response.status_code==200 and response.json()[0]['remaining']=={'requests':3,'tokens':1000,'usd':1}
        rules[0]['enabled']=False
        response=await client.put(f'/api/admin/keys/{key_id}',json={'quota_rules':rules})
        assert response.status_code==200 and not response.json()['quota_rules'][0]['enabled']
        response=await client.put(f'/api/admin/keys/{key_id}',json={'quota_rules':[{'usd':'NaN'}]})
        assert response.status_code==422
        response=await client.put(f'/api/admin/keys/{key_id}',json={'quota_rules':[]})
        assert response.status_code==200 and response.json()['quota_rules']==[]
        response=await client.get('/api/admin/keys')
        assert next(k for k in response.json() if k['id']==key_id)['quota_rules']==[]
        assert (await client.delete(f'/api/admin/keys/{key_id}')).status_code==200
        assert (await client.get(f'/api/admin/keys/{key_id}/usage')).status_code==404


def test_migration_fresh_and_representative_upgrade_twice(monkeypatch):
    import os
    import sqlite3
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.core.config import settings
    from app.core.database import engine
    original=Path(engine.url.database).resolve()
    assert original==Path(AsyncSessionLocal.kw['bind'].url.database).resolve()
    assert original.name.startswith('myairouter_test_')
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    for legacy in (False,True):
        path=Path(os.environ['TMPDIR'])/('myairouter_quota_migration_'+uuid.uuid4().hex+'.db')
        assert path.resolve()!=original
        monkeypatch.setattr(settings,'DATABASE_URL','sqlite+aiosqlite:///'+str(path))
        if legacy:
            command.upgrade(config,'o8p9q0r1s2t3')
            with sqlite3.connect(path) as db:
                db.execute("INSERT INTO router_api_keys (name,key_prefix,key_hash,masked_key,enabled,permissions,allowed_models,allowed_routes,allowed_fusions,allowed_judges,total_requests,ip_restrictions,created_at,updated_at) VALUES ('legacy','synthetic','synthetic','synthetic',1,'[]','[\"*\"]','[\"*\"]','[\"*\"]','[\"*\"]',7,'[]','2026-01-01','2026-01-01')")
        command.upgrade(config,'head')
        command.upgrade(config,'head')
        with sqlite3.connect(path) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            assert {'period_quota_counters','period_quota_reservations'}<=tables
            assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]==ScriptDirectory.from_config(config).get_current_head()
            if legacy:
                assert db.execute('SELECT total_requests,quota_rules FROM router_api_keys').fetchone()==(7,'[]')
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
        path.unlink()
    assert Path(engine.url.database).resolve()==original


@pytest.mark.asyncio
async def test_cache_hit_and_unlimited_no_new_writes():
    key=await create(rule(tokens=1000,requests=2))
    await admit(key)  # local response cache HIT: no dispatch
    assert (await usage(key))[0]['used']=={'requests':1,'tokens':0,'usd':0}
    unlimited=await create()
    await admit(unlimited)
    assert (await reserve(unlimited))[0] is None
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(PeriodQuotaCounter).where(PeriodQuotaCounter.key_id==unlimited.id))==0
        assert await db.scalar(select(func.count()).select_from(PeriodQuotaReservation).where(PeriodQuotaReservation.key_id==unlimited.id))==0
