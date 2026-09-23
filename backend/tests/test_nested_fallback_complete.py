import pytest
import uuid
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.crypto import encrypt_secret
from app.core.errors import normalize_upstream_error
from app.core.circuit_breaker import circuit_breaker
from app.models.entities import (
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
    RoutingCandidate,
    RequestLog,
)
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.routing.engine import RoutingEngine


@pytest.mark.asyncio
async def test_nested_fallback_all_scenarios():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        # Setup Provider
        p = Provider(
            name=f"p-nest-{run_id}",
            slug=f"p-nest-{run_id}",
            base_url="https://api.nested.test/v1",
            adapter_type="generic_openai",
            enabled=True,
        )
        db.add(p)
        await db.flush()

        # Credentials: 3 credentials for key randomization test
        c1 = ProviderCredential(
            provider_id=p.id,
            name=f"c1-{run_id}",
            encrypted_api_key=encrypt_secret("key-1"),
            key_fingerprint=f"fp-c1-{run_id}",
            masked_key="sk-***1",
            priority=1,
            enabled=True,
        )
        c2 = ProviderCredential(
            provider_id=p.id,
            name=f"c2-{run_id}",
            encrypted_api_key=encrypt_secret("key-2"),
            key_fingerprint=f"fp-c2-{run_id}",
            masked_key="sk-***2",
            priority=1,
            enabled=True,
        )
        c3 = ProviderCredential(
            provider_id=p.id,
            name=f"c3-{run_id}",
            encrypted_api_key=encrypt_secret("key-3"),
            key_fingerprint=f"fp-c3-{run_id}",
            masked_key="sk-***3",
            priority=1,
            enabled=True,
        )
        db.add_all([c1, c2, c3])
        await db.flush()

        # Models
        m_sub1 = DiscoveredModel(provider_id=p.id, provider_model_id="m-sub-1", display_name="Sub Model 1", canonical_slug=f"{p.slug}/m-sub-1", enabled=True, available=True)
        m_sub2 = DiscoveredModel(provider_id=p.id, provider_model_id="m-sub-2", display_name="Sub Model 2", canonical_slug=f"{p.slug}/m-sub-2", enabled=True, available=True)
        m_parent_backup = DiscoveredModel(provider_id=p.id, provider_model_id="m-parent-backup", display_name="Parent Backup", canonical_slug=f"{p.slug}/m-parent-backup", enabled=True, available=True)
        m_multi_key = DiscoveredModel(provider_id=p.id, provider_model_id="m-multi-key", display_name="Multi Key Model", canonical_slug=f"{p.slug}/m-multi-key", enabled=True, available=True)
        db.add_all([m_sub1, m_sub2, m_parent_backup, m_multi_key])
        await db.flush()

        # 1. Sub-Profile with 2 candidates
        sub_profile = RoutingProfile(
            name=f"SubProfile-{run_id}",
            slug=f"sub-slug-{run_id}",
            strategy="priority",
            randomize_candidates=False,
            randomize_keys=False,
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(sub_profile)
        await db.flush()

        sub_c1 = RoutingCandidate(profile_id=sub_profile.id, candidate_type="model", provider_id=p.id, credential_id=c1.id, model_id=m_sub1.id, priority_order=0, is_active=True)
        sub_c2 = RoutingCandidate(profile_id=sub_profile.id, candidate_type="model", provider_id=p.id, credential_id=c2.id, model_id=m_sub2.id, priority_order=1, is_active=True)
        db.add_all([sub_c1, sub_c2])
        await db.flush()

        # 2. Parent Profile: Candidate #1 is sub_profile, Candidate #2 is parent backup
        parent_profile = RoutingProfile(
            name=f"ParentProfile-{run_id}",
            slug=f"parent-slug-{run_id}",
            strategy="priority",
            randomize_candidates=False,
            randomize_keys=False,
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(parent_profile)
        await db.flush()

        parent_c1 = RoutingCandidate(profile_id=parent_profile.id, candidate_type="profile", target_profile_id=sub_profile.id, priority_order=0, is_active=True)
        parent_c2 = RoutingCandidate(profile_id=parent_profile.id, candidate_type="model", provider_id=p.id, credential_id=c3.id, model_id=m_parent_backup.id, priority_order=1, is_active=True)
        db.add_all([parent_c1, parent_c2])
        await db.commit()

        # =========================================================================
        # TEST 1: Subprofile candidate #1 fails -> subprofile candidate #2 succeeds
        # =========================================================================
        async def mock_chat_sub_fallback(*args, **kwargs):
            mid = kwargs.get("model_id")
            if mid == "m-sub-1":
                raise normalize_upstream_error(status_code=429, response_body={"error": {"message": f"Rate limited on {mid}"}})
            return ChatCompletionResponse(
                model=mid,
                choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=f"Success from {mid}"))],
                usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            )

        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_chat_sub_fallback):
            req = ChatCompletionRequest(
                model=f"route/{parent_profile.slug}",
                messages=[ChatMessage(role="user", content="Test sub fallback")],
            )
            res = await RoutingEngine.route_chat_completions(db, req, None)
            assert res.choices[0].message.content == "Success from m-sub-2"

        # Reset circuit breaker before test 2
        from app.core.circuit_breaker import circuit_breaker
        circuit_breaker.reset(c1.id)
        circuit_breaker.reset(c2.id)
        circuit_breaker.reset(c3.id)

        # =========================================================================
        # TEST 2: ALL candidates in subprofile fail -> Parent falls back to parent backup!
        # =========================================================================
        async def mock_chat_parent_recovery(*args, **kwargs):
            mid = kwargs.get("model_id")
            if mid in ("m-sub-1", "m-sub-2"):
                raise normalize_upstream_error(status_code=500, response_body={"error": {"message": f"Dead {mid}"}})
            return ChatCompletionResponse(
                model=mid,
                choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=f"Success from {mid}"))],
                usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            )

        req_id_parent_rec = f"req_par_rec_{run_id}"
        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_chat_parent_recovery):
            req = ChatCompletionRequest(
                model=f"route/{parent_profile.slug}",
                messages=[ChatMessage(role="user", content="Test parent recovery")],
            )
            res = await RoutingEngine.route_chat_completions(db, req, None, request_id=req_id_parent_rec)
            assert res.choices[0].message.content == "Success from m-parent-backup"

        # Check DB log for Test 2: attempts should show m-sub-1 FAILED, m-sub-2 FAILED, m-parent-backup SUCCESS
        async with AsyncSessionLocal() as vdb:
            log_item = (await vdb.execute(
                select(RequestLog).options(selectinload(RequestLog.attempts)).where(RequestLog.request_id == req_id_parent_rec)
            )).scalar_one_or_none()
            assert log_item is not None
            assert log_item.status == "FALLBACK_SUCCESS"
            attempts = sorted(log_item.attempts, key=lambda a: a.attempt_number)
            assert len(attempts) == 3
            assert attempts[0].status == "FAILED"
            assert "Sub Model 1" in attempts[0].model_name
            assert attempts[1].status == "FAILED"
            assert "Sub Model 2" in attempts[1].model_name
            assert attempts[2].status == "SUCCESS"
            assert "Parent Backup" in attempts[2].model_name


