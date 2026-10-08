from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from app.routing.cache_affinity import PrefixAnalyzer, resolve_prompt_cache_key
from app.routing.engine import RoutingEngine
from app.schemas.chat import ChatCompletionRequest
from app.core.errors import RouterException


def request(**kwargs):
    return ChatCompletionRequest(model="route/test", messages=[{"role": "system", "content": "stable"}, {"role": "user", "content": "hello"}], **kwargs)


def target():
    provider = NS(id=1, enabled=True, adapter_type="generic_openai", base_url="https://synthetic.invalid", configuration={}, adapter_configuration={}, extra_headers={}, updated_at=None)
    model = NS(id=2, provider_id=1, provider=provider, provider_model_id="synthetic", canonical_slug="synthetic/model", enabled=True, available=True, temperature=0.7, reasoning_effort="high", updated_at=None)
    cred = NS(id=3, enabled=True, provider=provider, metadata_json={}, updated_at=None)
    candidate = NS(id=4, priority_order=0, is_active=True, candidate_type="model", target_profile_id=None, provider=provider, model=model, credential_id=3, credential=cred, credential_group=None, temperature=0.5, thinking_effort="medium", updated_at=None)
    profile = NS(id=5, enabled=True, candidates=[candidate], temperature=0.3, thinking_effort="low", strategy="priority", randomize_candidates=False, updated_at=None)
    return profile, candidate, cred, model


def test_canonical_multimodal_prefix():
    a = [{"role": "system", "content": [{"type": "text", "text": "hello"}]}]
    b = [{"role": "system", "content": [{"text": "hello", "type": "text"}]}]
    assert PrefixAnalyzer.generate_prompt_cache_key(a) == PrefixAnalyzer.generate_prompt_cache_key(b)


def test_explicit_cache_key_preserved():
    assert resolve_prompt_cache_key({"prompt_cache_key": "  client-key  "}) == "  client-key  "


@pytest.mark.parametrize("params", [{"reasoning_effort": "none"}, {"reasoning": {"effort": "low", "max_tokens": 333}}, {"thinking": {"type": "enabled", "budget_tokens": 333}}])
def test_explicit_parameters_override_profile(params):
    original = request(temperature=0, **params)
    result = RoutingEngine._apply_model_defaults(original, eff_thinking="high", candidate_temperature=0.8, profile_temperature=0.6)
    assert result.temperature == 0
    assert result.reasoning_effort == original.reasoning_effort
    assert result.reasoning == original.reasoning
    assert result.thinking == original.thinking


@pytest.mark.asyncio
async def test_permissions_before_resolution(monkeypatch):
    resolver = AsyncMock()
    monkeypatch.setattr("app.routing.engine.RoutingService.get_profile_by_slug", resolver)
    key = NS(permissions=["direct"], allowed_routes=["*"])
    with pytest.raises(RouterException):
        await RoutingEngine.prepare_effective_request(None, request(), key)
    resolver.assert_not_called()


@pytest.mark.asyncio
async def test_effective_context_and_revision(monkeypatch):
    profile, candidate, cred, model = target()
    monkeypatch.setattr("app.routing.engine.RoutingService.get_profile_by_slug", AsyncMock(return_value=profile))
    effective, context = await RoutingEngine.prepare_effective_request(None, request(), None)
    assert effective.model == "route/test"
    assert effective.temperature == 0.5
    assert effective.reasoning_effort == "medium"
    assert context["resolved_model_id"] == "synthetic"
    assert context["provider_identity"] == "generic_openai"
    candidate.provider.name = "Renamed display label"
    _, renamed = await RoutingEngine.prepare_effective_request(None, request(), None)
    assert renamed["provider_identity"] == context["provider_identity"]
    assert not context["skip_response_cache"]
    model.temperature = 0.9
    _, changed = await RoutingEngine.prepare_effective_request(None, request(), None)
    assert changed["config_fingerprint"] != context["config_fingerprint"]
    candidate.credential_id = None
    _, ambiguous = await RoutingEngine.prepare_effective_request(None, request(), None)
    assert ambiguous["skip_response_cache"]


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["fusion/test", "judge/test", "smart/test"])
async def test_dynamic_route_skips_cache(model):
    effective, context = await RoutingEngine.prepare_effective_request(None, request().model_copy(update={"model": model}), None)
    assert context["skip_response_cache"]


