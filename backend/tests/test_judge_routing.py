import pytest
import httpx
import json
import uuid
import asyncio
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, delete

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    Provider,
    ProviderCredential,
    DiscoveredModel,
    JudgeProfile,
    JudgeCandidate,
    RequestLog,
)
from app.schemas.chat import (
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.services.api_key_service import ApiKeyService
from app.services.credential_service import CredentialService
from app.services.auth_service import AuthService


async def get_or_create_provider(db, slug="openai-judge-test"):
    p_res = await db.execute(select(Provider).where(Provider.slug == slug))
    provider = p_res.scalars().first()
    if not provider:
        provider = Provider(
            name="OpenAI Judge Test",
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
async def test_judge_admin_crud_and_validation():
    """Tests CRUD lifecycle and validation for Judge profiles via /api/admin/judges."""
    run_id = uuid.uuid4().hex[:8]
    token = AuthService.create_access_token("admin")
    admin_headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncSessionLocal() as db:
        p1 = await get_or_create_provider(db, f"judge-prov1-{run_id}")
        p2 = await get_or_create_provider(db, f"judge-prov2-{run_id}")

        c1 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": p1.id,
                "name": f"Cred1 {run_id}",
                "api_key": "sk-mock-key-1",
                "priority": 1,
                "weight": 1,
                "group_name": None,
                "proxy_id": None,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        c2 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": p2.id,
                "name": f"Cred2 {run_id}",
                "api_key": "sk-mock-key-2",
                "priority": 1,
                "weight": 1,
                "group_name": None,
                "proxy_id": None,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        judge_model = DiscoveredModel(
            provider_id=p1.id,
            credential_id=c1.id,
            provider_model_id="gpt-4o-judge",
            display_name="GPT-4o Judge",
            canonical_slug=f"openai/gpt-4o-judge-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        cand1_model = DiscoveredModel(
            provider_id=p1.id,
            credential_id=c1.id,
            provider_model_id="claude-3-5-sonnet",
            display_name="Claude 3.5 Sonnet",
            canonical_slug=f"anthropic/claude-3-5-sonnet-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        cand2_model = DiscoveredModel(
            provider_id=p2.id,
            credential_id=c2.id,
            provider_model_id="gpt-4o-mini",
            display_name="GPT-4o Mini",
            canonical_slug=f"openai/gpt-4o-mini-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        db.add_all([judge_model, cand1_model, cand2_model])

        router_k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"TestKey {run_id}",
                "permissions": ["direct", "routes", "fusion", "judge"],
                "allowed_models": ["*"],
                "allowed_routes": ["*"],
                "allowed_fusions": ["*"],
                "allowed_judges": ["*"],
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
                "request_limit": None,
                "expiration_date": None,
                "ip_restrictions": [],
            })(),
        )
        await db.commit()
        await db.refresh(judge_model)
        await db.refresh(cand1_model)
        await db.refresh(cand2_model)
        raw_key = router_k.raw_api_key

    client_headers = {"Authorization": f"Bearer {raw_key}"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Judge Profile
        slug = f"smart-router-{run_id}"
        create_payload = {
            "name": f"Smart Router {run_id}",
            "slug": slug,
            "description": "Routes complex code to Sonnet, lightweight chat to Mini",
            "strategy": "auto",
            "judge_type": "model",
            "judge_provider_id": p1.id,
            "judge_credential_id": c1.id,
            "judge_model_id": judge_model.id,
            "judge_temperature": 0.1,
            "timeout_seconds": 30.0,
            "enabled": True,
            "candidates": [
                {
                    "candidate_type": "model",
                    "provider_id": p1.id,
                    "credential_id": c1.id,
                    "model_id": cand1_model.id,
                    "priority_order": 0,
                    "label": "Sonnet Coder",
                    "task_types": ["code", "math", "reasoning"],
                    "complexity_level": "high",
                    "description": "Best for complex programming, algorithms, and deep logic",
                    "is_active": True,
                },
                {
                    "candidate_type": "model",
                    "provider_id": p2.id,
                    "credential_id": c2.id,
                    "model_id": cand2_model.id,
                    "priority_order": 1,
                    "label": "Mini Chat",
                    "task_types": ["chat", "general", "translation"],
                    "complexity_level": "low",
                    "description": "Best for simple chat, greetings, quick queries",
                    "is_active": True,
                },
            ],
        }

        resp = await client.post("/api/admin/judges", json=create_payload, headers=admin_headers)
        assert resp.status_code == 201, resp.text
        created = resp.json()
        assert created["slug"] == slug
        assert len(created["candidates"]) == 2
        assert created["candidates"][0]["complexity_level"] == "high"
        assert "code" in created["candidates"][0]["task_types"]
        profile_id = created["id"]

        # 2. List Profiles
        resp = await client.get("/api/admin/judges", headers=admin_headers)
        assert resp.status_code == 200
        profiles = resp.json()
        assert any(p["id"] == profile_id for p in profiles)

        # 3. Get by ID
        resp = await client.get(f"/api/admin/judges/{profile_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == profile_id

        # 4. Check /v1/models exposes judge/<slug>
        resp = await client.get("/v1/models", headers=client_headers)
        assert resp.status_code == 200, resp.text
        models_data = resp.json()["data"]
        assert any(m["id"] == f"judge/{slug}" for m in models_data)

        # 5. Check /v1/models/judge/<slug>
        resp = await client.get(f"/v1/models/judge/{slug}", headers=client_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == f"judge/{slug}"

        # 6. Update Profile
        update_payload = {
            "description": "Updated description for smart router",
            "timeout_seconds": 45.0,
        }
        resp = await client.put(f"/api/admin/judges/{profile_id}", json=update_payload, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["timeout_seconds"] == 45.0
        assert resp.json()["description"] == "Updated description for smart router"


@pytest.mark.asyncio
async def test_judge_evaluation_and_routing():
    """Tests that Judge evaluates query complexity/task type and routes to the selected candidate."""
    run_id = uuid.uuid4().hex[:8]
    token = AuthService.create_access_token("admin")
    transport = ASGITransport(app=app)

    async with AsyncSessionLocal() as db:
        p = await get_or_create_provider(db, f"eval-prov-{run_id}")
        c = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": p.id,
                "name": f"EvalCred {run_id}",
                "api_key": "sk-eval-key",
                "priority": 1,
                "weight": 1,
                "group_name": None,
                "proxy_id": None,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        judge_model = DiscoveredModel(
            provider_id=p.id,
            credential_id=c.id,
            provider_model_id="judge-eval-llm",
            display_name="Judge LLM",
            canonical_slug=f"eval/judge-llm-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        cand_code = DiscoveredModel(
            provider_id=p.id,
            credential_id=c.id,
            provider_model_id="heavy-coder-model",
            display_name="Heavy Coder",
            canonical_slug=f"eval/coder-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        cand_chat = DiscoveredModel(
            provider_id=p.id,
            credential_id=c.id,
            provider_model_id="light-chat-model",
            display_name="Light Chat",
            canonical_slug=f"eval/chat-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        db.add_all([judge_model, cand_code, cand_chat])

        router_k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"EvalKey {run_id}",
                "permissions": ["direct", "routes", "fusion", "judge"],
                "allowed_models": ["*"],
                "allowed_routes": ["*"],
                "allowed_fusions": ["*"],
                "allowed_judges": ["*"],
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
                "request_limit": None,
                "expiration_date": None,
                "ip_restrictions": [],
            })(),
        )
        raw_key = router_k.raw_api_key

        slug = f"route-test-{run_id}"
        j_prof = JudgeProfile(
            name="Route Test Judge",
            slug=slug,
            strategy="auto",
            judge_type="model",
            judge_provider_id=p.id,
            judge_credential_id=c.id,
            judge_model_id=judge_model.id,
            timeout_seconds=30.0,
            enabled=True,
        )
        db.add(j_prof)
        await db.flush()

        cand0 = JudgeCandidate(
            profile_id=j_prof.id,
            candidate_type="model",
            provider_id=p.id,
            credential_id=c.id,
            model_id=cand_code.id,
            priority_order=0,
            label="Coder Expert",
            task_types=["code", "architecture"],
            complexity_level="high",
            description="Deep software engineering and concurrency",
            is_active=True,
        )
        cand1 = JudgeCandidate(
            profile_id=j_prof.id,
            candidate_type="model",
            provider_id=p.id,
            credential_id=c.id,
            model_id=cand_chat.id,
            priority_order=1,
            label="Fast Chat",
            task_types=["chat", "casual"],
            complexity_level="low",
            description="Casual chatter and simple greetings",
            is_active=True,
        )
        db.add_all([cand0, cand1])
        await db.commit()
        await db.refresh(j_prof)

    # Mock adapter chat completions to simulate:
    # 1. Judge selecting candidate 0 when prompt is complex code
    # 2. Candidate 0 generating the answer
    async def mock_adapter_chat(*args, **kwargs):
        req = kwargs.get("request")
        model_id = kwargs.get("model_id")
        if model_id == "judge-eval-llm":
            # Judge deliberation response: selects candidate 0
            decision_content = json.dumps({
                "selected_candidate_index": 0,
                "estimated_complexity": "high",
                "detected_task_type": "code",
                "reasoning": "The prompt asks for complex distributed consensus in Rust.",
            })
            return ChatCompletionResponse(
                id=f"chatcmpl-judge-{uuid.uuid4().hex[:8]}",
                object="chat.completion",
                created=1700000000,
                model="judge-eval-llm",
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=decision_content),
                        finish_reason="stop",
                    )
                ],
                usage=UsageInfo(prompt_tokens=40, completion_tokens=30, total_tokens=70),
            )
        else:
            # Candidate execution response
            return ChatCompletionResponse(
                id=f"chatcmpl-cand-{uuid.uuid4().hex[:8]}",
                object="chat.completion",
                created=1700000000,
                model=model_id,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(
                            role="assistant",
                            content="Here is the Raft distributed consensus implementation in Rust.",
                        ),
                        finish_reason="stop",
                    )
                ],
                usage=UsageInfo(prompt_tokens=15, completion_tokens=85, total_tokens=100),
            )

    with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_adapter_chat):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test admin prompt evaluation test endpoint
            test_resp = await client.post(
                f"/api/admin/judges/{j_prof.id}/test",
                json={"prompt": "Write a Raft distributed consensus implementation in Rust with memory fences."},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert test_resp.status_code == 200, test_resp.text
            test_data = test_resp.json()
            assert test_data["selected_candidate_label"] == "Coder Expert"
            assert test_data["estimated_complexity"] == "high"
            assert "Rust" in test_data["judge_reasoning"]

            # Test actual end-to-end OpenAI-compatible chat completion
            chat_payload = {
                "model": f"judge/{slug}",
                "messages": [
                    {"role": "user", "content": "Write a Raft distributed consensus implementation in Rust with memory fences."}
                ],
            }
            resp = await client.post(
                "/v1/chat/completions",
                json=chat_payload,
                headers={"Authorization": f"Bearer {raw_key}"},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["model"] == f"judge/{slug}"
            assert "Raft" in data["choices"][0]["message"]["content"]

    # Verify request log recorded mode="JUDGE" and metadata
    async with AsyncSessionLocal() as db:
        log_entry = (
            await db.execute(
                select(RequestLog)
                .where(RequestLog.requested_model == f"judge/{slug}")
                .order_by(RequestLog.id.desc())
            )
        ).scalars().first()
        assert log_entry is not None
        assert log_entry.mode == "JUDGE"
        assert log_entry.status == "SUCCESS"
        assert log_entry.metadata_json.get("estimated_complexity") == "high"
        assert "Coder Expert" in log_entry.metadata_json.get("selected_candidate_label", "")


@pytest.mark.asyncio
async def test_judge_fallback_on_error():
    """Tests that if Judge evaluation fails or throws an exception, router falls back to default candidate."""
    run_id = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=app)

    async with AsyncSessionLocal() as db:
        p = await get_or_create_provider(db, f"fallback-prov-{run_id}")
        c = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": p.id,
                "name": f"FbCred {run_id}",
                "api_key": "sk-fb-key",
                "priority": 1,
                "weight": 1,
                "group_name": None,
                "proxy_id": None,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        judge_model = DiscoveredModel(
            provider_id=p.id,
            credential_id=c.id,
            provider_model_id="failing-judge-llm",
            display_name="Failing Judge",
            canonical_slug=f"fb/judge-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        cand_model = DiscoveredModel(
            provider_id=p.id,
            credential_id=c.id,
            provider_model_id="fb-candidate-model",
            display_name="Fallback Model",
            canonical_slug=f"fb/cand-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        db.add_all([judge_model, cand_model])

        router_k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"FbKey {run_id}",
                "permissions": ["direct", "routes", "fusion", "judge"],
                "allowed_models": ["*"],
                "allowed_routes": ["*"],
                "allowed_fusions": ["*"],
                "allowed_judges": ["*"],
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
                "request_limit": None,
                "expiration_date": None,
                "ip_restrictions": [],
            })(),
        )
        raw_key = router_k.raw_api_key

        slug = f"fallback-test-{run_id}"
        j_prof = JudgeProfile(
            name="Fallback Judge",
            slug=slug,
            strategy="auto",
            judge_type="model",
            judge_provider_id=p.id,
            judge_credential_id=c.id,
            judge_model_id=judge_model.id,
            timeout_seconds=5.0,
            enabled=True,
        )
        db.add(j_prof)
        await db.flush()

        cand = JudgeCandidate(
            profile_id=j_prof.id,
            candidate_type="model",
            provider_id=p.id,
            credential_id=c.id,
            model_id=cand_model.id,
            priority_order=0,
            label="Safe Fallback",
            task_types=["general"],
            complexity_level="all",
            description="Safety model",
            is_active=True,
        )
        db.add(cand)
        await db.commit()

    # Simulate Judge model failing with 500 error
    async def mock_failing_judge(*args, **kwargs):
        model_id = kwargs.get("model_id")
        if model_id == "failing-judge-llm":
            raise RuntimeError("Upstream judge model timeout / crash")
        return ChatCompletionResponse(
            id=f"chatcmpl-rescued-{uuid.uuid4().hex[:8]}",
            object="chat.completion",
            created=1700000000,
            model=model_id,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Rescued by fallback candidate!"),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

    with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_failing_judge):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            chat_payload = {
                "model": f"judge/{slug}",
                "messages": [{"role": "user", "content": "Hello!"}],
            }
            resp = await client.post(
                "/v1/chat/completions",
                json=chat_payload,
                headers={"Authorization": f"Bearer {raw_key}"},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert "Rescued by fallback" in data["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_judge_streaming_routing():
    """Tests streaming SSE chat completion with judge routing."""
    run_id = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=app)

    async with AsyncSessionLocal() as db:
        p = await get_or_create_provider(db, f"stream-prov-{run_id}")
        c = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": p.id,
                "name": f"StreamCred {run_id}",
                "api_key": "sk-stream-key",
                "priority": 1,
                "weight": 1,
                "group_name": None,
                "proxy_id": None,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        judge_model = DiscoveredModel(
            provider_id=p.id,
            credential_id=c.id,
            provider_model_id="stream-judge-llm",
            display_name="Stream Judge",
            canonical_slug=f"stream/judge-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        cand_model = DiscoveredModel(
            provider_id=p.id,
            credential_id=c.id,
            provider_model_id="stream-cand-llm",
            display_name="Stream Candidate",
            canonical_slug=f"stream/cand-{run_id}",
            capabilities={"chat": True},
            supported_endpoints=["/chat/completions"],
            model_type="openai",
            enabled=True,
            available=True,
            is_visible=True,
        )
        db.add_all([judge_model, cand_model])

        router_k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"StreamKey {run_id}",
                "permissions": ["direct", "routes", "fusion", "judge"],
                "allowed_models": ["*"],
                "allowed_routes": ["*"],
                "allowed_fusions": ["*"],
                "allowed_judges": ["*"],
                "rate_limit_rpm": None,
                "rate_limit_tpm": None,
                "request_limit": None,
                "expiration_date": None,
                "ip_restrictions": [],
            })(),
        )
        raw_key = router_k.raw_api_key

        slug = f"stream-test-{run_id}"
        j_prof = JudgeProfile(
            name="Stream Judge",
            slug=slug,
            strategy="auto",
            judge_type="model",
            judge_provider_id=p.id,
            judge_credential_id=c.id,
            judge_model_id=judge_model.id,
            timeout_seconds=10.0,
            enabled=True,
        )
        db.add(j_prof)
        await db.flush()

        cand = JudgeCandidate(
            profile_id=j_prof.id,
            candidate_type="model",
            provider_id=p.id,
            credential_id=c.id,
            model_id=cand_model.id,
            priority_order=0,
            label="Streaming Model",
            task_types=["general"],
            complexity_level="all",
            description="Streams responses",
            is_active=True,
        )
        db.add(cand)
        await db.commit()

    async def mock_judge_chat(*args, **kwargs):
        decision = json.dumps({
            "selected_candidate_index": 0,
            "estimated_complexity": "low",
            "detected_task_type": "chat",
            "reasoning": "Standard streaming hello",
        })
        return ChatCompletionResponse(
            id=f"chatcmpl-j-{uuid.uuid4().hex[:8]}",
            object="chat.completion",
            created=1700000000,
            model="stream-judge-llm",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=decision),
                    finish_reason="stop",
                )
            ],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        )

    async def mock_cand_stream(*args, **kwargs):
        chunk1 = {
            "id": "chatcmpl-chunk-1",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "stream-cand-llm",
            "choices": [{"index": 0, "delta": {"content": "Hello, "}, "finish_reason": None}],
        }
        chunk2 = {
            "id": "chatcmpl-chunk-2",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "stream-cand-llm",
            "choices": [{"index": 0, "delta": {"content": "world!"}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(chunk1)}\n\n"
        yield f"data: {json.dumps(chunk2)}\n\n"
        yield "data: [DONE]\n\n"

    with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_judge_chat), \
         patch("app.adapters.openai.GenericOpenAIAdapter.stream_chat", side_effect=mock_cand_stream):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            chat_payload = {
                "model": f"judge/{slug}",
                "messages": [{"role": "user", "content": "Hello world!"}],
                "stream": True,
            }
            resp = await client.post(
                "/v1/chat/completions",
                json=chat_payload,
                headers={"Authorization": f"Bearer {raw_key}"},
            )
            assert resp.status_code == 200, resp.text
            assert "text/event-stream" in resp.headers.get("content-type", "")
            chunks = resp.text
            assert "Hello, " in chunks
            assert "world!" in chunks
            assert "[DONE]" in chunks

