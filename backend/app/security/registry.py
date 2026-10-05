"""Guardrail Registry — Orchestrates pre-call and post-call security checks."""
import time
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from fastapi import HTTPException
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


def may_bypass_guardrails(principal: Any) -> bool:
    """The caller supplies an authenticated object, never request metadata."""
    permissions = getattr(principal, "permissions", None)
    return isinstance(permissions, list) and "guardrails_bypass" in permissions


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
        # Database-backed policies are read from their actual database, never a
        # process-global policy belonging to another session/engine.

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
                # An empty migrated table is valid and retains opt-in defaults.
                return default_config

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
            logger.error("Security configuration unavailable: %s", type(e).__name__)
            raise HTTPException(status_code=503, detail="Security configuration unavailable; check security_configs migration") from e

    @classmethod
    async def check_readiness(cls, db: AsyncSession) -> bool:
        """Uncached read-only schema/config readiness probe; does not create rows."""
        try:
            await db.execute(select(SecurityConfig).where(SecurityConfig.id == 1))
        except Exception as e:
            raise HTTPException(status_code=503, detail="Security configuration unavailable; check security_configs migration") from e
        return True

    @classmethod
    async def build_guardrails(cls, db: Optional[AsyncSession] = None) -> List[BaseGuardrail]:
        cfg = await cls.get_security_config(db)
        guardrails: List[BaseGuardrail] = []

        try:
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
        except Exception as e:
            raise HTTPException(status_code=503, detail="Invalid security policy") from e

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
        router_key: Any = None,
        principal: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GuardrailResult:
        """Run all pre_call security hooks sequentially."""
        metadata = metadata or (payload.get("metadata") if isinstance(payload, dict) else getattr(payload, "metadata", None))
        trusted = may_bypass_guardrails(router_key if router_key is not None else principal)
        disabled = parse_disabled_guardrails(headers, metadata) if trusted else []
        context = GuardrailContext(
            model_id=model_id,
            request_headers=headers,
            disabled_guardrails=disabled,
            trusted_bypass=trusted,
            router_key_id=getattr(router_key, "id", None),
            metadata=metadata if isinstance(metadata, dict) else {},
        )

        guardrails = await cls.build_guardrails(db)
        all_warnings: List[str] = []
        combined_meta: Dict[str, Any] = {}

        for guardrail in guardrails:
            try:
                res = await guardrail.pre_call(payload, context)
            except Exception as e:
                raise HTTPException(status_code=503, detail="Security guardrail unavailable") from e
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
        router_key: Any = None,
        principal: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GuardrailResult:
        """Run all post_call security hooks on response content."""
        trusted = may_bypass_guardrails(router_key if router_key is not None else principal)
        disabled = parse_disabled_guardrails(headers, metadata) if trusted else []
        context = GuardrailContext(
            model_id=model_id,
            request_headers=headers,
            disabled_guardrails=disabled,
            trusted_bypass=trusted,
            router_key_id=getattr(router_key, "id", None),
        )

        guardrails = await cls.build_guardrails(db)
        modified = False
        # Reverse order for post-call hooks
        for guardrail in reversed(guardrails):
            try:
                res = await guardrail.post_call(content, context)
            except Exception as e:
                raise HTTPException(status_code=503, detail="Security guardrail unavailable") from e
            if res.block:
                return res
            if res.modified and res.modified_content is not None:
                content = res.modified_content
                modified = True

        return GuardrailResult(
            block=False,
            modified_content=content,
            modified=modified,
        )

    @classmethod
    async def wrap_stream(
        cls, source, model: str, headers: Dict[str, str],
        db: Optional[AsyncSession] = None, router_key: Any = None,
        include_usage: bool = False, principal: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Secure native chat SSE before compatibility adapters or cache writes.

        Unmasked output is exact passthrough. Masking buffers a complete bounded
        stream, redacts assembled content/reasoning/tool arguments, then emits
        native chat SSE retaining choices, tool IDs/signatures and usage.
        No partial raw output escapes on assembly/redaction errors.
        """
        cfg = await cls.get_security_config(db)
        trusted = may_bypass_guardrails(router_key if router_key is not None else principal)
        disabled = parse_disabled_guardrails(headers, metadata) if trusted else []
        masking = cfg.get("credential_masking_enabled", False) and cfg.get("mask_outbound", True)
        masking = masking and not any(name in disabled for name in ("all", "credential-masker", "credential_masker"))
        if not masking:
            async for chunk in source:
                yield chunk
            return

        # ponytail: full 8 MiB buffering when masking; incremental release would
        # need a credential grammar (especially PEM), not a short suffix window.
        from app.modules.base import collect_chat_completion
        from app.cache.response_cache import ResponseCacheService
        try:
            response = await collect_chat_completion(source, model, require_complete=True)
            result = await cls.run_post_call_hooks(
                response, headers, model_id=model, db=db, router_key=router_key,
                principal=principal, metadata=metadata,
            )
            if result.block:
                raise ValueError("Outbound security rejected stream")
            safe = result.modified_content
        except Exception as e:
            raise HTTPException(status_code=503, detail="Security stream assembly or redaction failed") from e
        async for chunk in ResponseCacheService.synthesize_sse_stream(
            safe.model_dump(mode="json"), safe.id, include_usage=include_usage,
        ):
            yield chunk

    @classmethod
    def mask_text_sync(cls, text: str, custom_patterns: Optional[List[Dict[str, Any]]] = None) -> str:
        """Mask one complete text using the last loaded policy; not split SSE.

        Streaming callers must use wrap_stream, which assembles secret fields.
        """
        if not text:
            return text
        cfg = _CONFIG_CACHE
        if not cfg or not cfg.get("credential_masking_enabled", False):
            return text
        if cfg and not cfg.get("mask_outbound", True):
            return text

        patterns = custom_patterns or (cfg.get("custom_credential_patterns") if cfg else None)
        redacted, _, _ = redact_credentials(text, custom_patterns=patterns)
        return redacted