@pytest.mark.asyncio
async def test_direct_context(monkeypatch):
    _, _, cred, model = target()
    monkeypatch.setattr(RoutingEngine, "_get_candidate_credentials_for_model", AsyncMock(return_value=[(cred, model)]))
    effective, context = await RoutingEngine.prepare_effective_request(None, request().model_copy(update={"model": "synthetic/model"}), None)
    assert effective.temperature == 0.7
    assert effective.reasoning_effort == "high"
    assert not context["skip_response_cache"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("fail_first", [False, True])
async def test_priority_group_affinity_and_parameters(monkeypatch, stream, explicit, fail_first):
    profile, candidate, cred, model = target()
    profile.strategy = "cache-optimized"
    profile.name = "Synthetic"
    profile.timeout_seconds = 60
    profile.fallback_conditions = None
    profile.retry_count = 0
    candidate.credential_id = None
    candidate.credential_group = "synthetic"
    model.display_name = "Synthetic"
    model.input_price_per_1m = model.output_price_per_1m = 0
    provider = candidate.provider
    provider.name = "Synthetic"
    creds = [NS(id=i, provider_id=provider.id, rpm_limit=None, tpm_limit=None, max_concurrency=None, name=f"credential-{i}", provider=provider, enabled=True,
                encrypted_api_key="synthetic-not-a-real-secret", proxy=None,
                metadata_json={}) for i in (101, 102)]
    db = NS(execute=AsyncMock(return_value=NS(scalars=lambda: NS(all=lambda: creds))))
    seen = []

    def record(kwargs):
        seen.append((kwargs["api_key"], kwargs["request"]))
        if fail_first and len(seen) % 2 == 1:
            from app.core.errors import ErrorCategory
            raise RouterException("synthetic failure", ErrorCategory.UPSTREAM_5XX)

    async def chat(**kwargs):
        record(kwargs)
        from app.schemas.chat import ChatCompletionResponse
        return ChatCompletionResponse(model="synthetic", choices=[])

    async def chunks(**kwargs):
        record(kwargs)
        yield 'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
        yield 'data: [DONE]\n\n'

    monkeypatch.setattr("app.routing.engine.RoutingService.get_profile_by_slug", AsyncMock(return_value=profile))
    monkeypatch.setattr("app.routing.engine.decrypt_secret", lambda value: value)
    monkeypatch.setattr("app.routing.engine.get_adapter", lambda _: NS(chat_completions=chat, stream_chat=chunks))
    monkeypatch.setattr("app.routing.engine.LogService.record_request_log", AsyncMock())
    monkeypatch.setattr("app.routing.engine.circuit_breaker.is_available", lambda *args: (True, ""))
    monkeypatch.setattr("app.routing.engine.circuit_breaker.record_success", lambda *args: None)
    monkeypatch.setattr("app.routing.engine.circuit_breaker.record_failure", lambda *args: None)
    for cred_obj in creds:
        cred_obj.encrypted_api_key = str(cred_obj.id)
    for _ in range(8):
        req = request(**({"temperature": 0, "thinking": {"type": "enabled", "budget_tokens": 333}} if explicit else {}))
        if stream:
            result = [chunk async for chunk in RoutingEngine._handle_priority_stream(db, req, req.model, None, "test", 0, record_log=False)]
            assert result[-1] == "data: [DONE]\n\n"
        else:
            await RoutingEngine._handle_priority_route(db, req, req.model, None, "test", 0, record_log=False)
    if fail_first:
        assert len(seen) == 16
        assert len({key for key, _ in seen[::2]}) == 1
        assert seen[0][0] != seen[1][0]
    else:
        assert len({key for key, _ in seen}) == 1
    for _, sent in seen:
        assert sent.temperature == (0 if explicit else 0.5)
        assert sent.thinking == ({"type": "enabled", "budget_tokens": 333} if explicit else {"type": "enabled", "budget_tokens": 4096})


def test_nested_default_precedence_keeps_client_intent():
    omitted = RoutingEngine._apply_model_defaults(request(), eff_thinking="low", candidate_temperature=0.6)
    child = RoutingEngine._apply_model_defaults(omitted, eff_thinking="high", candidate_temperature=0.8)
    assert child.temperature == 0.8
    assert child.reasoning_effort == "high"
    original = request(temperature=0, reasoning_effort="none")
    parent = RoutingEngine._apply_model_defaults(original, eff_thinking="low", candidate_temperature=0.6)
    child = RoutingEngine._apply_model_defaults(parent, eff_thinking="high", candidate_temperature=0.8)
    assert child.temperature == 0
    assert child.reasoning_effort == "none"


@pytest.mark.asyncio
async def test_unknown_direct_skips_without_error(monkeypatch):
    monkeypatch.setattr(RoutingEngine, "_get_candidate_credentials_for_model", AsyncMock(return_value=[]))
    _, context = await RoutingEngine.prepare_effective_request(None, request().model_copy(update={"model": "unknown"}))
    assert context == {"skip_response_cache": True, "supports_vision": None, "config_fingerprint": ""}
