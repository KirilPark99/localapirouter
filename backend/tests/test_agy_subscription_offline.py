"""Synthetic-only Cloud Code regressions; use the guarded scratch runner.

Bootstrap fields: Google gemini-cli packages/core/src/code_assist/types.ts.
Quota semantics: antigravity.google/docs/cli/statusline (remaining_fraction,
reset_time). The private fetchAvailableModels camelCase wire schema is not
published there; primary implementation robinebers/openusage commit d067b1f
uses quotaInfo.remainingFraction/resetTime. These fixtures exercise that shape,
not a claim of live-provider compatibility.
"""
import json
from unittest.mock import Mock

import httpx
import pytest

from app.core.errors import ErrorCategory, RouterException
from app.modules.base import ModuleExecutionContext
from app.schemas.chat import ChatCompletionRequest
from modules.agy_cli import handler


pytestmark = pytest.mark.asyncio
RESET = "2030-01-02T03:04:05Z"


def context(**credentials):
    return ModuleExecutionContext(credentials={"auto_detect_local": False, "access_token": "synthetic-access", **credentials})


@pytest.fixture
def adapter(monkeypatch):
    result = handler.AgyCliAdapter()
    monkeypatch.setattr(result, "_find_local_token_file", Mock(side_effect=AssertionError("local tokens forbidden")))
    monkeypatch.setattr(result, "create_http_client", Mock(side_effect=AssertionError("unmocked HTTP forbidden")))
    monkeypatch.setattr(handler, "AGY_CLIENT_ID", "synthetic-client")
    monkeypatch.setattr(handler, "AGY_CLIENT_SECRET", "synthetic-secret")
    return result


def offline(monkeypatch, adapter, transport):
    monkeypatch.setattr(adapter, "create_http_client", lambda *a, **kw:
                        httpx.AsyncClient(transport=httpx.MockTransport(transport), trust_env=False))


def native_transport(models, seen, bootstrap=None, status=200):
    def transport(request):
        seen.append(request)
        assert request.headers["Authorization"] == "Bearer synthetic-access"
        assert request.method == "POST"
        if request.url.path.endswith(":loadCodeAssist"):
            return httpx.Response(200, json=bootstrap if bootstrap is not None else {
                "cloudaicompanionProject": "native-project", "currentTier": {"id": "native-tier", "name": "Native tier"}})
        assert request.url.path.endswith(":fetchAvailableModels")
        return httpx.Response(status, json={"models": models})
    return transport


async def test_native_limits_and_project(monkeypatch, adapter):
    seen = []
    models = {"gemini-native": {"quotaInfo": {"remainingFraction": 0.25, "resetTime": RESET}},
              "empty": {"quotaInfo": {"remainingFraction": 0}},
              "full": {"quotaInfo": {"remainingFraction": 1}},
              "unknown": {}, "reset-only": {"quotaInfo": {"resetTime": RESET}}}
    offline(monkeypatch, adapter, native_transport(models, seen))
    ctx = context()
    original = ctx.model_dump()
    result = await adapter.get_subscription_limits(ctx)
    assert result.status == "ok" and result.plan == "Native tier"
    assert result.checked_at
    limits = {limit.model: limit for limit in result.limits}
    assert set(limits) == {"gemini-native", "empty", "full", "reset-only"}
    assert limits["gemini-native"].remaining_percent == 25
    assert limits["gemini-native"].used_percent == 75
    assert limits["gemini-native"].reset_at == RESET
    assert limits["empty"].remaining_percent == 0
    assert limits["full"].remaining_percent == 100
    assert limits["reset-only"].remaining_percent is None
    assert limits["reset-only"].used_percent is None
    for limit in result.limits:
        assert limit.limit is limit.used is limit.remaining is limit.unit is limit.window_seconds is None
    assert json.loads(seen[-1].content) == {"project": "native-project"}
    assert ctx.model_dump() == original


@pytest.mark.parametrize("fraction", [None, True, False, "0.5", -0.1, 1.1, float("nan"), float("inf"), {}, []])
async def test_unknown_quota_never_becomes_zero(monkeypatch, adapter, fraction):
    # MockTransport accepts JSON text with non-finite floats for this boundary test.
    def transport(req):
        if req.url.path.endswith(":loadCodeAssist"):
            return httpx.Response(200, json={"cloudaicompanionProject": "native-project"})
        return httpx.Response(200, text=json.dumps({"models": {"m": {"quotaInfo": {"remainingFraction": fraction}}}}))
    offline(monkeypatch, adapter, transport)
    result = await adapter.get_subscription_limits(context())
    assert result.status == "unavailable" and result.limits == []


