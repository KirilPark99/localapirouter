import pytest
from app.core.crypto import encrypt_secret, decrypt_secret, mask_secret, compute_fingerprint
from app.core.errors import ErrorCategory, RouterException, normalize_upstream_error
from app.core.circuit_breaker import CircuitBreaker, CredentialStatus

def test_encryption_decryption():
    secret = "test-secret-value-1234567890abcdef"
    encrypted = encrypt_secret(secret)
    assert encrypted != secret
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret

def test_secret_masking():
    assert mask_secret("AIzaSy1234567890ABCDEF") == "AIzaSy••••••••••CDEF"
    assert mask_secret("sk-ant-api03-123456789") == "sk-ant-••••6789"
    assert mask_secret("sk-router-abcdef123456") == "sk-router-••••3456"

def test_secret_fingerprint():
    key1 = "sk-test-12345"
    key2 = "sk-test-12345"
    key3 = "sk-test-67890"
    fp1 = compute_fingerprint(key1)
    fp2 = compute_fingerprint(key2)
    fp3 = compute_fingerprint(key3)
    assert fp1 == fp2
    assert fp1 != fp3
    assert len(fp1) == 64  # SHA-256 hex length

def test_error_normalization_and_fallback_eligibility():
    # 429 Rate limit -> eligible for fallback
    err_429 = normalize_upstream_error(status_code=429, response_body={"error": {"message": "Rate limit exceeded"}})
    assert err_429.category == ErrorCategory.RATE_LIMIT
    assert err_429.category.is_fallback_eligible is True
    assert err_429.status_code == 429

    # 500 Upstream error -> eligible for fallback
    err_500 = normalize_upstream_error(status_code=500, response_body="Internal Server Error")
    assert err_500.category == ErrorCategory.UPSTREAM_5XX
    assert err_500.category.is_fallback_eligible is True

    # 400 Bad request -> NOT eligible for fallback (should return error directly to client!)
    err_400 = normalize_upstream_error(status_code=400, response_body={"error": {"message": "Invalid prompt formatting"}})
    assert err_400.category == ErrorCategory.INVALID_REQUEST
    assert err_400.category.is_fallback_eligible is False
    assert err_400.status_code == 400

    # 401 Auth error -> not fallback eligible, invalid key
    err_401 = normalize_upstream_error(status_code=401, response_body={"error": {"message": "Incorrect API key"}})
    assert err_401.category == ErrorCategory.AUTH_ERROR
    assert err_401.category.is_fallback_eligible is False

def test_circuit_breaker():
    cb = CircuitBreaker(failure_threshold=3, default_cooldown_seconds=30.0)
    cred_id = 999

    # Initially healthy
    avail, _ = cb.is_available(cred_id)
    assert avail is True

    # Record 2 failures -> degraded, still available
    cb.record_failure(cred_id, ErrorCategory.UPSTREAM_5XX, error_message="Server 500")
    cb.record_failure(cred_id, ErrorCategory.UPSTREAM_5XX, error_message="Server 502")
    avail, _ = cb.is_available(cred_id)
    assert avail is True
    assert cb.get_status(cred_id)["status"] == CredentialStatus.DEGRADED

    # 3rd failure trips cooldown
    cb.record_failure(cred_id, ErrorCategory.UPSTREAM_5XX, error_message="Server 503")
    avail, reason = cb.is_available(cred_id)
    assert avail is False
    assert "cooldown" in reason.lower()
    assert cb.get_status(cred_id)["status"] == CredentialStatus.COOLDOWN

    # Manual reset
    cb.reset(cred_id)
    avail, _ = cb.is_available(cred_id)
    assert avail is True
    assert cb.get_status(cred_id)["status"] == CredentialStatus.HEALTHY

@pytest.mark.asyncio
async def test_detailed_analytics_continuous_buckets():
    from app.core.database import AsyncSessionLocal
    from app.services.log_service import LogService

    async with AsyncSessionLocal() as db:
        # Test 24h default granularity (hourly, 24 continuous buckets)
        res_24h = await LogService.get_detailed_analytics(db, period="24h")
        assert res_24h.granularity == "hour"
        assert len(res_24h.timeline) == 24
        for item in res_24h.timeline:
            assert hasattr(item, "timestamp")
            assert hasattr(item, "requests")
            assert hasattr(item, "errors")
            assert hasattr(item, "fallbacks")
            assert hasattr(item, "tokens")
            assert hasattr(item, "cost")
            assert hasattr(item, "avg_latency_ms")

        # Test explicit daily granularity
        res_7d_day = await LogService.get_detailed_analytics(db, period="7d", granularity="day")
        assert res_7d_day.granularity == "day"
        assert len(res_7d_day.timeline) >= 7

