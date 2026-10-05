import uuid
import json
import time
import logging

logger = logging.getLogger(__name__)
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, AsyncSessionLocal, _safe_close_session
from app.api.deps import get_router_key_dep
from app.models.entities import RouterApiKey, DiscoveredModel, RoutingProfile, FusionProfile, JudgeProfile, Provider
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    ResponsesRequest,
    UsageInfo,
)
from app.schemas.entities import ModelListResponse, ModelCard
from app.schemas.jev import JevRequest, JevResponse
from app.routing.engine import RoutingEngine
from app.fusion.engine import FusionEngine
from app.judge.engine import JudgeEngine
from app.jev.engine import JevEngine
from app.core.errors import RouterException

router = APIRouter(prefix="/v1", tags=["OpenAI Compatible API"])

@router.get("/models", response_model=ModelListResponse)
async def list_models(
    db: AsyncSession = Depends(get_db),
    router_key: Optional[RouterApiKey] = Depends(get_router_key_dep),
):
    cards = []

    # 1. Discovered Models
    query = select(DiscoveredModel).where(
        DiscoveredModel.enabled == True,
        DiscoveredModel.available == True,
        DiscoveredModel.is_visible == True,
        DiscoveredModel.provider.has(Provider.enabled == True),
    )
    result = await db.execute(query)
    models = result.scalars().all()

    for m in models:
        # Check router_key permissions
        if router_key:
            if "direct" not in router_key.permissions:
                continue
            if "*" not in router_key.allowed_models and m.canonical_slug not in router_key.allowed_models and m.provider_model_id not in router_key.allowed_models:
                continue

        cards.append(
            ModelCard(
                id=m.canonical_slug,
                root=m.provider_model_id,
                context_length=m.context_length,
                max_tokens=m.max_output_tokens,
                reasoning_effort=getattr(m, "reasoning_effort", None),
                temperature=getattr(m, "temperature", None),
                model_type=getattr(m, "model_type", "openai"),
            )
        )

    # 2. Routing Profiles
    if not router_key or "routes" in router_key.permissions:
        r_query = select(RoutingProfile).where(RoutingProfile.enabled == True)
        r_res = await db.execute(r_query)
        for r in r_res.scalars().all():
            if router_key and "*" not in router_key.allowed_routes and r.slug not in router_key.allowed_routes:
                continue
            cards.append(ModelCard(id=f"route/{r.slug}", root=f"route/{r.slug}"))

    # 3. Fusion Profiles
    if not router_key or "fusion" in router_key.permissions:
        f_query = select(FusionProfile).where(FusionProfile.enabled == True)
        f_res = await db.execute(f_query)
        for f in f_res.scalars().all():
            if router_key and "*" not in router_key.allowed_fusions and f.slug not in router_key.allowed_fusions:
                continue
            cards.append(ModelCard(id=f"fusion/{f.slug}", root=f"fusion/{f.slug}"))

    # 4. Judge Profiles
    if not router_key or "judge" in router_key.permissions or "routes" in router_key.permissions:
        j_query = select(JudgeProfile).where(JudgeProfile.enabled == True)
        j_res = await db.execute(j_query)
        for j in j_res.scalars().all():
            allowed_j = getattr(router_key, "allowed_judges", ["*"]) or ["*"]
            if router_key and "*" not in allowed_j and j.slug not in allowed_j:
                continue
            cards.append(ModelCard(id=f"judge/{j.slug}", root=f"judge/{j.slug}"))

    # Deduplicate cards by id
    seen = set()
    unique_cards = []
    for c in cards:
        if c.id not in seen:
            seen.add(c.id)
            unique_cards.append(c)

    return ModelListResponse(data=unique_cards)

