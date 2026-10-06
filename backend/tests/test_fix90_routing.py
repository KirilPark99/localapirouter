"""Offline routing regressions; run through the guarded fix90 pytest runner."""
import asyncio
import json
import os
from pathlib import Path
import socket
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, func
from app.core.database import engine, Base, AsyncSessionLocal
DB_PATH = Path(engine.url.database).resolve()
assert DB_PATH == Path(AsyncSessionLocal.kw['bind'].url.database).resolve()
assert DB_PATH == Path(os.environ['DATABASE_URL'].split('///', 1)[1]).resolve()
assert DB_PATH.name.startswith('myairouter_test_')
from app.models.entities import Provider, ProviderCredential, DiscoveredModel, RouterApiKey, RequestLog
from app.schemas.entities import (RoutingProfileCreate, RoutingProfileUpdate, RoutingCandidateInput,
    FusionProfileCreate, FusionProfileUpdate, FusionParticipantInput, JudgeProfileCreate, JudgeProfileUpdate, JudgeCandidateInput)
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ChatCompletionResponse, ChatCompletionChoice, UsageInfo
from app.schemas.jev import JevRequest
from app.core.crypto import encrypt_secret
from app.core.errors import RouterException, ErrorCategory
from app.core.circuit_breaker import circuit_breaker, CircuitBreaker
from app.routing.engine import RoutingEngine
from app.fusion.engine import FusionEngine
from app.judge.engine import JudgeEngine
from app.jev.engine import JevEngine
from app.services.routing_service import RoutingService
from app.services.fusion_service import FusionService
from app.services.judge_service import JudgeService
from app.services.model_limits_service import ModelLimitsService
import app.services.model_limits_service as limits_module
import app.routing.engine as routing
import app.fusion.engine as fusion
import app.judge.engine as judge
import app.jev.engine as jev

POINTS = list(range(24, 31)) + list(range(69, 87)) + [88]

@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[False,True])
async def test_p71_retries_are_not_aborted_by_own_circuit_threshold(stream):
    pid,_,cid,_,mid,_ = await seed()
    calls=[]
    async def chat(**kw):
        calls.append(True)
        if len(calls)<3:
            raise RouterException('synthetic failure',ErrorCategory.UPSTREAM_5XX,status_code=503)
        return response()
    async def chunks(**kw):
        await chat(**kw)
        yield 'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\n'
        yield 'data: [DONE]\n\n'
    from types import SimpleNamespace
    adapter=SimpleNamespace(chat_completions=chat,stream_chat=chunks)
    circuit_breaker.record_failure(cid,ErrorCategory.UPSTREAM_5XX)
    circuit_breaker.record_failure(cid,ErrorCategory.UPSTREAM_5XX)
    async with AsyncSessionLocal() as db:
        provider=await db.get(Provider,pid);credential=await db.get(ProviderCredential,cid);model=await db.get(DiscoveredModel,mid)
        kw=dict(request=request('synthetic/m1'),model_id='m1',retry_count=2)
        if stream:
            result=[x async for x in RoutingEngine._dispatch_stream(adapter,credential,provider,model,**kw)]
            assert result[-1]=='data: [DONE]\n\n'
        else:
            assert (await RoutingEngine._dispatch_chat(adapter,credential,provider,model,**kw)).choices
    assert len(calls)==3 and circuit_breaker.is_available(cid,'m1')[0]


def request(model='route/r', **kw):
    return ChatCompletionRequest(model=model, messages=[ChatMessage(role='user', content='offline prompt')], **kw)

def response(model='m1', content='answer'):
    return ChatCompletionResponse(id='fixture', created=1, model=model,
        choices=[ChatCompletionChoice(index=0, message=ChatMessage(role='assistant', content=content), finish_reason='stop')],
        usage=UsageInfo(prompt_tokens=7, completion_tokens=3, total_tokens=10))