def test_model_ratings_service_lookup():
    from app.services.model_ratings_service import ModelRatingsService

    # Check Gemini lookup
    gemini_rating = ModelRatingsService.find_rating("gemini-2.5-flash", "google/gemini-2.5-flash", "Gemini 2.5 Flash")
    assert gemini_rating is not None
    assert gemini_rating["eval_provider"] == "Artificial Analysis"
    assert "intelligence_index" in gemini_rating
    assert isinstance(gemini_rating["intelligence_index"], (int, float))
    assert gemini_rating["intelligence_index"] > 0

    # Check GPT-4o lookup
    gpt_rating = ModelRatingsService.find_rating("gpt-4o", "openai/gpt-4o", "GPT-4o")
    assert gpt_rating is not None
    assert gpt_rating["intelligence_index"] > 0

@pytest.mark.asyncio
async def test_model_limits_service():
    from app.core.database import AsyncSessionLocal
    from app.services.model_limits_service import ModelLimitsService
    from app.models.entities import DiscoveredModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(DiscoveredModel).limit(1))
        model = res.scalar_one_or_none()
        if model:
            limits = await ModelLimitsService.get_model_limits(db, model.id)
            assert limits.model_id == model.id
            assert limits.canonical_slug == model.canonical_slug
            assert limits.source in ("direct_api", "credential_config", "database")


def test_reasoning_effort_normalization_and_adaptation():
    from app.schemas.chat import ChatCompletionRequest, ChatMessage
    from app.adapters.openai import GenericOpenAIAdapter
    from app.adapters.anthropic import AnthropicAdapter

    # 1. Standard OpenAI reasoning_effort parameter
    req1 = ChatCompletionRequest(
        model="o3-mini",
        messages=[ChatMessage(role="user", content="Hi")],
        reasoning_effort="high",
        temperature=0.7,
    )
    assert req1.get_effective_reasoning_effort() == "high"
    assert req1.get_effective_thinking_budget() == 16384

    # OpenAI adapter should set reasoning_effort and remove temperature for o-series
    openai_adapter = GenericOpenAIAdapter()
    p1 = openai_adapter._prepare_payload("o3-mini", req1, "https://api.openai.com/v1")
    assert p1.get("reasoning_effort") == "high"
    assert "thinking" not in p1
    assert "temperature" not in p1  # popped for o-series

    # 2. OpenRouter reasoning object parameter
    req2 = ChatCompletionRequest(
        model="openai/o3-mini",
        messages=[ChatMessage(role="user", content="Hi")],
        reasoning={"effort": "medium"},
    )
    assert req2.get_effective_reasoning_effort() == "medium"
    assert req2.get_effective_thinking_budget() == 4096

    p2 = openai_adapter._prepare_payload("openai/o3-mini", req2, "https://openrouter.ai/api/v1")
    assert p2.get("reasoning") == {"effort": "medium"}

    # 3. Anthropic cross-protocol adaptation from reasoning_effort to thinking budget
    anthropic_adapter = AnthropicAdapter()
    p3 = anthropic_adapter._prepare_payload("claude-3-7-sonnet-20250219", req1)
    assert p3.get("thinking") == {"type": "enabled", "budget_tokens": 16384}
    assert "reasoning_effort" not in p3
    assert p3.get("max_tokens") > 16384
    assert "temperature" not in p3  # popped for thinking

    # 4. Off / None reasoning effort
    req4 = ChatCompletionRequest(
        model="o3-mini",
        messages=[ChatMessage(role="user", content="Hi")],
        reasoning_effort="none",
    )
    assert req4.get_effective_reasoning_effort() == "none"
    assert req4.get_effective_thinking_budget() == 0

    p4_anthropic = anthropic_adapter._prepare_payload("claude-3-7-sonnet-20250219", req4)
    assert "thinking" not in p4_anthropic

@pytest.mark.asyncio
async def test_routing_profile_randomize_options():
    import uuid
    from app.core.database import AsyncSessionLocal
    from app.schemas.entities import RoutingProfileCreate, RoutingProfileUpdate
    from app.services.routing_service import RoutingService

    slug = f"test-randomize-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        create_data = RoutingProfileCreate(
            name="Test Randomize",
            slug=slug,
            randomize_candidates=True,
            randomize_keys=False,
            candidates=[],
        )
        created = await RoutingService.create_profile(db, create_data)
        assert created.randomize_candidates is True
        assert created.randomize_keys is False

        # Update to flip options
        update_data = RoutingProfileUpdate(
            randomize_candidates=False,
            randomize_keys=True,
        )
        updated = await RoutingService.update_profile(db, created.id, update_data)
        assert updated.randomize_candidates is False
        assert updated.randomize_keys is True

        # Update both True
        update_data2 = RoutingProfileUpdate(
            randomize_candidates=True,
            randomize_keys=True,
        )
        updated2 = await RoutingService.update_profile(db, created.id, update_data2)
        assert updated2.randomize_candidates is True
        assert updated2.randomize_keys is True

        # Clean up
        await RoutingService.delete_profile(db, created.id)

