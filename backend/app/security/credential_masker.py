"""Credential Masker Guardrail — Bidirectional Secret Redaction.

Redacts API keys, secret tokens, private keys, database URIs, and credentials
from inbound requests (messages, tools) and outbound responses (JSON, SSE streams).
"""
import re
import asyncio
from app.core.safe_regex import subn
from pydantic import BaseModel
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from app.security.base import BaseGuardrail, GuardrailContext, GuardrailResult

logger = logging.getLogger("app.security.credential_masker")

# Protocol identifiers and opaque provider signatures must survive round trips.
OPAQUE_FIELDS = {"id", "tool_call_id", "call_id", "item_id", "thoughtSignature",
                 "thought_signature", "signature", "encrypted_content"}

CREDENTIAL_PATTERNS = [
    # LLM provider keys
    {"name": "openai_proj", "regex": re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), "replacement": "[REDACTED:openai]"},
    {"name": "openai", "regex": re.compile(r"\bsk-[A-Za-z0-9]{48}\b"), "replacement": "[REDACTED:openai]"},
    {"name": "anthropic", "regex": re.compile(r"sk-ant-api[0-9]?-[A-Za-z0-9_-]{20,}"), "replacement": "[REDACTED:anthropic]"},
    {"name": "anthropic_alt", "regex": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "replacement": "[REDACTED:anthropic]"},
    {"name": "google", "regex": re.compile(r"AIza[0-9A-Za-z_-]{35}"), "replacement": "[REDACTED:google]"},
    {"name": "huggingface", "regex": re.compile(r"hf_[A-Za-z0-9]{34}"), "replacement": "[REDACTED:hf]"},
    {"name": "replicate", "regex": re.compile(r"r8_[A-Za-z0-9]{37}"), "replacement": "[REDACTED:replicate]"},
    # VCS / SaaS tokens
    {"name": "github", "regex": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "replacement": "[REDACTED:github]"},
    {"name": "slack", "regex": re.compile(r"xox[bpoa]-[A-Za-z0-9-]{10,}"), "replacement": "[REDACTED:slack]"},
    {"name": "linear", "regex": re.compile(r"lin_api_[A-Za-z0-9]{40}"), "replacement": "[REDACTED:linear]"},
    {"name": "notion", "regex": re.compile(r"secret_[A-Za-z0-9]{43}"), "replacement": "[REDACTED:notion]"},
    {"name": "npm", "regex": re.compile(r"npm_[A-Za-z0-9]{36}"), "replacement": "[REDACTED:npm]"},
    {"name": "postman", "regex": re.compile(r"PMAK-[a-f0-9]{8}-[a-f0-9]{32}"), "replacement": "[REDACTED:postman]"},
    {"name": "discord", "regex": re.compile(r"\b[MN][A-Za-z0-9]{23}\.[A-Za-z0-9]{6}\.[A-Za-z0-9]{27}\b"), "replacement": "[REDACTED:discord]"},
    # Payments
    {"name": "stripe", "regex": re.compile(r"(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,}"), "replacement": "[REDACTED:stripe]"},
    {"name": "square", "regex": re.compile(r"sq0(?:atp-[0-9A-Za-z_-]{22}|csp-[0-9A-Za-z_-]{43})"), "replacement": "[REDACTED:square]"},
    # Cloud / infra
    {"name": "aws_access_key", "regex": re.compile(r"AKIA[0-9A-Z]{16}"), "replacement": "[REDACTED:aws]"},
    {"name": "twilio", "regex": re.compile(r"\bSK[0-9a-fA-F]{32}\b"), "replacement": "[REDACTED:twilio]"},
    {"name": "sendgrid", "regex": re.compile(r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}"), "replacement": "[REDACTED:sendgrid]"},
    {"name": "mailgun", "regex": re.compile(r"key-[a-f0-9]{32}"), "replacement": "[REDACTED:mailgun]"},
    # Crypto / identity
    {
        "name": "private_key",
        "regex": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
        "replacement": "[REDACTED:private_key]",
    },
    {"name": "jwt", "regex": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}\b"), "replacement": "[REDACTED:jwt]"},
    # Database connection strings with embedded creds
    {
        "name": "connection_string",
        "regex": re.compile(r"(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|redis|amqp):\/\/[^:/@\s\"']+:[^:/@\s\"']+@"),
        "replacement": "[REDACTED:connection_string]",
    },
    # Header-style secrets
    {
        "name": "auth_header",
        "regex": re.compile(
            r"((?:[\"']?(?:Authorization|x-api-key|api-key|apikey)[\"']?\s*[:=]\s*[\"']?)(?:(?:Bearer|Basic|Token)\s+)?)[A-Za-z0-9._~+/=-]{10,}",
            re.IGNORECASE,
        ),
        "replacement": r"\1[REDACTED:auth_header]",
    },
]


