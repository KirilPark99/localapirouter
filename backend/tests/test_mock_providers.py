import pytest
import httpx
import json
import uuid
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
    RoutingCandidate,
    FusionProfile,
    FusionParticipant,
)
from app.core.crypto import encrypt_secret
from app.core.errors import RouterException
from app.routing.engine import RoutingEngine
from app.services.api_key_service import ApiKeyService
from app.services.provider_service import ProviderService
from app.services.credential_service import CredentialService

from sqlalchemy import select

async def get_or_create_provider(db, slug="openai"):
    p_res = await db.execute(select(Provider).where(Provider.slug == slug))
    provider = p_res.scalars().first()
    if not provider:
        provider = Provider(
            name="OpenAI",
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
async def test_fallback_between_credentials():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, "openai")

        key1_secret = f"sk-mock-failing-429-{run_id}"
        key2_secret = f"sk-mock-working-200-{run_id}"

        c1 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Key 1 {run_id}",
                "api_key": key1_secret,
                "proxy_id": None,
                "priority": 1,
                "weight": 1,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        c2 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Key 2 {run_id}",
                "api_key": key2_secret,
                "proxy_id": None,
                "priority": 2,
                "weight": 1,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        m = DiscoveredModel(
            provider_id=provider.id,
            credential_id=c1.id,
            provider_model_id=f"gpt-4o-{run_id}",
            display_name="GPT-4o Mock",
            canonical_slug=f"openai/gpt-4o-{run_id}",
            capabilities={"chat": True, "streaming": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        route_slug = f"fallback-{run_id}"
        profile = RoutingProfile(
            name=f"Route {run_id}",
            slug=route_slug,
            strategy="priority",
            retry_count=2,
            timeout_seconds=10.0,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX"],
            enabled=True,
        )
        db.add(profile)
        await db.flush()

        cand1 = RoutingCandidate(profile_id=profile.id, provider_id=provider.id, credential_id=c1.id, model_id=m.id, priority_order=1, is_active=True)
        cand2 = RoutingCandidate(profile_id=profile.id, provider_id=provider.id, credential_id=c2.id, model_id=m.id, priority_order=2, is_active=True)
        db.add(cand1)
        db.add(cand2)

        k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"Key {run_id}",
                "permissions": ["direct", "routes", "fusion"],
                "allowed_models": ["*"],
                "allowed_routes": ["*"],
                "allowed_fusions": ["*"],
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
                "request_limit": None,
                "expiration_date": None,
                "ip_restrictions": [],
            })(),
        )
        raw_key = k.raw_api_key

    def mock_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if key1_secret in auth:
            return httpx.Response(429, json={"error": {"message": "Rate limit exceeded on Key 1"}})
        elif key2_secret in auth:
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-mock-success",
                    "object": "chat.completion",
                    "created": 1234567,
                    "model": f"gpt-4o-{run_id}",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "Hello from Key 2!"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                },
            )
        return httpx.Response(404, json={"error": "Not found"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "model": f"route/{route_slug}",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["choices"][0]["message"]["content"] == "Hello from Key 2!"

@pytest.mark.asyncio
async def test_fusion_parallel_fanout_and_synthesis():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, "openai")

        key_a_secret = f"sk-mock-cand-a-{run_id}"
        key_b_secret = f"sk-mock-cand-b-{run_id}"
        key_judge_secret = f"sk-mock-judge-{run_id}"

        c_a = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Cand A {run_id}",
                "api_key": key_a_secret,
                "proxy_id": None,
                "priority": 1,
                "weight": 1,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        c_b = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Cand B {run_id}",
                "api_key": key_b_secret,
                "proxy_id": None,
                "priority": 1,
                "weight": 1,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        c_judge = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Judge {run_id}",
                "api_key": key_judge_secret,
                "proxy_id": None,
                "priority": 1,
                "weight": 1,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        m = DiscoveredModel(
            provider_id=provider.id,
            credential_id=c_a.id,
            provider_model_id=f"gpt-model-{run_id}",
            display_name="GPT Model",
            canonical_slug=f"openai/gpt-model-{run_id}",
            capabilities={"chat": True, "streaming": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        fusion_slug = f"fusion-{run_id}"
        fusion_prof = FusionProfile(
            name=f"Mock Fusion {run_id}",
            slug=fusion_slug,
            strategy="synthesize",
            judge_provider_id=provider.id,
            judge_credential_id=c_judge.id,
            judge_model_id=m.id,
            min_successful_candidates=2,
            max_parallelism=5,
            timeout_seconds=10.0,
            enabled=True,
        )
        db.add(fusion_prof)
        await db.flush()

        part_a = FusionParticipant(profile_id=fusion_prof.id, provider_id=provider.id, credential_id=c_a.id, model_id=m.id, label="Candidate A", is_active=True)
        part_b = FusionParticipant(profile_id=fusion_prof.id, provider_id=provider.id, credential_id=c_b.id, model_id=m.id, label="Candidate B", is_active=True)
        db.add(part_a)
        db.add(part_b)

        k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"Key Fusion {run_id}",
                "permissions": ["direct", "routes", "fusion"],
                "allowed_models": ["*"],
                "allowed_routes": ["*"],
                "allowed_fusions": ["*"],
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
                "request_limit": None,
                "expiration_date": None,
                "ip_restrictions": [],
            })(),
        )
        raw_key = k.raw_api_key

    judge_called_with = []

    def mock_fusion_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if key_a_secret in auth:
            return httpx.Response(200, json={
                "id": "cmpl-a", "object": "chat.completion", "created": 1, "model": f"gpt-model-{run_id}",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Solution from Candidate A"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            })
        elif key_b_secret in auth:
            return httpx.Response(200, json={
                "id": "cmpl-b", "object": "chat.completion", "created": 1, "model": f"gpt-model-{run_id}",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Solution from Candidate B"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
            })
        elif key_judge_secret in auth:
            req_body = json.loads(request.content.decode())
            judge_called_with.append(req_body)
            return httpx.Response(200, json={
                "id": "cmpl-judge", "object": "chat.completion", "created": 1, "model": f"gpt-model-{run_id}",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Synthesized Best Solution (combining A & B)"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
            })
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_fusion_handler))

    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "model": f"fusion/{fusion_slug}",
                    "messages": [{"role": "user", "content": "Implement binary search"}],
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "Synthesized Best Solution" in data["choices"][0]["message"]["content"]
            assert len(judge_called_with) == 1
            judge_prompt = judge_called_with[0]["messages"][-1]["content"]
            assert "Candidate A" in judge_prompt
            assert "Candidate B" in judge_prompt
            assert "Solution from Candidate A" in judge_prompt
            assert "Solution from Candidate B" in judge_prompt


