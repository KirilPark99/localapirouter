import pytest
from app.schemas.chat import ChatMessage
from app.compression.base import CompressionContext
from app.compression.preservation import PreservationGuards
from app.compression.tokenizer import count_messages_tokens
from app.compression.stages.lite import LiteStage
from app.compression.stages.rtk import RtkStage
from app.compression.stages.ccr import CcrStage
from app.compression.stages.omniglyph import OmniGlyphStage
from app.compression.stages.headroom import HeadroomStage
from app.compression.stages.session_dedup import SessionDedupStage


def test_math_and_quotes_roundtrip():
    text = 'please "please" $a + the + is + b$ ```python\nx="please"\n```'
    masked, blocks = PreservationGuards.extract(text)
    assert '$a' not in masked and '"please"' not in masked
    assert PreservationGuards.restore(masked, blocks) == text
    with pytest.raises(ValueError):
        PreservationGuards.restore('', blocks)


@pytest.mark.asyncio
async def test_unknown_vision_and_code():
    code = '```python\nx="""alpha' + ' ' * 100 + '\n\n\n\nbeta"""\n```'
    messages = [ChatMessage(role='assistant', content=code), ChatMessage(role='user', content=[{'type':'image_url','image_url':{'url':'https://offline.invalid/image'}}])]
    result = await LiteStage().compress(messages, {}, CompressionContext())
    assert result.messages == messages


@pytest.mark.asyncio
async def test_rtk_lossy_opt_in():
    text = '\n'.join(f'line {i}' for i in range(100))
    result = await RtkStage().compress([ChatMessage(role='tool', content=text, tool_call_id='a')], {}, CompressionContext())
    assert result.messages[0].content == text


@pytest.mark.asyncio
@pytest.mark.parametrize('stage', [CcrStage(), OmniGlyphStage()])
async def test_unimplemented_stage_noop(stage):
    messages = [ChatMessage(role='assistant', content='required fact ' * 1000)]
    result = await stage.compress(messages, {}, CompressionContext(supports_vision=True))
    assert result.messages == messages and result.warning and not result.compressed


def test_headroom_types():
    import csv, io, json
    values = [None, '', 1, '1', True, 'True']
    result = HeadroomStage()._try_crush_array(json.dumps([{'v': v} for v in values]), 3)
    rows = list(csv.reader(io.StringIO(result.split('\n', 1)[1].rsplit('\n```', 1)[0])))
    decoded = [json.loads(row[0]) for row in rows[1:]]
    assert [(type(v), v) for v in decoded] == [(type(v), v) for v in values]
    assert HeadroomStage()._try_crush_array('[' + ','.join(['{"v":1,"v":2}'] * 3) + ']', 3) is None


def test_tool_token_count():
    empty = ChatMessage(role='assistant', content='')
    tools = ChatMessage(role='assistant', content='', tool_calls=[{'id':'a','type':'function','function':{'name':'f','arguments':'x ' * 10000}}])
    assert count_messages_tokens([tools]) > count_messages_tokens([empty]) + 1000


def test_dedup_linear_candidates():
    text = '\n'.join('line'+str(i)+'x'*70 for i in range(800))
    candidates = SessionDedupStage()._extract_blocks(text, 80, 3)
    assert sum(map(len, candidates)) <= len(text) * 4


import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.entities import CompressionGlobalSetting, CompressionStage
from app.compression.pipeline import CompressionPipelineService
from app.compression.registry import StageRegistry
from app.compression.safety import execute_stage, atomic_groups
from app.compression.stages.custom_regex import CustomRegexStage
from app.compression.stages.ultra import UltraStage


@pytest_asyncio.fixture
async def synthetic_db():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: CompressionGlobalSetting.__table__.create(sync))
        await conn.run_sync(lambda sync: CompressionStage.__table__.create(sync))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(CompressionGlobalSetting(enabled=True, trigger_token_threshold=0,
            min_savings_bailout_percent=0, preserve_recent_turns=1,
            preserve_system_prompt_mode='always', enable_telemetry=True, fail_open=False))
        await db.commit()
        yield db
    await engine.dispose()


