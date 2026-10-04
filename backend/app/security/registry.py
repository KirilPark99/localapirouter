"""Guardrail Registry — Orchestrates pre-call and post-call security checks."""
import time
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.base import BaseGuardrail, GuardrailContext, GuardrailResult
from app.security.prompt_injection import PromptInjectionGuardrail
from app.security.credential_masker import CredentialMaskerGuardrail, redact_credentials
from app.models.entities import SecurityConfig

logger = logging.getLogger("app.security.registry")

_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_CACHE_TIMESTAMP: float = 0.0
CACHE_TTL_SECONDS = 5.0


def parse_disabled_guardrails(headers: Dict[str, str], metadata: Optional[Dict[str, Any]] = None) -> List[str]:
    """Extract list of disabled guardrail names from headers or metadata."""
    disabled: List[str] = []
    # 1. Header checks
    for k, v in headers.items():
        lk = k.lower()
        if lk in ("x-guardrails-disabled", "x-disabled-guardrails", "x-omniroute-disabled-guardrails"):
            parts = [p.strip().lower() for p in v.split(",") if p.strip()]
            disabled.extend(parts)

    # 2. Metadata checks
    if metadata and isinstance(metadata, dict):
        dg = metadata.get("disabled_guardrails") or metadata.get("disabledGuardrails")
        if isinstance(dg, list):
            disabled.extend([str(item).strip().lower() for item in dg])
        elif isinstance(dg, str):
            disabled.extend([p.strip().lower() for p in dg.split(",") if p.strip()])

    return list(set(disabled))


