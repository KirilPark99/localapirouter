import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import DiscoveredModel, Provider, ProviderCredential
from app.schemas.entities import ModelLimitsRead
from app.core.crypto import decrypt_secret
from app.services.proxy_service import ProxyService
from app.core.http_client import http_client_manager

logger = logging.getLogger(__name__)

# Live API caches: populated exclusively via direct provider API requests
_live_limits_cache: Dict[int, ModelLimitsRead] = {}
_credential_rates_cache: Dict[int, Dict[str, Any]] = {}

class ModelLimitsService:
    @staticmethod
    def _with_overrides(limits, cred):
        result = limits.model_copy(deep=True)
        if cred is not None:
            for field, value in _credential_rates_cache.get(cred.id, {}).items():
                if field in ModelLimitsRead.model_fields:
                    setattr(result, field, value)
            if cred.rpm_limit is not None:
                result.rate_limit_rpm = cred.rpm_limit
            if cred.tpm_limit is not None:
                result.rate_limit_tpm = cred.tpm_limit
        return result

    @classmethod
    def compute_model_limits_fast(
        cls,
        model: DiscoveredModel,
        cred: Optional[ProviderCredential] = None,
    ) -> Optional[ModelLimitsRead]:
        """
        Build limits strictly from API-discovered data and live API rate limits.
        No hardcoded guesses or static dictionary tables.
        """
        # If live probe data was already retrieved for this exact model, return it
        if model.id in _live_limits_cache:
            return cls._with_overrides(_live_limits_cache[model.id], cred)

        p_slug = (model.provider.slug if model.provider else "").lower().strip()

        # Check if rate limits were retrieved from live API for this credential
        cred_rates: Dict[str, Any] = {}
        if cred and cred.id in _credential_rates_cache:
            cred_rates = _credential_rates_cache[cred.id]

        # Rate limits strictly from API probe or user credential setting
        rpm: Optional[int] = cred_rates.get("rate_limit_rpm")
        tpm: Optional[int] = cred_rates.get("rate_limit_tpm")
        rpd: Optional[int] = cred_rates.get("rate_limit_rpd")
        remaining_requests: Optional[int] = cred_rates.get("remaining_requests")
        remaining_tokens: Optional[int] = cred_rates.get("remaining_tokens")
        reset_requests: Optional[str] = cred_rates.get("reset_requests")
        reset_tokens: Optional[str] = cred_rates.get("reset_tokens")
        account_usage: Optional[float] = cred_rates.get("account_usage")
        account_limit: Optional[float] = cred_rates.get("account_limit")
        is_free_tier: Optional[bool] = cred_rates.get("is_free_tier")

        # User's explicit credential limit in database takes precedence if set
        if cred and cred.rpm_limit is not None:
            rpm = cred.rpm_limit
        if cred and cred.tpm_limit is not None:
            tpm = cred.tpm_limit

        # If the API returned NO context length, NO max output tokens, and NO rate limits,
        # return None so an empty block is never rendered.
        if (
            model.context_length is None
            and model.max_output_tokens is None
            and rpm is None
            and tpm is None
            and rpd is None
            and account_usage is None
        ):
            return None

        return ModelLimitsRead(
            model_id=model.id,
            provider_model_id=model.provider_model_id,
            canonical_slug=model.canonical_slug,
            provider_slug=p_slug,
            context_length=model.context_length,
            max_output_tokens=model.max_output_tokens,
            rate_limit_rpm=rpm,
            rate_limit_tpm=tpm,
            rate_limit_rpd=rpd,
            remaining_requests=remaining_requests,
            remaining_tokens=remaining_tokens,
            reset_requests=reset_requests,
            reset_tokens=reset_tokens,
            account_usage=account_usage,
            account_limit=account_limit,
            is_free_tier=is_free_tier,
            source="direct_api" if cred_rates else "api_model",
            raw_details={},
        )

    @classmethod
    async def probe_credential_rate_limits(
        cls,
        provider: Provider,
        cred: ProviderCredential,
    ) -> Dict[str, Any]:
        """
        Query upstream provider API directly to extract live rate limits, headers, or quota.
        """
        api_key = decrypt_secret(cred.encrypted_api_key) if cred.encrypted_api_key else None
        if not api_key or api_key in ("no-key", "none", "empty"):
            return {}

        proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
        p_slug = provider.slug.lower()
        adapter_type = provider.adapter_type.lower()
        client = await http_client_manager.get_client(proxy_url=proxy_url, timeout=10.0)
        rates: Dict[str, Any] = {}

        # 1. Groq: Live headers probe
        if p_slug == "groq" or adapter_type == "groq":
            try:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "groq/compound",
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
                headers = resp.headers
                if "x-ratelimit-limit-requests" in headers:
                    rates["rate_limit_rpm"] = int(headers["x-ratelimit-limit-requests"])
                if "x-ratelimit-limit-tokens" in headers:
                    rates["rate_limit_tpm"] = int(headers["x-ratelimit-limit-tokens"])
                if "x-ratelimit-remaining-requests" in headers:
                    try:
                        rates["remaining_requests"] = int(headers["x-ratelimit-remaining-requests"])
                    except Exception:
                        pass
                if "x-ratelimit-remaining-tokens" in headers:
                    try:
                        rates["remaining_tokens"] = int(headers["x-ratelimit-remaining-tokens"])
                    except Exception:
                        pass
                if "x-ratelimit-reset-requests" in headers:
                    rates["reset_requests"] = str(headers["x-ratelimit-reset-requests"])
                if "x-ratelimit-reset-tokens" in headers:
                    rates["reset_tokens"] = str(headers["x-ratelimit-reset-tokens"])
            except Exception as e:
                logger.warning(f"Failed to probe Groq API rate limits: {e}")

        # 2. OpenRouter: /auth/key endpoint
        elif p_slug == "openrouter" or adapter_type == "openrouter":
            try:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    rates["account_usage"] = data.get("usage")
                    rates["account_limit"] = data.get("limit")
                    rates["is_free_tier"] = data.get("is_free_tier")
                    rl = data.get("rate_limit") or {}
                    reqs = rl.get("requests")
                    interval = rl.get("interval", "10s")
                    if reqs and isinstance(reqs, (int, float)) and reqs > 0:
                        if "s" in str(interval):
                            secs = float(str(interval).replace("s", ""))
                            rates["rate_limit_rpm"] = int(reqs * (60.0 / secs))
                        else:
                            rates["rate_limit_rpm"] = int(reqs)
            except Exception as e:
                logger.warning(f"Failed to fetch OpenRouter API key limits: {e}")

        # 3. Generic OpenAI / other providers with ratelimit headers
        else:
            try:
                base_url = provider.base_url.rstrip("/")
                auth_header = provider.auth_header or "Authorization"
                auth_type = provider.auth_type or "bearer"
                hdrs = {"Content-Type": "application/json"}
                if auth_type == "bearer":
                    hdrs[auth_header] = f"Bearer {api_key}"
                elif auth_type in ("x-api-key", "custom_header"):
                    hdrs[auth_header] = api_key

                resp = await client.get(f"{base_url}/models", headers=hdrs)
                for k, v in resp.headers.items():
                    kl = k.lower()
                    if "ratelimit-limit-requests" in kl or "ratelimit-limit-rpm" in kl:
                        try:
                            rates["rate_limit_rpm"] = int(v)
                        except Exception:
                            pass
                    elif "ratelimit-limit-tokens" in kl or "ratelimit-limit-tpm" in kl:
                        try:
                            rates["rate_limit_tpm"] = int(v)
                        except Exception:
                            pass
                    elif "ratelimit-remaining-requests" in kl:
                        try:
                            rates["remaining_requests"] = int(v)
                        except Exception:
                            pass
                    elif "ratelimit-reset" in kl:
                        rates["reset_requests"] = str(v)
            except Exception as e:
                logger.warning(f"Failed to query rate limit headers for {provider.slug}: {e}")

        if rates:
            _credential_rates_cache[cred.id] = rates

        return rates

    @classmethod
    async def get_model_limits(cls, db: AsyncSession, model_id: int) -> Optional[ModelLimitsRead]:
        """
        Execute an on-demand direct live request to upstream provider API for this model.
        Returns live limits strictly as reported by the API.
        """
        result = await db.execute(
            select(DiscoveredModel)
            .where(DiscoveredModel.id == model_id)
            .options(
                selectinload(DiscoveredModel.provider),
                selectinload(DiscoveredModel.credential),
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Model with ID {model_id} not found")

        provider: Provider = model.provider
        cred = model.credential

        if not cred or not cred.enabled:
            c_res = await db.execute(
                select(ProviderCredential)
                .where(
                    ProviderCredential.provider_id == provider.id,
                    ProviderCredential.enabled == True,
                )
                .limit(1)
            )
            cred = c_res.scalar_one_or_none()

        api_key = decrypt_secret(cred.encrypted_api_key) if cred and cred.encrypted_api_key else None
        proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred and cred.proxy else None

        # Probe credential rate limits from API if not yet cached
        if cred and cred.id not in _credential_rates_cache:
            await cls.probe_credential_rate_limits(provider, cred)

        # Base limits from fast calculation (strictly API data)
        limits = cls.compute_model_limits_fast(model, None) or ModelLimitsRead(
            model_id=model.id,
            provider_model_id=model.provider_model_id,
            canonical_slug=model.canonical_slug,
            provider_slug=provider.slug,
            context_length=model.context_length,
            max_output_tokens=model.max_output_tokens,
            source="direct_api",
            raw_details={},
        )

        if not api_key or api_key in ("no-key", "none", "empty"):
            _live_limits_cache[model.id] = limits
            return cls._with_overrides(limits, cred)

        p_slug = provider.slug.lower()
        adapter_type = provider.adapter_type.lower()
        client = await http_client_manager.get_client(proxy_url=proxy_url, timeout=12.0)

        # 1. Google Gemini API direct query: inputTokenLimit & outputTokenLimit from models endpoint
        if p_slug == "google" or adapter_type == "google":
            try:
                clean_model_id = model.provider_model_id.replace("models/", "").strip()
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model_id}"
                resp = await client.get(url, headers={"x-goog-api-key": api_key})
                if resp.status_code == 200:
                    data = resp.json()
                    in_limit = data.get("inputTokenLimit")
                    out_limit = data.get("outputTokenLimit")
                    if in_limit:
                        limits.context_length = int(in_limit)
                    if out_limit:
                        limits.max_output_tokens = int(out_limit)
                    limits.source = "direct_api"
                    limits.raw_details = {
                        "displayName": data.get("displayName"),
                        "thinking": data.get("thinking"),
                        "supportedGenerationMethods": data.get("supportedGenerationMethods"),
                    }
            except Exception as e:
                logger.warning(f"Error querying direct Google API limits: {e}")

        # 2. OpenRouter API direct query
        elif p_slug == "openrouter" or adapter_type == "openrouter":
            try:
                # Query models from OpenRouter API to verify context_length and max output
                m_resp = await client.get("https://openrouter.ai/api/v1/models")
                if m_resp.status_code == 200:
                    models_data = m_resp.json().get("data", [])
                    clean_id = model.provider_model_id.strip()
                    for m_item in models_data:
                        if m_item.get("id") == clean_id:
                            ctx = m_item.get("context_length")
                            if ctx:
                                limits.context_length = int(ctx)
                            top_p = m_item.get("top_provider") or {}
                            max_c = top_p.get("max_completion_tokens")
                            if max_c:
                                limits.max_output_tokens = int(max_c)
                            limits.source = "direct_api"
                            limits.raw_details = {
                                "per_request_limits": m_item.get("per_request_limits"),
                                "pricing": m_item.get("pricing"),
                            }
                            break

                # Also update credential rate limits from OpenRouter /auth/key
                if cred:
                    await cls.probe_credential_rate_limits(provider, cred)
                    c_rates = _credential_rates_cache.get(cred.id, {})
                    if c_rates.get("rate_limit_rpm"):
                        limits.rate_limit_rpm = c_rates["rate_limit_rpm"]
                    if c_rates.get("account_usage") is not None:
                        limits.account_usage = c_rates["account_usage"]
                    if c_rates.get("account_limit") is not None:
                        limits.account_limit = c_rates["account_limit"]
            except Exception as e:
                logger.warning(f"Error querying direct OpenRouter limits: {e}")

        # 3. Groq API direct query: probe completions to extract live rate limits
        elif p_slug == "groq" or adapter_type == "groq":
            try:
                probe_resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model.provider_model_id,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
                headers = probe_resp.headers
                if "x-ratelimit-limit-requests" in headers:
                    limits.rate_limit_rpm = int(headers["x-ratelimit-limit-requests"])
                if "x-ratelimit-limit-tokens" in headers:
                    limits.rate_limit_tpm = int(headers["x-ratelimit-limit-tokens"])
                if "x-ratelimit-remaining-requests" in headers:
                    try:
                        limits.remaining_requests = int(headers["x-ratelimit-remaining-requests"])
                    except Exception:
                        pass
                if "x-ratelimit-remaining-tokens" in headers:
                    try:
                        limits.remaining_tokens = int(headers["x-ratelimit-remaining-tokens"])
                    except Exception:
                        pass
                limits.reset_requests = headers.get("x-ratelimit-reset-requests")
                limits.reset_tokens = headers.get("x-ratelimit-reset-tokens")
                limits.source = "direct_api"
            except Exception as e:
                logger.warning(f"Error probing Groq rate limits: {e}")

        # 4. Generic OpenAI compatible / Other providers
        else:
            try:
                base_url = provider.base_url.rstrip("/")
                auth_header = provider.auth_header or "Authorization"
                auth_type = provider.auth_type or "bearer"
                hdrs = {"Content-Type": "application/json"}
                if auth_type == "bearer":
                    hdrs[auth_header] = f"Bearer {api_key}"
                elif auth_type in ("x-api-key", "custom_header"):
                    hdrs[auth_header] = api_key

                resp = await client.get(f"{base_url}/models/{model.provider_model_id}", headers=hdrs)
                if resp.status_code == 200:
                    d = resp.json()
                    ctx = d.get("context_window") or d.get("context_length")
                    max_out = d.get("max_output_tokens") or d.get("max_completion_tokens")
                    if ctx:
                        limits.context_length = int(ctx)
                    if max_out:
                        limits.max_output_tokens = int(max_out)
                    limits.source = "direct_api"

                for k, v in resp.headers.items():
                    kl = k.lower()
                    if "ratelimit-limit-requests" in kl or "ratelimit-limit-rpm" in kl:
                        try:
                            limits.rate_limit_rpm = int(v)
                            limits.source = "direct_api"
                        except Exception:
                            pass
                    elif "ratelimit-limit-tokens" in kl or "ratelimit-limit-tpm" in kl:
                        try:
                            limits.rate_limit_tpm = int(v)
                            limits.source = "direct_api"
                        except Exception:
                            pass
                    elif "ratelimit-remaining-requests" in kl:
                        try:
                            limits.remaining_requests = int(v)
                        except Exception:
                            pass
                    elif "ratelimit-reset" in kl:
                        limits.reset_requests = str(v)
            except Exception as e:
                logger.warning(f"Error querying generic OpenAI API limits: {e}")

        # Save to memory cache
        _live_limits_cache[model.id] = limits

        # Sync updated context/max_output back to DB if received from API (only if not already configured)
        changed = False
        if limits.context_length and model.context_length is None:
            model.context_length = limits.context_length
            changed = True
        if limits.max_output_tokens and model.max_output_tokens is None:
            model.max_output_tokens = limits.max_output_tokens
            changed = True
        if changed:
            try:
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to update model context/output limits in DB: {e}")

        return cls._with_overrides(limits, cred)
