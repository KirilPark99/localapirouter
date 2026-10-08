"""Offline wire-fidelity regressions; no provider calls or live configuration."""
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.adapters.anthropic import AnthropicAdapter
from app.adapters.openai import GenericOpenAIAdapter
from app.api.v1.router import (_anthropic_chat_request, _anthropic_payload,
                               _responses_event_stream, _responses_payload)
from app.core.http_client import http_client_manager
from app.modules.responses import messages_to_input, responses_to_chat
from app.schemas.chat import (ChatCompletionChoice, ChatCompletionRequest,
                              ChatCompletionResponse, ChatMessage, ResponsesRequest, UsageInfo)

REASONING = {"type": "reasoning", "id": "rs_fixture", "summary": [
    {"type": "summary_text", "text": "plan"}], "encrypted_content": "opaque-fixture"}
USAGE = {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17,
         "prompt_tokens_details": {"cached_tokens": 0},
         "completion_tokens_details": {"reasoning_tokens": 3}}


def test_responses_history_preserves_opaque_reasoning_and_signatures():
    items = [REASONING, {"type": "function_call", "call_id": "call_fixture", "name": "lookup",
             "arguments": "{}", "extra_content": {"google": {"thought_signature": "opaque"}}}]
    request = ResponsesRequest(model="fixture", input=items).to_chat_request()
    assert messages_to_input(request.messages) == items
    assert request.messages[0].reasoning_details == [REASONING]
    with pytest.raises(ValueError, match="Unsupported"):
        ResponsesRequest(model="fixture", input=[{"type": "item_reference", "id": "opaque"}]).to_chat_request()


