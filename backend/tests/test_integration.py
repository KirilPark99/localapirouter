import pytest
import httpx
import json
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.database import AsyncSessionLocal
from app.core.crypto import encrypt_secret
from app.models.entities import (
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
    RoutingCandidate,
    FusionProfile,
    FusionParticipant,
    RouterApiKey,
)
from app.services.api_key_service import ApiKeyService
from app.services.auth_service import AuthService
from app.services.provider_service import ProviderService
from app.services.credential_service import CredentialService

@pytest.mark.asyncio
async def test_api_key_auth_and_openai_models():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with AsyncSessionLocal() as db:
            key_created = await ApiKeyService.create_key(
                db,
                data=type("Obj", (), {
                    "name": "Test Key",
                    "permissions": ["direct", "routes", "fusion"],
                    "allowed_models": ["*"],
                    "allowed_routes": ["*"],
                    "allowed_fusions": ["*"],
                    "rate_limit_rpm": None,
                    "rate_limit_tpm": None,
                    "request_limit": None,
                    "expiration_date": None,
                    "ip_restrictions": [],
                })()
            )
            raw_key = key_created.raw_api_key

        # 1. Reject invalid key
        resp_bad = await client.get("/v1/models", headers={"Authorization": "Bearer sk-router-invalidkey123"})
        assert resp_bad.status_code == 401

        # 2. Accept valid key
        resp_good = await client.get("/v1/models", headers={"Authorization": f"Bearer {raw_key}"})
        assert resp_good.status_code == 200
        data = resp_good.json()
        assert data["object"] == "list"
        assert isinstance(data["data"], list)