@router.get("/models/{model_id:path}", response_model=ModelCard)
async def retrieve_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    router_key: Optional[RouterApiKey] = Depends(get_router_key_dep),
):
    m_id = model_id.strip()

    # 1. Routing profile
    if m_id.startswith("route/"):
        slug = m_id.removeprefix("route/")
        if router_key:
            if "routes" not in router_key.permissions:
                return JSONResponse(status_code=403, content={"error": {"message": "Forbidden", "type": "auth_error"}})
            if "*" not in router_key.allowed_routes and slug not in router_key.allowed_routes:
                return JSONResponse(status_code=403, content={"error": {"message": "Forbidden", "type": "auth_error"}})
        r_res = await db.execute(select(RoutingProfile).where(RoutingProfile.slug == slug, RoutingProfile.enabled == True))
        profile = r_res.scalar_one_or_none()
        if profile:
            return ModelCard(id=f"route/{profile.slug}", root=f"route/{profile.slug}")

    # 2. Fusion profile
    if m_id.startswith("fusion/"):
        slug = m_id.removeprefix("fusion/")
        if router_key:
            if "fusion" not in router_key.permissions:
                return JSONResponse(status_code=403, content={"error": {"message": "Forbidden", "type": "auth_error"}})
            if "*" not in router_key.allowed_fusions and slug not in router_key.allowed_fusions:
                return JSONResponse(status_code=403, content={"error": {"message": "Forbidden", "type": "auth_error"}})
        f_res = await db.execute(select(FusionProfile).where(FusionProfile.slug == slug, FusionProfile.enabled == True))
        profile = f_res.scalar_one_or_none()
        if profile:
            return ModelCard(id=f"fusion/{profile.slug}", root=f"fusion/{profile.slug}")

    # 3. Judge profile
    if m_id.startswith("judge/") or m_id.startswith("smart/"):
        slug = m_id.removeprefix("judge/").removeprefix("smart/")
        if router_key:
            if "judge" not in router_key.permissions and "routes" not in router_key.permissions:
                return JSONResponse(status_code=403, content={"error": {"message": "Forbidden", "type": "auth_error"}})
            allowed_j = getattr(router_key, "allowed_judges", ["*"]) or ["*"]
            if "*" not in allowed_j and slug not in allowed_j:
                return JSONResponse(status_code=403, content={"error": {"message": "Forbidden", "type": "auth_error"}})
        j_res = await db.execute(select(JudgeProfile).where(JudgeProfile.slug == slug, JudgeProfile.enabled == True))
        profile = j_res.scalar_one_or_none()
        if profile:
            return ModelCard(id=f"judge/{profile.slug}", root=f"judge/{profile.slug}")

    # 3. Discovered Model (by canonical_slug or provider_model_id)
    query = select(DiscoveredModel).where(
        DiscoveredModel.enabled == True,
        DiscoveredModel.available == True,
        DiscoveredModel.is_visible == True,
        DiscoveredModel.provider.has(Provider.enabled == True),
        (DiscoveredModel.canonical_slug == m_id) | (DiscoveredModel.provider_model_id == m_id),
    )
    result = await db.execute(query)
    model_obj = result.scalars().first()

    if not model_obj and ":" in m_id:
        # Strip trailing tag if present (e.g. gemini-3.8-flash:latest)
        base_name = m_id.split(":", 1)[0]
        query2 = select(DiscoveredModel).where(
            DiscoveredModel.enabled == True,
            DiscoveredModel.available == True,
            DiscoveredModel.is_visible == True,
            DiscoveredModel.provider.has(Provider.enabled == True),
            (DiscoveredModel.canonical_slug == base_name) | (DiscoveredModel.provider_model_id == base_name),
        )
        result2 = await db.execute(query2)
        model_obj = result2.scalars().first()

    if model_obj:
        if router_key:
            if "direct" not in router_key.permissions:
                return JSONResponse(status_code=403, content={"error": {"message": "Forbidden", "type": "auth_error"}})
            if "*" not in router_key.allowed_models and model_obj.canonical_slug not in router_key.allowed_models and model_obj.provider_model_id not in router_key.allowed_models:
                return JSONResponse(status_code=403, content={"error": {"message": "Forbidden", "type": "auth_error"}})
        return ModelCard(
            id=model_obj.canonical_slug,
            root=model_obj.provider_model_id,
            context_length=model_obj.context_length,
            max_tokens=model_obj.max_output_tokens,
            reasoning_effort=getattr(model_obj, "reasoning_effort", None),
            temperature=getattr(model_obj, "temperature", None),
            model_type=getattr(model_obj, "model_type", "openai"),
        )

    # 4. Check if bare slug matches a route
    r_res = await db.execute(select(RoutingProfile).where(RoutingProfile.slug == m_id, RoutingProfile.enabled == True))
    profile = r_res.scalar_one_or_none()
    if profile:
        return ModelCard(id=f"route/{profile.slug}", root=f"route/{profile.slug}")

    # 5. Check if bare slug matches a fusion profile
    f_res = await db.execute(select(FusionProfile).where(FusionProfile.slug == m_id, FusionProfile.enabled == True))
    f_profile = f_res.scalar_one_or_none()
    if f_profile:
        return ModelCard(id=f"fusion/{f_profile.slug}", root=f"fusion/{f_profile.slug}")

    # 4. Bare Judge profile slug
    j_res = await db.execute(select(JudgeProfile).where(JudgeProfile.slug == m_id, JudgeProfile.enabled == True))
    j_profile = j_res.scalar_one_or_none()
    if j_profile:
        return ModelCard(id=f"judge/{j_profile.slug}", root=f"judge/{j_profile.slug}")

    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "message": f"Model '{model_id}' not found",
                "type": "invalid_request_error",
                "param": "model",
                "code": "model_not_found",
            }
        },
    )

