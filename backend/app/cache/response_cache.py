"""Process-local LRU backed by SQLite; cache only completed, policy-safe responses."""
import asyncio
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import math
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import select, update, delete, func
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import ResponseCacheEntry
from app.schemas.chat import ChatMessage, ChatCompletionRequest

logger = logging.getLogger(__name__)


def _utc_naive(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


class ResponseCacheService:
    # ponytail: one process-wide lock includes SQLite I/O; split locks only if throughput requires it.
    # Cross-process invalidation needs a shared generation; this cache currently runs in one worker.
    _lock = asyncio.Lock()
    _generation = 0
    _memory_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    _max_memory_items = 500
    _metrics_started_at = datetime.now(timezone.utc).isoformat()
    _mem_metrics = {"hits": 0, "misses": 0, "tokens_saved": 0, "cost_saved_usd": 0.0}

    @classmethod
    def generate_signature(
        cls,
        model: str,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        tools: Optional[Any] = None,
        router_key_id: Optional[int] = None,
        *,
        request: Optional[ChatCompletionRequest] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Hash the full effective request, principal and effective policy/route context.

        The legacy positional form remains supported, but has a separate namespace
        and cannot share entries with full-request callers. Full-request callers
        must supply authenticated router_key_id (or context['principal']) and a
        nonempty context fingerprint. Only transport streaming options are omitted.
        """
        if request is not None:
            if not context or (router_key_id is None and context.get("principal") is None):
                raise ValueError("Full request cache signatures require principal and policy/route context")
            payload = _json_value(request)
            payload = {key: value for key, value in payload.items() if key not in ("stream", "stream_options")}
        else:
            payload = _json_value(dict(model=model, messages=messages, temperature=temperature, top_p=top_p, tools=tools))
        serialized = json.dumps({
            "namespace": "response-cache-v2-full" if request is not None else "response-cache-v2-legacy",
            "request": payload, "router_key_id": router_key_id, "context": _json_value(context),
        }, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        # Keep the existing 64-character DB column, with an unmistakable non-hex version prefix.
        return "v2:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:61]

    @classmethod
    def is_cacheable(cls, request: ChatCompletionRequest, headers: Dict[str, str]) -> bool:
        for key, value in headers.items():
            if key.lower() in ("x-bypass-cache", "x-no-cache") and str(value).lower() in ("true", "1"):
                return False
        temp = getattr(request, "temperature", None)
        return temp is not None and math.isfinite(float(temp)) and 0 <= float(temp) <= 0.05

    @classmethod
    def get_generation(cls) -> int:
        """Capture before upstream work; pass to set_response to reject writes across clear."""
        return cls._generation

    @classmethod
    def _remember(cls, signature: str, entry: Dict[str, Any]) -> None:
        cls._memory_cache[signature] = entry
        cls._memory_cache.move_to_end(signature)
        while len(cls._memory_cache) > cls._max_memory_items:
            cls._memory_cache.popitem(last=False)

    @classmethod
    def _hit(cls, entry: Dict[str, Any]) -> Dict[str, Any]:
        cls._mem_metrics["hits"] += 1
        cls._mem_metrics["tokens_saved"] += entry["input_tokens"] + entry["output_tokens"]
        cls._mem_metrics["cost_saved_usd"] += entry["estimated_cost_usd"]
        # Callers apply outbound policies; never let them mutate our stored response.
        return deepcopy(entry["response_json"])

    @classmethod
    async def get_response(cls, db: AsyncSession, signature: str) -> Optional[Dict[str, Any]]:
        generation = cls._generation
        async with cls._lock:
            if not signature or generation != cls._generation:
                cls._mem_metrics["misses"] += 1
                return None
            entry = cls._memory_cache.get(signature)
            if entry is not None:
                expires = entry.get("expires_at")
                if expires is None or _utc_naive(expires) > _now():
                    cls._memory_cache.move_to_end(signature)
                    return cls._hit(entry)
                del cls._memory_cache[signature]
            try:
                result = await db.execute(select(ResponseCacheEntry).where(ResponseCacheEntry.signature == signature)
                    .execution_options(populate_existing=True))
                stored = result.scalar_one_or_none()
                if stored is not None:
                    expires = _utc_naive(stored.expires_at) if stored.expires_at is not None else None
                    if expires is not None and expires <= _now():
                        await db.execute(delete(ResponseCacheEntry).where(ResponseCacheEntry.signature == signature))
                        await db.commit()
                    else:
                        entry = dict(response_json=deepcopy(stored.response_json), input_tokens=stored.input_tokens,
                            output_tokens=stored.output_tokens, estimated_cost_usd=stored.estimated_cost_usd, expires_at=expires)
                        await db.execute(update(ResponseCacheEntry).where(ResponseCacheEntry.signature == signature)
                            .values(hit_count=ResponseCacheEntry.hit_count + 1, last_hit_at=_now()))
                        await db.commit()
                        cls._remember(signature, entry)
                        return cls._hit(entry)
            except BaseException as exc:
                await db.rollback()
                if not isinstance(exc, Exception):
                    raise
                # Do not log SQL parameter dumps: cached responses may contain sensitive content.
                logger.warning("L2 response cache read failed (%s)", type(exc).__name__)
            cls._mem_metrics["misses"] += 1
            return None

    @classmethod
    async def set_response(
        cls,
        db: AsyncSession,
        signature: str,
        model: str,
        response_json: Dict[str, Any],
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
        ttl_seconds: Optional[int] = None,
        *,
        expected_generation: Optional[int] = None,
    ) -> None:
        generation = cls._generation if expected_generation is None else expected_generation
        if not signature:
            return
        expires_at = None
        if ttl_seconds is not None:
            try:
                if isinstance(ttl_seconds, bool) or not math.isfinite(ttl_seconds) or ttl_seconds < 0:
                    raise ValueError("TTL must be finite and nonnegative")
                expires_at = _now() + timedelta(seconds=ttl_seconds)
            except (OverflowError, TypeError) as exc:
                raise ValueError("TTL exceeds supported datetime range") from exc
        entry = dict(response_json=deepcopy(response_json), input_tokens=input_tokens, output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd, expires_at=expires_at)
        async with cls._lock:
            if generation != cls._generation:
                return
            try:
                values = dict(signature=signature, model=model, **entry, hit_count=0, last_hit_at=_now())
                stmt = insert(ResponseCacheEntry).values(**values)
                await db.execute(stmt.on_conflict_do_update(index_elements=[ResponseCacheEntry.signature], set_={
                    key: value for key, value in values.items() if key not in ("signature", "hit_count")
                }))
                await db.commit()
            except BaseException as exc:
                await db.rollback()
                if not isinstance(exc, Exception):
                    raise
                logger.warning("L2 response cache write failed (%s)", type(exc).__name__)
                return
            cls._remember(signature, entry)

    @classmethod
    async def synthesize_sse_stream(
        cls, cached_response: Dict[str, Any], req_id: str, include_usage: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Replay every choice with lossless message deltas and indexed tool calls."""
        base = {key: deepcopy(value) for key, value in cached_response.items()
                if key not in ("id", "object", "choices", "usage")}
        base.update(id=req_id, object="chat.completion.chunk")
        base.setdefault("created", int(datetime.now(timezone.utc).timestamp()))
        base.setdefault("model", "cached-model")
        for position, choice in enumerate(cached_response.get("choices") or []):
            delta = deepcopy(choice.get("message") or {})
            delta.setdefault("role", "assistant")
            if delta.get("tool_calls"):
                delta["tool_calls"] = [{**call, "index": index} for index, call in enumerate(delta["tool_calls"])]
            index = choice.get("index", position)
            chunk = {**base, "choices": [{"index": index, "delta": delta, "finish_reason": None}]}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            finished = {**choice, "index": index, "delta": {}}
            finished.pop("message", None)
            chunk = {**base, "choices": [finished]}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        if include_usage is True and cached_response.get("usage") is not None:
            yield f"data: {json.dumps({**base, 'choices': [], 'usage': cached_response['usage']}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    @classmethod
    async def get_metrics(cls, db: AsyncSession) -> Dict[str, Any]:
        """Counters are since process start; savings are estimates, not billing records."""
        async with cls._lock:
            now = _now()
            for signature, entry in list(cls._memory_cache.items()):
                if entry.get("expires_at") is not None and _utc_naive(entry["expires_at"]) <= now:
                    del cls._memory_cache[signature]
            try:
                count = await db.scalar(select(func.count()).select_from(ResponseCacheEntry).where(
                    ResponseCacheEntry.signature.like("v2:%"),
                    (ResponseCacheEntry.expires_at.is_(None)) | (ResponseCacheEntry.expires_at > now),
                ))
            except BaseException as exc:
                await db.rollback()
                if not isinstance(exc, Exception):
                    raise
                count = None
            hits, misses = cls._mem_metrics["hits"], cls._mem_metrics["misses"]
            rate = round(100 * hits / max(1, hits + misses), 2)
            memory_count = len(cls._memory_cache)
            return dict(total_entries=count, l2_db_entries=count, memory_entries=memory_count,
                l1_memory_entries=memory_count, l1_max_size=cls._max_memory_items,
                hits=hits, total_hits=hits, misses=misses, total_misses=misses,
                hit_rate_percent=rate, hit_rate_pct=rate, tokens_saved=cls._mem_metrics["tokens_saved"],
                cost_saved_usd=round(cls._mem_metrics["cost_saved_usd"], 4),
                metrics_scope="since_process_start", metrics_started_at=cls._metrics_started_at,
                cost_saved_is_estimate=True, cost_estimate_note="Only caller-supplied price estimates; zero may mean unavailable",
                l2_available=count is not None, cache_namespace="v2")

    @classmethod
    async def clear_cache(cls, db: AsyncSession) -> Dict[str, Any]:
        async with cls._lock:
            try:
                await db.execute(delete(ResponseCacheEntry))
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
            cls._generation += 1
            cls._memory_cache.clear()
            return {"message": "Response cache cleared successfully", "generation": cls._generation}
