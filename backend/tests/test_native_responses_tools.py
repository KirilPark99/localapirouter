import json
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.router import _responses_event_stream, _responses_payload, responses_api
from app.schemas.chat import ChatCompletionChoice, ChatCompletionResponse, ChatMessage, ResponsesRequest, UsageInfo


def completion(content=None):
    return ChatCompletionResponse(
        model="demo", choices=[ChatCompletionChoice(message=ChatMessage(
            role="assistant", content=content, tool_calls=[
                {"id": "call_weather", "function": {"name": "weather", "arguments": '{"city":"Paris"}'}},
                {"id": "call_time", "function": {"name": "clock", "arguments": "{}"}},
            ]), finish_reason="tool_calls")],
        usage=UsageInfo(prompt_tokens=5, completion_tokens=7, total_tokens=12),
    )


@pytest.mark.parametrize("content", [None, "Checking."])
def test_native_payload_function_calls(content):
    payload = _responses_payload(completion(content), "resp_test")
    calls = [item for item in payload["output"] if item["type"] == "function_call"]
    assert [(item["call_id"], item["name"], item["arguments"]) for item in calls] == [
        ("call_weather", "weather", '{"city":"Paris"}'), ("call_time", "clock", "{}"),
    ]
    assert all(item["status"] == "completed" and item["id"] != item["call_id"] for item in calls)
    assert len(payload["output"]) == (3 if content else 2)
    assert payload["output_text"] == (content or "")


async def events(chunks):
    async def source():
        for data in chunks:
            yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"
    return [json.loads(chunk.split("data: ", 1)[1]) async for chunk in
            _responses_event_stream(source(), "demo", "resp_test")]


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [None, "Checking."])
async def test_native_stream_parallel_calls_and_final_output(text):
    chunks = []
    if text:
        chunks.append({"choices": [{"delta": {"content": text}}]})
    chunks.extend([
        {"choices": [{"delta": {"tool_calls": [
            {"index": 3, "id": "call_weather", "function": {"name": "weather", "arguments": '{"city":'}},
            {"index": 9, "id": "call_time", "function": {"name": "clock", "arguments": "{"}},
        ]}}]},
        {"choices": [{"delta": {"tool_calls": [
            {"index": 9, "function": {"arguments": "}"}},
            {"index": 3, "function": {"arguments": '"Paris"}'}},
        ]}, "finish_reason": "tool_calls"}]},
        {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}},
    ])
    result = await events(chunks)
    assert [event["sequence_number"] for event in result] == list(range(len(result)))
    output = result[-1]["response"]["output"]
    assert result[-1]["type"] == "response.completed"
    assert result[-1]["response"]["usage"] == {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12}
    assert result[-1]["response"]["output_text"] == (text or "")
    assert len(output) == (3 if text else 2)
    for index, item in enumerate(output):
        related = [event for event in result if event.get("output_index") == index]
        assert related[0]["type"] == "response.output_item.added"
        assert related[0]["item"]["id"] == item["id"]
        assert related[-1]["type"] == "response.output_item.done"
        assert related[-1]["item"] == item
        assert all(event.get("item_id", item["id"]) == item["id"] for event in related)
        if item["type"] == "function_call":
            assert related[0]["item"]["call_id"] == item["call_id"]
            assert related[0]["item"]["arguments"] == ""
            assert "".join(event["delta"] for event in related if event["type"] == "response.function_call_arguments.delta") == item["arguments"]
            done = next(event for event in related if event["type"] == "response.function_call_arguments.done")
            assert done["arguments"] == item["arguments"]
    assert [(item["call_id"], item["arguments"]) for item in output if item["type"] == "function_call"] == [
        ("call_weather", '{"city":"Paris"}'), ("call_time", "{}"),
    ]


@pytest.mark.asyncio
async def test_native_stream_failure_never_completes():
    result = await events([{"error": {"message": "upstream failed"}}])
    assert [event["type"] for event in result] == ["response.created", "response.failed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ValueError("invalid tool"), KeyError("call_id")])
async def test_responses_input_conversion_errors_are_400(error):
    with patch.object(ResponsesRequest, "to_chat_request", side_effect=error):
        response = await responses_api(ResponsesRequest(model="demo", input="hello"), None, None)
    assert response.status_code == 400
    assert json.loads(response.body)["error"]["type"] == "invalid_request_error"


@pytest.mark.asyncio
async def test_native_stream_buffers_arguments_until_call_identity():
    result = await events([
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{"}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_delayed", "function": {"name": "clock", "arguments": "}"}}]}}]},
    ])
    added = next(event for event in result if event["type"] == "response.output_item.added")
    assert added["item"]["call_id"] == "call_delayed"
    assert result[-1]["response"]["output"][0]["arguments"] == "{}"
    assert "".join(event["delta"] for event in result if event["type"] == "response.function_call_arguments.delta") == "{}"


@pytest.mark.asyncio
async def test_native_stream_missing_call_identity_fails():
    result = await events([{"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{}"}}]}}]}])
    assert result[-1]["type"] == "response.failed"


@pytest.mark.asyncio
async def test_native_stream_text_after_tool_uses_its_own_output_index():
    result = await events([
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_clock", "function": {"name": "clock", "arguments": "{}"}}]}}]},
        {"choices": [{"delta": {"content": "Checking."}}]},
    ])
    output = result[-1]["response"]["output"]
    assert [item["type"] for item in output] == ["function_call", "message"]
    text = next(event for event in result if event["type"] == "response.output_text.delta")
    assert text["output_index"] == 1 and text["item_id"] == output[1]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("item", [
    {"type": "function_call", "name": "clock", "arguments": "{}"},
    {"type": "function_call", "call_id": "call_clock", "arguments": "{}"},
    {"type": "function_call_output", "output": "noon"},
])
async def test_responses_invalid_native_tool_items_are_400(item):
    response = await responses_api(ResponsesRequest(model="demo", input=[item]), None, None)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_responses_endpoint_output_can_be_sent_back_as_history():
    with patch("app.api.v1.router._resolve_is_fusion", AsyncMock(return_value=(False, "demo"))), patch(
        "app.api.v1.router.RoutingEngine.route_chat_completions", AsyncMock(return_value=completion())
    ) as route:
        output = await responses_api(ResponsesRequest(model="demo", input="hello"), None, None)
        history = [{"role": "user", "content": "hello"}, *output["output"],
                   {"type": "function_call_output", "call_id": "call_weather", "output": "sunny"},
                   {"type": "function_call_output", "call_id": "call_time", "output": "noon"}]
        await responses_api(ResponsesRequest(model="demo", input=history), None, None)
        request = route.call_args.kwargs["request"]
        calls = [call for message in request.messages for call in message.tool_calls or []]
        assert [call.id for call in calls] == ["call_weather", "call_time"]
        assert [(message.tool_call_id, message.content) for message in request.messages if message.role == "tool"] == [
            ("call_weather", "sunny"), ("call_time", "noon"),
        ]