class Adapter:
    def __init__(self):
        self.calls = []
        self.fail = None
        self.content = 'answer'
        self.closed = 0
        self.stream_error = False
        self.wait = None
    async def chat_completions(self, **kw):
        self.calls.append(kw)
        if self.wait:
            await self.wait.wait()
        if self.fail and kw['model_id'] == 'm1':
            raise self.fail
        text = self.content
        if kw['model_id'] == 'm2' and 'Routing Judge' in str(kw['request'].messages):
            text = '{"selected_candidate_index":0}'
        return response(kw['model_id'], text)
    async def stream_chat(self, **kw):
        self.calls.append(kw)
        try:
            if self.fail and kw['model_id']=='m1':
                raise self.fail
            if self.stream_error:
                yield 'data: {"error":{"message":"offline stream failure"}}\n\n'
                yield 'data: [DONE]\n\n'
                return
            yield 'data: '+json.dumps({'choices':[{'delta':{'content':'answer'},'finish_reason':None}], 'usage':None})+'\n\n'
            if self.wait:
                await self.wait.wait()
            yield 'data: '+json.dumps({'choices':[{'delta':{},'finish_reason':'stop'}]})+'\n\n'
            yield 'data: '+json.dumps({'choices':[], 'usage':{'prompt_tokens':7,'completion_tokens':3,'total_tokens':10}})+'\n\n'
            yield 'data: [DONE]\n\n'
        finally:
            self.closed += 1
    def normalize_error(self, exception):
        return exception if isinstance(exception, RouterException) else RouterException(str(exception), ErrorCategory.UPSTREAM_5XX)

async def seed():
    assert engine.url.database == str(DB_PATH) and AsyncSessionLocal.kw['bind'].url.database == str(DB_PATH)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    # Keep the existing session-fixture admin after per-case synthetic DB reset.
    from app.services.auth_service import AuthService
    async with AsyncSessionLocal() as db:
        await AuthService.init_admin_user(db)
    for cid in list(circuit_breaker._statuses):
        circuit_breaker.reset(cid)
    circuit_breaker._model_cooldown_until.clear()
    try:
        from app.core.admission import admission
        admission._states.clear()
    except ImportError:
        pass
    RoutingEngine._round_robin_indices.clear()
    async with AsyncSessionLocal() as db:
        p = Provider(name='Synthetic',slug='synthetic',adapter_type='openai',base_url='http://synthetic.invalid/v1')
        p2 = Provider(name='Other',slug='other',adapter_type='openai',base_url='http://other.invalid/v1')
        db.add_all([p,p2]); await db.flush()
        c = ProviderCredential(provider_id=p.id,name='c1',encrypted_api_key=encrypt_secret('synthetic-one'),key_fingerprint='one',masked_key='synthetic',group_name='A',priority=0)
        c2 = ProviderCredential(provider_id=p.id,name='c2',encrypted_api_key=encrypt_secret('synthetic-two'),key_fingerprint='two',masked_key='synthetic',group_name='B',priority=-1)
        db.add_all([c,c2]); await db.flush()
        m = DiscoveredModel(provider_id=p.id,provider_model_id='m1',canonical_slug='synthetic/m1',display_name='m1')
        m2 = DiscoveredModel(provider_id=p.id,provider_model_id='m2',canonical_slug='synthetic/m2',display_name='m2')
        db.add_all([m,m2]); await db.commit()
        return p.id,p2.id,c.id,c2.id,m.id,m2.id

async def route(db,p,c,m,**kw):
    return await RoutingService.create_profile(db,RoutingProfileCreate(name='r',slug='r',retry_count=0,
        candidates=[RoutingCandidateInput(provider_id=p,credential_id=c,model_id=m)],**kw))
async def ensemble(db,p,c,c2,m,m2,**kw):
    return await FusionService.create_profile(db,FusionProfileCreate(name='f',slug='f',judge_provider_id=p,
        judge_model_id=m2,judge_credential_id=c2,min_successful_candidates=kw.pop("min_successful_candidates",1),
        participants=[FusionParticipantInput(provider_id=p,model_id=m,credential_id=c,temperature=1.3)],**kw))
async def classifier(db,p,c,m,m2,**kw):
    return await JudgeService.create_profile(db,JudgeProfileCreate(name='j',slug='j',judge_provider_id=p,
        judge_model_id=m2,candidates=[JudgeCandidateInput(provider_id=p,model_id=m,credential_id=c,temperature=1.1)],**kw))

def wire_usage(chunks):
    return [json.loads(l[6:])['usage'] for ch in chunks for l in ch.splitlines()
            if l.startswith('data: {') and json.loads(l[6:]).get('usage')]

@pytest.mark.parametrize('point', POINTS)
def test_audit_point(point):
    asyncio.run(run_point(point))

