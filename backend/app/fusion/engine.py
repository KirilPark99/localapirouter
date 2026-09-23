import asyncio
import time
import uuid
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal, _safe_close_session
from app.models.entities import FusionProfile, FusionParticipant, Provider, ProviderCredential, DiscoveredModel, RouterApiKey
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.core.errors import RouterException, ErrorCategory
from app.core.circuit_breaker import circuit_breaker
from app.core.crypto import decrypt_secret
from app.adapters.factory import get_adapter
from app.services.proxy_service import ProxyService
from app.services.fusion_service import FusionService
from app.services.log_service import LogService
from app.routing.engine import RoutingEngine
from app.core.config import settings

logger = logging.getLogger(__name__)


async def _safe_record_log(**kwargs):
    passed_db = kwargs.get("db")
    try:
        if passed_db is not None:
            await LogService.record_request_log(**kwargs)
            return
    except Exception as e:
        logger.warning(f"Failed to record fusion log using active session: {e}")

    try:
        async with AsyncSessionLocal() as fresh_db:
            kwargs["db"] = fresh_db
            await LogService.record_request_log(**kwargs)
    except Exception as e:
        logger.error(f"Failed to record fusion log in fallback session: {e}")


class FusionEngine:
    @classmethod
    def _format_candidate_draft_block(cls, p: Dict[str, Any]) -> str:
        idx = p.get("idx", 0)
        label = p.get("label") or f"Candidate {chr(65 + idx)}"
        model = p.get("model_name", "Model")
        prov = p.get("provider_name", "")
        lat = p.get("latency_ms", 0.0)
        err = p.get("error")
        content = p.get("content")

        header = f"#### 🤖 {label}: `{model}`"
        if prov:
            header += f" ({prov})"
        header += f" • {lat:.0f}ms\n"

        if content:
            return f"{header}\n{content.strip()}\n\n"
        else:
            return f"{header}\n> ❌ Execution error: {err or 'Failed to obtain response'}\n\n"

    @classmethod
    def _format_ensemble_reasoning(
        cls,
        strategy: str,
        judge_model_name: str,
        candidates: List[Dict[str, Any]],
        judge_reasoning: Optional[str] = None,
    ) -> str:
        strategy_names = {
            "synthesize": "Synthesize best response (Synthesize)",
            "best_of_n": "Select best response (Best-of-N)",
            "consensus": "Find consensus (Consensus)",
            "critique_and_rewrite": "Critique and rewrite (Critique & Rewrite)",
        }
        strat_display = strategy_names.get(strategy, strategy)

        blocks = [
            "### 🧬 Fusion Ensemble Deliberation\n\n",
            f"**Judge Strategy**: {strat_display}\n",
            f"**Judge Model**: `{judge_model_name}`\n\n",
            "---\n\n",
            "### 📋 Candidate Draft Responses:\n\n",
        ]

        for c in candidates:
            blocks.append(cls._format_candidate_draft_block(c))

        blocks.append("---\n\n")
        blocks.append(f"### ⚖️ Judge Evaluation & Verdict (`{judge_model_name}`):\n\n")
        if judge_reasoning and judge_reasoning.strip():
            blocks.append(f"{judge_reasoning.strip()}\n\n")
        else:
            blocks.append(f"The judge evaluated all candidate responses and applied the '{strat_display}' strategy to determine the final output.\n\n")

        return "".join(blocks)

    @classmethod
    def _build_reasoning_chunk(cls, req_id: str, model_str: str, text: str) -> str:
        data = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_str,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "reasoning_content": text,
                    },
                    "finish_reason": None,
                }
            ],
        }
        return f"data: {json.dumps(data)}\n\n"

    @classmethod
    async def execute_fusion(
        cls,
        db: AsyncSession,
        request: ChatCompletionRequest,
        router_key: Optional[RouterApiKey] = None,
        request_id: Optional[str] = None,
    ) -> ChatCompletionResponse:
        req_id = request_id or f"req_{uuid.uuid4().hex}"
        model_str = request.model.strip()
        t0 = time.perf_counter()
        prompt_content = "\n".join([f"[{m.role}]: {m.content}" for m in request.messages if m.content])
        profile = None
        participants_trace: List[Dict[str, Any]] = []
        attempts_trace: List[Dict[str, Any]] = []
        judge_model_name: Optional[str] = None
        judge_provider_name: Optional[str] = None
        judge_credential_name: Optional[str] = None
        resolved_provider_id: Optional[int] = None
        resolved_credential_id: Optional[int] = None

        try:
            if router_key:
                RoutingEngine._check_permissions(router_key, model_str)

            profile = await FusionService.get_profile_by_slug(db, model_str)
            if not profile or not profile.enabled:
                raise RouterException(f"Fusion profile '{model_str}' not found or disabled", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)

            judge_is_profile = (profile.judge_type == "profile") or (profile.judge_routing_profile_id is not None)
            if judge_is_profile:
                if not profile.judge_routing_profile or not profile.judge_routing_profile.enabled:
                    raise RouterException(f"Judge routing profile for '{model_str}' not found or disabled", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)
                judge_model_name = f"route/{profile.judge_routing_profile.slug}"
                judge_provider_name = "Profile"
                judge_credential_name = profile.judge_routing_profile.name
            else:
                if (
                    not profile.judge_provider
                    or not profile.judge_provider.enabled
                    or not profile.judge_model
                    or not profile.judge_model.enabled
                    or not profile.judge_model.available
                ):
                    raise RouterException(f"Judge model for '{model_str}' not found or disabled", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)
                judge_model_name = profile.judge_model.provider_model_id
                judge_provider_name = profile.judge_provider.name
                judge_credential_name = profile.judge_credential.name if profile.judge_credential else "Auto"
                resolved_provider_id = profile.judge_provider.id
                resolved_credential_id = profile.judge_credential.id if profile.judge_credential else None

            def _is_active_part(p: FusionParticipant) -> bool:
                if not p.is_active:
                    return False
                is_p_profile = (p.participant_type == "profile") or (p.target_profile_id is not None)
                if is_p_profile:
                    return bool(p.target_profile and p.target_profile.enabled)
                if not p.provider or not p.provider.enabled:
                    return False
                if not p.model or not p.model.enabled or not p.model.available:
                    return False
                if p.credential_id is not None:
                    return bool(p.credential and p.credential.enabled)
                return True

            active_participants = [p for p in profile.participants if _is_active_part(p)]
            if len(active_participants) < profile.min_successful_candidates:
                raise RouterException(
                    f"Fusion profile requires at least {profile.min_successful_candidates} active participants, but only {len(active_participants)} configured",
                    ErrorCategory.INVALID_REQUEST,
                    request_id=req_id,
                )

            # STEP 2: Async fan-out to all participants
            sem = asyncio.Semaphore(profile.max_parallelism)

            async def run_participant(idx: int, part: FusionParticipant) -> Dict[str, Any]:
                async with sem:
                    return await cls._execute_single_participant(idx, part, request, profile.timeout_seconds, profile=profile)

            tasks = [run_participant(idx, p) for idx, p in enumerate(active_participants)]
            results = await asyncio.gather(*tasks)

            # STEP 3: Collect candidate results
            successful_candidates = []
            total_cand_p_tokens = 0
            total_cand_c_tokens = 0

            for r in results:
                total_cand_p_tokens += r["prompt_tokens"]
                total_cand_c_tokens += r["completion_tokens"]
                is_succ = r["content"] is not None

                participants_trace.append({
                    "idx": r["idx"],
                    "label": r["label"],
                    "model_name": r["model_name"],
                    "provider_name": r["provider_name"],
                    "credential_name": r["credential_name"],
                    "status": "SUCCESS" if is_succ else "FAILED",
                    "latency_ms": r["latency_ms"],
                    "http_status": r["http_status"],
                    "error": r["error"],
                    "content": r["content"] if settings.LOG_REQUEST_CONTENT else None,
                })

                attempts_trace.append({
                    "attempt_number": r["idx"] + 1,
                    "model_name": f"[{r['label']}] {r['model_name']}",
                    "provider_name": r["provider_name"],
                    "credential_name": r["credential_name"],
                    "status": "SUCCESS" if is_succ else "FAILED",
                    "latency_ms": r["latency_ms"],
                    "http_status": r["http_status"],
                    "error_message": r["error"],
                    "error_category": "CANDIDATE_FAILED" if not is_succ else None,
                })

                if is_succ:
                    successful_candidates.append({"label": r["label"], "content": r["content"]})

            if len(successful_candidates) < profile.min_successful_candidates:
                raise RouterException(
                    f"Fusion failed: only {len(successful_candidates)} of {len(active_participants)} candidates succeeded (minimum required: {profile.min_successful_candidates})",
                    ErrorCategory.UPSTREAM_5XX,
                    request_id=req_id,
                )

            # STEP 4: Build Judge Request
            judge_messages = cls._build_judge_prompt(profile, request.messages, successful_candidates)
            judge_t0 = time.perf_counter()
            judge_temp = profile.judge_temperature if profile.judge_temperature is not None else (
                profile.temperature if profile.temperature is not None else (
                    request.temperature if request.temperature is not None else (
                        getattr(profile.judge_model, "temperature", None) if (profile.judge_model and getattr(profile.judge_model, "temperature", None) is not None) else 0.7
                    )
                )
            )

            if judge_is_profile:
                judge_req = ChatCompletionRequest(
                    model=f"route/{profile.judge_routing_profile.slug}",
                    messages=judge_messages,
                    temperature=judge_temp,
                    max_tokens=request.get_effective_max_tokens(),
                    stream=False,
                )
                if profile.judge_thinking_effort:
                    judge_req = RoutingEngine._apply_thinking_effort(judge_req, profile.judge_thinking_effort)
                try:
                    judge_resp = await asyncio.wait_for(
                        RoutingEngine.route_chat_completions(
                            db=db,
                            request=judge_req,
                            router_key=None,
                            request_id=f"{req_id}_judge",
                            record_log=False,
                        ),
                        timeout=profile.timeout_seconds,
                    )
                except Exception as e:
                    re = e if isinstance(e, RouterException) else (
                        RouterException(f"Judge routing profile timed out after {profile.timeout_seconds}s", ErrorCategory.UPSTREAM_TIMEOUT, request_id=req_id)
                        if isinstance(e, asyncio.TimeoutError) else
                        RouterException(f"Judge routing profile failed: {e}", ErrorCategory.UPSTREAM_5XX, request_id=req_id)
                    )
                    raise re
            else:
                judge_req = ChatCompletionRequest(
                    model=profile.judge_model.provider_model_id,
                    messages=judge_messages,
                    temperature=judge_temp,
                    max_tokens=request.get_effective_max_tokens(),
                    stream=False,
                )
                judge_provider = profile.judge_provider
                judge_cred = profile.judge_credential
                if judge_cred and not judge_cred.enabled:
                    judge_cred = None
                if not judge_cred:
                    j_query = select(ProviderCredential).where(
                        ProviderCredential.provider_id == judge_provider.id,
                        ProviderCredential.enabled == True,
                    )
                    if profile.judge_credential_group:
                        j_query = j_query.where(ProviderCredential.group_name == profile.judge_credential_group)
                    j_query = j_query.order_by(ProviderCredential.priority.asc(), ProviderCredential.weight.desc())
                    j_res = await db.execute(j_query)
                    judge_cred = j_res.scalars().first()

                if not judge_cred:
                    raise RouterException("Judge credential not found or disabled", ErrorCategory.AUTH_ERROR, request_id=req_id)

                resolved_credential_id = judge_cred.id
                judge_credential_name = judge_cred.name
                judge_api_key = decrypt_secret(judge_cred.encrypted_api_key)
                judge_proxy = ProxyService.build_proxy_url(judge_cred.proxy) if judge_cred.proxy else None
                judge_adapter = get_adapter(judge_provider.adapter_type)

                eff_judge_thinking = (
                    getattr(profile, "judge_thinking_effort", None)
                    or (judge_req.get_effective_reasoning_effort() if hasattr(judge_req, "get_effective_reasoning_effort") else judge_req.reasoning_effort)
                    or getattr(profile.judge_model, "reasoning_effort", None)
                )
                judge_req = RoutingEngine._apply_thinking_effort(judge_req, eff_judge_thinking)
                try:
                    judge_resp = await asyncio.wait_for(
                        judge_adapter.chat_completions(
                            base_url=judge_provider.base_url,
                            api_key=judge_api_key,
                            model_id=profile.judge_model.provider_model_id,
                            request=judge_req,
                            extra_headers=judge_provider.extra_headers,
                            configuration=judge_provider.adapter_configuration,
                            proxy_url=judge_proxy,
                            timeout=profile.timeout_seconds,
                        ),
                        timeout=profile.timeout_seconds,
                    )
                    circuit_breaker.record_success(judge_cred.id)
                except Exception as e:
                    re = e if isinstance(e, RouterException) else (
                        RouterException(f"Judge request timed out after {profile.timeout_seconds}s", ErrorCategory.UPSTREAM_TIMEOUT, request_id=req_id)
                        if isinstance(e, asyncio.TimeoutError) else
                        judge_adapter.normalize_error(exception=e)
                    )
                    circuit_breaker.record_failure(judge_cred.id, re.category, re.retry_after, re.message)
                    re.request_id = req_id
                    raise re

            judge_latency = round((time.perf_counter() - judge_t0) * 1000, 2)
            total_latency = round((time.perf_counter() - t0) * 1000, 2)
            judge_p_tokens = judge_resp.usage.prompt_tokens if judge_resp.usage else 0
            judge_c_tokens = judge_resp.usage.completion_tokens if judge_resp.usage else 0

            # Replace model in response with fusion slug
            judge_resp.model = model_str
            judge_resp.usage = UsageInfo(
                prompt_tokens=total_cand_p_tokens + judge_p_tokens,
                completion_tokens=total_cand_c_tokens + judge_c_tokens,
                total_tokens=total_cand_p_tokens + total_cand_c_tokens + judge_p_tokens + judge_c_tokens,
            )

            response_content = judge_resp.choices[0].message.content if judge_resp.choices else ""
            judge_reasoning = judge_resp.choices[0].message.reasoning_content if judge_resp.choices else None

            ensemble_reasoning = cls._format_ensemble_reasoning(
                strategy=profile.strategy,
                judge_model_name=judge_model_name or "Judge",
                candidates=results,
                judge_reasoning=judge_reasoning,
            )
            if judge_resp.choices:
                judge_resp.choices[0].message.reasoning_content = ensemble_reasoning

            # Append judge to attempts_trace
            attempts_trace.append({
                "attempt_number": len(attempts_trace) + 1,
                "model_name": f"[Judge] {judge_model_name}",
                "provider_name": judge_provider_name or "Unknown",
                "credential_name": judge_credential_name or "Auto",
                "status": "SUCCESS",
                "latency_ms": judge_latency,
                "http_status": 200,
            })

            # Record SUCCESS Log
            await _safe_record_log(
                db=db,
                request_id=req_id,
                requested_model=model_str,
                mode="FUSION",
                status="FUSION_SUCCESS",
                status_code=200,
                latency_ms=total_latency,
                router_key_id=router_key.id if router_key else None,
                resolved_provider_id=resolved_provider_id,
                resolved_credential_id=resolved_credential_id,
                upstream_model=judge_model_name,
                input_tokens=judge_resp.usage.prompt_tokens,
                output_tokens=judge_resp.usage.completion_tokens,
                prompt_content=prompt_content,
                response_content=response_content,
                attempts=attempts_trace,
                metadata_json={
                    "strategy": profile.strategy,
                    "stream": False,
                    "participants": participants_trace,
                    "deliberation": ensemble_reasoning if settings.LOG_REQUEST_CONTENT else None,
                    "judge": {
                        "model_name": judge_model_name,
                        "provider_name": judge_provider_name,
                        "credential_name": judge_credential_name,
                        "latency_ms": judge_latency,
                        "status": "SUCCESS",
                        "reasoning": judge_reasoning if (settings.LOG_REQUEST_CONTENT and judge_reasoning) else None,
                    },
                },
            )

            return judge_resp

        except RouterException as re:
            total_latency = round((time.perf_counter() - t0) * 1000, 2)
            if judge_model_name and len(attempts_trace) == len(participants_trace):
                judge_lat = round((time.perf_counter() - judge_t0) * 1000, 2) if 'judge_t0' in locals() else 0.0
                attempts_trace.append({
                    "attempt_number": len(attempts_trace) + 1,
                    "model_name": f"[Judge] {judge_model_name}",
                    "provider_name": judge_provider_name or "Unknown",
                    "credential_name": judge_credential_name or "Auto",
                    "status": "FAILED",
                    "latency_ms": judge_lat,
                    "http_status": re.status_code,
                    "error_message": re.message,
                    "error_category": re.category.value if hasattr(re.category, "value") else str(re.category),
                })

            await _safe_record_log(
                db=db,
                request_id=req_id,
                requested_model=model_str,
                mode="FUSION",
                status="FAILED",
                status_code=re.status_code,
                latency_ms=total_latency,
                router_key_id=router_key.id if router_key else None,
                resolved_provider_id=resolved_provider_id,
                resolved_credential_id=resolved_credential_id,
                upstream_model=judge_model_name,
                error_category=re.category.value if hasattr(re.category, "value") else str(re.category),
                error_message=re.message,
                prompt_content=prompt_content,
                attempts=attempts_trace if attempts_trace else None,
                metadata_json={
                    "strategy": profile.strategy if profile else "unknown",
                    "stream": False,
                    "participants": participants_trace,
                    "judge": {
                        "model_name": judge_model_name,
                        "provider_name": judge_provider_name,
                        "credential_name": judge_credential_name,
                        "latency_ms": round((time.perf_counter() - judge_t0) * 1000, 2) if 'judge_t0' in locals() else 0.0,
                        "status": "FAILED",
                        "error": re.message,
                    } if judge_model_name else None,
                },
            )
            re.request_id = req_id
            raise re

        except Exception as e:
            total_latency = round((time.perf_counter() - t0) * 1000, 2)
            err_msg = str(e)
            re = RouterException(f"Fusion error: {err_msg}", ErrorCategory.INTERNAL_ERROR, request_id=req_id)
            await _safe_record_log(
                db=db,
                request_id=req_id,
                requested_model=model_str,
                mode="FUSION",
                status="FAILED",
                status_code=500,
                latency_ms=total_latency,
                router_key_id=router_key.id if router_key else None,
                resolved_provider_id=resolved_provider_id,
                resolved_credential_id=resolved_credential_id,
                upstream_model=judge_model_name,
                error_category="INTERNAL_ERROR",
                error_message=err_msg,
                prompt_content=prompt_content,
                attempts=attempts_trace if attempts_trace else None,
                metadata_json={
                    "strategy": profile.strategy if profile else "unknown",
                    "stream": False,
                    "participants": participants_trace,
                },
            )
            raise re

    @classmethod
    async def _execute_single_participant(
        cls,
        idx: int,
        part: FusionParticipant,
        request: ChatCompletionRequest,
        timeout_seconds: float,
        profile: Optional[FusionProfile] = None,
    ) -> Dict[str, Any]:
        label = part.label or f"Candidate {chr(65 + idx)}"
        p_t0 = time.perf_counter()
        is_profile = (part.participant_type == "profile") or (part.target_profile_id is not None)

        if is_profile and part.target_profile:
            profile_model = f"route/{part.target_profile.slug}"
            provider_name = "Profile"
            credential_name = part.target_profile.name
            async with AsyncSessionLocal() as part_db:
                try:
                    part_req = request.model_copy(deep=True)
                    part_req.model = profile_model
                    part_req.stream = False
                    cand_temp = getattr(part, "temperature", None)
                    prof_temp = getattr(profile, "temperature", None) if profile else None
                    eff_temp = cand_temp if cand_temp is not None else prof_temp
                    if eff_temp is not None:
                        part_req.temperature = float(eff_temp)
                    if getattr(part, "thinking_effort", None):
                        part_req = RoutingEngine._apply_thinking_effort(part_req, part.thinking_effort)
                    resp = await asyncio.wait_for(
                        RoutingEngine.route_chat_completions(
                            db=part_db,
                            request=part_req,
                            router_key=None,
                            request_id=f"part_{idx}_{uuid.uuid4().hex[:6]}",
                            record_log=False,
                        ),
                        timeout=timeout_seconds,
                    )
                    latency = round((time.perf_counter() - p_t0) * 1000, 2)
                    content = resp.choices[0].message.content if resp.choices else ""
                    p_toks = resp.usage.prompt_tokens if resp.usage else 0
                    c_toks = resp.usage.completion_tokens if resp.usage else 0
                    return {
                        "idx": idx,
                        "label": label,
                        "content": content,
                        "error": None,
                        "latency_ms": latency,
                        "prompt_tokens": p_toks,
                        "completion_tokens": c_toks,
                        "model_name": profile_model,
                        "provider_name": provider_name,
                        "credential_name": credential_name,
                        "http_status": 200,
                    }
                except Exception as e:
                    latency = round((time.perf_counter() - p_t0) * 1000, 2)
                    status_code = getattr(e, "status_code", 500)
                    msg = e.message if isinstance(e, RouterException) else str(e)
                    return {
                        "idx": idx,
                        "label": label,
                        "content": None,
                        "error": msg,
                        "latency_ms": latency,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "model_name": profile_model,
                        "provider_name": provider_name,
                        "credential_name": credential_name,
                        "http_status": status_code,
                    }

        # Standard Model candidate
        provider = part.provider
        model_obj = part.model
        cand_model_name = model_obj.provider_model_id if model_obj else "unknown"
        cand_prov_name = provider.name if provider else "unknown"
        cand_cred_name = part.credential.name if (part.credential_id is not None and part.credential) else (part.credential_group or "Auto")

        if not provider or not model_obj:
            return {
                "idx": idx,
                "label": label,
                "content": None,
                "error": "Candidate provider or model not configured",
                "latency_ms": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "model_name": cand_model_name,
                "provider_name": cand_prov_name,
                "credential_name": cand_cred_name,
                "http_status": 400,
            }

        adapter = get_adapter(provider.adapter_type)
        part_req = request.model_copy(deep=True)
        part_req.stream = False
        eff_part_thinking = (
            getattr(part, "thinking_effort", None)
            or (part_req.get_effective_reasoning_effort() if hasattr(part_req, "get_effective_reasoning_effort") else part_req.reasoning_effort)
            or getattr(model_obj, "reasoning_effort", None)
        )
        part_req = RoutingEngine._apply_thinking_effort(part_req, eff_part_thinking)
        cand_temp = getattr(part, "temperature", None)
        prof_temp = getattr(profile, "temperature", None) if profile else None
        eff_temp = cand_temp if cand_temp is not None else (
            prof_temp if prof_temp is not None else (
                request.temperature if request.temperature is not None else getattr(model_obj, "temperature", None)
            )
        )
        if eff_temp is not None:
            part_req.temperature = float(eff_temp)

        # Credentials to try: specific key or all available keys for this provider/group
        if part.credential_id is not None:
            creds_to_try = [part.credential] if (part.credential and part.credential.enabled) else []
        else:
            async with AsyncSessionLocal() as part_db:
                cred_query = select(ProviderCredential).options(selectinload(ProviderCredential.proxy)).where(
                    ProviderCredential.provider_id == provider.id,
                    ProviderCredential.enabled == True,
                )
                if part.credential_group:
                    cred_query = cred_query.where(ProviderCredential.group_name == part.credential_group)
                cred_query = cred_query.order_by(ProviderCredential.priority.asc(), ProviderCredential.weight.desc())
                c_res = await part_db.execute(cred_query)
                creds_to_try = list(c_res.scalars().all())

        if not creds_to_try:
            latency = round((time.perf_counter() - p_t0) * 1000, 2)
            return {
                "idx": idx,
                "label": label,
                "content": None,
                "error": "No active credentials available for candidate",
                "latency_ms": latency,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "model_name": cand_model_name,
                "provider_name": cand_prov_name,
                "credential_name": cand_cred_name,
                "http_status": 503,
            }

        last_err = None
        last_status_code = 502
        for cred in creds_to_try:
            is_avail, _ = circuit_breaker.is_available(cred.id)
            if not is_avail and len(creds_to_try) > 1:
                continue

            try:
                api_key = decrypt_secret(cred.encrypted_api_key)
                proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None

                resp = await asyncio.wait_for(
                    adapter.chat_completions(
                        base_url=provider.base_url,
                        api_key=api_key,
                        model_id=model_obj.provider_model_id,
                        request=part_req,
                        extra_headers=provider.extra_headers,
                        configuration=provider.adapter_configuration,
                        proxy_url=proxy_url,
                        timeout=timeout_seconds,
                    ),
                    timeout=timeout_seconds,
                )
                latency = round((time.perf_counter() - p_t0) * 1000, 2)
                content = resp.choices[0].message.content if resp.choices else ""
                p_toks = resp.usage.prompt_tokens if resp.usage else 0
                c_toks = resp.usage.completion_tokens if resp.usage else 0
                circuit_breaker.record_success(cred.id)
                return {
                    "idx": idx,
                    "label": label,
                    "content": content,
                    "error": None,
                    "latency_ms": latency,
                    "prompt_tokens": p_toks,
                    "completion_tokens": c_toks,
                    "model_name": cand_model_name,
                    "provider_name": cand_prov_name,
                    "credential_name": cred.name,
                    "http_status": 200,
                }
            except Exception as e:
                re = e if isinstance(e, RouterException) else adapter.normalize_error(exception=e)
                last_err = re.message
                last_status_code = re.status_code
                circuit_breaker.record_failure(cred.id, re.category, re.retry_after, re.message)

        latency = round((time.perf_counter() - p_t0) * 1000, 2)
        return {
            "idx": idx,
            "label": label,
            "content": None,
            "error": last_err or "Candidate execution failed",
            "latency_ms": latency,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model_name": cand_model_name,
            "provider_name": cand_prov_name,
            "credential_name": cand_cred_name,
            "http_status": last_status_code,
        }

    @classmethod
    async def execute_fusion_stream(
        cls,
        db: Optional[AsyncSession],
        request: ChatCompletionRequest,
        router_key: Optional[RouterApiKey] = None,
        request_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        req_id = request_id or f"req_{uuid.uuid4().hex}"
        model_str = request.model.strip()
        t0 = time.perf_counter()
        prompt_content = "\n".join([f"[{m.role}]: {m.content}" for m in request.messages if m.content])
        participants_trace: List[Dict[str, Any]] = []
        attempts_trace: List[Dict[str, Any]] = []
        collected_response: List[str] = []
        profile = None
        judge_model_name: Optional[str] = None
        judge_provider_name: Optional[str] = None
        judge_credential_name: Optional[str] = None
        resolved_provider_id: Optional[int] = None
        resolved_credential_id: Optional[int] = None

        async def _stream_runner(session: AsyncSession):
            nonlocal profile, judge_model_name, judge_provider_name, judge_credential_name
            nonlocal resolved_provider_id, resolved_credential_id
            total_cand_p_tokens = 0
            total_cand_c_tokens = 0
            approx_input_tokens = 0
            approx_output_tokens = 0
            judge_t0 = 0.0

            try:
                if router_key:
                    RoutingEngine._check_permissions(router_key, model_str)

                profile = await FusionService.get_profile_by_slug(session, model_str)
                if not profile or not profile.enabled:
                    raise RouterException(f"Fusion profile '{model_str}' not found or disabled", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)

                judge_is_profile = (profile.judge_type == "profile") or (profile.judge_routing_profile_id is not None)
                if judge_is_profile:
                    if not profile.judge_routing_profile or not profile.judge_routing_profile.enabled:
                        raise RouterException(f"Judge routing profile for '{model_str}' not found or disabled", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)
                    judge_model_name = f"route/{profile.judge_routing_profile.slug}"
                    judge_provider_name = "Profile"
                    judge_credential_name = profile.judge_routing_profile.name
                else:
                    if (
                        not profile.judge_provider
                        or not profile.judge_provider.enabled
                        or not profile.judge_model
                        or not profile.judge_model.enabled
                        or not profile.judge_model.available
                    ):
                        raise RouterException(f"Judge model for '{model_str}' not found or disabled", ErrorCategory.MODEL_NOT_FOUND, request_id=req_id)
                    judge_model_name = profile.judge_model.provider_model_id
                    judge_provider_name = profile.judge_provider.name
                    judge_credential_name = profile.judge_credential.name if profile.judge_credential else "Auto"
                    resolved_provider_id = profile.judge_provider.id
                    resolved_credential_id = profile.judge_credential.id if profile.judge_credential else None

                def _is_active_part(p: FusionParticipant) -> bool:
                    if not p.is_active:
                        return False
                    is_p_profile = (p.participant_type == "profile") or (p.target_profile_id is not None)
                    if is_p_profile:
                        return bool(p.target_profile and p.target_profile.enabled)
                    if not p.provider or not p.provider.enabled:
                        return False
                    if not p.model or not p.model.enabled or not p.model.available:
                        return False
                    if p.credential_id is not None:
                        return bool(p.credential and p.credential.enabled)
                    return True

                active_participants = [p for p in profile.participants if _is_active_part(p)]
                if len(active_participants) < profile.min_successful_candidates:
                    raise RouterException(
                        f"Fusion profile requires at least {profile.min_successful_candidates} active participants, but only {len(active_participants)} configured",
                        ErrorCategory.INVALID_REQUEST,
                        request_id=req_id,
                    )

                sem = asyncio.Semaphore(profile.max_parallelism)
                result_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

                strategy_names = {
                    "synthesize": "Synthesize best response (Synthesize)",
                    "best_of_n": "Select best response (Best-of-N)",
                    "consensus": "Find consensus (Consensus)",
                    "critique_and_rewrite": "Critique and rewrite (Critique & Rewrite)",
                }
                strat_display = strategy_names.get(profile.strategy, profile.strategy)

                # Announce ensemble start in reasoning_content
                yield cls._build_reasoning_chunk(
                    req_id,
                    model_str,
                    f"### 🧬 Fusion Ensemble Deliberation\n\n"
                    f"**Strategy**: {strat_display}\n"
                    f"**Judge Model**: `{judge_model_name}`\n"
                    f"**Running Candidates**: {len(active_participants)}\n\n"
                    f"---\n\n### 📋 Candidate Draft Responses:\n\n",
                )

                async def run_participant(idx: int, part: FusionParticipant) -> None:
                    async with sem:
                        res = await cls._execute_single_participant(idx, part, request, profile.timeout_seconds, profile=profile)
                        await result_queue.put(res)

                tasks = [asyncio.create_task(run_participant(idx, p)) for idx, p in enumerate(active_participants)]

                results: List[Dict[str, Any]] = []
                for _ in range(len(active_participants)):
                    r = await result_queue.get()
                    results.append(r)
                    cand_block = cls._format_candidate_draft_block(r)
                    yield cls._build_reasoning_chunk(req_id, model_str, cand_block)

                # Restore original order of participants
                results.sort(key=lambda x: x["idx"])

                successful_candidates = []
                for r in results:
                    total_cand_p_tokens += r["prompt_tokens"]
                    total_cand_c_tokens += r["completion_tokens"]
                    is_succ = r["content"] is not None

                    participants_trace.append({
                        "idx": r["idx"],
                        "label": r["label"],
                        "model_name": r["model_name"],
                        "provider_name": r["provider_name"],
                        "credential_name": r["credential_name"],
                        "status": "SUCCESS" if is_succ else "FAILED",
                        "latency_ms": r["latency_ms"],
                        "http_status": r["http_status"],
                        "error": r["error"],
                        "content": r["content"] if settings.LOG_REQUEST_CONTENT else None,
                    })

                    attempts_trace.append({
                        "attempt_number": r["idx"] + 1,
                        "model_name": f"[{r['label']}] {r['model_name']}",
                        "provider_name": r["provider_name"],
                        "credential_name": r["credential_name"],
                        "status": "SUCCESS" if is_succ else "FAILED",
                        "latency_ms": r["latency_ms"],
                        "http_status": r["http_status"],
                        "error_message": r["error"],
                        "error_category": "CANDIDATE_FAILED" if not is_succ else None,
                    })

                    if is_succ:
                        successful_candidates.append({"label": r["label"], "content": r["content"]})

                if len(successful_candidates) < profile.min_successful_candidates:
                    raise RouterException(
                        f"Fusion failed: only {len(successful_candidates)} of {len(active_participants)} candidates succeeded (minimum required: {profile.min_successful_candidates})",
                        ErrorCategory.UPSTREAM_5XX,
                        request_id=req_id,
                    )

                # Announce judge phase in reasoning_content
                yield cls._build_reasoning_chunk(
                    req_id,
                    model_str,
                    f"---\n\n### ⚖️ Judge Evaluation & Verdict (`{judge_model_name}`):\n\n"
                    f"Judge evaluating candidate responses with strategy '{strat_display}'...\n\n",
                )

                judge_prompt_messages = cls._build_judge_prompt(
                    profile=profile,
                    original_messages=request.messages,
                    candidates=successful_candidates,
                )

                prompt_len = sum(len(m.content or "") for m in judge_prompt_messages)
                approx_input_tokens = max(1, prompt_len // 3)
                has_seen_usage = False
                collected_judge_reasoning: List[str] = []
                judge_t0 = time.perf_counter()

                def _process_chunk_line(line: str) -> Optional[str]:
                    nonlocal approx_input_tokens, approx_output_tokens, has_seen_usage
                    if not line.strip():
                        return None
                    if line.strip() == "data: [DONE]":
                        return None
                    if line.startswith("data: "):
                        raw_json = line[6:].strip()
                        try:
                            c_data = json.loads(raw_json)
                            c_data["model"] = model_str
                            choices = c_data.get("choices") or []
                            if choices:
                                delta = choices[0].get("delta") or {}
                                d_content = delta.get("content")
                                if d_content:
                                    collected_response.append(d_content)
                                d_reasoning = delta.get("reasoning_content")
                                if d_reasoning:
                                    collected_judge_reasoning.append(d_reasoning)
                            if "usage" in c_data and c_data["usage"]:
                                has_seen_usage = True
                                approx_input_tokens = c_data["usage"].get("prompt_tokens", approx_input_tokens)
                                approx_output_tokens = c_data["usage"].get("completion_tokens", approx_output_tokens)
                            else:
                                approx_output_tokens += 1
                            return f"data: {json.dumps(c_data)}"
                        except Exception:
                            return line
                    return line

                judge_temp = profile.judge_temperature if profile.judge_temperature is not None else (
                    profile.temperature if profile.temperature is not None else (
                        request.temperature if request.temperature is not None else (
                            getattr(profile.judge_model, "temperature", None) if (profile.judge_model and getattr(profile.judge_model, "temperature", None) is not None) else 0.5
                        )
                    )
                )

                if judge_is_profile:
                    judge_req = ChatCompletionRequest(
                        model=f"route/{profile.judge_routing_profile.slug}",
                        messages=judge_prompt_messages,
                        temperature=judge_temp,
                        max_tokens=request.max_tokens,
                        stream=True,
                    )
                    if profile.judge_thinking_effort:
                        judge_req = RoutingEngine._apply_thinking_effort(judge_req, profile.judge_thinking_effort)

                    async for chunk in RoutingEngine.route_stream_chat(
                        db=session,
                        request=judge_req,
                        router_key=None,
                        request_id=f"{req_id}_judge",
                        record_log=False,
                    ):
                        lines = chunk.split("\n")
                        processed_lines = []
                        for l in lines:
                            pl = _process_chunk_line(l)
                            if pl:
                                processed_lines.append(pl)
                        if processed_lines:
                            yield "\n".join(processed_lines) + "\n\n"
                else:
                    judge_req = ChatCompletionRequest(
                        model=profile.judge_model.provider_model_id,
                        messages=judge_prompt_messages,
                        temperature=judge_temp,
                        max_tokens=request.max_tokens,
                        stream=True,
                    )
                    judge_provider = profile.judge_provider
                    judge_cred = profile.judge_credential
                    if judge_cred and not judge_cred.enabled:
                        judge_cred = None
                    if not judge_cred:
                        j_query = select(ProviderCredential).where(
                            ProviderCredential.provider_id == judge_provider.id,
                            ProviderCredential.enabled == True,
                        )
                        if profile.judge_credential_group:
                            j_query = j_query.where(ProviderCredential.group_name == profile.judge_credential_group)
                        j_query = j_query.order_by(ProviderCredential.priority.asc(), ProviderCredential.weight.desc())
                        j_res = await session.execute(j_query)
                        judge_cred = j_res.scalars().first()

                    if not judge_cred:
                        raise RouterException("Judge credential not found or disabled", ErrorCategory.AUTH_ERROR, request_id=req_id)

                    resolved_credential_id = judge_cred.id
                    judge_credential_name = judge_cred.name
                    judge_api_key = decrypt_secret(judge_cred.encrypted_api_key)
                    judge_proxy = ProxyService.build_proxy_url(judge_cred.proxy) if judge_cred.proxy else None
                    judge_adapter = get_adapter(judge_provider.adapter_type)

                    eff_judge_thinking = (
                        getattr(profile, "judge_thinking_effort", None)
                        or (judge_req.get_effective_reasoning_effort() if hasattr(judge_req, "get_effective_reasoning_effort") else judge_req.reasoning_effort)
                        or getattr(profile.judge_model, "reasoning_effort", None)
                    )
                    judge_req = RoutingEngine._apply_thinking_effort(judge_req, eff_judge_thinking)

                    async for chunk in judge_adapter.stream_chat(
                        base_url=judge_provider.base_url,
                        api_key=judge_api_key,
                        model_id=profile.judge_model.provider_model_id,
                        request=judge_req,
                        extra_headers=judge_provider.extra_headers,
                        configuration=judge_provider.adapter_configuration,
                        proxy_url=judge_proxy,
                        timeout=profile.timeout_seconds,
                    ):
                        lines = chunk.split("\n")
                        processed_lines = []
                        for l in lines:
                            pl = _process_chunk_line(l)
                            if pl:
                                processed_lines.append(pl)
                        if processed_lines:
                            yield "\n".join(processed_lines) + "\n\n"

                # Stream completed successfully
                judge_latency = round((time.perf_counter() - judge_t0) * 1000, 2)
                total_latency = round((time.perf_counter() - t0) * 1000, 2)
                final_output_tokens = total_cand_c_tokens + max(1, approx_output_tokens)
                final_input_tokens = total_cand_p_tokens + approx_input_tokens
                final_response_text = "".join(collected_response)

                attempts_trace.append({
                    "attempt_number": len(attempts_trace) + 1,
                    "model_name": f"[Judge] {judge_model_name}",
                    "provider_name": judge_provider_name or "Unknown",
                    "credential_name": judge_credential_name or "Auto",
                    "status": "SUCCESS",
                    "latency_ms": judge_latency,
                    "http_status": 200,
                })

                if not has_seen_usage:
                    usage_data = {
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_str,
                        "choices": [],
                        "usage": {
                            "prompt_tokens": final_input_tokens,
                            "completion_tokens": final_output_tokens,
                            "total_tokens": final_input_tokens + final_output_tokens,
                        },
                    }
                    yield f"data: {json.dumps(usage_data)}\n\n"

                judge_r_text = "".join(collected_judge_reasoning)
                ensemble_reasoning = cls._format_ensemble_reasoning(
                    strategy=profile.strategy,
                    judge_model_name=judge_model_name or "Judge",
                    candidates=results,
                    judge_reasoning=judge_r_text,
                )

                # Record SUCCESS log using shielded call BEFORE yielding DONE
                await asyncio.shield(
                    _safe_record_log(
                        db=session,
                        request_id=req_id,
                        requested_model=model_str,
                        mode="FUSION",
                        status="FUSION_SUCCESS",
                        status_code=200,
                        latency_ms=total_latency,
                        router_key_id=router_key.id if router_key else None,
                        resolved_provider_id=resolved_provider_id,
                        resolved_credential_id=resolved_credential_id,
                        upstream_model=judge_model_name,
                        input_tokens=final_input_tokens,
                        output_tokens=final_output_tokens,
                        prompt_content=prompt_content,
                        response_content=final_response_text,
                        attempts=attempts_trace,
                        metadata_json={
                            "strategy": profile.strategy,
                            "stream": True,
                            "participants": participants_trace,
                            "deliberation": ensemble_reasoning if settings.LOG_REQUEST_CONTENT else None,
                            "judge": {
                                "model_name": judge_model_name,
                                "provider_name": judge_provider_name,
                                "credential_name": judge_credential_name,
                                "latency_ms": judge_latency,
                                "status": "SUCCESS",
                                "reasoning": judge_r_text if (settings.LOG_REQUEST_CONTENT and judge_r_text) else None,
                            },
                        },
                    )
                )

                yield "data: [DONE]\n\n"

            except asyncio.CancelledError:
                total_latency = round((time.perf_counter() - t0) * 1000, 2)
                try:
                    await asyncio.shield(
                        _safe_record_log(
                            db=session,
                            request_id=req_id,
                            requested_model=model_str,
                            mode="FUSION",
                            status="CANCELLED",
                            status_code=499,
                            latency_ms=total_latency,
                            router_key_id=router_key.id if router_key else None,
                            resolved_provider_id=resolved_provider_id,
                            resolved_credential_id=resolved_credential_id,
                            upstream_model=judge_model_name,
                            prompt_content=prompt_content,
                            response_content="".join(collected_response),
                            attempts=attempts_trace if attempts_trace else None,
                            metadata_json={
                                "strategy": profile.strategy if profile else "unknown",
                                "stream": True,
                                "participants": participants_trace,
                            },
                        )
                    )
                except Exception:
                    pass
                raise

            except RouterException as re:
                total_latency = round((time.perf_counter() - t0) * 1000, 2)
                if judge_model_name and len(attempts_trace) == len(participants_trace):
                    judge_lat = round((time.perf_counter() - judge_t0) * 1000, 2) if judge_t0 > 0 else 0.0
                    attempts_trace.append({
                        "attempt_number": len(attempts_trace) + 1,
                        "model_name": f"[Judge] {judge_model_name}",
                        "provider_name": judge_provider_name or "Unknown",
                        "credential_name": judge_credential_name or "Auto",
                        "status": "FAILED",
                        "latency_ms": judge_lat,
                        "http_status": re.status_code,
                        "error_message": re.message,
                        "error_category": re.category.value if hasattr(re.category, "value") else str(re.category),
                    })

                try:
                    await asyncio.shield(
                        _safe_record_log(
                            db=session,
                            request_id=req_id,
                            requested_model=model_str,
                            mode="FUSION",
                            status="FAILED",
                            status_code=re.status_code,
                            latency_ms=total_latency,
                            router_key_id=router_key.id if router_key else None,
                            resolved_provider_id=resolved_provider_id,
                            resolved_credential_id=resolved_credential_id,
                            upstream_model=judge_model_name,
                            error_category=re.category.value if hasattr(re.category, "value") else str(re.category),
                            error_message=re.message,
                            prompt_content=prompt_content,
                            attempts=attempts_trace if attempts_trace else None,
                            metadata_json={
                                "strategy": profile.strategy if profile else "unknown",
                                "stream": True,
                                "participants": participants_trace,
                                "judge": {
                                    "model_name": judge_model_name,
                                    "provider_name": judge_provider_name,
                                    "credential_name": judge_credential_name,
                                    "latency_ms": round((time.perf_counter() - judge_t0) * 1000, 2) if judge_t0 > 0 else 0.0,
                                    "status": "FAILED",
                                    "error": re.message,
                                } if judge_model_name else None,
                            },
                        )
                    )
                except Exception:
                    pass

                yield f"data: {json.dumps(re.to_openai_dict(request_id=req_id))}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                total_latency = round((time.perf_counter() - t0) * 1000, 2)
                err_msg = str(e)
                try:
                    await asyncio.shield(
                        _safe_record_log(
                            db=session,
                            request_id=req_id,
                            requested_model=model_str,
                            mode="FUSION",
                            status="FAILED",
                            status_code=500,
                            latency_ms=total_latency,
                            router_key_id=router_key.id if router_key else None,
                            resolved_provider_id=resolved_provider_id,
                            resolved_credential_id=resolved_credential_id,
                            upstream_model=judge_model_name,
                            error_category="INTERNAL_ERROR",
                            error_message=err_msg,
                            prompt_content=prompt_content,
                            attempts=attempts_trace if attempts_trace else None,
                            metadata_json={
                                "strategy": profile.strategy if profile else "unknown",
                                "stream": True,
                                "participants": participants_trace,
                            },
                        )
                    )
                except Exception:
                    pass

                err_dict = {
                    "error": {
                        "message": err_msg,
                        "type": "fusion_stream_error",
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
    def _build_judge_prompt(
        cls,
        profile: FusionProfile,
        original_messages: List[ChatMessage],
        candidates: List[Dict[str, str]],
    ) -> List[ChatMessage]:
        strategy_instructions = {
            "synthesize": (
                "You are an expert impartial AI synthesizer. Several AI models independently responded to the user's prompt. "
                "Synthesize a single comprehensive, highly accurate, coherent answer by combining the strengths and best explanations from all candidates. "
                "Remove redundant repetition, rectify factual inaccuracies, and present the final output directly without meta-commentary."
            ),
            "best_of_n": (
                "You are an expert impartial AI evaluator. Multiple AI models responded to the user's prompt. "
                "Carefully select the single best, most accurate, and complete response among the candidates. "
                "Return the chosen response directly as the final output, preserving its exact helpfulness without meta-commentary."
            ),
            "consensus": (
                "You are an expert consensus evaluator. Multiple AI models answered the user prompt. "
                "Identify points of unanimous agreement and resolve conflicting claims by selecting the most mathematically/factually sound reasoning. "
                "Deliver a coherent consensus response directly to the user."
            ),
            "critique_and_rewrite": (
                "You are an elite code and reasoning reviewer. Multiple candidate drafts were generated for the user's prompt. "
                "Critique each draft internally to spot logical flaws, edge-case bugs, or omissions, then rewrite an ultimate refined, bug-free, and optimal final response."
            ),
        }

        system_instruction = profile.system_prompt or strategy_instructions.get(profile.strategy, strategy_instructions["synthesize"])

        # Format candidates text
        cand_text_blocks = []
        for c in candidates:
            cand_text_blocks.append(f"### {c['label']}\n{c['content']}\n")

        all_candidates_text = "\n\n".join(cand_text_blocks)

        # Original conversation summary / history
        history_text = "\n".join([f"[{m.role.upper()}]: {m.content}" for m in original_messages if m.content])

        judge_user_content = (
            f"=== ORIGINAL USER REQUEST & CONVERSATION ===\n{history_text}\n\n"
            f"=== CANDIDATE MODEL RESPONSES ===\n{all_candidates_text}\n\n"
            f"=== YOUR INSTRUCTION ===\n"
            f"Apply the '{profile.strategy.upper()}' strategy based on the system instructions. "
            f"Provide the final, definitive response to the user's request now. Do not include conversational filler like 'Sure, here is the synthesis'."
        )

        return [
            ChatMessage(role="system", content=system_instruction),
            ChatMessage(role="user", content=judge_user_content),
        ]
