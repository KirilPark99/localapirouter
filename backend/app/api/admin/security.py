"""Admin API for Security & Guardrails Management."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any, Dict, List, Optional, Literal
import asyncio
import re
from pydantic import BaseModel, Field, field_validator, model_validator
from app.core.safe_regex import validate_pattern

from app.core.database import get_db
from app.api.deps import get_current_admin
from app.models.entities import SecurityConfig
from app.security.registry import GuardrailRegistry
from app.security.prompt_injection import detect_injections, should_block, scan_text_from_messages
from app.security.credential_masker import redact_credentials
from app.services.search.duckduckgo_lite import search_duckduckgo_lite

router = APIRouter(prefix="/security", tags=["Admin Security & Guardrails"])


class InjectionPattern(BaseModel):
    name: str = Field(default="custom", max_length=128)
    pattern: str = Field(min_length=1, max_length=512)
    severity: Literal["high", "medium", "low"] = "high"

    @field_validator("pattern")
    @classmethod
    def valid_regex(cls, value):
        validate_pattern(value)
        return value


class CredentialPattern(InjectionPattern):
    replacement: str = Field(default="[REDACTED:secret]", max_length=1024)

    @model_validator(mode="after")
    def valid_replacement(self):
        try:
            re.compile(self.pattern, re.IGNORECASE).sub(self.replacement, "")
        except re.error as exc:
            raise ValueError("Invalid regex replacement") from exc
        return self


class SecuritySettingsUpdate(BaseModel):
    injection_guard_enabled: Optional[bool] = None
    injection_mode: Optional[Literal["block", "warn", "log"]] = None  # "block", "warn", "log"
    injection_threshold: Optional[Literal["high", "medium", "low"]] = None  # "high", "medium", "low"
    max_injection_scan_bytes: Optional[int] = Field(default=None, ge=512, le=65536)
    custom_injection_patterns: Optional[List[InjectionPattern]] = Field(default=None, max_length=32)

    credential_masking_enabled: Optional[bool] = None
    mask_inbound: Optional[bool] = None
    mask_outbound: Optional[bool] = None
    custom_credential_patterns: Optional[List[CredentialPattern]] = Field(default=None, max_length=32)

    duckduckgo_fallback_enabled: Optional[bool] = None

    oidc_enabled: Optional[bool] = None
    oidc_disable_password_login: Optional[bool] = None
    oidc_issuer: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_scopes: Optional[List[str]] = None
    oidc_allowed_emails: Optional[List[str]] = None


    @model_validator(mode="before")
    @classmethod
    def reject_security_nulls(cls, values):
        if isinstance(values, dict):
            for name in ("injection_guard_enabled", "injection_mode", "injection_threshold",
                         "max_injection_scan_bytes", "custom_injection_patterns",
                         "credential_masking_enabled", "mask_inbound", "mask_outbound",
                         "custom_credential_patterns"):
                if name in values and values[name] is None:
                    raise ValueError(f"{name} cannot be null")
                if name in ("custom_injection_patterns", "custom_credential_patterns") and isinstance(values.get(name), list) and len(values[name]) > 32:
                    raise ValueError("At most 32 custom patterns are allowed")
        return values


class TestInjectionRequest(BaseModel):
    prompt: str = Field(max_length=524288)
    custom_patterns: Optional[List[InjectionPattern]] = Field(default=None, max_length=32)


class TestMaskingRequest(BaseModel):
    text: str = Field(max_length=524288)
    custom_patterns: Optional[List[CredentialPattern]] = Field(default=None, max_length=32)


class TestSearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=5, ge=1, le=20)


@router.get("/settings")
async def get_security_settings(
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """Retrieve current security and guardrails settings."""
    cfg = await GuardrailRegistry.get_security_config(db)
    # Mask client_secret for safety in responses
    safe_cfg = dict(cfg)
    if safe_cfg.get("oidc_client_secret"):
        secret = safe_cfg["oidc_client_secret"]
        if len(secret) > 8:
            safe_cfg["oidc_client_secret"] = secret[:4] + "••••••••" + secret[-4:]
        else:
            safe_cfg["oidc_client_secret"] = "••••••••"
    return safe_cfg


@router.put("/settings")
async def update_security_settings(
    payload: SecuritySettingsUpdate,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """Update security and guardrails configuration."""
    await GuardrailRegistry.check_readiness(db)
    res = await db.execute(select(SecurityConfig).where(SecurityConfig.id == 1))
    cfg = res.scalar_one_or_none()
    if cfg is None:
        cfg = SecurityConfig(id=1)
        db.add(cfg)

    updates = payload.model_dump(exclude_unset=True)

    # Validate mode and threshold if provided
    if "injection_mode" in updates and updates["injection_mode"]:
        mode = updates["injection_mode"].lower()
        if mode not in ("block", "warn", "log"):
            raise HTTPException(status_code=400, detail="Invalid injection_mode. Must be block, warn, or log.")
        cfg.injection_mode = mode

    if "injection_threshold" in updates and updates["injection_threshold"]:
        thresh = updates["injection_threshold"].lower()
        if thresh not in ("high", "medium", "low"):
            raise HTTPException(status_code=400, detail="Invalid injection_threshold. Must be high, medium, or low.")
        cfg.injection_threshold = thresh

    if "injection_guard_enabled" in updates and updates["injection_guard_enabled"] is not None:
        cfg.injection_guard_enabled = bool(updates["injection_guard_enabled"])

    if "max_injection_scan_bytes" in updates and updates["max_injection_scan_bytes"] is not None:
        cfg.max_injection_scan_bytes = max(512, int(updates["max_injection_scan_bytes"]))

    if "custom_injection_patterns" in updates:
        cfg.custom_injection_patterns = updates["custom_injection_patterns"]

    if "credential_masking_enabled" in updates and updates["credential_masking_enabled"] is not None:
        cfg.credential_masking_enabled = bool(updates["credential_masking_enabled"])

    if "mask_inbound" in updates and updates["mask_inbound"] is not None:
        cfg.mask_inbound = bool(updates["mask_inbound"])

    if "mask_outbound" in updates and updates["mask_outbound"] is not None:
        cfg.mask_outbound = bool(updates["mask_outbound"])

    if "custom_credential_patterns" in updates:
        cfg.custom_credential_patterns = updates["custom_credential_patterns"]

    if "duckduckgo_fallback_enabled" in updates and updates["duckduckgo_fallback_enabled"] is not None:
        cfg.duckduckgo_fallback_enabled = bool(updates["duckduckgo_fallback_enabled"])

    if "oidc_enabled" in updates and updates["oidc_enabled"] is not None:
        cfg.oidc_enabled = bool(updates["oidc_enabled"])

    if "oidc_disable_password_login" in updates and updates["oidc_disable_password_login"] is not None:
        cfg.oidc_disable_password_login = bool(updates["oidc_disable_password_login"])

    if "oidc_issuer" in updates and updates["oidc_issuer"] is not None:
        cfg.oidc_issuer = updates["oidc_issuer"].strip()

    if "oidc_client_id" in updates and updates["oidc_client_id"] is not None:
        cfg.oidc_client_id = updates["oidc_client_id"].strip()

    if "oidc_client_secret" in updates and updates["oidc_client_secret"] is not None:
        # Don't overwrite if placeholder was sent back
        sec = updates["oidc_client_secret"].strip()
        if not ("••" in sec):
            cfg.oidc_client_secret = sec

    if "oidc_scopes" in updates and updates["oidc_scopes"] is not None:
        cfg.oidc_scopes = updates["oidc_scopes"]

    if "oidc_allowed_emails" in updates and updates["oidc_allowed_emails"] is not None:
        cfg.oidc_allowed_emails = updates["oidc_allowed_emails"]

    await db.commit()
    GuardrailRegistry.invalidate_cache()

    return {"message": "Security settings updated successfully"}


@router.post("/test-injection")
async def test_injection(
    payload: TestInjectionRequest,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """Test prompt injection detection on sample prompt."""
    cfg = await GuardrailRegistry.get_security_config(db)
    patterns = [p.model_dump() for p in payload.custom_patterns] if payload.custom_patterns is not None else cfg.get("custom_injection_patterns", [])
    max_bytes = cfg.get("max_injection_scan_bytes", 16384)

    text_to_scan, incomplete = scan_text_from_messages([{"content": payload.prompt}], max_bytes)
    try:
        detections = await asyncio.to_thread(detect_injections, text_to_scan, patterns)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Custom pattern evaluation failed") from exc
    threshold = cfg.get("injection_threshold", "high")
    would_block, top_sev = should_block(detections, threshold)

    return {
        "detections": detections,
        "count": len(detections),
        "top_severity": top_sev,
        "configured_threshold": threshold,
        "configured_mode": cfg.get("injection_mode", "warn"),
        "would_block": (would_block or incomplete) if cfg.get("injection_mode") == "block" else False,
        "scanned_bytes": len(text_to_scan.encode("utf-8")),
        "incomplete_scan": incomplete,
    }


@router.post("/test-masking")
async def test_masking(
    payload: TestMaskingRequest,
    db: AsyncSession = Depends(get_db),
    admin: str = Depends(get_current_admin),
):
    """Test credential masking on sample text."""
    cfg = await GuardrailRegistry.get_security_config(db)
    patterns = [p.model_dump() for p in payload.custom_patterns] if payload.custom_patterns is not None else cfg.get("custom_credential_patterns", [])
    try:
        redacted_text, detections, modified = await asyncio.to_thread(redact_credentials, payload.text, patterns)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Custom pattern evaluation failed") from exc

    return {
        "original_length": len(payload.text),
        "redacted_text": redacted_text,
        "detections": detections,
        "total_redactions": sum(d["count"] for d in detections),
        "modified": modified,
    }


@router.post("/test-search")
async def test_search(
    payload: TestSearchRequest,
    admin: str = Depends(get_current_admin),
):
    """Test free DuckDuckGo Lite search."""
    results = await search_duckduckgo_lite(payload.query, max_results=payload.max_results)
    return {
        "query": payload.query,
        "count": len(results),
        "results": results,
    }