async def run_point(point):
    p,p2,c,c2,m,m2 = await seed()
    adapter = Adapter()
    with patch.object(routing,'get_adapter',lambda _:adapter), patch.object(fusion,'get_adapter',lambda _:adapter), patch.object(judge,'get_adapter',lambda _:adapter), patch.object(jev,'get_adapter',lambda _:adapter):
        async with AsyncSessionLocal() as db:
            if point == 24:
                from fastapi import FastAPI
                import httpx
                from app.api.admin.routes import router as admin_router
                from app.api.deps import get_current_admin
                app = FastAPI(); app.include_router(admin_router)
                app.dependency_overrides[get_current_admin] = lambda: 'synthetic'
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,raise_app_exceptions=False),base_url='http://offline') as client:
                    for prov,model,cred in [(p2,m,c),(99999,99999,None),(p,m,99999)]:
                        out=await client.post('/routes',json={'name':'bad','slug':'bad','candidates':[{'provider_id':prov,'model_id':model,'credential_id':cred}]})
                        assert 400 <= out.status_code < 500
                assert (await db.execute(select(func.count()).select_from(routing.RoutingProfile))).scalar_one() == 0
            elif point in (25,79):
                await RoutingService.create_profile(db,RoutingProfileCreate(name='r',slug='r',retry_count=0,randomize_keys=False,
                    candidates=[RoutingCandidateInput(provider_id=p,model_id=m,credential_id=c2,credential_group='B')]))
                if point==79:
                    provider=await db.get(Provider,p); provider.enabled=False; await db.commit()
                used=[]
                async def emulate(**kw):
                    used.append(kw['api_key']); return {'q':{'type':'noul','answer':True,'probability':1}}, {'input_tokens':1,'output_tokens':1}
                with patch.object(JevEngine,'_emulate_jev_via_adapter',side_effect=emulate):
                    req=JevRequest(model='route/r',state='offline',questions={'q':{'type':'noul','instructions':'q'}})
                    if point==79:
                        with pytest.raises(RouterException): await JevEngine.execute_decision(db,req,record_log=False)
                        assert used==[]
                    else:
                        await JevEngine.execute_decision(db,req,record_log=False)
                        assert used==['synthetic-two']
            elif point==26:
                provider=await db.get(Provider,p); model=await db.get(DiscoveredModel,m)
                for bad in ['not JSON','[]','{"error":{"message":"failure"}}','{"answers":{}}','{"answers":{"q":{"answer":"true"}}}']:
                    adapter.content=bad
                    with pytest.raises(RouterException):
                        await JevEngine._emulate_jev_via_adapter(provider,'synthetic',model,JevRequest(model='m1',state='offline',questions={'q':{'type':'noul','instructions':'q'}}))
            elif point==27:
                prof=await classifier(db,p,c,m,m2)
                key=RouterApiKey(permissions=['judge'],allowed_judges=['j'],allowed_models=[],allowed_routes=[])
                await JudgeEngine.execute_judge(db,request('judge/j'),router_key=key)
                await JudgeService.update_profile(db,prof.id,JudgeProfileUpdate(candidates=[JudgeCandidateInput(provider_id=p,model_id=m,credential_group='B')]))
                db.expire_all()
                await JudgeEngine.execute_judge(db,request('judge/j'),router_key=key)
                assert adapter.calls[-1]['api_key']=='synthetic-two'
            elif point==28:
                for cls,kw in [(FusionProfileCreate,{'name':'f','slug':'f'}),(FusionProfileUpdate,{})]:
                    for field in ('max_parallelism','min_successful_candidates','timeout_seconds'):
                        with pytest.raises(ValueError): cls(**kw,**{field:0})
                with pytest.raises(ValueError):
                    await ensemble(db,p,c,c2,m,m2,max_parallelism=1,min_successful_candidates=2)
            elif point==29:
                await ensemble(db,p,c,c2,m,m2)
                started=asyncio.Event(); stopped=asyncio.Event()
                async def participant(*args,**kw):
                    started.set()
                    try: await asyncio.Event().wait()
                    finally: stopped.set()
                with patch.object(FusionEngine,'_execute_single_participant',side_effect=participant):
                    gen=FusionEngine.execute_fusion_stream(db,request('fusion/f'))
                    await anext(gen)
                    task=asyncio.create_task(anext(gen)); await started.wait(); task.cancel()
                    with pytest.raises(asyncio.CancelledError): await task
                    await gen.aclose()
                    assert stopped.is_set()
            elif point==30:
                await classifier(db,p,c,m,m2)
                circuit_breaker.record_failure(c,ErrorCategory.AUTH_ERROR)
                chunks=[x async for x in JudgeEngine.execute_judge_stream(db,request('judge/j'))]
                assert adapter.calls==[] and any('error' in x for x in chunks)
            elif point in (69,70):
                await route(db,p,c,m,timeout_seconds=1)
                await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                if point==69:
                    prof = await RoutingService.get_profile_by_slug(db, 'route/r')
                    await RoutingService.create_profile(db, RoutingProfileCreate(name='outer',slug='outer',
                        candidates=[RoutingCandidateInput(candidate_type='profile',target_profile_id=prof.id)]))
                    await RoutingEngine.route_chat_completions(db,request('route/outer'),record_log=False)
                    assert (await db.execute(select(func.count()).select_from(RequestLog))).scalar_one()==0
                else:
                    assert adapter.calls[-1]['timeout']==1
                    chunks=[x async for x in RoutingEngine.route_stream_chat(db,request(),record_log=False)]
                    assert adapter.calls[-1]['timeout']==1 and wire_usage(chunks)[-1]['total_tokens']==10
            elif point==71:
                await RoutingService.create_profile(db,RoutingProfileCreate(name='r',slug='r',retry_count=2,candidates=[RoutingCandidateInput(provider_id=p,credential_id=c,model_id=m)]))
                adapter.fail=RouterException('offline retry',ErrorCategory.UPSTREAM_5XX)
                with pytest.raises(RouterException): await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                assert len(adapter.calls)==3
                circuit_breaker.reset(c); adapter.calls.clear()
                chunks=[x async for x in RoutingEngine.route_stream_chat(db,request(),record_log=False)]
                assert len(adapter.calls)==3 and any('error' in x for x in chunks)
                circuit_breaker.reset(c); adapter.calls.clear(); adapter.fail=RouterException('bad request',ErrorCategory.INVALID_REQUEST)
                with pytest.raises(RouterException): await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                assert len(adapter.calls)==1
            elif point==72:
                await RoutingService.create_profile(db,RoutingProfileCreate(name='r',slug='r',retry_count=0,fallback_conditions=['RATE_LIMIT'],candidates=[RoutingCandidateInput(provider_id=p,credential_id=c,model_id=m),RoutingCandidateInput(provider_id=p,credential_id=c2,model_id=m2)]))
                adapter.fail=RouterException('bad request',ErrorCategory.INVALID_REQUEST)
                with pytest.raises(RouterException): await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                assert len(adapter.calls)==1
                adapter.calls.clear()
                chunks=[x async for x in RoutingEngine.route_stream_chat(db,request(),record_log=False)]
                assert any('error' in x for x in chunks)
                assert len(adapter.calls)==1
            elif point==73:
                await route(db,p,c,m)
                for cid in (c,c2): circuit_breaker.record_failure(cid,ErrorCategory.AUTH_ERROR)
                for model in ('route/r','synthetic/m1'):
                    with pytest.raises(RouterException): await RoutingEngine.route_chat_completions(db,request(model),record_log=False)
                assert adapter.calls==[]
            elif point==74:
                candidates=[RoutingCandidateInput(provider_id=p,credential_id=c,model_id=m,priority_order=9),RoutingCandidateInput(provider_id=p,credential_id=c2,model_id=m2,priority_order=2)]
                prof=await RoutingService.create_profile(db,RoutingProfileCreate(name='r',slug='r',candidates=candidates))
                await RoutingService.update_profile(db,prof.id,RoutingProfileUpdate(candidates=candidates))
                db.expire_all(); saved=await RoutingService.get_profile(db,prof.id)
                assert [x.priority_order for x in saved.candidates]==[2,9]
            elif point==75:
                cb=CircuitBreaker(); cb.record_failure(1,ErrorCategory.RATE_LIMIT,120,'insufficient_quota','m1'); cb.record_success(1,'m2')
                assert not cb.is_available(1,'m1')[0] and not cb.is_available(1,'m2')[0]
            elif point in (76,77,78):
                await ensemble(db,p,c,c2,m,m2,temperature=1.2)
                if point==76:
                    await FusionEngine.execute_fusion(db,request('fusion/f',temperature=0))
                    assert [x['request'].temperature for x in adapter.calls]==[0,0]
                    adapter.calls.clear(); await classifier(db,p,c,m,m2)
                    await JudgeEngine.execute_judge(db,request('judge/j',temperature=0))
                    assert adapter.calls[-1]['request'].temperature==0
                    adapter.calls.clear()
                    [x async for x in FusionEngine.execute_fusion_stream(db,request('fusion/f',temperature=0))]
                    assert [x['request'].temperature for x in adapter.calls]==[0,0]
                    adapter.calls.clear()
                    [x async for x in JudgeEngine.execute_judge_stream(db,request('judge/j',temperature=0))]
                    assert adapter.calls[-1]['request'].temperature==0
                elif point==77:
                    chunks=[x async for x in FusionEngine.execute_fusion_stream(db,request('fusion/f',max_completion_tokens=17))]
                    assert adapter.calls[-1]['request'].get_effective_max_tokens()==17
                    assert wire_usage(chunks)[-1]['total_tokens']==20
                else:
                    adapter.content=''
                    with pytest.raises(RouterException): await FusionEngine.execute_fusion(db,request('fusion/f'))
                    assert len(adapter.calls)==1
            elif point==80:
                prof=await classifier(db,p,c,m,m2,judge_credential_id=c,context_length=123)
                await JudgeService.update_profile(db,prof.id,JudgeProfileUpdate(judge_credential_id=None,context_length=None,judge_temperature=None))
                db.expire_all(); saved=await JudgeService.get_profile(db,prof.id)
                assert saved.judge_credential_id is None and saved.context_length is None and saved.judge_temperature is None
            elif point==81:
                from app.core.admission import admission
                from concurrent.futures import ThreadPoolExecutor
                def reserve():
                    try: return admission.reserve('test',1,rpm=1)
                    except RouterException: return None
                with ThreadPoolExecutor(max_workers=8) as pool: reservations=list(pool.map(lambda _:reserve(),range(8)))
                assert sum(x is not None for x in reservations)==1
                [x.finish() for x in reservations if x]
                a=admission.reserve('test',2,tpm=10,tokens=8); a.finish(actual_tokens=4); a.finish(actual_tokens=0)
                b=admission.reserve('test',2,tpm=10,tokens=6); b.finish()
                with pytest.raises(RouterException): admission.reserve('test',2,tpm=10,tokens=1)
                cred=await db.get(ProviderCredential,c); cred.max_concurrency=1; await db.commit()
                await route(db,p,c,m)
                adapter.wait=asyncio.Event()
                gen=RoutingEngine.route_stream_chat(db,request())
                await anext(gen)
                with pytest.raises(RouterException) as exc: await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                assert exc.value.status_code==429
                await gen.aclose(); await asyncio.sleep(0)
                adapter.wait=None
                await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                assert adapter.closed==1
                cred.rpm_limit=1; await db.commit(); admission._states.clear()
                await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                with pytest.raises(RouterException): await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                cred.rpm_limit=None; cred.tpm_limit=1; await db.commit(); admission._states.clear()
                with pytest.raises(RouterException): await RoutingEngine.route_chat_completions(db,request(),record_log=False)
            elif point==82:
                await RoutingService.create_profile(db,RoutingProfileCreate(name='r',slug='r',retry_count=0,randomize_keys=False,candidates=[RoutingCandidateInput(provider_id=p,model_id=m)]))
                with patch.object(routing.random,'shuffle') as shuffle:
                    await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                    assert not shuffle.called
                    [x async for x in RoutingEngine.route_stream_chat(db,request(),record_log=False)]
                    assert not shuffle.called
            elif point==83:
                await RoutingService.create_profile(db,RoutingProfileCreate(name='r',slug='r',retry_count=0,strategy='round_robin',candidates=[RoutingCandidateInput(provider_id=p,credential_id=c,model_id=m),RoutingCandidateInput(provider_id=p,credential_id=c2,model_id=m2)]))
                for _ in range(3): await RoutingEngine.route_chat_completions(db,request(),record_log=False)
                assert [x['model_id'] for x in adapter.calls]==['m1','m2','m1']
                adapter.calls.clear(); RoutingEngine._round_robin_indices.clear()
                for _ in range(3): [x async for x in RoutingEngine.route_stream_chat(db,request(),record_log=False)]
                assert [x['model_id'] for x in adapter.calls]==['m1','m2','m1']
            elif point==84:
                await classifier(db,p,c,m,m2); adapter.stream_error=True
                chunks=[x async for x in JudgeEngine.execute_judge_stream(db,request('judge/j'),request_id='failed')]
                log=(await db.execute(select(RequestLog).where(RequestLog.request_id=='failed'))).scalar_one()
                assert log.status=='FAILED' and log.status_code>=400 and any('error' in x for x in chunks)
            elif point==85:
                await JudgeService.create_profile(db,JudgeProfileCreate(name='j',slug='j',judge_provider_id=p,judge_model_id=m2,
                    candidates=[JudgeCandidateInput(provider_id=p,credential_id=c,model_id=m),JudgeCandidateInput(provider_id=p,credential_id=c2,model_id=m2)]))
                out=await JudgeEngine.execute_judge(db,request('judge/j'),request_id='usage')
                log=(await db.execute(select(RequestLog).where(RequestLog.request_id=='usage'))).scalar_one()
                assert out.usage.total_tokens==20 and log.input_tokens+log.output_tokens==20
                chunks=[x async for x in JudgeEngine.execute_judge_stream(db,request('judge/j'))]
                assert wire_usage(chunks)[-1]['total_tokens']==20
            elif point==86:
                import httpx
                provider=await db.get(Provider,p); provider.slug='typesafe'; await db.commit()
                client=httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(429,json={'error':{'message':'offline rate'}},headers={'Retry-After':'120'})))
                with patch.object(jev.http_client_manager,'get_client',AsyncMock(return_value=client)):
                    with pytest.raises(RouterException) as exc:
                        await JevEngine.execute_decision(db,JevRequest(model='synthetic/m1',state='offline',questions={'q':{'type':'noul','instructions':'q'}}),record_log=False)
                    assert exc.value.category==ErrorCategory.RATE_LIMIT and exc.value.retry_after==120
                    assert not circuit_breaker.is_available(c,'m1')[0]
                await client.aclose()
            elif point==88:
                model=(await RoutingEngine._get_candidate_credentials_for_model(db,'synthetic/m1'))[0][1]
                cred=await db.get(ProviderCredential,c)
                from app.schemas.entities import ModelLimitsRead
                limits_module._live_limits_cache[model.id]=ModelLimitsRead(model_id=m,provider_model_id='m1',canonical_slug='synthetic/m1',provider_slug='synthetic',rate_limit_rpm=1)
                cred.rpm_limit=42
                assert ModelLimitsService.compute_model_limits_fast(model,cred).rate_limit_rpm==42
                cred.rpm_limit=None
                assert ModelLimitsService.compute_model_limits_fast(model,cred).rate_limit_rpm==1
                limits_module._live_limits_cache.clear()
    await engine.dispose()


