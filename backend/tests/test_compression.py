import pytest
from app.schemas.chat import ChatMessage
from app.compression.base import CompressionContext
from app.compression.preservation import PreservationGuards
from app.compression.tokenizer import estimate_tokens, count_messages_tokens
from app.compression.stages.lite import LiteStage
from app.compression.stages.caveman import CavemanStage
from app.compression.stages.headroom import HeadroomStage
from app.compression.stages.rtk import RtkStage
from app.compression.stages.session_dedup import SessionDedupStage
from app.compression.stages.ccr import CcrStage
from app.compression.stages.responses_tool import ResponsesToolStage
from app.compression.stages.relevance import RelevanceStage
from app.compression.stages.aggressive import AggressiveStage
from app.compression.stages.llmlingua import LlmLinguaStage
from app.compression.stages.ultra import UltraStage
from app.compression.stages.custom_regex import CustomRegexStage
from app.compression.pipeline import CompressionPipelineService

@pytest.mark.asyncio
async def test_preservation_guards():
    text = (
        "Here is python code:\n"
        "```python\ndef foo(x):\n    return x + 1\n```\n"
        "And math: $$E = mc^2$$\n"
        "And link: https://example.com/api/test\n"
        "And inline `var_name = 123`."
    )
    extracted, blocks = PreservationGuards.extract(text)
    assert len(blocks) == 4
    assert "def foo" not in extracted
    assert "E = mc^2" not in extracted
    assert "https://example.com" not in extracted

    restored = PreservationGuards.restore(extracted, blocks)
    assert restored == text

@pytest.mark.asyncio
async def test_lite_stage():
    stage = LiteStage()
    msgs = [
        ChatMessage(role="system", content="System instruction"),
        ChatMessage(role="system", content="System instruction"),  # duplicate
        ChatMessage(role="user", content="Hello   \n\n\n\nWorld!   "),
    ]
    ctx = CompressionContext(model_id="test", original_tokens=50)
    res = await stage.compress(msgs, {"collapse_whitespace": True, "trim_trailing_spaces": True, "dedup_system_prompts": True}, ctx)
    assert res.compressed
    # duplicate system prompt removed
    system_msgs = [m for m in res.messages if m.role == "system"]
    assert len(system_msgs) == 1
    # whitespace collapsed
    user_msg = [m for m in res.messages if m.role == "user"][0]
    assert "\n\n\n\n" not in user_msg.content
    assert "\n\nWorld!" in user_msg.content

@pytest.mark.asyncio
async def test_caveman_stage():
    stage = CavemanStage()
    msgs = [
        ChatMessage(role="user", content="Could you please help me?"),
        ChatMessage(role="assistant", content="Sure! Certainly, I would be happy to help. Here is the answer due to the fact that you asked."),
    ]
    ctx = CompressionContext(model_id="test", original_tokens=50)
    res = await stage.compress(msgs, {"intensity": "full"}, ctx)
    assert res.compressed
    assert "Certainly" not in res.messages[1].content
    assert "because" in res.messages[1].content

@pytest.mark.asyncio
async def test_headroom_stage():
    stage = HeadroomStage()
    json_array = (
        '```json\n'
        '[\n'
        '  {"id": 1, "name": "Alice", "city": "Paris"},\n'
        '  {"id": 2, "name": "Bob", "city": "London"},\n'
        '  {"id": 3, "name": "Charlie", "city": "Berlin"},\n'
        '  {"id": 4, "name": "David", "city": "Madrid"},\n'
        '  {"id": 5, "name": "Eve", "city": "Rome"},\n'
        '  {"id": 6, "name": "Frank", "city": "Tokyo"}\n'
        ']\n'
        '```'
    )
    msgs = [ChatMessage(role="assistant", content=json_array)]
    ctx = CompressionContext(model_id="test", original_tokens=100)
    res = await stage.compress(msgs, {"min_rows": 5}, ctx)
    assert res.compressed
    import csv, io, json
    assert "```omni-tabular-json-cells [6 rows]" in res.messages[0].content
    rows = list(csv.reader(io.StringIO(res.messages[0].content.split("\n", 1)[1].rsplit("\n```", 1)[0])))
    assert rows[0] == ["id", "name", "city"]
    assert [json.loads(cell) for cell in rows[1]] == [1, "Alice", "Paris"]

@pytest.mark.asyncio
async def test_rtk_stage():
    stage = RtkStage()
    log_content = (
        "\x1b[32m[INFO]\x1b[0m Starting tests...\n"
        "repeated test line\n"
        "repeated test line\n"
        "repeated test line\n"
        "repeated test line\n"
        "All tests passed."
    )
    msgs = [ChatMessage(role="tool", content=log_content)]
    ctx = CompressionContext(model_id="test", original_tokens=50)
    res = await stage.compress(msgs, {"strip_ansi": True, "dedup_repeated_lines": True, "allow_lossy": True}, ctx)
    assert res.compressed
    assert "\x1b[32m" not in res.messages[0].content
    assert "[... repeated" in res.messages[0].content

@pytest.mark.asyncio
async def test_session_dedup_stage():
    stage = SessionDedupStage()
    shared_block = (
        "This is a long duplicated block of text that repeats across multiple messages.\n"
        "It spans multiple lines and contains many identical characters.\n"
        "Here is line three of the duplicated block.\n"
        "Here is line four of the duplicated block."
    )
    msgs = [
        ChatMessage(role="user", content=f"First time:\n{shared_block}"),
        ChatMessage(role="assistant", content="Acknowledged."),
        ChatMessage(role="user", content=f"Second time:\n{shared_block}"),
        ChatMessage(role="assistant", content="Final reply."),
    ]
    ctx = CompressionContext(model_id="test", original_tokens=150, preserve_recent_turns=0)
    res = await stage.compress(msgs, {"min_block_chars": 50, "min_block_lines": 3}, ctx)
    assert res.compressed
    assert "[dedup:block" in res.messages[2].content or "[dedup:ref" in res.messages[2].content

@pytest.mark.asyncio
async def test_custom_regex_stage():
    stage = CustomRegexStage()
    msgs = [
        ChatMessage(role="user", content="Hello AcmeConfidential and TopSecret internal data!"),
    ]
    ctx = CompressionContext(model_id="test", original_tokens=30)
    rules = [
        {"pattern": r"AcmeConfidential", "replacement": "[REDACTED]", "case_sensitive": False},
        {"pattern": r"TopSecret\s*", "replacement": "", "case_sensitive": False},
    ]
    res = await stage.compress(msgs, {"rules": rules, "guard_code_blocks": True}, ctx)
    assert not res.compressed
    assert res.messages == msgs  # User instructions are not regex data.
    assistant = msgs[0].model_copy(update={"role": "assistant"})
    allowed = await stage.compress([assistant], {"rules": rules, "guard_code_blocks": True}, ctx)
    assert allowed.compressed
    assert "[REDACTED]" in allowed.messages[0].content
    assert "TopSecret" not in allowed.messages[0].content
    assert allowed.messages[0].model_dump(exclude={"content"}) == assistant.model_dump(exclude={"content"})
