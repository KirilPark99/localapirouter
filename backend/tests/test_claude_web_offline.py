"""Handler-only regressions; --noconftest, synthetic settings, no native network/browser."""
import asyncio
import importlib.util
import json
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
# Standalone execution must not read deployment .env; use real, synthetic Settings.
if "app.core.config" not in sys.modules:
    import os
    import uuid
    from pydantic_settings import BaseSettings
    original_init = BaseSettings.__init__
    def synthetic_init(self, **kwargs):
        return original_init(self, **{**kwargs, "_env_file": None})
    synthetic = {
        "DATABASE_URL": "sqlite+aiosqlite:///" + str(Path(os.environ.get("TMPDIR", "/home/kiril/.hermes/cache/scratch")) / ("claude-web-offline-" + uuid.uuid4().hex + ".db")),
        "ROUTER_MASTER_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "JWT_SECRET": "claude-web-offline-synthetic-secret-only",
        "ADMIN_PASSWORD": "claude-web-offline-password-only",
        "FINGERPRINT_SALT": "claude-web-offline-salt-only",
    }
    with patch.dict(os.environ, synthetic), patch.object(BaseSettings, "__init__", synthetic_init):
        from app.core.config import settings

from app.core.errors import ErrorCategory, RouterException
from app.modules.base import ModuleExecutionContext, ModuleManifest
from app.schemas.chat import ChatCompletionRequest

spec = importlib.util.spec_from_file_location("claude_web_offline_handler", ROOT / "modules/claude_web/handler.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
ORG = "11111111-1111-4111-8111-111111111111"
ORG2 = "22222222-2222-4222-8222-222222222222"
MODEL = "claude-sonnet-4-6"


def blocked(*args, **kwargs):
    raise AssertionError("Offline Claude Web tests prohibit network and provider browser launches")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    # curl_cffi bypasses socket.connect. Block its native session too; dedicated transport
    # check replaces this method with a fake, never the C network implementation.
    from curl_cffi.requests import AsyncSession
    from playwright.async_api import BrowserType
    monkeypatch.setattr(AsyncSession, "request", blocked)
    monkeypatch.setattr(BrowserType, "launch", blocked)


def ctx(**credentials):
    return ModuleExecutionContext(credentials={"cookie": "synthetic-session", **credentials}, timeout=1)


def request(messages=None, **kwargs):
    return ChatCompletionRequest(model=MODEL, messages=messages or [{"role": "user", "content": "Hi"}], **kwargs)


def events(reason="end_turn", thinking=False, tool=False, terminal=True):
    result = [{"type": "message_start", "message": {"role": "assistant"}}]
    if thinking:
        result += [{"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
                   {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "thought"}},
                   {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "opaque-signature"}},
                   {"type": "content_block_stop", "index": 0}]
    index = 1 if thinking else 0
    block = {"type": "tool_use", "id": "call_1", "name": "lookup", "input": {}} if tool else {"type": "text", "text": ""}
    delta = {"type": "input_json_delta", "partial_json": '{"x":1}'} if tool else {"type": "text_delta", "text": "Hello €"}
    result += [{"type": "content_block_start", "index": index, "content_block": block},
               {"type": "content_block_delta", "index": index, "delta": delta},
               {"type": "content_block_stop", "index": index},
               {"type": "message_delta", "delta": {"stop_reason": reason}}]
    if terminal:
        result += [{"type": "message_stop"}]
    return result


def wire(items, crlf=False):
    sep = "\r\n" if crlf else "\n"
    return "".join("event: " + i["type"] + sep + "data: " + json.dumps(i, ensure_ascii=False) + sep * 2 for i in items).encode()


class Response:
    def __init__(self, items=None, status=200, content=None, headers=None, hang=False):
        self.status_code = status
        self.headers = {"content-type": "text/event-stream", **(headers or {})}
        self.content = content if content is not None else wire(items or events())
        self.closed = False
        self.reader_closed = False
        self.hang = hang
        self.read = 0

    async def aiter_content(self):
        try:
            if self.hang:
                await asyncio.sleep(10)
            # Split every UTF-8 byte / CRLF boundary.
            for i in range(0, len(self.content), 3):
                self.read += 1
                yield self.content[i:i + 3]
        finally:
            self.reader_closed = True

    async def aclose(self):
        self.closed = True