def test_permissions_31_32():
    for engine_cls, name in [(RoutingEngine,'judge/j'),(JudgeEngine,'j')]:
        key=RouterApiKey(permissions=['judge'],allowed_judges=['j'])
        engine_cls._check_permissions(key,name)
        key.allowed_judges=[]
        with pytest.raises(RouterException): engine_cls._check_permissions(key,name)


def test_admission_window_config_and_bounded_memory():
    from app.core.admission import Admission
    guard=Admission()
    with patch('app.core.admission.monotonic',return_value=100):
        first=guard.reserve('credential',1,rpm=2,tpm=8,tokens=4,concurrency=1)
        with pytest.raises(RouterException): guard.reserve('credential',1,rpm=99,tpm=99,concurrency=1)
        first.finish(actual_tokens=5); first.finish(actual_tokens=0)
        second=guard.reserve('credential',1,rpm=2,tpm=8,tokens=3)
        second.finish()
        # Changing config must not erase the existing budget.
        with pytest.raises(RouterException): guard.reserve('credential',1,rpm=1)
        with pytest.raises(RouterException): guard.reserve('credential',1,tpm=8,tokens=1)
        other=guard.reserve('router-key',1,rpm=1); other.finish()
    with patch('app.core.admission.monotonic',return_value=161):
        guard.reserve('credential',1,rpm=1,tpm=1,tokens=1).finish()
    limited=Admission(); limited._MAX_ENTRIES=2
    with patch('app.core.admission.monotonic',return_value=100):
        a=limited.reserve('credential',1,rpm=1)
        with pytest.raises(RouterException): limited.reserve('credential',2)
        a.finish()
        with pytest.raises(RouterException): limited.reserve('credential',2)
    with patch('app.core.admission.monotonic',return_value=161):
        limited.reserve('credential',2).finish()