@pytest.mark.asyncio
async def test_nested_fallback_randomization_and_circular():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name=f"p-rand-{run_id}",
            slug=f"p-rand-{run_id}",
            base_url="https://api.rand.test/v1",
            adapter_type="generic_openai",
            enabled=True,
        )
        db.add(p)
        await db.flush()

        # 3 credentials with same priority for randomize_keys
        creds = []
        for i in range(1, 4):
            c = ProviderCredential(
                provider_id=p.id,
                name=f"cred-{i}-{run_id}",
                encrypted_api_key=encrypt_secret(f"key-{i}"),
                key_fingerprint=f"fp-rand-{i}-{run_id}",
                masked_key=f"sk-***{i}",
                priority=1,
                weight=1,
                enabled=True,
            )
            db.add(c)
            creds.append(c)
        await db.flush()

        m1 = DiscoveredModel(provider_id=p.id, provider_model_id="m-rand-1", display_name="Rand 1", canonical_slug=f"{p.slug}/m-rand-1", enabled=True, available=True)
        m2 = DiscoveredModel(provider_id=p.id, provider_model_id="m-rand-2", display_name="Rand 2", canonical_slug=f"{p.slug}/m-rand-2", enabled=True, available=True)
        m3 = DiscoveredModel(provider_id=p.id, provider_model_id="m-rand-3", display_name="Rand 3", canonical_slug=f"{p.slug}/m-rand-3", enabled=True, available=True)
        db.add_all([m1, m2, m3])
        await db.flush()

        # Profile B (SubProfile with randomize_candidates = True and randomize_keys = True)
        prof_b = RoutingProfile(
            name=f"ProfB-{run_id}",
            slug=f"prof-b-{run_id}",
            strategy="priority",
            randomize_candidates=True,
            randomize_keys=True,
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(prof_b)
        await db.flush()

        # Candidate with credential_id = None -> tests randomize_keys
        b_c1 = RoutingCandidate(profile_id=prof_b.id, candidate_type="model", provider_id=p.id, credential_id=None, model_id=m1.id, priority_order=0, is_active=True)
        b_c2 = RoutingCandidate(profile_id=prof_b.id, candidate_type="model", provider_id=p.id, credential_id=None, model_id=m2.id, priority_order=1, is_active=True)
        db.add_all([b_c1, b_c2])
        await db.flush()

        # Profile A (Parent Profile with randomize_candidates = True)
        prof_a = RoutingProfile(
            name=f"ProfA-{run_id}",
            slug=f"prof-a-{run_id}",
            strategy="priority",
            randomize_candidates=True,
            randomize_keys=False,
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(prof_a)
        await db.flush()

        a_c1 = RoutingCandidate(profile_id=prof_a.id, candidate_type="profile", target_profile_id=prof_b.id, priority_order=0, is_active=True)
        a_c2 = RoutingCandidate(profile_id=prof_a.id, candidate_type="model", provider_id=p.id, credential_id=creds[0].id, model_id=m3.id, priority_order=1, is_active=True)
        db.add_all([a_c1, a_c2])

        # Circular dependency test setup: add Profile A as candidate inside Profile B!
        b_c_circular = RoutingCandidate(profile_id=prof_b.id, candidate_type="profile", target_profile_id=prof_a.id, priority_order=2, is_active=True)
        db.add(b_c_circular)
        await db.commit()

        # =========================================================================
        # TEST 3: Randomization verification in nested profile & key randomization
        # =========================================================================
        attempted_models = set()
        attempted_keys = set()

        async def mock_recording_chat(*args, **kwargs):
            mid = kwargs.get("model_id")
            api_k = kwargs.get("api_key")
            attempted_models.add(mid)
            attempted_keys.add(api_k)
            return ChatCompletionResponse(
                model=mid,
                choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=f"Resp from {mid} key {api_k}"))],
                usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            )

        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_recording_chat):
            # Run 25 calls through route/prof-a
            first_models = set()
            for _ in range(25):
                req = ChatCompletionRequest(
                    model=f"route/{prof_a.slug}",
                    messages=[ChatMessage(role="user", content="Test rand")],
                )
                res = await RoutingEngine.route_chat_completions(db, req, None)
                first_models.add(res.model)

            # Because randomize_candidates is True in prof_a (between prof_b and m3)
            # AND randomize_candidates is True in prof_b (between m1 and m2),
            # over 25 runs we should see multiple different models selected as the winner!
            assert len(first_models) > 1, f"Expected multiple models to win due to randomization, got: {first_models}"

            # And because randomize_keys is True in prof_b across 3 keys,
            # we should see multiple different keys used!
            assert len(attempted_keys) > 1, f"Expected multiple keys to be used due to key randomization, got: {attempted_keys}"

        # =========================================================================
        # TEST 4: Circular Reference Prevention (prof_a -> prof_b -> prof_a)
        # =========================================================================
        # Force m1, m2 to fail in prof_b. prof_b then attempts b_c_circular (prof_a).
        # prof_a should be detected in active_visited and SKIPPED, preventing loop!
        # Then prof_b fails, prof_a recovers to a_c2 (m3).
        prof_a.randomize_candidates = False
        prof_b.randomize_candidates = False
        await db.commit()
        for c in creds:
            circuit_breaker.reset(c.id)
        async def mock_circular_fallback(*args, **kwargs):
            mid = kwargs.get("model_id")
            if mid in ("m-rand-1", "m-rand-2"):
                raise normalize_upstream_error(status_code=429, response_body={"error": {"message": f"Rate limited {mid}"}})
            return ChatCompletionResponse(
                model=mid,
                choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=f"Handled by {mid}"))],
                usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            )

        test_req_id_circ = f"req_circ_{run_id}"
        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_circular_fallback):
            req = ChatCompletionRequest(
                model=f"route/{prof_a.slug}",
                messages=[ChatMessage(role="user", content="Test circular")],
            )
            res = await RoutingEngine.route_chat_completions(db, req, None, request_id=test_req_id_circ)
            assert res.choices[0].message.content == "Handled by m-rand-3"

        # Verify attempts log contains CIRCULAR_DEPENDENCY skipped attempt!
        async with AsyncSessionLocal() as vdb:
            log_item = (await vdb.execute(
                select(RequestLog).options(selectinload(RequestLog.attempts)).where(RequestLog.request_id == test_req_id_circ)
            )).scalar_one_or_none()
            assert log_item is not None
            circular_attempts = [a for a in log_item.attempts if a.error_category == "CIRCULAR_DEPENDENCY"]
            assert len(circular_attempts) >= 1, "Circular dependency should be recorded as SKIPPED"
            assert circular_attempts[0].status == "SKIPPED"


