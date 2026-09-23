import pytest
import httpx
import uuid
import json
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from openai import AsyncOpenAI
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import Provider, DiscoveredModel
from app.services.api_key_service import ApiKeyService
from app.services.provider_service import ProviderService
from app.services.credential_service import CredentialService
from app.services.auth_service import AuthService

@pytest.mark.asyncio
async def test_openai_sdk_compatibility_and_streaming():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        await AuthService.init_admin_user(db)
        await ProviderService.seed_default_presets(db)
        p_res = await db.execute(pytest.importorskip("sqlalchemy").select(Provider).where(Provider.slug == "openai"))
        provider = p_res.scalar_one()

        key_secret = f"sk-openai-sdk-{run_id}"
        cred = await CredentialService.create_credential(
            db,
            data=type("Obj", (), {
                "provider_id": provider.id,
                "name": f"SDK Key {run_id}",
                "api_key": key_secret,
                "proxy_id": None,
                "priority": 1,
                "weight": 1,
                "rpm_limit": None,
                "tpm_limit": None,
                "max_concurrency": None,
            })(),
        )

        model_id = f"gpt-4o-{run_id}"
        m = DiscoveredModel(
            provider_id=provider.id,
            credential_id=cred.id,
            provider_model_id=model_id,
            display_name="GPT-4o SDK Model",
            canonical_slug=f"openai/{model_id}",
            capabilities={"chat": True, "streaming": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        db.add(m)
        await db.commit()

        k = await ApiKeyService.create_key(
            db,
            data=type("Obj", (), {
                "name": f"SDK Client Key {run_id}",
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

    def mock_upstream(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        if '"stream": true' in body or '"stream":true' in body:
            chunk1 = json.dumps({"id": "cmpl-chunk-1", "object": "chat.completion.chunk", "created": 1, "model": model_id, "choices": [{"index": 0, "delta": {"content": "Hello "}, "finish_reason": None}]})
            chunk2 = json.dumps({"id": "cmpl-chunk-2", "object": "chat.completion.chunk", "created": 1, "model": model_id, "choices": [{"index": 0, "delta": {"content": "world!"}, "finish_reason": "stop"}]})
            sse_content = f"data: {chunk1}\n\ndata: {chunk2}\n\ndata: [DONE]\n\n"
            return httpx.Response(200, content=sse_content.encode(), headers={"content-type": "text/event-stream"})
        else:
            return httpx.Response(200, json={
                "id": "cmpl-sdk-1",
                "object": "chat.completion",
                "created": 1234567,
                "model": model_id,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello from SDK test!"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11},
            })

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_upstream))

    with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
        sdk_http_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        client = AsyncOpenAI(
            base_url="http://test/v1",
            api_key=raw_key,
            http_client=sdk_http_client,
        )

        # 1. Non-streaming call via official OpenAI SDK
        completion = await client.chat.completions.create(
            model=f"openai/{model_id}",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert completion.choices[0].message.content == "Hello from SDK test!"

        # 2. Models list call via official OpenAI SDK
        models_resp = await client.models.list()
        model_ids = [m.id for m in models_resp.data]
        assert f"openai/{model_id}" in model_ids

        # 3. Streaming call via official OpenAI SDK
        stream = await client.chat.completions.create(
            model=f"openai/{model_id}",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True,
            stream_options={"include_usage": True},
        )
        chunks = []
        final_usage = None
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                chunks.append(chunk.choices[0].delta.content)
            if chunk.usage:
                final_usage = chunk.usage

        full_streamed_text = "".join(chunks)
        assert full_streamed_text == "Hello world!"
        assert final_usage is not None
        assert final_usage.total_tokens > 0

        # 3b. Test client early disconnect / cancellation without crash or unclosed connection
        early_stream = await client.chat.completions.create(
            model=f"openai/{model_id}",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True,
        )
        async for _ in early_stream:
            break
        await early_stream.close()

        # 4. Verify request logs recorded the streaming call and admin logs endpoint works
        admin_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        login_resp = await admin_client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "test-admin-password-12345"},
        )
        assert login_resp.status_code == 200
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        logs_resp = await admin_client.get(
            f"/api/admin/logs?limit=10&search={model_id}",
            headers=admin_headers
        )
        assert logs_resp.status_code == 200
        assert "x-total-count" in logs_resp.headers
        assert int(logs_resp.headers["x-total-count"]) >= 2  # Non-streaming + streaming calls
        logs_data = logs_resp.json()
        assert len(logs_data) >= 2
        stream_log = next((l for l in logs_data if (l.get("metadata_json") or {}).get("stream") is True), None)
        assert stream_log is not None
        assert stream_log["status"] == "SUCCESS"
        assert stream_log["router_key_name"] == f"SDK Client Key {run_id}"
        assert stream_log["resolved_provider_name"] in ("OpenAI", "openai")

