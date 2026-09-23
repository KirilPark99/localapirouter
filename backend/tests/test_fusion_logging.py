import pytest
import uuid
import json
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch
from sqlalchemy import select, delete

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    Provider,
    DiscoveredModel,
    ProviderCredential,
    FusionProfile,
    FusionParticipant,
    RequestLog,
    RequestAttempt,
    RouterApiKey,
)
from app.schemas.chat import (
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.services.credential_service import CredentialService
from app.services.api_key_service import ApiKeyService
from app.services.auth_service import AuthService
from app.core.errors import RouterException, ErrorCategory
from app.core.config import settings


@pytest.mark.asyncio
async def test_fusion_request_logging_success_and_stream(monkeypatch):
    """
    Verifies that both non-streaming and streaming fusion requests
    are properly logged in the database with mode='FUSION', status='FUSION_SUCCESS',
    rich participant traces, judge traces, and attempts.
    """
    monkeypatch.setattr(settings, "LOG_REQUEST_CONTENT", True)
    run_id = uuid.uuid4().hex[:8]
    prov_id = None
    cred_id = None
    model_id = None
    fusion_id = None
    key_id = None
    created_request_ids = []

    try:
        async with AsyncSessionLocal() as db:
            p = Provider(
                name=f"Log Test Prov {run_id}",
                slug=f"log-prov-{run_id}",
                adapter_type="openai",
                base_url="https://api.openai.com/v1",
                models_endpoint="/models",
                chat_endpoint="/chat/completions",
                enabled=True,
                auth_type="bearer",
                auth_header="Authorization",
            )
            db.add(p)
            await db.commit()
            await db.refresh(p)
            prov_id = p.id

            cred = await CredentialService.create_credential(
                db,
                type("Obj", (), {
                    "provider_id": p.id,
                    "name": f"Log Cred {run_id}",
                    "api_key": f"sk-test-{run_id}",
                    "proxy_id": None,
                    "priority": 1,
                    "weight": 10,
                    "rpm_limit": None,
                    "tpm_limit": None,
                    "max_concurrency": None,
                    "group_name": None,
                })(),
            )
            cred_id = cred.id

            m = DiscoveredModel(
                provider_id=p.id,
                provider_model_id=f"log-model-{run_id}",
                canonical_slug=f"log-prov-{run_id}/log-model-{run_id}",
                display_name=f"Log Model {run_id}",
                context_length=128000,
                max_output_tokens=4096,
                enabled=True,
                available=True,
                is_visible=True,
            )
            db.add(m)
            await db.commit()
            await db.refresh(m)
            model_id = m.id

            fp = FusionProfile(
                name=f"Logging Fusion {run_id}",
                slug=f"log-fusion-{run_id}",
                strategy="synthesize",
                judge_type="model",
                judge_provider_id=p.id,
                judge_credential_id=cred.id,
                judge_model_id=m.id,
                min_successful_candidates=1,
                max_parallelism=2,
                timeout_seconds=10.0,
                enabled=True,
            )
            db.add(fp)
            await db.commit()
            await db.refresh(fp)
            fusion_id = fp.id

            part = FusionParticipant(
                profile_id=fp.id,
                participant_type="model",
                provider_id=p.id,
                credential_id=cred.id,
                model_id=m.id,
                label="Candidate 1",
                is_active=True,
            )
            db.add(part)

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
            key_id = k.id
            await db.commit()

        # Mock adapter responses
        async def mock_chat(*args, **kwargs):
            return ChatCompletionResponse(
                id=f"chatcmpl_{uuid.uuid4().hex[:8]}",
                object="chat.completion",
                created=1700000000,
                model=kwargs.get("model_id", "model"),
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content="Synthesized fusion answer"),
                        finish_reason="stop",
                    )
                ],
                usage=UsageInfo(prompt_tokens=15, completion_tokens=10, total_tokens=25),
            )

        async def mock_stream(*args, **kwargs):
            yield f'data: {json.dumps({"id": "chk1", "object": "chat.completion.chunk", "created": 1700000000, "model": "m", "choices": [{"index": 0, "delta": {"content": "Synthesized stream response"}, "finish_reason": None}]})}\n\n'
            yield f'data: {json.dumps({"id": "chk2", "object": "chat.completion.chunk", "created": 1700000000, "model": "m", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20}})}\n\n'
            yield "data: [DONE]\n\n"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_chat), \
                 patch("app.adapters.openai.GenericOpenAIAdapter.stream_chat", side_effect=mock_stream):

                # 1. NON-STREAMING FUSION REQUEST
                res_non_stream = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {raw_key}"},
                    json={
                        "model": f"fusion/log-fusion-{run_id}",
                        "messages": [{"role": "user", "content": "Explain gravity"}],
                        "stream": False,
                    },
                )
                assert res_non_stream.status_code == 200, f"Non-stream failed: {res_non_stream.text}"
                resp_data = res_non_stream.json()
                assert resp_data["model"] == f"fusion/log-fusion-{run_id}"
                choice = resp_data["choices"][0]
                assert "reasoning_content" in choice["message"]
                assert "Fusion Ensemble Deliberation" in choice["message"]["reasoning_content"]

                # Verify Log entry for non-streaming
                async with AsyncSessionLocal() as db:
                    q = (
                        select(RequestLog)
                        .where(RequestLog.requested_model == f"fusion/log-fusion-{run_id}")
                        .order_by(RequestLog.id.desc())
                    )
                    r = await db.execute(q)
                    log_entry = r.scalars().first()
                    assert log_entry is not None, "Log entry was not recorded for non-streaming fusion!"
                    created_request_ids.append(log_entry.request_id)

                    assert log_entry.mode == "FUSION"
                    assert log_entry.status == "FUSION_SUCCESS"
                    assert log_entry.status_code == 200
                    assert log_entry.router_key_id == key_id
                    assert log_entry.metadata_json is not None
                    assert log_entry.metadata_json.get("strategy") == "synthesize"
                    assert "participants" in log_entry.metadata_json
                    assert len(log_entry.metadata_json["participants"]) == 1
                    assert log_entry.metadata_json["participants"][0]["status"] == "SUCCESS"
                    assert log_entry.metadata_json["participants"][0].get("content") is not None
                    assert log_entry.metadata_json.get("deliberation") is not None
                    assert "judge" in log_entry.metadata_json
                    assert log_entry.metadata_json["judge"]["status"] == "SUCCESS"

                    # Verify attempts
                    att_q = select(RequestAttempt).where(RequestAttempt.request_log_id == log_entry.id)
                    att_res = await db.execute(att_q)
                    attempts = att_res.scalars().all()
                    assert len(attempts) >= 2, f"Expected at least 2 attempts (candidate + judge), got {len(attempts)}"

                # 2. STREAMING FUSION REQUEST
                res_stream = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {raw_key}"},
                    json={
                        "model": f"fusion/log-fusion-{run_id}",
                        "messages": [{"role": "user", "content": "Explain relativity"}],
                        "stream": True,
                    },
                )
                assert res_stream.status_code == 200, f"Stream failed: {res_stream.text}"
                stream_body = res_stream.text
                assert "reasoning_content" in stream_body
                assert "Synthesized stream response" in stream_body
                assert "data: [DONE]" in stream_body

                # Verify Log entry for streaming
                async with AsyncSessionLocal() as db:
                    q = (
                        select(RequestLog)
                        .where(RequestLog.requested_model == f"fusion/log-fusion-{run_id}")
                        .order_by(RequestLog.id.desc())
                    )
                    r = await db.execute(q)
                    logs = r.scalars().all()
                    assert len(logs) >= 2, "Expected at least 2 log entries (non-stream and stream)!"
                    stream_log = logs[0]
                    created_request_ids.append(stream_log.request_id)

                    assert stream_log.mode == "FUSION"
                    assert stream_log.status == "FUSION_SUCCESS"
                    assert stream_log.status_code == 200
                    assert stream_log.metadata_json.get("stream") is True
                    assert stream_log.metadata_json.get("strategy") == "synthesize"
                    assert "participants" in stream_log.metadata_json
                    assert stream_log.metadata_json["participants"][0].get("content") is not None
                    assert stream_log.metadata_json.get("deliberation") is not None
                    assert "judge" in stream_log.metadata_json
                    assert stream_log.metadata_json["judge"]["status"] == "SUCCESS"

                # 3. BARE SLUG FUSION REQUEST & GET_MODEL
                res_model_bare = await client.get(
                    f"/v1/models/log-fusion-{run_id}",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
                assert res_model_bare.status_code == 200, f"Get model bare slug failed: {res_model_bare.text}"
                assert res_model_bare.json()["id"] == f"fusion/log-fusion-{run_id}"

                res_bare = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {raw_key}"},
                    json={
                        "model": f"log-fusion-{run_id}",  # Bare slug without 'fusion/'
                        "messages": [{"role": "user", "content": "Explain bare slug fusion"}],
                        "stream": False,
                    },
                )
                assert res_bare.status_code == 200, f"Bare slug failed: {res_bare.text}"
                data_bare = res_bare.json()
                assert data_bare["choices"][0]["message"]["content"] == "Synthesized fusion answer"
                assert data_bare["model"] == f"fusion/log-fusion-{run_id}"

                # 4. VERIFY ADMIN LOGS API
                admin_token = AuthService.create_access_token("admin")
                admin_res = await client.get(
                    f"/api/admin/logs?mode=FUSION&model=fusion/log-fusion-{run_id}",
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                assert admin_res.status_code == 200
                admin_logs = admin_res.json()
                assert len(admin_logs) >= 2, f"Expected admin logs to list both requests, got {len(admin_logs)}"
                for l in admin_logs:
                    assert l["mode"] == "FUSION"
                    assert l["status"] == "FUSION_SUCCESS"

    finally:
        # CLEANUP
        async with AsyncSessionLocal() as db:
            for rid in created_request_ids:
                sub_q = select(RequestLog.id).where(RequestLog.request_id == rid)
                r = await db.execute(sub_q)
                lid = r.scalar_one_or_none()
                if lid:
                    await db.execute(delete(RequestAttempt).where(RequestAttempt.request_log_id == lid))
                    await db.execute(delete(RequestLog).where(RequestLog.id == lid))

            if fusion_id:
                await db.execute(delete(FusionParticipant).where(FusionParticipant.profile_id == fusion_id))
                await db.execute(delete(FusionProfile).where(FusionProfile.id == fusion_id))
            if key_id:
                await db.execute(delete(RouterApiKey).where(RouterApiKey.id == key_id))
            if model_id:
                await db.execute(delete(DiscoveredModel).where(DiscoveredModel.id == model_id))
            if cred_id:
                await db.execute(delete(ProviderCredential).where(ProviderCredential.id == cred_id))
            if prov_id:
                await db.execute(delete(Provider).where(Provider.id == prov_id))
            await db.commit()


@pytest.mark.asyncio
async def test_fusion_candidate_and_judge_failure_logging():
    """
    Verifies that when candidate fan-out fails or judge fails,
    the failed fusion request is recorded with status='FAILED',
    accurate error details, attempts trace, and HTTP status code.
    """
    run_id = uuid.uuid4().hex[:8]
    prov_id = None
    cred_id = None
    model_id = None
    fusion_id = None
    key_id = None
    created_request_ids = []

    try:
        async with AsyncSessionLocal() as db:
            p = Provider(
                name=f"Fail Test Prov {run_id}",
                slug=f"fail-prov-{run_id}",
                adapter_type="openai",
                base_url="https://api.openai.com/v1",
                models_endpoint="/models",
                chat_endpoint="/chat/completions",
                enabled=True,
                auth_type="bearer",
                auth_header="Authorization",
            )
            db.add(p)
            await db.commit()
            await db.refresh(p)
            prov_id = p.id

            cred = await CredentialService.create_credential(
                db,
                type("Obj", (), {
                    "provider_id": p.id,
                    "name": f"Fail Cred {run_id}",
                    "api_key": f"sk-fail-{run_id}",
                    "proxy_id": None,
                    "priority": 1,
                    "weight": 10,
                    "rpm_limit": None,
                    "tpm_limit": None,
                    "max_concurrency": None,
                    "group_name": None,
                })(),
            )
            cred_id = cred.id

            m = DiscoveredModel(
                provider_id=p.id,
                provider_model_id=f"fail-model-{run_id}",
                canonical_slug=f"fail-prov-{run_id}/fail-model-{run_id}",
                display_name=f"Fail Model {run_id}",
                context_length=128000,
                max_output_tokens=4096,
                enabled=True,
                available=True,
                is_visible=True,
            )
            db.add(m)
            await db.commit()
            await db.refresh(m)
            model_id = m.id

            fp = FusionProfile(
                name=f"Fail Fusion {run_id}",
                slug=f"fail-fusion-{run_id}",
                strategy="synthesize",
                judge_type="model",
                judge_provider_id=p.id,
                judge_credential_id=cred.id,
                judge_model_id=m.id,
                min_successful_candidates=1,
                max_parallelism=2,
                timeout_seconds=5.0,
                enabled=True,
            )
            db.add(fp)
            await db.commit()
            await db.refresh(fp)
            fusion_id = fp.id

            part = FusionParticipant(
                profile_id=fp.id,
                participant_type="model",
                provider_id=p.id,
                credential_id=cred.id,
                model_id=m.id,
                label="Candidate Failing",
                is_active=True,
            )
            db.add(part)

            k = await ApiKeyService.create_key(
                db,
                data=type("Obj", (), {
                    "name": f"KeyFail {run_id}",
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
            key_id = k.id
            await db.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            # 1. CANDIDATE FAILS
            async def mock_candidate_fail(*args, **kwargs):
                raise RouterException("Upstream model crashed", ErrorCategory.UPSTREAM_5XX, status_code=502)

            with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_candidate_fail):
                res_fail = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {raw_key}"},
                    json={
                        "model": f"fusion/fail-fusion-{run_id}",
                        "messages": [{"role": "user", "content": "Will candidate fail?"}],
                        "stream": False,
                    },
                )
                assert res_fail.status_code == 502

                # Verify FAILED request was logged
                async with AsyncSessionLocal() as db:
                    q = (
                        select(RequestLog)
                        .where(RequestLog.requested_model == f"fusion/fail-fusion-{run_id}")
                        .order_by(RequestLog.id.desc())
                    )
                    r = await db.execute(q)
                    log_entry = r.scalars().first()
                    assert log_entry is not None, "Failed candidate request was NOT logged!"
                    created_request_ids.append(log_entry.request_id)

                    assert log_entry.mode == "FUSION"
                    assert log_entry.status == "FAILED"
                    assert log_entry.status_code == 502
                    assert "participants" in log_entry.metadata_json
                    assert log_entry.metadata_json["participants"][0]["status"] == "FAILED"

            # 2. JUDGE FAILS (Candidate succeeds, but Judge fails)
            call_count = 0
            async def mock_judge_fail(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # Candidate succeeds
                    return ChatCompletionResponse(
                        id="cand1",
                        object="chat.completion",
                        created=1700000000,
                        model="model",
                        choices=[ChatCompletionChoice(index=0, message=ChatMessage(role="assistant", content="Candidate answer"), finish_reason="stop")],
                        usage=UsageInfo(prompt_tokens=5, completion_tokens=5, total_tokens=10),
                    )
                else:
                    # Judge fails
                    raise RouterException("Judge rate limit reached", ErrorCategory.RATE_LIMIT, status_code=429)

            with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_judge_fail):
                res_judge_fail = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {raw_key}"},
                    json={
                        "model": f"fusion/fail-fusion-{run_id}",
                        "messages": [{"role": "user", "content": "Will judge fail?"}],
                        "stream": False,
                    },
                )
                assert res_judge_fail.status_code == 429

                # Verify Log entry for judge failure
                async with AsyncSessionLocal() as db:
                    q = (
                        select(RequestLog)
                        .where(RequestLog.requested_model == f"fusion/fail-fusion-{run_id}")
                        .order_by(RequestLog.id.desc())
                    )
                    r = await db.execute(q)
                    judge_log = r.scalars().first()
                    assert judge_log is not None
                    created_request_ids.append(judge_log.request_id)

                    assert judge_log.mode == "FUSION"
                    assert judge_log.status == "FAILED"
                    assert judge_log.status_code == 429
                    assert "judge" in judge_log.metadata_json
                    assert judge_log.metadata_json["judge"]["status"] == "FAILED"
                    assert "rate limit" in judge_log.metadata_json["judge"]["error"].lower()

    finally:
        # CLEANUP
        async with AsyncSessionLocal() as db:
            for rid in created_request_ids:
                sub_q = select(RequestLog.id).where(RequestLog.request_id == rid)
                r = await db.execute(sub_q)
                lid = r.scalar_one_or_none()
                if lid:
                    await db.execute(delete(RequestAttempt).where(RequestAttempt.request_log_id == lid))
                    await db.execute(delete(RequestLog).where(RequestLog.id == lid))

            if fusion_id:
                await db.execute(delete(FusionParticipant).where(FusionParticipant.profile_id == fusion_id))
                await db.execute(delete(FusionProfile).where(FusionProfile.id == fusion_id))
            if key_id:
                await db.execute(delete(RouterApiKey).where(RouterApiKey.id == key_id))
            if model_id:
                await db.execute(delete(DiscoveredModel).where(DiscoveredModel.id == model_id))
            if cred_id:
                await db.execute(delete(ProviderCredential).where(ProviderCredential.id == cred_id))
            if prov_id:
                await db.execute(delete(Provider).where(Provider.id == prov_id))
            await db.commit()