def test_stream_abort_cancel_and_fusion_aclose():
    asyncio.run(_stream_abort_cancel_and_fusion_aclose())

async def _stream_abort_cancel_and_fusion_aclose():
    p,p2,c,c2,m,m2=await seed()
    adapter=Adapter()
    with patch.object(routing,'get_adapter',lambda _:adapter),patch.object(fusion,'get_adapter',lambda _:adapter):
        async with AsyncSessionLocal() as db:
            cred=await db.get(ProviderCredential,c);cred.max_concurrency=1;await db.commit()
            await route(db,p,c,m)
            adapter.wait=asyncio.Event()
            async def consume():
                async for _ in RoutingEngine.route_stream_chat(db,request(),record_log=False):
                    pass
            task=asyncio.create_task(consume())
            while not adapter.calls: await asyncio.sleep(0)
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass
            from app.core.admission import admission
            assert admission._states[('credential',c)]['active']==0 and adapter.closed==1
            adapter.wait=None
            await RoutingEngine.route_chat_completions(db,request(),record_log=False)
            prof=await FusionService.create_profile(db,FusionProfileCreate(name='f',slug='f',judge_provider_id=p,
                judge_model_id=m2,judge_credential_id=c2,min_successful_candidates=1,
                participants=[FusionParticipantInput(provider_id=p,model_id=m,credential_id=c),
                              FusionParticipantInput(provider_id=p,model_id=m2,credential_id=c2)]))
            started=asyncio.Event(); stopped=asyncio.Event()
            async def participant(idx,*args,**kw):
                if idx==0:
                    await started.wait()
                    return dict(idx=0,label='A',content='draft',error=None,latency_ms=0,prompt_tokens=1,
                        completion_tokens=1,model_name='m1',provider_name='Synthetic',credential_name='c1',http_status=200)
                started.set()
                try: await asyncio.Event().wait()
                finally: stopped.set()
            with patch.object(FusionEngine,'_execute_single_participant',side_effect=participant):
                gen=FusionEngine.execute_fusion_stream(db,request('fusion/f'))
                await anext(gen);await anext(gen)
                await gen.aclose()
                assert stopped.is_set()
    await engine.dispose()


