"""Native quota regressions: synthetic credentials and MockTransport only.

Primary schemas: openai/codex rust-v0.160.0 codex-backend-openapi-models;
xai-org/grok-build 2bdd1d6a extensions/billing.rs (including its fixtures).
"""
import asyncio
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.modules.base import ModuleExecutionContext
from modules.codex_cli.handler import CodexCliAdapter
from modules.grok_builder_cli.handler import GrokBuilderCliAdapter

ADAPTERS = [CodexCliAdapter, GrokBuilderCliAdapter]
CODEX_USAGE = "https://chatgpt.com/backend-api/wham/usage"
GROK_BILLING = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"


def context(**credentials):
    return ModuleExecutionContext(
        credentials={"auto_detect_local": False, "access_token": "synthetic-access", **credentials},
        proxy_url="http://synthetic-proxy.invalid:8080", timeout=7,
    )


def wire(monkeypatch, adapter, respond):
    requests = []

    def transport(request):
        requests.append(request)
        return respond(request)

    def client(ctx, **kwargs):
        assert ctx.proxy_url == "http://synthetic-proxy.invalid:8080" and ctx.timeout == 7
        return httpx.AsyncClient(transport=httpx.MockTransport(transport), timeout=ctx.timeout)

    monkeypatch.setattr(adapter, "create_http_client", client)
    monkeypatch.setattr(adapter, "_find_local_auth_file", lambda: pytest.fail("Local auth discovery forbidden"))
    return requests


def window(percent=25):
    return {"used_percent": percent, "limit_window_seconds": 18000,
            "reset_after_seconds": 600, "reset_at": 1791450000}


@pytest.mark.asyncio
async def test_codex_primary_secondary_additional_and_credits(monkeypatch):
    adapter = CodexCliAdapter()
    payload = {"plan_type": "plus", "rate_limit": {"primary_window": window(), "secondary_window": window(100)},
               "additional_rate_limits": [{"limit_name": "Code review", "metered_feature": "codex_review",
                                            "rate_limit": {"primary_window": window(0)}}],
               "credits": {"has_credits": True, "unlimited": False, "balance": "12.5"}}
    requests = wire(monkeypatch, adapter, lambda request: httpx.Response(200, json=payload))
    result = await adapter.get_subscription_limits(context(account_id="synthetic-account"))
    assert result.status == "ok" and result.plan == "plus" and result.checked_at
    assert [(x.name, x.used_percent, x.remaining_percent) for x in result.limits[:3]] == [
        ("Codex primary", 25, 75), ("Codex secondary", 100, 0), ("Code review primary", 0, 100)]
    assert result.limits[0].window_seconds == 18000
    assert result.limits[0].reset_at == "2026-10-08T09:00:00+00:00"
    assert result.limits[3].remaining == 12.5 and result.limits[3].unit == "credits"
    assert [(r.method, str(r.url)) for r in requests] == [
        ("GET", CODEX_USAGE), ("GET", CODEX_USAGE.replace("/usage", "/rate-limit-reset-credits"))]
    assert result.reset_credits_available is None
    assert requests[0].headers["chatgpt-account-id"] == "synthetic-account"
    assert requests[0].headers["authorization"] == "Bearer synthetic-access"
    assert requests[0].headers["accept"] == "application/json"


@pytest.mark.asyncio
async def test_grok_new_shared_pool_preferred_over_legacy(monkeypatch):
    adapter = GrokBuilderCliAdapter()
    payload = {"config": {"creditUsagePercent": 42.5,
                          "currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY", "end": "2026-10-12T00:00:00Z"},
                          "monthlyLimit": {"val": 9999}, "used": {"val": 9999},
                          "onDemandCap": {"val": 5000}, "onDemandUsed": {"val": 300},
                          "prepaidBalance": {"val": 1250}, "isUnifiedBillingUser": True}}
    requests = wire(monkeypatch, adapter, lambda request: httpx.Response(200, json=payload))
    auth = json.dumps({"synthetic": {"key": "synthetic-pasted", "user_id": "synthetic-user"}})
    result = await adapter.get_subscription_limits(context(auth_json=auth))
    assert result.status == "ok" and result.plan is None and result.checked_at
    included, demand, prepaid = result.limits
    assert included.used_percent == 42.5 and included.remaining_percent == 57.5
    assert included.limit is None and included.used is None and included.reset_at == "2026-10-12T00:00:00Z"
    assert (demand.limit, demand.used, demand.remaining, demand.unit) == (5000, 300, 4700, "USD cents")
    assert demand.reset_at is None  # shared-pool reset does not establish the on-demand reset
    assert prepaid.remaining == 1250 and prepaid.unit == "USD cents"
    assert len(requests) == 1 and requests[0].method == "GET" and str(requests[0].url) == GROK_BILLING
    assert requests[0].headers["authorization"] == "Bearer synthetic-pasted"
    assert requests[0].headers["x-userid"] == "synthetic-user"
    assert requests[0].headers["x-xai-token-auth"] == "xai-grok-cli"


