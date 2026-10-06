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
from app.api.deps import get_router_key_dep, get_inference_key_dep
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

async def _metadata_cards(db):
    models = (await db.scalars(select(DiscoveredModel).where(
        DiscoveredModel.enabled == True, DiscoveredModel.available == True,
        DiscoveredModel.is_visible == True, DiscoveredModel.provider.has(Provider.enabled == True),
    ))).all()
    cards = [ModelCard(id=m.canonical_slug, root=m.provider_model_id,
        context_length=m.context_length, max_tokens=m.max_output_tokens,
        reasoning_effort=m.reasoning_effort, temperature=m.temperature, model_type=m.model_type) for m in models]
    for kind, entity in (("route", RoutingProfile), ("fusion", FusionProfile), ("judge", JudgeProfile)):
        for profile in (await db.scalars(select(entity).where(entity.enabled == True))).all():
            identifier = f"{kind}/{profile.slug}"
            cards.append(ModelCard(id=identifier, root=identifier, context_length=getattr(profile, "context_length", None)))
    return list({card.id: card for card in cards}.values())


def _metadata_allowed(router_key, model_id):
    if router_key is None:
        return True
    try:
        RoutingEngine._check_permissions(router_key, model_id)
        return True
    except RouterException as exc:
        if exc.status_code != 403:
            raise
        return False


@router.get("/models", response_model=ModelListResponse)
async def list_models(db: AsyncSession = Depends(get_db), router_key: Optional[RouterApiKey] = Depends(get_router_key_dep)):
    return ModelListResponse(data=[card for card in await _metadata_cards(db) if _metadata_allowed(router_key, card.id)])


@router.get("/models/{model_id:path}", response_model=ModelCard)
async def retrieve_model(model_id: str, db: AsyncSession = Depends(get_db), router_key: Optional[RouterApiKey] = Depends(get_router_key_dep)):
    cards = await _metadata_cards(db)
    wanted = await _normalize_profile_id(model_id.strip(), db)
    card = next((card for card in cards if card.id == wanted or card.root == wanted), None)
    # Exact IDs (including native tags) win before Ollama's compatibility suffix.
    if card is None and wanted.endswith(":latest"):
        wanted = await _normalize_profile_id(wanted.removesuffix(":latest"), db)
        card = next((card for card in cards if card.id == wanted or card.root == wanted), None)
    if card is None:
        return JSONResponse(status_code=404, content={"error": {"message": "Model not found", "type": "invalid_request_error", "code": "model_not_found"}})
    permission_id = wanted if wanted == card.root else card.id
    if not _metadata_allowed(router_key, permission_id):
        return JSONResponse(status_code=403, content={"error": {"message": "Forbidden", "type": "auth_error"}})
    return card


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

async def _normalize_profile_id(model_id, db):
    fusion, model_id = await _resolve_is_fusion(model_id, db)
    if fusion:
        return model_id
    judge, model_id = await _resolve_is_judge(model_id, db)
    if judge or model_id.startswith("route/"):
        return model_id
    profile = await db.scalar(select(RoutingProfile).where(RoutingProfile.slug == model_id, RoutingProfile.enabled == True))
    return f"route/{profile.slug}" if profile else model_id


