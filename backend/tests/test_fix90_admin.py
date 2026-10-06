"""Admin-contract checks for fix90; all DB rows belong to the isolated pytest DB."""
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy import select

from app.api.deps import get_current_admin
from app.api.admin import settings as settings_api, providers, credentials, logs, dashboard
from app.core.config import settings
from app.core.crypto import encrypt_secret, compute_fingerprint
from app.core.database import AsyncSessionLocal
from app.models.entities import Provider, ProviderCredential, DiscoveredModel
from app.schemas.entities import CredentialCreate, CredentialUpdate, ProviderCreate, RouterApiKeyCreate, RouterApiKeyUpdate, DiscoveredModelUpdate
from app.services.credential_service import CredentialService
from app.services.api_key_service import ApiKeyService
from app.services.model_discovery_service import ModelDiscoveryService


def app():
    a=FastAPI()
    for route in [settings_api.router,providers.router,credentials.router,logs.router,dashboard.router]:a.include_router(route,prefix='/api/admin')
    a.dependency_overrides[get_current_admin]=lambda:'synthetic-admin'
    return a


async def provider(db,auth_type='bearer',configuration=None):
    p=Provider(name='synthetic',slug='fix90-'+uuid.uuid4().hex,adapter_type='openai',base_url='https://fixture.invalid',auth_type=auth_type,configuration=configuration or {})
    db.add(p);await db.commit();await db.refresh(p);return p


async def credential(db,p):
    return await CredentialService.create_credential(db,CredentialCreate(provider_id=p.id,name='synthetic',api_key='synthetic-'+uuid.uuid4().hex,rpm_limit=5,tpm_limit=10,max_concurrency=2))


@pytest.mark.asyncio
@pytest.mark.parametrize('value,expected', [('false',False),(False,False),('true',True)])
async def test_p11_settings_boolean_contract(value,expected,monkeypatch):
    monkeypatch.setattr(settings,'LOG_REQUEST_CONTENT',True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()),base_url='http://fixture') as client:
        r=await client.post('/api/admin/settings',json={'log_request_content':value})
        assert r.status_code==200 and r.json()['log_request_content'] is expected
        bad=await client.post('/api/admin/settings',json={'log_request_content':{'not':'bool'}})
        assert bad.status_code==422 and settings.LOG_REQUEST_CONTENT is expected


@pytest.mark.asyncio
async def test_p32_key_read_preserves_empty_judge_allowlist():
    async with AsyncSessionLocal() as db:
        key=await ApiKeyService.create_key(db,RouterApiKeyCreate(name='synthetic',allowed_judges=[]))
        assert key.allowed_judges==[]
        again=await ApiKeyService.list_keys(db)
        assert next(k for k in again if k.id==key.id).allowed_judges==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('raw',['','   ','no-key','none','empty','keyless'])
async def test_p43_bearer_rejects_blank_credentials_but_keyless_is_explicit(raw):
    async with AsyncSessionLocal() as db:
        p=await provider(db)
        with pytest.raises(ValueError):await CredentialService.create_credential(db,CredentialCreate(provider_id=p.id,name='synthetic',api_key=raw))
        existing=await credential(db,p)
        with pytest.raises(ValueError):await CredentialService.update_credential(db,existing.id,CredentialUpdate(api_key=raw))
        await db.rollback()
        none=await provider(db,auth_type='none')
        keyless=await CredentialService.create_credential(db,CredentialCreate(provider_id=none.id,name='synthetic-keyless',api_key=raw))
        assert keyless.masked_key=='(Keyless / No Auth)'


@pytest.mark.asyncio
async def test_p45_nullable_credential_limits_reset_only_when_present():
    async with AsyncSessionLocal() as db:
        p=await provider(db);c=await credential(db,p)
        kept=await CredentialService.update_credential(db,c.id,CredentialUpdate(name='renamed'))
        assert (kept.rpm_limit,kept.tpm_limit,kept.max_concurrency)==(5,10,2)
        cleared=await CredentialService.update_credential(db,c.id,CredentialUpdate(rpm_limit=None,tpm_limit=None,max_concurrency=None))
        assert (cleared.rpm_limit,cleared.tpm_limit,cleared.max_concurrency)==(None,None,None)


