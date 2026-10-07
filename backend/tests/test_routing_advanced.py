import pytest
import httpx
import json
import uuid
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
    RoutingCandidate,
)
from app.services.api_key_service import ApiKeyService
from app.services.credential_service import CredentialService


async def get_or_create_provider(db, slug="openai-routing-adv-test"):
    p_res = await db.execute(select(Provider).where(Provider.slug == slug))
    provider = p_res.scalars().first()
    if not provider:
        provider = Provider(
            name="OpenAI Routing Adv Test",
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
async def test_routing_fallback_to_second_candidate_and_retry_exhaustion():
    """
    Verifies that:
    1) When Candidate 1 fails, router falls back to Candidate 2;
    2) When all candidates in the route fail, router returns 502 with full failure details.
    """
    run_id = uuid.uuid4().hex[:8]
    k1 = f"sk-cand1-{run_id}"
    k2 = f"sk-cand2-{run_id}"

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-adv-{run_id}")

        c1 = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "C1", "api_key": k1, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())
        c2 = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "C2", "api_key": k2, "proxy_id": None, "priority": 2, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())

        m = DiscoveredModel(provider_id=provider.id, credential_id=c1.id, provider_model_id=f"m-{run_id}", display_name="M", canonical_slug=f"prov-adv-{run_id}/m-{run_id}", capabilities={"chat": True}, supported_endpoints=["/chat/completions"], enabled=True, available=True)
        db.add(m)
        await db.commit()
        await db.refresh(m)

        route_slug = f"route-adv-{run_id}"
        prof = RoutingProfile(
            name="Adv Route", slug=route_slug, strategy="priority",
            retry_count=2, timeout_seconds=10.0, enabled=True,
        )
        db.add(prof)
        await db.flush()

        db.add(RoutingCandidate(profile_id=prof.id, candidate_type="model", provider_id=provider.id, credential_id=c1.id, model_id=m.id, priority_order=1, is_active=True))
        db.add(RoutingCandidate(profile_id=prof.id, candidate_type="model", provider_id=provider.id, credential_id=c2.id, model_id=m.id, priority_order=2, is_active=True))

        k = await ApiKeyService.create_key(db, data=type("Obj", (), {"name": "Key Adv", "permissions": ["direct", "routes", "fusion"], "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"], "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None, "expiration_date": None, "ip_restrictions": []})())
        raw_key = k.raw_api_key

    # Case 1: C1 fails with 500, C2 succeeds -> 200 OK
    def mock_handler_recovery(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if k1 in auth:
            return httpx.Response(500, json={"error": {"message": "Server Error"}})
        elif k2 in auth:
            return httpx.Response(200, json={"id": "c2", "object": "chat.completion", "created": 1, "model": f"m-{run_id}", "choices": [{"index": 0, "message": {"role": "assistant", "content": "Recovered by C2"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}})
        return httpx.Response(404)

    mock_client_rec = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler_recovery))
    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client_rec):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={"model": f"route/{route_slug}", "messages": [{"role": "user", "content": "Test recovery"}]},
            )
            assert resp.status_code == 200
            assert "Recovered by C2" in resp.json()["choices"][0]["message"]["content"]

    # Case 2: Both C1 and C2 fail -> 502 / Upstream Error
    def mock_handler_all_fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "Service Unavailable"}})

    mock_client_fail = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler_all_fail))
    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client_fail):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={"model": f"route/{route_slug}", "messages": [{"role": "user", "content": "All fail"}]},
            )
            assert resp.status_code in (500, 502, 503)


@pytest.mark.asyncio
async def test_routing_credential_group_filtering():
    """
    Verifies that when a candidate has credential_group='Production',
    only credentials belonging to 'Production' are selected, and credentials from 'Dev' are ignored.
    """
    run_id = uuid.uuid4().hex[:8]
    k_prod = f"sk-prod-{run_id}"
    k_dev = f"sk-dev-{run_id}"

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-grp-{run_id}")

        c_prod = await CredentialService.create_credential(db, data=type("Obj", (), {
            "provider_id": provider.id, "name": "ProdKey", "api_key": k_prod, "group_name": "Production",
            "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None,
        })())
        c_dev = await CredentialService.create_credential(db, data=type("Obj", (), {
            "provider_id": provider.id, "name": "DevKey", "api_key": k_dev, "group_name": "Dev",
            "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None,
        })())

        m = DiscoveredModel(provider_id=provider.id, credential_id=c_prod.id, provider_model_id=f"m-{run_id}", display_name="M", canonical_slug=f"prov-grp-{run_id}/m-{run_id}", capabilities={"chat": True}, supported_endpoints=["/chat/completions"], enabled=True, available=True)
        db.add(m)
        await db.commit()
        await db.refresh(m)

        route_slug = f"route-grp-{run_id}"
        prof = RoutingProfile(
            name="Group Route", slug=route_slug, strategy="priority",
            retry_count=1, timeout_seconds=10.0, enabled=True,
        )
        db.add(prof)
        await db.flush()

        # Candidate specifically configured with credential_group="Production"
        db.add(RoutingCandidate(
            profile_id=prof.id, candidate_type="model", provider_id=provider.id,
            credential_id=None, credential_group="Production", model_id=m.id,
            priority_order=1, is_active=True,
        ))

        k = await ApiKeyService.create_key(db, data=type("Obj", (), {"name": "Key Grp", "permissions": ["direct", "routes", "fusion"], "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"], "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None, "expiration_date": None, "ip_restrictions": []})())
        raw_key = k.raw_api_key

    prod_called = False
    dev_called = False

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal prod_called, dev_called
        auth = request.headers.get("Authorization", "")
        if k_prod in auth:
            prod_called = True
            return httpx.Response(200, json={"id": "prod", "object": "chat.completion", "created": 1, "model": f"m-{run_id}", "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello from Production Key"}, "finish_reason": "stop"}]})
        elif k_dev in auth:
            dev_called = True
            return httpx.Response(200, json={"id": "dev", "object": "chat.completion", "created": 1, "model": f"m-{run_id}", "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello from Dev Key"}, "finish_reason": "stop"}]})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={"model": f"route/{route_slug}", "messages": [{"role": "user", "content": "Test group"}]},
            )
            assert resp.status_code == 200
            assert prod_called is True
            assert dev_called is False
            assert "Hello from Production Key" in resp.json()["choices"][0]["message"]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("outcome", ["recover", "exhaust", "policy_stop", "invalid_request"])
