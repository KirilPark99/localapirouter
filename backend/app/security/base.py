"""Base types and abstract classes for guardrails."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GuardrailContext:
    model_id: Optional[str] = None
    request_headers: Dict[str, str] = field(default_factory=dict)
    router_key_id: Optional[int] = None
    disabled_guardrails: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    trusted_bypass: bool = False


@dataclass
class GuardrailResult:
    block: bool = False
    block_reason: Optional[str] = None
    severity: str = "low"  # low, medium, high
    modified: bool = False
    modified_payload: Any = None
    modified_content: Any = None
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


class BaseGuardrail:
    """Base interface for all security guardrails."""

    def __init__(self, name: str, enabled: bool = True, priority: int = 50):
        self.name = name
        self.enabled = enabled
        self.priority = priority

    async def pre_call(self, payload: Any, context: GuardrailContext) -> GuardrailResult:
        """Executed before sending request to router/upstream LLM."""
        return GuardrailResult(block=False)

    async def post_call(self, content: Any, context: GuardrailContext) -> GuardrailResult:
        """Executed on response content before returning to client."""
        return GuardrailResult(block=False)