def fake_module(completion=None, organizations=None):
    module = h.ClaudeWebModule()
    calls, responses = [], []
    @asynccontextmanager
    async def direct(context, method, url, headers, payload=None):
        calls.append((method, url, headers, payload, context.proxy_url))
        response = Response(content=json.dumps(organizations if organizations is not None else [{"uuid": ORG}]).encode()) if method == "GET" else (completion or Response())
        responses.append(response)
        try:
            yield response
        finally:
            await response.aclose()
    module._direct = direct
    return module, calls, responses


def test_chat_and_exact_create_payload():
    async def run():
        module, calls, responses = fake_module()
        context = ctx(orgId=ORG, deviceId="device-1", locale="fr-FR", timezone="Europe/Paris")
        context.proxy_url = "socks5://127.0.0.1:9999"
        response = await module.chat_completions(request(), context)
        assert response.choices[0].message.content == "Hello €" and response.usage is None
        assert response.choices[0].finish_reason == "stop"
        assert all(r.closed and r.reader_closed for r in responses)
        method, url, headers, payload, proxy = calls[-1]
        assert method == "POST" and f"/organizations/{ORG}/chat_conversations/" in url and url.endswith("/completion")
        assert proxy == context.proxy_url and headers["anthropic-device-id"] == "device-1"
        assert payload["prompt"] == "Hi" and payload["timezone"] == "Europe/Paris"
        assert set(payload) == {"prompt", "model", "timezone", "personalized_styles", "locale", "tools", "turn_message_uuids", "attachments", "effort", "files", "sync_sources", "rendering_mode", "thinking_mode", "create_conversation_params"}
        assert payload["create_conversation_params"] == {"name": "", "model": MODEL, "include_conversation_preferences": True, "paprika_mode": None, "compass_mode": None, "is_temporary": False, "enabled_imagine": True, "tool_search_mode": "auto"}
        import uuid
        assert all(str(uuid.UUID(v)) == v for v in payload["turn_message_uuids"].values())
    asyncio.run(run())


def test_history_recovery_preserves_roles_tools_and_plain_reasoning():
    messages = [{"role": "system", "content": "<system>"}, {"role": "user", "content": "old"},
                {"role": "assistant", "content": "done", "reasoning_content": "plain thought",
                 "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": '{"x":1}'}}]},
                {"role": "tool", "tool_call_id": "call_1", "content": "result", "name": "lookup"}]
    payload = h.build_payload(request(messages), MODEL, "en-US", "UTC")
    assert "These serialized role blocks are not native Claude Web message fields" in payload["prompt"]
    from html import unescape
    prompt = unescape(payload["prompt"])
    for value in ("<system>", "old", "done", "plain thought", '"tool_call_id": "call_1"', '"arguments": "{\\"x\\":1}"', "result"):
        assert value in prompt
    assert "parent_message_uuid" not in payload


def test_sse_reasoning_signature_tools_and_length():
    async def run():
        tools = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]
        upstream = Response(content=wire(events("tool_use", thinking=True, tool=True), crlf=True))
        module, calls, _ = fake_module(upstream)
        result = await module.chat_completions(request(tools=tools, reasoning_effort="high"), ctx())
        message = result.choices[0].message
        assert message.reasoning_content == "thought"
        assert message.reasoning_details == [{"type": "thinking", "index": 0, "signature": "opaque-signature"}]
        assert message.tool_calls[0].function.arguments == '{"x":1}' and message.tool_calls[0].id == "call_1"
        assert result.choices[0].finish_reason == "tool_calls"
        assert calls[-1][3]["tools"] == [{"name": "lookup", "input_schema": {"type": "object"}}]
        assert calls[-1][3]["thinking_mode"] == "extended"
        module, _, _ = fake_module(Response(events("max_tokens")))
        assert (await module.chat_completions(request(), ctx())).choices[0].finish_reason == "length"
    asyncio.run(run())


