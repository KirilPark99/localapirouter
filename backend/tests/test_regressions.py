import json
import uuid
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from openai import AsyncOpenAI
from unittest.mock import AsyncMock, patch

from app.api.v1.router import _anthropic_event_stream, _responses_event_stream, _responses_payload
from app.core.crypto import encrypt_secret
from app.core.database import AsyncSessionLocal
from app.core.errors import ErrorCategory, normalize_upstream_error
from app.fusion.engine import FusionEngine
from app.main import app
from app.models.entities import (
    DiscoveredModel,
    Provider,
    ProviderCredential,
    RouterApiKey,
    RoutingCandidate,
    RoutingProfile,
)
from app.routing.engine import RoutingEngine
from app.schemas.chat import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    ResponsesRequest,
    UsageInfo,
)
from app.schemas.entities import (
    CredentialUpdate,
    FusionProfileCreate,
    RouterApiKeyCreate,
    RoutingCandidateInput,
    RoutingProfileCreate,
    RoutingProfileUpdate,
)
from app.services.api_key_service import ApiKeyService
from app.services.credential_service import CredentialService
from app.services.fusion_service import FusionService
from app.services.routing_service import RoutingService


def test_responses_translation_and_openapi_ids_are_valid():
    request = ResponsesRequest(model="demo", input="hello", instructions="brief", max_output_tokens=12)
    chat = request.to_chat_request()
    assert [(message.role, message.content) for message in chat.messages] == [
        ("system", "brief"),
        ("user", "hello"),
    ]
    assert chat.max_tokens == 12

    response = ChatCompletionResponse(
        model="demo",
        choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content="done"))],
        usage=UsageInfo(prompt_tokens=2, completion_tokens=1, total_tokens=3),
    )
    payload = _responses_payload(response, "resp_test")
    assert payload["object"] == "response"
    assert payload["output_text"] == "done"
    assert payload["usage"]["total_tokens"] == 3

    operation_ids = [
        operation.get("operationId")
        for methods in app.openapi()["paths"].values()
        for method, operation in methods.items()
        if method in {"get", "post", "put", "patch", "delete", "head"}
    ]
    assert len(operation_ids) == len(set(operation_ids))


@pytest.mark.asyncio
async def test_protocol_stream_wrappers_translate_text():
    async def source():
        yield 'data: {"choices":[{"delta":{"content":"hel"}}]}\n\n'
        yield 'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        yield "data: [DONE]\n\n"

    responses_stream = "".join([chunk async for chunk in _responses_event_stream(source(), "demo", "resp_test")])
    assert '"delta": "hel"' in responses_stream
    assert "response.completed" in responses_stream

    anthropic_stream = "".join([chunk async for chunk in _anthropic_event_stream(source(), "demo", "msg_test")])
    assert '"text": "hello"' not in anthropic_stream
    assert '"text": "hel"' in anthropic_stream
    assert "event: message_stop" in anthropic_stream


@pytest.mark.asyncio
async def test_x_api_key_and_naive_expiration_work():
    async with AsyncSessionLocal() as db:
        created = await ApiKeyService.create_key(
            db,
            RouterApiKeyCreate(
                name=f"Regression {uuid.uuid4().hex}",
                expiration_date=datetime(2100, 1, 1),
            ),
        )
        valid, _, _ = await ApiKeyService.authenticate_key(db, created.raw_api_key)
        assert valid

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v1/models", headers={"x-api-key": created.raw_api_key})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_fusion_permission_and_reference_validation():
    key = RouterApiKey(
        name="direct-only",
        key_prefix="sk-router-test",
        key_hash="x",
        masked_key="x",
        permissions=["direct"],
        allowed_models=["*"],
        allowed_routes=[],
        allowed_fusions=[],
    )
    request = ResponsesRequest(model="fusion/blocked", input="hello").to_chat_request()
    with pytest.raises(Exception) as exc_info:
        await FusionEngine.execute_fusion(None, request, key)
    assert getattr(exc_info.value, "status_code", None) == 403

    run_id = uuid.uuid4().hex
    async with AsyncSessionLocal() as db:
        provider_a = Provider(name=f"A-{run_id}", slug=f"a-{run_id}", adapter_type="openai", base_url="https://a.invalid")
        provider_b = Provider(name=f"B-{run_id}", slug=f"b-{run_id}", adapter_type="openai", base_url="https://b.invalid")
        db.add_all([provider_a, provider_b])
        await db.flush()
        credential = ProviderCredential(
            provider_id=provider_a.id,
            name="A key",
            encrypted_api_key=encrypt_secret("key"),
            key_fingerprint=run_id,
            masked_key="key",
        )
        model_b = DiscoveredModel(
            provider_id=provider_b.id,
            provider_model_id="model-b",
            display_name="Model B",
            canonical_slug=f"{provider_b.slug}/model-b",
        )
        db.add_all([credential, model_b])
        await db.commit()

        with pytest.raises(ValueError, match="does not belong"):
            await FusionService.create_profile(
                db,
                FusionProfileCreate(
                    name="Invalid",
                    slug=f"invalid-{run_id}",
                    judge_provider_id=provider_a.id,
                    judge_credential_id=credential.id,
                    judge_model_id=model_b.id,
                ),
            )


