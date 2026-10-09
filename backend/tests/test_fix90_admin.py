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


@pytest.mark.asyncio
async def test_preference_endpoint_validation_preserves_current_selection():
    from app.services.provider_service import ProviderService
    async with AsyncSessionLocal() as db:
        own=await provider(db);other=await provider(db);c=await credential(db,own)
        first=DiscoveredModel(provider_id=own.id,provider_model_id='own',canonical_slug='fixture/own',display_name='Own')
        foreign=DiscoveredModel(provider_id=other.id,provider_model_id='foreign',canonical_slug='fixture/foreign',display_name='Foreign')
        db.add_all([first,foreign]);await db.commit()
        cid,mid,fid,pid,other_pid=c.id,first.id,foreign.id,own.id,other.id
        await CredentialService.set_model_preferences(db,cid,[mid])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app(),raise_app_exceptions=False),base_url='http://fixture') as client:
        for credential_id,model_ids in [(cid,[fid]),(cid,[mid,mid]),(cid,[99999999]),(99999999,[mid])]:
            result=await client.post(f'/api/admin/credentials/{credential_id}/preferences',json={'model_ids':model_ids})
            assert result.status_code==400 and result.json()['detail']
            async with AsyncSessionLocal() as db:
                current=await CredentialService.get_credential(db,cid)
                assert [pref.model_id for pref in current.model_preferences]==[mid]
        assert (await client.post(f'/api/admin/credentials/{cid}/preferences',json={'model_ids':[]})).status_code==200
    async with AsyncSessionLocal() as db:
        assert not (await CredentialService.get_credential(db,cid)).model_preferences
        await ProviderService.delete_provider(db,pid)
        await ProviderService.delete_provider(db,other_pid)


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


@pytest.mark.asyncio
async def test_module_profile_settings_types_masks_and_ownership(monkeypatch, tmp_path):
    import json
    from app.api.admin import modules
    from app.core.crypto import decrypt_secret, mask_secret
    from app.modules.base import ModuleManifest
    from app.modules.loader import ModuleLoader, LoadedModule
    manifest = ModuleManifest.model_validate({'id':'fixture_web', 'name':'Fixture', 'version':'1.0',
        'fields':[{'key':'storage_state','label':'Storage','type':'password'}]})
    monkeypatch.setattr(ModuleLoader, '_modules', {'fixture_web':LoadedModule(manifest=manifest)})
    monkeypatch.setattr(ModuleLoader, '_adapters', {})
    monkeypatch.setattr(ModuleLoader, 'sync_with_db', AsyncMock(side_effect=AssertionError('GET must not sync files')))
    a=FastAPI();a.include_router(modules.router,prefix='/api/admin')
    a.dependency_overrides[get_current_admin]=lambda:'synthetic-admin'
    async with AsyncSessionLocal() as db:
        p=Provider(name='fixture',slug='module_fixture_web',adapter_type='custom_module',base_url='module://fixture_web',configuration={'module_id':'fixture_web'})
        db.add(p);await db.commit()
    state={'cookies':[], 'origins':[{'value':'original • state'}]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=a),base_url='http://fixture') as client:
        body={'name':'fixture','fields':{'storage_state':state,'locale':'en','access_token':'synthetic-token-old-A'},'group_name':'group',
            'rpm_limit':5,'tpm_limit':50,'max_concurrency':2,'quota_rules':[{'period':'hour','requests':3}]}
        r=await client.post('/api/admin/modules/fixture_web/profiles',json=body)
        assert r.status_code==201
        ident=r.json()['id'];url=f'/api/admin/modules/fixture_web/profiles/{ident}'
        listed=(await client.get('/api/admin/modules/fixture_web/profiles')).json()[0]
        assert listed['group_name']=='group' and listed['quota_rules'][0]['requests']==3
        assert (listed['rpm_limit'],listed['tpm_limit'],listed['max_concurrency'])==(5,50,2)
        masked=listed['fields']['storage_state']
        assert masked==mask_secret(str(state))
        assert (await client.put(url,json={'fields':{'storage_state':masked,'locale':'ru'}})).status_code==200
        async with AsyncSessionLocal() as db:
            c=await db.get(ProviderCredential,ident)
            assert json.loads(decrypt_secret(c.encrypted_api_key))=={'storage_state':state,'locale':'ru','access_token':'synthetic-token-old-A'}
        stale_token=listed['fields']['access_token']
        async with AsyncSessionLocal() as db:
            c=await db.get(ProviderCredential,ident)
            values=json.loads(decrypt_secret(c.encrypted_api_key))
            values['access_token']='synthetic-token-new-B'
            await CredentialService.update_credential(db,ident,CredentialUpdate(api_key=json.dumps(values)))
        response=await client.put(url,json={'fields':{'access_token':stale_token,'locale':'unchanged'}})
        assert response.status_code==409
        async with AsyncSessionLocal() as db:
            assert json.loads(decrypt_secret((await db.get(ProviderCredential,ident)).encrypted_api_key))['access_token']=='synthetic-token-new-B'
        assert (await client.put(url,json={'fields':{},'notes':'settings-only'})).status_code==200
        async with AsyncSessionLocal() as db:
            legacy=await CredentialService.create_credential(db,CredentialCreate(provider_id=p.id,name='legacy',api_key='synthetic-legacy-secret'))
        listed_legacy=next(row for row in (await client.get('/api/admin/modules/fixture_web/profiles')).json() if row['id']==legacy.id)
        assert listed_legacy['fields']['api_key']==mask_secret('synthetic-legacy-secret')
        assert (await client.put(f'/api/admin/modules/fixture_web/profiles/{legacy.id}',json={'fields':{'api_key':'synthetic-replacement-secret'}})).status_code==200
        async with AsyncSessionLocal() as db:
            assert json.loads(decrypt_secret((await db.get(ProviderCredential,legacy.id)).encrypted_api_key))['api_key']=='synthetic-replacement-secret'
        changed={'cookies':[], 'origins':[{'value':'edited • state'}]}
        assert (await client.put(url,json={'fields':{'storage_state':changed},'rpm_limit':None})).status_code==200
        assert (await client.get('/api/admin/modules')).status_code==200
        async with AsyncSessionLocal() as db:
            c=await db.get(ProviderCredential,ident)
            assert json.loads(decrypt_secret(c.encrypted_api_key))['storage_state']==changed and c.rpm_limit is None
        for method,suffix,payload in [('put','',{'name':'wrong'}),('put','/notes',{'notes':'wrong'}),
                                      ('delete','',None),('post','/test',None),('post','/sync-models',None),('post','/export',None)]:
            response=await client.request(method,f'/api/admin/modules/foreign/profiles/{ident}'+suffix,json=payload)
            assert response.status_code==404
        assert (await client.put(url,json={'quota_rules':[{'scope':'profile','model':'route/foo','requests':1}]})).status_code==422
        async with AsyncSessionLocal() as db:
            c=await db.get(ProviderCredential,ident);c.encrypted_api_key='invalid-synthetic-ciphertext';await db.commit()
        response=await client.put(url,json={'fields':{'locale':'must-not-replace-secret'}})
        assert response.status_code==400
        async with AsyncSessionLocal() as db:
            assert (await db.get(ProviderCredential,ident)).encrypted_api_key=='invalid-synthetic-ciphertext'
            from app.services.provider_service import ProviderService
            await ProviderService.delete_provider(db,p.id)


