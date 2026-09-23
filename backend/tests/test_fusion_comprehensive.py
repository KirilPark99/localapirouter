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
    FusionProfile,
    FusionParticipant,
    RequestLog,
)
from app.core.circuit_breaker import circuit_breaker
from app.services.api_key_service import ApiKeyService
from app.services.credential_service import CredentialService
from app.services.auth_service import AuthService


async def get_or_create_provider(db, slug="openai-fusion-test"):
    p_res = await db.execute(select(Provider).where(Provider.slug == slug))
    provider = p_res.scalars().first()
    if not provider:
        provider = Provider(
            name="OpenAI Fusion Test",
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
async def test_fusion_admin_api_crud_and_validation():
    """Tests CRUD lifecycle and validation for Fusion profiles via /api/admin/fusion."""
    run_id = uuid.uuid4().hex[:8]
    token = AuthService.create_access_token("admin")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncSessionLocal() as db:
        p1 = await get_or_create_provider(db, f"prov1-{run_id}")
        p2 = await get_or_create_provider(db, f"prov2-{run_id}")

        c1 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": p1.id, "name": f"K1-{run_id}", "api_key": f"sk-k1-{run_id}",
                "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                "tpm_limit": None, "max_concurrency": None,
            })(),
        )
        c2 = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": p2.id, "name": f"K2-{run_id}", "api_key": f"sk-k2-{run_id}",
                "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                "tpm_limit": None, "max_concurrency": None,
            })(),
        )

        m1 = DiscoveredModel(
            provider_id=p1.id, credential_id=c1.id, provider_model_id=f"gpt-4o-{run_id}",
            display_name="GPT-4o", canonical_slug=f"prov1-{run_id}/gpt-4o-{run_id}",
            capabilities={"chat": True}, supported_endpoints=["/chat/completions"],
            enabled=True, available=True,
        )
        m2 = DiscoveredModel(
            provider_id=p2.id, credential_id=c2.id, provider_model_id=f"claude-35-{run_id}",
            display_name="Claude", canonical_slug=f"prov2-{run_id}/claude-35-{run_id}",
            capabilities={"chat": True}, supported_endpoints=["/chat/completions"],
            enabled=True, available=True,
        )
        db.add_all([m1, m2])
        await db.commit()
        await db.refresh(m1)
        await db.refresh(m2)

        p1_id, p2_id = p1.id, p2.id
        c1_id, c2_id = c1.id, c2.id
        m1_id, m2_id = m1.id, m2.id

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Validation error: Mismatched provider_id and model_id
        bad_payload = {
            "name": f"Bad Fusion {run_id}",
            "slug": f"bad-fusion-{run_id}",
            "strategy": "synthesize",
            "judge_provider_id": p1_id,
            "judge_model_id": m2_id,  # m2 belongs to p2, not p1!
            "participants": [
                {"provider_id": p1_id, "credential_id": c1_id, "model_id": m1_id, "label": "Cand 1"}
            ],
            "min_successful_candidates": 1,
        }
        bad_res = await client.post("/api/admin/fusion", json=bad_payload, headers=headers)
        assert bad_res.status_code == 400
        assert "does not belong to provider" in bad_res.json()["detail"]

        # 2. Validation error: Duplicate slug
        valid_payload = {
            "name": f"Valid Fusion {run_id}",
            "slug": f"valid-fusion-{run_id}",
            "strategy": "synthesize",
            "judge_provider_id": p1_id,
            "judge_credential_id": c1_id,
            "judge_model_id": m1_id,
            "participants": [
                {"provider_id": p1_id, "credential_id": c1_id, "model_id": m1_id, "label": "A", "is_active": True},
                {"provider_id": p2_id, "credential_id": c2_id, "model_id": m2_id, "label": "B", "is_active": True},
            ],
            "min_successful_candidates": 2,
            "timeout_seconds": 30.0,
            "enabled": True,
        }
        create_res = await client.post("/api/admin/fusion", json=valid_payload, headers=headers)
        assert create_res.status_code == 201
        created_data = create_res.json()
        prof_id = created_data["id"]
        assert created_data["slug"] == f"valid-fusion-{run_id}"
        assert len(created_data["participants"]) == 2

        # Duplicate slug attempt
        dup_res = await client.post("/api/admin/fusion", json=valid_payload, headers=headers)
        assert dup_res.status_code == 400
        assert "already exists" in dup_res.json()["detail"]

        # 3. List profiles
        list_res = await client.get("/api/admin/fusion", headers=headers)
        assert list_res.status_code == 200
        slugs = [p["slug"] for p in list_res.json()]
        assert f"valid-fusion-{run_id}" in slugs

        # 4. Get by ID
        get_res = await client.get(f"/api/admin/fusion/{prof_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == f"Valid Fusion {run_id}"

        # 5. Update profile (change strategy to best_of_n)
        update_payload = {
            "name": f"Updated Fusion {run_id}",
            "strategy": "best_of_n",
            "min_successful_candidates": 1,
            "timeout_seconds": 45.0,
            "participants": [
                {"provider_id": p1_id, "credential_id": c1_id, "model_id": m1_id, "label": "Cand Alpha", "is_active": True},
            ],
        }
        upd_res = await client.put(f"/api/admin/fusion/{prof_id}", json=update_payload, headers=headers)
        assert upd_res.status_code == 200
        assert upd_res.json()["strategy"] == "best_of_n"
        assert upd_res.json()["min_successful_candidates"] == 1

        # 6. Delete profile
        del_res = await client.delete(f"/api/admin/fusion/{prof_id}", headers=headers)
        assert del_res.status_code == 200

        # Verify profile and participants are deleted
        async with AsyncSessionLocal() as db:
            p_check = await db.get(FusionProfile, prof_id)
            assert p_check is None
            parts_check = await db.execute(select(FusionParticipant).where(FusionParticipant.profile_id == prof_id))
            assert len(parts_check.scalars().all()) == 0


@pytest.mark.asyncio
async def test_fusion_all_four_strategies():
    """Tests execution of all 4 fusion strategies: synthesize, best_of_n, consensus, critique_and_rewrite."""
    strategies = ["synthesize", "best_of_n", "consensus", "critique_and_rewrite"]

    for strategy in strategies:
        run_id = uuid.uuid4().hex[:8]
        key_cand1 = f"sk-cand1-{strategy}-{run_id}"
        key_cand2 = f"sk-cand2-{strategy}-{run_id}"
        key_judge = f"sk-judge-{strategy}-{run_id}"

        async with AsyncSessionLocal() as db:
            provider = await get_or_create_provider(db, f"prov-{strategy}-{run_id}")

            c1 = await CredentialService.create_credential(
                db, data=type("Obj", (), {
                    "provider_id": provider.id, "name": "C1", "api_key": key_cand1,
                    "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                    "tpm_limit": None, "max_concurrency": None,
                })(),
            )
            c2 = await CredentialService.create_credential(
                db, data=type("Obj", (), {
                    "provider_id": provider.id, "name": "C2", "api_key": key_cand2,
                    "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                    "tpm_limit": None, "max_concurrency": None,
                })(),
            )
            c_judge = await CredentialService.create_credential(
                db, data=type("Obj", (), {
                    "provider_id": provider.id, "name": "Judge", "api_key": key_judge,
                    "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                    "tpm_limit": None, "max_concurrency": None,
                })(),
            )

            m = DiscoveredModel(
                provider_id=provider.id, credential_id=c1.id, provider_model_id=f"m-{run_id}",
                display_name="M", canonical_slug=f"prov-{strategy}-{run_id}/m-{run_id}",
                capabilities={"chat": True}, supported_endpoints=["/chat/completions"],
                enabled=True, available=True,
            )
            db.add(m)
            await db.commit()
            await db.refresh(m)

            fusion_slug = f"fusion-strat-{strategy}-{run_id}"
            fusion_prof = FusionProfile(
                name=f"Fusion {strategy}",
                slug=fusion_slug,
                strategy=strategy,
                judge_provider_id=provider.id,
                judge_credential_id=c_judge.id,
                judge_model_id=m.id,
                min_successful_candidates=2,
                max_parallelism=5,
                timeout_seconds=15.0,
                enabled=True,
            )
            db.add(fusion_prof)
            await db.flush()

            db.add(FusionParticipant(profile_id=fusion_prof.id, provider_id=provider.id, credential_id=c1.id, model_id=m.id, label="Model-A", is_active=True))
            db.add(FusionParticipant(profile_id=fusion_prof.id, provider_id=provider.id, credential_id=c2.id, model_id=m.id, label="Model-B", is_active=True))

            k = await ApiKeyService.create_key(
                db, data=type("Obj", (), {
                    "name": f"Key {strategy}", "permissions": ["direct", "routes", "fusion"],
                    "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"],
                    "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None,
                    "expiration_date": None, "ip_restrictions": [],
                })(),
            )
            raw_router_key = k.raw_api_key

        judge_received_payloads = []

        def mock_handler(request: httpx.Request) -> httpx.Response:
            auth = request.headers.get("Authorization", "")
            if key_cand1 in auth:
                return httpx.Response(200, json={
                    "id": "cmpl-c1", "object": "chat.completion", "created": 1, "model": f"m-{run_id}",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": f"Candidate 1 answer for {strategy}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
                })
            elif key_cand2 in auth:
                return httpx.Response(200, json={
                    "id": "cmpl-c2", "object": "chat.completion", "created": 1, "model": f"m-{run_id}",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": f"Candidate 2 answer for {strategy}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 15, "completion_tokens": 20, "total_tokens": 35},
                })
            elif key_judge in auth:
                body = json.loads(request.content.decode())
                judge_received_payloads.append(body)
                return httpx.Response(200, json={
                    "id": "cmpl-judge", "object": "chat.completion", "created": 1, "model": f"m-{run_id}",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": f"Final decision using {strategy}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 40, "completion_tokens": 25, "total_tokens": 65},
                })
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {raw_router_key}"},
                    json={
                        "model": f"fusion/{fusion_slug}",
                        "messages": [{"role": "user", "content": f"Explain {strategy}"}],
                    },
                )
                assert res.status_code == 200
                data = res.json()
                assert f"Final decision using {strategy}" in data["choices"][0]["message"]["content"]
                assert data["model"] == f"fusion/{fusion_slug}"

                # Verify strategy prompt sent to judge
                assert len(judge_received_payloads) == 1
                judge_messages = judge_received_payloads[0]["messages"]
                sys_msg = judge_messages[0]["content"].lower()
                user_msg = judge_messages[1]["content"]

                if strategy == "synthesize":
                    assert "synthesizer" in sys_msg or "synthesize" in sys_msg
                elif strategy == "best_of_n":
                    assert "evaluator" in sys_msg or "select the single best" in sys_msg
                elif strategy == "consensus":
                    assert "consensus" in sys_msg
                elif strategy == "critique_and_rewrite":
                    assert "critique" in sys_msg or "rewrite" in sys_msg

                assert "Model-A" in user_msg
                assert "Model-B" in user_msg


