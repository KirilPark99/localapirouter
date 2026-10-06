"""Serve the private build first: python -m http.server 18791 --bind 127.0.0.1 --directory /home/kiril/.local/state/MyAIrouter/audits/20261005_fixes90/frontend-build
Run with browser_exec(session='fix90ui'): exec(Path(this_file).read_text()); setup(); run_core(); run_navigation(); run_auth().
Uses the existing audit's synthetic fixture, a private static build, and no real API.
"""
from pathlib import Path
import json
import time
import re

AUDIT = Path('/home/kiril/.local/state/MyAIrouter/audits/20261005_full/ui')
OUT = Path('/home/kiril/.local/state/MyAIrouter/audits/20261005_fixes90')
URL = 'http://127.0.0.1:18791/'


def setup():
    new_tab('about:blank')
    cdp('Network.enable')
    cdp('Network.setBlockedURLs', urls=['*/api/*', '*/v1/*', '*fonts.googleapis.com*', '*fonts.gstatic.com*'])
    script = (AUDIT / 'intercept.js').read_text().replace('FIXTURES', (AUDIT / 'fixtures.json').read_text())
    cdp('Page.addScriptToEvaluateOnNewDocument', source=script)
    goto_url(URL)
    wait_for_load()
    time.sleep(.5)
    assert 'synthetic-audit' in text()


def text():
    return js('document.body.innerText')


def nav(i):
    js(f"document.querySelectorAll('aside nav button')[{i}].click()")
    time.sleep(.25)


def click(label):
    assert js('(()=>{const b=[...document.querySelectorAll("main button,form button,dialog button")].find(b=>b.innerText===' + json.dumps(label) + ');if(!b)return false;b.click();return true})()'), label
    time.sleep(.2)


def save(number, selectors, facts):
    snapshot = js('({text:document.body.innerText,requests:__audit.requests,errors:__audit.errors,alerts:__audit.alerts,url:location.href})')
    snapshot.update(number=number, selectors=selectors, facts=facts, passed=True)
    p = OUT / f'frontend-point-{number}.json'
    p.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    p.chmod(0o600)
    print(f'PASS {number}: {facts}')


