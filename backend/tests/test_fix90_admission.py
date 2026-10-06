"""Point10/49: actual key admission before dispatch; no provider/network calls."""
import asyncio,uuid
import pytest,httpx
from fastapi import FastAPI
from sqlalchemy import select
from app.api.v1 import router as api
from app.core.database import AsyncSessionLocal
from app.core.admission import Admission
import app.core.admission as admission_module
from app.models.entities import Provider,DiscoveredModel
from app.schemas.entities import RouterApiKeyCreate
from app.schemas.chat import ChatCompletionResponse,ChatCompletionChoice,ChatMessage,UsageInfo
from app.services.api_key_service import ApiKeyService

@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(admission_module,'admission',Admission())
    state={'calls':0}
    async def respond(*args,**kwargs):
        state['calls']+=1
        return ChatCompletionResponse(model='synthetic',choices=[ChatCompletionChoice(message=ChatMessage(role='assistant',content='OK'),finish_reason='stop')],usage=UsageInfo(prompt_tokens=1,completion_tokens=1,total_tokens=2))
    monkeypatch.setattr(api.RoutingEngine,'route_chat_completions',respond)
    app=FastAPI();app.include_router(api.router)
    return app,state

async def seed(**fields):
    async with AsyncSessionLocal() as db:
        slug='admit-'+uuid.uuid4().hex
        p=Provider(name='synthetic',slug=slug,adapter_type='openai',base_url='https://fixture.invalid');db.add(p);await db.flush()
        m=DiscoveredModel(provider_id=p.id,provider_model_id='model',canonical_slug=slug+'/model',display_name='synthetic');db.add(m);await db.commit()
        key=await ApiKeyService.create_key(db,RouterApiKeyCreate(name='synthetic',**fields))
        return m.canonical_slug,key

def body(model):return {'model':model,'max_tokens':1,'messages':[{'role':'user','content':'hello'}]}

@pytest.mark.asyncio
async def test_p10_rpm_rejects_before_dispatch_and_metadata_does_not_spend(setup):
    app,state=setup;model,key=await seed(rate_limit_rpm=1)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as c:
        headers={'Authorization':'Bearer '+key.raw_api_key}
        assert (await c.get('/v1/models',headers=headers)).status_code==200
        assert (await c.post('/v1/chat/completions',headers=headers,json=body(model))).status_code==200
        denied=await c.post('/v1/chat/completions',headers=headers,json=body(model))
        assert denied.status_code==429 and state['calls']==1

@pytest.mark.asyncio
async def test_p10_tpm_rejects_before_dispatch_and_reconciles_real_usage(setup):
    app,state=setup;model,key=await seed(rate_limit_tpm=1)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as c:
        denied=await c.post('/v1/chat/completions',headers={'Authorization':'Bearer '+key.raw_api_key},json=body(model))
        assert denied.status_code==429 and state['calls']==0
        model,key=await seed(rate_limit_tpm=100)
        assert (await c.post('/v1/chat/completions',headers={'Authorization':'Bearer '+key.raw_api_key},json=body(model))).status_code==200
    state=admission_module.admission._states[('router-key',key.id)]
    assert state['active']==0 and state['events'][-1][1]==2

@pytest.mark.asyncio
@pytest.mark.parametrize('ip,allowed',[('127.0.0.1/32',True),('203.0.113.0/24',False),('::1/128',False)])
async def test_p10_ip_restriction_uses_actual_peer_not_forged_forwarded_header(setup,ip,allowed):
    app,state=setup;model,key=await seed(ip_restrictions=[ip])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('127.0.0.1',1234)),base_url='http://fixture') as c:
        result=await c.post('/v1/chat/completions',headers={'Authorization':'Bearer '+key.raw_api_key,'X-Forwarded-For':ip.split('/')[0]},json=body(model))
    assert result.status_code==(200 if allowed else 403)
    assert state['calls']==int(allowed)

@pytest.mark.asyncio
async def test_p49_quota_atomic_when_concurrent_authentication_passed(setup):
    app,state=setup;model,key=await seed(request_limit=1)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as c:
        results=await asyncio.gather(*[c.post('/v1/chat/completions',headers={'Authorization':'Bearer '+key.raw_api_key},json=body(model)) for _ in range(2)])
    assert sum(r.status_code==200 for r in results)==1 and state['calls']==1
    async with AsyncSessionLocal() as db:
        assert (await ApiKeyService.get_key(db,key.id)).total_requests==1

def test_p10_invalid_ip_rejected_at_write_boundary():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):RouterApiKeyCreate(name='synthetic',ip_restrictions=['not-an-ip'])
