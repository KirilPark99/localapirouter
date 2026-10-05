"""Fixed cache invariants; SQLite and responses are synthetic only."""
import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import json
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.cache.response_cache import ResponseCacheService as Cache
from app.models.entities import ResponseCacheEntry
from app.schemas.chat import ChatCompletionRequest


REQUEST = {"model": "Synthetic/Model", "messages": [{"role": "user", "content": " hello "}], "temperature": 0.0}
RESPONSE = {"model": "Synthetic/Model", "choices": [{"index": 0, "message": {"role": "assistant", "content": "answer"}, "finish_reason": "stop"}]}
CONTEXT = {"policy_version": "test-policy", "route_fingerprint": "test-route"}


def signature(**changes):
    request = ChatCompletionRequest(**{**REQUEST, **changes})
    return Cache.generate_signature(request.model, request.messages, request=request, router_key_id=1, context=CONTEXT)


@asynccontextmanager
async def isolated_cache(tmp_path):
    Cache._lock = asyncio.Lock()
    Cache._memory_cache = OrderedDict()
    Cache._mem_metrics = dict(hits=0, misses=0, tokens_saved=0, cost_saved_usd=0.0)
    Cache._max_memory_items = 500
    Cache._generation = 0
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'synthetic.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(ResponseCacheEntry.__table__.create)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        Cache._memory_cache.clear()
        Cache._max_memory_items = 500


@pytest.mark.parametrize("field,value", [
    ("max_tokens", 10), ("max_completion_tokens", 11), ("stop", "END"),
    ("response_format", {"type": "json_object"}), ("tool_choice", "none"),
    ("parallel_tool_calls", False), ("seed", 42), ("n", 2),
    ("presence_penalty", 0.1), ("frequency_penalty", 0.2),
    ("logit_bias", {"3": 1.0}), ("reasoning_effort", "high"),
    ("temperature", 0.001), ("top_p", 0.999), ("user", "other"),
    ("metadata", {"semantic": True}), ("reasoning", {"effort": "low"}),
    ("thinking", {"budget_tokens": 2000}),
    ("messages", [{"role": "tool", "content": " hello ", "tool_call_id": "call-other"}]),
    ("model", "synthetic/model"),
])
def test_every_semantic_field_changes_signature(field, value):
    assert signature(**{field: value}) != signature()


