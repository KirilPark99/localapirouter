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
            models_data = data.get("data", [])
            discovered: List[DiscoveredModelData] = []
            for m in models_data:
                mid = m.get("id")
                if not mid:
                    continue
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

    def _convert_messages_to_anthropic(
        self, messages: List[ChatMessage]
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        system_prompts: List[str] = []
        anthropic_msgs: List[Dict[str, Any]] = []

        for m in messages:
            if m.role == "system":
                if isinstance(m.content, str):
                    system_prompts.append(m.content)
                elif isinstance(m.content, list):
                    text_parts = [p.get("text", "") for p in m.content if isinstance(p, dict) and p.get("type") == "text"]
                    system_prompts.append("\n".join(text_parts))
            else:
                role = "assistant" if m.role == "assistant" else "user"
                content_val = m.content or ""
                
                # Merge consecutive identical roles
                if anthropic_msgs and anthropic_msgs[-1]["role"] == role:
                    prev_content = anthropic_msgs[-1]["content"]
                    if isinstance(prev_content, str) and isinstance(content_val, str):
                        anthropic_msgs[-1]["content"] = f"{prev_content}\n\n{content_val}"
                    else:
                        anthropic_msgs.append({"role": role, "content": content_val})
                else:
                    anthropic_msgs.append({"role": role, "content": content_val})

        # Ensure first message is user
        if not anthropic_msgs:
            anthropic_msgs = [{"role": "user", "content": "Hello"}]
        elif anthropic_msgs[0]["role"] != "user":
            anthropic_msgs.insert(0, {"role": "user", "content": "Begin conversation."})

        system_str = "\n\n".join(system_prompts) if system_prompts else None
        return system_str, anthropic_msgs

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

    async def stream_chat(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        request: ChatCompletionRequest,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> AsyncGenerator[str, None]:
        client = await http_client_manager.get_client(proxy_url=proxy_url, timeout=timeout)
        url = f"{base_url.rstrip('/')}/v1/messages"
        headers = self._build_headers(api_key, extra_headers)
        payload = self._prepare_payload(model_id, request)
        payload["stream"] = True

        cmpl_id = f"chatcmpl-{uuid.uuid4().hex}"

        try:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    raise self.normalize_error(status_code=resp.status_code, response_body=err_body.decode("utf-8", errors="ignore"))

                async for line in resp.aiter_lines():
                    clean_line = line.strip()
                    if not clean_line or clean_line.startswith("event:") or clean_line.startswith(":"):
                        continue
                    if clean_line.startswith("data: "):
                        raw_data = clean_line[6:].strip()
                        try:
                            event = json.loads(raw_data)
                            event_type = event.get("type")
                            if event_type == "content_block_delta":
                                delta_text = event.get("delta", {}).get("text", "")
                                chunk = {
                                    "id": cmpl_id,
                                    "object": "chat.completion.chunk",
                                    "model": model_id,
                                    "choices": [{"index": 0, "delta": {"content": delta_text}, "finish_reason": None}],
                                }
                                yield f"data: {json.dumps(chunk)}\n\n"
                            elif event_type == "message_delta":
                                stop_reason = event.get("delta", {}).get("stop_reason")
                                finish = "stop" if stop_reason == "end_turn" else (stop_reason or None)
                                chunk = {
                                    "id": cmpl_id,
                                    "object": "chat.completion.chunk",
                                    "model": model_id,
                                    "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                                }
                                yield f"data: {json.dumps(chunk)}\n\n"
                            elif event_type == "message_stop":
                                yield "data: [DONE]\n\n"
                                break
                        except Exception:
                            continue
        except Exception as e:
            if isinstance(e, RouterException):
                raise
            raise self.normalize_error(exception=e)
