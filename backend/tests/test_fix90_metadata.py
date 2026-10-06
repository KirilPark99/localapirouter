"""Actual metadata routes with isolated DB/auth; zero provider requests."""
import uuid
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import FastAPI
from app.core.database import AsyncSessionLocal
from app.api.v1 import router as api
from app.api import ollama
from app.models.entities import Provider,DiscoveredModel,RoutingProfile,FusionProfile,JudgeProfile
from app.services.api_key_service import ApiKeyService
from app.schemas.entities import RouterApiKeyCreate


def app():
    value=FastAPI();value.include_router(api.router);value.include_router(ollama.router,prefix='/api');return value

async def seed(db,permissions=None,**kw):
    suffix=uuid.uuid4().hex
    provider=Provider(name='synthetic',slug='meta-'+suffix,adapter_type='openai',base_url='https://fixture.invalid')
    db.add(provider);await db.flush()
    model=DiscoveredModel(provider_id=provider.id,provider_model_id='model-'+suffix,canonical_slug=provider.slug+'/model',display_name='synthetic',context_length=4000,max_output_tokens=100)
    route=RoutingProfile(name='synthetic-route',slug='route-'+suffix,context_length=2000)
    fusion=FusionProfile(name='synthetic-fusion',slug='fusion-'+suffix)
    judge=JudgeProfile(name='synthetic-judge',slug='judge-'+suffix)
    db.add_all([model,route,fusion,judge]);await db.commit()
    key=await ApiKeyService.create_key(db,RouterApiKeyCreate(name='synthetic',permissions=permissions or ['*'],**kw))
    return model,route,fusion,judge,key

@pytest.mark.asyncio
async def test_p31_singular_judge_accepted_by_actual_request_boundary(monkeypatch):
    async with AsyncSessionLocal() as db:
        m,r,f,j,key=await seed(db,['judge'])
        from app.schemas.chat import ChatCompletionResponse,ChatCompletionChoice,ChatMessage,UsageInfo
        result=ChatCompletionResponse(id='synthetic',model='judge/'+j.slug,created=1,choices=[ChatCompletionChoice(index=0,message=ChatMessage(role='assistant',content='OK'),finish_reason='stop')],usage=UsageInfo(prompt_tokens=1,completion_tokens=1,total_tokens=2))
        mock=AsyncMock(return_value=result);monkeypatch.setattr(api.JudgeEngine,'execute_judge',mock)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app(),raise_app_exceptions=False),base_url='http://fixture') as client:
            response=await client.post('/v1/chat/completions',headers={'Authorization':'Bearer '+key.raw_api_key},json={'model':'judge/'+j.slug,'messages':[{'role':'user','content':'hello'}]})
        assert response.status_code==200,response.text
        assert mock.await_count==1

@pytest.mark.asyncio
async def test_p32_empty_judge_scope_never_becomes_wildcard_on_http():
    async with AsyncSessionLocal() as db:
        m,r,f,j,key=await seed(db,['judge'],allowed_judges=[])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()),base_url='http://fixture') as client:
            headers={'Authorization':'Bearer '+key.raw_api_key}
            catalog=await client.get('/v1/models',headers=headers)
            assert catalog.status_code==200 and not catalog.json()['data']
            for identifier in [j.slug,'judge/'+j.slug,'smart/'+j.slug]:
                assert (await client.get('/v1/models/'+identifier,headers=headers)).status_code==403

@pytest.mark.asyncio
async def test_p87_wildcard_and_bare_profiles_share_dispatch_guard():
    async with AsyncSessionLocal() as db:
        m,r,f,j,key=await seed(db,['*'])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()),base_url='http://fixture') as client:
            headers={'Authorization':'Bearer '+key.raw_api_key}
            catalog=await client.get('/v1/models',headers=headers)
            assert {m.canonical_slug,'route/'+r.slug,'fusion/'+f.slug,'judge/'+j.slug}<={x['id'] for x in catalog.json()['data']}
            for profile,kind in [(r,'route'),(f,'fusion'),(j,'judge')]:
                for identifier in [profile.slug,kind+'/'+profile.slug]:
                    detail=await client.get('/v1/models/'+identifier,headers=headers)
                    assert detail.status_code==200 and detail.json()['id']==kind+'/'+profile.slug
        denied=await ApiKeyService.create_key(db,RouterApiKeyCreate(name='denied',permissions=['direct'],allowed_models=[]))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()),base_url='http://fixture') as client:
            for profile,kind in [(r,'route'),(f,'fusion'),(j,'judge')]:
                for identifier in [profile.slug,kind+'/'+profile.slug]:
                    assert (await client.get('/v1/models/'+identifier,headers={'Authorization':'Bearer '+denied.raw_api_key})).status_code==403

@pytest.mark.asyncio
async def test_p40_ollama_metadata_requires_auth_and_scope():
    async with AsyncSessionLocal() as db:
        m,r,f,j,key=await seed(db,['routes'],allowed_routes=[],allowed_judges=[])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()),base_url='http://fixture') as client:
            assert (await client.get('/api/tags')).status_code==401
            assert (await client.post('/api/show',json={'name':'route/'+r.slug})).status_code==401
            headers={'Authorization':'Bearer '+key.raw_api_key}
            catalog=await client.get('/api/tags',headers=headers)
            assert catalog.status_code==200 and not catalog.json()['models']
            assert (await client.post('/api/show',headers=headers,json={'name':r.slug})).status_code==403

@pytest.mark.asyncio
async def test_p41_all_advertised_ollama_tags_roundtrip_and_exact_id_wins():
    async with AsyncSessionLocal() as db:
        m,r,f,j,key=await seed(db,['*'])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()),base_url='http://fixture') as client:
            headers={'Authorization':'Bearer '+key.raw_api_key}
            catalog=await client.get('/api/tags',headers=headers)
            ids=[x['name'] for x in catalog.json()['models']]
            assert 'route/'+r.slug+':latest' in ids
            for identifier in ids:
                response=await client.post('/api/show',headers=headers,json={'name':identifier})
                assert response.status_code==200,(identifier,response.text)
            response=await client.post('/api/show',headers=headers,json={'name':'route/'+r.slug+':latest'})
            assert response.json()['model_info']['context_length']==2000

@pytest.mark.asyncio
@pytest.mark.parametrize('bad',[{'name':12}, {'model':[]}, [], None, True])
async def test_p39_ollama_body_rejected_before_lookup(bad):
    async with AsyncSessionLocal() as db:
        *_,key=await seed(db,['*'])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()),base_url='http://fixture') as client:
        result=await client.post('/api/show',headers={'Authorization':'Bearer '+key.raw_api_key},content=__import__('json').dumps(bad))
        assert result.status_code in (400,422),result.text
        broken=await client.post('/api/show',headers={'Authorization':'Bearer '+key.raw_api_key},content='{broken')
        assert broken.status_code==400


@pytest.mark.asyncio
async def test_p49_metadata_authentication_never_debits_generation_quota():
    async with AsyncSessionLocal() as db:
        m,r,f,j,key=await seed(db,['*'],request_limit=1)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()),base_url='http://fixture') as client:
            headers={'Authorization':'Bearer '+key.raw_api_key}
            for path in ['/v1/models','/v1/models/'+m.canonical_slug,'/api/tags']:
                assert (await client.get(path,headers=headers)).status_code==200
            assert (await client.post('/api/show',headers=headers,json={'name':'route/'+r.slug})).status_code==200
        stored=await ApiKeyService.get_key(db,key.id);await db.refresh(stored)
        assert stored.total_requests==0