@pytest.mark.asyncio
async def test_nested_routing_profiles():
    run_id = uuid.uuid4().hex[:8]

    async with AsyncSessionLocal() as db:
        # 1. Setup Provider & Credentials
        provider = Provider(
            name=f"Mock Nested Provider {run_id}",
            slug=f"nested-provider-{run_id}",
            adapter_type="generic_openai",
            base_url="https://api.nested.mock/v1",
            auth_type="bearer",
            auth_header="Authorization",
            enabled=True,
        )
        db.add(provider)
        await db.commit()
        await db.refresh(provider)

        key_sub_secret = f"sk-sub-{run_id}"
        c_sub = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Sub Key {run_id}",
                "api_key": key_sub_secret,
                "proxy_id": None,
                "priority": 1,
                "weight": 1,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        key_backup_secret = f"sk-backup-{run_id}"
        c_backup = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Backup Key {run_id}",
                "api_key": key_backup_secret,
                "proxy_id": None,
                "priority": 2,
                "weight": 1,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        m_sub = DiscoveredModel(
            provider_id=provider.id,
            credential_id=c_sub.id,
            provider_model_id=f"model-sub-{run_id}",
            display_name="Model Sub",
            canonical_slug=f"mock/model-sub-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        m_backup = DiscoveredModel(
            provider_id=provider.id,
            credential_id=c_backup.id,
            provider_model_id=f"model-backup-{run_id}",
            display_name="Model Backup",
            canonical_slug=f"mock/model-backup-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        db.add_all([m_sub, m_backup])
        await db.commit()
        await db.refresh(m_sub)
        await db.refresh(m_backup)

        # 2. Create Sub-Profile
        sub_slug = f"sub-route-{run_id}"
        sub_profile = RoutingProfile(
            name=f"Sub Profile {run_id}",
            slug=sub_slug,
            strategy="priority",
            retry_count=1,
            timeout_seconds=10.0,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX"],
            enabled=True,
        )
        db.add(sub_profile)
        await db.flush()

        cand_sub = RoutingCandidate(
            profile_id=sub_profile.id,
            candidate_type="model",
            target_profile_id=None,
            provider_id=provider.id,
            credential_id=c_sub.id,
            model_id=m_sub.id,
            priority_order=0,
            is_active=True,
        )
        db.add(cand_sub)
        await db.commit()
        await db.refresh(sub_profile)

        # 3. Create Parent Profile containing Sub-Profile as candidate #1 and Backup Model as candidate #2
        parent_slug = f"parent-route-{run_id}"
        parent_profile = RoutingProfile(
            name=f"Parent Profile {run_id}",
            slug=parent_slug,
            strategy="priority",
            retry_count=2,
            timeout_seconds=10.0,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX"],
            enabled=True,
        )
        db.add(parent_profile)
        await db.flush()

        # Candidate 1: Embedded Sub-Profile
        cand_nested_p = RoutingCandidate(
            profile_id=parent_profile.id,
            candidate_type="profile",
            target_profile_id=sub_profile.id,
            provider_id=None,
            credential_id=None,
            model_id=None,
            priority_order=0,
            is_active=True,
        )
        # Candidate 2: Direct model backup
        cand_direct = RoutingCandidate(
            profile_id=parent_profile.id,
            candidate_type="model",
            target_profile_id=None,
            provider_id=provider.id,
            credential_id=c_backup.id,
            model_id=m_backup.id,
            priority_order=1,
            is_active=True,
        )
        db.add_all([cand_nested_p, cand_direct])

        # Router API key
        k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"Key {run_id}",
                "permissions": ["direct", "routes", "fusion"],
                "allowed_models": ["*"],
                "allowed_routes": ["*"],
                "allowed_fusions": ["*"],
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
                "request_limit": None,
                "expiration_date": None,
                "ip_restrictions": [],
            })(),
        )
        raw_key = k.raw_api_key
        await db.commit()

    # Test Case 1: Sub-profile succeeds
    def mock_sub_success(request: httpx.Request):
        auth = request.headers.get("Authorization", "")
        if key_sub_secret in auth:
            return httpx.Response(200, json={
                "id": "cmpl-sub", "object": "chat.completion", "created": 1, "model": f"model-sub-{run_id}",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello from nested sub-profile!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 8, "total_tokens": 13},
            })
        return httpx.Response(500, json={"error": "Unexpected key"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_sub_success))
    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "model": f"route/{parent_slug}",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["choices"][0]["message"]["content"] == "Hello from nested sub-profile!"

    # Test Case 2: Sub-profile fails, parent profile falls back to candidate #2 (Backup Model)
    def mock_sub_failure_backup_success(request: httpx.Request):
        auth = request.headers.get("Authorization", "")
        if key_sub_secret in auth:
            return httpx.Response(502, json={"error": {"message": "Sub-profile upstream error", "type": "bad_gateway"}})
        elif key_backup_secret in auth:
            return httpx.Response(200, json={
                "id": "cmpl-backup", "object": "chat.completion", "created": 1, "model": f"model-backup-{run_id}",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello from parent fallback backup!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 8, "total_tokens": 13},
            })
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_sub_failure_backup_success))
    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "model": f"route/{parent_slug}",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["choices"][0]["message"]["content"] == "Hello from parent fallback backup!"