@pytest.mark.asyncio
async def test_nested_fallback_streaming_recovery():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name=f"p-str-{run_id}",
            slug=f"p-str-{run_id}",
            base_url="https://api.str.test/v1",
            adapter_type="generic_openai",
            enabled=True,
        )
        db.add(p)
        await db.flush()

        c1 = ProviderCredential(
            provider_id=p.id,
            name=f"c-str-{run_id}",
            encrypted_api_key=encrypt_secret("key-str"),
            key_fingerprint=f"fp-str-{run_id}",
            masked_key="sk-***s",
            enabled=True,
        )
        db.add(c1)
        await db.flush()

        m_sub_fail = DiscoveredModel(provider_id=p.id, provider_model_id="m-str-fail", display_name="Str Fail", canonical_slug=f"{p.slug}/m-str-fail", enabled=True, available=True)
        m_parent_ok = DiscoveredModel(provider_id=p.id, provider_model_id="m-str-ok", display_name="Str OK", canonical_slug=f"{p.slug}/m-str-ok", enabled=True, available=True)
        db.add_all([m_sub_fail, m_parent_ok])
        await db.flush()

        # Nested SubProfile (fails)
        sub_p = RoutingProfile(
            name=f"StreamSub-{run_id}",
            slug=f"stream-sub-{run_id}",
            strategy="priority",
            randomize_candidates=True,
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(sub_p)
        await db.flush()
        db.add(RoutingCandidate(profile_id=sub_p.id, candidate_type="model", provider_id=p.id, credential_id=c1.id, model_id=m_sub_fail.id, priority_order=0, is_active=True))
        await db.flush()

        # Parent Profile
        parent_p = RoutingProfile(
            name=f"StreamParent-{run_id}",
            slug=f"stream-parent-{run_id}",
            strategy="priority",
            randomize_candidates=False,
            enabled=True,
            fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"],
        )
        db.add(parent_p)
        await db.flush()
        db.add(RoutingCandidate(profile_id=parent_p.id, candidate_type="profile", target_profile_id=sub_p.id, priority_order=0, is_active=True))
        db.add(RoutingCandidate(profile_id=parent_p.id, candidate_type="model", provider_id=p.id, credential_id=c1.id, model_id=m_parent_ok.id, priority_order=1, is_active=True))
        await db.commit()

        async def mock_stream_recovery(*args, **kwargs):
            mid = kwargs.get("model_id")
            if mid == "m-str-fail":
                raise normalize_upstream_error(status_code=503, response_body={"error": {"message": "Service unavailable"}})
            yield 'data: {"id":"cmpl-str","choices":[{"delta":{"content":"Stream recovered successfully!"}}]}\n\n'
            yield 'data: [DONE]\n\n'

        test_req_id = f"req_str_{run_id}"
        with patch("app.adapters.openai.GenericOpenAIAdapter.stream_chat", side_effect=mock_stream_recovery):
            req = ChatCompletionRequest(
                model=f"route/{parent_p.slug}",
                messages=[ChatMessage(role="user", content="Test stream")],
                stream=True,
            )
            chunks = []
            async for chunk in RoutingEngine.route_stream_chat(db, req, None, request_id=test_req_id):
                chunks.append(chunk)

            full_res = "".join(chunks)
            assert "Stream recovered successfully!" in full_res

        # Verify DB log
        async with AsyncSessionLocal() as vdb:
            log_item = (await vdb.execute(
                select(RequestLog).options(selectinload(RequestLog.attempts)).where(RequestLog.request_id == test_req_id)
            )).scalar_one_or_none()
            assert log_item is not None
            assert log_item.status == "FALLBACK_SUCCESS"


@pytest.mark.asyncio
async def test_nested_fallback_three_levels_deep():
    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(name=f"p3-{run_id}", slug=f"p3-{run_id}", base_url="https://api.p3.test/v1", adapter_type="generic_openai", enabled=True)
        db.add(p)
        await db.flush()

        creds = []
        for i in range(1, 4):
            c = ProviderCredential(provider_id=p.id, name=f"c3-{i}-{run_id}", encrypted_api_key=encrypt_secret(f"k3-{i}"), key_fingerprint=f"fp-3-{i}-{run_id}", masked_key=f"sk-***{i}", priority=1, enabled=True)
            db.add(c)
            creds.append(c)
        await db.flush()

        m_grandchild_fail = DiscoveredModel(provider_id=p.id, provider_model_id="m-gc-fail", display_name="GC Fail", canonical_slug=f"{p.slug}/m-gc-fail", enabled=True, available=True)
        m_grandchild_ok = DiscoveredModel(provider_id=p.id, provider_model_id="m-gc-ok", display_name="GC OK", canonical_slug=f"{p.slug}/m-gc-ok", enabled=True, available=True)
        m_child_backup = DiscoveredModel(provider_id=p.id, provider_model_id="m-ch-backup", display_name="Child Backup", canonical_slug=f"{p.slug}/m-ch-backup", enabled=True, available=True)
        m_root_backup = DiscoveredModel(provider_id=p.id, provider_model_id="m-root-backup", display_name="Root Backup", canonical_slug=f"{p.slug}/m-root-backup", enabled=True, available=True)
        db.add_all([m_grandchild_fail, m_grandchild_ok, m_child_backup, m_root_backup])
        await db.flush()

        # Level 3: Grandchild profile
        gc_prof = RoutingProfile(name=f"Grandchild-{run_id}", slug=f"gc-{run_id}", strategy="priority", enabled=True, fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"])
        db.add(gc_prof)
        await db.flush()
        db.add(RoutingCandidate(profile_id=gc_prof.id, candidate_type="model", provider_id=p.id, credential_id=creds[0].id, model_id=m_grandchild_fail.id, priority_order=0, is_active=True))
        db.add(RoutingCandidate(profile_id=gc_prof.id, candidate_type="model", provider_id=p.id, credential_id=creds[1].id, model_id=m_grandchild_ok.id, priority_order=1, is_active=True))
        await db.flush()

        # Level 2: Child profile
        child_prof = RoutingProfile(name=f"Child-{run_id}", slug=f"child-{run_id}", strategy="priority", enabled=True, fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"])
        db.add(child_prof)
        await db.flush()
        db.add(RoutingCandidate(profile_id=child_prof.id, candidate_type="profile", target_profile_id=gc_prof.id, priority_order=0, is_active=True))
        db.add(RoutingCandidate(profile_id=child_prof.id, candidate_type="model", provider_id=p.id, credential_id=creds[2].id, model_id=m_child_backup.id, priority_order=1, is_active=True))
        await db.flush()

        # Level 1: Root parent profile
        root_prof = RoutingProfile(name=f"Root-{run_id}", slug=f"root-{run_id}", strategy="priority", enabled=True, fallback_conditions=["RATE_LIMIT", "TIMEOUT", "NETWORK_ERROR", "UPSTREAM_5XX", "MODEL_NOT_FOUND"])
        db.add(root_prof)
        await db.flush()
        db.add(RoutingCandidate(profile_id=root_prof.id, candidate_type="profile", target_profile_id=child_prof.id, priority_order=0, is_active=True))
        db.add(RoutingCandidate(profile_id=root_prof.id, candidate_type="model", provider_id=p.id, credential_id=creds[0].id, model_id=m_root_backup.id, priority_order=1, is_active=True))
        await db.commit()

        # Sub-test 3A: Root -> Child -> Grandchild cand 1 fails -> Grandchild cand 2 succeeds!
        async def mock_3_levels_deep(*args, **kwargs):
            mid = kwargs.get("model_id")
            if mid == "m-gc-fail":
                raise normalize_upstream_error(status_code=429, response_body={"error": {"message": f"Rate limit on {mid}"}})
            return ChatCompletionResponse(
                model=mid,
                choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=f"Success from 3-deep: {mid}"))],
                usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            )

        req_id_3a = f"req_3a_{run_id}"
        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_3_levels_deep):
            req = ChatCompletionRequest(
                model=f"route/{root_prof.slug}",
                messages=[ChatMessage(role="user", content="Test 3 levels")],
            )
            res = await RoutingEngine.route_chat_completions(db, req, None, request_id=req_id_3a)
            assert res.choices[0].message.content == "Success from 3-deep: m-gc-ok"

        # Sub-test 3B: Grandchild fails completely -> Child falls back to Child Backup!
        async def mock_gc_fails_child_recovers(*args, **kwargs):
            mid = kwargs.get("model_id")
            if mid in ("m-gc-fail", "m-gc-ok"):
                raise normalize_upstream_error(status_code=500, response_body={"error": {"message": f"Dead {mid}"}})
            return ChatCompletionResponse(
                model=mid,
                choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=f"Recovered at child: {mid}"))],
                usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            )

        req_id_3b = f"req_3b_{run_id}"
        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_gc_fails_child_recovers):
            req = ChatCompletionRequest(
                model=f"route/{root_prof.slug}",
                messages=[ChatMessage(role="user", content="Test gc fails")],
            )
            res = await RoutingEngine.route_chat_completions(db, req, None, request_id=req_id_3b)
            assert res.choices[0].message.content == "Recovered at child: m-ch-backup"

        # Sub-test 3C: Grandchild AND Child fail completely -> Root falls back to Root Backup!
        async def mock_all_nested_fail(*args, **kwargs):
            mid = kwargs.get("model_id")
            if mid in ("m-gc-fail", "m-gc-ok", "m-ch-backup"):
                raise normalize_upstream_error(status_code=502, response_body={"error": {"message": f"Dead {mid}"}})
            return ChatCompletionResponse(
                model=mid,
                choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content=f"Recovered at root: {mid}"))],
                usage=UsageInfo(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            )

        req_id_3c = f"req_3c_{run_id}"
        with patch("app.adapters.openai.GenericOpenAIAdapter.chat_completions", side_effect=mock_all_nested_fail):
            req = ChatCompletionRequest(
                model=f"route/{root_prof.slug}",
                messages=[ChatMessage(role="user", content="Test root recovers")],
            )
            res = await RoutingEngine.route_chat_completions(db, req, None, request_id=req_id_3c)
            assert res.choices[0].message.content == "Recovered at root: m-root-backup"