class GuardrailRegistry:
    @classmethod
    def invalidate_cache(cls):
        global _CONFIG_CACHE, _CACHE_TIMESTAMP
        _CONFIG_CACHE = None
        _CACHE_TIMESTAMP = 0.0

    @classmethod
    async def get_security_config(cls, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        global _CONFIG_CACHE, _CACHE_TIMESTAMP
        now = time.time()
        if _CONFIG_CACHE is not None and (now - _CACHE_TIMESTAMP) < CACHE_TTL_SECONDS:
            return _CONFIG_CACHE

        default_config = {
            "injection_guard_enabled": True,
            "injection_mode": "warn",
            "injection_threshold": "high",
            "max_injection_scan_bytes": 16384,
            "custom_injection_patterns": [],
            "credential_masking_enabled": False,
            "mask_inbound": True,
            "mask_outbound": True,
            "custom_credential_patterns": [],
            "duckduckgo_fallback_enabled": True,
            "oidc_enabled": False,
            "oidc_disable_password_login": False,
            "oidc_issuer": "",
            "oidc_client_id": "",
            "oidc_client_secret": "",
            "oidc_scopes": ["openid", "profile", "email"],
            "oidc_allowed_emails": [],
        }

        if db is None:
            return default_config

        try:
            res = await db.execute(select(SecurityConfig).where(SecurityConfig.id == 1))
            cfg = res.scalar_one_or_none()
            if cfg is None:
                # Initialize default config row in database
                cfg = SecurityConfig(id=1)
                db.add(cfg)
                await db.commit()
                await db.refresh(cfg)

            loaded = {
                "injection_guard_enabled": cfg.injection_guard_enabled,
                "injection_mode": cfg.injection_mode,
                "injection_threshold": cfg.injection_threshold,
                "max_injection_scan_bytes": cfg.max_injection_scan_bytes,
                "custom_injection_patterns": cfg.custom_injection_patterns or [],
                "credential_masking_enabled": cfg.credential_masking_enabled,
                "mask_inbound": cfg.mask_inbound,
                "mask_outbound": cfg.mask_outbound,
                "custom_credential_patterns": cfg.custom_credential_patterns or [],
                "duckduckgo_fallback_enabled": cfg.duckduckgo_fallback_enabled,
                "oidc_enabled": cfg.oidc_enabled,
                "oidc_disable_password_login": cfg.oidc_disable_password_login,
                "oidc_issuer": cfg.oidc_issuer or "",
                "oidc_client_id": cfg.oidc_client_id or "",
                "oidc_client_secret": cfg.oidc_client_secret or "",
                "oidc_scopes": cfg.oidc_scopes or ["openid", "profile", "email"],
                "oidc_allowed_emails": cfg.oidc_allowed_emails or [],
            }
            _CONFIG_CACHE = loaded
            _CACHE_TIMESTAMP = now
            return loaded
        except Exception as e:
            logger.debug(f"Could not load security config from DB, using defaults: {e}")
            return default_config

    @classmethod
    async def build_guardrails(cls, db: Optional[AsyncSession] = None) -> List[BaseGuardrail]:
        cfg = await cls.get_security_config(db)
        guardrails: List[BaseGuardrail] = []

        # 1. Prompt injection guardrail
        inj = PromptInjectionGuardrail(
            enabled=cfg.get("injection_guard_enabled", True),
            mode=cfg.get("injection_mode", "warn"),
            threshold=cfg.get("injection_threshold", "high"),
            max_scan_bytes=cfg.get("max_injection_scan_bytes", 16384),
            custom_patterns=cfg.get("custom_injection_patterns", []),
        )
        guardrails.append(inj)

        # 2. Credential masker guardrail
        masker = CredentialMaskerGuardrail(
            enabled=cfg.get("credential_masking_enabled", False),
            mask_inbound=cfg.get("mask_inbound", True),
            mask_outbound=cfg.get("mask_outbound", True),
            custom_patterns=cfg.get("custom_credential_patterns", []),
        )
        guardrails.append(masker)

        # Sort by priority ascending (lower number runs first)
        guardrails.sort(key=lambda g: g.priority)
        return guardrails

    @classmethod
    async def run_pre_call_hooks(
        cls,
        payload: Any,
        headers: Dict[str, str],
        model_id: str = "",
        db: Optional[AsyncSession] = None,
    ) -> GuardrailResult:
        """Run all pre_call security hooks sequentially."""
        metadata = getattr(payload, "metadata", None)
        disabled = parse_disabled_guardrails(headers, metadata)
        context = GuardrailContext(
            model_id=model_id,
            request_headers=headers,
            disabled_guardrails=disabled,
            metadata=metadata if isinstance(metadata, dict) else {},
        )

        guardrails = await cls.build_guardrails(db)
        all_warnings: List[str] = []
        combined_meta: Dict[str, Any] = {}

        for guardrail in guardrails:
            res = await guardrail.pre_call(payload, context)
            if res.block:
                return res
            if res.warnings:
                all_warnings.extend(res.warnings)
            if res.meta:
                combined_meta[guardrail.name] = res.meta
            if res.modified and res.modified_payload is not None:
                payload = res.modified_payload

        return GuardrailResult(
            block=False,
            modified=bool(combined_meta.get("credential-masker")),
            modified_payload=payload,
            warnings=all_warnings,
            meta=combined_meta,
        )

    @classmethod
    async def run_post_call_hooks(
        cls,
        content: Any,
        headers: Dict[str, str],
        model_id: str = "",
        db: Optional[AsyncSession] = None,
    ) -> GuardrailResult:
        """Run all post_call security hooks on response content."""
        disabled = parse_disabled_guardrails(headers)
        context = GuardrailContext(
            model_id=model_id,
            request_headers=headers,
            disabled_guardrails=disabled,
        )

        guardrails = await cls.build_guardrails(db)
        # Reverse order for post-call hooks
        for guardrail in reversed(guardrails):
            res = await guardrail.post_call(content, context)
            if res.block:
                return res
            if res.modified and res.modified_content is not None:
                content = res.modified_content

        return GuardrailResult(
            block=False,
            modified_content=content if isinstance(content, str) else None,
        )

    @classmethod
    def mask_text_sync(cls, text: str, custom_patterns: Optional[List[Dict[str, Any]]] = None) -> str:
        """Synchronously mask credentials from text chunk using the cached pattern set."""
        if not text:
            return text
        cfg = _CONFIG_CACHE
        if cfg and not cfg.get("credential_masking_enabled", False):
            return text
        if cfg and not cfg.get("mask_outbound", True):
            return text

        patterns = custom_patterns or (cfg.get("custom_credential_patterns") if cfg else None)
        redacted, _, _ = redact_credentials(text, custom_patterns=patterns)
        return redacted