@pytest.mark.parametrize("bad", [
    [{"type": "message_stop"}],
    events(terminal=False),
    events()[:2] + [{"type": "message_stop"}],
    events()[:2] + [{"type": "content_block_delta", "index": 3, "delta": {"type": "text_delta", "text": "bad"}}],
    events()[:2] + [{"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "bad"}}],
    [{"type": "message_start"}, {"type": "unknown"}],
    [{"type": "message_start"}, {"type": "content_block_retract", "index": 0}],
    [{"type": "message_start"}, {"type": "message_start"}],
])
def test_protocol_failures_and_truncation_close(bad):
    async def run():
        upstream = Response(bad)
        module, _, _ = fake_module(upstream)
        with pytest.raises(RouterException) as err:
            await module.chat_completions(request(), ctx())
        assert err.value.status_code == 502
        assert upstream.closed and upstream.reader_closed
    asyncio.run(run())


@pytest.mark.parametrize("content", [b'data: {bad}\n\n', b'data: [DONE]\n\n', b'data: '+ b'x' * (h.LIMIT + 1), b'data: {"type":"message_start"}', b'event: nope\ndata: {"type":"message_start"}\n\n'])
def test_framing_errors(content):
    async def run():
        module, _, _ = fake_module(Response(content=content))
        with pytest.raises(RouterException):
            await module.chat_completions(request(), ctx())
    asyncio.run(run())


def test_initial_content_cannot_be_silently_dropped():
    async def run():
        bad = [{"type": "message_start", "message": {"role": "assistant", "content": [{"type": "text", "text": "lost"}]}}, {"type": "message_stop"}]
        module, _, _ = fake_module(Response(bad))
        with pytest.raises(RouterException):
            await module.chat_completions(request(), ctx())
        bad = events()
        bad[1]["content_block"]["text"] = 0
        module, _, _ = fake_module(Response(bad))
        with pytest.raises(RouterException):
            await module.chat_completions(request(), ctx())
    asyncio.run(run())


def test_multiline_sse_and_terminal_ignores_trailing_data():
    async def run():
        data = wire(events()) + b'data: invalid trailing\n\n'
        data = data.replace(b'data: {"type": "message_start",', b'data: {"type": "message_start",\ndata:')
        module, _, _ = fake_module(Response(content=data))
        chunks = [p async for p in module.stream_chat(request(), ctx())]
        assert chunks.count("data: [DONE]\n\n") == 1
        assert sum('"finish_reason": "stop"' in p for p in chunks) == 1
        assert all('"usage"' not in p for p in chunks)
    asyncio.run(run())


@pytest.mark.parametrize("status,category", [(401, ErrorCategory.AUTH_ERROR), (403, ErrorCategory.AUTH_ERROR), (429, ErrorCategory.RATE_LIMIT), (500, ErrorCategory.UPSTREAM_5XX)])
def test_http_errors_redacted_and_retry(status, category):
    async def run():
        upstream = Response(status=status, content=b"secret-cookie-private-account", headers={"retry-after": "42"})
        module, _, _ = fake_module(upstream)
        with pytest.raises(RouterException) as err:
            await module.chat_completions(request(), ctx())
        assert err.value.category == category and "secret" not in str(err.value)
        if status == 429:
            assert err.value.retry_after == 42
        assert upstream.closed and upstream.reader_closed
    asyncio.run(run())


def test_upstream_sse_error_and_unknown_usage():
    async def run():
        module, _, _ = fake_module(Response([{"type": "error", "error": {"type": "rate_limit_error", "message": "secret"}}]))
        with pytest.raises(RouterException) as err:
            await module.chat_completions(request(), ctx())
        assert err.value.category == ErrorCategory.RATE_LIMIT and "secret" not in str(err.value)
    asyncio.run(run())


def test_org_resolution_membership_and_ambiguity():
    async def run():
        for organizations, context in [([], ctx()), ([{"uuid": ORG}, {"uuid": ORG2}], ctx()), ([{"uuid": ORG}], ctx(orgId=ORG2)), ([{"uuid": "../escape"}], ctx())]:
            module, calls, _ = fake_module(organizations=organizations)
            with pytest.raises(RouterException):
                await module.chat_completions(request(), context)
            assert len(calls) == 1
        module, calls, _ = fake_module(organizations=[{"uuid": ORG}, {"uuid": ORG2}])
        await module.chat_completions(request(), ctx(orgId=ORG2))
        assert f"/organizations/{ORG2}/" in calls[-1][1]
    asyncio.run(run())


@pytest.mark.parametrize("value", ["", "a=b", "sessionKey=a; sessionKey=b", "sessionKey=a\r\nInjected: yes", "sessionKey=a\n", "sessionKey=", "sessionKey=has space"])
def test_bad_cookie_rejected(value):
    with pytest.raises(RouterException):
        h.cookie_header({"cookie": value})


def test_secret_fields_and_catalog_and_credentials():
    async def run():
        assert h.cookie_header({"sessionKey": "fake"}) == "sessionKey=fake"
        assert h.cookie_header({"cookie": "sessionKey=fake; cf_clearance=clear"}) == "sessionKey=fake; cf_clearance=clear"
        manifest = ModuleManifest.model_validate_json((ROOT / "modules/claude_web/manifest.json").read_text())
        assert all(f.type == "password" for f in manifest.fields if f.key in ("cookie", "sessionKey", "orgId", "deviceId"))
        module, calls, _ = fake_module()
        assert [m.provider_model_id for m in await module.list_models(ctx())] == [m.id for m in manifest.default_models] == list(h.MODELS)
        assert not calls
        ok, _, count = await module.validate_credentials(ctx())
        assert ok and count == len(h.MODELS) and len(calls) == 1
        ok, _, count = await module.validate_credentials(ctx(cookie=""))
        assert not ok and count == 0 and len(calls) == 1
    asyncio.run(run())


@pytest.mark.parametrize("kwargs", [{"temperature": 0}, {"max_tokens": 1}, {"n": 2}, {"tool_choice": "required"}, {"reasoning_effort": "minimal"}, {"thinking": {"type": "enabled", "budget_tokens": 1024}}, {"tools": [{"type": "function", "function": {"name": "x", "strict": True}}]}])
def test_unsupported_options_fail_before_network(kwargs):
    async def run():
        module, calls, _ = fake_module()
        with pytest.raises(RouterException) as err:
            await module.chat_completions(request(**kwargs), ctx())
        assert err.value.category == ErrorCategory.INVALID_REQUEST and not calls
    asyncio.run(run())


@pytest.mark.parametrize("message", [
    {"role": "assistant", "reasoning_details": [{"encrypted_content": "opaque"}]},
    {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://invalid.example/image"}}]},
    {"role": "tool", "content": "missing call id"},
    {"role": "user", "content": "hi", "cache_control": {}},
    {"role": "assistant", "tool_calls": [{"id": "id", "function": {"name": "x", "arguments": "{}"}, "extra_content": {"opaque": "signature"}}]},
])
def test_opaque_history_is_not_silently_lost(message):
    with pytest.raises(RouterException):
        h.build_payload(request([message, {"role": "user", "content": "continue"}]), MODEL, "en-US", "UTC")


def test_cancel_generator_and_pending_read_timeout():
    async def run():
        upstream = Response()
        module, _, _ = fake_module(upstream)
        stream = module.stream_chat(request(), ctx())
        await anext(stream)
        await stream.aclose()
        assert upstream.closed and upstream.reader_closed
        upstream = Response(hang=True)
        module, _, _ = fake_module(upstream)
        context = ctx()
        context.timeout = .02
        with pytest.raises(RouterException) as err:
            await module.chat_completions(request(), context)
        assert err.value.category == ErrorCategory.TIMEOUT and upstream.closed and upstream.reader_closed
        upstream = Response(hang=True)
        module, _, _ = fake_module(upstream)
        task = asyncio.create_task(module.chat_completions(request(), ctx()))
        await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert upstream.closed and upstream.reader_closed
    asyncio.run(run())


def test_challenge_only_opt_in_browser_fallback():
    async def run():
        for status, enabled, expected in [(403, "true", True), (403, "false", False), (429, "true", False), (401, "true", False)]:
            upstream = Response(status=status, headers={"cf-mitigated": "challenge"})
            module, _, _ = fake_module(upstream)
            browser_calls = []
            @asynccontextmanager
            async def browser(context, method, url, headers, payload=None):
                browser_calls.append(url)
                response = Response()
                try:
                    yield response
                finally:
                    await response.aclose()
            module._browser = browser
            if expected:
                assert (await module.chat_completions(request(), ctx(browser_fallback=enabled))).choices[0].message.content == "Hello €"
            else:
                with pytest.raises(RouterException):
                    await module.chat_completions(request(), ctx(browser_fallback=enabled))
            assert bool(browser_calls) == expected and upstream.closed
    asyncio.run(run())


def test_native_chrome_transport_parameters_without_network():
    async def run():
        from curl_cffi.requests import AsyncSession
        calls = []
        upstream = Response()
        async def fake_request(self, method, url, **kwargs):
            calls.append((self.impersonate, self.trust_env, method, url, kwargs))
            return upstream
        with patch.object(AsyncSession, "request", fake_request):
            context = ctx()
            context.proxy_url = "http://127.0.0.1:1234"
            async with h.ClaudeWebModule()._direct(context, "POST", h.API + "/organizations", {"Cookie": "sessionKey=fake"}, {"prompt": "hi"}) as response:
                assert response is upstream
        assert upstream.closed
        impersonate, trust_env, _, _, args = calls[0]
        assert impersonate == "chrome" and trust_env is False
        assert args["proxy"] == context.proxy_url and args["timeout"] == context.timeout
        assert args["stream"] is True and args["allow_redirects"] is False
    asyncio.run(run())


def test_native_curl_pending_task_is_cancelled_not_waited_for_eof():
    async def run():
        from curl_cffi.requests import Response as NativeResponse
        response = NativeResponse()
        response.quit_now = asyncio.Event()
        response.astream_task = asyncio.create_task(asyncio.sleep(10))
        await asyncio.sleep(0)
        await asyncio.wait_for(h.close_response(response), .1)
        assert response.astream_task.cancelled() and response.quit_now.is_set()
        await h.close_response(response)  # Idempotent cleanup.
    asyncio.run(run())


def test_playwright_fallback_capture_merge_and_cleanup_without_launch():
    async def run():
        import base64
        from playwright import async_api
        state = {"closed": False, "pages": [], "cookies": None, "launch": None}
        class FakePage:
            def __init__(self):
                self.callback = None
                self.keyboard = self
                self.closed = False
                self.evaluated = None
            async def goto(self, url, **kwargs):
                assert url == h.BASE + "/new"
            async def route(self, pattern, callback):
                self.callback = callback
            def locator(self, selector):
                return self
            @property
            def first(self):
                return self
            async def fill(self, prompt):
                self.prompt = prompt
            async def press(self, key):
                page = self
                class Route:
                    request = type("Request", (), {"url": f"{h.API}/organizations/{ORG}/chat_conversations/ui-uuid/completion", "method": "POST", "post_data_json": {
                        "tools": [{"name": "ui-tool"}], "personalized_styles": [{"type": "account-style"}], "tool_states": [{"account": True}]}})()
                    async def abort(self):
                        page.aborted = True
                await self.callback(Route())
                assert self.aborted
            async def evaluate(self, script, data):
                self.evaluated = data
                assert state["pages"][0].closed  # Captured UI cannot retry/send the turn.
                return {"status": 200, "headers": {"content-type": "text/event-stream"}, "chunks": [base64.b64encode(wire(events())).decode()]}
            async def close(self):
                self.closed = True
        class FakeContext:
            async def add_cookies(self, cookies):
                state["cookies"] = cookies
            async def new_page(self):
                page = FakePage()
                state["pages"].append(page)
                return page
        class FakeBrowser:
            async def new_context(self, **kwargs):
                assert kwargs == {"locale": "fr-FR", "timezone_id": "Europe/Paris"}
                return FakeContext()
            async def close(self):
                state["closed"] = True
        class FakePlaywright:
            chromium = None
            def __init__(self):
                self.chromium = self
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def launch(self, **kwargs):
                state["launch"] = kwargs
                return FakeBrowser()
        with patch.object(async_api, "async_playwright", FakePlaywright):
            context = ctx(locale="fr-FR", timezone="Europe/Paris")
            context.proxy_url = "http://username:password@localhost:1234"
            payload = h.build_payload(request(tools=[{"type": "function", "function": {"name": "lookup"}}]), MODEL, "fr-FR", "Europe/Paris")
            url = f"{h.API}/organizations/{ORG}/chat_conversations/prepared-uuid/completion"
            async with h.ClaudeWebModule()._browser(context, "POST", url, h.headers("sessionKey=fake; cf_clearance=clear", "fr-FR", None), payload) as response:
                assert response.status_code == 200
            data = state["pages"][-1].evaluated
            assert data["url"] == url and data["payload"]["tools"] == [{"name": "lookup"}]
            assert data["payload"]["personalized_styles"] == [{"type": "account-style"}]
            assert data["payload"]["tool_states"] == [{"account": True}]
            assert "Cookie" not in data["headers"] and state["closed"]
            assert state["launch"]["proxy"] == {"server": "http://localhost:1234", "username": "username", "password": "password"}
            assert [c["name"] for c in state["cookies"]] == ["sessionKey", "cf_clearance"]
    asyncio.run(run())
