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
import asyncio
from app.core.safe_regex import search
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


def scan_text_from_messages(messages: Any, max_bytes: int = MAX_INJECTION_SCAN_BYTES) -> Tuple[str, bool]:
    """UTF-8 bounded scan, newest user/tool turns first; all roles remain untrusted."""
    messages = messages or []
    if not isinstance(messages, list):
        messages = [{"content": messages}]
    def field(message, name, default=None):
        return message.get(name, default) if isinstance(message, dict) else getattr(message, name, default)
    ordered = sorted(enumerate(messages), key=lambda pair: (
        field(pair[1], "role") not in ("user", "tool", "function"), -pair[0]))
    parts = []
    remaining = max_bytes
    incomplete = False
    for _, message in ordered:
        content = field(message, "content", "")
        texts = [content] if isinstance(content, str) else [
            field(part, "text", "") for part in (content or [])
            if field(part, "type") in ("text", "input_text", "output_text")
        ] if isinstance(content, list) else []
        for text in texts:
            if not isinstance(text, str) or not text:
                continue
            separator = "\n" if parts else ""
            if remaining <= len(separator):
                incomplete = True
                continue
            # Slice characters before encoding so one huge turn cannot allocate
            # an equally huge temporary byte string just to enforce the cap.
            encoded = text[:remaining].encode("utf-8")
            take = encoded[:remaining - len(separator)].decode("utf-8", errors="ignore")
            incomplete |= len(take) != len(text)
            parts.append(separator + take)
            remaining -= len((separator + take).encode("utf-8"))
    return "".join(parts), incomplete


def extract_text_from_messages(messages: Any, max_bytes: int = MAX_INJECTION_SCAN_BYTES) -> str:
    return scan_text_from_messages(messages, max_bytes)[0]


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
            m = search(pat_str, text, flags=re.IGNORECASE)
            severity = cp.get("severity", "high")
            if severity not in SEVERITY_SCORES:
                raise ValueError("Invalid injection severity")
            if m:
                detections.append({"name": cp.get("name", f"custom_{idx}"),
                                   "match": m["match"], "severity": severity})

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
        if mode not in ("block", "warn", "log") or threshold not in SEVERITY_SCORES:
            raise ValueError("Invalid injection policy")
        if not 512 <= max_scan_bytes <= 65536:
            raise ValueError("Invalid injection scan budget")
        self.mode = mode.lower()
        self.threshold = threshold.lower()
        self.max_scan_bytes = max_scan_bytes
        self.custom_patterns = custom_patterns or []

    async def pre_call(self, payload: Any, context: GuardrailContext) -> GuardrailResult:
        if not self.enabled:
            return GuardrailResult(block=False)

        # Check bypass
        disabled = [d.lower().strip() for d in context.disabled_guardrails] if context.trusted_bypass else []
        if "prompt-injection" in disabled or "prompt_injection" in disabled or "all" in disabled:
            return GuardrailResult(block=False)

        messages = getattr(payload, "messages", None)
        if messages is None and isinstance(payload, dict):
            messages = payload.get("messages", [])

        scanned_text, incomplete = scan_text_from_messages(messages, self.max_scan_bytes)
        detections = await asyncio.to_thread(detect_injections, scanned_text, self.custom_patterns)
        block_candidate, top_severity = should_block(detections, self.threshold)
        meta = {"detections": detections, "scanned_bytes": len(scanned_text.encode("utf-8")),
                "incomplete_scan": incomplete}
        if self.mode == "block" and (block_candidate or incomplete):
            return GuardrailResult(
                block=True, severity=top_severity,
                block_reason="Security Violation: incomplete injection scan" if incomplete else "Security Violation: prompt injection detected",
                meta=meta,
            )
        warnings = [f"prompt_injection_{d['name']}" for d in detections] if self.mode != "log" else []
        if incomplete:
            logger.warning("Injection scan incomplete (mode=%s)", self.mode)
            warnings.append("prompt_injection_incomplete_scan")
        return GuardrailResult(warnings=warnings, severity=top_severity, meta=meta)