async def _resolve_is_fusion(model_str: str, db: Optional[AsyncSession] = None) -> tuple[bool, str]:
    """Returns (is_fusion, normalized_model_str). Handles explicit 'fusion/slug' and bare slug."""
    if model_str.startswith("fusion/"):
        return True, model_str
    if model_str.startswith("route/") or model_str.startswith("judge/") or model_str.startswith("smart/"):
        return False, model_str

    from app.services.fusion_service import FusionService
    session = db if db is not None else AsyncSessionLocal()
    try:
        f_prof = await FusionService.get_profile_by_slug(session, model_str)
        if f_prof and f_prof.enabled:
            return True, f"fusion/{f_prof.slug}"
    except Exception:
        pass
    finally:
        if db is None:
            await _safe_close_session(session)
    return False, model_str

async def _resolve_is_judge(model_str: str, db: Optional[AsyncSession] = None) -> tuple[bool, str]:
    """Returns (is_judge, normalized_model_str). Handles explicit 'judge/slug', 'smart/slug', and bare slug."""
    if model_str.startswith("judge/"):
        return True, model_str
    if model_str.startswith("smart/"):
        return True, f"judge/{model_str.removeprefix('smart/')}"
    if model_str.startswith("fusion/") or model_str.startswith("route/"):
        return False, model_str

    from app.services.judge_service import JudgeService
    session = db if db is not None else AsyncSessionLocal()
    try:
        j_prof = await JudgeService.get_profile_by_slug(session, model_str)
        if j_prof and j_prof.enabled:
            return True, f"judge/{j_prof.slug}"
    except Exception:
        pass
    finally:
        if db is None:
            await _safe_close_session(session)
    return False, model_str

async def _prepare_chat_payload(payload, request, response, db, router_key, *, compress=True):
    """Shared request boundary for Chat, Responses, Messages and decisions."""
    import hashlib
    from app.security.registry import GuardrailRegistry, may_bypass_guardrails, parse_disabled_guardrails
    from app.compression.pipeline import CompressionPipelineService
    session = db if db is not None else AsyncSessionLocal()
    payload = payload.model_copy(deep=True)
    headers = dict(request.headers)
    try:
        fusion, payload.model = await _resolve_is_fusion(payload.model.strip(), session)
        judge = False
        if not fusion:
            judge, payload.model = await _resolve_is_judge(payload.model, session)
        if router_key is not None:
            RoutingEngine._check_permissions(router_key, payload.model)
        sec_cfg = await GuardrailRegistry.get_security_config(session)

        async def guard():
            result = await GuardrailRegistry.run_pre_call_hooks(
                payload=payload, headers=headers, model_id=payload.model, db=session, router_key=router_key,
            )
            if result.block:
                return JSONResponse(status_code=400, content={"error": {
                    "message": result.block_reason or "Request blocked by security guardrails",
                    "type": "guardrail_violation", "code": "prompt_injection_blocked",
                }})
            if result.warnings:
                response.headers["X-Guardrail-Warning"] = ",".join(sorted(set(result.warnings)))
            if result.modified_payload is not None:
                return result.modified_payload
            return payload

        checked = await guard()
        if isinstance(checked, Response):
            return checked
        payload = checked
        payload, context = await RoutingEngine.prepare_effective_request(session, payload, router_key)
        context = dict(context)
        context["is_fusion"], context["is_judge"] = fusion, judge
        context["skip_response_cache"] = context.get("skip_response_cache", False) or router_key is None
        safe_policy = {k: v for k, v in sec_cfg.items() if k.startswith(("injection_", "mask_", "custom_")) or k in (
            "credential_masking_enabled", "max_injection_scan_bytes",
        )}
        context["guardrail_overrides"] = (parse_disabled_guardrails(headers, getattr(payload, "metadata", None))
            if may_bypass_guardrails(router_key) else [])
        context["security_policy"] = hashlib.sha256(json.dumps(safe_policy, sort_keys=True, default=str).encode()).hexdigest()
        context["authorization"] = {k: getattr(router_key, k, None) for k in (
            "permissions", "allowed_models", "allowed_routes", "allowed_fusions", "allowed_judges",
        )} if router_key is not None else {"principal": "uncached"}
        if compress:
            global_cfg = await CompressionPipelineService.get_global_settings(session)
            try:
                payload.messages, summary = await CompressionPipelineService.optimize_messages(
                    db=session, messages=payload.messages, model_id=payload.model,
                    request_headers=headers, supports_vision=context.get("supports_vision"), provider_name=context.get("provider_name"),
                )
            except Exception as exc:
                if not global_cfg.fail_open:
                    raise HTTPException(status_code=503, detail="Required compression failed") from exc
                logger.warning("Optional compression failed: %s", type(exc).__name__)
                summary = {"compressed": False}
            if summary.get("compressed"):
                for field in ("before", "after", "saved"):
                    response.headers[f"X-Tokens-{field.title()}"] = str(summary[f"tokens_{field}"])
                response.headers["X-Compression-Savings"] = f"{summary['savings_percent']}%"
            # Transformations may expose patterns that were obfuscated on input.
            checked = await guard()
            if isinstance(checked, Response):
                return checked
            payload = checked
        return payload, context
    except (HTTPException, RouterException):
        raise
    except Exception as exc:
        logger.error("Request preprocessing failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Request safety preprocessing is unavailable") from exc
    finally:
        if db is None:
            await _safe_close_session(session)