@pytest.mark.asyncio
async def test_p46_duplicate_provider_is409_and_rollback_keeps_session_usable():
    body={'name':'synthetic','slug':'fix90-'+uuid.uuid4().hex,'adapter_type':'openai','base_url':'https://fixture.invalid'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app(),raise_app_exceptions=False),base_url='http://fixture') as client:
        assert (await client.post('/api/admin/providers',json=body)).status_code==201
        duplicate=await client.post('/api/admin/providers',json=body)
        assert duplicate.status_code==409
        assert (await client.get('/api/admin/providers')).status_code==200


@pytest.mark.asyncio
@pytest.mark.parametrize('path',['/api/admin/logs','/api/admin/logs/summary','/api/admin/dashboard/detailed-stats'])
async def test_p47_bad_log_date_rejected_instead_of_widening_query(path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app(),raise_app_exceptions=False),base_url='http://fixture') as client:
        r=await client.get(path,params={'start_date':'garbage-date'})
        assert r.status_code==422


@pytest.mark.asyncio
async def test_p48_manual_model_credential_belongs_to_provider():
    async with AsyncSessionLocal() as db:
        first=await provider(db);other=await provider(db);c=await credential(db,first)
        with pytest.raises(ValueError):await ModelDiscoveryService.add_model_manually(db,other.id,c.id,'foreign-model','synthetic')
        with pytest.raises(ValueError):await ModelDiscoveryService.add_model_manually(db,other.id,99999999,'missing-model','synthetic')
        result=await ModelDiscoveryService.add_model_manually(db,first.id,c.id,'correct-model','synthetic')
        assert result.provider_id==first.id and result.credential_id==c.id


@pytest.mark.parametrize('field',['input_price_per_1m','output_price_per_1m'])
def test_p50_pricing_nonnegative_finite_or_unknown(field):
    for value in [-1,float('nan'),float('inf')]:
        with pytest.raises(ValidationError):DiscoveredModelUpdate(**{field:value})
    assert getattr(DiscoveredModelUpdate(**{field:None}),field) is None
    assert getattr(DiscoveredModelUpdate(**{field:0}),field)==0


@pytest.mark.asyncio
async def test_p52_nullable_key_limits_reset_only_when_present():
    from datetime import datetime,timezone,timedelta
    async with AsyncSessionLocal() as db:
        key=await ApiKeyService.create_key(db,RouterApiKeyCreate(name='synthetic',rate_limit_rpm=5,rate_limit_tpm=10,request_limit=2,expiration_date=datetime.now(timezone.utc)+timedelta(hours=1)))
        kept=await ApiKeyService.update_key(db,key.id,RouterApiKeyUpdate(name='renamed'))
        assert (kept.rate_limit_rpm,kept.rate_limit_tpm,kept.request_limit)==(5,10,2) and kept.expiration_date
        cleared=await ApiKeyService.update_key(db,key.id,RouterApiKeyUpdate(rate_limit_rpm=None,rate_limit_tpm=None,request_limit=None,expiration_date=None))
        assert (cleared.rate_limit_rpm,cleared.rate_limit_tpm,cleared.request_limit,cleared.expiration_date)==(None,None,None,None)


@pytest.mark.asyncio
async def test_p53_zero_quota_denies_null_is_unlimited():
    async with AsyncSessionLocal() as db:
        denied=await ApiKeyService.create_key(db,RouterApiKeyCreate(name='zero',request_limit=0))
        valid,_,message=await ApiKeyService.authenticate_key(db,denied.raw_api_key)
        assert not valid and 'limit' in message.lower()
        allowed=await ApiKeyService.create_key(db,RouterApiKeyCreate(name='null',request_limit=None))
        assert (await ApiKeyService.authenticate_key(db,allowed.raw_api_key))[0]