@pytest.mark.asyncio
async def test_disabling_credential_returns_disabled_status():
    run_id = uuid.uuid4().hex
    async with AsyncSessionLocal() as db:
        provider = Provider(name=f"P-{run_id}", slug=f"p-{run_id}", adapter_type="openai", base_url="https://p.invalid")
        db.add(provider)
        await db.flush()
        credential = ProviderCredential(
            provider_id=provider.id,
            name="key",
            encrypted_api_key=encrypt_secret("key"),
            key_fingerprint=run_id,
            masked_key="key",
        )
        db.add(credential)
        await db.commit()
        result = await CredentialService.update_credential(db, credential.id, CredentialUpdate(enabled=False))
    assert result is not None
    assert result.enabled is False
    assert result.status == "DISABLED"


def test_provider_adapter_configuration_uses_top_level_fields():
    provider = Provider(
        name="Custom",
        slug="custom",
        adapter_type="generic_openai",
        base_url="https://example.invalid",
        models_endpoint="/catalog",
        chat_endpoint="/generate",
        responses_endpoint="/respond",
        auth_type="custom_header",
        auth_header="X-Token",
        configuration={"chat_endpoint": "/stale"},
    )
    assert provider.adapter_configuration == {
        "models_endpoint": "/catalog",
        "chat_endpoint": "/generate",
        "responses_endpoint": "/respond",
        "auth_type": "custom_header",
        "auth_header": "X-Token",
    }


@pytest.mark.asyncio
async def test_protocol_endpoints_accept_native_payloads():
    async with AsyncSessionLocal() as db:
        created = await ApiKeyService.create_key(
            db, RouterApiKeyCreate(name=f"Protocol {uuid.uuid4().hex}")
        )

    completion = ChatCompletionResponse(
        model="demo",
        choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content="ok"))],
        usage=UsageInfo(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )
    with patch.object(
        RoutingEngine, "route_chat_completions", new=AsyncMock(return_value=completion)
    ) as mocked_complete:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/responses",
                headers={"x-api-key": created.raw_api_key},
                json={"model": "demo", "input": "hello", "instructions": "brief"},
            )
        assert response.status_code == 200
        assert response.json()["output_text"] == "ok"

        sdk_http = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        sdk = AsyncOpenAI(
            base_url="http://test/v1",
            api_key=created.raw_api_key,
            http_client=sdk_http,
        )
        sdk_response = await sdk.responses.create(
            model="demo", input="hello", instructions="brief"
        )
        assert sdk_response.object == "response"
        assert sdk_response.output_text == "ok"
        await sdk.close()

        routed_request = mocked_complete.await_args.args[1]
        assert [message.role for message in routed_request.messages] == ["system", "user"]

    async def source():
        yield 'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
        yield "data: [DONE]\n\n"

    with patch.object(RoutingEngine, "route_stream_chat", return_value=source()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                headers={"x-api-key": created.raw_api_key},
                json={"model": "demo", "max_tokens": 8, "messages": [{"role": "user", "content": "hello"}], "stream": True},
            )
        assert response.status_code == 200
        assert "event: content_block_delta" in response.text
        assert "event: message_stop" in response.text


@pytest.mark.asyncio
async def test_disabled_provider_is_not_routed():
    run_id = uuid.uuid4().hex
    async with AsyncSessionLocal() as db:
        provider = Provider(
            name=f"Disabled-{run_id}",
            slug=f"disabled-{run_id}",
            adapter_type="openai",
            base_url="https://disabled.invalid",
            enabled=False,
        )
        db.add(provider)
        await db.flush()
        credential = ProviderCredential(
            provider_id=provider.id,
            name="key",
            encrypted_api_key=encrypt_secret("key"),
            key_fingerprint=run_id,
            masked_key="key",
            enabled=True,
        )
        model = DiscoveredModel(
            provider_id=provider.id,
            provider_model_id="demo",
            display_name="Demo",
            canonical_slug=f"{provider.slug}/demo",
            enabled=True,
            available=True,
        )
        db.add_all([credential, model])
        await db.commit()
        candidates = await RoutingEngine._get_candidate_credentials_for_model(
            db, model.canonical_slug
        )
    assert candidates == []


