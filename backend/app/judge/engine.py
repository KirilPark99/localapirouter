import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.circuit_breaker import circuit_breaker
from app.core.crypto import decrypt_secret
from app.core.database import AsyncSessionLocal, _safe_close_session
from app.core.errors import RouterException, ErrorCategory
from app.adapters.factory import get_adapter
from app.models.entities import (
    JudgeProfile,
    JudgeCandidate,
    Provider,
    ProviderCredential,
    DiscoveredModel,
    RoutingProfile,
    RouterApiKey,
)
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    UsageInfo,
)
from app.schemas.jev import JevRequest
from app.schemas.entities import JudgeTestResponse
from app.services.proxy_service import ProxyService
from app.services.log_service import LogService
from app.services.judge_service import JudgeService
from app.routing.engine import RoutingEngine
from app.jev.engine import JevEngine

logger = logging.getLogger(__name__)


async def _safe_record_judge_log(**kwargs):
    passed_db = kwargs.get("db")
    try:
        if passed_db is not None:
            await LogService.record_request_log(**kwargs)
            return
    except Exception as e:
        logger.warning(f"Failed to record judge log using active session: {e}")

    try:
        async with AsyncSessionLocal() as fresh_db:
            kwargs["db"] = fresh_db
            await LogService.record_request_log(**kwargs)
    except Exception as e:
        logger.error(f"Failed to record judge log in fallback session: {e}")


