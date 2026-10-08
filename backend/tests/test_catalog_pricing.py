"""Catalog → persistence → USD quota, entirely offline via the Lingling runner."""
import json
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import select

from app.adapters.base import DiscoveredModelData
from app.core.crypto import encrypt_secret
from app.core.database import AsyncSessionLocal
from app.core.errors import RouterException
from app.models.entities import DiscoveredModel, Provider, ProviderCredential
from app.schemas.chat import ChatCompletionRequest, ChatMessage
from app.schemas.entities import DiscoveredModelUpdate, PeriodQuotaRule, RouterApiKeyCreate
from app.services.api_key_service import ApiKeyService
from app.services.log_service import request_log_context
from app.services.model_discovery_service import ModelDiscoveryService
from app.services.quota_service import QuotaService


@pytest.mark.asyncio
@pytest.mark.parametrize('pricing, expected', [
    ({'prompt': '0.000001', 'completion': '2e-6'}, (1., 2.)),
    ({'prompt': 0, 'completion': '0'}, (0., 0.)),
    ({'prompt': '0.000001'}, (1., None)),
    *[({'prompt': value, 'completion': '0'}, (None, 0.)) for value in
      (None, True, False, '', 'bad', '1_0', {}, [], -1, '-1e-999',
       'NaN', 'Infinity', '1e309', '1e-999', float('nan'), float('inf'))],
    (None, (None, None)),
    ([], (None, None)),
])
async def test_catalog_prices_persist_and_control_usd_quota(monkeypatch, pricing, expected):
    from app.adapters.openai import http_client_manager
    catalog = {'data': [{'id': 'model', 'pricing': pricing, 'max_output_tokens': 20}]}
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=json.dumps(catalog)))) as client:
        monkeypatch.setattr(http_client_manager, 'get_client', AsyncMock(return_value=client))
        async with AsyncSessionLocal() as db:
            slug = 'pricing-' + uuid.uuid4().hex
            provider = Provider(name=slug, slug=slug, adapter_type='generic_openai', base_url='https://fixture.invalid')
            db.add(provider)
            await db.flush()
            credential = ProviderCredential(provider_id=provider.id, name=slug,
                encrypted_api_key=encrypt_secret('synthetic'), key_fingerprint=slug, masked_key='synthetic')
            db.add(credential)
            await db.commit()
            reads = await ModelDiscoveryService.fetch_models_for_credential(db, credential.id)
            assert (reads[0].input_price_per_1m, reads[0].output_price_per_1m) == expected
            assert reads[0].model_dump(mode='json')['input_price_per_1m'] == expected[0]
            db.expunge_all()
            model = await db.scalar(select(DiscoveredModel).where(DiscoveredModel.id == reads[0].id))
            assert (model.input_price_per_1m, model.output_price_per_1m) == expected
            key_read = await ApiKeyService.create_key(db, RouterApiKeyCreate(name=slug,
                quota_rules=[PeriodQuotaRule(usd=1)]))
            key = await ApiKeyService.get_key(db, key_read.id)
        request = ChatCompletionRequest(model=model.canonical_slug, messages=[ChatMessage(role='user', content='Hi')])
        with request_log_context({'router_key_id': key.id, 'requested_model': model.canonical_slug}):
            if None in expected:
                with pytest.raises(RouterException, match='known input and output model prices'):
                    await QuotaService.reserve_dispatch(None, model, request)
            else:
                ticket, _ = await QuotaService.reserve_dispatch(None, model, request)
                await ticket.finish({'prompt_tokens': 5, 'completion_tokens': 7}, success=True)
                async with AsyncSessionLocal() as db:
                    usage = await QuotaService.usage(db, key)
                assert usage[0]['used']['usd'] == pytest.approx((5 * expected[0] + 7 * expected[1]) / 1e6)
        # Rediscovery cannot rewrite manual tariffs, including zero or cleared unknown.
        async with AsyncSessionLocal() as db:
            await ModelDiscoveryService.update_model(db, model.id,
                DiscoveredModelUpdate(input_price_per_1m=0., output_price_per_1m=9.))
            catalog['data'][0]['pricing'] = {'prompt': '1', 'completion': '1'}
            reads = await ModelDiscoveryService.fetch_models_for_credential(db, credential.id)
            assert (reads[0].input_price_per_1m, reads[0].output_price_per_1m) == (0., 9.)
            await ModelDiscoveryService.update_model(db, model.id, DiscoveredModelUpdate(input_price_per_1m=None))
            reads = await ModelDiscoveryService.fetch_models_for_credential(db, credential.id)
            assert (reads[0].input_price_per_1m, reads[0].output_price_per_1m) == (None, 9.)
            manual = await ModelDiscoveryService.add_model_manually(db, provider.id, credential.id, 'manual', 'Manual')
            assert manual.input_price_per_1m is None and manual.output_price_per_1m is None


def test_catalog_dto_defaults_to_unknown():
    model = DiscoveredModelData(provider_model_id='model', display_name='Model')
    assert model.input_price_per_1m is None and model.output_price_per_1m is None