async def _secure_outbound(content, request, db, router_key, model_id):
    from app.security.registry import GuardrailRegistry
    session = db if db is not None else AsyncSessionLocal()
    try:
        result = await GuardrailRegistry.run_post_call_hooks(
            content=content, headers=dict(request.headers), model_id=model_id, db=session, router_key=router_key,
        )
        if result.block:
            raise HTTPException(status_code=503, detail="Response blocked by safety policy")
        return result.modified_content if result.modified_content is not None else content
    except (HTTPException, RouterException):
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Response safety processing failed") from exc
    finally:
        if db is None:
            await _safe_close_session(session)


@router.post("/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    request: Request,
    response: Response,
    db: Optional[AsyncSession] = Depends(lambda: None),
    router_key: Optional[RouterApiKey] = Depends(get_router_key_dep),
):
    req_id = f"req_{uuid.uuid4().hex[:16]}"
    try:
        prepared = await _prepare_chat_payload(payload, request, response, db, router_key)
    except RouterException as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_openai_dict(request_id=req_id))
    if isinstance(prepared, Response):
        return prepared
    payload, cache_context = prepared
    model_str = payload.model
    is_fusion, is_judge = cache_context["is_fusion"], cache_context["is_judge"]
    from app.cache.response_cache import ResponseCacheService
    from app.modules.base import ChatStreamAccumulator
    req_headers = dict(request.headers)
    include_usage = bool(payload.stream_options and payload.stream_options.get("include_usage"))
    cache_signature = None
    cache_generation = ResponseCacheService.get_generation()
    is_cacheable = (not cache_context.get("skip_response_cache") and
                    ResponseCacheService.is_cacheable(payload, req_headers))
    if is_cacheable:
        cache_signature = ResponseCacheService.generate_signature(
            model=model_str, messages=payload.messages, temperature=payload.temperature,
            top_p=payload.top_p, tools=payload.tools, router_key_id=router_key.id if router_key is not None else None,
            request=payload, context=cache_context,
        )
        cache_db = db if db is not None else AsyncSessionLocal()
        try:
            cached = await ResponseCacheService.get_response(cache_db, cache_signature)
        finally:
            if db is None:
                await _safe_close_session(cache_db)
        if cached:
            # Old and new cache entries both cross the current outbound boundary.
            safe = await _secure_outbound(ChatCompletionResponse.model_validate(cached), request, db, router_key, model_str)
            response.headers["X-Cache"] = "HIT"
            response.headers["X-Cache-Latency"] = "local"
            if not payload.stream:
                return safe
            headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
            return StreamingResponse(
                ResponseCacheService.synthesize_sse_stream(safe.model_dump(), req_id, include_usage=include_usage),
                media_type="text/event-stream", headers=headers,
            )
        response.headers["X-Cache"] = "MISS"

    async def _save_to_cache(resp_obj):
        if not is_cacheable or not cache_signature or not resp_obj.choices or any(
            ch.finish_reason not in ("stop", "tool_calls", "function_call") for ch in resp_obj.choices
        ):
            return
        cache_db = db if db is not None else AsyncSessionLocal()
        try:
            usage = resp_obj.usage
            p_tok, c_tok = (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
            input_price, output_price = cache_context.get("input_price_per_1m"), cache_context.get("output_price_per_1m")
            cost = ((p_tok * input_price + c_tok * output_price) / 1_000_000
                    if input_price is not None and output_price is not None else 0.0)
            await ResponseCacheService.set_response(
                cache_db, signature=cache_signature, model=model_str, response_json=resp_obj.model_dump(),
                input_tokens=p_tok, output_tokens=c_tok, estimated_cost_usd=cost,
                expected_generation=cache_generation,
            )
        except Exception as exc:
            logger.warning("Optional response cache write failed: %s", type(exc).__name__)
        finally:
            if db is None:
                await _safe_close_session(cache_db)

    async def _process_outbound_response(resp_obj):
        safe = await _secure_outbound(resp_obj, request, db, router_key, model_str)
        await _save_to_cache(safe)
        return safe

    async def _wrap_streaming_with_cache(source):
        from app.security.registry import GuardrailRegistry
        stream_db = AsyncSessionLocal()
        accumulator = ChatStreamAccumulator() if is_cacheable and cache_signature else None
        try:
            safe_source = GuardrailRegistry.wrap_stream(
                source, model=model_str, headers=req_headers, db=stream_db,
                router_key=router_key, include_usage=include_usage,
            )
            async for chunk in safe_source:
                if accumulator is not None:
                    try:
                        accumulator.feed(chunk)
                    except (ValueError, TypeError):
                        # Large or malformed streams can still be delivered; never cached.
                        accumulator = None
                yield chunk
            if accumulator is not None:
                try:
                    assembled = accumulator.response(model_str, require_complete=True)
                except (ValueError, RouterException):
                    return
                await _process_outbound_response(assembled)
        except (RouterException, HTTPException) as exc:
            error = exc.to_openai_dict(req_id) if isinstance(exc, RouterException) else {"error": {
                "type": "guardrail_error", "message": "Response safety processing failed",
            }}
            yield f"data: {json.dumps(error)}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            await _safe_close_session(stream_db)

    def _make_streaming_response(source):
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return StreamingResponse(_wrap_streaming_with_cache(source), media_type="text/event-stream", headers=headers)

    try:
        if is_fusion:
            if payload.stream:
                stream_gen = FusionEngine.execute_fusion_stream(
                    db=None, request=payload, router_key=router_key, request_id=req_id
                )
                return _make_streaming_response(stream_gen)
            else:
                if db is not None:
                    res = await FusionEngine.execute_fusion(
                        db=db, request=payload, router_key=router_key, request_id=req_id
                    )
                    return await _process_outbound_response(res)
                else:
                    session = AsyncSessionLocal()
                    try:
                        res = await FusionEngine.execute_fusion(
                            db=session, request=payload, router_key=router_key, request_id=req_id
                        )
                        return await _process_outbound_response(res)
                    finally:
                        await _safe_close_session(session)
        elif is_judge:
            if payload.stream:
                stream_gen = JudgeEngine.execute_judge_stream(
                    db=None, request=payload, router_key=router_key, request_id=req_id
                )
                return _make_streaming_response(stream_gen)
            else:
                if db is not None:
                    res = await JudgeEngine.execute_judge(
                        db=db, request=payload, router_key=router_key, request_id=req_id
                    )
                    return await _process_outbound_response(res)
                else:
                    session = AsyncSessionLocal()
                    try:
                        res = await JudgeEngine.execute_judge(
                            db=session, request=payload, router_key=router_key, request_id=req_id
                        )
                        return await _process_outbound_response(res)
                    finally:
                        await _safe_close_session(session)
        else:
            # Check if caller passed a JEV decision structure or model is configured as JEV
            parsed_jev_payload = None
            if payload.messages and len(payload.messages) > 0:
                last_content = payload.messages[-1].content
                if isinstance(last_content, str) and ("\"questions\"" in last_content or "'questions'" in last_content):
                    try:
                        raw_data = json.loads(last_content)
                        if isinstance(raw_data, dict) and "questions" in raw_data:
                            parsed_jev_payload = JevRequest(
                                model=model_str,
                                state=raw_data.get("state", ""),
                                questions=raw_data["questions"],
                            )
                    except Exception:
                        pass

            is_jev_model = False
            if not model_str.startswith("route/"):
                session_to_use = db if db is not None else AsyncSessionLocal()
                try:
                    m_check = (await session_to_use.execute(
                        select(DiscoveredModel.model_type).where(
                            (DiscoveredModel.canonical_slug == model_str) | (DiscoveredModel.provider_model_id == model_str)
                        )
                    )).scalars().first()
                    if m_check == "jev":
                        is_jev_model = True
                except Exception:
                    pass
                finally:
                    if db is None:
                        await _safe_close_session(session_to_use)

            if parsed_jev_payload or is_jev_model:
                jev_req = parsed_jev_payload
                if not jev_req:
                    prompt_text = "\n".join(f"{m.role}: {m.content}" for m in payload.messages if m.content)
                    jev_req = JevRequest(
                        model=model_str,
                        state=prompt_text,
                        questions={
                            "evaluation": {
                                "choice": {
                                    "criteria": {
                                        "appropriate": "The prompt is valid and actionable",
                                        "inappropriate": "The prompt cannot be processed"
                                    }
                                }
                            }
                        }
                    )

                session = db if db is not None else AsyncSessionLocal()
                try:
                    jev_res = await JevEngine.execute_decision(
                        db=session,
                        request=jev_req,
                        router_key=router_key,
                        request_id=req_id,
                        record_log=True,
                    )
                finally:
                    if db is None:
                        await _safe_close_session(session)

                content_text = json.dumps(jev_res.answers, ensure_ascii=False, indent=2)
                return await _process_outbound_response(ChatCompletionResponse(
                    id=req_id,
                    object="chat.completion",
                    created=int(time.time()),
                    model=model_str,
                    choices=[
                        ChatCompletionChoice(
                            index=0,
                            message=ChatMessage(role="assistant", content=content_text),
                            finish_reason="stop",
                        )
                    ],
                    usage=UsageInfo(
                        prompt_tokens=jev_res.usage.input_tokens,
                        completion_tokens=jev_res.usage.output_tokens,
                        total_tokens=jev_res.usage.total_tokens,
                    ),
                ))

            if payload.stream:
                stream_gen = RoutingEngine.route_stream_chat(
                    db=None, request=payload, router_key=router_key, request_id=req_id
                )
                return _make_streaming_response(stream_gen)
            else:
                if db is not None:
                    res = await RoutingEngine.route_chat_completions(
                        db=db, request=payload, router_key=router_key, request_id=req_id
                    )
                    return await _process_outbound_response(res)
                else:
                    session = AsyncSessionLocal()
                    try:
                        res = await RoutingEngine.route_chat_completions(
                            db=session, request=payload, router_key=router_key, request_id=req_id
                        )
                        return await _process_outbound_response(res)
                    finally:
                        await _safe_close_session(session)
    except RouterException as re:
        return JSONResponse(
            status_code=re.status_code,
            content=re.to_openai_dict(request_id=req_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(e),
                    "type": "router_internal_error",
                    "code": "internal_error",
                    "request_id": req_id,
                }
            },
        )