@pytest.mark.parametrize("models", [{}, {"m": {}}, {"m": {"quotaInfo": None}}, {"m": {"quotaInfo": {"resetTime": "garbage"}}}, []])
async def test_missing_native_quota_is_unavailable(monkeypatch, adapter, models):
    offline(monkeypatch, adapter, native_transport(models, []))
    result = await adapter.get_subscription_limits(context())
    assert result.status == "unavailable" and not result.limits


@pytest.mark.parametrize("status", [401, 403, 429, 503])
async def test_quota_http_errors(monkeypatch, adapter, status):
    offline(monkeypatch, adapter, native_transport({}, [], status=status))
    result = await adapter.get_subscription_limits(context())
    assert result.status == "unavailable" and not result.limits
    assert str(status) in result.message and result.plan == "Native tier"


@pytest.mark.parametrize("kind", ["timeout", "malformed", "error"])
async def test_quota_failures_are_safe(monkeypatch, adapter, kind):
    def transport(req):
        if req.url.path.endswith(":loadCodeAssist"):
            return httpx.Response(200, json={"cloudaicompanionProject": "native-project"})
        if kind == "timeout":
            raise httpx.ReadTimeout("synthetic-sensitive-token")
        if kind == "malformed":
            return httpx.Response(200, text="synthetic-sensitive-token")
        return httpx.Response(200, json={"error": {"message": "synthetic-sensitive-token"}})
    offline(monkeypatch, adapter, transport)
    result = await adapter.get_subscription_limits(context())
    assert result.status == "unavailable" and not result.limits
    assert "synthetic-sensitive-token" not in result.message


async def test_explicit_project_and_paid_tier(monkeypatch, adapter):
    seen = []
    offline(monkeypatch, adapter, native_transport({"m": {"quotaInfo": {"remainingFraction": 0.5}}}, seen,
        bootstrap={"cloudaicompanionProject": "other-project", "currentTier": {"name": "Free"}, "paidTier": {"id": "paid-native"}}))
    result = await adapter.get_subscription_limits(context(project_id="explicit-project"))
    assert result.plan == "paid-native"
    assert json.loads(seen[0].content)["cloudaicompanionProject"] == "explicit-project"
    assert json.loads(seen[-1].content)["project"] == "explicit-project"


@pytest.mark.parametrize("bootstrap", [{}, {"currentTier": {"id": "native"}}, {"error": {"message": "blocked"}}])
async def test_no_fabricated_project_or_onboarding(monkeypatch, adapter, bootstrap):
    seen = []
    offline(monkeypatch, adapter, native_transport({}, seen, bootstrap=bootstrap))
    result = await adapter.get_subscription_limits(context())
    assert result.status == "unavailable" and not result.limits
    assert len(seen) == 1
    assert "aicode-consumers" not in seen[0].content.decode()


async def test_validation_does_not_accept_userinfo_alone(monkeypatch, adapter):
    seen = []
    def transport(req):
        seen.append(req)
        # Legacy code accepted userinfo 200 despite denied Cloud Code access.
        return httpx.Response(200, json={"email": "synthetic@example.invalid"}) if req.method == "GET" else httpx.Response(403)
    offline(monkeypatch, adapter, transport)
    success, message, count = await adapter.validate_credentials(context())
    assert not success and count == 0 and "403" in message
    assert len(seen) == 1 and seen[0].method == "POST"


async def test_project_resolution_reaches_generation(monkeypatch, adapter):
    seen = []
    def transport(req):
        seen.append(req)
        if req.url.path.endswith(":loadCodeAssist"):
            return httpx.Response(200, json={"cloudaicompanionProject": "native-project"})
        assert json.loads(req.content)["project"] == "native-project"
        return httpx.Response(200, text='data: {"response":{"candidates":[{"content":{"parts":[{"text":"ok"}]},"finishReason":"STOP"}]}}\n\n')
    offline(monkeypatch, adapter, transport)
    result = await adapter.chat_completions(ChatCompletionRequest(model="m", messages=[{"role": "user", "content": "hi"}]), context())
    assert result.choices[0].message.content == "ok" and len(seen) == 2


async def test_valid_expiry_avoids_refresh(adapter):
    for expiry in [4102444800, "4102444800", "2100-01-01T00:00:00Z"]:
        assert await adapter._get_valid_access_token(context(refresh_token="synthetic-refresh", expiry=expiry)) == ("synthetic-access", "")
    adapter.create_http_client.assert_not_called()


@pytest.mark.parametrize("expiry", [0, "1970-01-01T00:00:00Z", "bad", "nan", "2030-01-01T00:00:00"])
async def test_expired_or_invalid_token_not_sent(adapter, expiry):
    with pytest.raises(ValueError):
        await adapter._get_valid_access_token(context(expiry=expiry))
    adapter.create_http_client.assert_not_called()