def test_signature_preserves_strings_keys_and_policy():
    assert signature(messages=[{"role": "user", "content": "hello"}]) != signature()
    assert signature(stream=True, stream_options={"include_usage": True}) == signature()
    req = ChatCompletionRequest(**REQUEST)
    assert Cache.generate_signature(req.model, req.messages, request=req, router_key_id=2, context=CONTEXT) != signature()
    assert Cache.generate_signature(req.model, req.messages, request=req, router_key_id=1,
        context={**CONTEXT, "policy_version": "new"}) != signature()
    assert Cache.generate_signature(req.model, req.messages, request=req, router_key_id=1,
        context={**CONTEXT, "route_fingerprint": "new"}) != signature()
    assert signature(response_format={"type": "json", "schema": {"a": 1, "b": 2}}) == signature(
        response_format={"schema": {"b": 2, "a": 1}, "type": "json"})
    assert Cache.generate_signature(req.model, req.messages, 0, router_key_id=1) != Cache.generate_signature(
        req.model, req.messages, 0, router_key_id=2)
    old = {"model": req.model.strip().lower(), "messages": [{"role": "user", "content": "hello"}],
           "temperature": 0, "top_p": 1.0, "tools": []}
    import hashlib
    assert signature() != hashlib.sha256(json.dumps(old, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with pytest.raises(ValueError):
        Cache.generate_signature(req.model, req.messages, request=req, router_key_id=1)


def test_ttl_on_both_levels_and_invalid_ttl(tmp_path):
    async def check():
        async with isolated_cache(tmp_path) as sessions, sessions() as db:
            sig = signature()
            await Cache.set_response(db, sig, "synthetic", RESPONSE, ttl_seconds=0)
            assert await Cache.get_response(db, sig) is None
            await Cache.set_response(db, sig, "synthetic", RESPONSE, ttl_seconds=60)
            Cache._memory_cache[sig]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.execute(ResponseCacheEntry.__table__.update().values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
            await db.commit()
            assert await Cache.get_response(db, sig) is None
            assert await db.scalar(select(func.count()).select_from(ResponseCacheEntry)) == 0
            await Cache.set_response(db, sig, "synthetic", RESPONSE, ttl_seconds=60)
            Cache._memory_cache.clear()
            assert await Cache.get_response(db, sig) == RESPONSE  # SQLite naive UTC expiry
            for ttl in (float("nan"), float("inf"), 10**100, -1):
                with pytest.raises(ValueError):
                    await Cache.set_response(db, sig, "synthetic", RESPONSE, ttl_seconds=ttl)
    asyncio.run(check())


def test_upsert_lru_metrics_and_generation(tmp_path):
    async def check():
        async with isolated_cache(tmp_path) as sessions:
            async def write(sig):
                async with sessions() as db:
                    await Cache.set_response(db, sig, "synthetic", RESPONSE, input_tokens=2, output_tokens=3, estimated_cost_usd=0.2)
                    assert await db.scalar(select(1)) == 1
            await asyncio.gather(write("A"), write("A"))
            async with sessions() as db:
                assert await db.scalar(select(func.count()).select_from(ResponseCacheEntry)) == 1
                Cache._max_memory_items = 2
                await write("B")
                await write("A")
                await write("C")
                assert list(Cache._memory_cache) == ["A", "C"]
                cached = await Cache.get_response(db, "A")
                cached["choices"][0]["message"]["content"] = "modified"
                assert (await Cache.get_response(db, "A")) == RESPONSE
                metrics = await Cache.get_metrics(db)
                assert metrics["hits"] == 2 and metrics["tokens_saved"] == 10
                assert metrics["metrics_scope"] == "since_process_start"
                assert metrics["cost_saved_is_estimate"] is True
                generation = Cache.get_generation()
                await Cache.clear_cache(db)
                await Cache.set_response(db, "A", "synthetic", RESPONSE, expected_generation=generation)
                assert await Cache.get_response(db, "A") is None
                assert await db.scalar(select(func.count()).select_from(ResponseCacheEntry)) == 0
    asyncio.run(check())


def test_clear_during_read_or_queued_write_does_not_resurrect(tmp_path):
    async def check():
        async with isolated_cache(tmp_path) as sessions:
            async with sessions() as db:
                await Cache.set_response(db, "A", "synthetic", RESPONSE)
            Cache._memory_cache.clear()
            entered, release = asyncio.Event(), asyncio.Event()
            async with sessions() as reader, sessions() as clearer, sessions() as writer:
                real_execute = reader.execute
                async def paused_execute(*args, **kwargs):
                    result = await real_execute(*args, **kwargs)
                    entered.set()
                    await release.wait()
                    return result
                reader.execute = paused_execute
                reading = asyncio.create_task(Cache.get_response(reader, "A"))
                await entered.wait()
                clearing = asyncio.create_task(Cache.clear_cache(clearer))
                writing = asyncio.create_task(Cache.set_response(writer, "A", "synthetic", RESPONSE))
                await asyncio.sleep(0)
                release.set()
                await asyncio.gather(reading, clearing, writing)
                assert not Cache._memory_cache
                assert await writer.scalar(select(func.count()).select_from(ResponseCacheEntry)) == 0
    asyncio.run(check())


def test_inflight_completed_stream_cannot_write_after_clear(tmp_path):
    async def check():
        async with isolated_cache(tmp_path) as sessions:
            started, completed = asyncio.Event(), asyncio.Event()
            async def delayed_stream_save():
                expected_generation = Cache._generation
                started.set()
                await completed.wait()
                async with sessions() as db:
                    await Cache.set_response(db, signature(), "synthetic", RESPONSE,
                        expected_generation=expected_generation)
            saving = asyncio.create_task(delayed_stream_save())
            await started.wait()
            async with sessions() as db:
                await Cache.clear_cache(db)
                completed.set()
                await saving
                assert await Cache.get_response(db, signature()) is None
                assert await db.scalar(select(func.count()).select_from(ResponseCacheEntry)) == 0
    asyncio.run(check())


def test_failed_persistence_rolls_back(tmp_path):
    async def check():
        async with isolated_cache(tmp_path) as sessions, sessions() as db:
            await Cache.set_response(db, "bad", None, RESPONSE)  # NOT NULL model
            assert db.is_active
            assert await db.scalar(select(1)) == 1
            assert "bad" not in Cache._memory_cache
    asyncio.run(check())


def test_sse_all_choices_tools_reasoning_and_optional_usage():
    async def check():
        response = {**RESPONSE, "system_fingerprint": "test", "usage": {"total_tokens": 9}, "choices": [
            {"index": 0, "message": {"role": "assistant", "content": None, "reasoning_content": "reason",
             "tool_calls": [{"id": "first", "type": "function", "function": {"name": "f", "arguments": "{}"}},
                            {"id": "second", "type": "function", "function": {"name": "g", "arguments": "{}"}}]},
             "finish_reason": "tool_calls"},
            {"index": 1, "message": {"role": "assistant", "content": "choice two"}, "finish_reason": "length"},
        ]}
        async def collect(include_usage=False):
            chunks = [chunk async for chunk in Cache.synthesize_sse_stream(response, "request", include_usage=include_usage)]
            assert chunks[-1] == "data: [DONE]\n\n"
            return [json.loads(chunk[6:]) for chunk in chunks[:-1]]
        chunks = await collect()
        assert not any("usage" in chunk for chunk in chunks)
        choices = [choice for chunk in chunks for choice in chunk["choices"]]
        assert {choice["index"] for choice in choices} == {0, 1}
        assert any(choice["delta"].get("reasoning_content") == "reason" for choice in choices)
        calls = [call for choice in choices for call in choice["delta"].get("tool_calls", [])]
        assert [call["index"] for call in calls] == [0, 1]
        assert any(choice["finish_reason"] == "length" for choice in choices)
        assert (await collect(True))[-1]["usage"] == response["usage"]
        assert not any("usage" in chunk for chunk in await collect(1))
        # The shared collector must recover the replay's first choice losslessly.
        from app.modules.base import collect_chat_completion
        result = await collect_chat_completion(Cache.synthesize_sse_stream(response, "request", include_usage=True), "synthetic")
        assert result.choices[0].message.reasoning_content == "reason"
        assert [call.id for call in result.choices[0].message.tool_calls] == ["first", "second"]
    asyncio.run(check())


def test_message_ids_reasoning_and_names_are_semantic():
    base = {"role": "tool", "content": "same", "tool_call_id": "one", "name": "f", "reasoning_content": "reason"}
    first = signature(messages=[base])
    for field in ("tool_call_id", "name", "reasoning_content"):
        assert signature(messages=[{**base, field: "different"}]) != first
    assert signature(tools=[{"type": "function", "function": {"name": "one"}}]) != signature(
        tools=[{"type": "function", "function": {"name": "two"}}])


def test_metrics_ignore_old_namespace_and_do_not_invent_history(tmp_path):
    async def check():
        async with isolated_cache(tmp_path) as sessions, sessions() as db:
            await Cache.set_response(db, "old-unsafe-hex", "synthetic", RESPONSE)
            await Cache.set_response(db, signature(), "synthetic", RESPONSE)
            Cache._memory_cache.clear()
            await Cache.get_response(db, signature())
            metrics = await Cache.get_metrics(db)
            assert metrics["l2_db_entries"] == 1
            assert metrics["hits"] == 1 and metrics["misses"] == 0
            Cache._mem_metrics = dict(hits=0, misses=0, tokens_saved=0, cost_saved_usd=0.0)
            restarted = await Cache.get_metrics(db)
            assert restarted["hits"] == 0
            assert restarted["l2_db_entries"] == 1
    asyncio.run(check())


def test_cancelled_write_rolls_back_without_promotion(tmp_path):
    async def check():
        async with isolated_cache(tmp_path) as sessions, sessions() as db:
            real_commit = db.commit
            async def cancel_commit():
                raise asyncio.CancelledError()
            db.commit = cancel_commit
            with pytest.raises(asyncio.CancelledError):
                await Cache.set_response(db, signature(), "synthetic", RESPONSE)
            db.commit = real_commit
            assert db.is_active
            assert await db.scalar(select(func.count()).select_from(ResponseCacheEntry)) == 0
            assert not Cache._memory_cache
    asyncio.run(check())


def test_admin_clear_failure_is_controlled_and_keeps_memory(tmp_path):
    async def check():
        from app.api.admin.cache import clear_cache
        from fastapi import HTTPException
        from sqlalchemy.exc import SQLAlchemyError
        async with isolated_cache(tmp_path) as sessions, sessions() as db:
            await Cache.set_response(db, signature(), "synthetic", RESPONSE)
            generation = Cache.get_generation()
            async def failed_execute(*args, **kwargs):
                raise SQLAlchemyError("synthetic failure")
            db.execute = failed_execute
            with pytest.raises(HTTPException) as error:
                await clear_cache(db=db, admin="synthetic-admin")
            assert error.value.status_code == 503
            assert signature() in Cache._memory_cache
            assert generation == Cache.get_generation()
    asyncio.run(check())