@router.post("/systemone", response_model=JevResponse)
@router.post("/decisions", response_model=JevResponse)
async def systemone_decision(
    payload: JevRequest,
    request: Request,
    response: Response,
    db: Optional[AsyncSession] = Depends(lambda: None),
    router_key: Optional[RouterApiKey] = Depends(get_router_key_dep),
):
    req_id = f"dec_{uuid.uuid4().hex[:16]}"
    envelope = ChatCompletionRequest(model=payload.model, messages=[ChatMessage(
        role="user", content=json.dumps({"state": payload.state, "questions": payload.questions}, ensure_ascii=False),
    )])
    try:
        prepared = await _prepare_chat_payload(envelope, request, response, db, router_key)
    except RouterException as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_openai_dict(req_id))
    if isinstance(prepared, Response):
        return prepared
    envelope, _ = prepared
    try:
        decoded = json.loads(envelope.messages[0].content)
        payload = payload.model_copy(update={"model": envelope.model, "state": decoded["state"], "questions": decoded["questions"]})
    except (ValueError, KeyError, IndexError) as exc:
        raise HTTPException(status_code=503, detail="Decision input safety processing failed") from exc
    session = db if db is not None else AsyncSessionLocal()
    try:
        result = await JevEngine.execute_decision(
            db=session,
            request=payload,
            router_key=router_key,
            request_id=req_id,
            record_log=True,
        )
        return await _secure_outbound(result, request, session, router_key, payload.model)
    except HTTPException:
        raise
    except RouterException as re:
        return JSONResponse(
            status_code=re.status_code,
            content=re.to_openai_dict(request_id=req_id),
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(e),
                    "type": "jev_engine_error",
                    "code": "internal_error",
                    "request_id": req_id,
                }
            },
        )
    finally:
        if db is None:
            await _safe_close_session(session)

