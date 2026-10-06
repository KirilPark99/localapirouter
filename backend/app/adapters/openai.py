from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import json
import re
import httpx
from app.adapters.base import BaseProviderAdapter, DiscoveredModelData
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.core.http_client import http_client_manager
from app.core.errors import RouterException

def _extract_reasoning_and_content(content: Any) -> Tuple[Optional[str], Any]:
    if not isinstance(content, str):
        return None, content
    pattern = r"<(think|thought|reasoning)>([\s\S]*?)(?:<\/\1>|$)"
    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        reasoning = match.group(2).strip()
        clean_content = (content[:match.start()] + content[match.end():]).strip()
        return reasoning or None, clean_content
    return None, content

def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, dict):
        for k in ("tokens", "context_length", "max_tokens", "context_window", "length", "max_output_tokens"):
            v = val.get(k)
            if v is not None:
                parsed = _safe_int(v)
                if parsed is not None:
                    return parsed
        return None
    if isinstance(val, str):
        try:
            return int(float(val.strip()))
        except (ValueError, TypeError):
            return None
    return None


class GenericOpenAIAdapter(BaseProviderAdapter):
    def _build_headers(
        self,
        api_key: str,
        auth_type: str = "bearer",
        auth_header: str = "Authorization",
        extra_headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update({k: str(v) for k, v in extra_headers.items()})

        if auth_type == "none" or not api_key or api_key in ("no-key", "none", "empty"):
            return headers

        match auth_type:
            case "bearer":
                headers[auth_header or "Authorization"] = f"Bearer {api_key}"
            case "x-api-key":
                headers[auth_header or "x-api-key"] = api_key
            case "custom_header":
                headers[auth_header] = api_key
            case "none":
                pass
            case _:
                headers["Authorization"] = f"Bearer {api_key}"
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
        models_endpoint = configuration.get("models_endpoint", "/models")
        url = f"{base_url.rstrip('/')}/{models_endpoint.lstrip('/')}"
        auth_type = configuration.get("auth_type", "bearer")
        auth_header = configuration.get("auth_header", "Authorization")
        headers = self._build_headers(api_key, auth_type, auth_header, extra_headers)

        params = {}
        if auth_type == "query_param":
            params["key"] = api_key

        try:
            resp = await client.get(url, headers=headers, params=params)
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
        models_list: List[DiscoveredModelData] = []

        # Look for standard OpenAI format {"data": [...]} or {"data": {"models": [...]}} or {"models": [...]} or direct list
        items = None
        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                items = data.get("data")
            elif isinstance(data.get("data"), dict) and isinstance(data.get("data", {}).get("models"), list):
                items = data["data"]["models"]
            elif isinstance(data.get("models"), list):
                items = data.get("models")
        elif isinstance(data, list):
            items = data

        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                model_id = item.get("id") or item.get("name")
                if not model_id:
                    continue
                display_name = item.get("name") or model_id
                raw_ctx = item.get("context_window") or item.get("context_length")
                context_length = _safe_int(raw_ctx)
                raw_max_out = item.get("max_output_tokens") or item.get("max_completion_tokens")
                max_output_tokens = _safe_int(raw_max_out)

                # Capabilities detection
                capabilities = {
                    "chat": True,
                    "streaming": True,
                    "tools": "unknown",
                    "vision": "unknown",
                    "audio_input": "unknown",
                    "audio_output": "unknown",
                    "embeddings": True if "embed" in model_id.lower() else "unknown",
                    "structured_output": "unknown",
                    "reasoning": True if any(r in model_id.lower() for r in ["o1", "o3", "r1", "reasoning", "thinking", "gemma-4", "gemma4", "qwq"]) else "unknown",
                }
                if isinstance(item.get("capabilities"), dict):
                    cap_raw = item["capabilities"]
                    if "vision" in cap_raw:
                        capabilities["vision"] = bool(cap_raw["vision"])
                    if "tools" in cap_raw:
                        capabilities["tools"] = bool(cap_raw["tools"])
                    if "stream" in cap_raw:
                        capabilities["streaming"] = bool(cap_raw["stream"])
                    if "reasoning" in cap_raw:
                        capabilities["reasoning"] = bool(cap_raw["reasoning"])

                models_list.append(
                    DiscoveredModelData(
                        provider_model_id=str(model_id),
                        display_name=str(display_name),
                        capabilities=capabilities,
                        supported_endpoints=["/chat/completions"],
                        context_length=context_length,
                        max_output_tokens=max_output_tokens,
                    )
                )
        return models_list

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
            return True, f"Successfully connected! Found {len(models)} models.", len(models)
        except RouterException as re:
            return False, re.message, 0
        except Exception as e:
            return False, str(e), 0

    def _prepare_payload(self, model_id: str, request: ChatCompletionRequest, base_url: str = "") -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.n is not None and request.n != 1:
            payload["n"] = request.n
        if request.stop is not None:
            payload["stop"] = request.stop
        if request.stream is not None:
            payload["stream"] = request.stream
        if request.stream_options is not None:
            payload["stream_options"] = request.stream_options
        
        # Max tokens translation
        effective_max = request.get_effective_max_tokens()
        if effective_max is not None:
            # Some newer models require max_completion_tokens (like o1/o3), but standard uses max_tokens
            if any(k in model_id.lower() for k in ["o1", "o3"]):
                payload["max_completion_tokens"] = effective_max
            else:
                payload["max_tokens"] = effective_max

        if request.presence_penalty is not None:
            payload["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty is not None:
            payload["frequency_penalty"] = request.frequency_penalty
        if request.logit_bias is not None:
            payload["logit_bias"] = request.logit_bias
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        if request.seed is not None:
            payload["seed"] = request.seed
        if request.tools is not None:
            payload["tools"] = request.tools
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        if request.parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = request.parallel_tool_calls
        if request.user is not None:
            payload["user"] = request.user

        # Reasoning effort handling
        eff_effort = request.get_effective_reasoning_effort() if hasattr(request, "get_effective_reasoning_effort") else request.reasoning_effort
        is_openrouter = "openrouter.ai" in base_url.lower()

        if eff_effort is not None:
            clean_effort = str(eff_effort).strip()
            if clean_effort.lower() in ("off", "none", "disabled"):
                clean_effort = "none"

            if is_openrouter:
                if request.reasoning and isinstance(request.reasoning, dict):
                    payload["reasoning"] = request.reasoning
                else:
                    payload["reasoning"] = {"effort": clean_effort}
            else:
                payload["reasoning_effort"] = clean_effort

            # OpenAI o-series models forbid temperature, top_p, and penalty parameters
            if any(k in model_id.lower() for k in ["o1", "o3"]):
                payload.pop("temperature", None)
                payload.pop("top_p", None)
                payload.pop("presence_penalty", None)
                payload.pop("frequency_penalty", None)
        elif request.reasoning and isinstance(request.reasoning, dict):
            if is_openrouter:
                payload["reasoning"] = request.reasoning
            elif "effort" in request.reasoning:
                payload["reasoning_effort"] = str(request.reasoning["effort"])

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
        chat_endpoint = configuration.get("chat_endpoint", "/chat/completions")
        url = f"{base_url.rstrip('/')}/{chat_endpoint.lstrip('/')}"
        auth_type = configuration.get("auth_type", "bearer")
        auth_header = configuration.get("auth_header", "Authorization")
        headers = self._build_headers(api_key, auth_type, auth_header, extra_headers)

        params = {}
        if auth_type == "query_param":
            params["key"] = api_key

        payload = self._prepare_payload(model_id, request, base_url)
        payload["stream"] = False

        try:
            resp = await client.post(url, headers=headers, params=params, json=payload)
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

        try:
            data = resp.json()
            if not isinstance(data, dict):
                raise self.normalize_error(exception=httpx.RemoteProtocolError("Upstream Chat response must be an object"))
            if data.get("error") is not None:
                error = data["error"]
                code = str(error.get("code")) if isinstance(error, dict) else ""
                status = int(code) if code.isdigit() and 400 <= int(code) <= 599 else 502
                raise self.normalize_error(status_code=status, response_body=data)
            if not isinstance(data.get("choices"), list) or not data["choices"]:
                raise self.normalize_error(exception=httpx.RemoteProtocolError("Upstream Chat response has no choices"))
            normalized = {**data, "model": data.get("model") or model_id, "choices": []}
            for index, choice in enumerate(data["choices"]):
                if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
                    raise self.normalize_error(exception=httpx.RemoteProtocolError("Invalid upstream Chat choice"))
                message = {"role": "assistant", **choice["message"]}
                normalized["choices"].append({"index": index, **choice, "message": message})
            response = ChatCompletionResponse.model_validate(normalized)
            for choice in response.choices:
                if choice.message.content and not choice.message.reasoning_content:
                    reasoning, content = _extract_reasoning_and_content(choice.message.content)
                    if reasoning is not None:
                        choice.message.reasoning_content = reasoning
                        choice.message.content = content
            return response
        except RouterException:
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise self.normalize_error(exception=httpx.RemoteProtocolError(f"Invalid upstream Chat response: {type(exc).__name__}"))

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
        chat_endpoint = configuration.get("chat_endpoint", "/chat/completions")
        url = f"{base_url.rstrip('/')}/{chat_endpoint.lstrip('/')}"
        auth_type = configuration.get("auth_type", "bearer")
        auth_header = configuration.get("auth_header", "Authorization")
        headers = self._build_headers(api_key, auth_type, auth_header, extra_headers)

        params = {}
        if auth_type == "query_param":
            params["key"] = api_key

        payload = self._prepare_payload(model_id, request, base_url)
        payload["stream"] = True

        try:
            async with client.stream("POST", url, headers=headers, params=params, json=payload) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    raise self.normalize_error(status_code=resp.status_code, response_body=err_body.decode("utf-8", errors="ignore"))

                async for line in resp.aiter_lines():
                    clean_line = line.strip()
                    if not clean_line:
                        continue
                    if clean_line.startswith("data: "):
                        yield f"{clean_line}\n\n"
                        if clean_line == "data: [DONE]":
                            break
                    elif clean_line.startswith(":"):
                        # SSE keep-alive comment
                        continue
                    else:
                        yield f"data: {clean_line}\n\n"
        except Exception as e:
            if isinstance(e, RouterException):
                raise
            raise self.normalize_error(exception=e)