def test_responses_collected_reasoning_and_detailed_usage():
    response = ChatCompletionResponse(model="fixture", choices=[ChatCompletionChoice(
        message=ChatMessage(role="assistant", content="answer", reasoning_content="plan",
                            reasoning_details=[REASONING]))], usage=UsageInfo(**USAGE))
    payload = _responses_payload(response, "resp_fixture")
    assert payload["output"][0] == REASONING
    assert payload["usage"] == {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17,
        "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 3}}
    response.usage = UsageInfo(prompt_tokens=12)
    assert _responses_payload(response, "resp_fixture")["usage"] == {"input_tokens": 12}


@pytest.mark.asyncio
async def test_responses_stream_opaque_reasoning_usage_and_history():
    async def lines():
        for event in [
            {"type": "response.output_item.added", "output_index": 0, "item": {**REASONING, "summary": []}},
            {"type": "response.reasoning_summary_text.delta", "output_index": 0, "item_id": "rs_fixture", "summary_index": 0, "delta": "plan"},
            {"type": "response.output_item.done", "output_index": 0, "item": REASONING},
            {"type": "response.completed", "response": {"output": [REASONING], "usage": {
                "input_tokens": 12, "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 5, "output_tokens_details": {"reasoning_tokens": 3}, "total_tokens": 17}}},
        ]:
            yield "data: " + json.dumps(event)
    frames = [frame async for frame in _responses_event_stream(
        responses_to_chat(lines(), "fixture", "id", 1), "fixture", "resp_fixture")]
    events = [json.loads(frame.split("\ndata: ")[1]) for frame in frames]
    final = events[-1]["response"]
    assert final["output"] == [REASONING]
    assert final["usage"]["input_tokens_details"] == {"cached_tokens": 0}
    assert final["usage"]["output_tokens_details"] == {"reasoning_tokens": 3}
    assert any(e["type"] == "response.reasoning_summary_text.delta" and e["delta"] == "plan" for e in events)
    assert messages_to_input(ResponsesRequest(model="fixture", input=final["output"]).to_chat_request().messages) == [REASONING]


@pytest.mark.parametrize("is_error", [True, False])
def test_anthropic_roundtrip_error_and_cache_metadata(is_error):
    cache = {"type": "ephemeral", "ttl": "1h"}
    body = {"model": "fixture", "max_tokens": 20,
        "system": [{"type": "text", "text": "policy", "cache_control": cache}],
        "tools": [{"name": "lookup", "input_schema": {"type": "object"}, "cache_control": cache}],
        "messages": [{"role": "assistant", "content": [{"type": "tool_use", "id": "call_fixture",
            "name": "lookup", "input": {}, "cache_control": cache}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_fixture",
                "content": [{"type": "text", "text": "failed", "cache_control": cache}],
                "is_error": is_error, "cache_control": cache},
                {"type": "image", "source": {"type": "url", "url": "https://fixture.invalid/image"}, "cache_control": cache}]}]}
    request = _anthropic_chat_request(body)
    payload = AnthropicAdapter()._prepare_payload("fixture", request)
    assert payload["system"] == body["system"]
    assert payload["tools"][0]["cache_control"] == cache
    assert payload["messages"][-2:] == body["messages"]


def test_anthropic_usage_preserves_cache_counts_without_double_counting():
    response = ChatCompletionResponse(model="fixture", choices=[ChatCompletionChoice(
        message=ChatMessage(role="assistant", content="answer"))],
        usage=AnthropicAdapter()._convert_usage({"input_tokens": 2, "output_tokens": 3,
            "cache_read_input_tokens": 7, "cache_creation_input_tokens": 4}))
    assert _anthropic_payload(response)["usage"] == {"input_tokens": 2, "output_tokens": 3,
        "cache_read_input_tokens": 7, "cache_creation_input_tokens": 4}


@pytest.mark.asyncio
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
async def test_generic_sse_frames_not_lines_and_explicit_cache_key(monkeypatch, newline):
    captured = []
    wire = newline.join([":keepalive", "event: message", "id: fixture", "retry: 10",
        'data:{"choices": [', 'data: {"index":0,"delta":{"content":"a\u2028b"},"finish_reason":null}]}',
        "", "data:[DONE]", "", ""]).encode()
    class Chunks(httpx.AsyncByteStream):
        async def __aiter__(self):
            for i in range(0, len(wire), 3):
                yield wire[i:i+3]
    def handler(request):
        captured.append(json.loads(request.content))
        if captured[-1]["stream"]:
            return httpx.Response(200, stream=Chunks(), headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"model": "fixture", "choices": [{"message": {"role": "assistant", "content": "ok"}}]})
    request = ChatCompletionRequest(model="fixture", messages=[ChatMessage(role="user", content="fixture")], prompt_cache_key="")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(http_client_manager, "get_client", AsyncMock(return_value=client))
        adapter = GenericOpenAIAdapter()
        frames = [f async for f in adapter.stream_chat("https://fixture.invalid", "synthetic", "fixture", request, {}, {})]
        await adapter.chat_completions("https://fixture.invalid", "synthetic", "fixture", request, {}, {})
    assert len(frames) == 2 and frames[-1] == "data: [DONE]\n\n"
    assert json.loads(frames[0][6:])["choices"][0]["delta"]["content"] == "a\u2028b"
    assert all(body["prompt_cache_key"] == "" for body in captured)
    from app.modules.base import ChatStreamAccumulator
    accumulator = ChatStreamAccumulator()
    for frame in frames:
        accumulator.feed(frame)
    assert accumulator.response("fixture").choices[0].message.content == "a\u2028b"


@pytest.mark.asyncio
async def test_reasoning_item_ids_and_summary_indexes_survive_stream():
    first = {**REASONING, "summary": [{"type": "summary_text", "text": "a"}, {"type": "summary_text", "text": "b"}]}
    second = {**REASONING, "id": "rs_second", "summary": [{"type": "summary_text", "text": "c"}]}
    async def lines():
        for index, item in enumerate([first, second]):
            yield "data: " + json.dumps({"type": "response.output_item.added", "output_index": index, "item": {**item, "summary": []}})
            for summary_index, part in enumerate(item["summary"]):
                yield "data: " + json.dumps({"type": "response.reasoning_summary_text.delta", "output_index": index,
                    "item_id": item["id"], "summary_index": summary_index, "delta": part["text"]})
            yield "data: " + json.dumps({"type": "response.output_item.done", "output_index": index, "item": item})
        yield "data: " + json.dumps({"type": "response.completed", "response": {"output": [first, second]}})
    frames = [f async for f in _responses_event_stream(responses_to_chat(lines(), "fixture", "id", 1), "fixture", "resp_fixture")]
    events = [json.loads(f.split("\ndata: ")[1]) for f in frames]
    assert events[-1]["response"]["output"] == [first, second]
    deltas = [e for e in events if e["type"] == "response.reasoning_summary_text.delta"]
    assert [(e["item_id"], e["summary_index"], e["delta"]) for e in deltas] == [
        (first["id"], 0, "a"), (first["id"], 1, "b"), (second["id"], 0, "c")]


@pytest.mark.asyncio
async def test_legacy_reasoning_text_streamed_without_duplication():
    async def source():
        for text in ["a", "b"]:
            yield "data: " + json.dumps({"choices": [{"delta": {"reasoning_content": text}}]}) + "\n\n"
        yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
    frames = [f async for f in _responses_event_stream(source(), "fixture", "resp_fixture")]
    events = [json.loads(f.split("\ndata: ")[1]) for f in frames]
    assert events[-1]["response"]["output"][0]["summary"] == [{"type": "summary_text", "text": "ab"}]
    assert [e["delta"] for e in events if e["type"] == "response.reasoning_summary_text.delta"] == ["a", "b"]


def test_unsupported_opaque_history_conversion_is_explicit():
    from app.core.errors import RouterException
    native = ResponsesRequest(model="fixture", input=[REASONING]).to_chat_request()
    for adapter in [GenericOpenAIAdapter(), AnthropicAdapter()]:
        with pytest.raises(RouterException, match="reasoning"):
            adapter._prepare_payload("fixture", native)
    anthropic = ChatMessage(role="assistant", reasoning_details=[{"type": "thinking", "thinking": "a", "signature": "opaque"}])
    with pytest.raises(RouterException, match="reasoning"):
        messages_to_input([anthropic])
    response = ChatCompletionResponse(model="fixture", choices=[ChatCompletionChoice(message=anthropic)])
    with pytest.raises(ValueError, match="reasoning"):
        _responses_payload(response, "resp_fixture")


@pytest.mark.asyncio
@pytest.mark.parametrize("item", [{"type": "web_search_call", "id": "opaque"},
    {"type": "message", "role": "assistant", "content": [{"type": "refusal", "refusal": "no"}]}])
async def test_unsupported_responses_output_cannot_disappear(item):
    from app.core.errors import RouterException
    async def lines():
        yield "data: " + json.dumps({"type": "response.completed", "response": {"output": [item]}})
    with pytest.raises(RouterException, match="Unsupported"):
        _ = [f async for f in responses_to_chat(lines(), "fixture", "id", 1)]


@pytest.mark.asyncio
async def test_collected_reasoning_history_strips_only_transport_index():
    from app.modules.base import collect_chat_completion
    async def lines():
        yield "data: " + json.dumps({"type": "response.output_item.done", "output_index": 0, "item": REASONING})
        yield "data: " + json.dumps({"type": "response.completed", "response": {"output": [REASONING]}})
    response = await collect_chat_completion(responses_to_chat(lines(), "fixture", "id", 1), "fixture")
    message = response.choices[0].message
    before = message.model_dump()
    assert messages_to_input([message])[0] == REASONING
    assert message.model_dump() == before


@pytest.mark.asyncio
async def test_tool_use_cache_marker_protects_prefix_in_advancing_pipeline(monkeypatch):
    from types import SimpleNamespace
    from app.compression.pipeline import CompressionPipelineService as Pipeline
    cache = {"type": "ephemeral"}
    request = _anthropic_chat_request({"model": "fixture", "max_tokens": 20,
        "system": "prefix" + "\n" * 40 + "suffix", "messages": [
        {"role": "user", "content": "question" + "\n" * 40 + "suffix"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "call_fixture",
            "name": "lookup", "input": {}, "cache_control": cache}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_fixture", "content": "answer"}]},
        {"role": "user", "content": "next question"}]})
    config = SimpleNamespace(enabled=True, trigger_token_threshold=0,
        preserve_system_prompt_mode="when_caching", preserve_recent_turns=1,
        min_savings_bailout_percent=0, fail_open=False, enable_telemetry=True)
    stage = SimpleNamespace(id="lite", name="Lite", enabled=True, stage_type="builtin", config_json={}, icon="Sparkles")
    monkeypatch.setattr(Pipeline, "get_global_settings", AsyncMock(return_value=config))
    monkeypatch.setattr(Pipeline, "get_stages", AsyncMock(return_value=[stage]))
    output, summary = await Pipeline.optimize_messages(None, request.messages,
        model_id="fixture", provider_name="anthropic", tools=request.tools, supports_prompt_cache=False)
    assert summary["compressed"] and summary["breakdown"][0]["advanced"]
    assert output[0].content == request.messages[0].content
    assert output[1].content == [{"type": "text", "text": "question\n\nsuffix"}]
    assert output[2].tool_calls[0].extra_content["anthropic"]["cache_control"] == cache