@pytest.mark.asyncio
async def test_file_backed_token_callback_and_all_config_edits_survive_sync(monkeypatch, tmp_path):
    import json
    from app.core.crypto import decrypt_secret
    from app.modules.base import ModuleManifest
    from app.modules.loader import ModuleLoader, LoadedModule
    from app.modules.profile_loader import sync_profiles_from_disk
    manifest=ModuleManifest(id='codex_cli',name='Fixture Codex',version='1.0')
    monkeypatch.setattr(ModuleLoader,'_modules',{'codex_cli':LoadedModule(manifest=manifest)})
    monkeypatch.setattr(ModuleLoader,'_adapters',{})
    source=tmp_path/'codex_cli'/'account.json';source.parent.mkdir()
    payload={'module':'codex_cli','name':'file callback fixture','fields':{'access_token':'synthetic-old','refresh_token':'synthetic-old-refresh','auto_detect_local':False}}
    source.write_text(json.dumps(payload))
    async with AsyncSessionLocal() as db:
        p=Provider(name='fixture',slug='module_codex_cli',adapter_type='custom_module',base_url='module://codex_cli',configuration={'module_id':'codex_cli'})
        db.add(p);await db.commit()
        assert not (await sync_profiles_from_disk(db,tmp_path))['errors']
        c=(await db.scalars(select(ProviderCredential).where(ProviderCredential.provider_id==p.id))).one()
        ident=c.id
        configuration=CredentialService.module_runtime_configuration(p,c)
    await configuration['persist_credentials']({'access_token':'synthetic-new','refresh_token':'synthetic-new-refresh'})
    async with AsyncSessionLocal() as db:
        await sync_profiles_from_disk(db,tmp_path)
    async with AsyncSessionLocal() as db:
        c=await CredentialService.get_credential(db,ident)
        assert c is not None
        assert json.loads(decrypt_secret(c.encrypted_api_key))['refresh_token']=='synthetic-new-refresh'
        assert 'access_token' not in c.metadata_json
        await CredentialService.bulk_assign_group(db,[ident],'new group')
        await CredentialService.bulk_assign_proxy(db,[ident],None)
        await CredentialService.update_credential_notes(db,ident,'new notes')
        m=DiscoveredModel(provider_id=c.provider_id,provider_model_id='fixture',canonical_slug='codex_cli/fixture',display_name='fixture')
        db.add(m);await db.commit()
        await CredentialService.set_model_preferences(db,ident,[m.id])
        await sync_profiles_from_disk(db,tmp_path)
    async with AsyncSessionLocal() as db:
        c=await CredentialService.get_credential(db,ident)
        assert c is not None
        assert (c.group_name,c.notes)==('new group','new notes')
        assert len(c.model_preferences)==1
        assert json.loads(decrypt_secret(c.encrypted_api_key))['access_token']=='synthetic-new'
        from app.services.backup_service import BackupService
        backup = await BackupService.export_data(db, provider_ids=[c.provider_id], passphrase='synthetic-profile-backup-password')
        result = await BackupService.import_data(db, backup, 'synthetic-profile-backup-password',
            skip_duplicate_credentials=False, auto_discover_models=False)
        assert result['success'] and result['updated_credentials']==1
        await sync_profiles_from_disk(db,tmp_path)
    async with AsyncSessionLocal() as db:
        c=await CredentialService.get_credential(db,ident)
        assert c is not None and c.metadata_json['_file_db_owned']
        assert json.loads(decrypt_secret(c.encrypted_api_key))['refresh_token']=='synthetic-new-refresh'
        assert (c.group_name,c.notes)==('new group','new notes')
        from app.services.provider_service import ProviderService
        await ProviderService.delete_provider(db,c.provider_id)