@pytest.mark.asyncio
async def test_priority_route_full_fallback_beyond_ten_attempts():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p1 = Provider(
            name=f"Provider1-{run_id}",
            slug=f"p1-{run_id}",
            adapter_type="openai",
            base_url="https://p1.invalid",
            enabled=True,
        )
        p2 = Provider(
            name=f"Provider2-{run_id}",
            slug=f"p2-{run_id}",
            adapter_type="openai",
            base_url="https://p2.invalid",
            enabled=True,
        )
        db.add_all([p1, p2])
        await db.flush()

        # Add 12 credentials for Provider 1
        p1_creds = []
        for i in range(1, 13):
            c = ProviderCredential(
                provider_id=p1.id,
                name=f"key-p1-{i}-{run_id}",
                encrypted_api_key=encrypt_secret(f"secret-{i}"),
                key_fingerprint=f"fp-p1-{i}-{run_id}",
                masked_key=f"sk-***{i}",
                enabled=True,
            )
            p1_creds.append(c)
        db.add_all(p1_creds)

        # Add 1 credential for Provider 2
        c2 = ProviderCredential(
            provider_id=p2.id,
            name=f"key-p2-1-{run_id}",
            encrypted_api_key=encrypt_secret("secret-p2"),
            key_fingerprint=f"fp-p2-1-{run_id}",
            masked_key="sk-***p2",
            enabled=True,
        )
        db.add(c2)

        # Add Models
        m1 = DiscoveredModel(
            provider_id=p1.id,
            provider_model_id="model-1",
            display_name="Model 1",
            canonical_slug=f"{p1.slug}/model-1",
            enabled=True,
            available=True,
        )
        m2 = DiscoveredModel(
            provider_id=p2.id,
            provider_model_id="model-2",
            display_name="Model 2",
            canonical_slug=f"{p2.slug}/model-2",
            enabled=True,
            available=True,
        )
        db.add_all([m1, m2])
        await db.flush()

        # Add Routing Profile with 2 candidates
        profile = RoutingProfile(
            name=f"Route {run_id}",
            slug=f"route-{run_id}",
            strategy="priority",
            retry_count=3,
            timeout_seconds=30.0,
            enabled=True,
        )
        db.add(profile)
        await db.flush()

        cand1 = RoutingCandidate(
            profile_id=profile.id,
            provider_id=p1.id,
            credential_id=None,  # Full fallback across all p1 keys
            model_id=m1.id,
            priority_order=1,
            is_active=True,
        )
        cand2 = RoutingCandidate(
            profile_id=profile.id,
            provider_id=p2.id,
            credential_id=c2.id,
            model_id=m2.id,
            priority_order=2,
            is_active=True,
        )
        db.add_all([cand1, cand2])
        await db.commit()

        # Mark all 12 credentials of Provider 1 as in cooldown in circuit breaker
        from app.core.circuit_breaker import circuit_breaker
        from app.core.errors import ErrorCategory
        for c in p1_creds:
            circuit_breaker.record_failure(c.id, ErrorCategory.RATE_LIMIT, retry_after=60, error_message="Rate limited")

        expected_resp = ChatCompletionResponse(
            id="chatcmpl-test",
            object="chat.completion",
            created=123456,
            model=m2.provider_model_id,
            choices=[ChatCompletionChoice(index=0, message=ChatMessage(role="assistant", content="Hello from provider 2"))],
            usage=UsageInfo(prompt_tokens=5, completion_tokens=5, total_tokens=10),
        )

        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = expected_resp
            req = ChatCompletionRequest(
                model=f"route/{profile.slug}",
                messages=[ChatMessage(role="user", content="Hi")],
            )
            resp = await RoutingEngine.route_chat_completions(db, req, None)
            assert resp.choices[0].message.content == "Hello from provider 2"


@pytest.mark.asyncio
async def test_routing_profile_custom_context_length_and_ollama_show():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        provider = Provider(
            name=f"Provider-{run_id}",
            slug=f"p-{run_id}",
            adapter_type="openai",
            base_url="https://p.invalid",
            enabled=True,
        )
        db.add(provider)
        await db.flush()

        model = DiscoveredModel(
            provider_id=provider.id,
            provider_model_id="m-test",
            display_name="M Test",
            canonical_slug=f"{provider.slug}/m-test",
            context_length=65536,
            enabled=True,
            available=True,
        )
        db.add(model)
        await db.flush()

        # 1. Profile with explicit custom context_length
        p_data = RoutingProfileCreate(
            name=f"Route {run_id}",
            slug=f"route-{run_id}",
            context_length=200000,
            candidates=[
                RoutingCandidateInput(
                    candidate_type="model",
                    provider_id=provider.id,
                    model_id=model.id,
                    priority_order=0,
                    is_active=True,
                )
            ],
        )
        p_read = await RoutingService.create_profile(db, p_data)
        assert p_read.context_length == 200000

        # Test Ollama /api/show returns custom context_length
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/show", json={"name": f"route/{p_read.slug}"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["model_info"]["context_length"] == 200000

            # 2. Update profile to clear context_length (auto mode)
            update_data = RoutingProfileUpdate(context_length=0)
            p_updated = await RoutingService.update_profile(db, p_read.id, update_data)
            assert p_updated.context_length is None

            # Test Ollama /api/show falls back to candidate model's context_length (65536)
            resp2 = await client.post("/api/show", json={"name": f"route/{p_read.slug}"})
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["model_info"]["context_length"] == 65536


def test_normalize_upstream_provider_restrictions():
    # OpenCodeZen free tier error
    err_opencode = normalize_upstream_error(
        status_code=400,
        response_body={"error": {"message": "Error from provider (Console): OpenCode's free tier can only be used in OpenCode"}}
    )
    assert err_opencode.category == ErrorCategory.UPSTREAM_5XX
    assert err_opencode.category.is_fallback_eligible is True

    # Quota / balance / tier limits returned as 400
    err_quota = normalize_upstream_error(
        status_code=400,
        response_body={"error": {"message": "Insufficient quota for requested model"}}
    )
    assert err_quota.category == ErrorCategory.UPSTREAM_5XX
    assert err_quota.category.is_fallback_eligible is True

    # Provider rate limit returned as 400
    err_rate = normalize_upstream_error(
        status_code=400,
        response_body={"error": {"message": "Rate limit exceeded for provider"}}
    )
    assert err_rate.category == ErrorCategory.RATE_LIMIT
    assert err_rate.category.is_fallback_eligible is True

    # Unsupported model returned as 400
    err_model = normalize_upstream_error(
        status_code=400,
        response_body={"error": {"message": "Model not found on remote provider"}}
    )
    assert err_model.category == ErrorCategory.MODEL_NOT_FOUND
    assert err_model.category.is_fallback_eligible is True

    # 403 provider restriction (credit/balance)
    err_403_credit = normalize_upstream_error(
        status_code=403,
        response_body={"error": {"message": "Credit balance is too low for this request"}}
    )
    assert err_403_credit.category == ErrorCategory.UPSTREAM_5XX
    assert err_403_credit.category.is_fallback_eligible is True

    # True client syntax error remains INVALID_REQUEST
    err_client = normalize_upstream_error(
        status_code=400,
        response_body={"error": {"message": "Invalid prompt formatting"}}
    )
    assert err_client.category == ErrorCategory.INVALID_REQUEST
    assert err_client.category.is_fallback_eligible is False