class JudgeEngine:
    """
    Execution engine for Judge / Classifier Routing mode.
    Evaluates prompt complexity and task requirements via a configured Judge Model
    (standard LLM or JEV decision model) and dispatches to the winning Candidate.
    """

    @classmethod
    def _check_permissions(cls, router_key: RouterApiKey, slug: str):
        permissions = getattr(router_key, "permissions", [])
        if "judge" not in permissions and "routes" not in permissions:
            raise RouterException(
                "This API key lacks permission to access judge routing profiles",
                ErrorCategory.AUTH_ERROR,
                status_code=403,
            )
        allowed_judges = getattr(router_key, "allowed_judges", ["*"]) or ["*"]
        if "*" not in allowed_judges and slug not in allowed_judges:
            raise RouterException(
                f"Judge profile '{slug}' is not in allowed judges for this API key",
                ErrorCategory.AUTH_ERROR,
                status_code=403,
            )

    @classmethod
    async def _load_profile(cls, db: AsyncSession, slug: str) -> JudgeProfile:
        profile = await JudgeService.get_profile_by_slug(db, slug)
        if not profile:
            raise RouterException(
                f"Judge profile '{slug}' not found",
                ErrorCategory.MODEL_NOT_FOUND,
                status_code=404,
            )
        if not profile.enabled:
            raise RouterException(
                f"Judge profile '{slug}' is disabled",
                ErrorCategory.MODEL_NOT_FOUND,
                status_code=400,
            )
        return profile

    @classmethod
    def _extract_prompt_text(cls, messages: List[ChatMessage]) -> str:
        parts = []
        for m in messages:
            content = m.content
            if isinstance(content, str) and content.strip():
                parts.append(f"{m.role}: {content.strip()}")
            elif isinstance(content, list):
                # Multimodal or array content
                text_sub = " ".join(
                    item.get("text", "") for item in content if isinstance(item, dict) and "text" in item
                )
                if text_sub.strip():
                    parts.append(f"{m.role}: {text_sub.strip()}")
        return "\n\n".join(parts) if parts else "No prompt content provided."

    @classmethod
    def _format_candidates_prompt(cls, candidates: List[JudgeCandidate]) -> str:
        lines = []
        for idx, c in enumerate(candidates):
            target = (
                f"Routing Profile 'route/{c.target_profile.slug}'"
                if c.candidate_type == "profile" and c.target_profile
                else (c.model.display_name or c.model.provider_model_id if c.model else c.label)
            )
            tasks = ", ".join(c.task_types) if c.task_types else "any / general"
            desc = f" | Description: {c.description}" if c.description else ""
            lines.append(
                f"[Candidate Index {idx}] Label: \"{c.label}\" (Target: {target})\n"
                f"  - Suitable Complexity: {c.complexity_level}\n"
                f"  - Suitable Task Types: {tasks}{desc}"
            )
        return "\n\n".join(lines)

    @classmethod
    async def evaluate_judge(
        cls,
        db: AsyncSession,
        profile: JudgeProfile,
        prompt_text: str,
        active_candidates: List[JudgeCandidate],
        req_id: str,
    ) -> Tuple[int, Dict[str, Any], float, str, Optional[str]]:
        """
        Runs judge model to choose best candidate.
        Returns: (winning_idx, decision_metadata, judge_latency_ms, judge_status, error_msg)
        """
        t0 = time.perf_counter()

        if len(active_candidates) <= 1:
            latency = round((time.perf_counter() - t0) * 1000, 2)
            meta = {
                "reasoning": "Single active candidate configured; judge deliberation bypassed.",
                "estimated_complexity": "auto",
                "detected_task_type": "auto",
                "judge_model": "bypassed",
                "selected_candidate_index": 0,
            }
            return 0, meta, latency, "BYPASSED", None

        # Determine judge model name for trace
        judge_model_name = "unknown"
        if profile.judge_type == "profile" and profile.judge_routing_profile:
            judge_model_name = f"route/{profile.judge_routing_profile.slug}"
        elif profile.judge_model:
            judge_model_name = profile.judge_model.display_name or profile.judge_model.provider_model_id

        # Default fallback candidate index
        fallback_idx = 0
        if profile.fallback_candidate_id is not None:
            for idx, c in enumerate(active_candidates):
                if c.id == profile.fallback_candidate_id:
                    fallback_idx = idx
                    break

        try:
            # 1. JEV Model Evaluation
            is_jev = False
            if profile.judge_type == "model" and profile.judge_model:
                if getattr(profile.judge_model, "model_type", "openai") == "jev":
                    is_jev = True

            if is_jev:
                criteria_map = {}
                for idx, c in enumerate(active_candidates):
                    crit_desc = f"Label: {c.label}, Complexity: {c.complexity_level}, Tasks: {', '.join(c.task_types)}."
                    if c.description:
                        crit_desc += f" {c.description}"
                    criteria_map[f"candidate_{idx}"] = crit_desc

                jev_questions = {
                    "candidate_selection": {
                        "type": "choice",
                        "instructions": f"Analyze query complexity and task requirements ({profile.strategy}). Select the single best matching candidate model index.",
                        "criteria": criteria_map,
                    }
                }
                jev_req = JevRequest(
                    model=profile.judge_model.canonical_slug or profile.judge_model.provider_model_id,  # type: ignore
                    state=prompt_text,
                    questions=jev_questions,
                )
                jev_res = await JevEngine.execute_decision(
                    db=db,
                    request=jev_req,
                    request_id=f"{req_id}_judge",
                    record_log=False,
                )
                choice_ans = jev_res.answers.get("candidate_selection", {})
                choice_key = choice_ans.get("choice") or choice_ans.get("decision") or "candidate_0"
                cand_idx = fallback_idx
                if choice_key.startswith("candidate_"):
                    try:
                        cand_idx = int(choice_key.replace("candidate_", ""))
                    except Exception:
                        pass
                if cand_idx < 0 or cand_idx >= len(active_candidates):
                    cand_idx = fallback_idx

                lat = round((time.perf_counter() - t0) * 1000, 2)
                meta = {
                    "selected_candidate_index": cand_idx,
                    "estimated_complexity": active_candidates[cand_idx].complexity_level,
                    "detected_task_type": active_candidates[cand_idx].task_types[0] if active_candidates[cand_idx].task_types else "general",
                    "reasoning": f"JEV model selected {choice_key} with probabilities: {choice_ans.get('probabilities', {})}",
                    "judge_model": judge_model_name,
                }
                return cand_idx, meta, lat, "SUCCESS", None

            # 2. Standard LLM Evaluation (or Routing Profile as Judge)
            candidates_formatted = cls._format_candidates_prompt(active_candidates)
            system_msg = (
                "You are an expert AI Routing Judge.\n"
                "Your objective is to evaluate the user's prompt, estimate its complexity level, identify its task type, "
                "and select the single best candidate model from the list below to handle the request.\n\n"
                f"Candidate Options:\n{candidates_formatted}\n\n"
                f"Strategy: {profile.strategy}\n"
            )
            if profile.system_prompt and profile.system_prompt.strip():
                system_msg += f"\nCustom Judge Guidelines:\n{profile.system_prompt.strip()}\n"

            system_msg += (
                "\nRespond STRICTLY with a valid JSON object without any Markdown formatting or code fences:\n"
                "{\n"
                '  "selected_candidate_index": <int 0..' + str(len(active_candidates) - 1) + ">,\n"
                '  "estimated_complexity": "low" | "medium" | "high",\n'
                '  "detected_task_type": "<e.g. code, math, reasoning, chat, creative, etc.>",\n'
                '  "reasoning": "<concise rationale for why this candidate was chosen>"\n'
                "}\n"
            )

            user_msg = f"User Request to evaluate:\n---\n{prompt_text[:4000]}\n---\nSelect candidate index:"

            judge_req = ChatCompletionRequest(
                model=judge_model_name,
                messages=[
                    ChatMessage(role="system", content=system_msg),
                    ChatMessage(role="user", content=user_msg),
                ],
                temperature=profile.judge_temperature if profile.judge_temperature is not None else 0.1,
                stream=False,
            )

            raw_response_content = ""
            if profile.judge_type == "profile":
                resp = await RoutingEngine.route_chat_completions(
                    db=db,
                    request=judge_req,
                    router_key=None,
                    request_id=f"{req_id}_judge",
                    record_log=False,
                )
                raw_response_content = resp.choices[0].message.content if resp.choices else ""
            else:
                provider = profile.judge_provider
                model_obj = profile.judge_model
                if not provider or not model_obj:
                    raise RouterException("Judge provider or model not configured", ErrorCategory.UPSTREAM_5XX)

                adapter = get_adapter(provider.adapter_type)
                cred = profile.judge_credential
                if not cred or not cred.enabled:
                    # Look up active credential for provider
                    q = select(ProviderCredential).where(
                        ProviderCredential.provider_id == provider.id,
                        ProviderCredential.enabled == True,
                    )
                    if profile.judge_credential_group:
                        q = q.where(ProviderCredential.group_name == profile.judge_credential_group)
                    q = q.order_by(ProviderCredential.priority.asc(), ProviderCredential.weight.desc())
                    c_res = await db.execute(q)
                    cred = c_res.scalars().first()

                if not cred:
                    raise RouterException("No active credential available for judge model", ErrorCategory.UPSTREAM_5XX)

                api_key = decrypt_secret(cred.encrypted_api_key)
                proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
                resp = await adapter.chat_completions(
                    base_url=provider.base_url,
                    api_key=api_key,
                    model_id=model_obj.provider_model_id,
                    request=judge_req,
                    extra_headers=provider.extra_headers,
                    configuration={**provider.adapter_configuration, "credential_metadata": getattr(cred, "metadata_json", {})},
                    proxy_url=proxy_url,
                    timeout=profile.timeout_seconds or 30.0,
                )
                raw_response_content = resp.choices[0].message.content if resp.choices else ""

            # Parse JSON
            cleaned_json = raw_response_content.strip()
            # Strip markdown fences if present
            if cleaned_json.startswith("```"):
                cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
                cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

            data = json.loads(cleaned_json)
            cand_idx = int(data.get("selected_candidate_index", fallback_idx))
            if cand_idx < 0 or cand_idx >= len(active_candidates):
                logger.warning(f"Judge returned invalid candidate index {cand_idx}; using fallback {fallback_idx}")
                cand_idx = fallback_idx

            lat = round((time.perf_counter() - t0) * 1000, 2)
            meta = {
                "selected_candidate_index": cand_idx,
                "estimated_complexity": data.get("estimated_complexity", "auto"),
                "detected_task_type": data.get("detected_task_type", "general"),
                "reasoning": data.get("reasoning", "Selected by judge evaluation."),
                "judge_model": judge_model_name,
            }
            return cand_idx, meta, lat, "SUCCESS", None

        except Exception as e:
            lat = round((time.perf_counter() - t0) * 1000, 2)
            err_str = str(e)
            logger.warning(f"Judge evaluation failed: {err_str}; falling back to candidate #{fallback_idx}")
            meta = {
                "selected_candidate_index": fallback_idx,
                "estimated_complexity": "fallback",
                "detected_task_type": "fallback",
                "reasoning": f"Judge evaluation encountered an error ({err_str}). Routed to fallback candidate.",
                "judge_model": judge_model_name,
            }
            return fallback_idx, meta, lat, "FALLBACK", err_str

    @classmethod
    async def execute_judge(
        cls,
        db: AsyncSession,
        request: ChatCompletionRequest,
        router_key: Optional[RouterApiKey] = None,
        request_id: Optional[str] = None,
    ) -> ChatCompletionResponse:
        """
        Executes a non-streaming chat completion through the Judge Routing Engine.
        """
        t0 = time.perf_counter()
        req_id = request_id or f"req_{uuid.uuid4().hex[:16]}"
        slug = request.model.removeprefix("judge/").removeprefix("smart/").strip()

        if router_key:
            cls._check_permissions(router_key, slug)

        profile = await cls._load_profile(db, slug)
        active_candidates = [c for c in profile.candidates if c.is_active]
        if not active_candidates:
            raise RouterException(
                f"Judge profile '{slug}' has no active candidates",
                ErrorCategory.INVALID_REQUEST,
                status_code=400,
            )

        # 1. Deliberation Phase
        prompt_text = cls._extract_prompt_text(request.messages)
        winning_idx, judge_meta, judge_lat, judge_status, judge_err = await cls.evaluate_judge(
            db=db,
            profile=profile,
            prompt_text=prompt_text,
            active_candidates=active_candidates,
            req_id=req_id,
        )
        winning_candidate = active_candidates[winning_idx]

        attempts_trace = [
            {
                "attempt_number": 1,
                "provider_name": "JudgeRouter",
                "credential_name": "JudgeEvaluator",
                "model_name": f"[Judge] {judge_meta.get('judge_model', 'unknown')}",
                "status": "SUCCESS" if judge_status in ("SUCCESS", "BYPASSED") else "FALLBACK",
                "latency_ms": judge_lat,
                "http_status": 200 if judge_status in ("SUCCESS", "BYPASSED") else 500,
                "error_message": judge_err,
                "error_category": "JUDGE_EVAL_ERROR" if judge_err else None,
            }
        ]

        # 2. Dispatch to winning candidate
        cand_t0 = time.perf_counter()
        cand_req = request.model_copy(deep=True)
        if winning_candidate.temperature is not None:
            cand_req.temperature = float(winning_candidate.temperature)
        if winning_candidate.thinking_effort:
            cand_req = RoutingEngine._apply_thinking_effort(cand_req, winning_candidate.thinking_effort)

        target_model_name = "unknown"
        resolved_prov_id = None
        resolved_cred_id = None
        upstream_model_id = None

        try:
            if winning_candidate.candidate_type == "profile" and winning_candidate.target_profile:
                target_model_name = f"route/{winning_candidate.target_profile.slug}"
                cand_req.model = target_model_name
                response = await RoutingEngine.route_chat_completions(
                    db=db,
                    request=cand_req,
                    router_key=router_key,
                    request_id=req_id,
                    record_log=False,
                )
                upstream_model_id = response.model
            else:
                model_obj = winning_candidate.model
                provider = winning_candidate.provider
                if not model_obj or not provider:
                    raise RouterException("Winning candidate model or provider not configured", ErrorCategory.UPSTREAM_5XX)

                target_model_name = model_obj.canonical_slug or model_obj.provider_model_id
                resolved_prov_id = provider.id
                upstream_model_id = model_obj.provider_model_id
                cand_req.model = target_model_name

                # Check if specific credential assigned
                if winning_candidate.credential_id:
                    cand_req = RoutingEngine._apply_model_defaults(cand_req, model_obj, winning_candidate.thinking_effort)
                    adapter = get_adapter(provider.adapter_type)
                    cred = winning_candidate.credential
                    if not cred or not cred.enabled:
                        raise RouterException("Assigned credential for winning candidate is disabled", ErrorCategory.UPSTREAM_5XX)
                    resolved_cred_id = cred.id
                    api_key = decrypt_secret(cred.encrypted_api_key)
                    proxy_url = ProxyService.build_proxy_url(cred.proxy) if cred.proxy else None
                    response = await adapter.chat_completions(
                        base_url=provider.base_url,
                        api_key=api_key,
                        model_id=model_obj.provider_model_id,
                        request=cand_req,
                        extra_headers=provider.extra_headers,
                        configuration={**provider.adapter_configuration, "credential_metadata": getattr(cred, "metadata_json", {})},
                        proxy_url=proxy_url,
                        timeout=profile.timeout_seconds or 60.0,
                    )
                else:
                    response = await RoutingEngine.route_chat_completions(
                        db=db,
                        request=cand_req,
                        router_key=router_key,
                        request_id=req_id,
                        record_log=False,
                    )

            cand_lat = round((time.perf_counter() - cand_t0) * 1000, 2)
            attempts_trace.append({
                "attempt_number": 2,
                "provider_name": getattr(winning_candidate.provider, "name", "TargetProfile"),
                "credential_name": getattr(winning_candidate.credential, "name", "Auto"),
                "model_name": f"[{winning_candidate.label}] {target_model_name}",
                "status": "SUCCESS",
                "latency_ms": cand_lat,
                "http_status": 200,
            })

            total_lat = round((time.perf_counter() - t0) * 1000, 2)
            p_toks = response.usage.prompt_tokens if response.usage else 0
            c_toks = response.usage.completion_tokens if response.usage else 0

            # Override response model to indicate judge routing path
            response.model = f"judge/{profile.slug}"

            metadata = {
                "judge_profile": profile.slug,
                "judge_model": judge_meta.get("judge_model"),
                "judge_status": judge_status,
                "judge_latency_ms": judge_lat,
                "judge_reasoning": judge_meta.get("reasoning"),
                "estimated_complexity": judge_meta.get("estimated_complexity"),
                "detected_task_type": judge_meta.get("detected_task_type"),
                "selected_candidate_id": winning_candidate.id,
                "selected_candidate_label": winning_candidate.label,
                "target_model": target_model_name,
            }

            await _safe_record_judge_log(
                db=db,
                request_id=req_id,
                requested_model=f"judge/{profile.slug}",
                mode="JUDGE",
                status="SUCCESS" if judge_status in ("SUCCESS", "BYPASSED") else "JUDGE_FALLBACK_SUCCESS",
                status_code=200,
                latency_ms=total_lat,
                router_key_id=router_key.id if router_key else None,
                resolved_provider_id=resolved_prov_id,
                resolved_credential_id=resolved_cred_id,
                upstream_model=upstream_model_id,
                input_tokens=p_toks,
                output_tokens=c_toks,
                metadata_json=metadata,
                attempts=attempts_trace,
            )

            return response

        except Exception as e:
            cand_lat = round((time.perf_counter() - cand_t0) * 1000, 2)
            total_lat = round((time.perf_counter() - t0) * 1000, 2)
            err_msg = str(e)
            re = e if isinstance(e, RouterException) else RouterException(err_msg, ErrorCategory.UPSTREAM_5XX)

            attempts_trace.append({
                "attempt_number": 2,
                "provider_name": getattr(winning_candidate.provider, "name", "Target"),
                "credential_name": getattr(winning_candidate.credential, "name", "Auto"),
                "model_name": f"[{winning_candidate.label}] {target_model_name}",
                "status": "FAILED",
                "latency_ms": cand_lat,
                "http_status": re.status_code,
                "error_message": re.message,
                "error_category": re.category.value if hasattr(re.category, "value") else str(re.category),
            })

            metadata = {
                "judge_profile": profile.slug,
                "judge_model": judge_meta.get("judge_model"),
                "judge_status": judge_status,
                "judge_reasoning": judge_meta.get("reasoning"),
                "selected_candidate_id": winning_candidate.id,
                "selected_candidate_label": winning_candidate.label,
                "target_model": target_model_name,
            }

            await _safe_record_judge_log(
                db=db,
                request_id=req_id,
                requested_model=f"judge/{profile.slug}",
                mode="JUDGE",
                status="FAILED",
                status_code=re.status_code,
                latency_ms=total_lat,
                router_key_id=router_key.id if router_key else None,
                resolved_provider_id=resolved_prov_id,
                resolved_credential_id=resolved_cred_id,
                upstream_model=upstream_model_id,
                error_category=re.category.value if hasattr(re.category, "value") else "UPSTREAM_ERROR",
                error_message=re.message,
                metadata_json=metadata,
                attempts=attempts_trace,
            )
            re.request_id = req_id
            raise re

    @classmethod
    async def execute_judge_stream(
        cls,
        db: Optional[AsyncSession],
        request: ChatCompletionRequest,
        router_key: Optional[RouterApiKey] = None,
        request_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Executes a streaming chat completion through the Judge Routing Engine.
        """
        t0 = time.perf_counter()
        req_id = request_id or f"req_{uuid.uuid4().hex[:16]}"
        slug = request.model.removeprefix("judge/").removeprefix("smart/").strip()

        if router_key:
            cls._check_permissions(router_key, slug)

        async def _stream_runner(session: AsyncSession):
            profile = await cls._load_profile(session, slug)
            active_candidates = [c for c in profile.candidates if c.is_active]
            if not active_candidates:
                raise RouterException(
                    f"Judge profile '{slug}' has no active candidates",
                    ErrorCategory.INVALID_REQUEST,
                    status_code=400,
                )

            prompt_text = cls._extract_prompt_text(request.messages)
            winning_idx, judge_meta, judge_lat, judge_status, judge_err = await cls.evaluate_judge(
                db=session,
                profile=profile,
                prompt_text=prompt_text,
                active_candidates=active_candidates,
                req_id=req_id,
            )
            winning_candidate = active_candidates[winning_idx]

            cand_req = request.model_copy(deep=True)
            if winning_candidate.temperature is not None:
                cand_req.temperature = float(winning_candidate.temperature)
            if winning_candidate.thinking_effort:
                cand_req = RoutingEngine._apply_thinking_effort(cand_req, winning_candidate.thinking_effort)

            target_model_name = "unknown"
            if winning_candidate.candidate_type == "profile" and winning_candidate.target_profile:
                target_model_name = f"route/{winning_candidate.target_profile.slug}"
                cand_req.model = target_model_name
            else:
                model_obj = winning_candidate.model
                target_model_name = model_obj.canonical_slug if model_obj else winning_candidate.label
                cand_req.model = target_model_name

            cand_t0 = time.perf_counter()
            approx_input_tokens = max(1, len(prompt_text) // 3)
            approx_output_tokens = 0
            has_seen_usage = False

            try:
                stream_source = RoutingEngine.route_stream_chat(
                    db=session,
                    request=cand_req,
                    router_key=router_key,
                    request_id=req_id,
                    record_log=False,
                )
                async for chunk in stream_source:
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
                    yield chunk

                total_lat = round((time.perf_counter() - t0) * 1000, 2)
                metadata = {
                    "stream": True,
                    "judge_profile": profile.slug,
                    "judge_model": judge_meta.get("judge_model"),
                    "judge_status": judge_status,
                    "judge_latency_ms": judge_lat,
                    "judge_reasoning": judge_meta.get("reasoning"),
                    "estimated_complexity": judge_meta.get("estimated_complexity"),
                    "detected_task_type": judge_meta.get("detected_task_type"),
                    "selected_candidate_id": winning_candidate.id,
                    "selected_candidate_label": winning_candidate.label,
                    "target_model": target_model_name,
                }
                await _safe_record_judge_log(
                    db=session,
                    request_id=req_id,
                    requested_model=f"judge/{profile.slug}",
                    mode="JUDGE",
                    status="SUCCESS" if judge_status in ("SUCCESS", "BYPASSED") else "JUDGE_FALLBACK_SUCCESS",
                    status_code=200,
                    latency_ms=total_lat,
                    router_key_id=router_key.id if router_key else None,
                    resolved_provider_id=getattr(winning_candidate.provider, "id", None),
                    resolved_credential_id=getattr(winning_candidate.credential, "id", None),
                    upstream_model=target_model_name,
                    input_tokens=approx_input_tokens,
                    output_tokens=max(1, approx_output_tokens),
                    metadata_json=metadata,
                )
            except Exception as e:
                total_lat = round((time.perf_counter() - t0) * 1000, 2)
                re = e if isinstance(e, RouterException) else RouterException(str(e), ErrorCategory.UPSTREAM_5XX)
                await _safe_record_judge_log(
                    db=session,
                    request_id=req_id,
                    requested_model=f"judge/{profile.slug}",
                    mode="JUDGE",
                    status="FAILED",
                    status_code=re.status_code,
                    latency_ms=total_lat,
                    router_key_id=router_key.id if router_key else None,
                    error_category=re.category.value if hasattr(re.category, "value") else "STREAM_ERROR",
                    error_message=re.message,
                    metadata_json={"stream": True, "judge_profile": profile.slug},
                )
                yield f"data: {json.dumps(re.to_openai_dict(request_id=req_id))}\n\n"
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
    async def test_evaluation(
        cls, db: AsyncSession, profile_id: int, prompt: str
    ) -> JudgeTestResponse:
        """
        Tests the judge classifier on a sample prompt without invoking target candidate.
        """
        profile = await db.get(JudgeProfile, profile_id)
        if not profile:
            raise RouterException("Judge profile not found", ErrorCategory.MODEL_NOT_FOUND, status_code=404)

        # Reload with relationships
        full_prof = await JudgeService.get_profile_by_slug(db, profile.slug)
        if not full_prof:
            raise RouterException("Judge profile could not be loaded", ErrorCategory.MODEL_NOT_FOUND, status_code=404)

        active_candidates = [c for c in full_prof.candidates if c.is_active]
        if not active_candidates:
            raise RouterException("No active candidates in this profile", ErrorCategory.INVALID_REQUEST, status_code=400)

        winning_idx, judge_meta, judge_lat, judge_status, judge_err = await cls.evaluate_judge(
            db=db,
            profile=full_prof,
            prompt_text=prompt,
            active_candidates=active_candidates,
            req_id=f"test_{uuid.uuid4().hex[:12]}",
        )
        winning_cand = active_candidates[winning_idx]

        target_desc = (
            f"route/{winning_cand.target_profile.slug}"
            if winning_cand.candidate_type == "profile" and winning_cand.target_profile
            else (winning_cand.model.display_name or winning_cand.model.provider_model_id if winning_cand.model else winning_cand.label)
        )

        return JudgeTestResponse(
            selected_candidate_id=winning_cand.id,
            selected_candidate_label=winning_cand.label,
            selected_target=target_desc,
            strategy=full_prof.strategy,
            estimated_complexity=judge_meta.get("estimated_complexity", "auto"),
            detected_task_type=judge_meta.get("detected_task_type", "general"),
            judge_reasoning=judge_meta.get("reasoning", "Deliberation complete."),
            judge_model_name=judge_meta.get("judge_model", "Unknown"),
            latency_ms=judge_lat,
            status=judge_status,
            error=judge_err,
        )
