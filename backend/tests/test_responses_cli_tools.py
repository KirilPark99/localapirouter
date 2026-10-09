import json
from typing import Any

import httpx
import pytest

from app.adapters.module_adapter import CustomModuleAdapter
from app.core.errors import RouterException
from app.modules.base import collect_chat_completion
from app.modules.loader import ModuleLoader
from app.modules.responses import messages_to_input, responses_to_chat, tool_options
from app.routing.engine import RoutingEngine
from app.schemas.chat import ChatCompletionRequest, ChatMessage, ResponsesRequest
from modules.codex_cli.handler import CodexCliAdapter
from modules.grok_builder_cli.handler import GrokBuilderCliAdapter


FUNCTION = {"name": "lookup", "description": "Synthetic lookup", "parameters": {"type": "object"}, "strict": False}


def history():
    return [ChatMessage(role="user", content="Use lookup"),
        ChatMessage(role="assistant", tool_calls=[{"id": "call_old", "function": {"name": "lookup", "arguments": "{}"}}]),
        ChatMessage(role="tool", tool_call_id="call_old", content="synthetic result")]


def wire_events(final_only=False):
    items = [{"type": "function_call", "id": f"fc_{i}", "call_id": f"call_{i}", "name": "lookup", "arguments": "{}"} for i in range(2)]
    events = []
    if not final_only:
        for i, item in enumerate(items):
            events.append({"type": "response.output_item.added", "output_index": i + 1, "item": {**item, "arguments": ""}})
        for i, item in enumerate(items):
            for part in ("{", "}"):
                events.append({"type": "response.function_call_arguments.delta", "item_id": item["id"], "delta": part})
            events.append({"type": "response.function_call_arguments.done", "output_index": i + 1, "arguments": "{}"})
            events.append({"type": "response.output_item.done", "output_index": i + 1, "item": item})
    events.append({"type": "response.completed", "response": {"output": items,
        "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}}})
    return "".join("data: " + json.dumps(event) + "\n\n" for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize("module_id,adapter_type", [("codex_cli", CodexCliAdapter), ("grok_builder_cli", GrokBuilderCliAdapter)])
@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("final_only", [True, False])
@pytest.mark.parametrize("effort", [None, "high", "max"])
async def test_cli_tools_roundtrip(monkeypatch, module_id, adapter_type, stream, final_only, effort):
    adapter = adapter_type()
    async def synthetic_token(ctx):
        return "synthetic", "synthetic-account"
    monkeypatch.setattr(adapter, "_get_valid_access_token", synthetic_token)
    monkeypatch.setattr(ModuleLoader, "get_adapter", lambda mid: adapter)

    def upstream(request):
        body = json.loads(request.content)
        assert body["input"][1] == {"type": "function_call", "call_id": "call_old", "name": "lookup", "arguments": "{}"}
        assert body["input"][2] == {"type": "function_call_output", "call_id": "call_old", "output": "synthetic result"}
        assert body["tools"] == [{"type": "function", **FUNCTION}]
        assert body["tool_choice"] == {"type": "function", "name": "lookup"}
        assert body["parallel_tool_calls"] is False
        assert "thinking" not in body
        assert body.get("reasoning") == ({"effort": effort} if effort else None)
        assert request.extensions["timeout"]["read"] == 151
        return httpx.Response(200, text=wire_events(final_only), headers={"content-type": "text/event-stream"})
    monkeypatch.setattr(adapter, "create_http_client", lambda *args, **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(upstream)))
    request = ChatCompletionRequest(model="synthetic", stream=stream, messages=history(),
        tools=[{"type": "function", "function": FUNCTION}],
        tool_choice={"type": "function", "function": {"name": "lookup"}}, parallel_tool_calls=False)
    before = request.model_dump()
    request = RoutingEngine._apply_model_defaults(request, eff_thinking=effort)
    effective_before = request.model_dump()
    bridge = CustomModuleAdapter()
    kwargs = dict(base_url="", api_key=json.dumps({"auto_detect_local": False}), model_id="synthetic", request=request,
        extra_headers={}, configuration={"module_id": module_id}, timeout=151)
    if stream:
        response = await collect_chat_completion(bridge.stream_chat(**kwargs), "synthetic")
    else:
        response = await bridge.chat_completions(**kwargs)
    choice = response.choices[0]
    assert choice.finish_reason == "tool_calls"
    assert choice.message.content is None
    assert [(call.id, call.function.name, call.function.arguments) for call in choice.message.tool_calls] == [
        ("call_0", "lookup", "{}"), ("call_1", "lookup", "{}")]
    assert response.usage.total_tokens == 14
    assert request.model_dump() == effective_before
    if effort:
        assert before["thinking"] is None and request.thinking["type"] == "enabled"


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("temperature,top_p", [(0.7, 1.0), (0.0, 0.0), (None, 0.5), (0.8, None)])
async def test_cli_sampling_compatibility_is_codex_only(monkeypatch, stream, temperature, top_p):
    request = ChatCompletionRequest(model="synthetic", stream=stream, messages=history(),
        temperature=temperature, top_p=top_p, max_tokens=4096,
        tools=[{"type": "function", "function": FUNCTION}], parallel_tool_calls=False)
    request = RoutingEngine._apply_model_defaults(request, eff_thinking="high")
    snapshot = request.model_dump()
    provenance = set(getattr(request, "_routing_client_fields"))
    for module_id, adapter_type in (("grok_builder_cli", GrokBuilderCliAdapter), ("codex_cli", CodexCliAdapter)):
        adapter = adapter_type()
        auth_calls, bodies = [], []
        async def synthetic_token(ctx):
            auth_calls.append(True)
            return "synthetic", "synthetic-account"
        def upstream(wire_request):
            body = json.loads(wire_request.content)
            bodies.append(body)
            assert "temperature" not in body and "top_p" not in body and "thinking" not in body
            assert body["reasoning"] == {"effort": "high"}
            assert body["max_output_tokens"] == 4096
            assert body["input"] == messages_to_input(request.messages)
            assert body["tools"] == [{"type": "function", **FUNCTION}]
            assert body["parallel_tool_calls"] is False
            return httpx.Response(200, text=wire_events(), headers={"content-type": "text/event-stream"})
        monkeypatch.setattr(adapter, "_get_valid_access_token", synthetic_token)
        monkeypatch.setattr(adapter, "create_http_client", lambda *a, **kw: httpx.AsyncClient(transport=httpx.MockTransport(upstream)))
        monkeypatch.setattr(ModuleLoader, "get_adapter", lambda mid: adapter)
        bridge = CustomModuleAdapter()
        kwargs: dict[str, Any] = dict(base_url="", api_key=json.dumps({"auto_detect_local": False}), model_id="synthetic",
            request=request, extra_headers={}, configuration={"module_id": module_id}, timeout=151)
        async def invoke():
            if stream:
                return await collect_chat_completion(bridge.stream_chat(**kwargs), "synthetic")
            return await bridge.chat_completions(**kwargs)
        if module_id == "grok_builder_cli":
            with pytest.raises(RouterException, match="temperature|top_p") as caught:
                await invoke()
            assert caught.value.status_code == 422 and not auth_calls and not bodies
        else:
            response = await invoke()
            assert response.choices[0].finish_reason == "tool_calls" and response.usage.total_tokens == 14
            assert len(auth_calls) == len(bodies) == 1
            for unsupported in ({"seed": 1}, {"stop": ["END"]},
                                {"thinking": {"type": "enabled", "budget_tokens": 16384}, "_routing_client_fields": {"thinking"}}):
                overrides: dict[str, Any] = dict(unsupported)
                explicit_fields = overrides.pop("_routing_client_fields", None)
                kwargs["request"] = request.model_copy(update=overrides)
                if explicit_fields is not None:
                    object.__setattr__(kwargs["request"], "_routing_client_fields", explicit_fields)
                with pytest.raises(RouterException) as caught:
                    await invoke()
                assert caught.value.status_code == 422 and len(auth_calls) == len(bodies) == 1
        assert request.model_dump() == snapshot and getattr(request, "_routing_client_fields") == provenance


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [True, False])
async def test_codex_cache_affinity_is_stable_scoped_and_preserves_usage(monkeypatch, stream):
    adapter = CodexCliAdapter()
    account = ["synthetic-account"]
    captured = []

    async def synthetic_token(ctx):
        return "synthetic", account[0]

    def upstream(wire_request):
        body = json.loads(wire_request.content)
        session_id = wire_request.headers.get("session-id")
        assert session_id is not None and len(session_id) == 64
        assert all(char in "0123456789abcdef" for char in session_id)
        assert "x-codex-turn-state" not in wire_request.headers
        assert body["store"] is False and body["stream"] is True
        assert body["input"] == messages_to_input(current[0].messages)
        assert body["reasoning"] == {"effort": "high"}
        tools = current[0].tools
        assert tools is not None
        assert body["tools"] == [{"type": "function", **tools[0]["function"]}]
        captured.append((session_id, body["prompt_cache_key"]))
        event = {"type": "response.completed", "response": {"output": [],
            "usage": {"input_tokens": 10000, "output_tokens": 4, "total_tokens": 10004,
                      "input_tokens_details": {"cached_tokens": 4096}}}}
        return httpx.Response(200, text="data: " + json.dumps(event) + "\n\n",
                              headers={"content-type": "text/event-stream", "x-codex-turn-state": "do-not-replay"})

    monkeypatch.setattr(adapter, "_get_valid_access_token", synthetic_token)
    monkeypatch.setattr(adapter, "create_http_client", lambda *a, **kw: httpx.AsyncClient(transport=httpx.MockTransport(upstream)))
    monkeypatch.setattr(ModuleLoader, "get_adapter", lambda mid: adapter)
    bridge = CustomModuleAdapter()
    original = ChatCompletionRequest(model="synthetic", stream=stream,
        messages=[ChatMessage(role="system", content="Stable system"), *history()],
        reasoning_effort="high", tools=[{"type": "function", "function": FUNCTION}])
    snapshot = original.model_dump()
    current = [original]

    async def invoke(request, credential=80):
        current[0] = request
        before = request.model_dump()
        kwargs: dict[str, Any] = dict(base_url="", api_key=json.dumps({"auto_detect_local": False}), model_id=request.model,
            request=request, extra_headers={}, configuration={"module_id": "codex_cli", "credential_id": credential})
        response = (await collect_chat_completion(bridge.stream_chat(**kwargs), request.model) if stream
                    else await bridge.chat_completions(**kwargs))
        assert response.usage.prompt_tokens_details == {"cached_tokens": 4096}
        assert request.model_dump() == before
        return captured[-1]

    baseline = await invoke(original)
    assert baseline[0] == baseline[1]
    assert await invoke(original) == baseline
    grown = original.model_copy(update={"messages": [*original.messages,
        ChatMessage(role="assistant", content="More history"), ChatMessage(role="user", content="Next turn")]})
    assert await invoke(grown) == baseline
    changed_user = original.model_copy(deep=True)
    changed_user.messages[1].content = "Different first question"
    assert (await invoke(changed_user))[0] != baseline[0]
    changed_system = original.model_copy(deep=True)
    changed_system.messages[0].content = "Different system"
    assert (await invoke(changed_system))[0] != baseline[0]
    changed_tools = original.model_copy(deep=True)
    changed_tools.tools[0]["function"]["description"] = "Different schema"
    assert (await invoke(changed_tools))[0] != baseline[0]
    assert (await invoke(original.model_copy(update={"model": "another-model"})))[0] != baseline[0]
    assert (await invoke(original, credential=81))[0] != baseline[0]
    account[0] = "another-account"
    assert (await invoke(original))[0] != baseline[0]
    account[0] = "synthetic-account"
    # No initial system/assistant prefix is required for an append-stable key.
    user_first = original.model_copy(update={"messages": history()})
    user_first_key = await invoke(user_first)
    assert await invoke(user_first.model_copy(update={"messages": [*history(), ChatMessage(role="user", content="Next")]})) == user_first_key
    for explicit in ("client-explicit", "", "unicode-ключ\nbody-only"):
        request = original.model_copy(update={"prompt_cache_key": explicit})
        explicit_key = await invoke(request)
        assert explicit_key[1] == explicit
        assert await invoke(changed_user.model_copy(update={"prompt_cache_key": explicit})) == explicit_key
    assert original.model_dump() == snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("cached", [4096, 0, None])
async def test_grok_cache_affinity_headers_usage_and_scopes(monkeypatch, stream, cached):
    adapter = GrokBuilderCliAdapter()
    account = ["synthetic-account"]
    captured = []

    async def synthetic_token(ctx):
        return "synthetic", account[0]

    def upstream(wire_request):
        body = json.loads(wire_request.content)
        headers = wire_request.headers
        assert headers["authorization"] == "Bearer synthetic"
        assert headers["x-grok-client-identifier"] == "grok-shell"
        assert headers["x-grok-conv-id"] and headers["x-grok-session-id"]
        assert body["input"] == messages_to_input(current[0].messages)
        assert current[0].tools is not None
        assert body["tools"] == [{"type": "function", **current[0].tools[0]["function"]}]
        assert body["store"] is False and body["stream"] is True
        captured.append((headers["x-grok-conv-id"], headers["x-grok-session-id"], body["prompt_cache_key"]))
        usage: dict[str, Any] = {"input_tokens": 10000, "output_tokens": 4, "total_tokens": 10004}
        if cached is not None:
            usage["input_tokens_details"] = {"cached_tokens": cached}
        event = {"type": "response.completed", "response": {"output": [], "usage": usage}}
        return httpx.Response(200, text="data: " + json.dumps(event) + "\n\n",
                              headers={"content-type": "text/event-stream"})

    monkeypatch.setattr(adapter, "_get_valid_access_token", synthetic_token)
    monkeypatch.setattr(adapter, "create_http_client", lambda *a, **kw: httpx.AsyncClient(transport=httpx.MockTransport(upstream)))
    monkeypatch.setattr(ModuleLoader, "get_adapter", lambda mid: adapter)
    bridge = CustomModuleAdapter()
    original = ChatCompletionRequest(model="grok_builder_cli/synthetic", stream=stream,
        messages=[ChatMessage(role="system", content="Stable system"), *history()],
        tools=[{"type": "function", "function": FUNCTION}])
    current = [original]

    async def invoke(request=original, credential=80, extras=None):
        current[0] = request
        before = request.model_dump()
        configuration = {"module_id": "grok_builder_cli", "credential_id": credential}
        kwargs: dict[str, Any] = dict(base_url="", api_key=json.dumps({"auto_detect_local": False}), model_id=request.model,
            request=request, extra_headers=extras or {}, configuration=configuration)
        response = (await collect_chat_completion(bridge.stream_chat(**kwargs), request.model) if stream
                    else await bridge.chat_completions(**kwargs))
        assert response.usage is not None
        assert response.usage.prompt_tokens_details == ({"cached_tokens": cached} if cached is not None else None)
        assert response.usage.prompt_tokens == 10000 and response.usage.total_tokens == 10004
        assert request.model_dump() == before
        assert configuration == {"module_id": "grok_builder_cli", "credential_id": credential}
        return captured[-1]

    baseline = await invoke()
    assert baseline[0] == baseline[1] == baseline[2]
    assert len(baseline[0]) == 64 and set(baseline[0]) <= set("0123456789abcdef")
    assert await invoke() == baseline
    assert await invoke(original.model_copy(update={"model": "synthetic"})) == baseline
    grown = original.model_copy(update={"messages": [*original.messages,
        ChatMessage(role="assistant", content="More history"), ChatMessage(role="user", content="Next turn")]})
    assert await invoke(grown) == baseline
    for index in (0, 1):
        changed = original.model_copy(deep=True)
        changed.messages[index].content = "Different start"
        assert (await invoke(changed))[0] != baseline[0]
    changed = original.model_copy(deep=True)
    assert changed.tools is not None
    changed.tools[0]["function"]["description"] = "Different schema"
    assert (await invoke(changed))[0] != baseline[0]
    assert (await invoke(original.model_copy(update={"model": "other-model"})))[0] != baseline[0]
    assert (await invoke(credential=81))[0] != baseline[0]
    account[0] = "another-account"
    assert (await invoke())[0] != baseline[0]
    account[0] = "synthetic-account"
    user_first = original.model_copy(update={"messages": history()})
    key = await invoke(user_first)
    assert await invoke(user_first.model_copy(update={"messages": [*history(), ChatMessage(role="user", content="Next")]})) == key
    for explicit in ("client-explicit", "", "unicode-ключ\nbody-only"):
        request = original.model_copy(update={"prompt_cache_key": explicit})
        key = await invoke(request)
        assert key[2] == explicit and key[0] == key[1]
        assert await invoke(grown.model_copy(update={"prompt_cache_key": explicit})) == key
        assert (await invoke(request, credential=81))[0] != key[0]
    extras = {"X-Grok-Conv-ID": "native-conversation", "x-grok-session-id": "native-session"}
    assert await invoke(extras=extras) == ("native-conversation", "native-session", "native-conversation")
    assert await invoke(grown, extras=extras) == ("native-conversation", "native-session", "native-conversation")
    assert await invoke(original.model_copy(update={"prompt_cache_key": ""}), extras=extras) == ("native-conversation", "native-session", "")
    assert extras == {"X-Grok-Conv-ID": "native-conversation", "x-grok-session-id": "native-session"}
    assert (await invoke(extras={"x-grok-conv-id": "native-only"}))[0:3:2] == ("native-only", "native-only")
    assert await invoke(extras={"x-grok-session-id": "session-only"}) == (baseline[0], "session-only", baseline[2])
    calls = len(captured)
    for invalid in ({"Authorization": "unsafe"}, {"user-agent": "unsafe"}, {"x-grok-client-mode": "unsafe"},
                    {"X-Unknown": "discarded"}, {"x-grok-conv-id": "bad\nheader"},
                    {"x-grok-session-id": "unicode-ключ"}, {"x-grok-conv-id": ""},
                    {"x-grok-conv-id": "bad\x7fheader"}, {"x-grok-session-id": 123},
                    {"x-grok-conv-id": " spaced "}, {"x-grok-conv-id": "one", "X-Grok-Conv-ID": "two"}):
        with pytest.raises(RouterException, match="header") as caught:
            await invoke(extras=invalid)
        assert caught.value.status_code == 400
    assert len(captured) == calls


@pytest.mark.asyncio
async def test_module_bridge_passes_fresh_extra_headers_context(monkeypatch):
    contexts = []
    class SyntheticModule:
        async def list_models(self, ctx):
            contexts.append(ctx)
            ctx.extra_config["extra_headers"]["x-test"] = "mutated"
            ctx.extra_config["new"] = True
            return []
        async def validate_credentials(self, ctx):
            contexts.append(ctx)
            return True, "synthetic", 0
    monkeypatch.setattr(ModuleLoader, "get_adapter", lambda mid: SyntheticModule())
    bridge = CustomModuleAdapter()
    configuration = {"module_id": "synthetic", "extra_headers": {"old": "config"}}
    extras = {"x-test": "caller"}
    await bridge.list_models("", "", extras, configuration)
    await bridge.validate_credentials("", "", extras, configuration)
    assert configuration == {"module_id": "synthetic", "extra_headers": {"old": "config"}}
    assert extras == {"x-test": "caller"}
    assert contexts[1].extra_config["extra_headers"] == extras
    assert contexts[0].extra_config is not contexts[1].extra_config
    _, ctx = bridge._resolve_context("", configuration)
    assert ctx.extra_config["extra_headers"] == configuration["extra_headers"]
    ctx.extra_config["extra_headers"]["old"] = "changed"
    assert configuration["extra_headers"] == {"old": "config"}


@pytest.mark.asyncio
async def test_grok_discovery_and_compression_cache_capability(monkeypatch):
    from app.compression.caching_aware import is_prompt_caching_supported, should_preserve_system_prompt
    from app.modules.base import ModuleExecutionContext
    adapter = GrokBuilderCliAdapter()
    async def synthetic_token(ctx):
        return "synthetic", "synthetic-account"
    monkeypatch.setattr(adapter, "_get_valid_access_token", synthetic_token)
    for dynamic in (True, False):
        def upstream(request):
            return httpx.Response(200 if dynamic else 503, json={"data": [{"id": "grok-test"}]})
        monkeypatch.setattr(adapter, "create_http_client", lambda *a, **kw: httpx.AsyncClient(transport=httpx.MockTransport(upstream)))
        models = await adapter.list_models(ModuleExecutionContext(credentials={"auto_detect_local": False}))
        assert models and all(model.capabilities["prompt_caching"] is True for model in models)
    for model, provider in (("grok-4.7", None), ("grok_builder_cli/grok-4.7", None),
                            ("xai/grok-4.7", None), ("synthetic", "xAI"), ("synthetic", "grok_builder_cli")):
        assert is_prompt_caching_supported(model, provider)
        assert should_preserve_system_prompt("when_caching", model, provider_name=provider)
        assert not should_preserve_system_prompt("never", model, provider_name=provider)
    assert not is_prompt_caching_supported("unrelated", "unrelated")
    assert not should_preserve_system_prompt("when_caching", "grok-4.7", supports_prompt_cache=False)


def test_cli_reasoning_defaults_preserve_strict_client_validation():
    original = ChatCompletionRequest(model="synthetic", messages=history())
    before = original.model_dump()
    for effort in ("high", "max", "low", "medium", "auto", "off"):
        effective = RoutingEngine._apply_thinking_effort(original, effort).model_copy(deep=True)
        snapshot = effective.model_dump()
        assert tool_options(effective) == {"reasoning": {"effort": "none" if effort == "off" else effort}}
        assert effective.model_dump() == snapshot
    assert original.model_dump() == before
    effective = RoutingEngine._apply_thinking_effort(original, "max")
    for overrides, field in (({"thinking": effective.thinking, "reasoning_effort": "max"}, "thinking"),
                             ({"thinking": {"type": "enabled", "budget_tokens": 1024}}, "thinking"),
                             ({"reasoning": {"effort": "high", "max_tokens": 1024}}, "reasoning"),
                             ({"temperature": 0.2}, "temperature")):
        request = ChatCompletionRequest(model="synthetic", messages=history(), **overrides)
        request = RoutingEngine._apply_model_defaults(request, eff_thinking="high")
        with pytest.raises(RouterException, match=field) as caught:
            tool_options(request)
        assert caught.value.status_code == 422
    for overrides in ({"reasoning_effort": "low"}, {"reasoning": {"effort": "low"}}):
        request = ChatCompletionRequest(model="synthetic", messages=history(), **overrides)
        assert tool_options(RoutingEngine._apply_model_defaults(request, eff_thinking="max")) == {"reasoning": {"effort": "low"}}


def test_native_history_and_options_roundtrip():
    original = messages_to_input(history())
    request = ResponsesRequest(model="synthetic", input=original,
        tools=[{"type": "function", **FUNCTION}], tool_choice={"type": "function", "name": "lookup"}, parallel_tool_calls=False).to_chat_request()
    assert messages_to_input(request.messages) == original
    assert request.tools == [{"type": "function", "function": FUNCTION}]
    assert request.tool_choice == {"type": "function", "function": {"name": "lookup"}}
    assert request.parallel_tool_calls is False
    from app.adapters.openai import GenericOpenAIAdapter
    payload = GenericOpenAIAdapter()._prepare_payload("synthetic", request)
    assert payload["tool_choice"] == request.tool_choice
    assert payload["parallel_tool_calls"] is False
    with pytest.raises(ValueError, match="call_id"):
        ResponsesRequest(model="synthetic", input=[{"type": "function_call_output", "output": "x"}]).to_chat_request()
    with pytest.raises(RouterException) as caught:
        messages_to_input([ChatMessage(role="tool", content="x")])
    assert caught.value.status_code == 400


@pytest.mark.asyncio
async def test_stream_errors_and_text_are_not_swallowed():
    async def lines():
        yield 'data: {"type":"response.reasoning_summary_text.delta","delta":"Reason"}'
        yield 'data: {"type":"response.output_text.delta","delta":"Answer"}'
        yield 'data: {"type":"response.completed"}'
    result = await collect_chat_completion(responses_to_chat(lines(), "test", "id", 1), "test")
    assert result.choices[0].message.content == "Answer"
    assert result.choices[0].message.reasoning_content == "Reason"
    assert result.choices[0].finish_reason == "stop"
    async def error_lines():
        yield 'data: {"type":"response.failed","response":{"error":{"message":"Synthetic upstream failure"}}}'
    with pytest.raises(RouterException, match="Synthetic upstream failure"):
        await collect_chat_completion(responses_to_chat(error_lines(), "test", "id", 1), "test")