async def _prepare_chat_payload(payload, request, response, db, router_key, *, compress=True):
    """Shared request boundary for Chat, Responses, Messages and decisions."""
    import hashlib
    from app.security.registry import GuardrailRegistry, may_bypass_guardrails, parse_disabled_guardrails
    from app.compression.pipeline import CompressionPipelineService
    session = db if db is not None else AsyncSessionLocal()
    payload = payload.model_copy(deep=True)
    headers = dict(request.headers)
    try:
        payload.model = await _normalize_profile_id(payload.model.strip(), session)
        fusion, judge = payload.model.startswith("fusion/"), payload.model.startswith("judge/")
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
        if router_key is not None and not hasattr(request.state, "key_reservation"):
            from app.core.admission import admission
            from app.compression.tokenizer import count_messages_tokens
            from app.services.api_key_service import ApiKeyService
            prompt_tokens = count_messages_tokens(payload.messages)
            output_tokens = payload.get_effective_max_tokens()
            if router_key.rate_limit_tpm is not None and output_tokens is None:
                output_tokens = router_key.rate_limit_tpm - prompt_tokens
                if output_tokens <= 0:
                    from app.core.errors import ErrorCategory
                    raise RouterException("API key TPM budget cannot cover an output token", ErrorCategory.RATE_LIMIT, status_code=429, retry_after=60)
                payload = payload.model_copy(update={"max_tokens": output_tokens})
            reservation = admission.reserve("router-key", router_key.id, rpm=router_key.rate_limit_rpm,
                tpm=router_key.rate_limit_tpm, tokens=prompt_tokens + (output_tokens or 0))
            try:
                await ApiKeyService.admit_inference(session, router_key)
            except BaseException:
                reservation.finish(0)
                raise
            request.state.key_reservation = reservation
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
    # Meter actual structured usage; never count SSE chunks as tokens.
    if isinstance(content, str):
        values = []
        for line in content.splitlines():
            if line.startswith("data:") and line[5:].strip() != "[DONE]":
                try:
                    values.append(json.loads(line[5:]))
                except ValueError:
                    pass
    else:
        values = [content.model_dump() if hasattr(content, "model_dump") else content]
    for value in values:
        usage = value.get("usage") if isinstance(value, dict) else None
        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), int):
            request.state.key_actual_tokens = usage["total_tokens"]
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
    router_key: Optional[RouterApiKey] = Depends(get_inference_key_dep),
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
    router_key: Optional[RouterApiKey] = Depends(get_inference_key_dep),
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

async def _native_chat_stream(source, model):
    """Use the common UTF-8/SSE collector; expose only newly assembled deltas."""
    from contextlib import aclosing
    from copy import deepcopy
    from app.modules.base import ChatStreamAccumulator
    accumulator = ChatStreamAccumulator()
    previous = {}
    async with aclosing(source):
        async for chunk in source:
            accumulator.feed(chunk)
            if accumulator.error:
                accumulator.response(model)
            state = accumulator.choices.get(0)
            if state:
                old = previous.get(0, {})
                delta = {}
                for key, field in (("content", "content"), ("reasoning", "reasoning_content")):
                    text = "".join(state[key][len(old.get(key, [])):])
                    if text:
                        delta[field] = text
                details = []
                for index, detail in state["reasoning_details"].items():
                    prior = old.get("reasoning_details", {}).get(index, {})
                    changed = {k: (v[len(prior.get(k, "")):] if k in ("thinking", "signature") else v)
                               for k, v in detail.items() if prior.get(k) != v}
                    if changed:
                        details.append({"type": detail.get("type"), "index": index, **changed})
                if details:
                    delta["reasoning_details"] = details
                calls = []
                for index, call in state["calls"].items():
                    prior = old.get("calls", {}).get(index, {})
                    fn, before = call["function"], prior.get("function", {})
                    change = {"index": index, "function": {k: v[len(before.get(k, "")):]
                              for k, v in fn.items() if v != before.get(k, "")}}
                    for key in ("id", "extra_content"):
                        if call.get(key) and call.get(key) != prior.get(key):
                            change[key] = call[key]
                    if change["function"] or len(change) > 2:
                        calls.append(change)
                if calls:
                    delta["tool_calls"] = calls
                if delta or state["finish"] != old.get("finish"):
                    yield {"choices": [{"delta": delta, "finish_reason": state["finish"]}]}
                previous = deepcopy(accumulator.choices)
            if accumulator.usage is not None:
                yield {"choices": [], "usage": accumulator.usage.model_dump()}
            if accumulator.done:
                break
        accumulator.response(model, require_complete=True)


def _anthropic_stop_reason(finish):
    return {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use",
            "function_call": "tool_use", "content_filter": "refusal"}.get(finish, "end_turn")


