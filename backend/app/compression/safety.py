"""Shared fidelity boundary for live and preview compression."""
import uuid
from app.compression.preservation import PreservationGuards
from app.compression.tokenizer import count_messages_tokens

LOSSY_STAGES = {'ccr', 'omniglyph', 'relevance', 'caveman', 'aggressive', 'llmlingua', 'ultra', 'custom_regex'}


def atomic_groups(messages):
    """Contiguous tool exchanges, including overlapping multi-call groups."""
    last_result = {msg.tool_call_id: i for i, msg in enumerate(messages) if msg.tool_call_id}
    groups = []
    i = 0
    while i < len(messages):
        end = i + 1
        cursor = i
        while cursor < end:
            calls = messages[cursor].tool_calls or []
            ids = {c.get('id') if isinstance(c, dict) else c.id for c in calls}
            for call_id in ids:
                end = max(end, last_result.get(call_id, cursor) + 1)
            cursor += 1
        groups.append(list(range(i, end)))
        i = end
    return groups


def protected_indices(messages, recent):
    # A turn is a user message and the complete ensuing assistant/tool exchange.
    starts = [i for i, m in enumerate(messages) if m.role == 'user']
    if recent <= 0:
        start = len(messages)
    elif starts:
        start = starts[max(0, len(starts) - recent)]
    else:
        start = max(0, len(messages) - recent * 2)
    if recent > 0:
        start = min(start, max(0, len(messages) - recent * 2))
    protected = set(range(start, len(messages)))
    for group in atomic_groups(messages):
        if protected.intersection(group):
            protected.update(group)
    return protected


async def execute_stage(stage, messages, config, context):
    lossy = stage.stage_type == 'custom_regex' or stage.id in LOSSY_STAGES or (stage.id == 'rtk' and config.get('allow_lossy') is True)
    protected = protected_indices(messages, context.preserve_recent_turns)
    protected.update(i for i, m in enumerate(messages)
                     if (m.role in {'system', 'developer'} and (context.preserve_system_prompt or lossy))
                     or (stage.id == 'session_dedup' and m.role in {'user', 'system', 'developer'})
                     or (lossy and m.role == 'user')
                     or ((stage.stage_type == 'custom_regex' or stage.id in {'caveman', 'relevance', 'aggressive', 'llmlingua', 'custom_regex'})
                         and (m.role in {'tool', 'function'} or m.tool_calls)))
    # Ultra owns atomic removal and uses real payload token counts, not masked counts.
    if stage.id == 'ultra':
        result = await stage.compress([m.model_copy(deep=True) for m in messages], config, context)
        for i in protected:
            if sum(m == messages[i] for m in result.messages) < sum(m == messages[i] for m in messages):
                raise ValueError('Ultra changed protected context')
        return result
    if stage.id == 'lite':
        config = {**config, 'dedup_system_prompts': False}
    # Mask protected contents, retaining positions and group metadata for stages.
    markers = {}
    work = []
    for i, msg in enumerate(messages):
        if i in protected:
            marker = '__compression_guard_' + uuid.uuid4().hex
            markers[marker] = msg
            work.append(msg.model_copy(deep=True, update={'content': None, 'name': marker}))
        else:
            work.append(msg.model_copy(deep=True))
    result = await stage.compress(work, config, context)
    if not result.compressed:
        result.messages = messages
        result.tokens_before = result.tokens_after = count_messages_tokens(messages)
        result.savings_percent = 0
        return result
    seen = set()
    restored = []
    for msg in result.messages:
        if msg.name in markers:
            if msg.name in seen:
                raise ValueError('Stage duplicated protected message')
            seen.add(msg.name)
            restored.append(markers[msg.name])
        else:
            restored.append(msg)
    if seen != set(markers):
        raise ValueError('Stage removed protected message')
    # For position-preserving stages, exact structures must survive unchanged.
    if len(restored) == len(messages):
        for before, after in zip(messages, restored):
            if before.model_dump(exclude={'content'}) != after.model_dump(exclude={'content'}):
                raise ValueError('Stage changed message ordering or metadata')
            if isinstance(before.content, str) and isinstance(after.content, str) and lossy:
                _, blocks = PreservationGuards.extract(before.content)
                if any(after.content.count(b.content) < before.content.count(b.content) for b in blocks):
                    raise ValueError('Stage changed protected literal/code/math')
    elif stage.id != 'ultra':
        raise ValueError('Stage changed message positions')
    if stage.id == "ultra" and config.get("hard_token_limit", 0) > 0 and count_messages_tokens(restored) > config["hard_token_limit"]:
        result.warning = "Impossible hard budget: protected context exceeds limit"
    result.messages = restored
    result.tokens_before = count_messages_tokens(messages)
    result.tokens_after = count_messages_tokens(restored)
    result.savings_percent = max(0, round((result.tokens_before - result.tokens_after) / max(1, result.tokens_before) * 100, 2))
    result.compressed = result.tokens_after < result.tokens_before
    return result