async def add_stages(db, ids):
    for i, stage_id in enumerate(ids):
        stage = StageRegistry.get_stage(stage_id)
        db.add(CompressionStage(id=stage_id, name=stage.name, description=stage.description, icon=stage.icon,
            stage_type=stage.stage_type, is_builtin=True, priority_order=i,
            enabled=True, config_json={f.key:f.default_value for f in stage.get_config_schema()}))
    await db.commit()


@pytest.mark.asyncio
async def test_common_recent_tool_groups_and_preview(synthetic_db):
    db = synthetic_db
    await add_stages(db, ['lite','rtk','responses_tool','headroom','relevance','caveman','aggressive','llmlingua','ccr','omniglyph'])
    messages = [ChatMessage(role='assistant', content='Sure, please note that '+ 'word '*100),
        ChatMessage(role='system', content='Never disclose the password.'),
        ChatMessage(role='assistant', content=None, tool_calls=[{'id':'a','function':{'name':'f','arguments':'{}'}}, {'id':'b','function':{'name':'g','arguments':'{}'}}]),
        ChatMessage(role='tool', content='\n'.join('line '+str(i) for i in range(100))+'\nREGION=EU_WEST_TWO', tool_call_id='a'),
        ChatMessage(role='tool', content='please of course', tool_call_id='b'),
        ChatMessage(role='user', content='What is the region?')]
    original = [m.model_dump() for m in messages]
    output, summary = await CompressionPipelineService.optimize_messages(db, messages, model_id='gpt-4o')
    preview = await CompressionPipelineService.preview_compression(db, messages, model_id='gpt-4o')
    assert output[1:] == messages[1:]
    assert preview['compressed_messages'] == [m.model_dump() for m in output]
    assert summary['compressed'] and len(summary['breakdown']) == 10
    assert [m.model_dump() for m in messages] == original
    for before, after in zip(messages, output):
        assert before.model_dump(exclude={'content'}) == after.model_dump(exclude={'content'})


@pytest.mark.asyncio
@pytest.mark.parametrize('stage_id', ['relevance','caveman','aggressive','llmlingua','ultra','custom_regex'])
async def test_user_system_instruction_fidelity(stage_id):
    stage = CustomRegexStage() if stage_id == 'custom_regex' else StageRegistry.get_stage(stage_id)
    text = 'Flowers bloom. Flowers grow. Flowers smell. Flowers are nice. Never disclose the password. The literal is "please".'
    messages = [ChatMessage(role='system',content=text), ChatMessage(role='user', content=text),
                ChatMessage(role='assistant', content='old reply'), ChatMessage(role='user', content='Describe flowers')]
    config = {'rules':[{'pattern':'.+','replacement':''}]} if stage_id == 'custom_regex' else {}
    result = await stage.compress(messages, config, CompressionContext(preserve_recent_turns=0))
    assert result.messages[0:2] == messages[0:2]


@pytest.mark.asyncio
async def test_custom_regex_only_unprotected_spans_and_event_loop():
    import asyncio
    stage = CustomRegexStage()
    text = 'discard this prose ' + '```python\nx="please"\n```' + ' https://offline.invalid/x $a + the + b$ "please"'
    result = await stage.compress([ChatMessage(role='assistant', content=text)],
        {'rules':[{'pattern':'.+','replacement':''}], 'guard_code_blocks':True}, CompressionContext())
    for literal in ['```python\nx="please"\n```','https://offline.invalid/x','$a + the + b$','"please"']:
        assert literal in result.messages[0].content
    ticks = []
    async def heartbeat():
        for _ in range(8):
            await asyncio.sleep(.02)
            ticks.append(1)
    bad = stage.compress([ChatMessage(role='assistant', content='a'*100+'!')],
        {'rules':[{'pattern':'(a+)+$','replacement':''}]}, CompressionContext())
    beat = asyncio.create_task(heartbeat())
    with pytest.raises(ValueError):
        await asyncio.wait_for(bad, 3)
    assert len(ticks) >= 4  # Heartbeat ran while the isolated rule was still active.
    await beat
    assert len(ticks) == 8