async def test_randomized_profile_payment_fallback(monkeypatch, stream, outcome):
    from app.core.circuit_breaker import circuit_breaker
    from app.core.errors import RouterException, ErrorCategory
    from app.routing.engine import RoutingEngine
    from app.schemas.chat import ChatCompletionRequest, ChatMessage
    from app.core.crypto import encrypt_secret
    import time

    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"payment-{run_id}")
        profile = RoutingProfile(
            name="Payment fallback", slug=f"payment-{run_id}", enabled=True,
            strategy="round_robin", randomize_candidates=True, randomize_keys=True,
            retry_count=0, fallback_conditions=["RATE_LIMIT"] if outcome == "policy_stop" else ["UPSTREAM_5XX"],
        )
        db.add(profile)
        await db.flush()
        credentials = []
        for index in range(6):
            cred = ProviderCredential(provider_id=provider.id, name=f"synthetic-{index}",
                encrypted_api_key=encrypt_secret(f"synthetic-payment-{index}"),
                key_fingerprint=f"payment-{run_id}-{index}", masked_key="synthetic", enabled=True)
            model = DiscoveredModel(provider_id=provider.id, provider_model_id=f"payment-{index}",
                display_name=f"Payment {index}", canonical_slug=f"{provider.slug}/payment-{index}", enabled=True, available=True)
            db.add_all([cred, model])
            await db.flush()
            credentials.append(cred.id)
            circuit_breaker.reset(cred.id)
            db.add(RoutingCandidate(profile_id=profile.id, provider_id=provider.id,
                credential_id=cred.id, model_id=model.id, priority_order=index, is_active=True))
        await db.commit()

        calls, shuffled = [], []
        def shuffle(candidates):
            shuffled.append([c.priority_order for c in candidates])
            candidates.reverse()
        monkeypatch.setattr("app.routing.engine.random.shuffle", shuffle)

        def upstream(request):
            model_id = json.loads(request.content)["model"]
            calls.append(model_id)
            if outcome != "recover" or model_id != "payment-0":
                return httpx.Response(400 if outcome == "invalid_request" else 402,
                    json={"detail": "Invalid prompt formatting" if outcome == "invalid_request"
                          else "Insufficient balance. Top up your account to continue."})
            if stream:
                return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                    text='data: {"choices":[{"index":0,"delta":{"content":"Recovered"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
            return httpx.Response(200, json={"id": "payment-ok", "object": "chat.completion",
                "created": 1, "model": model_id,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Recovered"}, "finish_reason": "stop"}]})

        req = ChatCompletionRequest(model=f"route/{profile.slug}",
            messages=[ChatMessage(role="user", content="Synthetic fallback check")], stream=stream)
        async def invoke():
            if stream:
                return "".join([chunk async for chunk in RoutingEngine._handle_priority_stream(
                    db, req, req.model, None, "req_payment_test", time.perf_counter(), record_log=False)])
            result = await RoutingEngine._handle_priority_route(
                db, req, req.model, None, "req_payment_test", time.perf_counter(), record_log=False)
            content = result.choices[0].message.content
            assert isinstance(content, str)
            return content

        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
                monkeypatch.setattr("app.core.http_client.http_client_manager.get_client",
                    AsyncMock(return_value=client))
                if outcome == "recover":
                    assert "Recovered" in await invoke()
                else:
                    with pytest.raises(RouterException) as caught:
                        await invoke()
                    assert caught.value.category == (ErrorCategory.INVALID_REQUEST if outcome == "invalid_request" else ErrorCategory.UPSTREAM_5XX)
                    if outcome != "invalid_request":
                        assert caught.value.upstream_status == 402
            assert shuffled == [list(range(6))]
            assert calls == ([f"payment-{i}" for i in reversed(range(6))]
                             if outcome in ("recover", "exhaust") else ["payment-5"])
        finally:
            for cred_id in credentials:
                circuit_breaker.reset(cred_id)
