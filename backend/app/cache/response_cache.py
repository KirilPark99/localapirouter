"""Two-Tier Response Cache (L1 Memory LRU + L2 SQLite).
Caches deterministic LLM responses to eliminate latency (<5ms) and reduce external API costs to $0.
Supports both non-streaming and synthetic streaming responses.
"""
import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, _safe_close_session
from app.models.entities import ResponseCacheEntry, CacheMetric
from app.schemas.chat import ChatMessage, ChatCompletionRequest

logger = logging.getLogger(__name__)


class ResponseCacheService:
    _lock = asyncio.Lock()
    _memory_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
    _max_memory_items: int = 500

    # In-memory metrics buffer for fast increments
    _mem_metrics = {
        "hits": 0,
        "misses": 0,
        "tokens_saved": 0,
        "cost_saved_usd": 0.0,
    }

    @classmethod
    def generate_signature(
        cls,
        model: str,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        tools: Optional[Any] = None,
        router_key_id: Optional[int] = None,
    ) -> str:
        """
        Generates a deterministic SHA-256 signature for the request.
        """
        normalized_messages = []
        for m in messages:
            if isinstance(m, dict):
                role = m.get("role") or "user"
                content = m.get("content")
                tool_calls = m.get("tool_calls")
            else:
                role = getattr(m, "role", "user") or "user"
                content = getattr(m, "content", None)
                tool_calls = getattr(m, "tool_calls", None)

            msg_dict = {"role": str(role)}
            if content is not None:
                if isinstance(content, str):
                    msg_dict["content"] = content.strip()
                else:
                    msg_dict["content"] = content
            if tool_calls:
                msg_dict["tool_calls"] = [
                    tc.model_dump() if hasattr(tc, "model_dump") else tc
                    for tc in tool_calls
                ]
            normalized_messages.append(msg_dict)

        eff_temp = round(temperature, 2) if temperature is not None else 0.0
        eff_top_p = round(top_p, 2) if top_p is not None else 1.0

        key_dict = {
            "model": model.strip().lower(),
            "messages": normalized_messages,
            "temperature": eff_temp,
            "top_p": eff_top_p,
            "tools": tools or [],
        }
        serialized = json.dumps(key_dict, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def is_cacheable(cls, request: ChatCompletionRequest, headers: Dict[str, str]) -> bool:
        """
        Determines if the request is eligible for response caching.
        Follows OmniRoute semantic cache doctrine:
        - Must NOT have bypass header (x-bypass-cache, x-no-cache)
        - Requires explicit deterministic temperature (temperature == 0.0 or <= 0.05)
          Omitted temperature is treated as non-deterministic and not cached.
        """
        # Bypass headers
        for k, v in headers.items():
            if k.lower() in ("x-bypass-cache", "x-no-cache") and str(v).lower() in ("true", "1"):
                return False

        # Requires explicit deterministic temperature
        temp = getattr(request, "temperature", None)
        if temp is None or float(temp) > 0.05:
            return False

        return True

    @classmethod
    async def get_response(
        cls, db: AsyncSession, signature: str
    ) -> Optional[Dict[str, Any]]:
        """
        Looks up response in L1 (Memory) then L2 (SQLite).
        """
        # 1. L1 Memory Lookup
        async with cls._lock:
            if signature in cls._memory_cache:
                entry = cls._memory_cache[signature]
                # Move to end (most recently used)
                cls._memory_cache.move_to_end(signature)
                cls._mem_metrics["hits"] += 1
                cls._mem_metrics["tokens_saved"] += entry.get("input_tokens", 0) + entry.get("output_tokens", 0)
                cls._mem_metrics["cost_saved_usd"] += entry.get("estimated_cost_usd", 0.0)
                return entry["response_json"]

        # 2. L2 SQLite Lookup
        try:
            stmt = select(ResponseCacheEntry).where(ResponseCacheEntry.signature == signature)
            res = await db.execute(stmt)
            db_entry = res.scalar_one_or_none()

            if db_entry:
                now = datetime.now(timezone.utc)
                if db_entry.expires_at and db_entry.expires_at < now:
                    await db.delete(db_entry)
                    await db.commit()
                    cls._mem_metrics["misses"] += 1
                    return None

                # Update hit stats
                db_entry.hit_count += 1
                db_entry.last_hit_at = now
                await db.commit()

                # Promote to L1
                async with cls._lock:
                    cls._memory_cache[signature] = {
                        "response_json": db_entry.response_json,
                        "input_tokens": db_entry.input_tokens,
                        "output_tokens": db_entry.output_tokens,
                        "estimated_cost_usd": db_entry.estimated_cost_usd,
                    }
                    if len(cls._memory_cache) > cls._max_memory_items:
                        cls._memory_cache.popitem(last=False)
                    cls._mem_metrics["hits"] += 1
                    cls._mem_metrics["tokens_saved"] += db_entry.input_tokens + db_entry.output_tokens
                    cls._mem_metrics["cost_saved_usd"] += db_entry.estimated_cost_usd

                return db_entry.response_json
        except Exception as e:
            logger.warning(f"Error reading L2 response cache: {e}")

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
    ) -> None:
        """
        Stores response in both L1 (Memory) and L2 (SQLite).
        """
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + ttl_seconds, tz=timezone.utc
            )

        # Store in L1 Memory
        async with cls._lock:
            cls._memory_cache[signature] = {
                "response_json": response_json,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": estimated_cost_usd,
            }
            if len(cls._memory_cache) > cls._max_memory_items:
                cls._memory_cache.popitem(last=False)

        # Store in L2 SQLite
        try:
            stmt = select(ResponseCacheEntry).where(ResponseCacheEntry.signature == signature)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()

            if existing:
                existing.response_json = response_json
                existing.input_tokens = input_tokens
                existing.output_tokens = output_tokens
                existing.estimated_cost_usd = estimated_cost_usd
                existing.expires_at = expires_at
                existing.last_hit_at = datetime.now(timezone.utc)
            else:
                new_entry = ResponseCacheEntry(
                    signature=signature,
                    model=model,
                    response_json=response_json,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=estimated_cost_usd,
                    hit_count=1,
                    expires_at=expires_at,
                )
                db.add(new_entry)
            await db.commit()
        except Exception as e:
            logger.warning(f"Error persisting response cache to L2 SQLite: {e}")

    @classmethod
    async def synthesize_sse_stream(
        cls, cached_response: Dict[str, Any], req_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Synthesizes standard OpenAI SSE chunks from a cached JSON response.
        Allows instant streaming with 0 external API cost and <5ms latency.
        """
        choices = cached_response.get("choices", [])
        if not choices:
            yield "data: [DONE]\n\n"
            return

        choice = choices[0]
        msg = choice.get("message", {})
        content = msg.get("content") or ""
        role = msg.get("role") or "assistant"
        tool_calls = msg.get("tool_calls")
        model = cached_response.get("model", "cached-model")

        # 1. Role chunk
        role_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": role},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(role_chunk, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.001)

        # 2. Content chunk(s)
        if content:
            # Send in small chunks for realistic streaming feel
            chunk_size = 32
            for i in range(0, len(content), chunk_size):
                text_slice = content[i : i + chunk_size]
                content_chunk = {
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": int(datetime.now(timezone.utc).timestamp()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": text_slice},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(content_chunk, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.001)

        # 3. Tool calls chunk if present
        if tool_calls:
            tc_chunk = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"tool_calls": tool_calls},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(tc_chunk, ensure_ascii=False)}\n\n"

        # 4. Finish chunk
        finish_chunk = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": choice.get("finish_reason") or "stop",
                }
            ],
        }
        yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"

        # 5. Usage chunk if available
        if "usage" in cached_response:
            usage_chunk = {
                "id": req_id,
                "object": "chat.completion.chunk",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "model": model,
                "choices": [],
                "usage": cached_response["usage"],
            }
            yield f"data: {json.dumps(usage_chunk, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    @classmethod
    async def get_metrics(cls, db: AsyncSession) -> Dict[str, Any]:
        """Returns consolidated metrics: hits, misses, hit rate, tokens and cost saved."""
        total_hits = cls._mem_metrics["hits"]
        total_misses = cls._mem_metrics["misses"]
        tokens_saved = cls._mem_metrics["tokens_saved"]
        cost_saved = cls._mem_metrics["cost_saved_usd"]

        try:
            res = await db.execute(select(ResponseCacheEntry))
            entries = res.scalars().all()
            total_entries = len(entries)
            db_hits = sum(e.hit_count - 1 for e in entries)
            db_tokens_saved = sum((e.hit_count - 1) * (e.input_tokens + e.output_tokens) for e in entries)
            db_cost_saved = sum((e.hit_count - 1) * e.estimated_cost_usd for e in entries)

            # Combine memory metrics with persistent historical records
            effective_hits = max(total_hits, db_hits)
            effective_tokens = max(tokens_saved, db_tokens_saved)
            effective_cost = max(cost_saved, db_cost_saved)
        except Exception:
            total_entries = len(cls._memory_cache)
            effective_hits = total_hits
            effective_tokens = tokens_saved
            effective_cost = cost_saved

        total_lookups = effective_hits + total_misses
        hit_rate = round((effective_hits / max(1, total_lookups)) * 100, 2)

        return {
            "total_entries": total_entries,
            "l2_db_entries": total_entries,
            "memory_entries": len(cls._memory_cache),
            "l1_memory_entries": len(cls._memory_cache),
            "l1_max_size": cls._max_memory_items,
            "hits": effective_hits,
            "total_hits": effective_hits,
            "misses": total_misses,
            "total_misses": total_misses,
            "hit_rate_percent": hit_rate,
            "hit_rate_pct": hit_rate,
            "tokens_saved": effective_tokens,
            "cost_saved_usd": round(effective_cost, 4),
        }

    @classmethod
    async def clear_cache(cls, db: AsyncSession) -> Dict[str, Any]:
        """Clears both L1 memory cache and L2 SQLite cache table."""
        async with cls._lock:
            cls._memory_cache.clear()

        await db.execute(delete(ResponseCacheEntry))
        await db.commit()
        return {"message": "Response cache cleared successfully"}