def _anthropic_payload(resp):
    message = resp.choices[0].message
    content = [{k: v for k, v in detail.items() if k != "index"}
               for detail in message.reasoning_details or []
               if detail.get("type") in ("thinking", "redacted_thinking")]
    if message.content:
        content.append({"type": "text", "text": message.content})
    for call in message.tool_calls or []:
        arguments = json.loads(call.function.arguments)
        if not isinstance(arguments, dict):
            raise ValueError("Upstream tool input must be an object")
        content.append({"type": "tool_use", "id": call.id, "name": call.function.name, "input": arguments})
    return {"id": resp.id, "type": "message", "role": "assistant", "content": content,
            "model": resp.model, "stop_reason": _anthropic_stop_reason(resp.choices[0].finish_reason),
            "stop_sequence": None, "usage": {"input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens} if resp.usage is not None else None}


def _anthropic_chat_request(body):
    from app.schemas.chat import ToolCall, FunctionCall

    def string(value, label):
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label} must be a non-empty string")
        return value

    def blocks(value, role):
        if isinstance(value, str):
            return [{"type": "text", "text": value}], [], [], []
        if not isinstance(value, list) or not value:
            raise ValueError("Message content must be a string or non-empty block array")
        content, calls, details, results = [], [], [], []
        for part in value:
            if not isinstance(part, dict):
                raise ValueError("Content blocks must be objects")
            kind = part.get("type")
            if kind == "text" and isinstance(part.get("text"), str):
                content.append(dict(part))
            elif kind == "image" and role == "user":
                source = part.get("source")
                if not isinstance(source, dict):
                    raise ValueError("Image source must be an object")
                if source.get("type") == "url":
                    url = string(source.get("url"), "Image URL")
                    if not url.startswith(("https://", "http://")):
                        raise ValueError("Image URL must use HTTP(S)")
                elif source.get("type") == "base64":
                    import base64
                    media = source.get("media_type")
                    if media not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
                        raise ValueError("Unsupported image media type")
                    data = string(source.get("data"), "Image data")
                    base64.b64decode(data, validate=True)
                    url = f"data:{media};base64,{data}"
                else:
                    raise ValueError("Unsupported image source")
                content.append({"type": "image_url", "image_url": {"url": url}})
            elif kind == "tool_use" and role == "assistant":
                if not isinstance(part.get("input"), dict):
                    raise ValueError("Tool input must be an object")
                calls.append(ToolCall(id=string(part.get("id"), "Tool ID"), function=FunctionCall(
                    name=string(part.get("name"), "Tool name"), arguments=json.dumps(part["input"]))))
            elif kind == "tool_result" and role == "user":
                result_content = part.get("content", "")
                if isinstance(result_content, list):
                    result_content, _, _, nested = blocks(result_content, "user")
                    if nested:
                        raise ValueError("Nested tool results are not supported")
                elif not isinstance(result_content, str):
                    raise ValueError("Tool result content must be a string or blocks")
                # Keep is_error as a native tool_result block for lossless adapter roundtrips.
                if "is_error" in part and not isinstance(part["is_error"], bool):
                    raise ValueError("is_error must be boolean")
                results.append(ChatMessage(role="tool", tool_call_id=string(part.get("tool_use_id"), "Tool result ID"),
                                           content=result_content))
            elif kind == "thinking" and role == "assistant":
                if not isinstance(part.get("thinking"), str) or not isinstance(part.get("signature"), str):
                    raise ValueError("Thinking requires text and an opaque signature")
                details.append(dict(part))
            elif kind == "redacted_thinking" and role == "assistant":
                string(part.get("data"), "Redacted thinking data")
                details.append(dict(part))
            else:
                raise ValueError(f"Unsupported {role} content block: {kind}")
        return content, calls, details, results

    if not isinstance(body, dict):
        raise ValueError("Messages request must be an object")
    model = string(body.get("model"), "model")
    maximum = body.get("max_tokens")
    if type(maximum) is not int or maximum <= 0:
        raise ValueError("max_tokens must be a positive integer")
    raw_messages = body.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ValueError("messages must be a non-empty array")
    if "stream" in body and not isinstance(body["stream"], bool):
        raise ValueError("stream must be boolean")
    messages = []
    if body.get("system"):
        content, _, _, _ = blocks(body["system"], "system")
        messages.append(ChatMessage(role="system", content=content))
    call_ids = set()
    for raw in raw_messages:
        if not isinstance(raw, dict) or raw.get("role") not in ("user", "assistant"):
            raise ValueError("Message role must be user or assistant")
        content, calls, details, results = blocks(raw.get("content"), raw["role"])
        for result in results:
            if result.tool_call_id not in call_ids:
                raise ValueError("Tool result has no preceding tool_use")
        for call in calls:
            if call.id in call_ids:
                raise ValueError("Duplicate tool_use ID")
            call_ids.add(call.id)
        messages.extend(results)
        if content or calls or details:
            messages.append(ChatMessage(role=raw["role"], content=content or None,
                                        tool_calls=calls or None, reasoning_details=details or None))
    tools = body.get("tools")
    converted = None
    names = set()
    if tools is not None:
        if not isinstance(tools, list):
            raise ValueError("tools must be an array")
        converted = []
        for tool in tools:
            if not isinstance(tool, dict) or not isinstance(tool.get("input_schema"), dict):
                raise ValueError("Tool requires an input_schema object")
            name = string(tool.get("name"), "Tool name")
            if name in names:
                raise ValueError("Duplicate tool name")
            names.add(name)
            converted.append({"type": "function", "function": {"name": name, "parameters": tool["input_schema"],
                             **({"description": tool["description"]} if "description" in tool else {})}})
    choice, parallel = None, None
    if "tool_choice" in body:
        raw = body["tool_choice"]
        if not isinstance(raw, dict) or raw.get("type") not in ("auto", "any", "none", "tool"):
            raise ValueError("Invalid tool_choice")
        if raw["type"] == "tool":
            name = string(raw.get("name"), "Chosen tool name")
            if name not in names:
                raise ValueError("Chosen tool is not declared")
            choice = {"type": "function", "function": {"name": name}}
        else:
            choice = {"auto": "auto", "any": "required", "none": "none"}[raw["type"]]
        if choice != "none" and not names:
            raise ValueError("tool_choice requires tools")
        if "disable_parallel_tool_use" in raw:
            if not isinstance(raw["disable_parallel_tool_use"], bool):
                raise ValueError("disable_parallel_tool_use must be boolean")
            parallel = not raw["disable_parallel_tool_use"]
    thinking = body.get("thinking")
    if thinking is not None:
        if not isinstance(thinking, dict) or thinking.get("type") not in ("enabled", "disabled", "adaptive"):
            raise ValueError("Invalid thinking configuration")
        if thinking["type"] == "enabled":
            budget = thinking.get("budget_tokens")
            if type(budget) is not int or not 1024 <= budget < maximum:
                raise ValueError("Thinking budget must be at least 1024 and below max_tokens")
        if thinking["type"] != "disabled" and choice not in (None, "auto", "none"):
            raise ValueError("Thinking does not support forced tool choice")
    for key in ("temperature", "top_p"):
        if key in body and (type(body[key]) not in (int, float) or not 0 <= body[key] <= 1):
            raise ValueError(f"{key} must be between zero and one")
    stops = body.get("stop_sequences")
    if stops is not None and (not isinstance(stops, list) or any(not isinstance(s, str) for s in stops)):
        raise ValueError("stop_sequences must be strings")
    return ChatCompletionRequest(model=model, messages=messages, max_tokens=maximum,
        stream=body.get("stream", False), stream_options={"include_usage": True},
        temperature=body.get("temperature"), top_p=body.get("top_p"), stop=stops,
        tools=converted, tool_choice=choice, parallel_tool_calls=parallel, thinking=thinking)


def _responses_payload(response: ChatCompletionResponse, response_id: str) -> dict:
    message = response.choices[0].message if response.choices else None
    text = message.content if message else ""
    finish = response.choices[0].finish_reason if response.choices else None
    terminal = "incomplete" if finish == "length" else "completed"
    output = []
    if text or not (message and message.tool_calls):
        output.append({
            "id": f"msg_{uuid.uuid4().hex[:16]}", "type": "message",
            "status": terminal, "role": "assistant",
            "content": [{"type": "output_text", "text": text or "", "annotations": []}],
        })
    for call in (message.tool_calls or []) if message else []:
        output.append({
            "id": f"fc_{uuid.uuid4().hex[:16]}", "type": "function_call",
            "status": terminal, "call_id": call.id,
            "name": call.function.name, "arguments": call.function.arguments,
            **({"extra_content": call.extra_content} if call.extra_content else {}),
        })
    usage = response.usage
    return {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": terminal,
        "error": None,
        "incomplete_details": {"reason": "max_output_tokens"} if finish == "length" else None,
        "model": response.model,
        "output": output,
        "output_text": text or "",
        "usage": {
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        } if usage is not None else None,
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
    finish = None
    from contextlib import aclosing
    stream = _native_chat_stream(source, model)
    async with aclosing(stream):
        try:
            async for data in stream:
                if data.get("usage"):
                    usage = UsageInfo(**data["usage"])
                choices = data.get("choices") or []
                if choices:
                    finish = choices[0].get("finish_reason") or finish
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
        except (ValueError, TypeError, RouterException, HTTPException):
            yield event("response.failed", response={"id": response_id, "status": "failed", "error": {"type": "upstream_error", "message": "Upstream stream failed or ended before completion"}})
            return
    if any(not state["added"] for state in calls.values()):
        yield event("response.failed", response={"id": response_id, "status": "failed", "error": {"type": "upstream_error", "message": "Function call is missing call_id or name"}})
        return
    for index, item in enumerate(output):
        item["status"] = "incomplete" if finish == "length" else "completed"
        if item["type"] == "function_call":
            yield event("response.function_call_arguments.done", item_id=item["id"], output_index=index, name=item["name"], arguments=item["arguments"])
        else:
            part = item["content"][0]
            yield event("response.output_text.done", item_id=item["id"], output_index=index, content_index=0, text=part["text"])
            yield event("response.content_part.done", item_id=item["id"], output_index=index, content_index=0, part=part)
        yield event("response.output_item.done", output_index=index, item=item)
    completed = _responses_payload(ChatCompletionResponse(model=model, choices=[ChatCompletionChoice(message=ChatMessage(role="assistant"), finish_reason=finish)], usage=usage), response_id)
    completed["output"] = output
    completed["output_text"] = text_item["content"][0]["text"] if text_item else ""
    yield event("response.incomplete" if finish == "length" else "response.completed", response=completed)


@router.post("/responses")
async def responses_api(
    payload: ResponsesRequest,
    router_key: Optional[RouterApiKey] = Depends(get_inference_key_dep),
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
    from contextlib import aclosing

    def event(kind, **fields):
        return f"event: {kind}\ndata: {json.dumps({'type': kind, **fields})}\n\n"

    blocks, calls = {}, {}
    finish, usage = None, None
    stream = _native_chat_stream(source, model)
    async with aclosing(stream):
        try:
            yield event("message_start", message={"id": message_id, "type": "message", "role": "assistant",
                "content": [], "model": model, "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0}})
            async for data in stream:
                if data.get("usage") is not None:
                    usage = UsageInfo.model_validate(data["usage"])
                choices = data.get("choices") or []
                if not choices:
                    continue
                finish = choices[0].get("finish_reason") or finish
                delta = choices[0].get("delta") or {}
                for detail in delta.get("reasoning_details") or []:
                    key = ("thinking", detail.get("index", 0))
                    if key not in blocks:
                        blocks[key] = len(blocks)
                        block = {"type": detail["type"], **({"data": detail["data"]} if detail["type"] == "redacted_thinking"
                                 else {"thinking": "", "signature": ""})}
                        yield event("content_block_start", index=blocks[key], content_block=block)
                    for field in ("thinking", "signature"):
                        if detail.get(field):
                            yield event("content_block_delta", index=blocks[key], delta={"type": field+"_delta", field: detail[field]})
                text = delta.get("content")
                if text:
                    if "text" not in blocks:
                        blocks["text"] = len(blocks)
                        yield event("content_block_start", index=blocks["text"], content_block={"type": "text", "text": ""})
                    yield event("content_block_delta", index=blocks["text"], delta={"type": "text_delta", "text": text})
                for call in delta.get("tool_calls") or []:
                    key = ("tool", call["index"])
                    state = calls.setdefault(key, {"id": "", "name": "", "arguments": ""})
                    state["id"] = call.get("id") or state["id"]
                    fn = call.get("function") or {}
                    state["name"] += fn.get("name") or ""
                    arguments = fn.get("arguments") or ""
                    state["arguments"] += arguments
                    if key not in blocks and state["id"] and state["name"]:
                        blocks[key] = len(blocks)
                        yield event("content_block_start", index=blocks[key], content_block={
                            "type": "tool_use", "id": state["id"], "name": state["name"], "input": {}})
                        arguments = state["arguments"]
                    if key in blocks and arguments:
                        yield event("content_block_delta", index=blocks[key], delta={"type": "input_json_delta", "partial_json": arguments})
            for key, call in calls.items():
                if key not in blocks or not isinstance(json.loads(call["arguments"]), dict):
                    raise ValueError("Incomplete upstream tool call")
            for index in blocks.values():
                yield event("content_block_stop", index=index)
            yield event("message_delta", delta={"stop_reason": _anthropic_stop_reason(finish), "stop_sequence": None},
                        usage={"input_tokens": usage.prompt_tokens, "output_tokens": usage.completion_tokens} if usage is not None else {})
            yield event("message_stop")
        except (ValueError, TypeError, RouterException, HTTPException):
            yield event("error", error={"type": "api_error", "message": "Upstream stream failed or ended before completion"})


@router.post("/messages")
async def anthropic_messages_inbound(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    router_key: Optional[RouterApiKey] = Depends(get_inference_key_dep),
):
    try:
        req = _anthropic_chat_request(await request.json())
    except (ValueError, TypeError, KeyError):
        return JSONResponse(status_code=400, content={"type": "error", "error": {
            "type": "invalid_request_error", "message": "Invalid Messages request"}})
    try:
        resp = await chat_completions(req, request, response, db, router_key)
        if isinstance(resp, StreamingResponse):
            return StreamingResponse(_anthropic_event_stream(resp.body_iterator, req.model, f"msg_{uuid.uuid4().hex[:16]}"),
                media_type="text/event-stream", headers={k: v for k, v in resp.headers.items() if k.lower() != "content-length"})
        if isinstance(resp, JSONResponse):
            data = json.loads(resp.body)
            error = data.get("error", {})
            return JSONResponse(status_code=resp.status_code, headers={k: v for k, v in resp.headers.items()
                if k.lower() != "content-length"}, content={"type": "error", "error": {
                "type": _anthropic_error_type(resp.status_code), "message": error.get("message", "Request failed")}})
        if isinstance(resp, Response):
            return resp
        return _anthropic_payload(resp)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"type": "error", "error": {
            "type": _anthropic_error_type(exc.status_code), "message": str(exc.detail)}})
    except RouterException as exc:
        return JSONResponse(status_code=exc.status_code, content={"type": "error", "error": {
            "type": _anthropic_error_type(exc.status_code), "message": exc.message}})
    except Exception:
        logger.exception("Native Messages response failed")
        return JSONResponse(status_code=502, content={"type": "error", "error": {
            "type": "api_error", "message": "Upstream Messages response is invalid"}})


def _anthropic_error_type(status_code):
    return {400: "invalid_request_error", 401: "authentication_error", 403: "permission_error",
            404: "not_found_error", 413: "request_too_large", 422: "invalid_request_error",
            429: "rate_limit_error", 529: "overloaded_error"}.get(status_code, "api_error")
