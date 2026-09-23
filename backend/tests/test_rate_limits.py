import pytest
import httpx
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import Provider, ProviderCredential, DiscoveredModel, RouterApiKey
from app.services.api_key_service import ApiKeyService
from app.services.credential_service import CredentialService


async def get_or_create_provider(db, slug="openai-quota-test"):
    p_res = await db.execute(select(Provider).where(Provider.slug == slug))
    provider = p_res.scalars().first()
    if not provider:
        provider = Provider(
            name="OpenAI Quota Test",
            slug=slug,
            adapter_type="openai",
            base_url="https://api.openai.com/v1",
            models_endpoint="/models",
            chat_endpoint="/chat/completions",
            responses_endpoint="/responses",
            enabled=True,
            auth_type="bearer",
            auth_header="Authorization",
        )
        db.add(provider)
        await db.commit()
        await db.refresh(provider)
    return provider


@pytest.mark.asyncio
async def test_key_request_limit_quota_exhaustion():
    """Verifies that when request_limit is set on a Router API Key, requests beyond the limit return 401."""
    run_id = uuid.uuid4().hex[:8]
    k_secret = f"sk-cand-quota-{run_id}"

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-quota-{run_id}")
        c = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "C", "api_key": k_secret, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())
        m = DiscoveredModel(provider_id=provider.id, credential_id=c.id, provider_model_id=f"m-{run_id}", display_name="M", canonical_slug=f"prov-quota-{run_id}/m-{run_id}", capabilities={"chat": True}, supported_endpoints=["/chat/completions"], enabled=True, available=True)
        db.add(m)
        await db.commit()
        await db.refresh(m)

        # Key with quota limit of exactly 2 requests
        k = await ApiKeyService.create_key(db, data=type("Obj", (), {
            "name": f"Quota Key {run_id}", "permissions": ["direct", "routes", "fusion"],
            "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"],
            "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": 2,
            "expiration_date": None, "ip_restrictions": [],
        })())
        raw_key = k.raw_api_key

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "c", "object": "chat.completion", "created": 1, "model": f"m-{run_id}", "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Request 1 (Allowed)
            res1 = await client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": f"prov-quota-{run_id}/m-{run_id}", "messages": [{"role": "user", "content": "1"}]})
            assert res1.status_code == 200

            # Request 2 (Allowed)
            res2 = await client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": f"prov-quota-{run_id}/m-{run_id}", "messages": [{"role": "user", "content": "2"}]})
            assert res2.status_code == 200

            # Request 3 (Exceeded Limit -> 401)
            res3 = await client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_key}"}, json={"model": f"prov-quota-{run_id}/m-{run_id}", "messages": [{"role": "user", "content": "3"}]})
            assert res3.status_code == 401
            assert "request limit reached" in res3.json()["detail"].lower()


@pytest.mark.asyncio
async def test_key_expiration_and_disabled():
    """Verifies that expired or disabled router API keys are rejected with 401."""
    run_id = uuid.uuid4().hex[:8]
    k_secret = f"sk-cand-exp-{run_id}"

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-exp-{run_id}")
        c = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "C", "api_key": k_secret, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())
        m = DiscoveredModel(provider_id=provider.id, credential_id=c.id, provider_model_id=f"m-{run_id}", display_name="M", canonical_slug=f"prov-exp-{run_id}/m-{run_id}", capabilities={"chat": True}, supported_endpoints=["/chat/completions"], enabled=True, available=True)
        db.add(m)
        await db.commit()

        # 1. Expired key
        past_time = datetime.now(timezone.utc) - timedelta(hours=2)
        k_exp = await ApiKeyService.create_key(db, data=type("Obj", (), {
            "name": f"Expired {run_id}", "permissions": ["direct"],
            "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"],
            "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None,
            "expiration_date": past_time, "ip_restrictions": [],
        })())

        # 2. Disabled key
        k_dis = await ApiKeyService.create_key(db, data=type("Obj", (), {
            "name": f"Disabled {run_id}", "permissions": ["direct"],
            "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"],
            "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None,
            "expiration_date": None, "ip_restrictions": [],
        })())
        dis_obj = (await db.execute(select(RouterApiKey).where(RouterApiKey.id == k_dis.id))).scalar_one()
        dis_obj.enabled = False
        await db.commit()

        raw_exp = k_exp.raw_api_key
        raw_dis = k_dis.raw_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test Expired Key
        res_exp = await client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_exp}"}, json={"model": f"prov-exp-{run_id}/m-{run_id}", "messages": [{"role": "user", "content": "Hi"}]})
        assert res_exp.status_code == 401
        assert "expired" in res_exp.json()["detail"].lower()

        # Test Disabled Key
        res_dis = await client.post("/v1/chat/completions", headers={"Authorization": f"Bearer {raw_dis}"}, json={"model": f"prov-exp-{run_id}/m-{run_id}", "messages": [{"role": "user", "content": "Hi"}]})
        assert res_dis.status_code == 401
        assert "disabled" in res_dis.json()["detail"].lower()


@pytest.mark.asyncio
async def test_key_allowed_models_permission_enforcement():
    """Verifies that allowed_models restrictions are strictly enforced."""
    run_id = uuid.uuid4().hex[:8]

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-perm-{run_id}")
        c = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "C", "api_key": f"sk-p-{run_id}", "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())
        m = DiscoveredModel(provider_id=provider.id, credential_id=c.id, provider_model_id=f"allowed-model-{run_id}", display_name="M", canonical_slug=f"prov-perm-{run_id}/allowed-model-{run_id}", capabilities={"chat": True}, supported_endpoints=["/chat/completions"], enabled=True, available=True)
        db.add(m)
        await db.commit()

        # Key restricted ONLY to prov-perm-*/allowed-model-*
        k = await ApiKeyService.create_key(db, data=type("Obj", (), {
            "name": f"Restricted {run_id}", "permissions": ["direct"],
            "allowed_models": [f"prov-perm-{run_id}/allowed-model-{run_id}"],
            "allowed_routes": [], "allowed_fusions": [],
            "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None,
            "expiration_date": None, "ip_restrictions": [],
        })())
        raw_key = k.raw_api_key

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "c", "object": "chat.completion", "created": 1, "model": "m", "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}]})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Access to allowed model -> 200
            res_ok = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={"model": f"prov-perm-{run_id}/allowed-model-{run_id}", "messages": [{"role": "user", "content": "Hi"}]},
            )
            assert res_ok.status_code == 200

            # 2. Access to forbidden model -> 403
            res_forbidden = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={"model": "openai/gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
            )
            assert res_forbidden.status_code == 403
            assert "not in allowed models" in res_forbidden.json()["error"]["message"].lower()
