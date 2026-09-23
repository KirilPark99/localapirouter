import uuid
import json
import time
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, AsyncSessionLocal, _safe_close_session
from app.api.deps import get_router_key_dep
from app.models.entities import RouterApiKey, DiscoveredModel, RoutingProfile, FusionProfile, Provider
from app.schemas.chat import ChatCompletionRequest, ChatCompletionResponse, ChatMessage, ResponsesRequest
from app.schemas.entities import ModelListResponse, ModelCard
from app.routing.engine import RoutingEngine
from app.fusion.engine import FusionEngine
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
    if model_str.startswith("route/"):
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

@router.post("/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    request: Request,
    db: Optional[AsyncSession] = Depends(lambda: None),
    router_key: Optional[RouterApiKey] = Depends(get_router_key_dep),
):
    req_id = f"req_{uuid.uuid4().hex[:16]}"
    model_str = payload.model.strip()
    is_fusion, model_str = await _resolve_is_fusion(model_str, db)
    payload.model = model_str

    try:
        if is_fusion:
            if payload.stream:
                stream_gen = FusionEngine.execute_fusion_stream(
                    db=None, request=payload, router_key=router_key, request_id=req_id
                )
                return StreamingResponse(stream_gen, media_type="text/event-stream")
            else:
                if db is not None:
                    return await FusionEngine.execute_fusion(
                        db=db, request=payload, router_key=router_key, request_id=req_id
                    )
                else:
                    session = AsyncSessionLocal()
                    try:
                        return await FusionEngine.execute_fusion(
                            db=session, request=payload, router_key=router_key, request_id=req_id
                        )
                    finally:
                        await _safe_close_session(session)
        else:
            if payload.stream:
                stream_gen = RoutingEngine.route_stream_chat(
                    db=None, request=payload, router_key=router_key, request_id=req_id
                )
                return StreamingResponse(stream_gen, media_type="text/event-stream")
            else:
                if db is not None:
                    return await RoutingEngine.route_chat_completions(
                        db=db, request=payload, router_key=router_key, request_id=req_id
                    )
                else:
                    session = AsyncSessionLocal()
                    try:
                        return await RoutingEngine.route_chat_completions(
                            db=session, request=payload, router_key=router_key, request_id=req_id
                        )
                    finally:
                        await _safe_close_session(session)
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
                    "type": "router_internal_error",
                    "code": "internal_error",
                    "request_id": req_id,
                }
            },
        )

def _responses_payload(response: ChatCompletionResponse, response_id: str) -> dict:
    text = response.choices[0].message.content if response.choices else ""
    usage = response.usage
    return {
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": response.model,
        "output": [{
            "id": f"msg_{uuid.uuid4().hex[:16]}",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text or "", "annotations": []}],
        }],
        "output_text": text or "",
        "usage": {
            "input_tokens": usage.prompt_tokens if usage else 0,
            "output_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        },
        "metadata": {},
    }


async def _responses_event_stream(source: AsyncGenerator[str, None], model: str, response_id: str):
    created = {
        "type": "response.created",
        "response": {"id": response_id, "object": "response", "status": "in_progress", "model": model},
    }
    yield f"event: response.created\ndata: {json.dumps(created)}\n\n"
    output_index = 0
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
                yield f"event: response.failed\ndata: {json.dumps({'type': 'response.failed', 'response': {'id': response_id, 'status': 'failed', 'error': data['error']}})}\n\n"
                return
            delta = data.get("choices", [{}])[0].get("delta", {}).get("content") if data.get("choices") else None
            if delta:
                event = {"type": "response.output_text.delta", "item_id": response_id, "output_index": output_index, "content_index": 0, "delta": delta}
                yield f"event: response.output_text.delta\ndata: {json.dumps(event)}\n\n"
    completed = {"type": "response.completed", "response": {"id": response_id, "object": "response", "status": "completed", "model": model}}
    yield f"event: response.completed\ndata: {json.dumps(completed)}\n\n"


@router.post("/responses")
async def responses_api(
    payload: ResponsesRequest,
    router_key: Optional[RouterApiKey] = Depends(get_router_key_dep),
    db: AsyncSession = Depends(get_db),
):
    req_id = f"resp_{uuid.uuid4().hex[:16]}"
    chat_request = payload.to_chat_request()
    is_fusion, chat_request.model = await _resolve_is_fusion(chat_request.model, db)
    try:
        if payload.stream:
            source = (
                FusionEngine.execute_fusion_stream(None, chat_request, router_key, req_id)
                if is_fusion
                else RoutingEngine.route_stream_chat(None, chat_request, router_key, req_id)
            )
            return StreamingResponse(
                _responses_event_stream(source, chat_request.model, req_id),
                media_type="text/event-stream",
            )
        response = (
            await FusionEngine.execute_fusion(db, chat_request, router_key, req_id)
            if is_fusion
            else await RoutingEngine.route_chat_completions(db, chat_request, router_key, req_id)
        )
        return _responses_payload(response, req_id)
    except RouterException as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_openai_dict(request_id=req_id))
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": {"message": str(exc), "type": "router_internal_error", "request_id": req_id}})

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

        is_fusion, req.model = await _resolve_is_fusion(req.model, db)
        model = req.model

        if is_stream:
            message_id = f"msg_{uuid.uuid4().hex[:16]}"
            source = (
                FusionEngine.execute_fusion_stream(None, req, router_key, message_id)
                if is_fusion
                else RoutingEngine.route_stream_chat(None, req, router_key, message_id)
            )
            return StreamingResponse(
                _anthropic_event_stream(source, model, message_id),
                media_type="text/event-stream",
            )

        resp = (
            await FusionEngine.execute_fusion(db, req, router_key)
            if is_fusion
            else await RoutingEngine.route_chat_completions(db, req, router_key)
        )
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
    except RouterException as exc:
        return JSONResponse(status_code=exc.status_code, content={"type": "error", "error": {"type": exc.category.value.lower(), "message": exc.message}})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"type": "error", "error": {"type": "api_error", "message": str(exc)}})
