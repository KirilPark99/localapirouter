"""Backup-format regressions for audit point44 (no real backup or secret values)."""
import uuid
import pytest
from sqlalchemy import select,func
from app.core.database import AsyncSessionLocal
from app.models.entities import Provider,ProviderCredential
from app.services.backup_service import BackupService,encrypt_payload

PASSPHRASE='synthetic-backup-passphrase'

def envelope(**changes):
    data={'version':1,'type':'myairouter_backup','providers':[],'credentials':[],'proxies':[]}
    data.update(changes);return encrypt_payload(data,PASSPHRASE)

@pytest.mark.asyncio
@pytest.mark.parametrize('changes',[{'version':999},{'version':True},{'type':'other'},
    {'providers':{}},{'credentials':[{'name':'orphan','provider_slug':'missing','api_key':'synthetic'}]},
    {'credentials':[{'name':'badshape','api_key':17}]}])
async def test_p44_invalid_backup_rejected_before_any_write(changes):
    raw=envelope(**changes)
    async with AsyncSessionLocal() as db:
        before=await db.scalar(select(func.count(ProviderCredential.id)))
        with pytest.raises(ValueError):await BackupService.preview_import(db,raw,PASSPHRASE)
        with pytest.raises(ValueError):await BackupService.import_data(db,raw,PASSPHRASE,auto_discover_models=False)
        assert await db.scalar(select(func.count(ProviderCredential.id)))==before

@pytest.mark.asyncio
async def test_p44_import_failure_is_not_success_and_valid_backup_still_imports():
    slug='backup-'+uuid.uuid4().hex
    data={'providers':[{'slug':slug,'name':'synthetic','adapter_type':'openai','base_url':'https://fixture.invalid'}],
        'credentials':[{'name':'bad-keyless','provider_slug':slug,'api_key':''}]}
    async with AsyncSessionLocal() as db:
        stats=await BackupService.import_data(db,envelope(**data),PASSPHRASE,auto_discover_models=False)
        assert stats['success'] is False and stats['errors'] and stats['imported_credentials']==0
        good=envelope(providers=data['providers'],credentials=[{'name':'synthetic','provider_slug':slug,'api_key':'synthetic-fixture-only'}])
        preview=await BackupService.preview_import(db,good,PASSPHRASE)
        assert preview['valid'] and preview['total_credentials']==1
        stats=await BackupService.import_data(db,good,PASSPHRASE,auto_discover_models=False)
        assert stats['success'] and not stats['errors'] and stats['imported_credentials']==1
        target=await db.scalar(select(Provider).where(Provider.slug==slug))
        cred=await db.scalar(select(ProviderCredential).where(ProviderCredential.provider_id==target.id))
        assert cred.name=='synthetic'