def _responses_payload(response: ChatCompletionResponse, response_id: str) -> dict:
    message = response.choices[0].message if response.choices else None
    text = message.content if message else ""
    output = []
    if text or not (message and message.tool_calls):
        output.append({
            "id": f"msg_{uuid.uuid4().hex[:16]}", "type": "message",
            "status": "completed", "role": "assistant",
            "content": [{"type": "output_text", "text": text or "", "annotations": []}],
        })
    for call in (message.tool_calls or []) if message else []:
        output.append({
            "id": f"fc_{uuid.uuid4().hex[:16]}", "type": "function_call",
            "status": "completed", "call_id": call.id,
            "name": call.function.name, "arguments": call.function.arguments,
            **({"extra_content": call.extra_content} if call.extra_content else {}),
        })
    usage = response.usage
    return {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": response.model,
        "output": output,
        "output_text": text or "",
        "usage": {
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        },
        "metadata": {},
    }


async def _responses_event_stream(source: AsyncGenerator[str, None], model: str, response_id: str):
    sequence_number = 0

    def event(kind, **fields):
        nonlocal sequence_number
        payload = {"type": kind, "sequence_number": sequence_number, **fields}
        sequence_number += 1
        return f"event: {kind}\ndata: {json.dumps(payload)}\n\n"

    yield event("response.created", response={"id": response_id, "object": "response", "status": "in_progress", "model": model})
    output = []
    calls = {}
    text_item = None
    text_index = None
    usage = None
    async for chunk in source:
        if isinstance(chunk, bytes):
            chunk = chunk.decode()
        for line in chunk.splitlines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if "error" in data:
                yield event("response.failed", response={"id": response_id, "status": "failed", "error": data["error"]})
                return
            if data.get("usage"):
                usage = UsageInfo(**data["usage"])
            choices = data.get("choices") or []
            delta = choices[0].get("delta") or {} if choices else {}
            text = delta.get("content")
            if text:
                if text_item is None:
                    text_index = len(output)
                    text_item = {"id": f"msg_{uuid.uuid4().hex[:16]}", "type": "message", "status": "in_progress", "role": "assistant", "content": []}
                    output.append(text_item)
                    yield event("response.output_item.added", output_index=text_index, item=text_item)
                    part = {"type": "output_text", "text": "", "annotations": []}
                    yield event("response.content_part.added", item_id=text_item["id"], output_index=text_index, content_index=0, part=part)
                    text_item["content"].append(part)
                text_item["content"][0]["text"] += text
                yield event("response.output_text.delta", item_id=text_item["id"], output_index=text_index, content_index=0, delta=text)
            for position, call in enumerate(delta.get("tool_calls") or []):
                index = call.get("index", position)
                function = call.get("function") or {}
                if index not in calls:
                    item = {"id": f"fc_{uuid.uuid4().hex[:16]}", "type": "function_call", "status": "in_progress", "call_id": "", "name": "", "arguments": ""}
                    calls[index] = {"item": item, "output_index": len(output), "added": False}
                    output.append(item)
                state = calls[index]
                item = state["item"]
                if call.get("id"):
                    item["call_id"] = call["id"]
                if call.get("extra_content"):
                    item["extra_content"] = call["extra_content"]
                if function.get("name"):
                    item["name"] += function["name"]
                arguments = function.get("arguments") or ""
                item["arguments"] += arguments
                # Wait for identity before exposing a call; early arguments remain buffered.
                if not state["added"] and item["call_id"] and item["name"]:
                    yield event("response.output_item.added", output_index=state["output_index"], item={**item, "arguments": ""})
                    state["added"] = True
                    arguments = item["arguments"]
                if state["added"] and arguments:
                    yield event("response.function_call_arguments.delta", item_id=item["id"], output_index=state["output_index"], delta=arguments)
    if any(not state["added"] for state in calls.values()):
        yield event("response.failed", response={"id": response_id, "status": "failed", "error": {"type": "upstream_error", "message": "Function call is missing call_id or name"}})
        return
    for index, item in enumerate(output):
        item["status"] = "completed"
        if item["type"] == "function_call":
            yield event("response.function_call_arguments.done", item_id=item["id"], output_index=index, name=item["name"], arguments=item["arguments"])
        else:
            part = item["content"][0]
            yield event("response.output_text.done", item_id=item["id"], output_index=index, content_index=0, text=part["text"])
            yield event("response.content_part.done", item_id=item["id"], output_index=index, content_index=0, part=part)
        yield event("response.output_item.done", output_index=index, item=item)
    completed = _responses_payload(ChatCompletionResponse(model=model, choices=[], usage=usage), response_id)
    completed["output"] = output
    completed["output_text"] = text_item["content"][0]["text"] if text_item else ""
    yield event("response.completed", response=completed)