def test_direct_stream_terminal_and_usage_null():
    asyncio.run(_direct_stream_terminal_and_usage_null())

async def _direct_stream_terminal_and_usage_null():
    p,p2,c,c2,m,m2=await seed()
    adapter=Adapter()
    with patch.object(routing,'get_adapter',lambda _:adapter):
        async with AsyncSessionLocal() as db:
            await route(db,p,c,m)
            async def truncated(**kw):
                yield 'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}],"usage":null}\n\n'
            with patch.object(adapter,'stream_chat',truncated):
                chunks=[x async for x in RoutingEngine.route_stream_chat(db,request(),record_log=False)]
                assert any('error' in chunk for chunk in chunks)
            async def no_usage(**kw):
                yield 'data: {"choices":[{"delta":{"content":"answer"},"finish_reason":null}],"usage":null}\n\n'
                yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":null}\n\n'
                yield 'data: [DONE]\n\n'
            circuit_breaker.reset(c)
            with patch.object(adapter,'stream_chat',no_usage):
                chunks=[x async for x in RoutingEngine.route_stream_chat(db,request(),record_log=False)]
                assert wire_usage(chunks) and wire_usage(chunks)[-1]['total_tokens']>0
    await engine.dispose()


def test_owned_schema_boundaries():
    for schema,base in [(RoutingProfileCreate,{'name':'r','slug':'r'}),(RoutingProfileUpdate,{}),
                        (JudgeProfileCreate,{'name':'j','slug':'j'}),(JudgeProfileUpdate,{}),
                        (FusionProfileCreate,{'name':'f','slug':'f'}),(FusionProfileUpdate,{})]:
        for bad in (0,-1,float('inf'),float('nan')):
            with pytest.raises(ValueError): schema(**base,timeout_seconds=bad)
        for bad in (-1,float('inf'),float('nan'),3):
            field='judge_temperature' if schema in (JudgeProfileCreate,JudgeProfileUpdate) else 'temperature'
            with pytest.raises(ValueError): schema(**base,**{field:bad})
    for bad in (-1,11):
        with pytest.raises(ValueError): RoutingProfileUpdate(retry_count=bad)