def run_core():
    # 12: error envelope after partial content, seven-byte CRLF chunks.
    nav(3)
    fill_input('main textarea', 'audit normal stream')
    click('Send')
    assert 'AUDIT_STREAM_OK' in text()
    js("__audit.stream='error'")
    fill_input('main textarea', 'audit error stream')
    click('Send')
    assert 'AUDIT_STREAM_FAILURE' in text()
    # The failed Chat does not append a successful empty assistant message.
    assert text().count('AUDIT_STREAM_OK') == 1
    # Exercise malformed JSON separately: parser failures must be visible too.
    js(r"""window.__realMockFetch=window.fetch;window.fetch=async(u,o)=>new URL(u,location.href).pathname==='/v1/chat/completions'?new Response('data: {broken}\n\ndata: [DONE]\n\n',{headers:{'content-type':'text/event-stream'}}):__realMockFetch(u,o)""")
    fill_input('main textarea', 'malformed stream')
    click('Send')
    assert 'JSON' in text() or 'Unexpected' in text() or 'Expected' in text()
    click('Single')
    js(r'''window.__cancelled=false;window.fetch=async(u,o)=>new URL(u,location.href).pathname==='/v1/chat/completions'?new Response(new ReadableStream({start(c){let bytes=new TextEncoder().encode('data: {"choices":[{"delta":{"content":"PARTIAL_VISIBLE"}}]}\n\ndata: {"error":{"message":"LATE_FAILURE"}}\n\n');for(let i=0;i<bytes.length;i+=7)c.enqueue(bytes.slice(i,i+7))},cancel(){__cancelled=true}}),{headers:{'content-type':'text/event-stream'}}):__realMockFetch(u,o)''')
    fill_input('main textarea', 'late failure')
    click('Send')
    assert 'LATE_FAILURE' in text() and 'tok/s' not in text()
    assert js('__cancelled') is True
    js('window.fetch=__realMockFetch')
    save(12, ['main textarea', 'button: Send'], {'inband_error_visible': True, 'parser_error_visible': True, 'empty_success_not_appended': True, 'late_error_visible': True, 'reader_cancelled': True})

    # 90: metrics use usage, not delta event count; no usage is unavailable.
    js("__audit.stream='success'")
    click('Single')
    fill_input('main textarea', 'audit metric')
    click('Send')
    body = text()
    match = re.search(r'Response Output\n(\d+)ms\n([\d.]+) tok/s', body)
    assert match, body[-1800:]
    implied = int(match[1]) * float(match[2]) / 1000
    assert abs(implied - 20) < .2, implied
    request = js("__audit.requests.filter(r=>r.path==='/v1/chat/completions').at(-1)")
    assert request['body']['stream_options']['include_usage'] is True
    assert '10p / 20c' in body
    js(r"""window.fetch=async(u,o)=>new URL(u,location.href).pathname==='/v1/chat/completions'?new Response('data: {"choices":[{"delta":{"content":"NO_USAGE"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',{headers:{'content-type':'text/event-stream'}}):__realMockFetch(u,o)""")
    fill_input('main textarea', 'no usage')
    click('Send')
    assert 'NO_USAGE' in text() and 'tok/s' not in text()
    js('window.fetch=__realMockFetch')
    click('Compare (x2)')
    fill_input('main textarea', 'compare usage')
    click('Run Comparison')
    assert text().count('Tokens: 30') == 2, text()[-1800:]
    click('Single')
    save(90, ['button: Single', 'main textarea', 'button: Send', 'button: Run Comparison'], {'completion_tokens': 20, 'implied_tokens': implied, 'include_usage': True, 'missing_usage_has_no_fake_rate': True, 'compare_total_tokens_each': 30})

    # 13: selected ID never replaces admin Bearer credential.
    click('Jev (System One)')
    js(r"""(()=>{let s=[...document.querySelectorAll('main select')].find(s=>[...s.options].some(o=>o.text.includes('Audit Key')));s.value='1';s.dispatchEvent(new Event('change',{bubbles:true}));window.fetch=async(u,o={})=>{if(new URL(u,location.href).pathname==='/v1/systemone'){__audit.jev_headers=o.headers;__audit.requests.push({path:'/v1/systemone',method:'POST',body:JSON.parse(o.body),transport:'fetch',status:200});return new Response(JSON.stringify({id:'mock-jev',model:JSON.parse(o.body).model,answers:{},usage:{input_tokens:10,output_tokens:20,total_tokens:30}}),{headers:{'content-type':'application/json'}})}return __realMockFetch(u,o)}})()""")
    click('Evaluate Decision')
    facts = js("({admin_bearer:__audit.jev_headers.Authorization==='Bearer synthetic-audit-only',router_key_id:__audit.jev_headers['X-Router-Key-Id'],token_preserved:localStorage.getItem('myairouter_token')==='synthetic-audit-only'})")
    assert facts == {'admin_bearer': True, 'router_key_id': '1', 'token_preserved': True}
    assert '30 tok' in text() and 'Visual' in text()
    js("document.querySelector('main button[title=\"Export code (cURL / Python / Node.js)\"]').click()")
    time.sleep(.1)
    click('cURL')
    code = js("document.querySelector('main code').innerText")
    assert 'Bearer 1' not in code and 'synthetic-audit-only' not in code and 'sk-router-YOUR-KEY' in code
    js("document.querySelector('main code').closest('.fixed').querySelector('button').click()")
    facts['jev_success_rendered'] = True
    facts['export_uses_placeholder_not_key_id_or_admin_secret'] = True
    js('window.fetch=__realMockFetch')
    save(13, ['main select: Audit Key', 'button: Evaluate Decision'], facts)

    # 56: provider Edit sends explicit empty note, readback removes old note.
    js("__audit.fixtures['/api/admin/providers'][0].notes='AUDIT_EXISTING_NOTE'")
    nav(9)
    js("document.querySelector('main button[title=Edit]').click()")
    time.sleep(.1)
    fill_input('form textarea', '')
    click('Save')
    req = js("__audit.requests.filter(r=>r.path==='/api/admin/providers/1'&&r.method==='PUT').at(-1)")
    assert req['body']['notes'] == ''
    assert js("__audit.fixtures['/api/admin/providers'][0].notes") == ''
    assert 'AUDIT_EXISTING_NOTE' not in text()
    save(56, ['main button[title=Edit]', 'form textarea', 'button: Save'], {'sent_notes': '', 'readback_clear': True})

    # 57: failed and pending privacy writes do not lie about persisted value.
    nav(14)
    js(r"""window.__privacy=document.querySelectorAll('main input[type=checkbox]')[7];__audit.fail={path:'/api/admin/settings',method:'POST',status:503};__privacy.click()""")
    time.sleep(.2)
    assert 'AUDIT_CONTROLLED_FAILURE' in text()
    assert js('__privacy.checked') is False
    assert js("__audit.fixtures['/api/admin/settings'].log_request_content") is False
    js(r"""__audit.fail=null;window.fetch=(u,o={})=>new URL(u,location.href).pathname==='/api/admin/settings'&&o.method==='POST'?new Promise(resolve=>window.__finishPrivacy=()=>{__audit.fixtures['/api/admin/settings'].log_request_content=JSON.parse(o.body).log_request_content;resolve(new Response('{}',{headers:{'content-type':'application/json'}}))}):__realMockFetch(u,o);__privacy.click()""")
    time.sleep(.1)
    assert js('__privacy.disabled && !__privacy.checked') is True
    js('__finishPrivacy()')
    time.sleep(.15)
    assert js('__privacy.checked && !__privacy.disabled') is True
    assert js("__audit.fixtures['/api/admin/settings'].log_request_content") is True
    js('window.fetch=__realMockFetch')
    save(57, ['main input[type=checkbox]: privacy (index 7)'], {'failure_restored': True, 'pending_disabled': True, 'success_readback': True})

    # 58: initial error is visible and retry recovers catalog.
    js("__audit.fail={path:'/api/admin/providers',method:'GET',status:503}")
    nav(9)
    assert 'AUDIT_CONTROLLED_FAILURE' in text()
    assert js("document.querySelector('main [role=alert]')!==null")
    js('__audit.fail=null')
    click('Retry')
    assert 'Audit Provider' in text() and 'AUDIT_CONTROLLED_FAILURE' not in text()
    save(58, ['main [role=alert]', 'button: Retry'], {'visible_load_error': True, 'retry_recovers': True})

    # 54: failed optimistic reorder rolls back, preserving mutation error.
    stages = [{'id': 'audit-custom', 'name': 'Audit Custom Stage', 'description': 'Synthetic stage', 'icon': 'Sliders', 'stage_type': 'custom', 'priority_order': 10, 'enabled': True, 'is_builtin': False, 'config_json': {}, 'custom_rules': [], 'config_schema': []}, {'id': 'audit-second', 'name': 'Audit Second Stage', 'description': 'Synthetic second', 'icon': 'Sliders', 'stage_type': 'custom', 'priority_order': 20, 'enabled': True, 'is_builtin': False, 'config_json': {}, 'custom_rules': [], 'config_schema': []}]
    js("__audit.fixtures['/api/admin/compression/stages']=" + json.dumps(stages))
    nav(8)
    js("__audit.fail={path:'/api/admin/compression/stages/reorder',method:'PUT',status:503};document.querySelector('main button[title=\"Опустить ниже\"]').click()")
    time.sleep(.3)
    body = text()
    assert 'AUDIT_CONTROLLED_FAILURE' in body
    assert body.index('Audit Custom Stage') < body.index('Audit Second Stage')
    assert js("__audit.requests.some(r=>r.path.endsWith('/stages/reorder')&&r.status===503)")
    js('__audit.fail=null')
    save(54, ['main button[title="Опустить ниже"]'], {'rollback_order': True, 'mutation_error_visible': True})

    # 59: actual log Inspector action, no reload, replay payload consumed.
    log = json.loads((AUDIT / 'log-fixture.json').read_text())
    log['prompt_content'] = 'AUDIT_REPLAY_PROMPT'
    js("__audit.fixtures['/api/admin/logs']=" + json.dumps([log]))
    nav(2)
    js("window.__replaySentinel=true;document.querySelector('main tbody tr').click()")
    time.sleep(.15)
    click('Replay in Playground')
    time.sleep(.3)
    assert 'Interactive Playground' in text()
    assert js('window.__replaySentinel') is True
    assert js("sessionStorage.getItem('replay_log_data')") is None
    assert log['prompt_content'] in js(r"Array.from(document.querySelectorAll('main textarea')).map(t=>t.value).join('\n')")
    click('Send')
    replay_request = js("__audit.requests.filter(r=>r.path==='/v1/chat/completions').at(-1).body")
    assert replay_request['model'] == log['requested_model']
    assert replay_request['messages'][-1]['content'] == log['prompt_content']
    save(59, ['main tbody tr', 'button: Replay in Playground', 'main textarea'], {'playground_mounted': True, 'no_reload': True, 'payload_consumed': True, 'prompt_restored': True})


