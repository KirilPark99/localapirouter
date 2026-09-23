import pytest
import uuid
import json
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.entities import Provider, DiscoveredModel, RoutingProfile, RoutingCandidate, ProviderCredential, FusionProfile, FusionParticipant
from app.schemas.chat import ChatCompletionResponse, ChatCompletionChoice, ChatMessage, UsageInfo
from app.services.credential_service import CredentialService
from app.services.fusion_service import FusionService
from app.services.auth_service import AuthService
from app.core.errors import RouterException, ErrorCategory


@pytest.mark.asyncio
async def test_candidate_all_keys_auto_selection_and_failover():
    """
    Verifies that a candidate with credential_id=None ('подбор всех ключей')
    iterates through available provider credentials, handles key failure,
    and succeeds using the working credential.
    """
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name=f"MultiKey Prov {run_id}", slug=f"multikey-{run_id}", adapter_type="openai",
            base_url="https://api.openai.com/v1", models_endpoint="/models",
            chat_endpoint="/chat/completions", enabled=True,
            auth_type="bearer", auth_header="Authorization",
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)

        # Create two credentials: key 1 will fail, key 2 will succeed
        c1 = await CredentialService.create_credential(db, type("Obj", (), {
            "provider_id": p.id, "name": f"Key 1 Bad {run_id}", "api_key": f"sk-bad-{run_id}",
            "proxy_id": None, "priority": 1, "weight": 10, "rpm_limit": None,
            "tpm_limit": None, "max_concurrency": None, "group_name": None,
        })())
        c2 = await CredentialService.create_credential(db, type("Obj", (), {
            "provider_id": p.id, "name": f"Key 2 Good {run_id}", "api_key": f"sk-good-{run_id}",
            "proxy_id": None, "priority": 2, "weight": 5, "rpm_limit": None,
            "tpm_limit": None, "max_concurrency": None, "group_name": None,
        })())

        m = DiscoveredModel(
            provider_id=p.id, provider_model_id=f"model-{run_id}",
            canonical_slug=f"multikey/model-{run_id}", display_name=f"Model {run_id}",
            context_length=128000, max_output_tokens=4096, enabled=True, available=True, is_visible=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        # Fusion profile where candidate has credential_id=None (auto-selection)
        fp = FusionProfile(
            name=f"AutoKey Fusion {run_id}", slug=f"autokey-fusion-{run_id}",
            strategy="synthesize", judge_type="model",
            judge_provider_id=p.id, judge_credential_id=c2.id, judge_model_id=m.id,
            min_successful_candidates=1, max_parallelism=2, timeout_seconds=10.0, enabled=True,
        )
        db.add(fp)
        await db.commit()
        await db.refresh(fp)

        part = FusionParticipant(
            profile_id=fp.id, participant_type="model",
            provider_id=p.id, credential_id=None, model_id=m.id,
            label="Candidate AutoKey", is_active=True,
        )
        db.add(part)

        from app.services.api_key_service import ApiKeyService
        k = await ApiKeyService.create_key(
            db, data=type("Obj", (), {
                "name": f"Key {run_id}", "permissions": ["direct", "routes", "fusion"],
                "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"],
                "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None,
                "expiration_date": None, "ip_restrictions": [],
            })(),
        )
        raw_key = k.raw_api_key
        await db.commit()

    # Mock adapter: sk-bad fails, sk-good succeeds
    call_keys = []
    async def mock_chat_completions(*args, **kwargs):
        api_key = kwargs.get("api_key", "")
        call_keys.append(api_key)
        if "bad" in api_key:
            raise RouterException("Key 1 rate-limited", ErrorCategory.RATE_LIMIT, status_code=429)
        return ChatCompletionResponse(
            id=f"chatcmpl_{uuid.uuid4().hex[:8]}",
            object="chat.completion",
            created=1700000000,
            model="model",
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=f"Success from key: {api_key}"),
                finish_reason="stop",
            )],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        )

    with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", new=mock_chat_completions):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key}"},
                json={
                    "model": f"fusion/autokey-fusion-{run_id}",
                    "messages": [{"role": "user", "content": "Hello AutoKey"}],
                }
            )
            assert res.status_code == 200, f"Error: {res.text}"
            data = res.json()
            assert "Success from key" in data["choices"][0]["message"]["content"]
            # Verify that both bad key was attempted, then good key succeeded
            assert any("bad" in k for k in call_keys)
            assert any("good" in k for k in call_keys)


