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
    JudgeProfile, JudgeCandidate, PeriodQuotaReservation)
from app.routing.engine import RoutingEngine
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from app.schemas.entities import RouterApiKeyCreate, PeriodQuotaRule
from app.services.api_key_service import ApiKeyService
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
        created=await ApiKeyService.create_key(db,RouterApiKeyCreate(name=slug,quota_rules=rules))
        key=await ApiKeyService.get_key(db,created.id)
        app.dependency_overrides[get_inference_key_dep]=lambda:key
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
            body={'model':model.canonical_slug,'state':'offline','questions':{'q':{'type':'noul','instructions':'ok?'}}}
            response=await client.post('/v1/decisions',json=body)
            assert response.status_code==200,response.text
            stats=await QuotaService.usage(db,key)
            assert all(row['used']=={'requests':1,'tokens':12,'usd':pytest.approx(.000014)} for row in stats)
            assert (await client.post('/v1/systemone',json=body)).status_code==429
            assert calls==[True]
