from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.chat import ChatMessage


class StageConfigField(BaseModel):
    """Defines a configurable setting for a compression stage."""
    key: str
    label: str
    type: str  # "boolean" | "number" | "text" | "select" | "textarea"
    default_value: Any
    description: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None  # For select fields: [{"label": "...", "value": "..."}]
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class CompressionContext(BaseModel):
    """Runtime context passed to compression stages."""
    model_id: str = ""
    supports_vision: bool = False
    original_tokens: int = 0
    preserve_recent_turns: int = 1
    preserve_system_prompt: bool = False
    request_headers: Dict[str, str] = Field(default_factory=dict)
    principal_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StageExecutionResult(BaseModel):
    """Result of running a single compression stage."""
    stage_id: str
    stage_name: str
    messages: List[ChatMessage]
    compressed: bool = False
    tokens_before: int = 0
    tokens_after: int = 0
    savings_percent: float = 0.0
    duration_ms: float = 0.0
    rules_applied: List[str] = Field(default_factory=list)
    warning: Optional[str] = None


class BaseCompressionStage(ABC):
    """
    Abstract base class that all compression stage modules must implement.
    """
    id: str                 # Unique slug: "lite", "rtk", "caveman", etc.
    name: str               # Display name: "RTK Command Filter"
    description: str        # Detailed explanation
    icon: str = "Zap"       # Lucide icon identifier
    stage_type: str = "builtin"  # "builtin" | "custom_regex" | "custom_script"
    default_order: int = 10
    default_enabled: bool = True
    is_builtin: bool = True

    @abstractmethod
    def get_config_schema(self) -> List[StageConfigField]:
        """Return the configuration schema for this stage to render in UI."""
        pass

    @abstractmethod
    async def compress(
        self,
        messages: List[ChatMessage],
        config: Dict[str, Any],
        context: CompressionContext,
    ) -> StageExecutionResult:
        """
        Process the message sequence and return the compressed messages and metrics.
        Must be fail-safe: if something fails, caught or returns original messages.
        """
        pass
