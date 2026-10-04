"""Prompt Injection Guardrail — Red-Team Suite with 16 KB bounded scanning.

Protects against:
- system_override: attempts to ignore/disregard system instructions
- role_hijack: forcing the LLM into unauthorized personas
- system_prompt_leak: probing for internal/confidential system instructions
- delimiter_injection: fake prompt delimiters like [SYSTEM], <|im_start|>, etc.
- jailbreak_dan: classic 'DAN', 'developer mode' evasion attacks
- encoding_evasion: rot13/base64/hex decode instruction evasion
"""
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from app.security.base import BaseGuardrail, GuardrailContext, GuardrailResult

logger = logging.getLogger("app.security.prompt_injection")

MAX_INJECTION_SCAN_BYTES = 16 * 1024  # 16 KB CPU bound to prevent ReDoS on huge context/RAG

SEVERITY_SCORES = {
    "high": 1.0,
    "medium": 0.5,
    "low": 0.2,
}

BUILTIN_PATTERNS = [
    {
        "name": "system_override",
        "pattern": re.compile(
            r"\b(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)\b",
            re.IGNORECASE,
        ),
        "severity": "high",
    },
    {
        "name": "role_hijack",
        "pattern": re.compile(
            r"\b(you\s+are\s+now|act\s+as\s+if|pretend\s+(to\s+be|you\s+are)|from\s+now\s+on\s+you\s+are)\b",
            re.IGNORECASE,
        ),
        "severity": "medium",
    },
    {
        "name": "system_prompt_leak",
        # Requires system/initial/hidden/original qualifier to prevent false positives on coding prompts
        "pattern": re.compile(
            r"\b(reveals?|shows?|displays?|prints?|outputs?|repeats?)\s+((your|the)\s+)?(system|initial|hidden|original)\s+(prompt|instructions?)\b",
            re.IGNORECASE,
        ),
        "severity": "high",
    },
    {
        "name": "delimiter_injection",
        "pattern": re.compile(
            r"(\[SYSTEM\]|\[INST\]|<<SYS>>|<\|im_start\|>|<\|system\|>|<\|user\|>)",
            re.IGNORECASE,
        ),
        "severity": "high",
    },
    {
        "name": "jailbreak_dan",
        "pattern": re.compile(
            r"\b(DAN|do\s+anything\s+now|jailbreak|developer\s+mode|enable\s+developer)\b",
            re.IGNORECASE,
        ),
        "severity": "medium",
    },
    {
        "name": "encoding_evasion",
        "pattern": re.compile(
            r"\b(base64\s+decode|rot13|hex\s+decode|unicode\s+escape)\b.*\b(instruction|prompt|command)\b",
            re.IGNORECASE,
        ),
        "severity": "medium",
    },
    {
        "name": "system_override_inline",
        "pattern": re.compile(r"\bsystem\s*:\s*override\b", re.IGNORECASE),
        "severity": "high",
    },
    {
        "name": "markdown_system_block",
        "pattern": re.compile(r"```+\s*system\b", re.IGNORECASE),
        "severity": "high",
    },
]


def extract_text_from_messages(messages: Any, max_bytes: int = MAX_INJECTION_SCAN_BYTES) -> str:
    """Extract plain text string from chat messages up to max_bytes."""
    if not messages:
        return ""

    buffer: List[str] = []
    current_len = 0

    if isinstance(messages, list):
        for msg in messages:
            content = ""
            if isinstance(msg, dict):
                content = msg.get("content", "")
            elif hasattr(msg, "content"):
                content = getattr(msg, "content", "")

            if isinstance(content, str):
                buffer.append(content)
                current_len += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        t = part.get("text", "")
                        buffer.append(t)
                        current_len += len(t)
                    elif hasattr(part, "type") and getattr(part, "type") == "text":
                        t = getattr(part, "text", "")
                        buffer.append(t)
                        current_len += len(t)

            if current_len >= max_bytes:
                break

    full_text = " \n ".join(buffer)
    # Strict slice to max_bytes
    return full_text[:max_bytes]