@pytest.mark.asyncio
async def test_fusion_streaming():
    """Tests execute_fusion_stream: parallel candidate execution and streamed Judge response."""
    run_id = uuid.uuid4().hex[:8]
    key_c1 = f"sk-stream-c1-{run_id}"
    key_judge = f"sk-stream-judge-{run_id}"

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-stream-{run_id}")

        c1 = await CredentialService.create_credential(
            db, data=type("Obj", (), {
                "provider_id": provider.id, "name": "C1", "api_key": key_c1,
                "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                "tpm_limit": None, "max_concurrency": None,
            })(),
        )
        c_judge = await CredentialService.create_credential(
            db, data=type("Obj", (), {
                "provider_id": provider.id, "name": "Judge", "api_key": key_judge,
                "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                "tpm_limit": None, "max_concurrency": None,
            })(),
        )

        m = DiscoveredModel(
            provider_id=provider.id, credential_id=c1.id, provider_model_id=f"m-{run_id}",
            display_name="M", canonical_slug=f"prov-stream-{run_id}/m-{run_id}",
            capabilities={"chat": True, "streaming": True}, supported_endpoints=["/chat/completions"],
            enabled=True, available=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        fusion_slug = f"fusion-stream-{run_id}"
        prof = FusionProfile(
            name="Stream Fusion", slug=fusion_slug, strategy="synthesize",
            judge_provider_id=provider.id, judge_credential_id=c_judge.id, judge_model_id=m.id,
            min_successful_candidates=1, max_parallelism=2, timeout_seconds=10.0, enabled=True,
        )
        db.add(prof)
        await db.flush()
        db.add(FusionParticipant(profile_id=prof.id, provider_id=provider.id, credential_id=c1.id, model_id=m.id, label="Stream-Cand", is_active=True))

        k = await ApiKeyService.create_key(
            db, data=type("Obj", (), {
                "name": "Key Stream", "permissions": ["direct", "routes", "fusion"],
                "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"],
                "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None,
                "expiration_date": None, "ip_restrictions": [],
            })(),
        )
        raw_key = k.raw_api_key

    def mock_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if key_c1 in auth:
            # Non-streaming candidate response
            return httpx.Response(200, json={
                "id": "cmpl-c1", "object": "chat.completion", "created": 1, "model": f"m-{run_id}",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Stream candidate answer"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            })
        elif key_judge in auth:
            # Streaming judge response (SSE)
            sse_lines = [
                'data: {"id":"cmpl-j1","object":"chat.completion.chunk","created":1,"choices":[{"index":0,"delta":{"content":"Hello "},"finish_reason":null}]}\n\n',
                'data: {"id":"cmpl-j2","object":"chat.completion.chunk","created":1,"choices":[{"index":0,"delta":{"content":"World!"},"finish_reason":"stop"}]}\n\n',
                'data: [DONE]\n\n',
            ]
            return httpx.Response(200, content="".join(sse_lines).encode(), headers={"content-type": "text/event-stream"})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "model": f"fusion/{fusion_slug}",
                    "messages": [{"role": "user", "content": "Test stream"}],
                    "stream": True,
                },
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            body = resp.text
            assert "Hello " in body
            assert "World!" in body
            assert "[DONE]" in body
            assert "usage" in body


@pytest.mark.asyncio
async def test_fusion_partial_failure_with_quorum():
    """Tests fault tolerance: 3 candidates, 1 fails with 500, but quorum (2) is met, so Fusion succeeds."""
    run_id = uuid.uuid4().hex[:8]
    k_failing = f"sk-failing-{run_id}"
    k_ok1 = f"sk-ok1-{run_id}"
    k_ok2 = f"sk-ok2-{run_id}"
    k_judge = f"sk-judge-quorum-{run_id}"

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-quorum-{run_id}")

        cfail = await CredentialService.create_credential(
            db, data=type("Obj", (), {
                "provider_id": provider.id, "name": "Fail", "api_key": k_failing,
                "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                "tpm_limit": None, "max_concurrency": None,
            })(),
        )
        cok1 = await CredentialService.create_credential(
            db, data=type("Obj", (), {
                "provider_id": provider.id, "name": "OK1", "api_key": k_ok1,
                "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                "tpm_limit": None, "max_concurrency": None,
            })(),
        )
        cok2 = await CredentialService.create_credential(
            db, data=type("Obj", (), {
                "provider_id": provider.id, "name": "OK2", "api_key": k_ok2,
                "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                "tpm_limit": None, "max_concurrency": None,
            })(),
        )
        cjudge = await CredentialService.create_credential(
            db, data=type("Obj", (), {
                "provider_id": provider.id, "name": "Judge", "api_key": k_judge,
                "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
                "tpm_limit": None, "max_concurrency": None,
            })(),
        )

        m = DiscoveredModel(
            provider_id=provider.id, credential_id=cok1.id, provider_model_id=f"m-{run_id}",
            display_name="M", canonical_slug=f"prov-quorum-{run_id}/m-{run_id}",
            capabilities={"chat": True}, supported_endpoints=["/chat/completions"],
            enabled=True, available=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        fusion_slug = f"fusion-quorum-{run_id}"
        prof = FusionProfile(
            name="Quorum Fusion", slug=fusion_slug, strategy="synthesize",
            judge_provider_id=provider.id, judge_credential_id=cjudge.id, judge_model_id=m.id,
            min_successful_candidates=2, max_parallelism=3, timeout_seconds=10.0, enabled=True,
        )
        db.add(prof)
        await db.flush()

        db.add(FusionParticipant(profile_id=prof.id, provider_id=provider.id, credential_id=cfail.id, model_id=m.id, label="Failing-Model", is_active=True))
        db.add(FusionParticipant(profile_id=prof.id, provider_id=provider.id, credential_id=cok1.id, model_id=m.id, label="Good-Model-1", is_active=True))
        db.add(FusionParticipant(profile_id=prof.id, provider_id=provider.id, credential_id=cok2.id, model_id=m.id, label="Good-Model-2", is_active=True))

        k = await ApiKeyService.create_key(
            db, data=type("Obj", (), {
                "name": "Key Quorum", "permissions": ["direct", "routes", "fusion"],
                "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"],
                "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None,
                "expiration_date": None, "ip_restrictions": [],
            })(),
        )
        raw_key = k.raw_api_key

    judge_user_prompt = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if k_failing in auth:
            return httpx.Response(500, json={"error": {"message": "Internal Server Error from upstream"}})
        elif k_ok1 in auth:
            return httpx.Response(200, json={
                "id": "cmpl-ok1", "object": "chat.completion", "created": 1, "model": f"m-{run_id}",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Valid answer from OK1"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            })
        elif k_ok2 in auth:
            return httpx.Response(200, json={
                "id": "cmpl-ok2", "object": "chat.completion", "created": 1, "model": f"m-{run_id}",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Valid answer from OK2"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            })
        elif k_judge in auth:
            body = json.loads(request.content.decode())
            judge_user_prompt.append(body["messages"][-1]["content"])
            return httpx.Response(200, json={
                "id": "cmpl-judge", "object": "chat.completion", "created": 1, "model": f"m-{run_id}",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Synthesized from OK1 and OK2"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50},
            })
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={"model": f"fusion/{fusion_slug}", "messages": [{"role": "user", "content": "Explain binary search"}]},
            )
            assert resp.status_code == 200
            assert "Synthesized from OK1 and OK2" in resp.json()["choices"][0]["message"]["content"]
            # Verify judge only received the 2 successful candidates
            prompt_text = judge_user_prompt[0]
            assert "Good-Model-1" in prompt_text
            assert "Good-Model-2" in prompt_text
            assert "Failing-Model" not in prompt_text


@pytest.mark.asyncio
async def test_fusion_quorum_failure_raises_502():
    """Tests quorum failure: 3 candidates, min_successful=2. 2 fail, only 1 succeeds -> raises 502/UPSTREAM_5XX."""
    run_id = uuid.uuid4().hex[:8]
    k_fail1 = f"sk-fail1-{run_id}"
    k_fail2 = f"sk-fail2-{run_id}"
    k_ok = f"sk-ok-lonely-{run_id}"
    k_judge = f"sk-judge-unreached-{run_id}"

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-qfail-{run_id}")

        cf1 = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "F1", "api_key": k_fail1, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())
        cf2 = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "F2", "api_key": k_fail2, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())
        cok = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "OK", "api_key": k_ok, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())
        cjudge = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "Judge", "api_key": k_judge, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())

        m = DiscoveredModel(provider_id=provider.id, credential_id=cok.id, provider_model_id=f"m-{run_id}", display_name="M", canonical_slug=f"prov-qfail-{run_id}/m-{run_id}", capabilities={"chat": True}, supported_endpoints=["/chat/completions"], enabled=True, available=True)
        db.add(m)
        await db.commit()
        await db.refresh(m)

        fusion_slug = f"fusion-qfail-{run_id}"
        prof = FusionProfile(name="Quorum Fail", slug=fusion_slug, strategy="synthesize", judge_provider_id=provider.id, judge_credential_id=cjudge.id, judge_model_id=m.id, min_successful_candidates=2, max_parallelism=3, timeout_seconds=10.0, enabled=True)
        db.add(prof)
        await db.flush()

        db.add(FusionParticipant(profile_id=prof.id, provider_id=provider.id, credential_id=cf1.id, model_id=m.id, label="F1", is_active=True))
        db.add(FusionParticipant(profile_id=prof.id, provider_id=provider.id, credential_id=cf2.id, model_id=m.id, label="F2", is_active=True))
        db.add(FusionParticipant(profile_id=prof.id, provider_id=provider.id, credential_id=cok.id, model_id=m.id, label="OK", is_active=True))

        k = await ApiKeyService.create_key(db, data=type("Obj", (), {"name": "Key QFail", "permissions": ["direct", "routes", "fusion"], "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"], "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None, "expiration_date": None, "ip_restrictions": []})())
        raw_key = k.raw_api_key

    def mock_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if k_fail1 in auth or k_fail2 in auth:
            return httpx.Response(503, json={"error": {"message": "Service Unavailable"}})
        elif k_ok in auth:
            return httpx.Response(200, json={"id": "cmpl-ok", "object": "chat.completion", "created": 1, "model": f"m-{run_id}", "choices": [{"index": 0, "message": {"role": "assistant", "content": "I am alone"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}})
        return httpx.Response(500)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={"model": f"fusion/{fusion_slug}", "messages": [{"role": "user", "content": "Fail me"}]},
            )
            assert resp.status_code == 502
            err = resp.json()["error"]
            assert "only 1 of 3 candidates succeeded" in err["message"]


@pytest.mark.asyncio
async def test_fusion_judge_auto_select_key_and_circuit_breaker():
    """Tests: 1) auto-selection of active judge key when judge_credential_id is None; 2) Circuit breaker recording on judge error."""
    run_id = uuid.uuid4().hex[:8]
    k_cand = f"sk-cand-auto-{run_id}"
    k_judge_active = f"sk-judge-active-{run_id}"

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-auto-judge-{run_id}")

        c_cand = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "CandKey", "api_key": k_cand, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())
        c_judge_active = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "JudgeActive", "api_key": k_judge_active, "proxy_id": None, "priority": 0, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())

        m = DiscoveredModel(provider_id=provider.id, credential_id=c_cand.id, provider_model_id=f"m-{run_id}", display_name="M", canonical_slug=f"prov-auto-judge-{run_id}/m-{run_id}", capabilities={"chat": True}, supported_endpoints=["/chat/completions"], enabled=True, available=True)
        db.add(m)
        await db.commit()
        await db.refresh(m)

        fusion_slug = f"fusion-auto-judge-{run_id}"
        prof = FusionProfile(
            name="Auto Judge", slug=fusion_slug, strategy="synthesize",
            judge_provider_id=provider.id,
            judge_credential_id=None,  # Note: None! Should auto-pick c_judge_active
            judge_model_id=m.id, min_successful_candidates=1, max_parallelism=2, timeout_seconds=10.0, enabled=True,
        )
        db.add(prof)
        await db.flush()

        db.add(FusionParticipant(profile_id=prof.id, provider_id=provider.id, credential_id=c_cand.id, model_id=m.id, label="C", is_active=True))

        k = await ApiKeyService.create_key(db, data=type("Obj", (), {"name": "Key Auto", "permissions": ["direct", "routes", "fusion"], "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"], "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None, "expiration_date": None, "ip_restrictions": []})())
        raw_key = k.raw_api_key
        judge_cred_id = c_judge_active.id

    judge_called = False

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal judge_called
        auth = request.headers.get("Authorization", "")
        if k_cand in auth:
            return httpx.Response(200, json={"id": "c", "object": "chat.completion", "created": 1, "model": f"m-{run_id}", "choices": [{"index": 0, "message": {"role": "assistant", "content": "Candidate ok"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}})
        elif k_judge_active in auth:
            judge_called = True
            # Simulate judge failure 429 to test circuit breaker
            return httpx.Response(429, json={"error": {"message": "Rate limit reached on judge"}})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={"model": f"fusion/{fusion_slug}", "messages": [{"role": "user", "content": "Test judge auto"}]},
            )
            assert resp.status_code == 429
            assert judge_called is True

            # Verify circuit breaker tracked failure on the judge key
            cb_state = circuit_breaker.get_status(judge_cred_id)
            assert cb_state["consecutive_failures"] > 0


@pytest.mark.asyncio
async def test_fusion_cross_protocol_anthropic_and_permissions():
    """Tests: 1) Anthropic Messages API /v1/messages with fusion; 2) Router key permissions enforcement."""
    run_id = uuid.uuid4().hex[:8]
    k_cand = f"sk-cand-cross-{run_id}"
    k_judge = f"sk-judge-cross-{run_id}"

    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-cross-{run_id}")

        c_cand = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "Cand", "api_key": k_cand, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())
        c_judge = await CredentialService.create_credential(db, data=type("Obj", (), {"provider_id": provider.id, "name": "Judge", "api_key": k_judge, "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None, "tpm_limit": None, "max_concurrency": None})())

        m = DiscoveredModel(provider_id=provider.id, credential_id=c_cand.id, provider_model_id=f"m-{run_id}", display_name="M", canonical_slug=f"prov-cross-{run_id}/m-{run_id}", capabilities={"chat": True}, supported_endpoints=["/chat/completions"], enabled=True, available=True)
        db.add(m)
        await db.commit()
        await db.refresh(m)

        fusion_slug = f"fusion-cross-{run_id}"
        prof = FusionProfile(name="Cross Fusion", slug=fusion_slug, strategy="synthesize", judge_provider_id=provider.id, judge_credential_id=c_judge.id, judge_model_id=m.id, min_successful_candidates=1, max_parallelism=2, timeout_seconds=10.0, enabled=True)
        db.add(prof)
        await db.flush()
        db.add(FusionParticipant(profile_id=prof.id, provider_id=provider.id, credential_id=c_cand.id, model_id=m.id, label="C", is_active=True))

        # 1. Permitted key
        k_ok = await ApiKeyService.create_key(db, data=type("Obj", (), {"name": "Key OK", "permissions": ["direct", "routes", "fusion"], "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"], "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None, "expiration_date": None, "ip_restrictions": []})())
        # 2. Key without fusion permission
        k_nofusion = await ApiKeyService.create_key(db, data=type("Obj", (), {"name": "Key NoFusion", "permissions": ["direct", "routes"], "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"], "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None, "expiration_date": None, "ip_restrictions": []})())
        # 3. Key restricted to another fusion slug
        k_restricted = await ApiKeyService.create_key(db, data=type("Obj", (), {"name": "Key Restricted", "permissions": ["direct", "routes", "fusion"], "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["fusion/different-slug"], "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None, "expiration_date": None, "ip_restrictions": []})())

        raw_ok = k_ok.raw_api_key
        raw_nofusion = k_nofusion.raw_api_key
        raw_restricted = k_restricted.raw_api_key

    def mock_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if k_cand in auth:
            return httpx.Response(200, json={"id": "c", "object": "chat.completion", "created": 1, "model": f"m-{run_id}", "choices": [{"index": 0, "message": {"role": "assistant", "content": "Anthropic candidate ok"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}})
        elif k_judge in auth:
            return httpx.Response(200, json={"id": "j", "object": "chat.completion", "created": 1, "model": f"m-{run_id}", "choices": [{"index": 0, "message": {"role": "assistant", "content": "Final synthesized answer for Claude format"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 20, "completion_tokens": 20, "total_tokens": 40}})
        return httpx.Response(404)

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test Permission Check: Key without fusion permission receives 403
            res_noperm = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_nofusion}"},
                json={"model": f"fusion/{fusion_slug}", "messages": [{"role": "user", "content": "Hi"}]},
            )
            assert res_noperm.status_code == 403

            # Test Permission Check: Key with allowed_fusions restriction receives 403
            res_restr = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_restricted}"},
                json={"model": f"fusion/{fusion_slug}", "messages": [{"role": "user", "content": "Hi"}]},
            )
            assert res_restr.status_code == 403

            # Test Anthropic Protocol: POST /v1/messages
            res_anthropic = await client.post(
                "/v1/messages",
                headers={"x-api-key": raw_ok, "anthropic-version": "2023-06-01"},
                json={
                    "model": f"fusion/{fusion_slug}",
                    "messages": [{"role": "user", "content": "Explain via Anthropic protocol"}],
                    "max_tokens": 512,
                },
            )
            assert res_anthropic.status_code == 200
            ant_data = res_anthropic.json()
            assert ant_data["type"] == "message"
            assert ant_data["role"] == "assistant"
            assert "Final synthesized answer for Claude format" in ant_data["content"][0]["text"]
            assert ant_data["model"] == f"fusion/{fusion_slug}"
