"""Point64: actual handler refresh persists rotated JSON through encrypted storage."""
import asyncio,json,uuid
from urllib.parse import parse_qs
from unittest.mock import patch
import httpx,pytest
from app.core.database import AsyncSessionLocal
from app.core.crypto import encrypt_secret,decrypt_secret
from app.models.entities import Provider,ProviderCredential
from app.services.credential_service import CredentialService
from modules.codex_cli.handler import CodexCliAdapter
from modules.grok_builder_cli.handler import GrokBuilderCliAdapter

@pytest.mark.asyncio
@pytest.mark.parametrize('module_id,cls',[('codex_cli',CodexCliAdapter),('grok_builder_cli',GrokBuilderCliAdapter)])
@pytest.mark.parametrize('nested',[False,True])
async def test_p64_rotated_refresh_survives_fresh_handler_and_is_never_plaintext(module_id,cls,nested,monkeypatch):
    payload={'access_token':'synthetic-old-access','refresh_token':'synthetic-old-refresh','auto_detect_local':False,'untouched':'keep'}
    if nested:
        data={'tokens':{'access_token':payload['access_token'],'refresh_token':payload['refresh_token'],'account_id':'synthetic-account'}} if module_id=='codex_cli' else {'synthetic':{'key':payload['access_token'],'refresh_token':payload['refresh_token'],'email':'synthetic@example.invalid'}}
        payload['auth_json']=json.dumps(data)
    async with AsyncSessionLocal() as db:
        p=Provider(name='synthetic',slug='refresh-'+uuid.uuid4().hex,adapter_type='custom_module',base_url='https://fixture.invalid',configuration={'module_id':module_id})
        db.add(p);await db.flush()
        c=ProviderCredential(provider_id=p.id,name='synthetic',encrypted_api_key=encrypt_secret(json.dumps(payload)),key_fingerprint=uuid.uuid4().hex,masked_key='synthetic',metadata_json={'health':'keep'})
        db.add(c);await db.commit();cid=c.id
        configuration=CredentialService.module_runtime_configuration(p,c)
        assert configuration['credential_id']==cid and callable(configuration['persist_credentials'])
    calls=[]
    async def transport(request):
        fields=parse_qs(request.content.decode());calls.append(fields['refresh_token'][0])
        return httpx.Response(200,json={'access_token':'synthetic-new-access','refresh_token':'synthetic-rotated-refresh','expires_in':3600})
    handler=cls()
    monkeypatch.setattr(handler,'create_http_client',lambda ctx:httpx.AsyncClient(transport=httpx.MockTransport(transport)))
    from app.modules.base import ModuleExecutionContext
    ctx=ModuleExecutionContext(credentials=payload,extra_config=configuration)
    await asyncio.gather(handler._get_valid_access_token(ctx),handler._get_valid_access_token(ctx))
    assert calls==['synthetic-old-refresh']
    async with AsyncSessionLocal() as db:
        fresh=await CredentialService.get_credential(db,cid)
        stored=json.loads(decrypt_secret(fresh.encrypted_api_key))
        assert stored['refresh_token']=='synthetic-rotated-refresh' and stored['untouched']=='keep'
        assert fresh.metadata_json=={'health':'keep'} and 'synthetic-new-access' not in fresh.encrypted_api_key
        if nested:
            auth=json.loads(stored['auth_json']);entry=auth['tokens'] if module_id=='codex_cli' else auth['synthetic']
            assert entry['refresh_token']=='synthetic-rotated-refresh'
            assert entry.get('key',entry.get('access_token'))=='synthetic-new-access'
        configuration=CredentialService.module_runtime_configuration(fresh.provider,fresh)
    restarted=cls();monkeypatch.setattr(restarted,'create_http_client',lambda ctx:httpx.AsyncClient(transport=httpx.MockTransport(transport)))
    await restarted._get_valid_access_token(ModuleExecutionContext(credentials=stored,extra_config=configuration))
    assert calls[-1]=='synthetic-rotated-refresh'
