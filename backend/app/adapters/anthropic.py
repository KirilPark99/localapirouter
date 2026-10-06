from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import json
import uuid
import httpx
from app.adapters.base import BaseProviderAdapter, DiscoveredModelData
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
    ToolCall,
    FunctionCall,
)
from app.core.http_client import http_client_manager
from app.core.errors import RouterException

class AnthropicAdapter(BaseProviderAdapter):
    def _build_headers(self, api_key: str, extra_headers: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if extra_headers:
            headers.update({k: str(v) for k, v in extra_headers.items()})
        return headers

    async def list_models(
        self,
        base_url: str,
        api_key: str,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> List[DiscoveredModelData]:
        client = await http_client_manager.get_client(proxy_url=proxy_url, timeout=timeout)
        url = f"{base_url.rstrip('/')}/v1/models"
        headers = self._build_headers(api_key, extra_headers)

        try:
            resp = await client.get(url, headers=headers)
        except Exception as e:
            raise self.normalize_error(exception=e)

        if resp.status_code == 200:
            data = resp.json()
            if not isinstance(data, dict) or not isinstance(data.get("data", []), list):
                raise self.normalize_error(exception=httpx.RemoteProtocolError("Invalid Anthropic models page"))
            models_data = list(data.get("data", []))
            seen_pages = set()
            while data.get("has_more") is True:
                cursor = data.get("last_id")
                if not isinstance(cursor, str) or not cursor or cursor in seen_pages or len(seen_pages) >= 1000:
                    raise self.normalize_error(exception=httpx.RemoteProtocolError("Invalid or repeated Anthropic pagination cursor"))
                seen_pages.add(cursor)
                try:
                    resp = await client.get(url, headers=headers, params={"after_id": cursor})
                except Exception as exc:
                    raise self.normalize_error(exception=exc)
                if resp.status_code != 200:
                    raise self.normalize_error(status_code=resp.status_code, response_body=resp.text)
                data = resp.json()
                if not isinstance(data, dict) or not isinstance(data.get("data", []), list):
                    raise self.normalize_error(exception=httpx.RemoteProtocolError("Invalid Anthropic models page"))
                models_data.extend(data.get("data", []))
            discovered: List[DiscoveredModelData] = []
            seen_models = set()
            for m in models_data:
                mid = m.get("id")
                if not mid or mid in seen_models:
                    continue
                seen_models.add(mid)
                name = m.get("display_name") or mid
                discovered.append(
                    DiscoveredModelData(
                        provider_model_id=mid,
                        display_name=name,
                        capabilities={
                            "chat": True,
                            "streaming": True,
                            "tools": True,
                            "vision": True,
                            "audio_input": False,
                            "audio_output": False,
                            "embeddings": False,
                            "structured_output": True,
                            "reasoning": True if "thinking" in mid.lower() or "3-7" in mid.lower() else "unknown",
                        },
                        supported_endpoints=["/chat/completions", "/v1/messages"],
                        context_length=200000,
                        max_output_tokens=8192,
                    )
                )
            if discovered:
                return discovered

        # Fallback catalog if models endpoint is unavailable or returns 404
        if resp.status_code != 200:
            retry_after = None
            if "Retry-After" in resp.headers:
                try:
                    retry_after = float(resp.headers["Retry-After"])
                except Exception:
                    pass
            raise self.normalize_error(status_code=resp.status_code, response_body=resp.text, retry_after=retry_after)

        return []

    async def validate_credentials(
        self,
        base_url: str,
        api_key: str,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 15.0,
    ) -> Tuple[bool, str, int]:
        try:
            models = await self.list_models(
                base_url=base_url,
                api_key=api_key,
                extra_headers=extra_headers,
                configuration=configuration,
                proxy_url=proxy_url,
                timeout=timeout,
            )
            return True, f"Anthropic key verified! Found {len(models)} models.", len(models)
        except RouterException as re:
            return False, re.message, 0
        except Exception as e:
            return False, str(e), 0

    def _convert_messages_to_anthropic(self, messages: List[ChatMessage]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        def blocks(content):
            if content is None or content == "":
                return []
            if isinstance(content, str):
                return [{"type": "text", "text": content}]
            converted = []
            for part in content:
                kind = part.get("type")
                if kind == "image_url":
                    image = part.get("image_url", {})
                    url = image if isinstance(image, str) else image.get("url", "")
                    if not isinstance(url, str) or not url:
                        raise self.normalize_error(status_code=400, response_body="Image requires a URL")
                    if url.startswith("data:"):
                        meta, sep, data = url[5:].partition(",")
                        if not sep or not meta.endswith(";base64"):
                            raise self.normalize_error(status_code=400, response_body="Image data URL must be base64")
                        source = {"type": "base64", "media_type": meta[:-7], "data": data}
                    else:
                        source = {"type": "url", "url": url}
                    converted.append({"type": "image", "source": source})
                elif kind in ("text", "image", "thinking", "redacted_thinking", "tool_use", "tool_result"):
                    converted.append(dict(part))
                else:
                    raise self.normalize_error(status_code=400, response_body=f"Unsupported Anthropic content block: {kind}")
            return converted

        system_prompts = []
        anthropic_msgs = []
        for message in messages:
            if message.role in ("system", "developer"):
                system_prompts.extend(p["text"] for p in blocks(message.content) if p.get("type") == "text")
                continue
            role = "assistant" if message.role == "assistant" else "user"
            if message.role in ("tool", "function"):
                if not message.tool_call_id:
                    raise self.normalize_error(status_code=400, response_body="Anthropic tool results require tool_call_id")
                content = [{"type": "tool_result", "tool_use_id": message.tool_call_id,
                            "content": message.content if isinstance(message.content, str) else blocks(message.content)}]
            else:
                content = [{k: value for k, value in detail.items() if k != "index"}
                           for detail in (message.reasoning_details or [])
                           if detail.get("type") in ("thinking", "redacted_thinking")]
                content.extend(blocks(message.content))
                for call in message.tool_calls or []:
                    try:
                        arguments = json.loads(call.function.arguments or "{}")
                    except (ValueError, TypeError):
                        raise self.normalize_error(status_code=400, response_body="Tool arguments must be a JSON object")
                    if not isinstance(arguments, dict):
                        raise self.normalize_error(status_code=400, response_body="Tool arguments must be a JSON object")
                    content.append({"type": "tool_use", "id": call.id, "name": call.function.name, "input": arguments})
            if anthropic_msgs and anthropic_msgs[-1]["role"] == role:
                anthropic_msgs[-1]["content"].extend(content)
            else:
                anthropic_msgs.append({"role": role, "content": content})
        if not anthropic_msgs:
            anthropic_msgs = [{"role": "user", "content": "Hello"}]
        elif anthropic_msgs[0]["role"] != "user":
            anthropic_msgs.insert(0, {"role": "user", "content": "Begin conversation."})
        return "\n\n".join(system_prompts) if system_prompts else None, anthropic_msgs

    def _prepare_payload(self, model_id: str, request: ChatCompletionRequest) -> Dict[str, Any]:
        system_str, messages = self._convert_messages_to_anthropic(request.messages)
        max_tokens = request.get_effective_max_tokens() or 4096

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system_str:
            payload["system"] = system_str
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.stop:
            payload["stop_sequences"] = [request.stop] if isinstance(request.stop, str) else request.stop

        if request.tools:
            tools_list = []
            for t in request.tools:
                fn = t.get("function", {})
                tools_list.append({
                    "name": fn.get("name", "tool"),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                })
            payload["tools"] = tools_list
        if request.tool_choice is not None or (request.tools and request.parallel_tool_calls is not None):
            choice = request.tool_choice or "auto"
            if isinstance(choice, str):
                if choice not in ("auto", "none", "required"):
                    raise self.normalize_error(status_code=400, response_body="Unsupported tool_choice")
                payload["tool_choice"] = {"type": "any" if choice == "required" else choice}
            elif choice.get("type") == "function" and choice.get("function", {}).get("name"):
                payload["tool_choice"] = {"type": "tool", "name": choice["function"]["name"]}
            else:
                raise self.normalize_error(status_code=400, response_body="Unsupported tool_choice")
            if request.parallel_tool_calls is not None and payload["tool_choice"]["type"] != "none":
                payload["tool_choice"]["disable_parallel_tool_use"] = not request.parallel_tool_calls

        # Anthropic thinking parameter translation
        eff_budget = request.get_effective_thinking_budget() if hasattr(request, "get_effective_thinking_budget") else None
        if eff_budget is not None:
            if eff_budget <= 0:
                payload.pop("thinking", None)
            else:
                budget_tokens = max(eff_budget, 1024)
                payload["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
                payload.pop("temperature", None)
                current_max = payload.get("max_tokens", 4096)
                if current_max <= budget_tokens:
                    payload["max_tokens"] = budget_tokens + 4096
        elif request.thinking is not None:
            if isinstance(request.thinking, dict) and request.thinking.get("type") == "disabled":
                payload.pop("thinking", None)
            else:
                payload["thinking"] = request.thinking
                payload.pop("temperature", None)

        return payload

    async def chat_completions(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        request: ChatCompletionRequest,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> ChatCompletionResponse:
        client = await http_client_manager.get_client(proxy_url=proxy_url, timeout=timeout)
        url = f"{base_url.rstrip('/')}/v1/messages"
        headers = self._build_headers(api_key, extra_headers)
        payload = self._prepare_payload(model_id, request)
        payload["stream"] = False

        try:
            resp = await client.post(url, headers=headers, json=payload)
        except Exception as e:
            raise self.normalize_error(exception=e)

        if resp.status_code != 200:
            retry_after = None
            if "Retry-After" in resp.headers:
                try:
                    retry_after = float(resp.headers["Retry-After"])
                except Exception:
                    pass
            raise self.normalize_error(status_code=resp.status_code, response_body=resp.text, retry_after=retry_after)

        data = resp.json()
        content_text = ""
        tool_calls = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                content_text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                        function=FunctionCall(
                            name=block.get("name", ""),
                            arguments=json.dumps(block.get("input", {})),
                        ),
                    )
                )

        usage_raw = data.get("usage", {})
        prompt_tokens = usage_raw.get("input_tokens", 0)
        completion_tokens = usage_raw.get("output_tokens", 0)

        finish_reason = "stop"
        if data.get("stop_reason") == "tool_use":
            finish_reason = "tool_calls"
        elif data.get("stop_reason") == "max_tokens":
            finish_reason = "length"

        return ChatCompletionResponse(
            id=data.get("id", f"chatcmpl-{uuid.uuid4().hex}"),
            model=data.get("model", model_id),
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=content_text if content_text or not tool_calls else None,
                        tool_calls=tool_calls if tool_calls else None,
                    ),
                    finish_reason=finish_reason,
                )
            ],
            usage=UsageInfo(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    async def stream_chat(self, base_url: str, api_key: str, model_id: str, request: ChatCompletionRequest,
                          extra_headers: Dict[str, Any], configuration: Dict[str, Any],
                          proxy_url: Optional[str] = None, timeout: float = 60.0) -> AsyncGenerator[str, None]:
        client = await http_client_manager.get_client(proxy_url=proxy_url, timeout=timeout)
        url = f"{base_url.rstrip('/')}/v1/messages"
        payload = {**self._prepare_payload(model_id, request), "stream": True}
        cmpl_id = f"chatcmpl-{uuid.uuid4().hex}"
        usage = {}; tool_indices = {}; finish = None
        def chunk(delta, finish_reason=None, final_usage=None):
            value = {"id": cmpl_id, "object": "chat.completion.chunk", "model": model_id,
                     "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]}
            if final_usage is not None:
                value["choices"] = []; value["usage"] = final_usage
            return "data: " + json.dumps(value) + "\n\n"
        try:
            async with client.stream("POST", url, headers=self._build_headers(api_key, extra_headers), json=payload) as resp:
                if resp.status_code != 200:
                    error = (await resp.aread()).decode("utf-8", errors="replace")
                    raise self.normalize_error(status_code=resp.status_code, response_body=error)
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except ValueError:
                        raise self.normalize_error(exception=httpx.RemoteProtocolError("Invalid Anthropic SSE JSON"))
                    if not isinstance(event, dict):
                        raise self.normalize_error(exception=httpx.RemoteProtocolError("Invalid Anthropic SSE event"))
                    kind = event.get("type"); delta = event.get("delta") or {}; index = event.get("index", 0)
                    if kind == "error":
                        err = event.get("error") or {}
                        status = {"overloaded_error": 529, "rate_limit_error": 429, "authentication_error": 401,
                                  "permission_error": 403, "invalid_request_error": 400}.get(err.get("type"), 502)
                        raise self.normalize_error(status_code=status, response_body=event)
                    if kind == "message_start":
                        message = event.get("message") or {}
                        cmpl_id = message.get("id", cmpl_id); usage.update(message.get("usage") or {})
                        yield chunk({"role": "assistant"})
                    elif kind == "content_block_start":
                        block = event.get("content_block") or {}; block_type = block.get("type")
                        if block_type == "tool_use":
                            tool_indices[index] = len(tool_indices)
                            yield chunk({"tool_calls": [{"index": tool_indices[index], "id": block["id"], "type": "function",
                                "function": {"name": block["name"], "arguments": json.dumps(block["input"]) if block.get("input") else ""}}]})
                        elif block_type in ("thinking", "redacted_thinking"):
                            yield chunk({"reasoning_details": [{**block, "index": index}]})
                        elif block_type == "text" and block.get("text"):
                            yield chunk({"content": block["text"]})
                    elif kind == "content_block_delta":
                        delta_type = delta.get("type")
                        if delta_type == "text_delta":
                            yield chunk({"content": delta.get("text", "")})
                        elif delta_type == "input_json_delta":
                            if index not in tool_indices:
                                raise self.normalize_error(exception=httpx.RemoteProtocolError("Tool delta without tool block"))
                            yield chunk({"tool_calls": [{"index": tool_indices[index], "function": {"arguments": delta.get("partial_json", "")}}]})
                        elif delta_type in ("thinking_delta", "signature_delta"):
                            field = "thinking" if delta_type == "thinking_delta" else "signature"
                            converted = {"reasoning_details": [{"type": "thinking", "index": index, field: delta.get(field, "")}]}
                            if field == "thinking": converted["reasoning_content"] = delta.get(field, "")
                            yield chunk(converted)
                    elif kind == "message_delta":
                        usage.update(event.get("usage") or {})
                        reason = delta.get("stop_reason")
                        if reason:
                            finish = {"tool_use": "tool_calls", "max_tokens": "length", "end_turn": "stop", "stop_sequence": "stop"}.get(reason, reason)
                            yield chunk({}, finish)
                    elif kind == "message_stop":
                        if not finish:
                            raise self.normalize_error(exception=httpx.RemoteProtocolError("Anthropic message stopped without finish reason"))
                        prompt = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
                        completion = usage.get("output_tokens", 0)
                        info = {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}
                        if usage.get("cache_read_input_tokens"):
                            info["prompt_tokens_details"] = {"cached_tokens": usage["cache_read_input_tokens"]}
                        yield chunk({}, final_usage=info)
                        yield "data: [DONE]\n\n"
                        return
                raise self.normalize_error(exception=httpx.RemoteProtocolError("Anthropic stream ended before message_stop"))
        except RouterException:
            raise
        except Exception as exc:
            raise self.normalize_error(exception=exc)
