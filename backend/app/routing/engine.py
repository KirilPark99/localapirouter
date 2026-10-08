import asyncio
from contextlib import aclosing
import hashlib
import json
import math
import random
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal, _safe_close_session
from app.models.entities import (
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
    RoutingCandidate,
    RouterApiKey,
)
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.core.errors import RouterException, ErrorCategory
from app.core.config import settings
from app.core.circuit_breaker import circuit_breaker, CredentialStatus
from app.core.crypto import decrypt_secret
from app.adapters.factory import get_adapter
from app.services.proxy_service import ProxyService
from app.services.credential_service import CredentialService
from app.services.routing_service import RoutingService
from app.services.log_service import LogService

class RoutingEngine:
    _round_robin_indices: Dict[str, int] = {}

    @staticmethod
    def _eligible(provider, model_obj, cred):
        return bool(provider and provider.enabled and model_obj and model_obj.enabled
                    and model_obj.available and model_obj.provider_id == provider.id
                    and cred and cred.enabled and cred.provider_id == provider.id
                    and circuit_breaker.is_available(cred.id, model_obj.provider_model_id)[0])

    @classmethod
    async def _candidate_credentials(cls, db, provider, model_obj, *, credential_id=None, credential_group=None):
        if not provider or not model_obj or not provider.enabled or not model_obj.enabled or not model_obj.available:
            return []
        query = select(ProviderCredential).options(selectinload(ProviderCredential.proxy), selectinload(ProviderCredential.provider)).where(
            ProviderCredential.provider_id == provider.id, ProviderCredential.enabled == True)
        if credential_id is not None:
            query = query.where(ProviderCredential.id == credential_id)
        if credential_group:
            query = query.where(ProviderCredential.group_name == credential_group)
        query = query.order_by(ProviderCredential.priority.asc(), ProviderCredential.weight.desc(), ProviderCredential.id.asc())
        return [c for c in (await db.execute(query)).scalars().all() if cls._eligible(provider, model_obj, c)]

    @staticmethod
    def _reserve_credential(cred, request, model_obj):
        from app.core.admission import admission
        from app.compression.tokenizer import count_messages_tokens
        prompt_tokens = count_messages_tokens(request.messages)
        output_tokens = request.get_effective_max_tokens()
        if cred.tpm_limit is not None and output_tokens is None:
            output_tokens = model_obj.max_output_tokens
            if output_tokens is None:
                # Bound unknown provider output instead of reserving only the prompt.
                output_tokens = cred.tpm_limit - prompt_tokens
            if output_tokens <= 0:
                raise RouterException('Local TPM budget cannot cover an output token', ErrorCategory.RATE_LIMIT,
                    status_code=429, retry_after=60, raw_error={'local_admission': True})
            request = request.model_copy(update={'max_tokens': output_tokens})
        reservation = admission.reserve('credential', cred.id, rpm=cred.rpm_limit, tpm=cred.tpm_limit,
            concurrency=cred.max_concurrency, tokens=prompt_tokens + (output_tokens or 0))
        return reservation, request

    @classmethod
    async def _reserve_dispatch(cls, cred, provider, model_obj, request):
        # Reject native history before charging quota or dispatching to a lossy adapter.
        wire = getattr(provider, 'adapter_type', '')
        module = (getattr(provider, 'configuration', None) or {}).get('module_id')
        from urllib.parse import urlparse
        from app.schemas.chat import openrouter_reasoning_details
        if wire in ('openai', 'generic_openai', 'openrouter') and urlparse(getattr(provider, 'base_url', '') or '').hostname in ('openrouter.ai', 'api.kilo.ai'):
            try:
                request = request.model_copy(update={'messages': [message.model_copy(update={
                    'reasoning_details': openrouter_reasoning_details(message.reasoning_details),
                }) if message.reasoning_details else message for message in request.messages]})
            except ValueError as exc:
                raise RouterException(str(exc), ErrorCategory.INVALID_REQUEST, status_code=400) from exc
        supported = ({'thinking', 'redacted_thinking'} if wire == 'anthropic' else
                     {'reasoning'} if wire == 'custom_module' and module in ('codex_cli', 'grok_builder_cli') else set())
        if any(detail.get('type') in {'reasoning', 'thinking', 'redacted_thinking'} - supported
               for message in request.messages for detail in message.reasoning_details or []):
            raise RouterException('Selected adapter cannot preserve native reasoning history',
                                  ErrorCategory.INVALID_REQUEST, status_code=400)
        if wire != 'anthropic' and (any(message.is_error is not None or message.cache_control is not None
                or isinstance(message.content, list) and any(part.get('cache_control') is not None for part in message.content)
                or any((call.extra_content or {}).get('anthropic') for call in message.tool_calls or [])
                for message in request.messages) or any(tool.get('cache_control') is not None for tool in request.tools or [])):
            raise RouterException('Selected adapter cannot preserve Anthropic history/cache metadata',
                                  ErrorCategory.INVALID_REQUEST, status_code=400)
        from app.services.quota_service import QuotaService
        quota, request = await QuotaService.reserve_dispatch(provider, model_obj, request, credential=cred)
        try:
            reservation, request = cls._reserve_credential(cred, request, model_obj)
            return reservation, request, quota
        except BaseException:
            if quota is not None:
                await quota.finish(dispatched=False)
            raise

    @classmethod
    def _dispatch_deadline(cls, timeout):
        timeout = settings.DEFAULT_TIMEOUT_SECONDS if timeout is None else timeout
        if (not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
                or not math.isfinite(timeout) or timeout <= 0):
            raise RouterException('Dispatch timeout must be positive and finite', ErrorCategory.INVALID_REQUEST)
        return time.monotonic() + timeout

    @staticmethod
    async def _pause_retry(error, attempt, deadline):
        delay = min(2.0, 0.25 * 2**attempt) * random.uniform(0.5, 1.0)
        retry_after = error.retry_after
        if (isinstance(retry_after, (int, float)) and not isinstance(retry_after, bool)
                and math.isfinite(retry_after) and retry_after > 0):
            delay = max(delay, retry_after)
        if delay >= deadline - time.monotonic():
            return False
        await asyncio.sleep(delay)
        return time.monotonic() < deadline

    @classmethod
    async def _dispatch_chat(cls, adapter, cred, provider, model_obj, *, retry_count=0, **kwargs):
        if not isinstance(retry_count, int) or isinstance(retry_count, bool) or not 0 <= retry_count <= 10:
            raise RouterException('retry_count must be between 0 and 10', ErrorCategory.INVALID_REQUEST)
        deadline = cls._dispatch_deadline(kwargs.get('timeout'))
        for attempt in range(retry_count + 1):
            if not cls._eligible(provider, model_obj, cred):
                raise RouterException('Credential/provider/model unavailable', ErrorCategory.MODEL_NOT_FOUND, status_code=503)
            reservation, kwargs['request'], quota = await cls._reserve_dispatch(cred, provider, model_obj, kwargs['request'])
            dispatch = LogService.start_dispatch(provider, model_obj, kwargs['request'], stream=False)
            dispatch_started = time.perf_counter()
            actual_usage, dispatched = None, False
            try:
                async with asyncio.timeout(max(0, deadline - time.monotonic())):
                    dispatched = True
                    response = await adapter.chat_completions(**kwargs)
                actual_usage = response.usage.model_dump(exclude_unset=True) if response.usage else None
                LogService.dispatch_usage(dispatch, actual_usage)
                LogService.finish_dispatch(dispatch, 'SUCCESS', (time.perf_counter() - dispatch_started) * 1000)
                reservation.finish(response.usage.total_tokens if response.usage else None)
                circuit_breaker.record_success(cred.id, model_obj.provider_model_id)
                return response
            except Exception as e:
                LogService.finish_dispatch(dispatch, 'FAILED', (time.perf_counter() - dispatch_started) * 1000)
                error = e if isinstance(e, RouterException) else adapter.normalize_error(exception=e)
                if attempt >= retry_count or not error.category.is_retryable or error.category == ErrorCategory.RATE_LIMIT:
                    circuit_breaker.record_failure(cred.id, error.category, error.retry_after, error.message, model_obj.provider_model_id)
                    raise error
            finally:
                reservation.finish()
                if quota is not None:
                    await quota.finish(actual_usage, success=dispatch is not None and dispatch['status'] == 'SUCCESS', dispatched=dispatched)
                if dispatch is not None and dispatch['status'] == 'RUNNING':
                    LogService.finish_dispatch(dispatch, 'CANCELLED', (time.perf_counter() - dispatch_started) * 1000)
            # Release capacity before backoff; all attempts share the caller's timeout.
            if not await cls._pause_retry(error, attempt, deadline):
                circuit_breaker.record_failure(cred.id, error.category, error.retry_after, error.message, model_obj.provider_model_id)
                raise error

    @classmethod
    async def _dispatch_stream(cls, adapter, cred, provider, model_obj, *, retry_count=0, **kwargs):
        if not isinstance(retry_count, int) or isinstance(retry_count, bool) or not 0 <= retry_count <= 10:
            raise RouterException('retry_count must be between 0 and 10', ErrorCategory.INVALID_REQUEST)
        deadline = cls._dispatch_deadline(kwargs.get('timeout'))
        for attempt in range(retry_count + 1):
            if not cls._eligible(provider, model_obj, cred):
                raise RouterException('Credential/provider/model unavailable', ErrorCategory.MODEL_NOT_FOUND, status_code=503)
            reservation, kwargs['request'], quota = await cls._reserve_dispatch(cred, provider, model_obj, kwargs['request'])
            started = terminal = False
            dispatch = LogService.start_dispatch(provider, model_obj, kwargs['request'], stream=True)
            dispatch_started = time.perf_counter()
            actual_tokens = None
            actual_usage, dispatched = None, False
            try:
                async with aclosing(adapter.stream_chat(**kwargs)) as source:
                    while True:
                        try:
                            async with asyncio.timeout(max(0, deadline - time.monotonic())):
                                dispatched = True
                                chunk = await anext(source)
                        except StopAsyncIteration:
                            break
                        for frame in chunk.replace('\r\n', '\n').split('\n\n'):
                            data_lines = [line[5:].lstrip(' ') for line in frame.split('\n') if line.startswith('data:')]
                            if not data_lines:
                                continue
                            payload = '\n'.join(data_lines).strip()
                            if payload == '[DONE]':
                                terminal = True
                                LogService.finish_dispatch(dispatch, 'SUCCESS', (time.perf_counter() - dispatch_started) * 1000)
                                continue
                            try:
                                data = json.loads(payload)
                            except ValueError:
                                raise RouterException('Invalid upstream SSE JSON', ErrorCategory.UPSTREAM_5XX)
                            if data.get('error'):
                                from app.core.errors import normalize_upstream_error
                                err = data['error']
                                code = err.get('code') if isinstance(err, dict) else None
                                raise normalize_upstream_error(status_code=code if isinstance(code, int) else 502, response_body=data)
                            if data.get('usage'):
                                usage = data['usage']
                                actual_usage = usage
                                LogService.dispatch_usage(dispatch, usage)
                                actual_tokens = usage.get('total_tokens', usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0))
                            terminal = terminal or any(c.get('finish_reason') for c in data.get('choices', []))
                        started = True
                        yield chunk
                if not terminal:
                    raise RouterException('Upstream stream ended without a terminal event', ErrorCategory.UPSTREAM_5XX)
                circuit_breaker.record_success(cred.id, model_obj.provider_model_id)
                LogService.finish_dispatch(dispatch, 'SUCCESS', (time.perf_counter() - dispatch_started) * 1000)
                return
            except Exception as e:
                LogService.finish_dispatch(dispatch, 'FAILED', (time.perf_counter() - dispatch_started) * 1000)
                error = e if isinstance(e, RouterException) else adapter.normalize_error(exception=e)
                if started or attempt >= retry_count or not error.category.is_retryable or error.category == ErrorCategory.RATE_LIMIT:
                    circuit_breaker.record_failure(cred.id, error.category, error.retry_after, error.message, model_obj.provider_model_id)
                    raise error
            finally:
                reservation.finish(actual_tokens)
                if quota is not None:
                    await quota.finish(actual_usage, success=terminal, dispatched=dispatched)
                if dispatch is not None and dispatch['status'] == 'RUNNING':
                    LogService.finish_dispatch(dispatch, 'CANCELLED', (time.perf_counter() - dispatch_started) * 1000)
            if not await cls._pause_retry(error, attempt, deadline):
                circuit_breaker.record_failure(cred.id, error.category, error.retry_after, error.message, model_obj.provider_model_id)
                raise error

    @classmethod
    def _order_candidates(cls, profile, candidates, request):
        candidates = sorted(candidates, key=lambda c: c.priority_order)
        if getattr(profile, 'randomize_candidates', False):
            random.shuffle(candidates)
        elif profile.strategy == 'round_robin' and candidates:
            key = str(profile.id)
            idx = cls._round_robin_indices.get(key, 0) % len(candidates)
            cls._round_robin_indices[key] = (idx + 1) % len(candidates)
            candidates = candidates[idx:] + candidates[:idx]
        elif profile.strategy == 'cache-optimized' and len(candidates) > 1:
            from app.routing.cache_affinity import apply_prompt_cache_affinity
            candidates, _ = apply_prompt_cache_affinity(candidates, request)
        return candidates

    @classmethod
    async def route_chat_completions(
        cls,
        db: AsyncSession,
        request: ChatCompletionRequest,
        router_key: Optional[RouterApiKey] = None,
        request_id: Optional[str] = None,
        record_log: bool = True,
    ) -> ChatCompletionResponse:
        req_id = request_id or f"req_{uuid.uuid4().hex}"
        model_str = request.model.strip()
        t0 = time.perf_counter()

        # Check permission for model/route
        if router_key:
            cls._check_permissions(router_key, model_str)

        # 1. PRIORITY ROUTE
        if model_str.startswith("route/"):
            return await cls._handle_priority_route(db, request, model_str, router_key, req_id, t0, record_log=record_log)

        # 2. DIRECT ROUTING
        return await cls._handle_direct_route(db, request, model_str, router_key, req_id, t0, record_log=record_log)

    @classmethod
    async def route_stream_chat(
        cls,
        db: Optional[AsyncSession],
        request: ChatCompletionRequest,
        router_key: Optional[RouterApiKey] = None,
        request_id: Optional[str] = None,
        record_log: bool = True,
    ) -> AsyncGenerator[str, None]:
        req_id = request_id or f"req_{uuid.uuid4().hex}"
        model_str = request.model.strip()
        t0 = time.perf_counter()

        if router_key:
            try:
                cls._check_permissions(router_key, model_str)
            except RouterException as perm_err:
                yield f"data: {json.dumps(perm_err.to_openai_dict(request_id=req_id))}\n\n"
                yield "data: [DONE]\n\n"
                return

        async def _stream_runner(session: AsyncSession):
            try:
                if model_str.startswith("route/"):
                    async with aclosing(cls._handle_priority_stream(session, request, model_str, router_key, req_id, t0, record_log=record_log)) as source:
                        async for chunk in source:
                            yield chunk
                else:
                    async with aclosing(cls._handle_direct_stream(session, request, model_str, router_key, req_id, t0, record_log=record_log)) as source:
                        async for chunk in source:
                            yield chunk
            except asyncio.CancelledError:
                # Client disconnected or cancelled request gracefully
                return
            except RouterException as re:
                yield f"data: {json.dumps(re.to_openai_dict(request_id=req_id))}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                err_dict = {
                    "error": {
                        "message": str(e),
                        "type": "router_stream_error",
                        "code": "upstream_error",
                        "request_id": req_id,
                    }
                }
                yield f"data: {json.dumps(err_dict)}\n\n"
                yield "data: [DONE]\n\n"

        if db is not None:
            async with aclosing(_stream_runner(db)) as source:
                async for chunk in source:
                    yield chunk
        else:
            fresh_db = AsyncSessionLocal()
            try:
                async with aclosing(_stream_runner(fresh_db)) as source:
                    async for chunk in source:
                        yield chunk
            finally:
                await _safe_close_session(fresh_db)

    @classmethod
    def _check_permissions(cls, router_key: RouterApiKey, model_str: str):
        has_all = "*" in router_key.permissions
        if model_str.startswith("route/"):
            if not has_all and "routes" not in router_key.permissions:
                raise RouterException("This API key lacks permission to access routing profiles", ErrorCategory.AUTH_ERROR, status_code=403)
            slug = model_str.removeprefix("route/")
            allowed = router_key.allowed_routes if router_key.allowed_routes is not None else ["*"]
            if "*" not in allowed and slug not in allowed:
                raise RouterException(f"Route '{slug}' is not in allowed routes for this API key", ErrorCategory.AUTH_ERROR, status_code=403)
        elif model_str.startswith("fusion/"):
            if not has_all and "fusion" not in router_key.permissions:
                raise RouterException("This API key lacks permission to access fusion profiles", ErrorCategory.AUTH_ERROR, status_code=403)
            slug = model_str.removeprefix("fusion/")
            allowed = router_key.allowed_fusions if router_key.allowed_fusions is not None else ["*"]
            if "*" not in allowed and slug not in allowed:
                raise RouterException(f"Fusion profile '{slug}' is not in allowed fusions for this key", ErrorCategory.AUTH_ERROR, status_code=403)
        elif model_str.startswith("judge/") or model_str.startswith("smart/"):
            if not has_all and "judge" not in router_key.permissions and "judges" not in router_key.permissions and "routes" not in router_key.permissions:
                raise RouterException("This API key lacks permission to access judge profiles", ErrorCategory.AUTH_ERROR, status_code=403)
            slug = model_str.split("/", 1)[1]
            allowed_judges = getattr(router_key, "allowed_judges", None)
            if allowed_judges is None:
                allowed_judges = ["*"]
            if "*" not in allowed_judges and slug not in allowed_judges:
                raise RouterException(f"Judge profile '{slug}' is not in allowed judges for this key", ErrorCategory.AUTH_ERROR, status_code=403)
        else:
            if not has_all and "direct" not in router_key.permissions:
                raise RouterException("This API key lacks permission for direct model access", ErrorCategory.AUTH_ERROR, status_code=403)
            allowed = router_key.allowed_models if router_key.allowed_models is not None else ["*"]
            if "*" not in allowed and model_str not in allowed:
                raise RouterException(f"Model '{model_str}' is not in allowed models for this API key", ErrorCategory.AUTH_ERROR, status_code=403)

    @staticmethod
    def _client_parameter_fields(request: ChatCompletionRequest) -> Set[str]:
        return getattr(request, "_routing_client_fields", {
            field for field in ("temperature", "reasoning_effort", "reasoning", "thinking")
            if getattr(request, field, None) is not None
        })

    @staticmethod
    def _apply_thinking_effort(request: ChatCompletionRequest, eff_thinking: Optional[str]) -> ChatCompletionRequest:
        client_fields = RoutingEngine._client_parameter_fields(request)
        if not eff_thinking or client_fields.intersection(("reasoning_effort", "reasoning", "thinking")):
            return request
        cand_request = request.model_copy()
        object.__setattr__(cand_request, "_routing_client_fields", client_fields)
        cand_request.thinking = None
        cand_request.reasoning = None
        if eff_thinking in ("off", "none"):
            cand_request.reasoning_effort = "none"
            cand_request.thinking = {"type": "disabled"}
        elif eff_thinking == "auto":
            cand_request.reasoning_effort = "auto"
        else:
            cand_request.reasoning_effort = eff_thinking
            if eff_thinking.isdigit():
                cand_request.thinking = {"type": "enabled", "budget_tokens": int(eff_thinking)}
            else:
                budget_map = {
                    "low": 1024,
                    "medium": 4096,
                    "high": 16384,
                    "minimal": 1024,
                    "maximum": 32768,
                    "thorough": 16384,
                }
                budget = budget_map.get(eff_thinking.lower(), 4096)
                cand_request.thinking = {"type": "enabled", "budget_tokens": budget}
        return cand_request

    @classmethod
    def _apply_model_defaults(
        cls,
        request: ChatCompletionRequest,
        model_obj: Optional[Any] = None,
        eff_thinking: Optional[str] = None,
        candidate_temperature: Optional[float] = None,
        profile_temperature: Optional[float] = None,
    ) -> ChatCompletionRequest:
        cand_request = cls._apply_thinking_effort(request, eff_thinking)
        req_temp = getattr(cand_request, "temperature", None) if not isinstance(cand_request, dict) else cand_request.get("temperature")
        eff_temp = None
        if req_temp is not None and "temperature" in cls._client_parameter_fields(request):
            eff_temp = req_temp
        elif candidate_temperature is not None:
            eff_temp = candidate_temperature
        elif profile_temperature is not None:
            eff_temp = profile_temperature
        elif req_temp is not None:
            eff_temp = req_temp
        elif model_obj is not None and getattr(model_obj, "temperature", None) is not None:
            eff_temp = getattr(model_obj, "temperature", None)

        if eff_temp is not None:
            if hasattr(cand_request, "temperature"):
                if cand_request.temperature != float(eff_temp):
                    if cand_request is request and hasattr(cand_request, "model_copy"):
                        cand_request = cand_request.model_copy()
                        object.__setattr__(cand_request, "_routing_client_fields", cls._client_parameter_fields(request))
                    cand_request.temperature = float(eff_temp)
            elif isinstance(cand_request, dict):
                cand_request["temperature"] = float(eff_temp)

        return cand_request

    @classmethod
    async def prepare_effective_request(
        cls, db: AsyncSession, request: ChatCompletionRequest,
        router_key: Optional[RouterApiKey] = None,
    ) -> Tuple[ChatCompletionRequest, Dict[str, Any]]:
        """Resolve only unambiguous cache contexts; actual routing validates misses.

        The returned request retains its route alias for dispatch. Defaults share
        the upstream helper; ambiguous groups/fallbacks/dynamic routes skip cache.
        Configuration values are hashed, never exposed in the context.
        """
        model_str = request.model.strip()
        if router_key is not None:
            cls._check_permissions(router_key, model_str)
        context = {"skip_response_cache": True, "supports_vision": None,
                   "config_fingerprint": ""}
        profile = candidate = None
        if model_str.startswith(("fusion/", "judge/", "smart/")):
            return request, context
        if model_str.startswith("route/"):
            profile = await RoutingService.get_profile_by_slug(db, model_str)
            if not profile or not profile.enabled:
                return request, context
            candidates = [c for c in profile.candidates if c.is_active]
            if len(candidates) != 1:
                return request, context
            candidate = candidates[0]
            if (candidate.candidate_type == "profile" or candidate.target_profile_id is not None
                    or not candidate.credential_id):
                return request, context
            provider, model_obj = candidate.provider, candidate.model
            cred = candidate.credential
            if not cred or not cred.enabled:
                return request, context
        else:
            pairs = await cls._get_candidate_credentials_for_model(db, model_str)
            if len(pairs) != 1:
                # Multiple credentials may share one resolved upstream identity.
                if pairs and len({(m.provider_id, m.id) for _, m in pairs}) == 1:
                    identity_cred, identity_model = pairs[0]
                    context.update(resolved_model_id=identity_model.provider_model_id,
                        resolved_model_slug=identity_model.canonical_slug,
                        provider_identity=(identity_cred.provider.configuration or {}).get('module_id') or identity_cred.provider.adapter_type,
                        supports_prompt_cache=(identity_model.capabilities or {}).get('prompt_caching'))
                return request, context
            cred, model_obj = pairs[0]
            provider = cred.provider
        if (not provider or not getattr(provider, "enabled", False) or not model_obj
                or not getattr(model_obj, "enabled", False) or not getattr(model_obj, "available", False)):
            return request, context
        eff_thinking = (getattr(candidate, "thinking_effort", None)
                        or getattr(profile, "thinking_effort", None)
                        or request.get_effective_reasoning_effort()
                        or getattr(model_obj, "reasoning_effort", None))
        effective = cls._apply_model_defaults(
            request, model_obj, eff_thinking,
            candidate_temperature=getattr(candidate, "temperature", None),
            profile_temperature=getattr(profile, "temperature", None),
        )
        # Explicit allowlist: never serialize credential secrets or whole ORM rows.
        fields = ("id", "updated_at", "temperature", "reasoning_effort", "thinking_effort",
                  "strategy", "randomize_candidates", "credential_id", "credential_group",
                  "provider_model_id", "canonical_slug", "capabilities", "context_length",
                  "max_output_tokens", "timeout_seconds", "fallback_conditions", "input_price_per_1m", "output_price_per_1m")
        config = [{field: getattr(obj, field, None) for field in fields}
                  for obj in (profile, candidate, model_obj, cred)]
        config.append({"adapter_type": provider.adapter_type,
                       "base_url": provider.base_url,
                       "updated_at": getattr(provider, "updated_at", None),
                       "configuration": provider.adapter_configuration,
                       "headers": provider.extra_headers,
                       "credential_metadata": getattr(cred, "metadata_json", {})})
        fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True, default=str,
                                                ensure_ascii=False).encode()).hexdigest()
        capabilities = getattr(model_obj, "capabilities", {}) or {}
        vision = capabilities.get("vision")
        context.update(skip_response_cache=False, supports_vision=vision if isinstance(vision, bool) else None,
                       config_fingerprint=fingerprint,
                       resolved_model_id=model_obj.provider_model_id,
                       resolved_model_slug=model_obj.canonical_slug,
                       provider_identity=(provider.configuration or {}).get('module_id') or provider.adapter_type,
                       supports_prompt_cache=capabilities.get('prompt_caching'),
                       provider_name=getattr(provider, "name", None),
                       input_price_per_1m=getattr(model_obj, "input_price_per_1m", None),
                       output_price_per_1m=getattr(model_obj, "output_price_per_1m", None))
        return effective, context

    @classmethod
    async def _handle_direct_route(
        cls,
        db: AsyncSession,
        request: ChatCompletionRequest,
        model_str: str,
        router_key: Optional[RouterApiKey],
        req_id: str,
        t0: float,
        record_log: bool = True,
    ) -> ChatCompletionResponse:
        candidates = await cls._get_candidate_credentials_for_model(db, model_str)
        if not candidates:
            await cls._raise_no_candidates(db, model_str, req_id)

        if len(candidates) > 1:
            from app.routing.cache_affinity import apply_prompt_cache_affinity
            candidates, _ = apply_prompt_cache_affinity(candidates, request)

        attempts_trace = []
        last_exception = None

        for attempt_idx, (cred, model_obj) in enumerate(candidates, start=1):
            provider = cred.provider
            api_key = decrypt_secret(cred.encrypted_api_key)
            proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
            adapter = get_adapter(provider.adapter_type)

            eff_thinking = (
                request.get_effective_reasoning_effort() if hasattr(request, "get_effective_reasoning_effort") else request.reasoning_effort
            ) or getattr(model_obj, "reasoning_effort", None)
            cand_request = cls._apply_model_defaults(request, model_obj, eff_thinking)

            cand_t0 = time.perf_counter()
            try:
                response = await cls._dispatch_chat(adapter, cred, provider, model_obj,
                    base_url=provider.base_url,
                    api_key=api_key,
                    model_id=model_obj.provider_model_id,
                    request=cand_request,
                    extra_headers=provider.extra_headers,
                    configuration=CredentialService.module_runtime_configuration(provider, cred),
                    proxy_url=proxy_url,
                    timeout=settings.DEFAULT_TIMEOUT_SECONDS,
                )
                cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)

                attempts_trace.append({
                    "attempt_number": attempt_idx,
                    "provider_name": provider.name,
                    "credential_name": cred.name,
                    "model_name": model_obj.display_name or model_obj.provider_model_id,
                    "status": "SUCCESS",
                    "http_status": 200,
                    "latency_ms": cand_latency,
                })

                total_latency = round((time.perf_counter() - t0) * 1000, 2)
                p_tokens = response.usage.prompt_tokens if response.usage else 0
                c_tokens = response.usage.completion_tokens if response.usage else 0

                if record_log:
                    await LogService.record_request_log(
                        db=db,
                        request_id=req_id,
                        requested_model=model_str,
                        mode="DIRECT",
                        status="FALLBACK_SUCCESS" if attempt_idx > 1 else "SUCCESS",
                        status_code=200,
                        latency_ms=total_latency,
                        router_key_id=router_key.id if router_key else None,
                        resolved_provider_id=provider.id,
                        resolved_credential_id=cred.id,
                        upstream_model=model_obj.provider_model_id,
                        input_tokens=p_tokens,
                        output_tokens=c_tokens,
                        input_price_per_1m=model_obj.input_price_per_1m or 0.0,
                        output_price_per_1m=model_obj.output_price_per_1m or 0.0,
                        attempts=attempts_trace if len(candidates) > 1 else None,
                    )
                return response
            except Exception as e:
                cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)
                re = e if isinstance(e, RouterException) else adapter.normalize_error(exception=e)
                last_exception = re

                attempts_trace.append({
                    "attempt_number": attempt_idx,
                    "provider_name": provider.name,
                    "credential_name": cred.name,
                    "model_name": model_obj.display_name or model_obj.provider_model_id,
                    "status": "FAILED",
                    "http_status": re.status_code,
                    "error_category": re.category.value,
                    "error_message": re.message,
                    "latency_ms": cand_latency,
                })

                # If the error is client-side / prompt-specific, fallback won't help
                is_eligible = re.category.is_fallback_eligible or re.category == ErrorCategory.AUTH_ERROR
                if not is_eligible:
                    total_latency = round((time.perf_counter() - t0) * 1000, 2)
                    if record_log:
                        await LogService.record_request_log(
                            db=db,
                            request_id=req_id,
                            requested_model=model_str,
                            mode="DIRECT",
                            status="FAILED",
                            status_code=re.status_code,
                            latency_ms=total_latency,
                            router_key_id=router_key.id if router_key else None,
                            resolved_provider_id=provider.id,
                            resolved_credential_id=cred.id,
                            upstream_model=model_obj.provider_model_id,
                            error_category=re.category.value,
                            error_message=re.message,
                            attempts=attempts_trace if len(candidates) > 1 else None,
                        )
                    re.request_id = req_id
                    raise re

                # If eligible, try next available candidate credential
                continue

        # All candidate credentials failed
        total_latency = round((time.perf_counter() - t0) * 1000, 2)
        if record_log:
            await LogService.record_request_log(
                db=db,
                request_id=req_id,
                requested_model=model_str,
                mode="DIRECT",
                status="FAILED",
                status_code=last_exception.status_code if last_exception else 502,
                latency_ms=total_latency,
                router_key_id=router_key.id if router_key else None,
                error_category=last_exception.category.value if last_exception else "UPSTREAM_5XX",
                error_message=f"All {len(candidates)} credentials failed for '{model_str}'. Last: {last_exception.message if last_exception else 'Unknown'}",
                attempts=attempts_trace,
            )
        if last_exception:
            last_exception.request_id = req_id
            raise last_exception
        raise RouterException(f"All credentials failed for model '{model_str}'", ErrorCategory.UPSTREAM_5XX, request_id=req_id)

    @classmethod
    async def _handle_direct_stream(
        cls,
        db: AsyncSession,
        request: ChatCompletionRequest,
        model_str: str,
        router_key: Optional[RouterApiKey],
        req_id: str,
        t0: float,
        record_log: bool = True,
    ) -> AsyncGenerator[str, None]:
        candidates = await cls._get_candidate_credentials_for_model(db, model_str)
        if not candidates:
            await cls._raise_no_candidates(db, model_str, req_id)

        if len(candidates) > 1:
            from app.routing.cache_affinity import apply_prompt_cache_affinity
            candidates, _ = apply_prompt_cache_affinity(candidates, request)

        last_exception = None
        attempts_trace = []
        for attempt_idx, (cred, model_obj) in enumerate(candidates, start=1):
            provider = cred.provider
            api_key = decrypt_secret(cred.encrypted_api_key)
            proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
            adapter = get_adapter(provider.adapter_type)

            has_seen_usage = False
            stream_started = False
            cand_t0 = time.perf_counter()
            prompt_len = sum(len(m.content or "") for m in request.messages)
            approx_input_tokens = max(1, prompt_len // 3)
            approx_output_tokens = 0

            eff_thinking = (
                request.get_effective_reasoning_effort() if hasattr(request, "get_effective_reasoning_effort") else request.reasoning_effort
            ) or getattr(model_obj, "reasoning_effort", None)
            cand_request = cls._apply_model_defaults(request, model_obj, eff_thinking)

            try:
                async with aclosing(cls._dispatch_stream(adapter, cred, provider, model_obj,
                    base_url=provider.base_url,
                    api_key=api_key,
                    model_id=model_obj.provider_model_id,
                    request=cand_request,
                    extra_headers=provider.extra_headers,
                    configuration=CredentialService.module_runtime_configuration(provider, cred),
                    proxy_url=proxy_url,
                    timeout=settings.DEFAULT_TIMEOUT_SECONDS,
                )) as source:
                    async for chunk in source:
                        stream_started = True
                        if '"usage"' in chunk:
                            try:
                                for line in chunk.split("\n"):
                                    if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                                        c_data = json.loads(line[6:])
                                        if "usage" in c_data and c_data["usage"]:
                                            has_seen_usage = True
                                            approx_input_tokens = c_data["usage"].get("prompt_tokens", approx_input_tokens)
                                            approx_output_tokens = c_data["usage"].get("completion_tokens", approx_output_tokens)
                            except Exception:
                                pass
                        else:
                            approx_output_tokens += 1

                        if "data: [DONE]" in chunk:
                            if not has_seen_usage:
                                has_seen_usage = True
                                usage_data = {
                                    "id": req_id,
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model_str,
                                    "choices": [],
                                    "usage": {
                                        "prompt_tokens": approx_input_tokens,
                                        "completion_tokens": max(1, approx_output_tokens),
                                        "total_tokens": approx_input_tokens + max(1, approx_output_tokens),
                                    },
                                }
                                yield f"data: {json.dumps(usage_data)}\n\n"
                            yield chunk
                        else:
                            yield chunk

                if not has_seen_usage and stream_started:
                    has_seen_usage = True
                    usage_data = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_str,
                        "choices": [],
                        "usage": {
                            "prompt_tokens": approx_input_tokens,
                            "completion_tokens": max(1, approx_output_tokens),
                            "total_tokens": approx_input_tokens + max(1, approx_output_tokens),
                        },
                    }
                    yield f"data: {json.dumps(usage_data)}\n\n"
                    yield "data: [DONE]\n\n"

                cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)

                attempts_trace.append({
                    "attempt_number": attempt_idx,
                    "provider_name": provider.name,
                    "credential_name": cred.name,
                    "model_name": model_obj.display_name or model_obj.provider_model_id,
                    "status": "SUCCESS",
                    "http_status": 200,
                    "latency_ms": cand_latency,
                })

                if record_log:
                    total_latency = round((time.perf_counter() - t0) * 1000, 2)
                    try:
                        async with AsyncSessionLocal() as log_db:
                            await LogService.record_request_log(
                                db=log_db,
                                request_id=req_id,
                                requested_model=model_str,
                                mode="DIRECT",
                                status="FALLBACK_SUCCESS" if attempt_idx > 1 else "SUCCESS",
                                status_code=200,
                                latency_ms=total_latency,
                                router_key_id=router_key.id if router_key else None,
                                resolved_provider_id=provider.id,
                                resolved_credential_id=cred.id,
                                upstream_model=model_obj.provider_model_id,
                                input_tokens=approx_input_tokens,
                                output_tokens=approx_output_tokens,
                                input_price_per_1m=model_obj.input_price_per_1m or 0.0,
                                output_price_per_1m=model_obj.output_price_per_1m or 0.0,
                                metadata_json={"stream": True},
                                attempts=attempts_trace if len(candidates) > 1 else None,
                            )
                    except Exception:
                        pass
                return
            except Exception as e:
                cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)
                re = e if isinstance(e, RouterException) else adapter.normalize_error(exception=e)
                last_exception = re

                attempts_trace.append({
                    "attempt_number": attempt_idx,
                    "provider_name": provider.name,
                    "credential_name": cred.name,
                    "model_name": model_obj.display_name or model_obj.provider_model_id,
                    "status": "FAILED",
                    "http_status": re.status_code,
                    "error_category": re.category.value,
                    "error_message": re.message,
                    "latency_ms": cand_latency,
                })

                if stream_started:
                    if record_log:
                        total_latency = round((time.perf_counter() - t0) * 1000, 2)
                        try:
                            async with AsyncSessionLocal() as log_db:
                                await LogService.record_request_log(
                                    db=log_db,
                                    request_id=req_id,
                                    requested_model=model_str,
                                    mode="DIRECT",
                                    status="FAILED",
                                    status_code=re.status_code,
                                    latency_ms=total_latency,
                                    router_key_id=router_key.id if router_key else None,
                                    resolved_provider_id=provider.id,
                                    resolved_credential_id=cred.id,
                                    upstream_model=model_obj.provider_model_id,
                                    error_category=re.category.value,
                                    error_message=re.message,
                                    metadata_json={"stream": True},
                                    attempts=attempts_trace if len(candidates) > 1 else None,
                                )
                        except Exception:
                            pass
                    re.request_id = req_id
                    raise re

                is_eligible = re.category.is_fallback_eligible or re.category == ErrorCategory.AUTH_ERROR
                if not is_eligible:
                    if record_log:
                        total_latency = round((time.perf_counter() - t0) * 1000, 2)
                        try:
                            async with AsyncSessionLocal() as log_db:
                                await LogService.record_request_log(
                                    db=log_db,
                                    request_id=req_id,
                                    requested_model=model_str,
                                    mode="DIRECT",
                                    status="FAILED",
                                    status_code=re.status_code,
                                    latency_ms=total_latency,
                                    router_key_id=router_key.id if router_key else None,
                                    resolved_provider_id=provider.id,
                                    resolved_credential_id=cred.id,
                                    upstream_model=model_obj.provider_model_id,
                                    error_category=re.category.value,
                                    error_message=re.message,
                                    metadata_json={"stream": True},
                                    attempts=attempts_trace if len(candidates) > 1 else None,
                                )
                        except Exception:
                            pass
                    re.request_id = req_id
                    raise re
                continue

        if record_log:
            total_latency = round((time.perf_counter() - t0) * 1000, 2)
            try:
                async with AsyncSessionLocal() as log_db:
                    await LogService.record_request_log(
                        db=log_db,
                        request_id=req_id,
                        requested_model=model_str,
                        mode="DIRECT",
                        status="FAILED",
                        status_code=last_exception.status_code if last_exception else 502,
                        latency_ms=total_latency,
                        router_key_id=router_key.id if router_key else None,
                        error_category=last_exception.category.value if last_exception else "UPSTREAM_5XX",
                        error_message=f"All {len(candidates)} credentials failed streaming for '{model_str}'. Last: {last_exception.message if last_exception else 'Unknown'}",
                        metadata_json={"stream": True},
                        attempts=attempts_trace,
                    )
            except Exception:
                pass

        if last_exception:
            last_exception.request_id = req_id
            raise last_exception
        raise RouterException(f"All credentials failed streaming for model '{model_str}'", ErrorCategory.UPSTREAM_5XX, request_id=req_id)

    @classmethod
    async def _handle_priority_route(
        cls,
        db: AsyncSession,
        request: ChatCompletionRequest,
        model_str: str,
        router_key: Optional[RouterApiKey],
        req_id: str,
        t0: float,
        visited_profile_ids: Optional[Set[int]] = None,
        parent_attempts_trace: Optional[List[Dict[str, Any]]] = None,
        root_model_str: Optional[str] = None,
        record_log: bool = True,
    ) -> ChatCompletionResponse:
        profile = await RoutingService.get_profile_by_slug(db, model_str)
        if not profile or not profile.enabled:
            raise RouterException(f"Routing profile '{model_str}' not found or disabled", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)

        candidates = [c for c in profile.candidates if c.is_active]
        if not candidates:
            raise RouterException(f"Routing profile '{model_str}' has no active candidates", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)

        candidates = cls._order_candidates(profile, candidates, request)

        active_visited = set(visited_profile_ids or set())
        is_sub_route = bool(visited_profile_ids) or not record_log
        effective_root_model = root_model_str or model_str
        active_visited.add(profile.id)

        attempts_trace = parent_attempts_trace if parent_attempts_trace is not None else []
        last_exception = None

        for cand_idx, candidate in enumerate(candidates):
            # Handle NESTED ROUTING PROFILE Candidate
            if candidate.candidate_type == "profile" or candidate.target_profile_id is not None:
                attempt_idx = len(attempts_trace) + 1
                target_p = candidate.target_profile
                if not target_p and candidate.target_profile_id:
                    target_p = (await db.execute(select(RoutingProfile).where(RoutingProfile.id == candidate.target_profile_id))).scalar_one_or_none()

                if not target_p or not target_p.enabled:
                    attempts_trace.append({
                        "attempt_number": attempt_idx,
                        "provider_name": "SubRoute",
                        "credential_name": "Profile",
                        "model_name": target_p.name if target_p else f"Profile #{candidate.target_profile_id}",
                        "status": "SKIPPED",
                        "error_category": "MODEL_NOT_FOUND",
                        "error_message": "Nested routing profile not found or disabled",
                        "latency_ms": 0.0,
                    })
                    continue

                if target_p.id in active_visited:
                    attempts_trace.append({
                        "attempt_number": attempt_idx,
                        "provider_name": "SubRoute",
                        "credential_name": "Profile",
                        "model_name": target_p.name,
                        "status": "SKIPPED",
                        "error_category": "CIRCULAR_DEPENDENCY",
                        "error_message": "Circular nested profile reference prevented",
                        "latency_ms": 0.0,
                    })
                    continue

                sub_t0 = time.perf_counter()
                initial_attempts_len = len(attempts_trace)
                try:
                    sub_req = cls._apply_model_defaults(
                        request,
                        eff_thinking=(getattr(candidate, "thinking_effort", None)
                                      or getattr(profile, "thinking_effort", None)),
                        candidate_temperature=getattr(candidate, "temperature", None),
                        profile_temperature=getattr(profile, "temperature", None),
                    )
                    sub_response = await cls._handle_priority_route(
                        db=db,
                        request=sub_req,
                        model_str=f"route/{target_p.slug}",
                        router_key=router_key,
                        req_id=req_id,
                        t0=t0,
                        visited_profile_ids=active_visited,
                        parent_attempts_trace=attempts_trace,
                        root_model_str=effective_root_model,
                        record_log=record_log,
                    )
                    return sub_response
                except Exception as e:
                    sub_lat = round((time.perf_counter() - sub_t0) * 1000, 2)
                    re = e if isinstance(e, RouterException) else RouterException(str(e), ErrorCategory.UPSTREAM_5XX)
                    last_exception = re
                    if len(attempts_trace) == initial_attempts_len:
                        attempts_trace.append({
                            "attempt_number": len(attempts_trace) + 1,
                            "provider_name": "SubRoute",
                            "credential_name": target_p.name,
                            "model_name": f"route/{target_p.slug}",
                            "status": "FAILED",
                            "http_status": re.status_code,
                            "error_category": re.category.value if hasattr(re.category, "value") else str(re.category),
                            "error_message": re.message,
                            "latency_ms": sub_lat,
                        })
                    is_cat_fallback = (
                        re.category.is_fallback_eligible
                        or re.category == ErrorCategory.AUTH_ERROR
                    )
                    in_profile_conds = (
                        profile.fallback_conditions is None
                        or (re.category.value in profile.fallback_conditions)
                    )
                    if not (is_cat_fallback and in_profile_conds):
                        raise re
                    continue

            # Handle STANDARD MODEL Candidate
            provider = candidate.provider
            model_obj = candidate.model
            if (
                not provider
                or not provider.enabled
                or not model_obj
                or not model_obj.enabled
                or not model_obj.available
            ):
                attempts_trace.append({
                    "attempt_number": len(attempts_trace) + 1,
                    "provider_name": provider.name if provider else "Unknown",
                    "credential_name": "None",
                    "model_name": (model_obj.display_name or model_obj.provider_model_id) if model_obj else "Unknown",
                    "status": "SKIPPED",
                    "error_category": "DISABLED",
                    "error_message": "Provider or model is disabled/unavailable",
                    "latency_ms": 0.0,
                })
                continue

            # Get credentials to attempt for this candidate:
            # If candidate.credential_id is set -> try only that specific credential.
            # If candidate.credential_id is None -> Full Fallback across all active credentials of this provider!
            creds_to_try = await cls._candidate_credentials(db, provider, model_obj,
                credential_id=candidate.credential_id, credential_group=candidate.credential_group)

            # Random key selection is built-in by default across available credentials
            if len(creds_to_try) > 1:
                creds_to_try = list(creds_to_try)
                if getattr(profile, "strategy", "priority") == "cache-optimized":
                    from app.routing.cache_affinity import apply_prompt_cache_affinity
                    pairs, _ = apply_prompt_cache_affinity([(cred, model_obj) for cred in creds_to_try], request)
                    creds_to_try = [cred for cred, _ in pairs]
                elif profile.randomize_keys:
                    random.shuffle(creds_to_try)

            cand_model_name = f"[{profile.name}] {model_obj.display_name or model_obj.provider_model_id}" if is_sub_route else (model_obj.display_name or model_obj.provider_model_id)

            if not creds_to_try:
                attempts_trace.append({
                    "attempt_number": len(attempts_trace) + 1,
                    "provider_name": provider.name if provider else "Unknown",
                    "credential_name": "None",
                    "model_name": cand_model_name if model_obj else "Unknown",
                    "status": "FAILED",
                    "error_category": "AUTH_ERROR",
                    "error_message": "No enabled credential available for candidate",
                    "latency_ms": 0.0,
                })
                continue

            # Iterate over credentials for this candidate (supporting full fallback across all keys)
            for cred_idx, cred in enumerate(creds_to_try):
                # Circuit breaker check
                is_avail, reason = circuit_breaker.is_available(cred.id, model_obj.provider_model_id)
                if not is_avail:
                    raw_status = circuit_breaker.get_status(cred.id, model_obj.provider_model_id).get("status")
                    cred_status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
                    attempts_trace.append({
                        "attempt_number": len(attempts_trace) + 1,
                        "provider_name": provider.name,
                        "credential_name": cred.name,
                        "model_name": cand_model_name,
                        "status": "SKIPPED",
                        "error_category": cred_status,
                        "error_message": reason,
                        "latency_ms": 0.0,
                    })
                    continue

                # Attempt upstream call with healthy minimum timeout for LLMs
                cand_t0 = time.perf_counter()
                api_key = decrypt_secret(cred.encrypted_api_key)
                proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
                adapter = get_adapter(provider.adapter_type)
                candidate_timeout = float(profile.timeout_seconds)

                # Apply candidate/profile thinking effort override
                eff_thinking = (
                    getattr(candidate, "thinking_effort", None)
                    or getattr(profile, "thinking_effort", None)
                    or (request.get_effective_reasoning_effort() if hasattr(request, "get_effective_reasoning_effort") else request.reasoning_effort)
                    or getattr(model_obj, "reasoning_effort", None)
                )
                cand_request = cls._apply_model_defaults(
                    request,
                    model_obj,
                    eff_thinking,
                    candidate_temperature=getattr(candidate, "temperature", None),
                    profile_temperature=getattr(profile, "temperature", None),
                )

                try:
                    response = await cls._dispatch_chat(adapter, cred, provider, model_obj, retry_count=profile.retry_count,
                        base_url=provider.base_url,
                        api_key=api_key,
                        model_id=model_obj.provider_model_id,
                        request=cand_request,
                        extra_headers=provider.extra_headers,
                        configuration=CredentialService.module_runtime_configuration(provider, cred),
                        proxy_url=proxy_url,
                        timeout=candidate_timeout,
                    )
                    cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)

                    attempts_trace.append({
                        "attempt_number": len(attempts_trace) + 1,
                        "provider_name": provider.name,
                        "credential_name": cred.name,
                        "model_name": cand_model_name,
                        "status": "SUCCESS",
                        "http_status": 200,
                        "latency_ms": cand_latency,
                    })

                    total_latency = round((time.perf_counter() - t0) * 1000, 2)
                    p_tokens = response.usage.prompt_tokens if response.usage else 0
                    c_tokens = response.usage.completion_tokens if response.usage else 0

                    if record_log:
                        await LogService.record_request_log(
                            db=db,
                            request_id=req_id,
                            requested_model=effective_root_model,
                            mode="PRIORITY",
                            status="FALLBACK_SUCCESS" if len(attempts_trace) > 1 else "SUCCESS",
                            status_code=200,
                            latency_ms=total_latency,
                            router_key_id=router_key.id if router_key else None,
                            resolved_provider_id=provider.id,
                            resolved_credential_id=cred.id,
                            upstream_model=model_obj.provider_model_id,
                            input_tokens=p_tokens,
                            output_tokens=c_tokens,
                            input_price_per_1m=model_obj.input_price_per_1m or 0.0,
                            output_price_per_1m=model_obj.output_price_per_1m or 0.0,
                            attempts=attempts_trace,
                    )
                    return response
                except Exception as e:
                    cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)
                    re = e if isinstance(e, RouterException) else adapter.normalize_error(exception=e)
                    last_exception = re

                    attempts_trace.append({
                        "attempt_number": len(attempts_trace) + 1,
                        "provider_name": provider.name,
                        "credential_name": cred.name,
                        "model_name": cand_model_name,
                        "status": "FAILED",
                        "http_status": re.status_code,
                        "error_category": re.category.value if hasattr(re.category, "value") else str(re.category),
                        "error_message": re.message,
                        "latency_ms": cand_latency,
                    })


                    # More candidates do not override the configured fallback policy.
                    is_cat_fallback = (
                        re.category.is_fallback_eligible
                        or re.category == ErrorCategory.AUTH_ERROR
                    )
                    in_profile_conds = (
                        profile.fallback_conditions is None
                        or (re.category.value in profile.fallback_conditions)
                    )

                    if not (is_cat_fallback and in_profile_conds):
                        if not is_sub_route:
                            total_latency = round((time.perf_counter() - t0) * 1000, 2)
                            await LogService.record_request_log(
                                db=db,
                                request_id=req_id,
                                requested_model=effective_root_model,
                                mode="PRIORITY",
                                status="FAILED",
                                status_code=re.status_code,
                                latency_ms=total_latency,
                                router_key_id=router_key.id if router_key else None,
                                resolved_provider_id=provider.id,
                                resolved_credential_id=cred.id,
                                upstream_model=model_obj.provider_model_id,
                                error_category=re.category.value if hasattr(re.category, "value") else str(re.category),
                                error_message=re.message,
                                attempts=attempts_trace,
                            )
                        re.request_id = req_id
                        raise re

        # All candidates failed
        if not is_sub_route:
            total_latency = round((time.perf_counter() - t0) * 1000, 2)
            await LogService.record_request_log(
                db=db,
                request_id=req_id,
                requested_model=effective_root_model,
                mode="PRIORITY",
                status="FAILED",
                status_code=last_exception.status_code if last_exception else 502,
                latency_ms=total_latency,
                router_key_id=router_key.id if router_key else None,
                error_category=last_exception.category.value if (last_exception and hasattr(last_exception.category, "value")) else ("UPSTREAM_5XX" if not last_exception else str(last_exception.category)),
                error_message=f"All {len(candidates)} candidates in route failed",
                attempts=attempts_trace,
            )

        if last_exception:
            last_exception.request_id = req_id
            raise last_exception
        raise RouterException(
            f"All candidates in '{model_str}' failed. Last error: {last_exception.message if last_exception else 'Unknown'}",
            ErrorCategory.UPSTREAM_5XX,
            status_code=502,
            request_id=req_id,
        )

    @classmethod
    async def _handle_priority_stream(
        cls,
        db: AsyncSession,
        request: ChatCompletionRequest,
        model_str: str,
        router_key: Optional[RouterApiKey],
        req_id: str,
        t0: float,
        visited_profile_ids: Optional[Set[int]] = None,
        parent_attempts_trace: Optional[List[Dict[str, Any]]] = None,
        root_model_str: Optional[str] = None,
        record_log: bool = True,
    ) -> AsyncGenerator[str, None]:
        profile = await RoutingService.get_profile_by_slug(db, model_str)
        if not profile or not profile.enabled:
            raise RouterException(f"Routing profile '{model_str}' not found or disabled", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)

        candidates = [c for c in profile.candidates if c.is_active]
        if not candidates:
            raise RouterException(f"Routing profile '{model_str}' has no active candidates", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)

        candidates = cls._order_candidates(profile, candidates, request)

        is_sub_route = bool(visited_profile_ids) or not record_log
        effective_root_model = root_model_str or model_str
        active_visited = set(visited_profile_ids or set())
        active_visited.add(profile.id)

        last_exception = None
        attempts_trace = parent_attempts_trace if parent_attempts_trace is not None else []
        for cand_idx, candidate in enumerate(candidates):
            # Handle NESTED ROUTING PROFILE Candidate
            if candidate.candidate_type == "profile" or candidate.target_profile_id is not None:
                attempt_idx = len(attempts_trace) + 1
                target_p = candidate.target_profile
                if not target_p and candidate.target_profile_id:
                    target_p = (await db.execute(select(RoutingProfile).where(RoutingProfile.id == candidate.target_profile_id))).scalar_one_or_none()
                if not target_p or not target_p.enabled:
                    attempts_trace.append({
                        "attempt_number": attempt_idx,
                        "provider_name": "SubRoute",
                        "credential_name": "Profile",
                        "model_name": target_p.name if target_p else f"Profile #{candidate.target_profile_id}",
                        "status": "SKIPPED",
                        "error_category": "MODEL_NOT_FOUND",
                        "error_message": "Nested routing profile not found or disabled",
                        "latency_ms": 0.0,
                    })
                    continue

                if target_p.id in active_visited:
                    attempts_trace.append({
                        "attempt_number": attempt_idx,
                        "provider_name": "SubRoute",
                        "credential_name": "Profile",
                        "model_name": target_p.name,
                        "status": "SKIPPED",
                        "error_category": "CIRCULAR_DEPENDENCY",
                        "error_message": "Circular nested profile reference prevented",
                        "latency_ms": 0.0,
                    })
                    continue

                stream_started = False
                sub_t0 = time.perf_counter()
                initial_attempts_len = len(attempts_trace)
                try:
                    sub_req = cls._apply_model_defaults(
                        request,
                        eff_thinking=(getattr(candidate, "thinking_effort", None)
                                      or getattr(profile, "thinking_effort", None)),
                        candidate_temperature=getattr(candidate, "temperature", None),
                        profile_temperature=getattr(profile, "temperature", None),
                    )
                    async with aclosing(cls._handle_priority_stream(
                        db=db,
                        request=sub_req,
                        model_str=f"route/{target_p.slug}",
                        router_key=router_key,
                        req_id=req_id,
                        t0=t0,
                        visited_profile_ids=active_visited,
                        parent_attempts_trace=attempts_trace,
                        root_model_str=effective_root_model,
                        record_log=record_log,
                    )) as source:
                        async for chunk in source:
                            stream_started = True
                            yield chunk
                    return
                except Exception as e:
                    if stream_started:
                        raise
                    sub_lat = round((time.perf_counter() - sub_t0) * 1000, 2)
                    re = e if isinstance(e, RouterException) else RouterException(str(e), ErrorCategory.UPSTREAM_5XX)
                    last_exception = re
                    if len(attempts_trace) == initial_attempts_len:
                        attempts_trace.append({
                            "attempt_number": len(attempts_trace) + 1,
                            "provider_name": "SubRoute",
                            "credential_name": target_p.name,
                            "model_name": f"route/{target_p.slug}",
                            "status": "FAILED",
                            "http_status": re.status_code,
                            "error_category": re.category.value if hasattr(re.category, "value") else str(re.category),
                            "error_message": re.message,
                            "latency_ms": sub_lat,
                        })
                    is_cat_fallback = (
                        re.category.is_fallback_eligible
                        or re.category == ErrorCategory.AUTH_ERROR
                    )
                    in_profile_conds = (
                        profile.fallback_conditions is None
                        or (re.category.value in profile.fallback_conditions)
                    )
                    if not (is_cat_fallback and in_profile_conds):
                        raise re
                    continue

            # Handle STANDARD MODEL Candidate
            provider = candidate.provider
            model_obj = candidate.model
            if (
                not provider
                or not provider.enabled
                or not model_obj
                or not model_obj.enabled
                or not model_obj.available
            ):
                attempts_trace.append({
                    "attempt_number": len(attempts_trace) + 1,
                    "provider_name": provider.name if provider else "Unknown",
                    "credential_name": "None",
                    "model_name": (model_obj.display_name or model_obj.provider_model_id) if model_obj else "Unknown",
                    "status": "SKIPPED",
                    "error_category": "DISABLED",
                    "error_message": "Provider or model is disabled/unavailable",
                    "latency_ms": 0.0,
                })
                continue

            # Get credentials to attempt for this candidate:
            creds_to_try = await cls._candidate_credentials(db, provider, model_obj,
                credential_id=candidate.credential_id, credential_group=candidate.credential_group)

            # Random key selection is built-in by default across available credentials
            if len(creds_to_try) > 1:
                creds_to_try = list(creds_to_try)
                if getattr(profile, "strategy", "priority") == "cache-optimized":
                    from app.routing.cache_affinity import apply_prompt_cache_affinity
                    pairs, _ = apply_prompt_cache_affinity([(cred, model_obj) for cred in creds_to_try], request)
                    creds_to_try = [cred for cred, _ in pairs]
                elif profile.randomize_keys:
                    random.shuffle(creds_to_try)

            cand_model_name = f"[{profile.name}] {model_obj.display_name or model_obj.provider_model_id}" if is_sub_route else (model_obj.display_name or model_obj.provider_model_id)

            if not creds_to_try:
                attempts_trace.append({
                    "attempt_number": len(attempts_trace) + 1,
                    "provider_name": provider.name if provider else "Unknown",
                    "credential_name": "None",
                    "model_name": cand_model_name if model_obj else "Unknown",
                    "status": "FAILED",
                    "error_category": "AUTH_ERROR",
                    "error_message": "No enabled credential available for candidate",
                    "latency_ms": 0.0,
                })
                continue

            for cred_idx, cred in enumerate(creds_to_try):
                is_avail, reason = circuit_breaker.is_available(cred.id, model_obj.provider_model_id)
                if not is_avail:
                    raw_status = circuit_breaker.get_status(cred.id, model_obj.provider_model_id).get("status")
                    cred_status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
                    attempts_trace.append({
                        "attempt_number": len(attempts_trace) + 1,
                        "provider_name": provider.name,
                        "credential_name": cred.name,
                        "model_name": cand_model_name,
                        "status": "SKIPPED",
                        "error_category": cred_status,
                        "error_message": reason,
                        "latency_ms": 0.0,
                    })
                    continue

                api_key = decrypt_secret(cred.encrypted_api_key)
                proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
                adapter = get_adapter(provider.adapter_type)
                candidate_timeout = float(profile.timeout_seconds)

                # Apply candidate/profile thinking effort override
                eff_thinking = (
                    getattr(candidate, "thinking_effort", None)
                    or getattr(profile, "thinking_effort", None)
                    or (request.get_effective_reasoning_effort() if hasattr(request, "get_effective_reasoning_effort") else request.reasoning_effort)
                    or getattr(model_obj, "reasoning_effort", None)
                )
                cand_request = cls._apply_model_defaults(
                    request,
                    model_obj,
                    eff_thinking,
                    candidate_temperature=getattr(candidate, "temperature", None),
                    profile_temperature=getattr(profile, "temperature", None),
                )

                cand_t0 = time.perf_counter()
                prompt_len = sum(len(m.content or "") for m in request.messages)
                approx_input_tokens = max(1, prompt_len // 3)
                approx_output_tokens = 0
                has_seen_usage = False
                stream_started = False

                try:
                    async with aclosing(cls._dispatch_stream(adapter, cred, provider, model_obj, retry_count=profile.retry_count,
                        base_url=provider.base_url,
                        api_key=api_key,
                        model_id=model_obj.provider_model_id,
                        request=cand_request,
                        extra_headers=provider.extra_headers,
                        configuration=CredentialService.module_runtime_configuration(provider, cred),
                        proxy_url=proxy_url,
                        timeout=candidate_timeout,
                    )) as source:
                        async for chunk in source:
                            stream_started = True
                            if '"usage"' in chunk:
                                try:
                                    for line in chunk.split("\n"):
                                        if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                                            c_data = json.loads(line[6:])
                                            if "usage" in c_data and c_data["usage"]:
                                                has_seen_usage = True
                                                approx_input_tokens = c_data["usage"].get("prompt_tokens", approx_input_tokens)
                                                approx_output_tokens = c_data["usage"].get("completion_tokens", approx_output_tokens)
                                except Exception:
                                    pass
                            else:
                                approx_output_tokens += 1

                            if "data: [DONE]" in chunk:
                                if not has_seen_usage:
                                    has_seen_usage = True
                                    usage_data = {
                                        "id": req_id,
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": model_str,
                                        "choices": [],
                                        "usage": {
                                            "prompt_tokens": approx_input_tokens,
                                            "completion_tokens": max(1, approx_output_tokens),
                                            "total_tokens": approx_input_tokens + max(1, approx_output_tokens),
                                        },
                                    }
                                    yield f"data: {json.dumps(usage_data)}\n\n"
                                yield chunk
                            else:
                                yield chunk

                    if not has_seen_usage and stream_started:
                        has_seen_usage = True
                        usage_data = {
                            "id": req_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model_str,
                            "choices": [],
                            "usage": {
                                "prompt_tokens": approx_input_tokens,
                                "completion_tokens": max(1, approx_output_tokens),
                                "total_tokens": approx_input_tokens + max(1, approx_output_tokens),
                            },
                        }
                        yield f"data: {json.dumps(usage_data)}\n\n"
                        yield "data: [DONE]\n\n"

                    cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)

                    attempts_trace.append({
                        "attempt_number": len(attempts_trace) + 1,
                        "provider_name": provider.name,
                        "credential_name": cred.name,
                        "model_name": cand_model_name,
                        "status": "SUCCESS",
                        "http_status": 200,
                        "latency_ms": cand_latency,
                    })

                    if not is_sub_route:
                        total_latency = round((time.perf_counter() - t0) * 1000, 2)
                        try:
                            async with AsyncSessionLocal() as log_db:
                                await LogService.record_request_log(
                                    db=log_db,
                                    request_id=req_id,
                                    requested_model=effective_root_model,
                                    mode="PRIORITY",
                                    status="FALLBACK_SUCCESS" if len(attempts_trace) > 1 else "SUCCESS",
                                    status_code=200,
                                    latency_ms=total_latency,
                                    router_key_id=router_key.id if router_key else None,
                                    resolved_provider_id=provider.id,
                                    resolved_credential_id=cred.id,
                                    upstream_model=model_obj.provider_model_id,
                                    input_tokens=approx_input_tokens,
                                    output_tokens=approx_output_tokens,
                                    input_price_per_1m=model_obj.input_price_per_1m or 0.0,
                                    output_price_per_1m=model_obj.output_price_per_1m or 0.0,
                                    metadata_json={"stream": True},
                                    attempts=attempts_trace,
                                )
                        except Exception:
                            pass
                    return
                except Exception as e:
                    cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)
                    re = e if isinstance(e, RouterException) else adapter.normalize_error(exception=e)
                    last_exception = re

                    attempts_trace.append({
                        "attempt_number": len(attempts_trace) + 1,
                        "provider_name": provider.name,
                        "credential_name": cred.name,
                        "model_name": cand_model_name,
                        "status": "FAILED",
                        "http_status": re.status_code,
                        "error_category": re.category.value if hasattr(re.category, "value") else str(re.category),
                        "error_message": re.message,
                        "latency_ms": cand_latency,
                    })


                    # Check if fallback is eligible:
                    is_cat_fallback = (
                        re.category.is_fallback_eligible
                        or re.category == ErrorCategory.AUTH_ERROR
                    )
                    in_profile_conds = (
                        profile.fallback_conditions is None
                        or (re.category.value in profile.fallback_conditions)
                    )

                    if stream_started or not (is_cat_fallback and in_profile_conds):
                        if not is_sub_route:
                            total_latency = round((time.perf_counter() - t0) * 1000, 2)
                            try:
                                async with AsyncSessionLocal() as log_db:
                                    await LogService.record_request_log(
                                        db=log_db,
                                        request_id=req_id,
                                        requested_model=effective_root_model,
                                        mode="PRIORITY",
                                        status="FAILED",
                                        status_code=re.status_code,
                                        latency_ms=total_latency,
                                        router_key_id=router_key.id if router_key else None,
                                        resolved_provider_id=provider.id,
                                        resolved_credential_id=cred.id,
                                        upstream_model=model_obj.provider_model_id,
                                        error_category=re.category.value if hasattr(re.category, "value") else str(re.category),
                                        error_message=re.message,
                                        metadata_json={"stream": True},
                                        attempts=attempts_trace,
                                    )
                            except Exception:
                                pass
                        re.request_id = req_id
                        raise re
                    continue

        if not is_sub_route:
            total_latency = round((time.perf_counter() - t0) * 1000, 2)
            try:
                async with AsyncSessionLocal() as log_db:
                    await LogService.record_request_log(
                        db=log_db,
                        request_id=req_id,
                        requested_model=effective_root_model,
                        mode="PRIORITY",
                        status="FAILED",
                        status_code=last_exception.status_code if last_exception else 502,
                        latency_ms=total_latency,
                        router_key_id=router_key.id if router_key else None,
                        error_category=last_exception.category.value if (last_exception and hasattr(last_exception.category, "value")) else ("UPSTREAM_5XX" if not last_exception else str(last_exception.category)),
                        error_message=f"All candidates in '{model_str}' failed streaming. Last: {last_exception.message if last_exception else 'Unknown'}",
                        metadata_json={"stream": True},
                        attempts=attempts_trace,
                    )
            except Exception:
                pass

        if last_exception:
            last_exception.request_id = req_id
            raise last_exception
        raise RouterException(f"All candidates in '{model_str}' failed streaming", ErrorCategory.UPSTREAM_5XX, request_id=req_id)

    @classmethod
    async def _get_candidate_credentials_for_model(
        cls, db: AsyncSession, model_str: str
    ) -> List[Tuple[ProviderCredential, DiscoveredModel]]:
        """
        Resolves candidate credentials for direct model routing.
        Rules:
        1. Exact Canonical Slug Match (e.g. 'google/gemini-3.8-flash', 'openrouter/google/gemini-3.8-flash'):
           Only matches models where canonical_slug == model_str AND enabled == True.
           Credentials must strictly belong to that model's provider.
        2. Unprefixed / Raw Model ID Match (e.g. 'gemini-3.8-flash', 'gpt-4o'):
           Matches models where provider_model_id == model_str AND enabled == True.
           If multiple providers offer this model, selects ONLY the native primary provider
           (e.g., 'google' for gemini, 'openai' for gpt/o1/o3, 'anthropic' for claude),
           never mixing credentials from different providers into a direct call.
        3. Only active credentials belonging to that single chosen provider are used.
        """
        clean_model = model_str.strip()

        # Step 1: Check exact match by canonical_slug (e.g. 'google/gemini-3.8-flash')
        query = select(DiscoveredModel).where(
            DiscoveredModel.canonical_slug == clean_model,
            DiscoveredModel.enabled == True,
            DiscoveredModel.available == True,
            DiscoveredModel.provider.has(Provider.enabled == True),
        ).options(
            selectinload(DiscoveredModel.provider),
            selectinload(DiscoveredModel.credential).selectinload(ProviderCredential.proxy),
        )
        result = await db.execute(query)
        matching_models = list(result.scalars().all())

        # Step 2: If no canonical match, check by provider_model_id (e.g. 'gemini-3.8-flash')
        if not matching_models:
            query = select(DiscoveredModel).where(
                DiscoveredModel.provider_model_id == clean_model,
                DiscoveredModel.enabled == True,
                DiscoveredModel.available == True,
                DiscoveredModel.provider.has(Provider.enabled == True),
            ).options(
                selectinload(DiscoveredModel.provider),
                selectinload(DiscoveredModel.credential).selectinload(ProviderCredential.proxy),
            )
            result = await db.execute(query)
            matching_models = list(result.scalars().all())

        if not matching_models:
            return []

        # Step 3: Choose SINGLE primary provider to avoid mixing providers in direct routing
        providers_by_id = {m.provider_id: m.provider for m in matching_models}
        if len(providers_by_id) == 1:
            chosen_provider_id = list(providers_by_id.keys())[0]
        else:
            # Determine native provider by model name heuristic
            low_model = clean_model.lower()
            native_slug = None
            if "gemini" in low_model or "gemma" in low_model:
                native_slug = "google"
            elif "gpt" in low_model or low_model.startswith("o1") or low_model.startswith("o3"):
                native_slug = "openai"
            elif "claude" in low_model:
                native_slug = "anthropic"
            elif "mistral" in low_model or "codestral" in low_model:
                native_slug = "mistral"
            elif "grok" in low_model:
                native_slug = "xai"
            elif "deepseek" in low_model:
                native_slug = "deepseek"
            elif "qwen" in low_model:
                native_slug = "alibaba"
            elif "minimax" in low_model:
                native_slug = "minimax"

            chosen_provider_id = None
            if native_slug:
                for pid, p in providers_by_id.items():
                    if p.slug == native_slug:
                        chosen_provider_id = pid
                        break

            # If no native match or native not found, pick first non-aggregator provider (avoid openrouter/kilo)
            if not chosen_provider_id:
                for pid, p in providers_by_id.items():
                    if p.slug not in ("openrouter", "kilo-ai"):
                        chosen_provider_id = pid
                        break

            # Fallback to first matched provider
            if not chosen_provider_id:
                chosen_provider_id = list(providers_by_id.keys())[0]

        # Filter matching_models to only the chosen provider
        matching_models = [m for m in matching_models if m.provider_id == chosen_provider_id]
        if not matching_models:
            return []

        target_model = matching_models[0]
        provider = target_model.provider

        # Zen's free tier requires the native client; keep the public model name and actual execution profile separate.
        if provider.adapter_type == "generic_openai" and (provider.base_url or "").rstrip("/") in (
                "https://opencode.ai/zen/v1", "https://opencode.ai:443/zen/v1"):
            from app.modules.base import ModuleManifest
            from app.modules.loader import MODULES_DIR, ModuleLoader
            module = ModuleLoader.get_module("lingling")
            manifest = module.manifest if module else ModuleManifest.model_validate_json(
                (MODULES_DIR / "lingling" / "manifest.json").read_text())
            if target_model.provider_model_id in {m.id for m in manifest.default_models}:
                if ModuleLoader.get_adapter("lingling") is None:
                    raise RouterException("Free OpenCode Zen models require the loaded Lingling module", ErrorCategory.MODEL_NOT_FOUND, status_code=503)
                native_models = (await db.execute(select(DiscoveredModel).where(
                    DiscoveredModel.provider_model_id == target_model.provider_model_id,
                    DiscoveredModel.enabled == True, DiscoveredModel.available == True,
                    DiscoveredModel.provider.has(Provider.enabled == True),
                    DiscoveredModel.provider.has(Provider.adapter_type == "custom_module"),
                    DiscoveredModel.provider.has(Provider.configuration["module_id"].as_string() == "lingling"),
                ).options(selectinload(DiscoveredModel.provider)).order_by(DiscoveredModel.credential_id.asc()))).scalars().all()
                native_pairs = {}
                for model_obj in native_models:
                    for cred in await cls._candidate_credentials(db, model_obj.provider, model_obj,
                            credential_id=model_obj.credential_id):
                        native_pairs[cred.id] = (cred, model_obj)
                if native_pairs:
                    return list(native_pairs.values())
                raise RouterException("Free OpenCode Zen models require an enabled, healthy Lingling profile; generic HTTP is unsupported",
                    ErrorCategory.MODEL_NOT_FOUND, status_code=503)

        # Step 4: Find all enabled credentials for this specific primary provider
        p_creds_res = await db.execute(
            select(ProviderCredential).where(
                ProviderCredential.provider_id == provider.id,
                ProviderCredential.enabled == True,
            ).order_by(
                ProviderCredential.priority.asc(),
                ProviderCredential.weight.desc(),
                ProviderCredential.id.asc(),
            ).options(selectinload(ProviderCredential.proxy))
        )
        p_creds = p_creds_res.scalars().all()

        valid_pairs: List[Tuple[ProviderCredential, DiscoveredModel]] = []
        if p_creds:
            for c in p_creds:
                valid_pairs.append((c, target_model))
        elif target_model.credential and target_model.credential.enabled:
            valid_pairs.append((target_model.credential, target_model))

        if not valid_pairs:
            return []

        # Step 5: Separate into available (non-cooldown) and cooldown/unavailable pairs
        available_pairs = [pair for pair in valid_pairs if circuit_breaker.is_available(pair[0].id, pair[1].provider_model_id)[0]]
        active_pool = available_pairs

        # Default random key selection across available credentials for this provider/model
        if len(active_pool) > 1:
            active_pool = list(active_pool)
            random.shuffle(active_pool)

        ordered_candidates = list(active_pool)

        return ordered_candidates

    @classmethod
    async def _select_credential_for_model(
        cls, db: AsyncSession, model_str: str
    ) -> Tuple[Optional[ProviderCredential], Optional[DiscoveredModel]]:
        candidates = await cls._get_candidate_credentials_for_model(db, model_str)
        if not candidates:
            return None, None
        return candidates[0]

    @classmethod
    async def _raise_no_candidates(cls, db: AsyncSession, model_str: str, req_id: str):
        clean_model = model_str.strip()
        disabled_model = (await db.execute(
            select(DiscoveredModel).where(
                (DiscoveredModel.canonical_slug == clean_model) | (DiscoveredModel.provider_model_id == clean_model),
                DiscoveredModel.enabled == False,
            )
        )).scalars().first()
        if disabled_model:
            raise RouterException(
                f"Model '{clean_model}' is disabled in the Models Catalog",
                ErrorCategory.MODEL_NOT_FOUND,
                request_id=req_id,
            )

        any_model = (await db.execute(
            select(DiscoveredModel).where(
                (DiscoveredModel.canonical_slug == clean_model) | (DiscoveredModel.provider_model_id == clean_model),
            )
        )).scalars().first()
        if any_model:
            raise RouterException(
                f"No available healthy credentials found for model '{clean_model}' (credentials may be disabled or in circuit-breaker cooldown)",
                ErrorCategory.TIMEOUT,
                request_id=req_id,
            )

        raise RouterException(
            f"Model '{clean_model}' not found in catalog. Please discover models for its provider first.",
            ErrorCategory.MODEL_NOT_FOUND,
            request_id=req_id,
        )
