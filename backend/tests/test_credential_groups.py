import pytest
import httpx
import uuid
from unittest.mock import patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, delete
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import (
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
    RoutingCandidate,
)
from app.schemas.entities import (
    CredentialCreate,
    CredentialUpdate,
    RoutingProfileCreate,
    RoutingCandidateInput,
)
from app.services.credential_service import CredentialService
from app.services.routing_service import RoutingService
from app.services.api_key_service import ApiKeyService

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
async def test_credential_group_crud():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, "openai")

        # 1. Create with group_name
        cred_create = CredentialCreate(
            provider_id=provider.id,
            name=f"Grouped Key {run_id}",
            api_key=f"sk-grouped-{run_id}",
            group_name="Primary Team",
            priority=1,
            weight=1,
        )
        c = await CredentialService.create_credential(db, cred_create)
        assert c.group_name == "Primary Team"

        # Check in DB
        db_cred = await CredentialService.get_credential(db, c.id)
        assert db_cred is not None
        assert db_cred.group_name == "Primary Team"

        # 2. Update group_name to another group
        c_up = await CredentialService.update_credential(
            db, c.id, CredentialUpdate(group_name="Backup Team")
        )
        assert c_up is not None
        assert c_up.group_name == "Backup Team"

        # 3. Clear group_name (pass empty string or None)
        c_clear = await CredentialService.update_credential(
            db, c.id, CredentialUpdate(group_name="")
        )
        assert c_clear is not None
        assert c_clear.group_name is None

        # Clean up
        await CredentialService.delete_credential(db, c.id)

@pytest.mark.asyncio
async def test_routing_candidate_credential_group_fallback():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, "openai")

        key1_secret = f"sk-groupA-fail429-{run_id}"
        key2_secret = f"sk-groupA-ok200-{run_id}"
        key3_secret = f"sk-groupB-unused-{run_id}"

        c1 = await CredentialService.create_credential(
            db,
            CredentialCreate(
                provider_id=provider.id,
                name=f"Key 1 Group A {run_id}",
                api_key=key1_secret,
                group_name="tier_a",
                priority=1,
                weight=1,
            ),
        )

        c2 = await CredentialService.create_credential(
            db,
            CredentialCreate(
                provider_id=provider.id,
                name=f"Key 2 Group A {run_id}",
                api_key=key2_secret,
                group_name="tier_a",
                priority=2,
                weight=1,
            ),
        )

        c3 = await CredentialService.create_credential(
            db,
            CredentialCreate(
                provider_id=provider.id,
                name=f"Key 3 Group B {run_id}",
                api_key=key3_secret,
                group_name="tier_b",
                priority=1,
                weight=1,
            ),
        )

        m = DiscoveredModel(
            provider_id=provider.id,
            credential_id=c1.id,
            provider_model_id=f"gpt-group-{run_id}",
            display_name="GPT Group Mock",
            canonical_slug=f"openai/gpt-group-{run_id}",
            capabilities={"chat": True, "streaming": True},
            supported_endpoints=["/chat/completions"],
            enabled=True,
            available=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        route_slug = f"route-group-{run_id}"
        profile_data = RoutingProfileCreate(
            name=f"Group Route {run_id}",
            slug=route_slug,
            strategy="priority",
            retry_count=2,
            timeout_seconds=10.0,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX"],
            enabled=True,
            candidates=[
                RoutingCandidateInput(
                    candidate_type="model",
                    provider_id=provider.id,
                    credential_id=None,
                    credential_group="tier_a",
                    model_id=m.id,
                    priority_order=1,
                    is_active=True,
                )
            ],
        )
        created_profile = await RoutingService.create_profile(db, profile_data)
        assert created_profile.candidates[0].credential_group == "tier_a"
        assert created_profile.candidates[0].credential_id is None

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

    called_keys = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        if key1_secret in auth:
            called_keys.append("key1_fail")
            return httpx.Response(429, json={"error": {"message": "Rate limit on Key 1"}})
        elif key2_secret in auth:
            called_keys.append("key2_ok")
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-group-success",
                    "object": "chat.completion",
                    "created": 1234567,
                    "model": f"gpt-group-{run_id}",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "Hello from tier_a Key 2!"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                },
            )
        elif key3_secret in auth:
            called_keys.append("key3_tier_b")
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "from tier_b"}}]})
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
            assert data["choices"][0]["message"]["content"] == "Hello from tier_a Key 2!"
            # Verify Key 3 (tier_b) was NEVER called because routing was restricted to tier_a!
            assert "key3_tier_b" not in called_keys
            assert "key2_ok" in called_keys