def test_randomize_logic():
    import random
    candidates = ["cand_1", "cand_2", "cand_3", "cand_4", "cand_5"]
    profile_with_random = type("Profile", (), {"randomize_candidates": True})()
    profile_without_random = type("Profile", (), {"randomize_candidates": False})()

    # Deterministic when False
    cand_copy = list(candidates)
    if getattr(profile_without_random, "randomize_candidates", False):
        random.shuffle(cand_copy)
    assert cand_copy == candidates

    # Shuffled across runs when True
    shuffled_results = set()
    for _ in range(20):
        c = list(candidates)
        if getattr(profile_with_random, "randomize_candidates", False) and len(c) > 1:
            random.shuffle(c)
        shuffled_results.add(tuple(c))
    assert len(shuffled_results) > 1

@pytest.mark.asyncio
async def test_direct_routing_default_key_randomization():
    import uuid
    from app.core.database import AsyncSessionLocal
    from app.models.entities import Provider, ProviderCredential, DiscoveredModel
    from app.core.crypto import encrypt_secret
    from app.routing.engine import RoutingEngine

    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(name=f"p-dir-{run_id}", slug=f"p-dir-{run_id}", base_url="https://api.dir.test", adapter_type="generic_openai", enabled=True)
        db.add(p)
        await db.flush()

        for i in range(1, 5):
            c = ProviderCredential(
                provider_id=p.id,
                name=f"c-dir-{i}-{run_id}",
                encrypted_api_key=encrypt_secret(f"key-{i}"),
                key_fingerprint=f"fp-dir-{i}-{run_id}",
                masked_key=f"sk-***{i}",
                priority=1,
                weight=1,
                enabled=True,
            )
            db.add(c)
        await db.flush()

        m = DiscoveredModel(provider_id=p.id, provider_model_id="dir-model", display_name="Dir Model", canonical_slug=f"{p.slug}/dir-model", enabled=True, available=True)
        db.add(m)
        await db.commit()

        first_keys = set()
        for _ in range(20):
            cands = await RoutingEngine._get_candidate_credentials_for_model(db, f"{p.slug}/dir-model")
            assert len(cands) == 4
            first_keys.add(cands[0][0].name)

        assert len(first_keys) > 1, f"Expected first key in direct route to vary due to default randomization, got: {first_keys}"


@pytest.mark.asyncio
async def test_model_discovery_new_models_tracking():
    import uuid
    from unittest.mock import AsyncMock, patch
    from app.core.database import AsyncSessionLocal
    from app.models.entities import Provider, ProviderCredential
    from app.core.crypto import encrypt_secret
    from app.services.model_discovery_service import ModelDiscoveryService
    from app.adapters.base import DiscoveredModelData

    run_id = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        p = Provider(
            name=f"p-disc-{run_id}",
            slug=f"p-disc-{run_id}",
            base_url="https://api.disc.test",
            adapter_type="generic_openai",
            enabled=True,
        )
        db.add(p)
        await db.flush()

        cred = ProviderCredential(
            provider_id=p.id,
            name=f"c-disc-{run_id}",
            encrypted_api_key=encrypt_secret("test-key"),
            key_fingerprint=f"fp-disc-{run_id}",
            masked_key="sk-***1",
            priority=1,
            weight=1,
            enabled=True,
        )
        db.add(cred)
        await db.commit()

        # Mock adapter list_models to return 2 models first
        mock_models_round1 = [
            DiscoveredModelData(provider_model_id="model-alpha", display_name="Model Alpha"),
            DiscoveredModelData(provider_model_id="model-beta", display_name="Model Beta"),
        ]

        with patch("app.services.model_discovery_service.get_adapter") as mock_get_adapter:
            mock_adapter = AsyncMock()
            mock_adapter.list_models = AsyncMock(return_value=mock_models_round1)
            mock_get_adapter.return_value = mock_adapter

            new_models_1 = []
            models_read = await ModelDiscoveryService.fetch_models_for_credential(
                db, cred.id, new_models_out=new_models_1
            )
            assert len(models_read) == 2
            assert len(new_models_1) == 2
            assert f"{p.slug}/model-alpha" in new_models_1
            assert f"{p.slug}/model-beta" in new_models_1
            assert models_read[0].created_at is not None

            # Round 2: same models returned -> 0 new models
            new_models_2 = []
            models_read_2 = await ModelDiscoveryService.fetch_models_for_credential(
                db, cred.id, new_models_out=new_models_2
            )
            assert len(models_read_2) == 2
            assert len(new_models_2) == 0

            # Round 3: 1 brand new model added upstream
            mock_models_round3 = mock_models_round1 + [
                DiscoveredModelData(provider_model_id="model-gamma", display_name="Model Gamma")
            ]
            mock_adapter.list_models = AsyncMock(return_value=mock_models_round3)

            summary = await ModelDiscoveryService.fetch_models_for_provider(db, p.id)
            assert summary["new_models_count"] == 1
            assert summary["new_models"] == [f"{p.slug}/model-gamma"]