@pytest.mark.asyncio
async def test_thinking_effort_routing_override():
    run_id = uuid.uuid4().hex[:8]
    captured_requests = []
    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, "openai")

        key_secret = f"sk-mock-thinking-{run_id}"
        cred = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Key Thinking {run_id}",
                "api_key": key_secret,
                "proxy_id": None,
                "priority": 1,
                "weight": 1,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        model = DiscoveredModel(
            provider_id=provider.id,
            credential_id=cred.id,
            provider_model_id=f"o3-mini-{run_id}",
            display_name="o3 mini",
            canonical_slug=f"mock/o3-mini-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        db.add(model)
        await db.commit()
        await db.refresh(model)

        prof = RoutingProfile(
            name=f"Thinking Profile {run_id}",
            slug=f"thinking-{run_id}",
            strategy="priority",
            retry_count=2,
            timeout_seconds=30.0,
            thinking_effort="medium",
        )
        db.add(prof)
        await db.commit()
        await db.refresh(prof)

        cand = RoutingCandidate(
            profile_id=prof.id,
            candidate_type="model",
            provider_id=provider.id,
            credential_id=cred.id,
            model_id=model.id,
            priority_order=0,
            is_active=True,
            thinking_effort="8192",
        )
        db.add(cand)
        await db.commit()

        k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"Thinking Router Key {run_id}",
                "permissions": ["direct", "routes", "fusion"],
                "allowed_models": ["*"],
                "allowed_routes": ["*"],
                "allowed_fusions": ["*"],
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
                "request_limit": None,
                "expiration_date": None,
                "ip_restrictions": [],
            })(),
        )
        raw_key = k.raw_api_key

    def mock_server(request: httpx.Request):
        req_body = json.loads(request.content.decode("utf-8"))
        captured_requests.append(req_body)
        return httpx.Response(200, json={
            "id": "cmpl-thinking", "object": "chat.completion", "created": 1, "model": f"o3-mini-{run_id}",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Thought deeply!"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        })

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_server))
    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "model": f"route/thinking-{run_id}",
                    "messages": [{"role": "user", "content": "Solve math"}],
                },
            )
            assert resp.status_code == 200
            assert len(captured_requests) == 1
            assert captured_requests[0].get("reasoning_effort") == "8192"

