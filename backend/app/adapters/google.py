from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import json
import httpx
from app.adapters.base import BaseProviderAdapter, DiscoveredModelData
from app.adapters.openai import GenericOpenAIAdapter
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from app.core.http_client import http_client_manager
from app.core.errors import RouterException

class GoogleAIStudioAdapter(BaseProviderAdapter):
    def __init__(self):
        self._openai_delegate = GenericOpenAIAdapter()

    async def list_models(
        self,
        base_url: str,
        api_key: str,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> List[DiscoveredModelData]:
        """Fetch actual available models for this Google AI Studio API key using Gemini v1beta API."""
        client = await http_client_manager.get_client(proxy_url=proxy_url, timeout=timeout)
        
        # Primary: Google AI Studio native discovery endpoint
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        params = {"key": api_key}
        headers = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update({k: str(v) for k, v in extra_headers.items()})

        try:
            resp = await client.get(url, headers=headers, params=params)
        except Exception as e:
            raise self.normalize_error(exception=e)

        if resp.status_code != 200:
            # If native endpoint failed, try openai-compatible endpoint
            try:
                openai_base = base_url.rstrip("/") if base_url else "https://generativelanguage.googleapis.com/v1beta/openai"
                return await self._openai_delegate.list_models(
                    base_url=openai_base,
                    api_key=api_key,
                    extra_headers=extra_headers,
                    configuration={"auth_type": "bearer"},
                    proxy_url=proxy_url,
                    timeout=timeout,
                )
            except Exception:
                retry_after = None
                if "Retry-After" in resp.headers:
                    try:
                        retry_after = float(resp.headers["Retry-After"])
                    except Exception:
                        pass
                raise self.normalize_error(status_code=resp.status_code, response_body=resp.text, retry_after=retry_after)

        data = resp.json()
        models_raw = data.get("models", [])
        discovered: List[DiscoveredModelData] = []

        for m in models_raw:
            raw_name = m.get("name", "")  # e.g. "models/gemini-2.5-flash"
            model_id = raw_name.replace("models/", "")
            methods = m.get("supportedGenerationMethods", [])
            # Only include models capable of generating content
            if "generateContent" not in methods and "chat" not in methods:
                continue

            display_name = m.get("displayName") or model_id
            input_limit = m.get("inputTokenLimit")
            output_limit = m.get("outputTokenLimit")

            is_vision = any(term in model_id.lower() for term in ["flash", "pro", "vision", "gemini"])
            is_thinking = any(term in model_id.lower() for term in ["thinking", "reasoning", "2.5-pro", "3.", "gemma-4", "gemma4"])

            capabilities = {
                "chat": True,
                "streaming": True,
                "tools": True,
                "vision": is_vision,
                "audio_input": True if "gemini" in model_id.lower() else "unknown",
                "audio_output": "unknown",
                "embeddings": "embedContent" in methods,
                "structured_output": True,
                "reasoning": is_thinking,
            }

            discovered.append(
                DiscoveredModelData(
                    provider_model_id=model_id,
                    display_name=display_name,
                    capabilities=capabilities,
                    supported_endpoints=["/chat/completions", "/responses"],
                    context_length=input_limit,
                    max_output_tokens=output_limit,
                )
            )

        return discovered

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
            return True, f"Google AI Studio key verified! Discovered {len(models)} Gemini models.", len(models)
        except RouterException as re:
            return False, re.message, 0
        except Exception as e:
            return False, str(e), 0

    def _get_effective_base_url(self, base_url: str) -> str:
        if not base_url or base_url.strip() in ("https://generativelanguage.googleapis.com", "https://generativelanguage.googleapis.com/v1beta"):
            return "https://generativelanguage.googleapis.com/v1beta/openai"
        return base_url.rstrip("/")

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
        effective_base = self._get_effective_base_url(base_url)
        clean_model_id = model_id.replace("models/", "")
        return await self._openai_delegate.chat_completions(
            base_url=effective_base,
            api_key=api_key,
            model_id=clean_model_id,
            request=request,
            extra_headers=extra_headers,
            configuration={"chat_endpoint": "/chat/completions", "auth_type": "bearer"},
            proxy_url=proxy_url,
            timeout=timeout,
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
        effective_base = self._get_effective_base_url(base_url)
        clean_model_id = model_id.replace("models/", "")
        async for chunk in self._openai_delegate.stream_chat(
            base_url=effective_base,
            api_key=api_key,
            model_id=clean_model_id,
            request=request,
            extra_headers=extra_headers,
            configuration={"chat_endpoint": "/chat/completions", "auth_type": "bearer"},
            proxy_url=proxy_url,
            timeout=timeout,
        ):
            yield chunk