@pytest.mark.asyncio
async def test_candidate_and_judge_as_routing_profile():
    """
    Verifies that:
    1) A candidate can be a fallback RoutingProfile (participant_type='profile');
    2) The judge can be a fallback RoutingProfile (judge_type='profile').
    """
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name=f"RouteProv {run_id}", slug=f"routeprov-{run_id}", adapter_type="openai",
            base_url="https://api.openai.com/v1", models_endpoint="/models",
            chat_endpoint="/chat/completions", enabled=True,
            auth_type="bearer", auth_header="Authorization",
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)

        c = await CredentialService.create_credential(db, type("Obj", (), {
            "provider_id": p.id, "name": f"Key {run_id}", "api_key": f"sk-route-{run_id}",
            "proxy_id": None, "priority": 1, "weight": 1, "rpm_limit": None,
            "tpm_limit": None, "max_concurrency": None, "group_name": None,
        })())

        m = DiscoveredModel(
            provider_id=p.id, provider_model_id=f"gpt-model-{run_id}",
            canonical_slug=f"routeprov/gpt-model-{run_id}", display_name=f"GPT Model {run_id}",
            context_length=128000, max_output_tokens=4096, enabled=True, available=True, is_visible=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        # 1. Routing profile to be used as candidate
        cand_route = RoutingProfile(
            name=f"Candidate Route {run_id}", slug=f"cand-route-{run_id}",
            strategy="priority", enabled=True, retry_count=2, timeout_seconds=10.0,
        )
        db.add(cand_route)
        await db.commit()
        await db.refresh(cand_route)

        cand_candidate = RoutingCandidate(
            profile_id=cand_route.id, candidate_type="model",
            provider_id=p.id, credential_id=c.id, model_id=m.id,
            priority_order=1, is_active=True,
        )
        db.add(cand_candidate)

        # 2. Routing profile to be used as judge
        judge_route = RoutingProfile(
            name=f"Judge Route {run_id}", slug=f"judge-route-{run_id}",
            strategy="priority", enabled=True, retry_count=2, timeout_seconds=10.0,
        )
        db.add(judge_route)
        await db.commit()
        await db.refresh(judge_route)

        judge_candidate = RoutingCandidate(
            profile_id=judge_route.id, candidate_type="model",
            provider_id=p.id, credential_id=c.id, model_id=m.id,
            priority_order=1, is_active=True,
        )
        db.add(judge_candidate)

        # 3. Fusion profile with:
        # - judge_type="profile", judge_routing_profile_id=judge_route.id
        # - participant 1: profile (cand_route)
        # - participant 2: model (m)
        fusion = FusionProfile(
            name=f"Profile Fusion {run_id}", slug=f"profile-fusion-{run_id}",
            strategy="synthesize",
            judge_type="profile",
            judge_routing_profile_id=judge_route.id,
            min_successful_candidates=2, max_parallelism=2, timeout_seconds=15.0, enabled=True,
        )
        db.add(fusion)
        await db.commit()
        await db.refresh(fusion)

        part_profile = FusionParticipant(
            profile_id=fusion.id, participant_type="profile",
            target_profile_id=cand_route.id, label="Candidate Route Profile", is_active=True,
        )
        part_model = FusionParticipant(
            profile_id=fusion.id, participant_type="model",
            provider_id=p.id, credential_id=c.id, model_id=m.id,
            label="Candidate Direct Model", is_active=True,
        )
        db.add(part_profile)
        db.add(part_model)

        from app.services.api_key_service import ApiKeyService
        k2 = await ApiKeyService.create_key(
            db, data=type("Obj", (), {
                "name": f"Key2 {run_id}", "permissions": ["direct", "routes", "fusion"],
                "allowed_models": ["*"], "allowed_routes": ["*"], "allowed_fusions": ["*"],
                "rate_limit_rpm": None, "rate_limit_tpm": None, "request_limit": None,
                "expiration_date": None, "ip_restrictions": [],
            })(),
        )
        raw_key2 = k2.raw_api_key
        await db.commit()

    called_models = []
    async def mock_chat(*args, **kwargs):
        model_id = kwargs.get("model_id", "")
        called_models.append(model_id)
        return ChatCompletionResponse(
            id=f"chatcmpl_{uuid.uuid4().hex[:8]}",
            object="chat.completion",
            created=1700000000,
            model=model_id,
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=f"Synthesized answer via route judge for {model_id}"),
                finish_reason="stop",
            )],
            usage=UsageInfo(prompt_tokens=15, completion_tokens=20, total_tokens=35),
        )

    with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", new=mock_chat):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": f"Bearer {raw_key2}"},
                json={
                    "model": f"fusion/profile-fusion-{run_id}",
                    "messages": [{"role": "user", "content": "Synthesize via route profiles!"}],
                }
            )
            assert res.status_code == 200, f"Error: {res.text}"
            data = res.json()
            assert "Synthesized answer via route judge" in data["choices"][0]["message"]["content"]
            assert data["model"] == f"fusion/profile-fusion-{run_id}"
            # Verify candidate route and judge route were both executed
            assert len(called_models) >= 3  # 2 candidates + 1 judge


