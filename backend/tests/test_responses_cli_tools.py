import json

import httpx
import pytest

from app.adapters.module_adapter import CustomModuleAdapter
from app.core.errors import RouterException
from app.modules.base import collect_chat_completion
from app.modules.loader import ModuleLoader
from app.modules.responses import messages_to_input, responses_to_chat
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
async def test_cli_tools_roundtrip(monkeypatch, module_id, adapter_type, stream, final_only):
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
        assert request.extensions["timeout"]["read"] == 151
        return httpx.Response(200, text=wire_events(final_only), headers={"content-type": "text/event-stream"})
    monkeypatch.setattr(adapter, "create_http_client", lambda *args, **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(upstream)))
    request = ChatCompletionRequest(model="synthetic", stream=stream, messages=history(),
        tools=[{"type": "function", "function": FUNCTION}],
        tool_choice={"type": "function", "function": {"name": "lookup"}}, parallel_tool_calls=False)
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