def run_navigation():
    # 14: mobile content/header fits; native dialog traps focus and Escape restores.
    nav(14)
    cdp('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=1, mobile=False)
    time.sleep(.15)
    rects = js("({main:document.querySelector('main').getBoundingClientRect().toJSON(),buttons:[...document.querySelectorAll('header button')].filter(b=>b.getBoundingClientRect().width).map(b=>b.getBoundingClientRect().toJSON()),sidebar_hidden:getComputedStyle(document.querySelector('aside').parentElement).display==='none'})")
    assert rects['main']['width'] >= 380 and rects['sidebar_hidden'], rects
    assert all(b['left'] >= 0 and b['right'] <= 390 for b in rects['buttons']), rects
    js("document.querySelector('button[aria-label=\"Open navigation\"]').focus()")
    cdp('Page.bringToFront')
    cdp('Input.dispatchKeyEvent', type='rawKeyDown', key='Enter', code='Enter', windowsVirtualKeyCode=13)
    cdp('Input.dispatchKeyEvent', type='char', text='\r', key='Enter', code='Enter', windowsVirtualKeyCode=13)
    cdp('Input.dispatchKeyEvent', type='keyUp', key='Enter', code='Enter', windowsVirtualKeyCode=13)
    time.sleep(.15)
    assert js("document.querySelector('dialog').open && document.querySelector('dialog').contains(document.activeElement)")
    for _ in range(22):
        cdp('Input.dispatchKeyEvent', type='keyDown', key='Tab', code='Tab', windowsVirtualKeyCode=9)
        cdp('Input.dispatchKeyEvent', type='keyUp', key='Tab', code='Tab', windowsVirtualKeyCode=9)
        assert js("document.querySelector('dialog').contains(document.activeElement) || document.activeElement===document.body")
    cdp('Input.dispatchKeyEvent', type='keyDown', key='Escape', code='Escape', windowsVirtualKeyCode=27)
    cdp('Input.dispatchKeyEvent', type='keyUp', key='Escape', code='Escape', windowsVirtualKeyCode=27)
    time.sleep(.15)
    assert js("!document.querySelector('dialog').open && document.activeElement.getAttribute('aria-label')==='Open navigation'")
    js("document.querySelector('button[aria-label=\"Open navigation\"]').click()")
    time.sleep(.1)
    js("document.querySelectorAll('dialog aside nav button')[3].click()")
    time.sleep(.2)
    assert not js("document.querySelector('dialog').open")
    assert 'Interactive Playground' in text()
    save(14, ['header button', 'main', 'button[aria-label="Open navigation"]', 'dialog aside nav button'], {'viewport': 390, 'main_width': rects['main']['width'], 'header_buttons_inside_viewport': True, 'focus_contained': True, 'escape_restores_focus': True, 'navigation_closes_drawer': True})
    cdp('Emulation.clearDeviceMetricsOverride')

    # 89: switch actual language controls; Sidebar and header use same English fallback.
    results = []
    for lang, name in [('zh', '中文 (简体)'), ('hi', 'हिन्दी'), ('es', 'Español'), ('fr', 'Français'), ('ar', 'العربية'), ('bn', 'বাংলা'), ('pt', 'Português'), ('ja', '日本語'), ('de', 'Deutsch'), ('uk', 'Українська'), ('be', 'Беларуская')]:
        nav(14)
        assert js("(()=>{let b=[...document.querySelectorAll('main button')].find(b=>b.innerText.includes(" + json.dumps(name) + "));if(!b)return false;b.click();return true})()"), name
        time.sleep(.12)
        assert js('document.documentElement.lang') == lang
        for idx, expected in [(6, 'Judge Router'), (8, 'Token Compression'), (10, 'Modules')]:
            label = js(f"document.querySelectorAll('aside nav button')[{idx}].innerText")
            assert expected in label and 'Судейская' not in label and 'Оптимизация' not in label, (lang, label)
            nav(idx)
            assert expected in js('document.querySelector("header").innerText'), (lang, expected)
        results.append({'lang': lang, 'dir': js('document.documentElement.dir'), 'labels_match_header': True})
    nav(14)
    js("[...document.querySelectorAll('main button')].find(b=>b.innerText.includes('English')).click()")
    time.sleep(.15)
    save(89, ['main button: language', 'aside nav button (6,8,10)', 'header'], {'locales': results, 'count': len(results)})


def run_auth():
    # 55: common API 401 replaces authenticated App, not just a hash change.
    js("__audit.fail={path:'/api/admin/proxies',method:'GET',status:401}")
    nav(13)
    assert js("localStorage.getItem('myairouter_token')") is None
    assert js('document.querySelector("aside")') is None
    assert 'Add Proxy' not in text() and 'synthetic-audit' not in text()
    assert js('document.querySelector("form")!==null')
    # Normal rejected login should remain on LoginPage and report its own error.
    js("__audit.fail={path:'/api/admin/auth/login',method:'POST',status:401};window.__expiryEvents=0;window.addEventListener('myairouter:session-expired',()=>__expiryEvents++)")
    # Test the common client response through the real LoginPage form submission,
    # without entering any credential: submit the empty form event directly.
    js("document.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
    time.sleep(.2)
    assert js('__expiryEvents') == 0
    assert 'AUDIT_CONTROLLED_FAILURE' in text()
    save(55, ['aside (must unmount)', 'LoginPage form'], {'admin_ui_unmounted': True, 'token_removed': True, 'normal_login_401_not_expiry': True})
    resources = js("performance.getEntriesByType('resource').filter(r=>r.initiatorType==='fetch'||r.initiatorType==='xmlhttprequest').map(r=>r.name)")
    assert not resources, resources
    assert not js("__audit.requests.some(r=>r.path.includes('agy')||r.path.includes('antigravity'))")
    print('ISOLATION: zero real fetch/XHR resources; no excluded-module requests')
