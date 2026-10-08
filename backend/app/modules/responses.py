"""Responses wire format shared by the Codex and Grok CLI endpoints."""
import json
from contextlib import aclosing
from typing import Any, AsyncGenerator, AsyncIterator

from app.core.errors import ErrorCategory, RouterException, normalize_upstream_error
from app.schemas.chat import ChatCompletionRequest, ChatMessage


def invalid(message: str):
    raise RouterException(message, ErrorCategory.INVALID_REQUEST, status_code=400)


def messages_to_input(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    items = []
    for msg in messages:
        for detail in msg.reasoning_details or []:
            if detail.get("type") != "reasoning":
                invalid("Unsupported Responses reasoning history type: " + str(detail.get("type")))
            items.append({key: value for key, value in detail.items() if key != "index"})
        if msg.is_error is not None or msg.cache_control is not None:
            invalid("Responses cannot represent Anthropic tool-result or cache metadata")
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
                          "name": call.function.name, "arguments": call.function.arguments,
                          **({"extra_content": call.extra_content} if call.extra_content else {})})
    return items or [{"role": "user", "content": [{"type": "input_text", "text": "Hello"}]}]


def tool_options(request: ChatCompletionRequest) -> dict[str, Any]:
    options = {}
    unsupported = ("temperature", "top_p", "stop", "seed", "response_format",
                   "presence_penalty", "frequency_penalty", "logit_bias", "user", "metadata")
    fields = [key for key in unsupported if getattr(request, key, None) is not None]
    if request.n not in (None, 1):
        fields.append("n")
    if request.reasoning and set(request.reasoning) - {"effort"}:
        fields.append("reasoning")
    # Routing defaults include a thinking budget for other providers; CLI uses effort only.
    if request.thinking and request.thinking != {"type": "disabled"} and (
        "thinking" in getattr(request, "_routing_client_fields", {"thinking"})
        or request.reasoning_effort is None
    ):
        fields.append("thinking")
    if fields:
        raise RouterException("Unsupported CLI options: " + ", ".join(fields),
                              ErrorCategory.INVALID_REQUEST, status_code=422)
    maximum = request.get_effective_max_tokens()
    if maximum is not None:
        options["max_output_tokens"] = maximum
    effort = request.get_effective_reasoning_effort()
    if effort is not None:
        options["reasoning"] = {"effort": effort}
    if request.prompt_cache_key is not None:
        options["prompt_cache_key"] = request.prompt_cache_key
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
    reasoning_seen = set()
    reasoning_items = {}

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

    async with aclosing(lines):
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
                index = event.get("output_index", 0)
                item = reasoning_items.setdefault(index, {"type": "reasoning", "id": event.get("item_id"), "summary": []})
                summary_index = event.get("summary_index", 0)
                while len(item["summary"]) <= summary_index:
                    item["summary"].append({"type": "summary_text", "text": ""})
                item["summary"][summary_index]["text"] += event.get("delta", "")
                yield chunk({"reasoning_content": event.get("delta", ""), "reasoning_details": [{**item, "index": index}]})
            elif kind == "response.content_part.delta":
                delta = event.get("delta", {})
                text_seen = True
                yield chunk({"content": delta.get("text", "") if isinstance(delta, dict) else str(delta)})
            elif kind in ("response.output_item.added", "response.output_item.done"):
                item = event.get("item") or {}
                if item.get("type") not in ("reasoning", "function_call", "message"):
                    invalid("Unsupported Responses output item type: " + str(item.get("type")))
                if item.get("type") == "reasoning":
                    index = event.get("output_index", 0)
                    reasoning_items[index] = item
                    if kind == "response.output_item.done":
                        reasoning_seen.add(item.get("id") or index)
                    yield chunk({"reasoning_details": [{**item, "index": index}]})
                elif item.get("type") == "function_call":
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
                    if item.get("type") not in ("reasoning", "function_call", "message"):
                        invalid("Unsupported Responses output item type: " + str(item.get("type")))
                    if item.get("type") == "message" and any(part.get("type") != "output_text" for part in item.get("content", [])):
                        invalid("Unsupported Responses output content type")
                    if item.get("type") == "reasoning" and (item.get("id") or index) not in reasoning_seen:
                        yield chunk({"reasoning_details": [{**item, "index": index}]})
                    elif item.get("type") == "function_call":
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
                    usage = {target: raw_usage[source] for source, target in (
                        ("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens"),
                        ("total_tokens", "total_tokens"), ("input_tokens_details", "prompt_tokens_details"),
                        ("output_tokens_details", "completion_tokens_details")) if source in raw_usage}
                reason = "length" if kind == "response.incomplete" else ("tool_calls" if calls else "stop")
                yield chunk({}, reason, usage)
                finished = True
                break
    if not finished:
        raise normalize_upstream_error(status_code=502, response_body="Responses stream ended before terminal event")
    yield "data: [DONE]\n\n"