@pytest.mark.asyncio
async def test_admin_api_fusion_with_profiles():
    """
    Tests CRUD through Admin API with judge_type='profile' and participant_type='profile'.
    """
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name=f"Admin Prov {run_id}", slug=f"admin-prov-{run_id}", adapter_type="openai",
            base_url="https://api.openai.com/v1", models_endpoint="/models",
            chat_endpoint="/chat/completions", enabled=True,
            auth_type="bearer", auth_header="Authorization",
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)

        route = RoutingProfile(
            name=f"Fallback Route {run_id}", slug=f"fallback-route-{run_id}",
            strategy="priority", enabled=True, retry_count=2, timeout_seconds=10.0,
        )
        db.add(route)
        await db.commit()
        await db.refresh(route)
        route_id = route.id

    token = AuthService.create_access_token("admin")
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create with judge as profile and candidate as profile
        create_payload = {
            "name": f"Admin Profile Fusion {run_id}",
            "slug": f"admin-profile-fusion-{run_id}",
            "strategy": "best_of_n",
            "judge_type": "profile",
            "judge_routing_profile_id": route_id,
            "min_successful_candidates": 1,
            "participants": [
                {
                    "participant_type": "profile",
                    "target_profile_id": route_id,
                    "label": "Route Candidate",
                    "is_active": True,
                }
            ],
        }
        res = await client.post("/api/admin/fusion", json=create_payload, headers=headers)
        assert res.status_code == 201, f"Error: {res.text}"
        data = res.json()
        assert data["judge_type"] == "profile"
        assert data["judge_routing_profile_id"] == route_id
        assert data["participants"][0]["participant_type"] == "profile"
        assert data["participants"][0]["target_profile_id"] == route_id
        created_id = data["id"]

        # Read back
        get_res = await client.get(f"/api/admin/fusion/{created_id}", headers=headers)
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["judge_routing_profile_slug"] == f"fallback-route-{run_id}"
        assert get_data["participants"][0]["canonical_slug"] == f"route/fallback-route-{run_id}"

        # Delete
        del_res = await client.delete(f"/api/admin/fusion/{created_id}", headers=headers)
        assert del_res.status_code == 200