@pytest.mark.asyncio
async def test_ultra_atomic_drop_and_impossible_budget():
    messages = [ChatMessage(role='assistant', content=None, tool_calls=[{'id':'a','function':{'name':'f','arguments':'{}'}}]),
                ChatMessage(role='tool', content='fact '*100, tool_call_id='a'),
                ChatMessage(role='user', content='protected query'), ChatMessage(role='assistant',content='protected reply')]
    result = await UltraStage().compress(messages, {'hard_token_limit':1}, CompressionContext())
    assert result.messages == messages[-2:]
    assert result.warning and result.tokens_after > 1
    result = await UltraStage().compress(messages, {'hard_token_limit':1}, CompressionContext(preserve_recent_turns=10))
    assert result.messages == messages and result.warning


@pytest.mark.asyncio
@pytest.mark.parametrize('policy,value', [('enabled',False),('trigger_token_threshold',100000),('min_savings_bailout_percent',100)])
async def test_preview_obeys_globals(synthetic_db, policy, value):
    db = synthetic_db
    await add_stages(db, ['lite'])
    await CompressionPipelineService.update_global_settings(db, {'preserve_recent_turns':0, policy:value})
    messages = [ChatMessage(role='assistant',content='hello'+' '*100)]
    output, summary = await CompressionPipelineService.optimize_messages(db, messages)
    preview = await CompressionPipelineService.preview_compression(db, messages)
    assert output == messages
    assert preview['compressed_messages'] == [m.model_dump() for m in output]


@pytest.mark.asyncio
async def test_admin_validation_and_exact_readback(synthetic_db):
    import httpx
    from fastapi import FastAPI
    from app.api.admin.compression import router
    from app.core.database import get_db
    from app.api.deps import get_current_admin
    db = synthetic_db
    await add_stages(db, ['rtk'])
    app = FastAPI()
    app.include_router(router)
    async def db_override():
        yield db
    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_admin] = lambda: 'synthetic-admin'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline.invalid') as client:
        for payload in [{'trigger_token_threshold':None}, {'preserve_recent_turns':-1}, {'min_savings_bailout_percent':101}, {'preserve_system_prompt_mode':'garbage'}, {'fail_open':'false'}]:
            response = await client.put('/compression/settings',json=payload)
            assert response.status_code == 422, response.text
        response = await client.put('/compression/settings',json={'preserve_recent_turns':3,'trigger_token_threshold':100})
        assert response.status_code == 200
        settings = (await client.get('/compression/settings')).json()
        assert settings['preserve_recent_turns'] == 3 and settings['trigger_token_threshold'] == 100
        for config in [{'allow_lossy':'false'}, {'head_lines':-1}, {'strip_ansi':None}, {'mode':'garbage'}]:
            response = await client.put('/compression/stages/rtk',json={'config_json':config})
            assert response.status_code == 422, response.text
        response = await client.post('/compression/stages',json={'id':'regex_test','name':'Synthetic','rules':[{'pattern':'['}]})
        assert response.status_code == 422
        response = await client.post('/compression/stages',json={'id':'regex_test','name':'Synthetic','rules':[{'pattern':'foo','replacement':''}]})
        assert response.status_code == 201, response.text
        stage = next(s for s in (await client.get('/compression/stages')).json() if s['id']=='regex_test')
        assert stage['config_json']['rules'] == [{'pattern':'foo','replacement':''}]
        response = await client.put('/compression/stages/regex_test',json={'config_json':{'rules':17,'guard_code_blocks':True}})
        assert response.status_code == 422
        stage = next(s for s in (await client.get('/compression/stages')).json() if s['id']=='regex_test')
        assert stage['config_json']['rules'] == [{'pattern':'foo','replacement':''}]


