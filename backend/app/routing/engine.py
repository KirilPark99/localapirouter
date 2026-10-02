import asyncio
import json
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
from app.core.circuit_breaker import circuit_breaker, CredentialStatus
from app.core.crypto import decrypt_secret
from app.adapters.factory import get_adapter
from app.services.proxy_service import ProxyService
from app.services.routing_service import RoutingService
from app.services.log_service import LogService

class RoutingEngine:
    _round_robin_indices: Dict[str, int] = {}

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
                    async for chunk in cls._handle_priority_stream(session, request, model_str, router_key, req_id, t0, record_log=record_log):
                        yield chunk
                else:
                    async for chunk in cls._handle_direct_stream(session, request, model_str, router_key, req_id, t0, record_log=record_log):
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
            async for chunk in _stream_runner(db):
                yield chunk
        else:
            fresh_db = AsyncSessionLocal()
            try:
                async for chunk in _stream_runner(fresh_db):
                    yield chunk
            finally:
                await _safe_close_session(fresh_db)

    @classmethod
    def _check_permissions(cls, router_key: RouterApiKey, model_str: str):
        if model_str.startswith("route/"):
            if "routes" not in router_key.permissions:
                raise RouterException("This API key lacks permission to access routing profiles", ErrorCategory.AUTH_ERROR, status_code=403)
            slug = model_str.removeprefix("route/")
            if "*" not in router_key.allowed_routes and slug not in router_key.allowed_routes:
                raise RouterException(f"Route '{slug}' is not in allowed routes for this API key", ErrorCategory.AUTH_ERROR, status_code=403)
        elif model_str.startswith("fusion/"):
            if "fusion" not in router_key.permissions:
                raise RouterException("This API key lacks permission to access fusion profiles", ErrorCategory.AUTH_ERROR, status_code=403)
            slug = model_str.removeprefix("fusion/")
            if "*" not in router_key.allowed_fusions and slug not in router_key.allowed_fusions:
                raise RouterException(f"Fusion profile '{slug}' is not in allowed fusions for this key", ErrorCategory.AUTH_ERROR, status_code=403)
        else:
            if "direct" not in router_key.permissions:
                raise RouterException("This API key lacks permission for direct model access", ErrorCategory.AUTH_ERROR, status_code=403)
            if "*" not in router_key.allowed_models and model_str not in router_key.allowed_models:
                raise RouterException(f"Model '{model_str}' is not in allowed models for this API key", ErrorCategory.AUTH_ERROR, status_code=403)

    @staticmethod
    def _apply_thinking_effort(request: ChatCompletionRequest, eff_thinking: Optional[str]) -> ChatCompletionRequest:
        if not eff_thinking:
            return request
        cand_request = request.model_copy()
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
        if candidate_temperature is not None:
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
                    cand_request.temperature = float(eff_temp)
            elif isinstance(cand_request, dict):
                cand_request["temperature"] = float(eff_temp)

        return cand_request

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
                response = await adapter.chat_completions(
                    base_url=provider.base_url,
                    api_key=api_key,
                    model_id=model_obj.provider_model_id,
                    request=cand_request,
                    extra_headers=provider.extra_headers,
                    configuration={**provider.adapter_configuration, "credential_metadata": getattr(cred, "metadata_json", {})},
                    proxy_url=proxy_url,
                    timeout=60.0,
                )
                cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)
                circuit_breaker.record_success(cred.id, model_obj.provider_model_id)

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
                circuit_breaker.record_failure(cred.id, re.category, re.retry_after, re.message, model_obj.provider_model_id)

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
                async for chunk in adapter.stream_chat(
                    base_url=provider.base_url,
                    api_key=api_key,
                    model_id=model_obj.provider_model_id,
                    request=cand_request,
                    extra_headers=provider.extra_headers,
                    configuration={**provider.adapter_configuration, "credential_metadata": getattr(cred, "metadata_json", {})},
                    proxy_url=proxy_url,
                    timeout=60.0,
                ):
                    stream_started = True
                    if '"usage"' in chunk:
                        has_seen_usage = True
                        try:
                            for line in chunk.split("\n"):
                                if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                                    c_data = json.loads(line[6:])
                                    if "usage" in c_data and c_data["usage"]:
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
                circuit_breaker.record_success(cred.id, model_obj.provider_model_id)

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
                                output_tokens=max(1, approx_output_tokens),
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
                circuit_breaker.record_failure(cred.id, re.category, re.retry_after, re.message, model_obj.provider_model_id)

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

        if getattr(profile, "randomize_candidates", False) and len(candidates) > 1:
            candidates = list(candidates)
            random.shuffle(candidates)

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
                    sub_req = request
                    cand_temp = getattr(candidate, "temperature", None)
                    prof_temp = getattr(profile, "temperature", None)
                    eff_sub_temp = cand_temp if cand_temp is not None else prof_temp
                    if eff_sub_temp is not None:
                        sub_req = request.model_copy()
                        sub_req.temperature = float(eff_sub_temp)
                    if getattr(candidate, "thinking_effort", None):
                        sub_req = cls._apply_thinking_effort(sub_req, candidate.thinking_effort)
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
                    has_more_candidates = (cand_idx < len(candidates) - 1)
                    is_cat_fallback = (
                        re.category.is_fallback_eligible
                        or re.category == ErrorCategory.AUTH_ERROR
                        or has_more_candidates
                    )
                    in_profile_conds = (
                        not profile.fallback_conditions
                        or (re.category.value in profile.fallback_conditions)
                        or (re.category == ErrorCategory.AUTH_ERROR)
                        or has_more_candidates
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
            if candidate.credential_id:
                cand_cred = candidate.credential
                if not cand_cred:
                    cand_cred = (await db.execute(
                        select(ProviderCredential).options(selectinload(ProviderCredential.proxy)).where(ProviderCredential.id == candidate.credential_id)
                    )).scalar_one_or_none()
                creds_to_try = [cand_cred] if (cand_cred and cand_cred.enabled) else []
            else:
                cred_query = (
                    select(ProviderCredential)
                    .options(selectinload(ProviderCredential.proxy))
                    .where(
                        ProviderCredential.provider_id == provider.id,
                        ProviderCredential.enabled == True,
                    )
                )
                if candidate.credential_group:
                    cred_query = cred_query.where(ProviderCredential.group_name == candidate.credential_group)
                cred_query = cred_query.order_by(ProviderCredential.priority.asc(), ProviderCredential.weight.desc())
                cred_res = await db.execute(cred_query)
                creds_to_try = list(cred_res.scalars().all())

            # Random key selection is built-in by default across available credentials
            if len(creds_to_try) > 1:
                creds_to_try = list(creds_to_try)
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
                if not is_avail and (len(creds_to_try) > 1 or len(candidates) > 1):
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
                candidate_timeout = max(float(profile.timeout_seconds or 60.0), 30.0)

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
                    response = await adapter.chat_completions(
                        base_url=provider.base_url,
                        api_key=api_key,
                        model_id=model_obj.provider_model_id,
                        request=cand_request,
                        extra_headers=provider.extra_headers,
                        configuration={**provider.adapter_configuration, "credential_metadata": getattr(cred, "metadata_json", {})},
                        proxy_url=proxy_url,
                        timeout=candidate_timeout,
                    )
                    cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)
                    circuit_breaker.record_success(cred.id, model_obj.provider_model_id)

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
                    circuit_breaker.record_failure(cred.id, re.category, re.retry_after, re.message, model_obj.provider_model_id)

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

                    has_more_creds = (cred_idx < len(creds_to_try) - 1)
                    has_more_candidates = (cand_idx < len(candidates) - 1)
                    has_more_options = has_more_creds or has_more_candidates

                    # Check if fallback is eligible:
                    # Fallback occurs on standard eligible errors, credential auth failures,
                    # or whenever further candidates/credentials exist in this priority route.
                    is_cat_fallback = (
                        re.category.is_fallback_eligible
                        or re.category == ErrorCategory.AUTH_ERROR
                        or has_more_options
                    )
                    in_profile_conds = (
                        not profile.fallback_conditions
                        or (re.category.value in profile.fallback_conditions)
                        or (re.category == ErrorCategory.AUTH_ERROR)
                        or has_more_options
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

        if getattr(profile, "randomize_candidates", False) and len(candidates) > 1:
            candidates = list(candidates)
            random.shuffle(candidates)

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
                    sub_req = request
                    cand_temp = getattr(candidate, "temperature", None)
                    prof_temp = getattr(profile, "temperature", None)
                    eff_sub_temp = cand_temp if cand_temp is not None else prof_temp
                    if eff_sub_temp is not None:
                        sub_req = request.model_copy()
                        sub_req.temperature = float(eff_sub_temp)
                    if getattr(candidate, "thinking_effort", None):
                        sub_req = cls._apply_thinking_effort(sub_req, candidate.thinking_effort)
                    async for chunk in cls._handle_priority_stream(
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
                    ):
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
                    has_more_candidates = (cand_idx < len(candidates) - 1)
                    is_cat_fallback = (
                        re.category.is_fallback_eligible
                        or re.category == ErrorCategory.AUTH_ERROR
                        or has_more_candidates
                    )
                    in_profile_conds = (
                        not profile.fallback_conditions
                        or (re.category.value in profile.fallback_conditions)
                        or (re.category == ErrorCategory.AUTH_ERROR)
                        or has_more_candidates
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
            if candidate.credential_id:
                cand_cred = candidate.credential
                if not cand_cred:
                    cand_cred = (await db.execute(
                        select(ProviderCredential).options(selectinload(ProviderCredential.proxy)).where(ProviderCredential.id == candidate.credential_id)
                    )).scalar_one_or_none()
                creds_to_try = [cand_cred] if (cand_cred and cand_cred.enabled) else []
            else:
                cred_query = (
                    select(ProviderCredential)
                    .options(selectinload(ProviderCredential.proxy))
                    .where(
                        ProviderCredential.provider_id == provider.id,
                        ProviderCredential.enabled == True,
                    )
                )
                if candidate.credential_group:
                    cred_query = cred_query.where(ProviderCredential.group_name == candidate.credential_group)
                cred_query = cred_query.order_by(ProviderCredential.priority.asc(), ProviderCredential.weight.desc())
                cred_res = await db.execute(cred_query)
                creds_to_try = list(cred_res.scalars().all())

            # Random key selection is built-in by default across available credentials
            if len(creds_to_try) > 1:
                creds_to_try = list(creds_to_try)
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
                if not is_avail and (len(creds_to_try) > 1 or len(candidates) > 1):
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
                candidate_timeout = max(float(profile.timeout_seconds or 60.0), 30.0)

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
                    async for chunk in adapter.stream_chat(
                        base_url=provider.base_url,
                        api_key=api_key,
                        model_id=model_obj.provider_model_id,
                        request=cand_request,
                        extra_headers=provider.extra_headers,
                        configuration={**provider.adapter_configuration, "credential_metadata": getattr(cred, "metadata_json", {})},
                        proxy_url=proxy_url,
                        timeout=candidate_timeout,
                    ):
                        stream_started = True
                        if '"usage"' in chunk:
                            has_seen_usage = True
                            try:
                                for line in chunk.split("\n"):
                                    if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                                        c_data = json.loads(line[6:])
                                        if "usage" in c_data and c_data["usage"]:
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
                    circuit_breaker.record_success(cred.id, model_obj.provider_model_id)

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
                                    output_tokens=max(1, approx_output_tokens),
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
                    circuit_breaker.record_failure(cred.id, re.category, re.retry_after, re.message, model_obj.provider_model_id)

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

                    has_more_creds = (cred_idx < len(creds_to_try) - 1)
                    has_more_candidates = (cand_idx < len(candidates) - 1)
                    has_more_options = has_more_creds or has_more_candidates

                    # Check if fallback is eligible:
                    is_cat_fallback = (
                        re.category.is_fallback_eligible
                        or re.category == ErrorCategory.AUTH_ERROR
                        or has_more_options
                    )
                    in_profile_conds = (
                        not profile.fallback_conditions
                        or (re.category.value in profile.fallback_conditions)
                        or (re.category == ErrorCategory.AUTH_ERROR)
                        or has_more_options
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
        active_pool = available_pairs if available_pairs else valid_pairs

        # Default random key selection across available credentials for this provider/model
        if len(active_pool) > 1:
            active_pool = list(active_pool)
            random.shuffle(active_pool)

        ordered_candidates = list(active_pool)

        # If some credentials were in cooldown, append them at the very end as last resort fallback
        if available_pairs and len(available_pairs) < len(valid_pairs):
            cooldown_pairs = [p for p in valid_pairs if p not in available_pairs]
            if len(cooldown_pairs) > 1:
                random.shuffle(cooldown_pairs)
            ordered_candidates.extend(cooldown_pairs)

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
                ErrorCategory.UPSTREAM_TIMEOUT,
                request_id=req_id,
            )

        raise RouterException(
            f"Model '{clean_model}' not found in catalog. Please discover models for its provider first.",
            ErrorCategory.MODEL_NOT_FOUND,
            request_id=req_id,
        )