@router.post("/responses")
async def responses_api(
    payload: ResponsesRequest,
    router_key: Optional[RouterApiKey] = Depends(get_router_key_dep),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    req_id = f"resp_{uuid.uuid4().hex[:16]}"
    request = request if request is not None else Request({"type": "http", "headers": []})
    response = response if response is not None else Response()
    try:
        chat_request = payload.to_chat_request()
    except (ValueError, KeyError) as exc:
        return JSONResponse(status_code=400, content={"error": {"message": str(exc), "type": "invalid_request_error", "request_id": req_id}})
    result = await chat_completions(chat_request, request, response, db, router_key)
    if isinstance(result, StreamingResponse):
        return StreamingResponse(
            _responses_event_stream(result.body_iterator, chat_request.model, req_id),
            media_type="text/event-stream", headers=dict(result.headers),
        )
    if isinstance(result, Response):
        return result
    return _responses_payload(result, req_id)

async def _anthropic_event_stream(source: AsyncGenerator[str, None], model: str, message_id: str):
    yield f"event: message_start\ndata: {json.dumps({'type': 'message_start', 'message': {'id': message_id, 'type': 'message', 'role': 'assistant', 'content': [], 'model': model, 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n\n"
    yield f"event: content_block_start\ndata: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\n"
    output_tokens = 0
    async for chunk in source:
        for line in chunk.splitlines():
            if not line.startswith("data: "):
                continue
            raw = line[6:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if "error" in data:
                yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': {'type': data['error'].get('type', 'api_error'), 'message': data['error'].get('message', 'Request failed')}})}\n\n"
                return
            delta = data.get("choices", [{}])[0].get("delta", {}).get("content") if data.get("choices") else None
            if delta:
                output_tokens += 1
                event = {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": delta}}
                yield f"event: content_block_delta\ndata: {json.dumps(event)}\n\n"
    yield f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n\n"
    yield f"event: message_delta\ndata: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': output_tokens}})}\n\n"
    yield f"event: message_stop\ndata: {json.dumps({'type': 'message_stop'})}\n\n"


@router.post("/messages")
async def anthropic_messages_inbound(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    router_key: Optional[RouterApiKey] = Depends(get_router_key_dep),
):
    try:
        body = await request.json()
        model = body.get("model", "")
        system_text = body.get("system", "")
        anthropic_msgs = body.get("messages", [])

        messages = []
        if system_text:
            messages.append(ChatMessage(role="system", content=system_text))
        for message in anthropic_msgs:
            messages.append(ChatMessage(role=message.get("role", "user"), content=message.get("content", "")))

        is_stream = bool(body.get("stream", False))
        req = ChatCompletionRequest(
            model=model,
            messages=messages,
            temperature=body.get("temperature"),
            top_p=body.get("top_p"),
            max_tokens=body.get("max_tokens"),
            stop=body.get("stop_sequences"),
            stream=is_stream,
            tools=body.get("tools"),
            tool_choice=body.get("tool_choice"),
        )

        resp = await chat_completions(req, request, response, db, router_key)
        if isinstance(resp, StreamingResponse):
            message_id = f"msg_{uuid.uuid4().hex[:16]}"
            return StreamingResponse(
                _anthropic_event_stream(resp.body_iterator, req.model, message_id),
                media_type="text/event-stream", headers=dict(resp.headers),
            )
        if isinstance(resp, Response):
            return resp
        content_text = resp.choices[0].message.content if resp.choices else ""
        return {
            "id": resp.id,
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": content_text}],
            "model": resp.model,
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "output_tokens": resp.usage.completion_tokens if resp.usage else 0,
            },
        }
    except HTTPException:
        raise
    except (ValueError, TypeError) as exc:
        return JSONResponse(status_code=400, content={"type": "error", "error": {"type": "invalid_request_error", "message": "Invalid Messages request"}})
    except RouterException as exc:
        return JSONResponse(status_code=exc.status_code, content={"type": "error", "error": {"type": exc.category.value.lower(), "message": exc.message}})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"type": "error", "error": {"type": "api_error", "message": str(exc)}})