def test_mocktransport_common_dispatch():
    asyncio.run(_mocktransport_common_dispatch())

async def _mocktransport_common_dispatch():
    import httpx
    from app.adapters.openai import GenericOpenAIAdapter
    p,p2,c,c2,m,m2=await seed()
    seen=[]
    def transport(req):
        seen.append(json.loads(req.content))
        if seen[-1].get('stream'):
            return httpx.Response(200,headers={'content-type':'text/event-stream'},content=(
                'data: {"id":"offline","choices":[{"index":0,"delta":{"content":"answer"},"finish_reason":null}]}\n\n'
                'data: {"id":"offline","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":7,"completion_tokens":3,"total_tokens":10}}\n\n'
                'data: [DONE]\n\n'))
        return httpx.Response(200,json=response().model_dump())
    client=httpx.AsyncClient(transport=httpx.MockTransport(transport))
    adapter=GenericOpenAIAdapter()
    with patch.object(routing,'get_adapter',lambda _:adapter),patch.object(routing,'settings',routing.settings),patch('app.core.http_client.http_client_manager.get_client',AsyncMock(return_value=client)):
        async with AsyncSessionLocal() as db:
            await route(db,p,c,m,timeout_seconds=1)
            await RoutingEngine.route_chat_completions(db,request(),record_log=False)
            chunks=[x async for x in RoutingEngine.route_stream_chat(db,request(),record_log=False)]
            assert len(seen)==2 and wire_usage(chunks)[-1]['total_tokens']==10
    await client.aclose();await engine.dispose()


