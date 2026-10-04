import pytest
from app.schemas.chat import ChatMessage, ChatCompletionRequest
from app.compression.caching_aware import is_prompt_caching_supported, should_preserve_system_prompt
from app.routing.cache_affinity import (
    PrefixAnalyzer,
    RendezvousHasher,
    resolve_prompt_cache_key,
    apply_prompt_cache_affinity,
)
from app.cache.response_cache import ResponseCacheService
from app.core.database import AsyncSessionLocal


def test_is_prompt_caching_supported():
    assert is_prompt_caching_supported("anthropic/claude-3-5-sonnet") is True
    assert is_prompt_caching_supported("openai/gpt-4o") is True
    assert is_prompt_caching_supported("deepseek/deepseek-chat") is True
    assert is_prompt_caching_supported("google/gemini-2.0-flash") is True
    assert is_prompt_caching_supported("qwen/qwen-2.5-72b") is True
    assert is_prompt_caching_supported("unknown-provider/some-random-model") is False


def test_should_preserve_system_prompt():
    # mode = 'always'
    assert should_preserve_system_prompt("always", "random/model") is True
    # mode = 'never'
    assert should_preserve_system_prompt("never", "openai/gpt-4o") is False
    # mode = 'when_caching'
    assert should_preserve_system_prompt("when_caching", "openai/gpt-4o") is True
    assert should_preserve_system_prompt("when_caching", "random/model") is False
    # header with cache-control
    assert should_preserve_system_prompt("when_caching", "random/model", {"cache-control": "max-age=3600"}) is True


def test_prefix_analyzer():
    msgs = [
        ChatMessage(role="system", content="System instruction for assistant"),
        ChatMessage(role="user", content="Turn 1 user question"),
        ChatMessage(role="assistant", content="Turn 1 assistant answer"),
        ChatMessage(role="user", content="Turn 2 user question"),
    ]
    analysis = PrefixAnalyzer.analyze_prefix(msgs)
    assert analysis["prefix_end_idx"] == 0
    assert analysis["prefix_hash"] != ""
    assert analysis["prefix_tokens"] > 0

    cache_key = PrefixAnalyzer.generate_prompt_cache_key(msgs)
    assert cache_key.startswith("myai-")
    assert len(cache_key) > 10


def test_rendezvous_hasher():
    key = "myai-1234567890abcdef"
    score1 = RendezvousHasher.score(key, "target_A")
    score2 = RendezvousHasher.score(key, "target_B")
    assert 0.0 <= score1 <= 1.0
    assert 0.0 <= score2 <= 1.0
    # Determinism: same key and target must yield exact same score
    assert RendezvousHasher.score(key, "target_A") == score1


def test_apply_prompt_cache_affinity():
    msgs = [
        ChatMessage(role="system", content="Consistent system prompt across sessions"),
        ChatMessage(role="user", content="Hello world"),
    ]
    req = ChatCompletionRequest(model="route/test", messages=msgs)

    class DummyCandidate:
        def __init__(self, cid, mid, cred_id):
            self.id = cid
            self.model_id = mid
            self.credential_id = cred_id
            self.credential_group = None

    cands = [
        DummyCandidate(1, 10, 100),
        DummyCandidate(2, 20, 200),
        DummyCandidate(3, 30, 300),
    ]

    reordered, info = apply_prompt_cache_affinity(cands, req)
    assert info["applied"] is True
    assert len(reordered) == 3

    # Repeat with same prompt: winner must be identical (Affinity stickiness)
    reordered_repeat, info_repeat = apply_prompt_cache_affinity(cands, req)
    assert reordered_repeat[0].id == reordered[0].id
    assert info_repeat["winner_target"] == info["winner_target"]


@pytest.mark.asyncio
async def test_response_cache_lifecycle():
    msgs = [ChatMessage(role="user", content="What is 10 + 10?")]
    model = "test-model"
    sig = ResponseCacheService.generate_signature(model=model, messages=msgs, temperature=0.0)
    assert len(sig) == 64

    # Check cacheable
    req = ChatCompletionRequest(model=model, messages=msgs, temperature=0.0)
    assert ResponseCacheService.is_cacheable(req, {}) is True

    # Bypass header
    assert ResponseCacheService.is_cacheable(req, {"x-bypass-cache": "true"}) is False

    # Store in cache
    dummy_resp = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "The answer is 20."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    async with AsyncSessionLocal() as db:
        await ResponseCacheService.set_response(
            db=db,
            signature=sig,
            model=model,
            response_json=dummy_resp,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.0001,
        )

        # Retrieve
        cached = await ResponseCacheService.get_response(db, sig)
        assert cached is not None
        assert cached["choices"][0]["message"]["content"] == "The answer is 20."

        # Synthetic streaming
        chunks = []
        async for chunk in ResponseCacheService.synthesize_sse_stream(cached, "req-123"):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert any("The answer is 20." in c for c in chunks)
        assert chunks[-1] == "data: [DONE]\n\n"

        # Check metrics
        metrics = await ResponseCacheService.get_metrics(db)
        assert metrics["hits"] >= 1
        assert metrics["total_entries"] >= 1

        # Clear cache
        await ResponseCacheService.clear_cache(db)
        cached_after = await ResponseCacheService.get_response(db, sig)
        assert cached_after is None