@pytest.mark.asyncio
async def test_folder_configuration_and_dnd_group_switch():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-{run_id}")

        from app.services.provider_service import ProviderService
        from app.schemas.entities import ProviderUpdate

        folders = ["Production", "Staging", "Empty-Folder"]
        updated_prov = await ProviderService.update_provider(
            db, provider.id, ProviderUpdate(configuration={"folders": folders})
        )
        assert updated_prov.configuration.get("folders") == folders

        c = await CredentialService.create_credential(
            db,
            CredentialCreate(
                provider_id=provider.id,
                name=f"Key {run_id}",
                api_key=f"sk-test-{run_id}",
                group_name=None,
            ),
        )
        assert c.group_name is None

        c_moved = await CredentialService.update_credential(
            db, c.id, CredentialUpdate(group_name="Empty-Folder")
        )
        assert c_moved.group_name == "Empty-Folder"

        c_returned = await CredentialService.update_credential(
            db, c.id, CredentialUpdate(group_name=None)
        )
        assert c_returned.group_name is None

        await CredentialService.delete_credential(db, c.id)
        await ProviderService.delete_provider(db, provider.id)

@pytest.mark.asyncio
async def test_bulk_assign_group():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        provider = await get_or_create_provider(db, f"prov-bulk-{run_id}")

        c1 = await CredentialService.create_credential(
            db,
            CredentialCreate(
                provider_id=provider.id,
                name=f"Bulk Key 1 {run_id}",
                api_key=f"sk-b1-{run_id}",
            ),
        )
        c2 = await CredentialService.create_credential(
            db,
            CredentialCreate(
                provider_id=provider.id,
                name=f"Bulk Key 2 {run_id}",
                api_key=f"sk-b2-{run_id}",
            ),
        )
        c3 = await CredentialService.create_credential(
            db,
            CredentialCreate(
                provider_id=provider.id,
                name=f"Bulk Key 3 {run_id}",
                api_key=f"sk-b3-{run_id}",
            ),
        )

        # 1. Bulk assign to "Folder Alpha"
        updated = await CredentialService.bulk_assign_group(
            db, [c1.id, c2.id, c3.id], "Folder Alpha"
        )
        assert len(updated) == 3
        assert all(c.group_name == "Folder Alpha" for c in updated)

        # 2. Check provider config persisted "Folder Alpha"
        from app.services.provider_service import ProviderService
        prov_recheck = await ProviderService.get_provider(db, provider.id)
        assert "Folder Alpha" in prov_recheck.configuration.get("folders", [])

        # 3. Test via API endpoint with admin login
        from app.services.auth_service import AuthService
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
                "/api/admin/credentials/bulk-assign-group",
                headers=headers,
                json={"credential_ids": [c1.id, c2.id], "group_name": "Folder Beta"},
            )
            assert api_resp.status_code == 200
            data = api_resp.json()
            assert len(data) == 2
            assert all(c["group_name"] == "Folder Beta" for c in data)

            # Move back to "Без группы" (None)
            clear_resp = await client.post(
                "/api/admin/credentials/bulk-assign-group",
                headers=headers,
                json={"credential_ids": [c1.id, c2.id, c3.id], "group_name": ""},
            )
            assert clear_resp.status_code == 200
            clear_data = clear_resp.json()
            assert len(clear_data) == 3
            assert all(c["group_name"] is None for c in clear_data)

        # Cleanup
        db.expunge_all()
        await db.execute(delete(ProviderCredential).where(ProviderCredential.id.in_([c1.id, c2.id, c3.id])))
        await db.commit()
        await ProviderService.delete_provider(db, provider.id)