@pytest.mark.asyncio
async def test_direct_routing_candidate_provider_isolation():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p_google = Provider(name=f"Google {run_id}", slug=f"google-{run_id}", base_url="https://api.google.com", adapter_type="google")
        p_or = Provider(name=f"OpenRouter {run_id}", slug=f"openrouter-{run_id}", base_url="https://openrouter.ai/api/v1", adapter_type="openai")
        db.add(p_google)
        db.add(p_or)
        await db.flush()

        c_g1 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {"provider_id": p_google.id, "name": "Google Key 1", "api_key": "key1", "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})()
        )
        c_g2 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {"provider_id": p_google.id, "name": "Google Key 2", "api_key": "key2", "proxy_id": None, "priority": 2, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})()
        )
        c_or = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {"provider_id": p_or.id, "name": "OpenRouter Key", "api_key": "key_or", "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})()
        )

        m_google = DiscoveredModel(
            provider_id=p_google.id,
            credential_id=c_g1.id,
            provider_model_id=f"gemini-flash-{run_id}",
            canonical_slug=f"google-{run_id}/gemini-flash-{run_id}",
            display_name="Gemini Flash",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        m_openrouter = DiscoveredModel(
            provider_id=p_or.id,
            credential_id=c_or.id,
            provider_model_id=f"google-{run_id}/gemini-flash-{run_id}",
            canonical_slug=f"openrouter-{run_id}/google-{run_id}/gemini-flash-{run_id}",
            display_name="OpenRouter Gemini Flash",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        db.add(m_google)
        db.add(m_openrouter)
        await db.commit()

        # 1. Calling by canonical slug MUST return ONLY Google credentials, NEVER OpenRouter
        cands = await RoutingEngine._get_candidate_credentials_for_model(db, f"google-{run_id}/gemini-flash-{run_id}")
        assert len(cands) == 2
        for cred, model in cands:
            assert cred.provider_id == p_google.id
            assert cred.provider.slug == f"google-{run_id}"

        # 2. Disabled model in catalog raises disabled exception
        m_google.enabled = False
        await db.commit()

        with pytest.raises(RouterException) as exc_info:
            await RoutingEngine._raise_no_candidates(db, f"google-{run_id}/gemini-flash-{run_id}", "req_test")
        assert "disabled in the Models Catalog" in str(exc_info.value)


@pytest.mark.asyncio
async def test_priority_route_all_keys_candidate_fallback():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"mock-allkeys-{run_id}")

        key1_secret = f"sk-mock-key1-{run_id}"
        key2_secret = f"sk-mock-key2-{run_id}"

        c1 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Key 1 {run_id}",
                "api_key": key1_secret,
                "proxy_id": None,
                "priority": 1,
                "weight": 10,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        c2 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"Key 2 {run_id}",
                "api_key": key2_secret,
                "proxy_id": None,
                "priority": 2,
                "weight": 5,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        m = DiscoveredModel(
            provider_id=provider.id,
            credential_id=c1.id,
            provider_model_id=f"gemini-flash-{run_id}",
            display_name=f"Gemini Flash {run_id}",
            canonical_slug=f"mock-allkeys-{run_id}/gemini-flash-{run_id}",
            capabilities={"chat": True, "streaming": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        route_slug = f"allkeys-route-{run_id}"
        profile = RoutingProfile(
            name=f"All Keys Route {run_id}",
            slug=route_slug,
            strategy="priority",
            retry_count=3,
            timeout_seconds=10.0,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX"],
            enabled=True,
        )
        db.add(profile)
        await db.flush()

        # Candidate with credential_id=None -> represents "⚡ Все ключи провайдера (полный fallback)"
        cand = RoutingCandidate(
            profile_id=profile.id,
            provider_id=provider.id,
            credential_id=None,
            model_id=m.id,
            priority_order=1,
            is_active=True,
        )
        db.add(cand)
        await db.commit()

        k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"Client Key {run_id}",
                "permissions": ["direct", "routes", "fusion"],
                "allowed_models": ["*"],
                "allowed_routes": ["*"],
                "allowed_fusions": ["*"],
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
                "request_limit": None,
                "expiration_date": None,
                "ip_restrictions": [],
            })(),
        )
        raw_key = k.raw_api_key

    def mock_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if key1_secret in auth:
            # Key 1 fails with 503 high demand (fallback-eligible error)
            return httpx.Response(503, json={"error": {"code": 503, "message": "This model is currently experiencing high demand. Please try again later.", "status": "UNAVAILABLE"}})
        elif key2_secret in auth:
            # Key 2 succeeds!
            if request.url.path.endswith("/chat/completions"):
                body = json.loads(request.content.decode())
                if body.get("stream"):
                    chunk1 = "data: " + json.dumps({"choices": [{"delta": {"content": "Streamed from Key 2!"}}]}) + "\n\n"
                    chunk2 = "data: [DONE]\n\n"
                    return httpx.Response(200, content=(chunk1 + chunk2).encode("utf-8"), headers={"Content-Type": "text/event-stream"})
                return httpx.Response(
                    200,
                    json={
                        "id": f"chatcmpl-allkeys-{run_id}",
                        "object": "chat.completion",
                        "created": 1234567,
                        "model": f"gemini-flash-{run_id}",
                        "choices": [
                            {"index": 0, "message": {"role": "assistant", "content": "Success from Key 2 via All Keys Fallback!"}, "finish_reason": "stop"}
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22},
                    },
                )
        return httpx.Response(404, json={"error": "Not found"})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Non-streaming Priority route fallback across all keys
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "model": f"route/{route_slug}",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["choices"][0]["message"]["content"] == "Success from Key 2 via All Keys Fallback!"

            # 2. Streaming Priority route fallback across all keys
            stream_resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "model": f"route/{route_slug}",
                    "messages": [{"role": "user", "content": "Stream me"}],
                    "stream": True,
                },
            )
            assert stream_resp.status_code == 200, stream_resp.text
            stream_text = stream_resp.text
            assert "Streamed from Key 2!" in stream_text



