"""Offline usage conversion checks; every upstream is synthetic."""
import json

import httpx
import pytest

from app.adapters.anthropic import AnthropicAdapter
from app.adapters.google import GoogleAIStudioAdapter
from app.core.http_client import http_client_manager
from app.modules.base import collect_chat_completion
from app.modules.responses import responses_to_chat
from app.schemas.chat import ChatCompletionRequest, ChatMessage, UsageInfo


@pytest.mark.asyncio
@pytest.mark.parametrize("details", [None, {"cached_tokens": 0}, {"cached_tokens": 8}])
async def test_responses_usage_survives_stream_and_collection(details):
    raw = {"input_tokens": 12, "output_tokens": 7, "total_tokens": 19,
           "input_tokens_details": details,
           "output_tokens_details": {"reasoning_tokens": 3, "audio_tokens": None}}

    async def lines():
        yield "data: " + json.dumps({"type": "response.completed", "response": {
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
            "usage": raw}}) + "\n\n"

    chunks = [chunk async for chunk in responses_to_chat(lines(), "synthetic", "id", 1)]
    wire_usage = json.loads(chunks[-2][5:])["usage"]
    assert wire_usage["completion_tokens_details"] == raw["output_tokens_details"]

    async def stream():
        for chunk in chunks:
            yield chunk

    result = await collect_chat_completion(stream(), "synthetic")
    usage = json.loads(result.model_dump_json())["usage"]
    assert usage["prompt_tokens_details"] == details
    assert usage["completion_tokens_details"] == raw["output_tokens_details"]
    assert UsageInfo().completion_tokens_details is None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["anthropic", "google"])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("cache", [None, 0, 8])
async def test_adapter_usage_details(monkeypatch, provider, stream, cache):
    if provider == "anthropic":
        raw: dict = {"input_tokens": 12, "output_tokens": 7}
        expected_details = None
        if cache is not None:
            raw.update(cache_read_input_tokens=cache, cache_creation_input_tokens=4)
            raw["output_tokens_details"] = {"thinking_tokens": 0 if cache == 0 else 3}
            expected_details = {"cached_tokens": cache, "cache_creation_input_tokens": 4}
        prompt = 12 + (cache + 4 if cache is not None else 0)
        expected = UsageInfo(prompt_tokens=prompt, completion_tokens=7, total_tokens=prompt + 7,
                             prompt_tokens_details=expected_details,
                             completion_tokens_details=None if cache is None else
                                 {"reasoning_tokens": raw["output_tokens_details"]["thinking_tokens"]}).model_dump()
        data = {"id": "synthetic", "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn", "usage": raw}
        events = [{"type": "message_start", "message": {"id": "synthetic", "usage": {**raw, "output_tokens": 0}}},
                  {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "ok"}},
                  {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {
                      key: value for key, value in raw.items() if key in ("output_tokens", "output_tokens_details")}},
                  {"type": "message_stop"}]
        adapter = AnthropicAdapter()
    else:
        expected = UsageInfo(prompt_tokens=12, completion_tokens=7, total_tokens=19,
            prompt_tokens_details=None if cache is None else {"cached_tokens": cache},
            completion_tokens_details={"reasoning_tokens": 3}).model_dump()
        data = {"id": "synthetic", "model": "synthetic", "choices": [{"index": 0,
                "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}], "usage": expected}
        events = [{"id": "synthetic", "choices": [{"index": 0, "delta": {"content": "ok"}, "finish_reason": "stop"}]},
                  {"id": "synthetic", "choices": [], "usage": expected}]
        adapter = GoogleAIStudioAdapter()

    def upstream(request):
        assert request.url.host == "synthetic.invalid"
        if not stream:
            return httpx.Response(200, json=data)
        text = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
        if provider == "google":
            text += "data: [DONE]\n\n"
        return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        async def get_client(**kwargs):
            return client
        monkeypatch.setattr(http_client_manager, "get_client", get_client)
        kwargs = dict(base_url="https://synthetic.invalid", api_key="synthetic", model_id="synthetic",
                      request=ChatCompletionRequest(model="synthetic", stream=stream,
                          messages=[ChatMessage(role="user", content="hello")]),
                      extra_headers={}, configuration={})
        result = (await collect_chat_completion(adapter.stream_chat(**kwargs), "synthetic")
                  if stream else await adapter.chat_completions(**kwargs))
    assert json.loads(result.model_dump_json())["usage"] == expected


def test_anthropic_absent_and_partial_usage_stays_unreported():
    adapter = AnthropicAdapter()
    assert adapter._convert_usage({}) is None
    for raw, fields in (({'input_tokens': 12}, {'prompt_tokens': 12}),
                        ({'output_tokens': 7}, {'completion_tokens': 7})):
        result = adapter._convert_usage(raw)
        assert result is not None
        assert result.model_dump(exclude_unset=True) == fields
