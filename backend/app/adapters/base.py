from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse, UsageInfo
from app.core.errors import RouterException, normalize_upstream_error

class DiscoveredModelData(BaseModel):
    provider_model_id: str
    display_name: str
    capabilities: Dict[str, Any] = Field(default_factory=lambda: {
        "chat": True,
        "streaming": True,
        "tools": "unknown",
        "vision": "unknown",
        "audio_input": "unknown",
        "audio_output": "unknown",
        "embeddings": "unknown",
        "structured_output": "unknown",
        "reasoning": "unknown",
    })
    supported_endpoints: List[str] = Field(default_factory=lambda: ["/chat/completions"])
    context_length: Optional[int] = None
    max_output_tokens: Optional[int] = None

class BaseProviderAdapter(ABC):
    @abstractmethod
    async def list_models(
        self,
        base_url: str,
        api_key: str,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> List[DiscoveredModelData]:
        """Fetch available models from upstream provider API."""
        pass

    @abstractmethod
    async def validate_credentials(
        self,
        base_url: str,
        api_key: str,
        extra_headers: Dict[str, Any],
        configuration: Dict[str, Any],
        proxy_url: Optional[str] = None,
        timeout: float = 15.0,
    ) -> Tuple[bool, str, int]:
        """Validate if credentials work. Returns (success, message, models_found_count)."""
        pass

    @abstractmethod
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
        """Execute chat completion request to upstream."""
        pass

    @abstractmethod
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
        """Yield SSE data lines for streaming: data: {...}\n\n"""
        pass

    def normalize_error(
        self,
        status_code: Optional[int] = None,
        response_body: Optional[Any] = None,
        exception: Optional[Exception] = None,
        retry_after: Optional[float] = None,
    ) -> RouterException:
        return normalize_upstream_error(status_code, response_body, exception, retry_after)