@pytest.mark.asyncio
async def test_priority_route_fallback_on_provider_400_error():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p1 = Provider(name=f"OpenCodeZen-{run_id}", slug=f"opencode-{run_id}", adapter_type="openai", base_url="https://opencode.invalid", enabled=True)
        p2 = Provider(name=f"OpenRouter-{run_id}", slug=f"openrouter-{run_id}", adapter_type="openai", base_url="https://openrouter.invalid", enabled=True)
        db.add_all([p1, p2])
        await db.flush()

        c1 = ProviderCredential(
            provider_id=p1.id,
            name="opencode-cred",
            encrypted_api_key=encrypt_secret("key1"),
            key_fingerprint=f"fp-c1-{run_id}",
            masked_key="sk-***1",
            enabled=True,
        )
        c2 = ProviderCredential(
            provider_id=p2.id,
            name="openrouter-cred",
            encrypted_api_key=encrypt_secret("key2"),
            key_fingerprint=f"fp-c2-{run_id}",
            masked_key="sk-***2",
            enabled=True,
        )
        db.add_all([c1, c2])
        await db.flush()

        m1 = DiscoveredModel(provider_id=p1.id, provider_model_id="nemotron-free", display_name="Nemotron Free", canonical_slug=f"{p1.slug}/nemotron-free", enabled=True, available=True)
        m2 = DiscoveredModel(provider_id=p2.id, provider_model_id="nemotron-ultra", display_name="Nemotron Ultra", canonical_slug=f"{p2.slug}/nemotron-ultra", enabled=True, available=True)
        db.add_all([m1, m2])
        await db.flush()

        profile = RoutingProfile(
            name=f"Priority Route {run_id}",
            slug=f"priority-{run_id}",
            strategy="priority",
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(profile)
        await db.flush()

        cand1 = RoutingCandidate(profile_id=profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m1.id, priority_order=0, is_active=True)
        cand2 = RoutingCandidate(profile_id=profile.id, candidate_type="model", provider_id=p2.id, credential_id=c2.id, model_id=m2.id, priority_order=1, is_active=True)
        db.add_all([cand1, cand2])
        await db.commit()

        # Mock adapter chat completions:
        # Candidate 1 (OpenCodeZen) raises 400 error from provider
        # Candidate 2 (OpenRouter) succeeds
        async def mock_chat(*args, **kwargs):
            model_id = kwargs.get("model_id")
            if model_id == "nemotron-free":
                raise normalize_upstream_error(
                    status_code=400,
                    response_body={"error": {"message": "Error from provider (Console): OpenCode's free tier can only be used in OpenCode"}}
                )
            return ChatCompletionResponse(
                id="chatcmpl-openrouter",
                object="chat.completion",
                created=123456,
                model=model_id,
                choices=[ChatCompletionChoice(index=0, message=ChatMessage(role="assistant", content="Hello from OpenRouter!"))],
                usage=UsageInfo(prompt_tokens=10, completion_tokens=15, total_tokens=25),
            )

        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_chat):
            req = ChatCompletionRequest(
                model=f"route/{profile.slug}",
                messages=[ChatMessage(role="user", content="Test prompt")],
            )
            resp = await RoutingEngine.route_chat_completions(db, req, None)
            assert resp.choices[0].message.content == "Hello from OpenRouter!"