@pytest.mark.asyncio
async def test_grok_legacy_zero_cents_and_direct_identity(monkeypatch):
    adapter = GrokBuilderCliAdapter()
    requests = wire(monkeypatch, adapter, lambda request: httpx.Response(200, json={"config": {
        "monthlyLimit": {"val": 2000}, "used": {}, "onDemandCap": {},
        "billingPeriodEnd": "2026-11-01T00:00:00Z"}}))
    result = await adapter.get_subscription_limits(context(user_id="synthetic-direct"))
    assert result.status == "ok"
    assert (result.limits[0].limit, result.limits[0].used, result.limits[0].remaining) == (2000, 0, 2000)
    assert result.limits[1].limit == 0 and result.limits[1].used is None and result.limits[1].remaining is None
    assert requests[0].headers["x-userid"] == "synthetic-direct"


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type", ADAPTERS)
@pytest.mark.parametrize("status", [401, 403, 429, 500, 404, 405, 501])
async def test_upstream_failures_are_controlled(monkeypatch, adapter_type, status):
    adapter = adapter_type()
    wire(monkeypatch, adapter, lambda request: httpx.Response(status, text="SECRET upstream raw body"))
    result = await adapter.get_subscription_limits(context())
    assert result.status == ("unsupported" if status in (404, 405, 501) else "unavailable")
    assert not result.limits and str(status) in result.message and "SECRET" not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type", ADAPTERS)
@pytest.mark.parametrize("kind", ["missing", "refresh_rejected", "transport", "invalid_json"])
async def test_auth_transport_and_json_failures(monkeypatch, adapter_type, kind):
    adapter = adapter_type()

    def respond(request):
        if kind == "transport":
            raise httpx.ReadTimeout("SECRET transport details", request=request)
        if kind == "invalid_json":
            return httpx.Response(200, text="SECRET not JSON")
        assert request.method == "POST" and str(request.url).endswith("/token")
        return httpx.Response(401, text="SECRET rejected token")

    requests = wire(monkeypatch, adapter, respond)
    ctx = context()
    if kind == "missing":
        ctx.credentials.pop("access_token")
    if kind == "refresh_rejected":
        ctx.credentials["refresh_token"] = "synthetic-refresh"
    result = await adapter.get_subscription_limits(ctx)
    assert result.status == "unavailable" and not result.limits and "SECRET" not in result.model_dump_json()
    if kind == "missing":
        assert requests == []
    if kind == "refresh_rejected":
        assert len(requests) == 1  # no usage request with stale access token


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type,payload", [
    (CodexCliAdapter, {}), (CodexCliAdapter, []),
    (CodexCliAdapter, {"plan_type": "pro", "credits": {"unlimited": True}}),
    (CodexCliAdapter, {"rate_limit": {"primary_window": {}}}),
    (GrokBuilderCliAdapter, {"config": None}), (GrokBuilderCliAdapter, {"config": {}}),
    (GrokBuilderCliAdapter, {"config": {"history": [{"used": {"val": 3}}]}}),
])
async def test_absent_quotas_never_mean_zero_or_unlimited(monkeypatch, adapter_type, payload):
    adapter = adapter_type()
    wire(monkeypatch, adapter, lambda request: httpx.Response(200, json=payload))
    result = await adapter.get_subscription_limits(context())
    assert result.status == "unavailable" and result.limits == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [-1, True, "12", float("nan"), float("inf")])
