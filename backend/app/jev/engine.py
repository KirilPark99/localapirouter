import asyncio
import json
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import (
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
    RoutingCandidate,
    RouterApiKey,
)
from app.schemas.jev import JevRequest, JevResponse, JevUsage
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatMessage,
)
from app.core.errors import RouterException, ErrorCategory, normalize_upstream_error
from app.routing.engine import RoutingEngine
from app.core.circuit_breaker import circuit_breaker
from app.core.crypto import decrypt_secret
from app.core.http_client import http_client_manager
from app.adapters.factory import get_adapter
from app.services.proxy_service import ProxyService
from app.services.log_service import LogService

class JevEngine:
    """
    Execution engine for Jev (System One) decision models.
    Supports native upstream SystemOne endpoints (e.g. TypeSafe AI, OpenRouter /api/v1/systemone)
    and emulation mode for standard OpenAI-compatible models designated as 'jev' type.
    """

    @classmethod
    async def execute_decision(
        cls,
        db: AsyncSession,
        request: JevRequest,
        router_key: Optional[RouterApiKey] = None,
        request_id: Optional[str] = None,
        record_log: bool = True,
    ) -> JevResponse:
        req_id = request_id or f"req_{uuid.uuid4().hex[:16]}"
        model_str = request.model.strip()
        t0 = time.perf_counter()
        request.questions = cls._normalize_questions_for_upstream(request.questions)

        if router_key:
            cls._check_permissions(router_key, model_str)

        # 1. Routing profile support
        if model_str.startswith("route/"):
            return await cls._handle_profile_decision(db, request, model_str, router_key, req_id, t0, record_log=record_log)

        # 2. Direct model execution
        return await cls._handle_direct_decision(db, request, model_str, router_key, req_id, t0, record_log=record_log)

    @classmethod
    def _check_permissions(cls, router_key: RouterApiKey, model_str: str):
        RoutingEngine._check_permissions(router_key, model_str)

    @classmethod
    async def _get_candidates_for_model(
        cls, db: AsyncSession, model_str: str
    ) -> List[Tuple[ProviderCredential, DiscoveredModel]]:
        query = (
            select(DiscoveredModel)
            .join(Provider, DiscoveredModel.provider_id == Provider.id)
            .where(
                (DiscoveredModel.canonical_slug == model_str)
                | (DiscoveredModel.provider_model_id == model_str),
                DiscoveredModel.enabled == True,
                DiscoveredModel.available == True,
                Provider.enabled == True,
            )
            .options(
                selectinload(DiscoveredModel.provider),
                selectinload(DiscoveredModel.credential).selectinload(ProviderCredential.proxy),
            )
        )
        result = await db.execute(query)
        models = result.scalars().all()

        if not models:
            # Fallback: case-insensitive or partial match
            query_fallback = (
                select(DiscoveredModel)
                .join(Provider, DiscoveredModel.provider_id == Provider.id)
                .where(
                    DiscoveredModel.canonical_slug.ilike(f"%{model_str}%"),
                    DiscoveredModel.enabled == True,
                    DiscoveredModel.available == True,
                    Provider.enabled == True,
                )
                .options(
                    selectinload(DiscoveredModel.provider),
                    selectinload(DiscoveredModel.credential).selectinload(ProviderCredential.proxy),
                )
            )
            res_fallback = await db.execute(query_fallback)
            models = res_fallback.scalars().all()

        candidates: List[Tuple[ProviderCredential, DiscoveredModel]] = []
        for m in models:
            if m.credential and m.credential.enabled:
                if circuit_breaker.is_available(m.credential.id, m.provider_model_id)[0]:
                    candidates.append((m.credential, m))
            else:
                # Provider credentials
                c_query = (
                    select(ProviderCredential)
                    .where(
                        ProviderCredential.provider_id == m.provider_id,
                        ProviderCredential.enabled == True,
                    )
                    .options(selectinload(ProviderCredential.proxy))
                )
                c_res = await db.execute(c_query)
                for cred in c_res.scalars().all():
                    if circuit_breaker.is_available(cred.id, m.provider_model_id)[0]:
                        candidates.append((cred, m))

        # Sort by priority desc, then consecutive failures asc
        candidates.sort(key=lambda x: (x[0].priority, -x[0].consecutive_failures), reverse=True)
        return candidates

    @classmethod
    async def _handle_direct_decision(
        cls,
        db: AsyncSession,
        request: JevRequest,
        model_str: str,
        router_key: Optional[RouterApiKey],
        req_id: str,
        t0: float,
        record_log: bool = True,
    ) -> JevResponse:
        candidates = await cls._get_candidates_for_model(db, model_str)
        if not candidates:
            raise RouterException(
                f"No available healthy credentials found for model '{model_str}'. "
                "Ensure credentials are enabled and not in rate-limit cooldown.",
                ErrorCategory.MODEL_NOT_FOUND,
                status_code=503,
            )

        attempts_trace = []
        last_exception = None

        for attempt_idx, (cred, model_obj) in enumerate(candidates, start=1):
            provider = cred.provider
            api_key = decrypt_secret(cred.encrypted_api_key)
            proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
            cand_t0 = time.perf_counter()

            try:
                is_native_jev = cls._is_native_jev_provider(provider, model_obj)
                answers, usage = await cls._dispatch_decision(cred, provider, model_obj, request, proxy_url, 60.0)

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
                in_tok = usage.get("input_tokens", 0) if isinstance(usage, dict) else getattr(usage, "input_tokens", 0)
                out_tok = usage.get("output_tokens", 0) if isinstance(usage, dict) else getattr(usage, "output_tokens", 0)

                if record_log:
                    await LogService.record_request_log(
                        db=db,
                        request_id=req_id,
                        requested_model=model_str,
                        mode="JEV",
                        resolved_provider_id=provider.id,
                        resolved_credential_id=cred.id,
                        upstream_model=model_obj.provider_model_id,
                        latency_ms=total_latency,
                        status_code=200,
                        status="SUCCESS",
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        router_key_id=router_key.id if router_key else None,
                        attempts=attempts_trace,
                        metadata_json={
                            "strategy": "systemone",
                            "questions_count": len(request.questions),
                            "is_native_jev": is_native_jev,
                        },
                        prompt_content=json.dumps({"state": request.state, "questions": request.questions}, ensure_ascii=False),
                        response_content=json.dumps(answers, ensure_ascii=False),
                    )

                return JevResponse(
                    id=f"dec_{uuid.uuid4().hex[:16]}",
                    model=model_str,
                    answers=answers,
                    usage=JevUsage(
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        total_tokens=in_tok + out_tok,
                    ),
                    latency_ms=total_latency,
                )

            except Exception as e:
                cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)
                status_code = getattr(e, "status_code", 500)
                cat = getattr(e, "category", None) or (
                    ErrorCategory.RATE_LIMIT if status_code == 429
                    else ErrorCategory.AUTH_ERROR if status_code in (401, 403)
                    else ErrorCategory.UPSTREAM_5XX
                )
                retry_after = getattr(e, "retry_after", None)


                attempts_trace.append({
                    "attempt_number": attempt_idx,
                    "provider_name": provider.name,
                    "credential_name": cred.name,
                    "model_name": model_obj.display_name or model_obj.provider_model_id,
                    "status": "FAILED",
                    "http_status": status_code,
                    "error_message": str(e),
                    "latency_ms": cand_latency,
                })
                last_exception = e

        total_latency = round((time.perf_counter() - t0) * 1000, 2)
        if record_log:
            await LogService.record_request_log(
                db=db,
                request_id=req_id,
                requested_model=model_str,
                mode="JEV",
                latency_ms=total_latency,
                status_code=last_exception.status_code if isinstance(last_exception, RouterException) else 502,
                status="FAILED",
                error_category=last_exception.category.value if isinstance(last_exception, RouterException) else "UPSTREAM_5XX",
                error_message=str(last_exception) if last_exception else "All credentials failed",
                router_key_id=router_key.id if router_key else None,
                attempts=attempts_trace,
                metadata_json={"strategy": "systemone", "attempts_count": len(attempts_trace)},
            )

        if isinstance(last_exception, RouterException):
            raise last_exception
        raise RouterException(
            f"Jev decision failed after {len(attempts_trace)} attempt(s). Last error: {last_exception}",
            ErrorCategory.UPSTREAM_5XX,
            status_code=502,
        )

    @classmethod
    async def _handle_profile_decision(
        cls,
        db: AsyncSession,
        request: JevRequest,
        model_str: str,
        router_key: Optional[RouterApiKey],
        req_id: str,
        t0: float,
        record_log: bool = True,
    ) -> JevResponse:
        from app.services.routing_service import RoutingService
        slug = model_str.removeprefix('route/')
        profile = await RoutingService.get_profile_by_slug(db, model_str)
        if not profile:
            raise RouterException(f"Routing profile '{slug}' not found or disabled", ErrorCategory.INVALID_REQUEST, status_code=404)

        active_cands = [c for c in profile.candidates if c.is_active and c.provider and c.provider.enabled
                        and c.model and c.model.enabled and c.model.available]
        if not active_cands:
            raise RouterException(f"Routing profile '{slug}' has no active candidates", ErrorCategory.MODEL_NOT_FOUND, status_code=503)

        active_cands = RoutingEngine._order_candidates(profile, active_cands, request)

        attempts_trace = []
        last_exception = None

        for attempt_idx, cand in enumerate(active_cands, start=1):
            if isinstance(last_exception, RouterException) and (not last_exception.category.is_fallback_eligible or
                    (profile.fallback_conditions is not None and last_exception.category.value not in profile.fallback_conditions)):
                break
            model_obj = cand.model
            provider = cand.provider or model_obj.provider
            creds = await RoutingEngine._candidate_credentials(db, provider, model_obj,
                credential_id=cand.credential_id, credential_group=cand.credential_group)
            if profile.randomize_keys:
                random.shuffle(creds)

            for cred in creds:
                if not circuit_breaker.is_available(cred.id, model_obj.provider_model_id)[0]:
                    continue

                api_key = decrypt_secret(cred.encrypted_api_key)
                proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
                cand_t0 = time.perf_counter()

                try:
                    is_native_jev = cls._is_native_jev_provider(provider, model_obj)
                    answers, usage = await cls._dispatch_decision(cred, provider, model_obj, request, proxy_url, profile.timeout_seconds, retry_count=profile.retry_count)

                    cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)

                    attempts_trace.append({
                        "attempt_number": len(attempts_trace) + 1,
                        "provider_name": provider.name,
                        "credential_name": cred.name,
                        "model_name": model_obj.display_name or model_obj.provider_model_id,
                        "status": "SUCCESS",
                        "http_status": 200,
                        "latency_ms": cand_latency,
                    })

                    total_latency = round((time.perf_counter() - t0) * 1000, 2)
                    in_tok = usage.get("input_tokens", 0) if isinstance(usage, dict) else getattr(usage, "input_tokens", 0)
                    out_tok = usage.get("output_tokens", 0) if isinstance(usage, dict) else getattr(usage, "output_tokens", 0)

                    if record_log:
                        await LogService.record_request_log(
                            db=db,
                            request_id=req_id,
                            requested_model=model_str,
                            mode="JEV",
                            resolved_provider_id=provider.id,
                            resolved_credential_id=cred.id,
                            upstream_model=model_obj.provider_model_id,
                            latency_ms=total_latency,
                            status_code=200,
                            status="SUCCESS",
                            input_tokens=in_tok,
                            output_tokens=out_tok,
                            router_key_id=router_key.id if router_key else None,
                            attempts=attempts_trace,
                            metadata_json={
                                "strategy": "profile_systemone",
                                "profile_id": profile.id,
                                "profile_name": profile.name,
                                "questions_count": len(request.questions),
                            },
                            prompt_content=json.dumps({"state": request.state, "questions": request.questions}, ensure_ascii=False),
                            response_content=json.dumps(answers, ensure_ascii=False),
                        )

                    return JevResponse(
                        id=f"dec_{uuid.uuid4().hex[:16]}",
                        model=model_str,
                        answers=answers,
                        usage=JevUsage(
                            input_tokens=in_tok,
                            output_tokens=out_tok,
                            total_tokens=in_tok + out_tok,
                        ),
                        latency_ms=total_latency,
                    )
                except Exception as e:
                    cand_latency = round((time.perf_counter() - cand_t0) * 1000, 2)
                    status_code = getattr(e, "status_code", 500)
                    cat = getattr(e, "category", None) or (
                        ErrorCategory.RATE_LIMIT if status_code == 429
                        else ErrorCategory.AUTH_ERROR if status_code in (401, 403)
                        else ErrorCategory.UPSTREAM_5XX
                    )
                    retry_after = getattr(e, "retry_after", None)

                    attempts_trace.append({
                        "attempt_number": len(attempts_trace) + 1,
                        "provider_name": provider.name,
                        "credential_name": cred.name,
                        "model_name": model_obj.display_name or model_obj.provider_model_id,
                        "status": "FAILED",
                        "http_status": status_code,
                        "error_message": str(e),
                        "latency_ms": cand_latency,
                    })
                    last_exception = e
                    if isinstance(e, RouterException) and (not e.category.is_fallback_eligible or
                            (profile.fallback_conditions is not None and e.category.value not in profile.fallback_conditions)):
                        break

        total_latency = round((time.perf_counter() - t0) * 1000, 2)
        if record_log:
            await LogService.record_request_log(
                db=db,
                request_id=req_id,
                requested_model=model_str,
                mode="JEV",
                latency_ms=total_latency,
                status_code=last_exception.status_code if isinstance(last_exception, RouterException) else 502,
                status="FAILED",
                error_category=last_exception.category.value if isinstance(last_exception, RouterException) else "UPSTREAM_5XX",
                error_message=str(last_exception) if last_exception else "All profile candidates failed",
                router_key_id=router_key.id if router_key else None,
                attempts=attempts_trace,
                metadata_json={"strategy": "profile_systemone", "profile_id": profile.id},
            )

        if isinstance(last_exception, RouterException):
            raise last_exception
        raise RouterException(
            f"Jev decision across profile '{slug}' failed. Last error: {last_exception}",
            ErrorCategory.UPSTREAM_5XX,
            status_code=502,
        )

    @classmethod
    async def _dispatch_decision(cls, cred, provider, model_obj, request, proxy_url, timeout, *, retry_count=0):
        from app.core.admission import admission
        from app.compression.tokenizer import estimate_tokens
        if not isinstance(retry_count, int) or not 0 <= retry_count <= 10:
            raise RouterException('retry_count must be between 0 and 10', ErrorCategory.INVALID_REQUEST)
        if not cls._is_native_jev_provider(provider, model_obj):
            return await cls._emulate_jev_via_adapter(provider=provider, api_key=decrypt_secret(cred.encrypted_api_key),
                model_obj=model_obj, request=request, proxy_url=proxy_url, timeout=timeout, credential=cred, retry_count=retry_count)
        prompt_tokens = estimate_tokens(json.dumps({'state': request.state, 'questions':request.questions}))
        if cred.tpm_limit is not None and not model_obj.max_output_tokens:
            raise RouterException('Native JEV needs a known output ceiling for finite TPM', ErrorCategory.RATE_LIMIT,
                status_code=429, retry_after=60, raw_error={'local_admission': True})
        for attempt in range(retry_count + 1):
            if not RoutingEngine._eligible(provider, model_obj, cred):
                raise RouterException('JEV credential unavailable', ErrorCategory.MODEL_NOT_FOUND, status_code=503)
            reservation = admission.reserve('credential', cred.id, rpm=cred.rpm_limit, tpm=cred.tpm_limit,
                concurrency=cred.max_concurrency, tokens=prompt_tokens + (model_obj.max_output_tokens or 0))
            try:
                answers, usage = await cls._call_native_jev_upstream(provider, decrypt_secret(cred.encrypted_api_key),
                    model_obj.provider_model_id, request, proxy_url, timeout)
                reservation.finish(usage.get('input_tokens', 0) + usage.get('output_tokens', 0))
                circuit_breaker.record_success(cred.id, model_obj.provider_model_id)
                return answers, usage
            except Exception as exc:
                error = exc if isinstance(exc, RouterException) else normalize_upstream_error(exception=exc)
                circuit_breaker.record_failure(cred.id, error.category, error.retry_after, error.message, model_obj.provider_model_id)
                if attempt >= retry_count or not error.category.is_retryable or error.category == ErrorCategory.RATE_LIMIT:
                    raise error
            finally:
                reservation.finish()

    @classmethod
    def _validate_answers(cls, answers, questions):
        import math
        if not isinstance(answers, dict) or set(answers) != set(questions):
            raise RouterException('Invalid JEV answer object', ErrorCategory.UPSTREAM_5XX)
        for key, question in cls._normalize_questions_for_upstream(questions).items():
            answer = answers[key]
            if not isinstance(answer, dict) or answer.get('type', question.get('type')) != question.get('type'):
                raise RouterException('Invalid JEV answer shape', ErrorCategory.UPSTREAM_5XX)
            kind = question.get('type')
            if kind == 'choice' and answer.get('choice', answer.get('decision')) not in question.get('criteria', {}):
                raise RouterException('Invalid JEV choice', ErrorCategory.UPSTREAM_5XX)
            if kind == 'noul':
                if any(field in answer and not isinstance(answer[field], bool) for field in ('answer', 'judgment')):
                    raise RouterException('Invalid JEV boolean', ErrorCategory.UPSTREAM_5XX)
                if not any(field in answer for field in ('answer', 'judgment', 'noul')):
                    raise RouterException('Missing JEV boolean', ErrorCategory.UPSTREAM_5XX)
            if kind == 'score':
                score = answer.get('score')
                levels = question.get('criteria', [])
                valid_score = (not isinstance(score, bool) and isinstance(score, (int, float))
                               and math.isfinite(score) and 1 <= score <= len(levels)) or (isinstance(score, str) and score in levels)
                if not valid_score:
                    raise RouterException('Invalid JEV score', ErrorCategory.UPSTREAM_5XX)
            values = [answer[k] for k in ('probability','confidence','noul') if k in answer]
            probabilities = answer.get('probabilities', {})
            if not isinstance(probabilities, dict):
                raise RouterException('Invalid JEV probabilities', ErrorCategory.UPSTREAM_5XX)
            values.extend(probabilities.values())
            if any(isinstance(v, bool) or not isinstance(v, (int,float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise RouterException('Invalid JEV probability', ErrorCategory.UPSTREAM_5XX)
        return cls._normalize_answers(answers)

    @classmethod
    def _normalize_questions_for_upstream(cls, questions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalizes questions dictionary into standard System One typed schema:
        {"type": "choice"|"score"|"noul", "instructions": "...", "criteria": ...}
        """
        normalized = {}
        for q_id, q_val in questions.items():
            if not isinstance(q_val, dict):
                normalized[q_id] = q_val
                continue

            if "type" in q_val and q_val["type"] in ("choice", "score", "noul"):
                q_type = q_val["type"]
                instr = q_val.get("instructions") or q_val.get("description") or f"Evaluate {q_id}"
                crit = q_val.get("criteria") or q_val.get("rubric") or {}
                item = {"type": q_type, "instructions": instr}
                if q_type != "noul":
                    item["criteria"] = crit
                normalized[q_id] = item
                continue

            if "choice" in q_val and isinstance(q_val["choice"], dict):
                ch = q_val["choice"]
                normalized[q_id] = {
                    "type": "choice",
                    "instructions": ch.get("instructions") or ch.get("description") or f"Select choice for {q_id}",
                    "criteria": ch.get("criteria", {}),
                }
            elif "score" in q_val and isinstance(q_val["score"], dict):
                sc = q_val["score"]
                normalized[q_id] = {
                    "type": "score",
                    "instructions": sc.get("instructions") or sc.get("description") or f"Score {q_id}",
                    "criteria": sc.get("criteria") or sc.get("rubric") or [],
                }
            elif "noul" in q_val:
                nl = q_val["noul"]
                desc = nl.get("description") or nl.get("instructions") if isinstance(nl, dict) else str(nl)
                normalized[q_id] = {
                    "type": "noul",
                    "instructions": desc or f"Evaluate {q_id}",
                }
            else:
                normalized[q_id] = q_val
        return normalized

    @classmethod
    def _normalize_answers(cls, answers: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalizes answers from native or emulated upstreams so frontend and API clients
        always have uniform fields (probabilities, confidence, score, answer, judgment).
        """
        normalized = {}
        for q_id, ans in answers.items():
            if not isinstance(ans, dict):
                normalized[q_id] = ans
                continue
            item = dict(ans)
            ans_type = item.get("type")

            # 1. Normalize noul
            if ans_type == "noul" or "noul" in item:
                item["type"] = "noul"
                if "noul" in item:
                    try:
                        p = float(item["noul"])
                        item["probability"] = p
                        if "answer" not in item:
                            item["answer"] = p >= 0.5
                        if "judgment" not in item:
                            item["judgment"] = p >= 0.5
                    except (ValueError, TypeError):
                        pass

            # 2. Normalize score
            elif ans_type == "score" or "score" in item:
                item["type"] = "score"
                legend = item.get("legend")
                probs = item.get("probabilities")
                if legend and probs and isinstance(probs, dict):
                    remapped_probs = {}
                    for k, v in probs.items():
                        if isinstance(legend, list) and str(k).isdigit() and int(k) < len(legend):
                            remapped_probs[legend[int(k)]] = v
                        elif isinstance(legend, dict) and str(k) in legend:
                            remapped_probs[legend[str(k)]] = v
                        else:
                            remapped_probs[str(k)] = v
                    item["probabilities"] = remapped_probs

                    score_val = item.get("score")
                    if isinstance(score_val, (int, float)):
                        idx = int(round(score_val))
                        if isinstance(legend, list) and 0 <= idx < len(legend):
                            item["rubric_level"] = legend[idx]
                            item["level"] = legend[idx]
                        elif isinstance(legend, dict) and str(idx) in legend:
                            item["rubric_level"] = legend[str(idx)]
                            item["level"] = legend[str(idx)]

            # 3. Normalize choice
            elif ans_type == "choice" or "choice" in item or "decision" in item:
                item["type"] = "choice"
                if "decision" not in item and "choice" in item:
                    item["decision"] = item["choice"]
                elif "choice" not in item and "decision" in item:
                    item["choice"] = item["decision"]

            normalized[q_id] = item
        return normalized

    @classmethod
    def _is_native_jev_provider(cls, provider: Provider, model_obj: DiscoveredModel) -> bool:
        p_slug = (provider.slug or "").lower()
        p_url = (provider.base_url or "").lower()
        p_name = (provider.name or "").lower()
        m_id = (model_obj.provider_model_id or "").lower()
        m_slug = (model_obj.canonical_slug or "").lower()

        # Known System One / Jev native providers
        native_keywords = ("typesafe", "drex", "nace", "experientiallabs", "experiential", "systemone")
        if any(kw in p_slug or kw in p_url or kw in p_name for kw in native_keywords):
            return True

        # OpenRouter hosting Jev / System One models
        if ("openrouter" in p_slug or "openrouter.ai" in p_url) and ("typesafe/jev" in m_id or "jev-" in m_id or "drex" in m_id):
            return True

        # Model explicitly named drex or jev in a provider that supports systemone
        if "drex" in m_id or "drex" in m_slug:
            return True

        return False

    @classmethod
    async def _call_native_jev_upstream(
        cls,
        provider: Provider,
        api_key: str,
        model_id: str,
        request: JevRequest,
        proxy_url: Optional[str] = None,
        timeout: float = 60.0,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        client = await http_client_manager.get_client(proxy_url=proxy_url, timeout=timeout)
        base = provider.base_url.rstrip("/")

        if base.endswith("/v1") or base.endswith("/api/v1"):
            endpoint = f"{base}/systemone"
        else:
            endpoint = f"{base}/v1/systemone"

        auth_hdr = provider.auth_header or "Authorization"
        headers = {
            "Content-Type": "application/json",
        }
        if auth_hdr.lower() == "authorization":
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            headers[auth_hdr] = api_key

        if provider.extra_headers:
            headers.update(provider.extra_headers)

        payload = {
            "model": model_id,
            "state": request.state,
            "questions": cls._normalize_questions_for_upstream(request.questions),
        }

        resp = await client.post(endpoint, headers=headers, json=payload)
        if resp.status_code == 404 and not (base.endswith("/v1") or base.endswith("/api/v1")):
            alt_endpoint = f"{base}/systemone"
            alt_resp = await client.post(alt_endpoint, headers=headers, json=payload)
            if alt_resp.status_code == 200:
                resp = alt_resp
                endpoint = alt_endpoint

        if resp.status_code != 200:
            from email.utils import parsedate_to_datetime
            from datetime import datetime, timezone
            retry_after = None
            raw_retry = resp.headers.get('Retry-After')
            if raw_retry:
                try:
                    retry_after = float(raw_retry)
                except ValueError:
                    try:
                        retry_after = max(0.0, (parsedate_to_datetime(raw_retry) - datetime.now(timezone.utc)).total_seconds())
                    except (ValueError, TypeError):
                        pass
            raise normalize_upstream_error(resp.status_code, resp.text, retry_after=retry_after)
        try:
            data = resp.json()
        except ValueError as exc:
            raise RouterException('Invalid JEV JSON', ErrorCategory.UPSTREAM_5XX) from exc
        if not isinstance(data, dict) or data.get('error'):
            raise RouterException('Invalid JEV response', ErrorCategory.UPSTREAM_5XX)
        answers = cls._validate_answers(data.get('answers'), request.questions)
        raw_usage = data.get("usage", {})
        in_tok = raw_usage.get("input_tokens", raw_usage.get("prompt_tokens", 0)) if isinstance(raw_usage, dict) else 0
        out_tok = raw_usage.get("output_tokens", raw_usage.get("completion_tokens", 0)) if isinstance(raw_usage, dict) else 0
        usage = {"input_tokens": in_tok, "output_tokens": out_tok}
        return answers, usage

    @classmethod
    async def _emulate_jev_via_adapter(
        cls,
        provider: Provider,
        api_key: str,
        model_obj: DiscoveredModel,
        request: JevRequest,
        proxy_url: Optional[str] = None,
        timeout: float = 60.0,
        credential: Optional[ProviderCredential] = None,
        retry_count: int = 0,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Emulates Jev System One decisions on top of any standard LLM (OpenAI, Gemini, Anthropic, Ollama, Groq).
        """
        adapter = get_adapter(provider.adapter_type)

        system_instructions = (
            "You are Jev, a high-speed System One decision engine.\n"
            "You do NOT produce conversational prose, greetings, explanations, or markdown codeblocks.\n"
            "Evaluate the provided State against the defined Questions and output strict, valid JSON with a single top-level key: 'answers'.\n\n"
            "Primitives specification:\n"
            "1. 'choice':\n"
            "   Select exactly one choice key from criteria.\n"
            "   Format: {\"type\": \"choice\", \"choice\": \"<key>\", \"probabilities\": {\"<key1>\": <float 0..1>, ...}, \"confidence\": <float 0..1>}\n"
            "   Note: sum of probabilities across options must equal 1.0.\n"
            "2. 'score':\n"
            "   Rate on the ordered scale criteria (ordered list of levels).\n"
            "   Format: {\"type\": \"score\", \"score\": <integer 1..N or level string>, \"probabilities\": {\"<level>\": <float 0..1>}, \"confidence\": <float 0..1>}\n"
            "3. 'noul':\n"
            "   Binary True/False judgment based on instructions.\n"
            "   Format: {\"type\": \"noul\", \"answer\": true/false, \"probability\": <float 0..1>}\n\n"
            "Output schema:\n"
            "{\n"
            "  \"answers\": {\n"
            "    \"<question_key>\": { ... }\n"
            "  }\n"
            "}"
        )

        user_content = json.dumps({
            "state": request.state,
            "questions": request.questions,
        }, ensure_ascii=False)

        chat_req = ChatCompletionRequest(
            model=model_obj.provider_model_id,
            messages=[
                ChatMessage(role="system", content=system_instructions),
                ChatMessage(role="user", content=user_content),
            ],
            temperature=0.0,
            stream=False,
            response_format={"type": "json_object"} if getattr(model_obj, "capabilities", {}).get("structured_output") else None,
        )

        dispatch_kwargs = dict(
            base_url=provider.base_url, api_key=api_key, model_id=model_obj.provider_model_id,
            request=chat_req, extra_headers=provider.extra_headers, configuration=provider.adapter_configuration,
            proxy_url=proxy_url, timeout=timeout)
        if credential is not None:
            resp = await RoutingEngine._dispatch_chat(adapter, credential, provider, model_obj,
                retry_count=retry_count, **dispatch_kwargs)
        else:
            resp = await adapter.chat_completions(**dispatch_kwargs)

        content = ""
        if resp.choices and resp.choices[0].message:
            content = resp.choices[0].message.content or ""

        # Parse JSON output
        answers = {}
        try:
            # Clean markdown codeblocks if model included them
            clean_str = content.strip()
            if clean_str.startswith("```"):
                lines = clean_str.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_str = "\n".join(lines).strip()

            parsed = json.loads(clean_str)
            if not isinstance(parsed, dict) or parsed.get('error'):
                raise ValueError('Invalid JEV response object')
            answers = cls._validate_answers(parsed.get('answers'), request.questions)
        except (ValueError, TypeError) as exc:
            raise RouterException('Invalid JEV decision JSON', ErrorCategory.UPSTREAM_5XX) from exc

        usage_dict = {
            "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
        }
        return cls._normalize_answers(answers), usage_dict