def test_concurrent_credential_tpm_and_stream_cancel():
    asyncio.run(_concurrent_credential_tpm_and_stream_cancel())

async def _concurrent_credential_tpm_and_stream_cancel():
    from app.core.admission import admission
    from app.compression.tokenizer import count_messages_tokens
    p,p2,c,c2,m,m2=await seed()
    adapter=Adapter(); started=asyncio.Event(); stopped=asyncio.Event()
    async def partial(**kw):
        adapter.calls.append(kw)
        try:
            yield 'data: {"choices":[],"usage":{"prompt_tokens":4,"completion_tokens":1,"total_tokens":5}}\n\n'
            started.set()
            await asyncio.Event().wait()
        finally: stopped.set()
    with patch.object(routing,'get_adapter',lambda _:adapter),patch.object(adapter,'stream_chat',partial):
        async with AsyncSessionLocal() as db:
            cred=await db.get(ProviderCredential,c);cred.tpm_limit=100;cred.max_concurrency=2
            model=await db.get(DiscoveredModel,m);model.max_output_tokens=60
            await db.commit();await route(db,p,c,m)
            async def consume():
                async for _ in RoutingEngine.route_stream_chat(db,request(),record_log=False):pass
            task=asyncio.create_task(consume());await started.wait()
            assert adapter.calls[0]['request'].get_effective_max_tokens()==60
            assert admission._states[('credential',c)]['events'][0][1]==count_messages_tokens(request().messages)+60
            # A second concurrent request must not spend the first stream's output reservation.
            with pytest.raises(RouterException) as error:
                await RoutingEngine.route_chat_completions(db,request(),record_log=False)
            assert error.value.status_code==429 and len(adapter.calls)==1
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
            state=admission._states[('credential',c)]
            assert stopped.is_set() and state['active']==0 and state['events'][0][1]==5
            admission._states.clear();adapter.calls.clear()
            model.max_output_tokens=None;await db.commit()
            await RoutingEngine.route_chat_completions(db,request(),record_log=False)
            assert adapter.calls[0]['request'].get_effective_max_tokens()==100-count_messages_tokens(request().messages)
    await engine.dispose()


def test_developer_defaults_preserve_role():
    from types import SimpleNamespace
    req=ChatCompletionRequest(model='s/m1',messages=[{'role':'developer','content':'policy'},{'role':'user','content':'question'}])
    model=SimpleNamespace(system_prompt='model default',temperature=None,thinking_effort=None,max_output_tokens=None)
    result=RoutingEngine._apply_model_defaults(req,model)
    assert result.messages[0].role=='developer' and result.messages[0].content=='policy'
    assert not any(message.role=='system' for message in result.messages)