@pytest.mark.parametrize("adapter_type", ADAPTERS)
async def test_invalid_percentages_fail_closed(monkeypatch, adapter_type, bad):
    adapter = adapter_type()
    payload = ({"rate_limit": {"primary_window": window(bad)}} if adapter_type is CodexCliAdapter
               else {"config": {"creditUsagePercent": bad}})
    wire(monkeypatch, adapter, lambda request: httpx.Response(200, content=json.dumps(payload)))
    result = await adapter.get_subscription_limits(context())
    assert result.status == "unavailable" and not result.limits


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type", ADAPTERS)
async def test_refresh_reuse_and_profile_isolation(monkeypatch, adapter_type):
    adapter = adapter_type()
    persisted = []

    async def persist(fields):
        persisted.append(fields)

    def respond(request):
        if request.method == "POST":
            token = parse_qs(request.content.decode())["refresh_token"][0]
            return httpx.Response(200, json={"access_token": token + "-access", "refresh_token": token + "-rotated", "expires_in": 3600})
        token = request.headers["authorization"]
        used = 20 if "first" in token else 80
        payload = ({"rate_limit": {"primary_window": window(used)}} if adapter_type is CodexCliAdapter
                   else {"config": {"creditUsagePercent": used}})
        return httpx.Response(200, json=payload)

    requests = wire(monkeypatch, adapter, respond)
    first, second = context(refresh_token="synthetic-first"), context(refresh_token="synthetic-second")
    first.extra_config = {"credential_id": 101, "persist_credentials": persist}
    second.extra_config = {"credential_id": 102, "persist_credentials": persist}
    results = await asyncio.gather(adapter.get_subscription_limits(first), adapter.get_subscription_limits(second))
    assert [r.limits[0].used_percent for r in results] == [20, 80]
    assert len(persisted) == 2 and len(requests) == (6 if adapter_type is CodexCliAdapter else 4)
    assert (await adapter.get_subscription_limits(first)).limits[0].used_percent == 20
    assert len(persisted) == 2 and len(requests) == (8 if adapter_type is CodexCliAdapter else 5)
    assert all(r.method == "GET" or str(r.url).endswith("/token") for r in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type,payload", [
    (CodexCliAdapter, {"rate_limit": []}),
    (CodexCliAdapter, {"additional_rate_limits": [{"limit_name": True}]}),
    (CodexCliAdapter, {"credits": {"balance": "nan"}}),
    (CodexCliAdapter, {"credits": {"balance": "-2"}}),
    (CodexCliAdapter, {"rate_limit": {"primary_window": {**window(), "reset_at": True}}}),
    (CodexCliAdapter, {"rate_limit": {"primary_window": {**window(), "limit_window_seconds": -1}}}),
    (GrokBuilderCliAdapter, {"config": []}),
    (GrokBuilderCliAdapter, {"config": {"prepaidBalance": {"val": -1}}}),
    (GrokBuilderCliAdapter, {"config": {"monthlyLimit": {"val": True}}}),
    (GrokBuilderCliAdapter, {"config": {"onDemandUsed": {"val": "300"}}}),
    (GrokBuilderCliAdapter, {"config": {"creditUsagePercent": 50, "currentPeriod": {"end": "SECRET invalid date"}}}),
])
async def test_malformed_shapes_balances_and_resets(monkeypatch, adapter_type, payload):
    adapter = adapter_type()
    wire(monkeypatch, adapter, lambda request: httpx.Response(200, json=payload))
    result = await adapter.get_subscription_limits(context())
    assert result.status == "unavailable" and not result.limits and "SECRET" not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("adapter_type", ADAPTERS)
async def test_overage_is_not_hidden_and_missing_values_stay_unknown(monkeypatch, adapter_type):
    adapter = adapter_type()
    payload = ({"rate_limit": {"primary_window": {"used_percent": 105}}, "credits": {"balance": "0"}}
               if adapter_type is CodexCliAdapter else {"config": {"creditUsagePercent": 105}})
    wire(monkeypatch, adapter, lambda request: httpx.Response(200, json=payload))
    result = await adapter.get_subscription_limits(context())
    assert result.status == "ok" and result.limits[0].used_percent == 105 and result.limits[0].remaining_percent == 0
    assert result.limits[0].limit is None and result.limits[0].window_seconds is None and result.limits[0].reset_at is None
    if adapter_type is CodexCliAdapter:
        assert result.limits[1].remaining == 0