def redact_credentials(
    text: str, custom_patterns: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, List[Dict[str, Any]], bool]:
    """Redact known credentials from text string."""
    if not isinstance(text, str) or not text:
        return text, [], False

    result = text
    detections: List[Dict[str, Any]] = []

    # 1. Built-in patterns
    for p in CREDENTIAL_PATTERNS:
        matches = p["regex"].findall(result)
        if matches:
            result = p["regex"].sub(p["replacement"], result)
            detections.append({"type": p["name"], "count": len(matches)})

    # 2. Custom patterns
    if custom_patterns:
        for idx, cp in enumerate(custom_patterns):
            if not isinstance(cp, dict):
                continue
            pat_str = cp.get("pattern")
            replacement = cp.get("replacement", "[REDACTED:secret]")
            if not pat_str:
                continue
            result, count = subn(pat_str, replacement, result, flags=re.IGNORECASE)
            if count:
                detections.append({"type": cp.get("name", f"custom_{idx}"), "count": count})

    modified = result != text
    return result, detections, modified


def walk_and_redact(
    value: Any,
    detections: List[Dict[str, Any]],
    custom_patterns: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Any, bool]:
    """Recursively traverse JSON-like data structure and redact credentials in string leaves."""
    if isinstance(value, str):
        redacted, dets, mod = redact_credentials(value, custom_patterns=custom_patterns)
        if mod:
            detections.extend(dets)
        return redacted, mod

    if isinstance(value, list):
        any_mod = False
        new_list = []
        for item in value:
            new_item, mod = walk_and_redact(item, detections, custom_patterns)
            if mod:
                any_mod = True
            new_list.append(new_item)
        return new_list, any_mod

    if isinstance(value, dict):
        any_mod = False
        new_dict = {}
        for k, v in value.items():
            if k in OPAQUE_FIELDS:
                new_dict[k] = v
                continue
            new_v, mod = walk_and_redact(v, detections, custom_patterns)
            if mod:
                any_mod = True
            new_dict[k] = new_v
        return new_dict, any_mod

    if isinstance(value, BaseModel):
        fields = {name: getattr(value, name) for name in type(value).model_fields}
        fields.update(value.model_extra or {})
        updates, mod = walk_and_redact(fields, detections, custom_patterns)
        return (value.model_copy(update=updates) if mod else value), mod

    return value, False


class CredentialMaskerGuardrail(BaseGuardrail):
    def __init__(
        self,
        enabled: bool = False,  # Opt-in by default
        mask_inbound: bool = True,
        mask_outbound: bool = True,
        custom_patterns: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(name="credential-masker", enabled=enabled, priority=95)
        self.mask_inbound = mask_inbound
        self.mask_outbound = mask_outbound
        self.custom_patterns = custom_patterns or []

    async def pre_call(self, payload: Any, context: GuardrailContext) -> GuardrailResult:
        """Inbound redaction: cleans request messages and tool arguments."""
        if not self.enabled or not self.mask_inbound:
            return GuardrailResult(block=False)

        disabled = [d.lower().strip() for d in context.disabled_guardrails] if context.trusted_bypass else []
        if "credential-masker" in disabled or "credential_masker" in disabled or "all" in disabled:
            return GuardrailResult(block=False)

        detections: List[Dict[str, Any]] = []
        new_payload, modified = await asyncio.to_thread(walk_and_redact, payload, detections, self.custom_patterns)
        if modified:
            return GuardrailResult(
                modified=True, modified_payload=new_payload,
                meta={"credentials_redacted": detections, "count": sum(d["count"] for d in detections)},
            )

        return GuardrailResult(block=False)

    async def post_call(self, content: Any, context: GuardrailContext) -> GuardrailResult:
        """Outbound redaction: cleans assistant response before returning to client."""
        if not self.enabled or not self.mask_outbound:
            return GuardrailResult(block=False)

        disabled = [d.lower().strip() for d in context.disabled_guardrails] if context.trusted_bypass else []
        if "credential-masker" in disabled or "credential_masker" in disabled or "all" in disabled:
            return GuardrailResult(block=False)

        detections: List[Dict[str, Any]] = []
        new_val, modified = await asyncio.to_thread(walk_and_redact, content, detections, self.custom_patterns)
        if modified:
            count = sum(d["count"] for d in detections)
            logger.info(f"Redacted {count} leaked credentials from outbound response")
            return GuardrailResult(
                block=False,
                modified=True,
                modified_content=new_val,
                meta={"credentials_redacted": detections, "count": count},
            )

        return GuardrailResult(block=False)
