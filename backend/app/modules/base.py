import os
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict
import httpx

from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.adapters.base import DiscoveredModelData


class ModuleField(BaseModel):
    """Defines a configuration / credential field required by the custom module."""
    key: str
    label: str
    type: str = "text"  # "text" | "password" | "textarea" | "number" | "select"
    required: bool = True
    default: Optional[Any] = None
    placeholder: Optional[str] = None
    description: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None  # For select fields: [{"label": "...", "value": "..."}]


class ModuleDefaultModel(BaseModel):
    """Default model exposed by the module if live model listing is not dynamically available."""
    id: str
    name: str
    context_length: Optional[int] = 32768
    max_output_tokens: Optional[int] = 4096
    reasoning_effort: Optional[str] = None
    capabilities: Dict[str, Any] = Field(default_factory=lambda: {
        "chat": True,
        "streaming": True,
        "vision": "unknown",
        "tools": "unknown",
        "reasoning": "unknown",
    })


class ModuleManifest(BaseModel):
    """Manifest describing a custom provider module."""
    id: str  # Unique slug, e.g. "codex_oauth", "deepseek_web"
    name: str  # Display name, e.g. "Codex OAuth Provider"
    version: str = "1.0.0"
    description: str = ""
    author: Optional[str] = None
    icon: Optional[str] = "Puzzle"  # Lucide icon name, e.g. "Puzzle", "Bot", "MessageSquare", "KeyRound"
    auth_type: str = "custom_fields"  # "custom_fields" | "oauth_device" | "bearer"
    fields: List[ModuleField] = Field(default_factory=list)
    default_models: List[ModuleDefaultModel] = Field(default_factory=list)
    folder_path: Optional[str] = None


class ModuleExecutionContext(BaseModel):
    """Runtime execution context passed to custom module handlers."""
    credentials: Dict[str, Any] = Field(default_factory=dict)
    proxy_url: Optional[str] = None
    model_id: str = ""
    timeout: float = 60.0
    extra_config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class BaseModuleAdapter(ABC):
    """
    Base class that all custom modules in `backend/modules/<name>/handler.py` must inherit from.
    """

    @abstractmethod
    async def validate_credentials(
        self,
        ctx: ModuleExecutionContext,
    ) -> Tuple[bool, str, int]:
        """
        Validate whether the given credentials and proxy connection are healthy and working.
        Returns: (success: bool, message: str, models_found_count: int)
        """
        pass

    @abstractmethod
    async def list_models(
        self,
        ctx: ModuleExecutionContext,
    ) -> List[DiscoveredModelData]:
        """
        Fetch or return the list of available models for this module profile.
        """
        pass

    @abstractmethod
    async def chat_completions(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> ChatCompletionResponse:
        """
        Execute a standard non-streaming chat completion request.
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        request: ChatCompletionRequest,
        ctx: ModuleExecutionContext,
    ) -> AsyncGenerator[str, None]:
        """
        Execute a streaming chat completion request, yielding Server-Sent Events (SSE) data chunks:
        e.g. data: {"id":"...","choices":[{"delta":{"content":"..."}}]}\n\n
        Followed by: data: [DONE]\n\n
        """
        pass

    def create_http_client(
        self,
        ctx: ModuleExecutionContext,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.AsyncClient:
        """
        Helper method to create an async HTTPX client preconfigured with the assigned proxy (if any).
        Supports HTTP, HTTPS, SOCKS5, and SOCKS5H proxies.
        """
        client_kwargs: Dict[str, Any] = {
            "timeout": timeout or ctx.timeout or 60.0,
            "follow_redirects": True,
        }
        if headers:
            client_kwargs["headers"] = headers

        if ctx.proxy_url:
            client_kwargs["proxy"] = ctx.proxy_url

        return httpx.AsyncClient(**client_kwargs)
