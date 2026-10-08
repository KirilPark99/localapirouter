"""Real shared API/dispatch boundaries with synthetic SQLite and HTTP only."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.api.deps import get_inference_key_dep
from app.api.v1.router import router, _native_chat_stream
from app.core.database import AsyncSessionLocal
from app.core.errors import RouterException
from app.core.http_client import http_client_manager
from app.models.entities import (DiscoveredModel, FusionProfile, FusionParticipant,
    JudgeProfile, JudgeCandidate, PeriodQuotaReservation, ProviderCredential,
    CredentialPeriodQuotaReservation)
from app.routing.engine import RoutingEngine
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from app.schemas.entities import RouterApiKeyCreate, PeriodQuotaRule, CredentialUpdate
from app.services.api_key_service import ApiKeyService
from app.services.credential_service import CredentialService
from app.services.quota_service import QuotaService
from test_request_log_telemetry import seed


@pytest.mark.asyncio
async def test_native_stream_does_not_manufacture_missing_usage():
    async def source():
        yield 'data: {"choices":[{"index":0,"delta":{"content":"ok"},"finish_reason":"stop"}],"usage":{"prompt_tokens":7}}\n\n'
        yield 'data: [DONE]\n\n'
    events = [event async for event in _native_chat_stream(source(), 'fixture')]
    assert all(event['usage'] == {'prompt_tokens': 7} for event in events if 'usage' in event)


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('kind', ['reasoning', 'thinking'])
async def test_opaque_history_rejected_before_unrelated_module_dispatch(stream, kind):
    called = []
    async def chat(**kwargs):
        called.append(True)
        return SimpleNamespace(usage=None)
    async def chunks(**kwargs):
        called.append(True)
        yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
    provider = SimpleNamespace(enabled=True, id=1, name='fixture', adapter_type='custom_module', configuration={'module_id':'unrelated'})
    model = SimpleNamespace(enabled=True, available=True, provider_id=1, provider_model_id='fixture', max_output_tokens=20)
    cred = SimpleNamespace(enabled=True, provider_id=1, id=int(uuid4().hex[:8],16), rpm_limit=None,tpm_limit=None,max_concurrency=None)
    request = ChatCompletionRequest(model='fixture', messages=[ChatMessage(role='assistant', reasoning_details=[{'type':kind,'id':'opaque','signature':'opaque','encrypted_content':'opaque'}])])
    adapter = SimpleNamespace(chat_completions=chat,stream_chat=chunks)
    with pytest.raises(RouterException, match='history'):
        if stream:
            _ = [chunk async for chunk in RoutingEngine._dispatch_stream(adapter,cred,provider,model,request=request)]
        else:
            await RoutingEngine._dispatch_chat(adapter,cred,provider,model,request=request)
    assert not called


@pytest.mark.asyncio
@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('endpoint', ['chat/completions', 'responses', 'messages'])
@pytest.mark.parametrize('mode,count', [('direct',1),('route',1),('judge',2),('fusion',3)])
async def test_api_counts_every_physical_dispatch_and_settles_usage(monkeypatch,stream,endpoint,mode,count):
    from fastapi import FastAPI
    app=FastAPI()
    app.include_router(router)
    calls=[]
    usage={'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}
    def upstream(req):
        body=json.loads(req.content)
        calls.append(body)
        evaluating='expert AI Routing Judge' in str(body['messages'])
        text=json.dumps({'selected_candidate_index':0}) if evaluating else 'ok'
        if body['stream']:
            event={'choices':[{'index':0,'delta':{'content':text},'finish_reason':'stop'}],'usage':usage}
            return httpx.Response(200,text='data: '+json.dumps(event)+'\n\ndata: [DONE]\n\n')
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':text},'finish_reason':'stop'}],'usage':usage})
    async with AsyncSessionLocal() as db, httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as provider_client:
        slug=await seed(db)
        model=await db.scalar(select(DiscoveredModel).where(DiscoveredModel.canonical_slug==slug))
        model.canonical_slug='fixture/'+slug
        model.max_output_tokens=50
        model.input_price_per_1m=1.
        model.output_price_per_1m=2.
        target=dict(provider_id=model.provider_id,credential_id=model.credential_id,model_id=model.id)
        judge=await db.scalar(select(JudgeProfile).where(JudgeProfile.slug==slug+'-judge'))
        judge.judge_provider_id,judge.judge_credential_id,judge.judge_model_id=model.provider_id,model.credential_id,model.id
        db.add(JudgeCandidate(profile_id=judge.id,**target))
        fusion=FusionProfile(name=slug,slug=slug+'-fusion',judge_provider_id=model.provider_id,judge_credential_id=model.credential_id,judge_model_id=model.id)
        db.add(fusion)
        await db.flush()
        db.add_all([FusionParticipant(profile_id=fusion.id,**target) for _ in range(2)])
        await db.commit()
        alias=model.canonical_slug if mode=='direct' else mode+'/'+slug+'-'+mode
        rules=[PeriodQuotaRule(requests=3,tokens=100000,usd=1),PeriodQuotaRule(scope='model',model=model.canonical_slug,requests=count,tokens=100000,usd=1)]
        await CredentialService.update_credential(db, model.credential_id, CredentialUpdate(quota_rules=[
            PeriodQuotaRule(requests=count,tokens=100000,usd=1),
            PeriodQuotaRule(scope='model',model=model.canonical_slug,requests=count,tokens=100000,usd=1)]))
        credential=await db.get(ProviderCredential, model.credential_id)
        if mode!='direct':
            rules.append(PeriodQuotaRule(scope='profile',model=alias,requests=3,tokens=100000,usd=1))
        created=await ApiKeyService.create_key(db,RouterApiKeyCreate(name=slug,quota_rules=rules))
        key=await ApiKeyService.get_key(db,created.id)
        app.dependency_overrides[get_inference_key_dep]=lambda:key
        monkeypatch.setattr(http_client_manager,'get_client',AsyncMock(return_value=provider_client))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
            body={'model':alias,'stream':stream,'max_tokens':50,'messages':[{'role':'user','content':'quota integration '+slug}]}
            if endpoint=='responses':
                body={'model':alias,'stream':stream,'max_output_tokens':50,'input':body['messages']}
            response=await client.post('/v1/'+endpoint,json=body)
            assert response.status_code==200,response.text
            assert len(calls)==count,response.text
            stats=await QuotaService.usage(db,key)
            assert stats[0]['used']['requests']==1
            assert stats[1]['used']['requests']==count
            assert all(row['used']['tokens']==count*12 for row in stats)
            assert all(row['used']['usd']==pytest.approx(count*.000014) for row in stats)
            if mode!='direct':
                assert stats[2]['used']['requests']==1
            reservations=(await db.scalars(select(PeriodQuotaReservation).where(PeriodQuotaReservation.key_id==key.id))).all()
            assert len(reservations)==count and all(row.settled for row in reservations)
            provider_stats=await QuotaService.usage(db,credential)
            assert len(provider_stats)==2
            assert all(row['used']=={'requests':count,'tokens':count*12,'usd':pytest.approx(count*.000014)} for row in provider_stats)
            provider_reservations=(await db.scalars(select(CredentialPeriodQuotaReservation).where(CredentialPeriodQuotaReservation.key_id==credential.id))).all()
            assert len(provider_reservations)==count and all(row.settled for row in provider_reservations)
            # A real local response-cache HIT consumes a logical request, not more tokens.
            if mode=='direct':
                response=await client.post('/v1/'+endpoint,json=body)
                assert response.status_code==429  # model request cap also gates cached delivery
                assert len(calls)==count


@pytest.mark.asyncio
async def test_native_decision_api_is_metered(monkeypatch):
    from fastapi import FastAPI
    from app.jev.engine import JevEngine
    app=FastAPI()
    app.include_router(router)
    calls=[]
    async def upstream(*args):
        calls.append(True)
        return {'q': {'type':'noul','answer':True,'probability':1}}, {'input_tokens':10,'output_tokens':2}
    monkeypatch.setattr(JevEngine,'_is_native_jev_provider',staticmethod(lambda *args: True))
    monkeypatch.setattr(JevEngine,'_call_native_jev_upstream',upstream)
    async with AsyncSessionLocal() as db:
        slug=await seed(db)
        model=await db.scalar(select(DiscoveredModel).where(DiscoveredModel.canonical_slug==slug))
        model.canonical_slug='fixture/'+slug
        model.max_output_tokens=50
        model.input_price_per_1m=1.
        model.output_price_per_1m=2.
        await db.commit()
        rules=[PeriodQuotaRule(requests=1,tokens=10000,usd=1),
            PeriodQuotaRule(scope='model',model=model.canonical_slug,requests=1,tokens=10000,usd=1)]
        await CredentialService.update_credential(db,model.credential_id,CredentialUpdate(quota_rules=rules))
        credential=await db.get(ProviderCredential,model.credential_id)
        created=await ApiKeyService.create_key(db,RouterApiKeyCreate(name=slug,quota_rules=rules))
        key=await ApiKeyService.get_key(db,created.id)
        app.dependency_overrides[get_inference_key_dep]=lambda:key
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
            body={'model':model.canonical_slug,'state':'offline','questions':{'q':{'type':'noul','instructions':'ok?'}}}
            response=await client.post('/v1/decisions',json=body)
            assert response.status_code==200,response.text
            stats=await QuotaService.usage(db,key)
            assert all(row['used']=={'requests':1,'tokens':12,'usd':pytest.approx(.000014)} for row in stats)
            assert all(row['used']=={'requests':1,'tokens':12,'usd':pytest.approx(.000014)} for row in await QuotaService.usage(db,credential))
            assert (await client.post('/v1/systemone',json=body)).status_code==429
            assert calls==[True]


@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[False,True])
@pytest.mark.parametrize('fallback',[False,True])
async def test_provider_quota_gates_dispatch_and_preserves_key_fallback(monkeypatch,stream,fallback):
    from fastapi import FastAPI
    from app.core.crypto import encrypt_secret
    from app.core.circuit_breaker import circuit_breaker
    app=FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_inference_key_dep]=lambda:None
    calls=[]
    def upstream(req):
        calls.append(req.headers['authorization'])
        if stream:
            return httpx.Response(200,text='data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'ok'},'finish_reason':'stop'}]})
    async with AsyncSessionLocal() as db, httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as provider_client:
        slug=await seed(db)
        model=await db.scalar(select(DiscoveredModel).where(DiscoveredModel.canonical_slug==slug))
        primary=await CredentialService.get_credential(db,model.credential_id)
        await CredentialService.update_credential(db,primary.id,CredentialUpdate(quota_rules=[PeriodQuotaRule(requests=1)]))
        ticket,_=await QuotaService.reserve_dispatch(primary.provider,model,ChatCompletionRequest(model=slug,messages=[ChatMessage(role='user',content='pre-used')]),credential=primary)
        await ticket.finish({'prompt_tokens':0,'completion_tokens':0})
        before=circuit_breaker.get_status(primary.id)
        if fallback:
            secondary=ProviderCredential(provider_id=primary.provider_id,name=slug+'-second',priority=primary.priority+1,
                encrypted_api_key=encrypt_secret('synthetic-second'),key_fingerprint=slug+'-second',masked_key='synthetic')
            db.add(secondary)
            await db.commit()
            await CredentialService.update_credential(db,secondary.id,CredentialUpdate(quota_rules=[PeriodQuotaRule(requests=1)]))
        monkeypatch.setattr(http_client_manager,'get_client',AsyncMock(return_value=provider_client))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
            response=await client.post('/v1/chat/completions',json={'model':slug,'stream':stream,'messages':[{'role':'user','content':'fallback '+slug}]})
            if fallback:
                assert response.status_code==200 and '"error"' not in response.text,response.text
                assert calls==['Bearer synthetic-second']
                assert (await QuotaService.usage(db,secondary))[0]['used']['requests']==1
            else:
                assert not calls
                assert response.status_code==429 or 'Period requests quota reached' in response.text
            assert (await QuotaService.usage(db,primary))[0]['used']['requests']==1
            assert circuit_breaker.get_status(primary.id)==before


@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[False,True])
async def test_provider_quota_does_not_charge_a_local_cache_hit(monkeypatch,stream):
    from fastapi import FastAPI
    app=FastAPI()
    app.include_router(router)
    calls=[]
    usage={'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}
    def upstream(req):
        calls.append(True)
        if stream:
            return httpx.Response(200,text='data: '+json.dumps({'choices':[{'index':0,'delta':{'content':'ok'},'finish_reason':'stop'}],'usage':usage})+'\n\ndata: [DONE]\n\n')
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'ok'},'finish_reason':'stop'}],'usage':usage})
    async with AsyncSessionLocal() as db, httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as provider_client:
        slug=await seed(db)
        model=await db.scalar(select(DiscoveredModel).where(DiscoveredModel.canonical_slug==slug))
        await CredentialService.update_credential(db,model.credential_id,CredentialUpdate(quota_rules=[PeriodQuotaRule(requests=1)]))
        credential=await db.get(ProviderCredential,model.credential_id)
        created=await ApiKeyService.create_key(db,RouterApiKeyCreate(name=slug,quota_rules=[PeriodQuotaRule(requests=3)]))
        key=await ApiKeyService.get_key(db,created.id)
        app.dependency_overrides[get_inference_key_dep]=lambda:key
        monkeypatch.setattr(http_client_manager,'get_client',AsyncMock(return_value=provider_client))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
            body={'model':slug,'stream':stream,'temperature':0,'messages':[{'role':'user','content':'cached '+slug}]}
            for _ in range(2):
                response=await client.post('/v1/chat/completions',json=body)
                assert response.status_code==200 and '"error"' not in response.text,response.text
            assert response.headers['x-cache']=='HIT'
            assert calls==[True]
            assert (await QuotaService.usage(db,credential))[0]['used']['requests']==1
            assert (await QuotaService.usage(db,key))[0]['used']['requests']==2


@pytest.mark.asyncio
@pytest.mark.parametrize('stream',[False,True])
@pytest.mark.parametrize('limit',[1,2])
async def test_provider_quota_counts_and_bounds_retries_without_router_key(monkeypatch,stream,limit):
    from fastapi import FastAPI
    from app.models.entities import RoutingProfile
    app=FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_inference_key_dep]=lambda:None
    calls=[]
    def upstream(req):
        calls.append(True)
        if len(calls)==1:
            return httpx.Response(503,json={'error':{'message':'synthetic retry'}})
        if stream:
            return httpx.Response(200,text='data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
        return httpx.Response(200,json={'choices':[{'message':{'role':'assistant','content':'ok'},'finish_reason':'stop'}]})
    async with AsyncSessionLocal() as db, httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as provider_client:
        slug=await seed(db)
        model=await db.scalar(select(DiscoveredModel).where(DiscoveredModel.canonical_slug==slug))
        route=await db.scalar(select(RoutingProfile).where(RoutingProfile.slug==slug+'-route'))
        route.retry_count=1
        await db.commit()
        await CredentialService.update_credential(db,model.credential_id,CredentialUpdate(quota_rules=[PeriodQuotaRule(requests=limit)]))
        credential=await db.get(ProviderCredential,model.credential_id)
        monkeypatch.setattr(http_client_manager,'get_client',AsyncMock(return_value=provider_client))
        monkeypatch.setattr(RoutingEngine,'_pause_retry',AsyncMock(return_value=True))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
            response=await client.post('/v1/chat/completions',json={'model':'route/'+route.slug,'stream':stream,'messages':[{'role':'user','content':'retry '+slug}]})
            assert len(calls)==limit
            assert (await QuotaService.usage(db,credential))[0]['used']['requests']==limit
            if limit==2:
                assert response.status_code==200 and '"error"' not in response.text,response.text
            else:
                assert response.status_code==429 or 'Period requests quota reached' in response.text