async def test_refresh_cache_identity_and_string_lifetime(monkeypatch, adapter):
    seen = []
    def transport(req):
        seen.append(req)
        assert str(req.url) == handler.GOOGLE_OAUTH_TOKEN_URL
        return httpx.Response(200, json={"access_token": f"synthetic-refreshed-{len(seen)}", "expires_in": "3600"})
    offline(monkeypatch, adapter, transport)
    first = context(refresh_token="synthetic-refresh", expiry=0)
    first.extra_config["credential_id"] = 1
    second = first.model_copy(deep=True)
    second.extra_config["credential_id"] = 2
    assert (await adapter._get_valid_access_token(first))[0] == "synthetic-refreshed-1"
    assert (await adapter._get_valid_access_token(first))[0] == "synthetic-refreshed-1"
    assert (await adapter._get_valid_access_token(second))[0] == "synthetic-refreshed-2"
    first.credentials["access_token"] = "synthetic-rotated"
    assert (await adapter._get_valid_access_token(first))[0] == "synthetic-refreshed-3"
    assert len(seen) == 3


@pytest.mark.parametrize("response", [httpx.Response(400, json={"error": "synthetic-sensitive-token"}),
    httpx.Response(200, json={"access_token": "synthetic-new", "expires_in": "bad"}),
    httpx.Response(200, json={"access_token": "synthetic-new", "expires_in": -1}),
    httpx.Response(200, json={"access_token": "synthetic-new", "expires_in": True}),
    httpx.Response(200, json={"access_token": {"bad": "token"}})])
async def test_refresh_errors_not_silently_expired_fallback(monkeypatch, adapter, response):
    offline(monkeypatch, adapter, lambda req: response)
    with pytest.raises(RouterException) as caught:
        await adapter._get_valid_access_token(context(refresh_token="synthetic-refresh", expiry=0))
    assert "synthetic-sensitive-token" not in str(caught.value)
    if response.status_code == 400:
        assert caught.value.category == ErrorCategory.AUTH_ERROR
    assert not adapter._token_cache


async def test_refresh_transport_error_and_no_invented_lifetime(monkeypatch, adapter):
    def timeout(req):
        raise httpx.ReadTimeout("synthetic timeout", request=req)
    offline(monkeypatch, adapter, timeout)
    with pytest.raises(RouterException) as caught:
        await adapter._get_valid_access_token(context(refresh_token="synthetic-refresh", expiry=0))
    assert caught.value.category == ErrorCategory.TIMEOUT and not adapter._token_cache
    offline(monkeypatch, adapter, lambda req: httpx.Response(200, json={"access_token": "synthetic-new"}))
    assert (await adapter._get_valid_access_token(context(refresh_token="synthetic-refresh", expiry=0)))[0] == "synthetic-new"
    assert not adapter._token_cache


async def test_explicit_identity_never_falls_back_local(adapter):
    for credentials in [{"auth_json": "malformed"}, {"auth_json": "[]"}, {"project_id": "explicit"}]:
        ctx = ModuleExecutionContext(credentials=credentials)
        if "auth_json" in credentials:
            with pytest.raises(ValueError):
                adapter._resolve_raw_tokens(ctx)
        else:
            assert adapter._resolve_raw_tokens(ctx) == {}
    assert adapter._resolve_raw_tokens(ModuleExecutionContext(extra_config={"credential_id": 42})) == {}
    direct = adapter._resolve_raw_tokens(context(auth_json=json.dumps({"access_token": "other-account", "refresh_token": "other-refresh", "expiry": 0})))
    assert direct["access_token"] == "synthetic-access" and direct["refresh_token"] == "" and direct["expiry"] is None
    adapter._find_local_token_file.assert_not_called()


async def test_developer_instruction_and_multiline_sse(monkeypatch, adapter):
    request = ChatCompletionRequest(model="m", messages=[{"role": "developer", "content": "rules"}, {"role": "user", "content": "hello"}])
    envelope = adapter._build_cloudcode_envelope(request, "explicit", "m")
    assert "System Instructions:\nrules" in envelope["request"]["contents"][0]["parts"][0]["text"]
    assert len(envelope["request"]["contents"]) == 1
    offline(monkeypatch, adapter, lambda req: httpx.Response(200, text=': heartbeat\r\nevent: message\r\ndata: {"response":\r\ndata: {"candidates":[{"content":{"parts":[{"text":"ok"}]},"finishReason":"STOP"}]}}\r\n\r\ndata: [DONE]\r\n\r\n'))
    result = await adapter.chat_completions(request, context(project_id="explicit"))
    assert result.choices[0].message.content == "ok"