@pytest.mark.asyncio
async def test_priority_route_streaming_fallback_on_provider_400_error():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p1 = Provider(name=f"OpenCodeZen-Stream-{run_id}", slug=f"opencode-s-{run_id}", adapter_type="openai", base_url="https://opencode.invalid", enabled=True)
        p2 = Provider(name=f"OpenRouter-Stream-{run_id}", slug=f"openrouter-s-{run_id}", adapter_type="openai", base_url="https://openrouter.invalid", enabled=True)
        db.add_all([p1, p2])
        await db.flush()

        c1 = ProviderCredential(
            provider_id=p1.id,
            name="opencode-s-cred",
            encrypted_api_key=encrypt_secret("key1"),
            key_fingerprint=f"fp-c1-s-{run_id}",
            masked_key="sk-***1",
            enabled=True,
        )
        c2 = ProviderCredential(
            provider_id=p2.id,
            name="openrouter-s-cred",
            encrypted_api_key=encrypt_secret("key2"),
            key_fingerprint=f"fp-c2-s-{run_id}",
            masked_key="sk-***2",
            enabled=True,
        )
        db.add_all([c1, c2])
        await db.flush()

        m1 = DiscoveredModel(provider_id=p1.id, provider_model_id="nemotron-free-s", display_name="Nemotron Free Stream", canonical_slug=f"{p1.slug}/nemotron-free-s", enabled=True, available=True)
        m2 = DiscoveredModel(provider_id=p2.id, provider_model_id="nemotron-ultra-s", display_name="Nemotron Ultra Stream", canonical_slug=f"{p2.slug}/nemotron-ultra-s", enabled=True, available=True)
        db.add_all([m1, m2])
        await db.flush()

        profile = RoutingProfile(
            name=f"Priority Stream Route {run_id}",
            slug=f"priority-s-{run_id}",
            strategy="priority",
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(profile)
        await db.flush()

        cand1 = RoutingCandidate(profile_id=profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m1.id, priority_order=0, is_active=True)
        cand2 = RoutingCandidate(profile_id=profile.id, candidate_type="model", provider_id=p2.id, credential_id=c2.id, model_id=m2.id, priority_order=1, is_active=True)
        db.add_all([cand1, cand2])
        await db.commit()

        async def mock_stream(*args, **kwargs):
            model_id = kwargs.get("model_id")
            if model_id == "nemotron-free-s":
                raise normalize_upstream_error(
                    status_code=400,
                    response_body={"error": {"message": "Error from provider (Console): OpenCode's free tier can only be used in OpenCode"}}
                )
            yield 'data: {"id":"cmpl-1","choices":[{"delta":{"content":"Streaming "}}]}\n\n'
            yield 'data: {"id":"cmpl-1","choices":[{"delta":{"content":"success!"}}]}\n\n'
            yield 'data: [DONE]\n\n'

        with patch("app.adapters.openai.GenericOpenAIAdapter.stream_chat", side_effect=mock_stream):
            req = ChatCompletionRequest(
                model=f"route/{profile.slug}",
                messages=[ChatMessage(role="user", content="Test stream prompt")],
                stream=True,
            )
            chunks = []
            async for chunk in RoutingEngine.route_stream_chat(db, req, None):
                chunks.append(chunk)
            full_text = "".join(chunks)
            assert "Streaming " in full_text
            assert "success!" in full_text


@pytest.mark.asyncio
async def test_circuit_breaker_model_specific_rate_limit():
    from app.core.circuit_breaker import circuit_breaker, CredentialStatus

    test_cred_id = 99999
    circuit_breaker.reset(test_cred_id)

    # 1. Record model-specific OTPM rate limit on qwen/qwen3.6-27b
    groq_error = (
        "Request too large for model `qwen/qwen3.6-27b` in organization `org_xxx` "
        "service tier `on_demand` on output tokens per minute (OTPM): Limit 1000, Requested 1320."
    )
    circuit_breaker.record_failure(
        cred_id=test_cred_id,
        category=ErrorCategory.RATE_LIMIT,
        retry_after=60,
        error_message=groq_error,
        model_id="qwen/qwen3.6-27b",
    )

    # 2. qwen/qwen3.6-27b must be in cooldown
    avail, reason = circuit_breaker.is_available(test_cred_id, "qwen/qwen3.6-27b")
    assert not avail
    assert "in cooldown" in reason
    assert "RATE_LIMITED" in reason

    # 3. Other models on the SAME credential must NOT be in cooldown!
    avail_compound, _ = circuit_breaker.is_available(test_cred_id, "groq/compound")
    assert avail_compound is True
    avail_gpt, _ = circuit_breaker.is_available(test_cred_id, "openai/gpt-oss-120b")
    assert avail_gpt is True
    avail_gen, _ = circuit_breaker.is_available(test_cred_id)
    assert avail_gen is True

    # 4. Status checks
    status_qwen = circuit_breaker.get_status(test_cred_id, "qwen/qwen3.6-27b")
    assert status_qwen["status"] == CredentialStatus.RATE_LIMITED
    status_compound = circuit_breaker.get_status(test_cred_id, "groq/compound")
    assert status_compound["status"] == CredentialStatus.HEALTHY

    # 5. Reset clears it
    circuit_breaker.reset(test_cred_id)
    avail_after, _ = circuit_breaker.is_available(test_cred_id, "qwen/qwen3.6-27b")
    assert avail_after is True


@pytest.mark.asyncio
async def test_priority_route_nested_profile_attempts_tracing_and_logging():
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.entities import RequestLog

    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p1 = Provider(name=f"p1-{run_id}", slug=f"p1-{run_id}", base_url="https://p1.example.com", adapter_type="generic_openai", enabled=True)
        db.add(p1)
        await db.flush()

        c1 = ProviderCredential(
            provider_id=p1.id,
            name=f"c1-{run_id}",
            encrypted_api_key=encrypt_secret("key1"),
            key_fingerprint=f"fp-c1-{run_id}",
            masked_key="sk-***1",
            enabled=True,
        )
        db.add(c1)
        await db.flush()

        m_fail1 = DiscoveredModel(provider_id=p1.id, provider_model_id="fail-1", display_name="Fail Model 1", canonical_slug=f"{p1.slug}/fail-1", enabled=True, available=True)
        m_sub_fail = DiscoveredModel(provider_id=p1.id, provider_model_id="sub-fail", display_name="Sub Fail Model", canonical_slug=f"{p1.slug}/sub-fail", enabled=True, available=True)
        m_sub_ok = DiscoveredModel(provider_id=p1.id, provider_model_id="sub-ok", display_name="Sub OK Model", canonical_slug=f"{p1.slug}/sub-ok", enabled=True, available=True)
        m_parent_fallback = DiscoveredModel(provider_id=p1.id, provider_model_id="parent-ok", display_name="Parent OK Model", canonical_slug=f"{p1.slug}/parent-ok", enabled=True, available=True)
        db.add_all([m_fail1, m_sub_fail, m_sub_ok, m_parent_fallback])
        await db.flush()

        # Nested SubProfile
        sub_profile = RoutingProfile(
            name=f"Sub Profile {run_id}",
            slug=f"sub-prof-{run_id}",
            strategy="priority",
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(sub_profile)
        await db.flush()

        sub_cand1 = RoutingCandidate(profile_id=sub_profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m_sub_fail.id, priority_order=0, is_active=True)
        sub_cand2 = RoutingCandidate(profile_id=sub_profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m_sub_ok.id, priority_order=1, is_active=True)
        db.add_all([sub_cand1, sub_cand2])
        await db.flush()

        # Parent Profile
        parent_profile = RoutingProfile(
            name=f"Parent Profile {run_id}",
            slug=f"parent-prof-{run_id}",
            strategy="priority",
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(parent_profile)
        await db.flush()

        parent_cand1 = RoutingCandidate(profile_id=parent_profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m_fail1.id, priority_order=0, is_active=True)
        parent_cand2 = RoutingCandidate(profile_id=parent_profile.id, candidate_type="profile", target_profile_id=sub_profile.id, priority_order=1, is_active=True)
        parent_cand3 = RoutingCandidate(profile_id=parent_profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m_parent_fallback.id, priority_order=2, is_active=True)
        db.add_all([parent_cand1, parent_cand2, parent_cand3])
        await db.commit()

        # Test non-streaming: candidate #1 fails -> subroute candidate #1 fails -> subroute candidate #2 succeeds
        async def mock_chat(*args, **kwargs):
            model_id = kwargs.get("model_id")
            if model_id in ("fail-1", "sub-fail"):
                raise normalize_upstream_error(status_code=429, response_body={"error": {"message": f"Rate limit on {model_id}"}})
            return ChatCompletionResponse(
                model=model_id,
                choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=f"Hello from {model_id}"))],
                usage=UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            )

        test_req_id = f"req_test_nested_{run_id}"
        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_chat):
            req = ChatCompletionRequest(
                model=f"route/{parent_profile.slug}",
                messages=[ChatMessage(role="user", content="Hi")],
            )
            res = await RoutingEngine.route_chat_completions(db, req, None, request_id=test_req_id)
            assert res.choices[0].message.content == "Hello from sub-ok"

        # Verify DB request log and attempts trace
        async with AsyncSessionLocal() as verify_db:
            log_entry = (await verify_db.execute(
                select(RequestLog).options(selectinload(RequestLog.attempts)).where(RequestLog.request_id == test_req_id)
            )).scalar_one_or_none()
            assert log_entry is not None
            assert log_entry.status == "FALLBACK_SUCCESS"
            assert log_entry.requested_model == f"route/{parent_profile.slug}"
            # 3 attempts should be recorded: #1 fail-1, #2 [Sub Profile] sub-fail, #3 [Sub Profile] sub-ok
            attempts = sorted(log_entry.attempts, key=lambda a: a.attempt_number)
            assert len(attempts) == 3
            assert attempts[0].status == "FAILED"
            assert "Fail Model 1" in attempts[0].model_name
            assert attempts[1].status == "FAILED"
            assert f"[{sub_profile.name}]" in attempts[1].model_name
            assert "Sub Fail Model" in attempts[1].model_name
            assert attempts[2].status == "SUCCESS"
            assert f"[{sub_profile.name}]" in attempts[2].model_name
            assert "Sub OK Model" in attempts[2].model_name