def detect_injections(
    text: str, custom_patterns: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """Scan text for prompt injection patterns."""
    if not text:
        return []

    detections = []
    # 1. Builtin patterns
    for item in BUILTIN_PATTERNS:
        match = item["pattern"].search(text)
        if match:
            detections.append(
                {
                    "name": item["name"],
                    "match": match.group(0),
                    "severity": item["severity"],
                }
            )

    # 2. Custom patterns
    if custom_patterns:
        for idx, cp in enumerate(custom_patterns):
            if not isinstance(cp, dict):
                continue
            pat_str = cp.get("pattern")
            if not pat_str:
                continue
            try:
                rx = re.compile(pat_str, re.IGNORECASE)
                m = rx.search(text)
                if m:
                    detections.append(
                        {
                            "name": cp.get("name", f"custom_{idx}"),
                            "match": m.group(0),
                            "severity": cp.get("severity", "high"),
                        }
                    )
            except Exception as e:
                logger.warning(f"Invalid custom regex pattern '{pat_str}': {e}")

    return detections


def should_block(detections: List[Dict[str, Any]], threshold: str) -> Tuple[bool, str]:
    """Check if detections meet or exceed the block threshold."""
    if not detections:
        return False, "low"

    threshold_score = {
        "low": 0.2,
        "medium": 0.5,
        "high": 1.0,
    }.get(threshold.lower(), 1.0)

    max_score = 0.0
    top_severity = "low"

    for d in detections:
        sev = d.get("severity", "low").lower()
        score = SEVERITY_SCORES.get(sev, 0.2)
        if score > max_score:
            max_score = score
            top_severity = sev

    return max_score >= threshold_score, top_severity


class PromptInjectionGuardrail(BaseGuardrail):
    def __init__(
        self,
        enabled: bool = True,
        mode: str = "warn",  # "block", "warn", "log"
        threshold: str = "high",  # "high", "medium", "low"
        max_scan_bytes: int = MAX_INJECTION_SCAN_BYTES,
        custom_patterns: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(name="prompt-injection", enabled=enabled, priority=10)
        self.mode = mode.lower()
        self.threshold = threshold.lower()
        self.max_scan_bytes = max_scan_bytes
        self.custom_patterns = custom_patterns or []

    async def pre_call(self, payload: Any, context: GuardrailContext) -> GuardrailResult:
        if not self.enabled:
            return GuardrailResult(block=False)

        # Check bypass
        disabled = [d.lower().strip() for d in context.disabled_guardrails]
        if "prompt-injection" in disabled or "prompt_injection" in disabled or "all" in disabled:
            return GuardrailResult(block=False)

        messages = getattr(payload, "messages", None)
        if messages is None and isinstance(payload, dict):
            messages = payload.get("messages", [])

        scanned_text = extract_text_from_messages(messages, max_bytes=self.max_scan_bytes)
        detections = detect_injections(scanned_text, custom_patterns=self.custom_patterns)

        if not detections:
            return GuardrailResult(block=False)

        block_candidate, top_severity = should_block(detections, self.threshold)
        det_names = [d["name"] for d in detections]
        log_msg = f"Prompt injection detected ({det_names}, top_severity={top_severity}, mode={self.mode})"

        if self.mode == "block" and block_candidate:
            logger.warning(f"BLOCKING request: {log_msg}")
            return GuardrailResult(
                block=True,
                block_reason=f"Security Violation: Prompt injection pattern detected ('{det_names[0]}'). Request blocked.",
                severity=top_severity,
                meta={"detections": detections, "scanned_bytes": len(scanned_text)},
            )
        elif self.mode in ("warn", "block"):
            logger.info(f"WARNING: {log_msg}")
            return GuardrailResult(
                block=False,
                warnings=[f"prompt_injection_{name}" for name in det_names],
                severity=top_severity,
                meta={"detections": detections, "scanned_bytes": len(scanned_text)},
            )
        else:
            # log mode
            logger.debug(f"LOG: {log_msg}")
            return GuardrailResult(
                block=False,
                severity=top_severity,
                meta={"detections": detections, "scanned_bytes": len(scanned_text)},
            )
