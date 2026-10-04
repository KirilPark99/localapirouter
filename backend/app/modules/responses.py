"""Responses wire format shared by the Codex and Grok CLI endpoints."""
import json
from typing import Any, AsyncGenerator, AsyncIterator

from app.core.errors import ErrorCategory, RouterException, normalize_upstream_error
from app.schemas.chat import ChatCompletionRequest, ChatMessage


def invalid(message: str):
    raise RouterException(message, ErrorCategory.INVALID_REQUEST, status_code=400)


def messages_to_input(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    items = []
    for msg in messages:
        if msg.role in ("tool", "function"):
            if not msg.tool_call_id:
                invalid("Tool results require a non-empty tool_call_id")
            items.append({"type": "function_call_output", "call_id": msg.tool_call_id,
                          "output": msg.content if isinstance(msg.content, str) else json.dumps(msg.content)})
            continue
        if msg.content is not None:
            content = msg.content
            if isinstance(content, str):
                content = [{"type": "output_text" if msg.role == "assistant" else "input_text", "text": content}]
            else:
                content = [dict(part) for part in content]
                for part in content:
                    if part.get("type") in ("text", "input_text", "output_text"):
                        part["type"] = "output_text" if msg.role == "assistant" else "input_text"
                    elif part.get("type") == "image_url":
                        image = part["image_url"]
                        part.clear()
                        part.update(type="input_image", image_url=image["url"] if isinstance(image, dict) else image)
                        if isinstance(image, dict) and image.get("detail"):
                            part["detail"] = image["detail"]
            items.append({"role": msg.role, "content": content})
        for call in msg.tool_calls or []:
            if not call.id:
                invalid("Assistant tool calls require a non-empty id")
            items.append({"type": "function_call", "call_id": call.id,
                          "name": call.function.name, "arguments": call.function.arguments})
    return items or [{"role": "user", "content": [{"type": "input_text", "text": "Hello"}]}]


def tool_options(request: ChatCompletionRequest) -> dict[str, Any]:
    options = {}
    if request.tools is not None:
        tools = []
        for tool in request.tools:
            if tool.get("type") != "function":
                invalid("CLI adapters support function tools only")
            function = tool.get("function", tool)
            if not isinstance(function, dict) or not function.get("name"):
                invalid("Function tools require a name")
            tools.append({"type": "function", **{k: function[k] for k in
                         ("name", "description", "parameters", "strict") if k in function}})
        options["tools"] = tools
    if request.tool_choice is not None:
        choice = request.tool_choice
        if isinstance(choice, dict):
            name = (choice.get("function") or {}).get("name") or choice.get("name")
            if choice.get("type") != "function" or not name:
                invalid("Invalid function tool_choice")
            choice = {"type": "function", "name": name}
        elif choice not in ("auto", "none", "required"):
            invalid("Invalid tool_choice")
        options["tool_choice"] = choice
    if request.parallel_tool_calls is not None:
        options["parallel_tool_calls"] = request.parallel_tool_calls
    return options


async def responses_to_chat(lines: AsyncIterator[str], model: str,
                            chunk_id: str, created: int) -> AsyncGenerator[str, None]:
    calls: dict[int, dict] = {}
    text_seen = False
    finished = False

    def chunk(delta: dict, finish_reason=None, usage=None):
        payload = {"id": chunk_id, "object": "chat.completion.chunk", "created": created,
                   "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]}
        if usage is not None:
            payload["usage"] = usage
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def call_delta(output_index: int, item: dict, arguments=None):
        output_index = next((i for i, c in calls.items() if c["id"] == item.get("call_id")), output_index)
        state = calls.get(output_index)
        if state is None:
            state = {"index": len(calls), "id": item.get("call_id") or item.get("id"),
                     "name": item.get("name", ""), "arguments": "", "item_id": item.get("id")}
            if not state["id"] or not state["name"]:
                invalid("Upstream function call is missing call_id or name")
            calls[output_index] = state
            function = {"name": state["name"], "arguments": arguments or item.get("arguments") or ""}
            state["arguments"] = function["arguments"]
            return {"tool_calls": [{"index": state["index"], "id": state["id"], "type": "function", "function": function}]}
        # Done/completed events may repeat arguments already emitted as deltas.
        full = arguments if arguments is not None else item.get("arguments", "")
        emitted = state["arguments"]
        if full and full != emitted:
            if not full.startswith(emitted):
                invalid("Upstream function arguments changed after streaming")
            suffix = full[len(emitted):]
            state["arguments"] = full
            return {"tool_calls": [{"index": state["index"], "function": {"arguments": suffix}}]}
        return None

    async for line in lines:
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = event.get("type", "")
        if kind in ("error", "response.failed"):
            error = event.get("error") or event.get("response", {}).get("error") or event
            raise normalize_upstream_error(status_code=event.get("status") or 502, response_body={"error": error})
        if kind in ("response.output_text.delta", "response.text.delta"):
            text_seen = True
            yield chunk({"content": event.get("delta", "")})
        elif kind in ("response.reasoning_summary_part.delta", "response.reasoning.delta", "response.reasoning_summary_text.delta"):
            yield chunk({"reasoning_content": event.get("delta", "")})
        elif kind == "response.content_part.delta":
            delta = event.get("delta", {})
            text_seen = True
            yield chunk({"content": delta.get("text", "") if isinstance(delta, dict) else str(delta)})
        elif kind in ("response.output_item.added", "response.output_item.done"):
            item = event.get("item") or {}
            if item.get("type") == "function_call":
                delta = call_delta(event.get("output_index", 0), item)
                if delta:
                    yield chunk(delta)
        elif kind == "response.function_call_arguments.delta":
            index = event.get("output_index")
            if index not in calls:
                index = next((i for i, c in calls.items() if c["item_id"] == event.get("item_id")), index)
            if index not in calls:
                invalid("Upstream function argument delta arrived without a function call")
            state = calls[index]
            args = event.get("delta", "")
            state["arguments"] += args
            yield chunk({"tool_calls": [{"index": state["index"], "function": {"arguments": args}}]})
        elif kind == "response.function_call_arguments.done":
            index = event.get("output_index", 0)
            delta = call_delta(index, event, event.get("arguments", ""))
            if delta:
                yield chunk(delta)
        elif kind in ("response.completed", "response.incomplete"):
            response = event.get("response") or {}
            for index, item in enumerate(response.get("output") or []):
                if item.get("type") == "function_call":
                    delta = call_delta(index, item)
                    if delta:
                        yield chunk(delta)
                elif item.get("type") == "message" and not text_seen:
                    for part in item.get("content", []):
                        if part.get("type") == "output_text":
                            yield chunk({"content": part.get("text", "")})
            raw_usage = response.get("usage")
            usage = None
            if raw_usage:
                usage = {"prompt_tokens": raw_usage.get("input_tokens", 0),
                         "completion_tokens": raw_usage.get("output_tokens", 0),
                         "total_tokens": raw_usage.get("total_tokens", 0)}
            reason = "length" if kind == "response.incomplete" else ("tool_calls" if calls else "stop")
            yield chunk({}, reason, usage)
            finished = True
            break
    if not finished:
        yield chunk({}, "tool_calls" if calls else "stop")
    yield "data: [DONE]\n\n"