@pytest.mark.asyncio
async def test_admin_auth_and_provider_presets():
    async with AsyncSessionLocal() as db:
        await AuthService.init_admin_user(db)
        await ProviderService.seed_default_presets(db, force=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as default admin
        login_resp = await client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "test-admin-password-12345"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # List providers (presets should be seeded)
        prov_resp = await client.get("/api/admin/providers", headers=headers)
        assert prov_resp.status_code == 200
        providers = prov_resp.json()
        assert len(providers) >= 5
        slugs = [p["slug"] for p in providers]
        assert "google" in slugs
        assert any(s in slugs for s in ["openai", "openrouter", "groq"])

@pytest.mark.asyncio
async def test_priority_fallback_execution():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with AsyncSessionLocal() as db:
            k = await ApiKeyService.create_key(
                db,
                data=type("Obj", (), {
                    "name": "Route Test Key",
                    "permissions": ["direct", "routes", "fusion"],
                    "allowed_models": ["*"],
                    "allowed_routes": ["*"],
                    "allowed_fusions": ["*"],
                    "rate_limit_rpm": None,
                    "rate_limit_tpm": None,
                    "request_limit": None,
                    "expiration_date": None,
                    "ip_restrictions": [],
                })()
            )
            raw_key = k.raw_api_key

        # Send request to a nonexistent route -> returns 404
        resp = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={
                "model": "route/nonexistent-route",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert resp.status_code == 404
        err_body = resp.json()
        assert "error" in err_body
        assert "not found" in err_body["error"]["message"].lower()

@pytest.mark.asyncio
async def test_fusion_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with AsyncSessionLocal() as db:
            k = await ApiKeyService.create_key(
                db,
                data=type("Obj", (), {
                    "name": "Fusion Test Key",
                    "permissions": ["direct", "routes", "fusion"],
                    "allowed_models": ["*"],
                    "allowed_routes": ["*"],
                    "allowed_fusions": ["*"],
                    "rate_limit_rpm": None,
                    "rate_limit_tpm": None,
                    "request_limit": None,
                    "expiration_date": None,
                    "ip_restrictions": [],
                })()
            )
            raw_key = k.raw_api_key

        # Nonexistent fusion profile
        resp = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={
                "model": "fusion/unknown-fusion",
                "messages": [{"role": "user", "content": "Test prompt"}],
            },
        )
        assert resp.status_code == 404
        assert "fusion profile 'fusion/unknown-fusion' not found" in resp.json()["error"]["message"].lower()

@pytest.mark.asyncio
async def test_model_visibility_and_filtering():
    from datetime import datetime, timezone
    from sqlalchemy import select

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Admin login
        async with AsyncSessionLocal() as db:
            await AuthService.init_admin_user(db)
            await ProviderService.seed_default_presets(db)

        login_resp = await client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "test-admin-password-12345"},
        )
        assert login_resp.status_code == 200
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Create router client API key
        async with AsyncSessionLocal() as db:
            k = await ApiKeyService.create_key(
                db,
                data=type("Obj", (), {
                    "name": "Visibility Test Key",
                    "permissions": ["direct", "routes"],
                    "allowed_models": ["*"],
                    "allowed_routes": ["*"],
                    "allowed_fusions": ["*"],
                    "rate_limit_rpm": None,
                    "rate_limit_tpm": None,
                    "request_limit": None,
                    "expiration_date": None,
                    "ip_restrictions": [],
                })()
            )
            raw_key = k.raw_api_key

            # Get a provider
            prov_res = await db.execute(select(Provider).limit(1))
            provider = prov_res.scalar_one()

            # Clean any old test models with these slugs
            old_res = await db.execute(
                select(DiscoveredModel).where(
                    DiscoveredModel.canonical_slug.in_(["test/visible-model", "test/hidden-model"])
                )
            )
            for old_m in old_res.scalars().all():
                await db.delete(old_m)
            await db.commit()

            # Insert one visible model and one hidden model
            m_vis = DiscoveredModel(
                provider_id=provider.id,
                provider_model_id="test-model-visible",
                canonical_slug="test/visible-model",
                display_name="Test Visible Model",
                capabilities={"chat": True},
                supported_endpoints=["/chat/completions"],
                enabled=True,
                available=True,
                is_visible=True,
                discovered_at=datetime.now(timezone.utc),
            )
            m_hid = DiscoveredModel(
                provider_id=provider.id,
                provider_model_id="test-model-hidden",
                canonical_slug="test/hidden-model",
                display_name="Test Hidden Model",
                capabilities={"chat": True},
                supported_endpoints=["/chat/completions"],
                enabled=True,
                available=True,
                is_visible=False,
                discovered_at=datetime.now(timezone.utc),
            )
            db.add(m_vis)
            db.add(m_hid)
            await db.commit()
            await db.refresh(m_vis)
            await db.refresh(m_hid)
            vis_id = m_vis.id
            hid_id = m_hid.id

        router_headers = {"Authorization": f"Bearer {raw_key}"}

        # 3. Verify GET /v1/models only returns visible model
        v1_resp = await client.get("/v1/models", headers=router_headers)
        assert v1_resp.status_code == 200
        models_data = v1_resp.json()["data"]
        model_ids = [m["id"] for m in models_data]

        assert "test/visible-model" in model_ids
        assert "test/hidden-model" not in model_ids

        # 4. Hide visible model via Admin PUT /api/admin/models/{id}
        put_resp = await client.put(
            f"/api/admin/models/{vis_id}",
            headers=admin_headers,
            json={"is_visible": False},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["is_visible"] is False

        # Now GET /v1/models should NOT have either model
        v1_resp2 = await client.get("/v1/models", headers=router_headers)
        models_data2 = v1_resp2.json()["data"]
        model_ids2 = [m["id"] for m in models_data2]
        assert "test/visible-model" not in model_ids2
        assert "test/hidden-model" not in model_ids2

        # 5. Batch update both models to is_visible = True via Admin POST /api/admin/models/batch-update
        batch_resp = await client.post(
            "/api/admin/models/batch-update",
            headers=admin_headers,
            json={"model_ids": [vis_id, hid_id], "is_visible": True},
        )
        assert batch_resp.status_code == 200
        assert batch_resp.json()["updated_count"] == 2

        # Now GET /v1/models should contain BOTH models
        v1_resp3 = await client.get("/v1/models", headers=router_headers)
        models_data3 = v1_resp3.json()["data"]
        model_ids3 = [m["id"] for m in models_data3]
        assert "test/visible-model" in model_ids3
        assert "test/hidden-model" in model_ids3

@pytest.mark.asyncio
async def test_retrieve_model_endpoint_and_ollama_compatibility():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization":"Bearer " + __import__("app.services.auth_service",fromlist=["AuthService"]).AuthService.create_access_token("admin")}) as client:
        async with AsyncSessionLocal() as db:
            p = Provider(name="Retrieve Test Provider", slug="retrieve-test", adapter_type="generic_openai", base_url="https://api.test.com")
            db.add(p)
            await db.flush()
            m = DiscoveredModel(
                provider_id=p.id,
                provider_model_id="special/model-xyz",
                display_name="Special Model XYZ",
                canonical_slug="retrieve-test/special/model-xyz",
                capabilities={},
                supported_endpoints=["/chat/completions"],
                context_length=65536,
                max_output_tokens=4096,
                enabled=True,
                available=True,
                is_visible=True,
            )
            db.add(m)
            r = RoutingProfile(name="Test Route", slug="test-single-route", strategy="priority", enabled=True)
            db.add(r)
            k = await ApiKeyService.create_key(
                db,
                data=type("Obj", (), {
                    "name": "Retrieve Test Key",
                    "permissions": ["direct", "routes", "fusion"],
                    "allowed_models": ["*"],
                    "allowed_routes": ["*"],
                    "allowed_fusions": ["*"],
                    "rate_limit_rpm": None,
                    "rate_limit_tpm": None,
                    "request_limit": None,
                    "expiration_date": None,
                    "ip_restrictions": [],
                })()
            )
            raw_key = k.raw_api_key
            await db.commit()

        router_headers = {"Authorization": f"Bearer {raw_key}"}

        # 1. Retrieve model by canonical_slug
        resp = await client.get("/v1/models/retrieve-test/special/model-xyz", headers=router_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "retrieve-test/special/model-xyz"

        # 2. Retrieve model by provider_model_id
        resp2 = await client.get("/v1/models/special/model-xyz", headers=router_headers)
        assert resp2.status_code == 200

        # 3. Retrieve route model
        resp3 = await client.get("/v1/models/route/test-single-route", headers=router_headers)
        assert resp3.status_code == 200
        assert resp3.json()["id"] == "route/test-single-route"

        # 4. Non-existent model returns 404
        resp4 = await client.get("/v1/models/non-existent-model-12345", headers=router_headers)
        assert resp4.status_code == 404
        assert resp4.json()["error"]["code"] == "model_not_found"

        # 5. Ollama /api/show
        resp_show = await client.post("/api/show", json={"name": "retrieve-test/special/model-xyz"})
        assert resp_show.status_code == 200
        show_data = resp_show.json()
        assert show_data["model_info"]["context_length"] == 65536

        # 6. Ollama /api/tags
        resp_tags = await client.get("/api/tags")
        assert resp_tags.status_code == 200
        assert "models" in resp_tags.json()

        # 7. Ollama /api/version
        resp_ver = await client.get("/api/version")
        assert resp_ver.status_code == 200
        assert "version" in resp_ver.json()


@pytest.mark.asyncio
async def test_custom_context_length_override():
    """Verify that admin can set custom context length, and it overrides upstream / reflects in /api/show and /v1/models."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as admin
        login_resp = await client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "test-admin-password-12345"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {token}"}

        # 2. Setup provider and model
        async with AsyncSessionLocal() as db:
            p = Provider(
                name="CtxProvider",
                slug="ctx-provider",
                adapter_type="openai",
                base_url="https://api.ctx.test/v1",
                models_endpoint="/models",
                chat_endpoint="/chat/completions",
                enabled=True,
                auth_type="bearer",
            )
            db.add(p)
            await db.commit()
            await db.refresh(p)

            m = DiscoveredModel(
                provider_id=p.id,
                provider_model_id="ctx-model-1",
                display_name="Context Test Model",
                canonical_slug="ctx-provider/ctx-model-1",
                context_length=8192,
                enabled=True,
                available=True,
                is_visible=True,
            )
            db.add(m)
            await db.commit()
            await db.refresh(m)
            m_id = m.id

        # 3. Verify initial context_length in /api/show is 8192
        show1 = await client.post("/api/show", json={"name": "ctx-provider/ctx-model-1"})
        assert show1.status_code == 200
        assert show1.json()["model_info"]["context_length"] == 8192

        # 4. Admin updates context_length to 32768
        put_resp = await client.put(
            f"/api/admin/models/{m_id}",
            headers=admin_headers,
            json={"context_length": 32768},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["context_length"] == 32768

        # 5. Verify /api/show returns updated 32768
        show2 = await client.post("/api/show", json={"name": "ctx-provider/ctx-model-1"})
        assert show2.status_code == 200
        assert show2.json()["model_info"]["context_length"] == 32768

        # 6. Verify GET /v1/models/{id} returns updated context_length
        v1_resp = await client.get("/v1/models/ctx-provider/ctx-model-1")
        assert v1_resp.status_code == 200
        assert v1_resp.json()["context_length"] == 32768

        # 7. Batch update context_length to 65536
        batch_resp = await client.post(
            "/api/admin/models/batch-update",
            headers=admin_headers,
            json={"model_ids": [m_id], "context_length": 65536},
        )
        assert batch_resp.status_code == 200
        assert batch_resp.json()["updated_count"] == 1

        # 8. Verify /api/show now reflects 65536
        show3 = await client.post("/api/show", json={"name": "ctx-provider/ctx-model-1"})
        assert show3.status_code == 200
        assert show3.json()["model_info"]["context_length"] == 65536

        # 9. Reset context_length by passing 0 or null via Admin PUT
        reset_resp = await client.put(
            f"/api/admin/models/{m_id}",
            headers=admin_headers,
            json={"context_length": 0},
        )
        assert reset_resp.status_code == 200
        assert reset_resp.json()["context_length"] is None

        # 10. Fallback in /api/show when context_length is None is 131072
        show4 = await client.post("/api/show", json={"name": "ctx-provider/ctx-model-1"})
        assert show4.status_code == 200
        assert show4.json()["model_info"]["context_length"] == 131072


@pytest.mark.asyncio
async def test_custom_reasoning_effort_configuration_and_routing():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Admin login
        login_resp = await client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "test-admin-password-12345"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {token}"}

        # 2. Setup provider, credential, model, router key
        async with AsyncSessionLocal() as db:
            p = Provider(
                name="Reasoning Test Provider",
                slug="reasoning-provider",
                adapter_type="openai",
                base_url="https://api.reasoning.test/v1",
                models_endpoint="/models",
                chat_endpoint="/chat/completions",
                enabled=True,
                auth_type="bearer",
            )
            db.add(p)
            await db.commit()
            await db.refresh(p)

            cred = await CredentialService.create_credential(
                db,
                data=type("Obj", (), {
                    "provider_id": p.id,
                    "name": "Reasoning Credential",
                    "api_key": "sk-reasoning-test-123",
                    "proxy_id": None,
                    "priority": 1,
                    "weight": 1,
                    "rpm_limit": None,
                    "tpm_limit": None,
                    "max_concurrency": None,
                })(),
            )

            m = DiscoveredModel(
                provider_id=p.id,
                credential_id=cred.id,
                provider_model_id="reasoning-model-1",
                display_name="Reasoning Test Model",
                canonical_slug="reasoning-provider/reasoning-model-1",
                capabilities={"chat": True, "reasoning": True},
                supported_endpoints=["/chat/completions"],
                enabled=True,
                available=True,
                is_visible=True,
            )
            db.add(m)
            await db.commit()
            await db.refresh(m)
            m_id = m.id

            k = await ApiKeyService.create_key(
                db,
                data=type("Obj", (), {
                    "name": "Reasoning Test Router Key",
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
            router_key = k.raw_api_key

        # 3. Update reasoning_effort to valid words ("high", "medium", "minimal")
        put_resp = await client.put(
            f"/api/admin/models/{m_id}",
            headers=admin_headers,
            json={"reasoning_effort": "high"},
        )
        assert put_resp.status_code == 200, put_resp.text
        assert put_resp.json()["reasoning_effort"] == "high"

        # 4. Attempt to update with numbers -> MUST be rejected (no digits allowed!)
        fail_put = await client.put(
            f"/api/admin/models/{m_id}",
            headers=admin_headers,
            json={"reasoning_effort": "4096"},
        )
        assert fail_put.status_code in (400, 422), fail_put.text

        fail_put2 = await client.put(
            f"/api/admin/models/{m_id}",
            headers=admin_headers,
            json={"reasoning_effort": "level2"},
        )
        assert fail_put2.status_code in (400, 422), fail_put2.text

        # 5. Batch update reasoning_effort
        batch_resp = await client.post(
            "/api/admin/models/batch-update",
            headers=admin_headers,
            json={"model_ids": [m_id], "reasoning_effort": "medium"},
        )
        assert batch_resp.status_code == 200, batch_resp.text
        assert batch_resp.json()["updated_count"] == 1

        # Check model has medium
        get_model = await client.get(f"/v1/models/reasoning-provider/reasoning-model-1")
        assert get_model.status_code == 200

        # Batch update with digits -> rejected
        batch_fail = await client.post(
            "/api/admin/models/batch-update",
            headers=admin_headers,
            json={"model_ids": [m_id], "reasoning_effort": "8192"},
        )
        assert batch_fail.status_code in (400, 422)

        # 6. Test routing with model default reasoning effort
        # Set to 'high'
        await client.put(
            f"/api/admin/models/{m_id}",
            headers=admin_headers,
            json={"reasoning_effort": "high"},
        )

        captured_requests = []

        def mock_handler(request: httpx.Request) -> httpx.Response:
            req_body = json.loads(request.content.decode("utf-8"))
            captured_requests.append(req_body)
            return httpx.Response(
                200,
                json={
                    "id": "cmpl-reasoning-test",
                    "object": "chat.completion",
                    "created": 12345,
                    "model": "reasoning-model-1",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "I reasoned!"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
                },
            )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))

        with patch("app.core.http_client.http_client_manager.get_client", return_value=mock_client):
            # A) Request without reasoning_effort -> upstream receives model default 'high'
            resp_a = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {router_key}"},
                json={
                    "model": "reasoning-provider/reasoning-model-1",
                    "messages": [{"role": "user", "content": "Solve math"}],
                },
            )
            assert resp_a.status_code == 200, resp_a.text
            assert len(captured_requests) == 1
            assert captured_requests[0]["reasoning_effort"] == "high"

            # B) Request with explicit reasoning_effort='low' -> request override takes precedence!
            resp_b = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {router_key}"},
                json={
                    "model": "reasoning-provider/reasoning-model-1",
                    "messages": [{"role": "user", "content": "Quick answer"}],
                    "reasoning_effort": "low",
                },
            )
            assert resp_b.status_code == 200, resp_b.text
            assert len(captured_requests) == 2
            assert captured_requests[1]["reasoning_effort"] == "low"

        # 7. Reset reasoning effort to None
        reset_resp = await client.put(
            f"/api/admin/models/{m_id}",
            headers=admin_headers,
            json={"reasoning_effort": None},
        )
        assert reset_resp.status_code == 200
        assert reset_resp.json()["reasoning_effort"] is None