@pytest.mark.asyncio
async def test_priority_route_streaming_nested_profile_attempts_propagation_on_fallback():
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.entities import RequestLog

    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p1 = Provider(name=f"sp1-{run_id}", slug=f"sp1-{run_id}", base_url="https://p1.example.com", adapter_type="generic_openai", enabled=True)
        db.add(p1)
        await db.flush()

        c1 = ProviderCredential(
            provider_id=p1.id,
            name=f"sc1-{run_id}",
            encrypted_api_key=encrypt_secret("key1"),
            key_fingerprint=f"fp-sc1-{run_id}",
            masked_key="sk-***1",
            enabled=True,
        )
        db.add(c1)
        await db.flush()

        m_fail1 = DiscoveredModel(provider_id=p1.id, provider_model_id="s-fail-1", display_name="S Fail 1", canonical_slug=f"{p1.slug}/s-fail-1", enabled=True, available=True)
        m_sub_fail1 = DiscoveredModel(provider_id=p1.id, provider_model_id="s-sub-fail-1", display_name="S Sub Fail 1", canonical_slug=f"{p1.slug}/s-sub-fail-1", enabled=True, available=True)
        m_sub_fail2 = DiscoveredModel(provider_id=p1.id, provider_model_id="s-sub-fail-2", display_name="S Sub Fail 2", canonical_slug=f"{p1.slug}/s-sub-fail-2", enabled=True, available=True)
        m_parent_ok = DiscoveredModel(provider_id=p1.id, provider_model_id="s-parent-ok", display_name="S Parent OK", canonical_slug=f"{p1.slug}/s-parent-ok", enabled=True, available=True)
        db.add_all([m_fail1, m_sub_fail1, m_sub_fail2, m_parent_ok])
        await db.flush()

        # Nested SubProfile where ALL candidates fail
        sub_profile = RoutingProfile(
            name=f"Stream SubProfile {run_id}",
            slug=f"stream-sub-{run_id}",
            strategy="priority",
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(sub_profile)
        await db.flush()

        sub_c1 = RoutingCandidate(profile_id=sub_profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m_sub_fail1.id, priority_order=0, is_active=True)
        sub_c2 = RoutingCandidate(profile_id=sub_profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m_sub_fail2.id, priority_order=1, is_active=True)
        db.add_all([sub_c1, sub_c2])
        await db.flush()

        # Parent Profile: Cand1 (fails) -> Cand2 (SubProfile fails all) -> Cand3 (succeeds)
        parent_profile = RoutingProfile(
            name=f"Stream ParentProfile {run_id}",
            slug=f"stream-parent-{run_id}",
            strategy="priority",
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(parent_profile)
        await db.flush()

        parent_c1 = RoutingCandidate(profile_id=parent_profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m_fail1.id, priority_order=0, is_active=True)
        parent_c2 = RoutingCandidate(profile_id=parent_profile.id, candidate_type="profile", target_profile_id=sub_profile.id, priority_order=1, is_active=True)
        parent_c3 = RoutingCandidate(profile_id=parent_profile.id, candidate_type="model", provider_id=p1.id, credential_id=c1.id, model_id=m_parent_ok.id, priority_order=2, is_active=True)
        db.add_all([parent_c1, parent_c2, parent_c3])
        await db.commit()

        async def mock_stream(*args, **kwargs):
            model_id = kwargs.get("model_id")
            if model_id in ("s-fail-1", "s-sub-fail-1", "s-sub-fail-2"):
                raise normalize_upstream_error(status_code=429, response_body={"error": {"message": f"Rate limit on {model_id}"}})
            yield 'data: {"id":"cmpl-stream","choices":[{"delta":{"content":"Recovered from subroute!"}}]}\n\n'
            yield 'data: [DONE]\n\n'

        test_req_id = f"req_test_stream_nested_{run_id}"
        with patch("app.adapters.openai.GenericOpenAIAdapter.stream_chat", side_effect=mock_stream):
            req = ChatCompletionRequest(
                model=f"route/{parent_profile.slug}",
                messages=[ChatMessage(role="user", content="Hi stream")],
                stream=True,
            )
            chunks = []
            async for chunk in RoutingEngine.route_stream_chat(db, req, None, request_id=test_req_id):
                chunks.append(chunk)
            full_text = "".join(chunks)
            assert "Recovered from subroute!" in full_text

        # Verify DB request log has all 4 attempts:
        # #1 parent cand 1 (fail)
        # #2 subprofile cand 1 (fail)
        # #3 subprofile cand 2 (fail)
        # #4 parent cand 3 (success)
        async with AsyncSessionLocal() as verify_db:
            log_entry = (await verify_db.execute(
                select(RequestLog).options(selectinload(RequestLog.attempts)).where(RequestLog.request_id == test_req_id)
            )).scalar_one_or_none()
            assert log_entry is not None
            assert log_entry.status == "FALLBACK_SUCCESS"
            assert log_entry.requested_model == f"route/{parent_profile.slug}"
            attempts = sorted(log_entry.attempts, key=lambda a: a.attempt_number)
            assert len(attempts) == 4
            assert attempts[0].status == "FAILED"
            assert "S Fail 1" in attempts[0].model_name
            assert attempts[1].status == "FAILED"
            assert f"[{sub_profile.name}]" in attempts[1].model_name
            assert attempts[2].status == "FAILED"
            assert f"[{sub_profile.name}]" in attempts[2].model_name
            assert attempts[3].status == "SUCCESS"
            assert "S Parent OK" in attempts[3].model_name

@pytest.mark.asyncio
async def test_bulk_assign_proxy():
    from sqlalchemy import select
    from app.models.entities import Proxy
    from app.services.auth_service import AuthService
    from app.services.provider_service import ProviderService
    from app.services.proxy_service import ProxyService
    from app.schemas.entities import ProxyCreate, CredentialCreate

    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        # Create a test proxy
        proxy = await ProxyService.create_proxy(
            db,
            ProxyCreate(
                name=f"Bulk Test Proxy {run_id}",
                scheme="socks5",
                host="127.0.0.1",
                port=1080,
                country="United States",
                country_code="US",
            )
        )

        # Get existing provider or seed presets
        prov = (await db.execute(select(Provider))).scalars().first()
        if not prov:
            await ProviderService.seed_default_presets(db, force=True)
            prov = (await db.execute(select(Provider))).scalars().first()
        assert prov is not None

        # Create two credentials
        cred1 = await CredentialService.create_credential(
            db,
            CredentialCreate(
                provider_id=prov.id,
                name=f"Bulk Key 1 {run_id}",
                api_key=f"sk-bulk-1-{run_id}",
            )
        )
        cred2 = await CredentialService.create_credential(
            db,
            CredentialCreate(
                provider_id=prov.id,
                name=f"Bulk Key 2 {run_id}",
                api_key=f"sk-bulk-2-{run_id}",
            )
        )
        assert cred1.proxy_id is None
        assert cred2.proxy_id is None

        # 1. Bulk assign to proxy
        updated = await CredentialService.bulk_assign_proxy(
            db, [cred1.id, cred2.id], proxy.id
        )
        assert len(updated) == 2
        assert all(c.proxy_id == proxy.id for c in updated)
        assert all(c.proxy_name == proxy.name for c in updated)

        # 2. Bulk remove proxy (assign None)
        updated_none = await CredentialService.bulk_assign_proxy(
            db, [cred1.id, cred2.id], None
        )
        assert len(updated_none) == 2
        assert all(c.proxy_id is None for c in updated_none)
        assert all(c.proxy_name is None for c in updated_none)

        # 3. Test via API endpoint
        await AuthService.init_admin_user(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_resp = await client.post(
                "/api/admin/auth/login",
                json={"username": "admin", "password": "test-admin-password-12345"},
            )
            assert login_resp.status_code == 200
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            api_resp = await client.post(
                "/api/admin/credentials/bulk-assign-proxy",
                headers=headers,
                json={"credential_ids": [cred1.id, cred2.id], "proxy_id": proxy.id},
            )
            assert api_resp.status_code == 200
            data = api_resp.json()
            assert len(data) == 2
            assert all(c["proxy_id"] == proxy.id for c in data)

        # Cleanup
        await CredentialService.delete_credential(db, cred1.id)
        await CredentialService.delete_credential(db, cred2.id)
        await ProxyService.delete_proxy(db, proxy.id)


@pytest.mark.asyncio
async def test_request_logs_summary_and_advanced_filters():
    from app.services.log_service import LogService
    from app.services.auth_service import AuthService
    from app.models.entities import RequestLog

    run_id = uuid.uuid4().hex[:8]
    req_id_1 = f"req-test-1-{run_id}"
    req_id_2 = f"req-test-2-{run_id}"

    async with AsyncSessionLocal() as db:
        # Create log 1: successful streaming direct call
        log1 = await LogService.record_request_log(
            db=db,
            request_id=req_id_1,
            requested_model="test/model-alpha",
            mode="direct",
            status="success",
            status_code=200,
            latency_ms=350.0,
            input_tokens=150,
            output_tokens=75,
            cached_tokens=25,
            reasoning_tokens=10,
            metadata_json={"stream": True, "ip": "127.0.0.1"},
            input_price_per_1m=1.0,
            output_price_per_1m=2.0,
            attempts=[
                {
                    "attempt_order": 1,
                    "model": "test/model-alpha",
                    "status": "success",
                    "status_code": 200,
                    "latency_ms": 350.0,
                }
            ],
        )

        # Create log 2: error fallback route call > 2000ms
        log2 = await LogService.record_request_log(
            db=db,
            request_id=req_id_2,
            requested_model="route/fallback-test",
            mode="route",
            status="error",
            status_code=502,
            latency_ms=2500.0,
            input_tokens=300,
            output_tokens=0,
            cached_tokens=0,
            reasoning_tokens=0,
            error_category="UPSTREAM_5XX",
            error_message="Bad Gateway",
            metadata_json={"stream": False, "ip": "127.0.0.1"},
            input_price_per_1m=0.0,
            output_price_per_1m=0.0,
            attempts=[
                {
                    "attempt_order": 1,
                    "model": "p1/m1",
                    "status": "error",
                    "status_code": 502,
                    "latency_ms": 1200.0,
                    "error_message": "Bad Gateway",
                },
                {
                    "attempt_order": 2,
                    "model": "p2/m2",
                    "status": "error",
                    "status_code": 502,
                    "latency_ms": 1300.0,
                    "error_message": "Bad Gateway",
                },
            ],
        )
        await db.commit()

        # Test LogService.get_logs_summary with search filter
        summary = await LogService.get_logs_summary(db, search=run_id)
        assert summary.total_requests == 2
        assert summary.total_errors == 1
        assert summary.error_rate == 50.0
        assert summary.total_tokens == (150 + 75 + 300)
        assert summary.total_prompt_tokens == 450
        assert summary.total_completion_tokens == 75
        assert summary.total_cached_tokens == 25
        assert summary.total_reasoning_tokens == 10
        assert summary.avg_latency_ms > 0

        # Test LogService.list_logs with advanced filters
        logs_stream = await LogService.list_logs(db, is_stream=True, search=run_id)
        assert len(logs_stream) == 1
        assert logs_stream[0].request_id == req_id_1

        logs_slow = await LogService.list_logs(db, min_latency=2000.0, search=run_id)
        assert len(logs_slow) == 1
        assert logs_slow[0].request_id == req_id_2

        logs_err = await LogService.list_logs(db, has_error=True, search=run_id)
        assert len(logs_err) == 1
        assert logs_err[0].request_id == req_id_2

        logs_status = await LogService.list_logs(db, status_code=200, search=run_id)
        assert len(logs_status) == 1
        assert logs_status[0].request_id == req_id_1

        # Test API endpoints
        await AuthService.init_admin_user(db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login_resp = await client.post(
                "/api/admin/auth/login",
                json={"username": "admin", "password": "test-admin-password-12345"},
            )
            assert login_resp.status_code == 200
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Summary API
            sum_api_resp = await client.get(
                "/api/admin/logs/summary",
                params={"search": run_id},
                headers=headers,
            )
            assert sum_api_resp.status_code == 200
            s_data = sum_api_resp.json()
            assert s_data["total_requests"] == 2
            assert s_data["total_errors"] == 1
            assert s_data["error_rate"] == 50.0

            # Logs API with sorting and filters
            logs_api_resp = await client.get(
                "/api/admin/logs",
                params={"search": run_id, "sort_by": "latency_ms", "sort_order": "desc"},
                headers=headers,
            )
            assert logs_api_resp.status_code == 200
            l_data = logs_api_resp.json()
            assert len(l_data) == 2
            assert l_data[0]["latency_ms"] >= l_data[1]["latency_ms"]

        # Cleanup created test logs
        from sqlalchemy import delete
        await db.execute(delete(RequestLog).where(RequestLog.request_id.in_([req_id_1, req_id_2])))
        await db.commit()