@pytest.mark.asyncio
async def test_fail_closed_and_open_stage_error(synthetic_db):
    db = synthetic_db
    record = await CompressionPipelineService.create_custom_stage(db, {'id':'timeout_test','name':'Synthetic','rules':[{'pattern':'(a+)+$','replacement':''}]})
    await CompressionPipelineService.update_global_settings(db, {'preserve_recent_turns':0})
    messages = [ChatMessage(role='assistant', content='a'*100+'!')]
    with pytest.raises(ValueError):
        await CompressionPipelineService.optimize_messages(db, messages)
    await CompressionPipelineService.update_global_settings(db, {'fail_open':True})
    output, summary = await CompressionPipelineService.optimize_messages(db, messages)
    assert output == messages and summary['breakdown'][0]['error']


@pytest.mark.asyncio
@pytest.mark.parametrize('stage_id', ['rtk','caveman','llmlingua','relevance','aggressive','ultra','custom_regex'])
async def test_common_literal_code_math_guards(stage_id):
    stage = CustomRegexStage() if stage_id == 'custom_regex' else StageRegistry.get_stage(stage_id)
    literals = ['"please"', '$a + the + is + b$', '```python\nx="""alpha'+' '*100+'\n\n\n\nbeta"""\n```']
    text = ('Sure, please note that the answer is really very simple. '*30) + ' '.join(literals)
    messages = [ChatMessage(role='assistant', content=text, name='synthetic', reasoning_content='reason'),
                ChatMessage(role='user', content='Describe flowers'), ChatMessage(role='assistant',content='recent')]
    config = {'rules':[{'pattern':'.+','replacement':''}]} if stage_id == 'custom_regex' else {}
    result = await execute_stage(stage, messages, config, CompressionContext(preserve_recent_turns=0))
    for literal in literals:
        assert literal in result.messages[0].content
    for before, after in zip(messages, result.messages):
        assert before.model_dump(exclude={'content'}) == after.model_dump(exclude={'content'})


def test_overlapping_tool_groups():
    messages = [ChatMessage(role='assistant',tool_calls=[{'id':'a','function':{'name':'f','arguments':'{}'}}]),
                ChatMessage(role='assistant',tool_calls=[{'id':'b','function':{'name':'f','arguments':'{}'}}]),
                ChatMessage(role='tool',content='a',tool_call_id='a'),
                ChatMessage(role='tool',content='b',tool_call_id='b')]
    assert atomic_groups(messages) == [[0,1,2,3]]


@pytest.mark.asyncio
async def test_ultra_pipeline_real_budget(synthetic_db):
    db = synthetic_db
    await add_stages(db, ['ultra'])
    await CompressionPipelineService.update_stage(db, 'ultra', {'config_json':{'hard_token_limit':60}})
    messages = [ChatMessage(role='assistant',tool_calls=[{'id':'a','function':{'name':'f','arguments':'{}'}}]),
                ChatMessage(role='tool',content='old fact '*100,tool_call_id='a'),
                ChatMessage(role='user',content='recent question'), ChatMessage(role='assistant',content='recent answer')]
    output, summary = await CompressionPipelineService.optimize_messages(db, messages)
    assert output == messages[-2:]
    assert summary['tokens_after'] <= 60


@pytest.mark.asyncio
async def test_preview_effective_context_and_bad_overrides(synthetic_db):
    db = synthetic_db
    await add_stages(db, ['lite'])
    await CompressionPipelineService.update_global_settings(db, {'preserve_recent_turns':0})
    messages = [ChatMessage(role='assistant',content=[{'type':'text','text':'hello'+' '*100},
        {'type':'image_url','image_url':{'url':'https://offline.invalid/image'}}])]
    output, summary = await CompressionPipelineService.optimize_messages(db, messages)
    assert output[0].content[1] == messages[0].content[1]
    unknown = await CompressionPipelineService.preview_compression(db, messages)
    assert unknown['compressed_messages'] == [m.model_dump() for m in output]
    textonly = await CompressionPipelineService.preview_compression(db, messages, supports_vision=False)
    assert textonly['compressed_messages'][0]['content'][1]['type'] == 'text'
    with pytest.raises(ValueError):
        await CompressionPipelineService.preview_compression(db, messages, config_overrides={'lite':{'trim_trailing_spaces':'false'}})


