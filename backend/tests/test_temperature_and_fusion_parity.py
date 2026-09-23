import pytest
import uuid
from unittest.mock import patch, AsyncMock

from app.core.database import AsyncSessionLocal
from app.models.entities import Provider, DiscoveredModel, RoutingProfile, RoutingCandidate, ProviderCredential, FusionProfile, FusionParticipant
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatMessage, UsageInfo
from app.schemas.entities import FusionProfileCreate, FusionParticipantInput
from app.services.credential_service import CredentialService
from app.services.fusion_service import FusionService
from app.routing.engine import RoutingEngine
from app.fusion.engine import FusionEngine


@pytest.mark.asyncio
async def test_routing_temperature_resolution_hierarchy():
    """
    Verifies that RoutingEngine correctly resolves temperature in the proper order:
    Candidate override -> Profile default -> Request temperature -> Model default -> fallback.
    """
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name=f"Temp Prov {run_id}", slug=f"temp-prov-{run_id}", adapter_type="openai",
            base_url="https://api.openai.com/v1", models_endpoint="/models",
            chat_endpoint="/chat/completions", enabled=True,
            auth_type="bearer", auth_header="Authorization",
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)

        c = await CredentialService.create_credential(db, type("Obj", (), {
            "provider_id": p.id, "name": f"Key {run_id}", "api_key": f"sk-{run_id}",
            "proxy_id": None, "priority": 1, "weight": 10, "rpm_limit": None,
            "tpm_limit": None, "max_concurrency": None, "group_name": "prod-keys",
        })())

        m = DiscoveredModel(
            provider_id=p.id, provider_model_id=f"temp-model-{run_id}",
            canonical_slug=f"temp/model-{run_id}", display_name=f"Model {run_id}",
            context_length=128000, max_output_tokens=4096, enabled=True, available=True, is_visible=True,
            temperature=0.7,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        # Profile with temperature=0.5, candidate 1 with temperature=0.2, candidate 2 with temperature=None
        rp = RoutingProfile(
            name=f"Temp Route {run_id}", slug=f"temp-route-{run_id}",
            description="Testing temp hierarchy", temperature=0.5,
        )
        db.add(rp)
        await db.commit()
        await db.refresh(rp)

        cand1 = RoutingCandidate(
            profile_id=rp.id, candidate_type="model",
            provider_id=p.id, model_id=m.id, credential_id=c.id,
            priority_order=1, temperature=0.2,
        )
        cand2 = RoutingCandidate(
            profile_id=rp.id, candidate_type="model",
            provider_id=p.id, model_id=m.id, credential_id=c.id,
            priority_order=2, temperature=None,
        )
        db.add_all([cand1, cand2])
        await db.commit()

        # Case 1: Candidate 1 has override 0.2 -> must resolve to 0.2
        req1 = ChatCompletionRequest(model=f"route/{rp.slug}", messages=[{"role": "user", "content": "Hi"}], temperature=1.0)
        mod_req1 = RoutingEngine._apply_model_defaults(req1, m, candidate_temperature=cand1.temperature, profile_temperature=rp.temperature)
        assert mod_req1.temperature == 0.2

        # Case 2: Candidate 2 has no override (None), Profile has 0.5 -> must resolve to 0.5
        req2 = ChatCompletionRequest(model=f"route/{rp.slug}", messages=[{"role": "user", "content": "Hi"}], temperature=1.0)
        mod_req2 = RoutingEngine._apply_model_defaults(req2, m, candidate_temperature=cand2.temperature, profile_temperature=rp.temperature)
        assert mod_req2.temperature == 0.5

        # Case 3: Both candidate and profile have None -> uses request temperature 0.9
        req3 = ChatCompletionRequest(model=f"route/{rp.slug}", messages=[{"role": "user", "content": "Hi"}], temperature=0.9)
        mod_req3 = RoutingEngine._apply_model_defaults(req3, m, candidate_temperature=None, profile_temperature=None)
        assert mod_req3.temperature == 0.9

        # Case 4: Candidate has 0.0 (falsy in python) -> must NOT be skipped, resolves to 0.0
        req4 = ChatCompletionRequest(model=f"route/{rp.slug}", messages=[{"role": "user", "content": "Hi"}], temperature=1.0)
        mod_req4 = RoutingEngine._apply_model_defaults(req4, m, candidate_temperature=0.0, profile_temperature=0.5)
        assert mod_req4.temperature == 0.0


@pytest.mark.asyncio
async def test_fusion_parity_and_temperature():
    """
    Verifies that Fusion profile and participants support temperature, thinking_effort,
    credential groups, and priority order properly.
    """
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name=f"FusionParity Prov {run_id}", slug=f"fparity-{run_id}", adapter_type="openai",
            base_url="https://api.openai.com/v1", models_endpoint="/models",
            chat_endpoint="/chat/completions", enabled=True,
            auth_type="bearer", auth_header="Authorization",
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)

        c_prod = await CredentialService.create_credential(db, type("Obj", (), {
            "provider_id": p.id, "name": f"Key Prod {run_id}", "api_key": f"sk-prod-{run_id}",
            "proxy_id": None, "priority": 1, "weight": 10, "rpm_limit": None,
            "tpm_limit": None, "max_concurrency": None, "group_name": "prod-group",
        })())

        c_judge = await CredentialService.create_credential(db, type("Obj", (), {
            "provider_id": p.id, "name": f"Key Judge {run_id}", "api_key": f"sk-judge-{run_id}",
            "proxy_id": None, "priority": 1, "weight": 10, "rpm_limit": None,
            "tpm_limit": None, "max_concurrency": None, "group_name": "judge-group",
        })())

        m = DiscoveredModel(
            provider_id=p.id, provider_model_id=f"fmodel-{run_id}",
            canonical_slug=f"fparity/model-{run_id}", display_name=f"Model {run_id}",
            context_length=128000, max_output_tokens=4096, enabled=True, available=True, is_visible=True,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        # Create Fusion profile via FusionService
        create_data = FusionProfileCreate(
            name=f"Full Parity Fusion {run_id}",
            slug=f"full-parity-{run_id}",
            strategy="synthesize",
            temperature=0.6,
            judge_type="model",
            judge_routing_profile_id=None,
            judge_provider_id=p.id,
            judge_credential_id=None,
            judge_credential_group="judge-group",
            judge_model_id=m.id,
            judge_thinking_effort="high",
            judge_temperature=0.1,
            min_successful_candidates=1,
            max_parallelism=3,
            timeout_seconds=60.0,
            system_prompt="Judge synthesized output",
            participants=[
                FusionParticipantInput(
                    participant_type="model",
                    target_profile_id=None,
                    provider_id=p.id,
                    credential_id=None,
                    credential_group="prod-group",
                    model_id=m.id,
                    label="Candidate A",
                    thinking_effort="medium",
                    temperature=0.3,
                    priority_order=0,
                    is_active=True,
                ),
                FusionParticipantInput(
                    participant_type="model",
                    target_profile_id=None,
                    provider_id=p.id,
                    credential_id=c_prod.id,
                    credential_group=None,
                    model_id=m.id,
                    label="Candidate B",
                    thinking_effort="off",
                    temperature=None,
                    priority_order=1,
                    is_active=True,
                ),
            ],
        )

        fp_read = await FusionService.create_profile(db, create_data)
        assert fp_read.temperature == 0.6
        assert fp_read.judge_temperature == 0.1
        assert fp_read.judge_thinking_effort == "high"
        assert fp_read.judge_credential_group == "judge-group"
        assert len(fp_read.participants) == 2

        part_a = next(pt for pt in fp_read.participants if pt.label == "Candidate A")
        assert part_a.temperature == 0.3
        assert part_a.thinking_effort == "medium"
        assert part_a.credential_group == "prod-group"
        assert part_a.priority_order == 0

        part_b = next(pt for pt in fp_read.participants if pt.label == "Candidate B")
        assert part_b.temperature is None
        assert part_b.thinking_effort == "off"
        assert part_b.credential_id == c_prod.id
        assert part_b.priority_order == 1

        # Fetch DB entity
        fp_entity = await FusionService.get_profile_by_slug(db, fp_read.slug)
        assert fp_entity is not None
        db_part_a = next(pt for pt in fp_entity.participants if pt.label == "Candidate A")
        db_part_b = next(pt for pt in fp_entity.participants if pt.label == "Candidate B")

        # Test single participant execution parameter preparation
        base_req = ChatCompletionRequest(model=f"fusion/{fp_entity.slug}", messages=[{"role": "user", "content": "Hello"}])

        mock_resp = ChatCompletionResponse(
            id="chatcmpl-test",
            object="chat.completion",
            created=123456789,
            model=m.provider_model_id,
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content="Candidate output"),
                finish_reason="stop",
            )],
            usage=UsageInfo(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )

        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_resp
            # Execute participant A (has temp 0.3 and thinking_effort medium)
            res_a = await FusionEngine._execute_single_participant(0, db_part_a, base_req, 30.0, fp_entity)
            assert res_a["error"] is None
            assert res_a["content"] == "Candidate output"
            call_kwargs = mock_chat.call_args[1]
            called_req = call_kwargs["request"]
            assert called_req.temperature == 0.3
            assert called_req.reasoning_effort == "medium"

        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_resp
            # Execute participant B (temp is None -> inherits profile.temperature 0.6, thinking_effort is off)
            res_b = await FusionEngine._execute_single_participant(1, db_part_b, base_req, 30.0, fp_entity)
            assert res_b["error"] is None
            assert res_b["content"] == "Candidate output"
            call_kwargs = mock_chat.call_args[1]
            called_req = call_kwargs["request"]
            assert called_req.temperature == 0.6
            assert called_req.reasoning_effort == "none"
