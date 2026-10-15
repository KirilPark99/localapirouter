// Run: node check_runtime.mjs [workers-checkout]. All accounts and traffic are synthetic.
import assert from 'node:assert/strict';
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const source = path.resolve(process.argv[2] || '/home/kiril/PythonProjects/freebuff2api-wokers');
const scratch = process.env.TMPDIR || '/home/kiril/.hermes/cache/scratch';
fs.mkdirSync(scratch, { recursive: true });
const tmp = fs.mkdtempSync(path.join(scratch, 'freebuff-runtime-check-'));
const children = [], servers = [], sockets = new Set(), seen = [], tunnels = [], closed = new Set();
let statusReply, loginMode = 'done', sessionRefusal;
const user = { id: 'synthetic-user', email: 'fixture@example.invalid', authToken: 'synthetic-token-not-real' };
function reply(res, value, status = 200) { res.writeHead(status, { 'content-type': 'application/json' }); res.end(JSON.stringify(value)); }
const chunk = (delta, finish_reason = null) => `data: ${JSON.stringify({ data: { id: 'fixture-completion', model: 'mimo/mimo-v2.5', choices: [{ index: 0, delta, finish_reason }] } })}\n\n`;
async function fixture(req, res) {
  let text = ''; for await (const part of req) text += part;
  const url = new URL(req.url, 'https://fixture.invalid');
  const body = text ? JSON.parse(text) : {};
  seen.push({ route: url.pathname, method: req.method, body, authorization: req.headers.authorization, query: url.searchParams });
  if (url.pathname.endsWith('free-agents.ts')) return res.end("export const FREEBUFF_ROOT_AGENT_ID_BY_MODEL = { [FREEBUFF_FIXTURE_MODEL_ID]: 'fixture-agent', [FREEBUFF_LEGACY_MODEL_ID]: 'legacy-agent', [FREEBUFF_SOLAR_FIXTURE_MODEL_ID]: 'entitlement-agent', [FREEBUFF_DEEPSEEK_FIXTURE_MODEL_ID]: 'flash-agent' }; // synthetic mappings");
  if (url.pathname.endsWith('freebuff-model-entitlements.ts')) return res.end(`
    export const FREEBUFF_SOLAR_FIXTURE_ENTITLEMENT = { modelId: 'fixture/entitlement-model' } as const;
    export const FREEBUFF_SOLAR_FIXTURE_MODEL_ID = FREEBUFF_SOLAR_FIXTURE_ENTITLEMENT.modelId;
  `);
  if (url.pathname.endsWith('.ts')) return res.end(`
    export const FREEBUFF_FIXTURE_MODEL_ID = 'fixture/offline-model';
    export const FREEBUFF_LEGACY_MODEL_ID = 'fixture/legacy-model';
    export const FREEBUFF_DEEPSEEK_FIXTURE_MODEL_ID = 'deepseek/deepseek-v4-flash';
const FIXTURE_MODEL = {
      id: FREEBUFF_FIXTURE_MODEL_ID,
      displayName: 'Fixture v2 Current',
      premium: false,
      newBadge: { tooltip: 'Nested metadata must not hide a model' },
} as const;
const ENTITLEMENT_MODEL = {
      id: FREEBUFF_SOLAR_FIXTURE_MODEL_ID,
      displayName: 'Entitlement Current',
      premium: false,
} as const;
const FLASH_MODEL = {
      id: FREEBUFF_DEEPSEEK_FIXTURE_MODEL_ID,
      displayName: 'DeepSeek V4.1 Flash',
      premium: false,
} as const;
const LEGACY_MODEL = {
      id: FREEBUFF_LEGACY_MODEL_ID,
      premium: true,
} as const;
    export const FIXTURE_DISABLED_IN_UI = false;
    export const FREEBUFF_MODELS = [
      FIXTURE_MODEL,
      ENTITLEMENT_MODEL,
      FLASH_MODEL,
      // LEGACY_MODEL stays routable but is not advertised.
      ...(FIXTURE_DISABLED_IN_UI ? [LEGACY_MODEL] : []),
    ] as const;
    export const FREEBUFF_PREMIUM_MODEL_IDS = [] as const;
  `);
  if (url.pathname.endsWith('/freebuff-models.json')) return reply(res, { models: [{ id: 'fixture/offline-model', session: 'fixture/offline-model', agent: 'fixture-agent', upstream: 'fixture/offline-model' }], pools: { premium: [], glm: [] } });
  if (url.pathname === '/api/auth/cli/code') {
    assert.match(body.fingerprintId, /^runtime-/);
    return reply(res, { loginUrl: 'https://www.codebuff.com/login?fixture=1', fingerprintHash: 'private-fixture-hash', expiresAt: Date.now() + (loginMode === 'expire' ? 1000 : 300000) });
  }
  if (url.pathname === '/api/auth/cli/status') {
    assert.equal(url.searchParams.get('fingerprintHash'), 'private-fixture-hash');
    if (loginMode === 'hold') { statusReply = res; return; }
    return reply(res, { user: { ...user, id: 'login-user', email: 'login@example.invalid', authToken: loginMode === 'rotate' ? 'rotated-fixture-token' : 'login-synthetic-token' } });
  }
  assert.equal(req.headers.authorization, `Bearer ${user.authToken}`);
  if (url.pathname === '/api/v1/freebuff/session') return sessionRefusal ? reply(res, sessionRefusal, 403) : reply(res, { status: 'active', model: 'mimo/mimo-v2.5', instanceId: 'synthetic-instance', expiresAt: new Date(Date.now() + 3600000).toISOString() });
  if (url.pathname === '/api/v1/agent-runs') return reply(res, { runId: randomUUID() });
  if (url.pathname === '/api/v1/chat/completions') {
    const name = body.messages.find(m => m.role === 'user').content;
    assert.equal(body.stream, true);
    assert.equal(body.codebuff_metadata.cost_mode, 'free');
    if (name === 'update') return reply(res, { error: 'freebuff_update_required', message: 'secret must not escape' }, 410);
    res.writeHead(200, { 'content-type': 'text/event-stream' }); res.flushHeaders();
    res.on('close', () => closed.add(name));
    if (name === 'early') return;
    res.write(chunk({ content: 'fixture answer' }));
    if (name === 'cancel') return;
    if (name === 'truncated') { setTimeout(() => res.end(), 50); return; }
    if (name === 'no-finish') { res.end('data: [DONE]\n\n'); return; }
    if (body.tools) {
      assert.equal(body.tools[0].function.name, 'mcp__fixture_tool');
      res.write(chunk({ tool_calls: [{ index: 0, id: 'fixture-call', function: { name: 'mcp__fixture_tool', arguments: '{"ok":true}' } }] }));
    }
    res.write(chunk({}, body.tools ? 'tool_calls' : 'stop'));
    res.end('data: {"data":{"choices":[],"usage":{"prompt_tokens":2,"completion_tokens":3,"total_tokens":5}}}\n\ndata: [DONE]\n\n');
    return;
  }
  reply(res, { error: 'unexpected fixture route' }, 404);
}
async function listen(server) {
  servers.push(server);
  server.on('connection', socket => { sockets.add(socket); socket.on('close', () => sockets.delete(socket)); });
  server.listen(0, '127.0.0.1'); await once(server, 'listening'); return server.address().port;
}
async function until(fn, message, timeout = 15000) {
  const end = Date.now() + timeout;
  while (!fn()) { assert.ok(Date.now() < end, message); await new Promise(r => setTimeout(r, 20)); }
}
const key = 'synthetic-loopback-key-no-secrets';
let output = '', errors = '';
async function start(root, proxy, apiBase, accounts = [user]) {
  // Deny DNS and raw socket paths to non-loopback, even if a future bridge accidentally bypasses its proxy.
  const guard = `import net from 'node:net'; import dns from 'node:dns'; import {syncBuiltinESMExports} from 'node:module';
    const original = net.Socket.prototype.connect;
    net.Socket.prototype.connect = function(...args) {
      const a = Array.isArray(args[0]) ? args[0] : args;
      const o = typeof a[0] === 'object' ? a[0] : {host: typeof a[1] === 'string' ? a[1] : 'localhost'};
      if (o.host && !['127.0.0.1','localhost','::1'].includes(o.host)) throw Error('External socket blocked by verifier');
      return original.apply(this,args);
    };
    const lookup = dns.lookup;
    dns.lookup = function(host,...args) { if (!['127.0.0.1','localhost','::1'].includes(host)) throw Error('External DNS blocked by verifier'); return lookup.call(this,host,...args); }; syncBuiltinESMExports();`;
  const child = spawn(process.execPath, ['--import', 'data:text/javascript,' + encodeURIComponent(guard), path.join(path.dirname(fileURLToPath(import.meta.url)), 'runtime.mjs')], {
    env: { ...process.env, NODE_EXTRA_CA_CERTS: path.join(tmp, 'cert.pem'), HTTP_PROXY: 'http://127.0.0.1:1', HTTPS_PROXY: 'http://127.0.0.1:1', ALL_PROXY: 'http://127.0.0.1:1' }, stdio: ['pipe', 'pipe', 'pipe'],
  });
  children.push(child);
  let stdout = ''; child.stdout.on('data', c => { stdout += c; output += c; }); child.stderr.on('data', c => { errors += c; });
  child.stdin.write(JSON.stringify({ source, root, token: key, proxy, apiBase, accounts }) + '\n');
  await until(() => stdout.includes('\n') || child.exitCode !== null, 'runtime startup');
  assert.equal(child.exitCode, null, errors);
  const info = JSON.parse(stdout.trim()); assert.equal(info.msg, 'freebuff2api listening');
  return { child, base: `http://127.0.0.1:${info.port}` };
}
try {
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', path.join(tmp, 'key.pem'), '-out', path.join(tmp, 'cert.pem'), '-days', '1', '-subj', '/CN=offline fixture', '-addext', 'subjectAltName=DNS:raw.githubusercontent.com,DNS:cdn.jsdelivr.net,DNS:github.com'], { stdio: 'ignore' });
  const apiPort = await listen(http.createServer((req, res) => fixture(req, res).catch(e => { console.error(e); res.destroy(); })));
  const tlsPort = await listen(https.createServer({ key: fs.readFileSync(path.join(tmp, 'key.pem')), cert: fs.readFileSync(path.join(tmp, 'cert.pem')) }, (req, res) => fixture(req, res).catch(e => { console.error(e); res.destroy(); })));
  const proxyServer = http.createServer((req, res) => {
    const target = new URL(req.url);
    assert.equal(target.origin, `http://127.0.0.1:${apiPort}`, 'HTTP proxy must not forward externally');
    tunnels.push(target.host);
    const upstream = http.request(target, { method: req.method, headers: req.headers }, response => {
      res.writeHead(response.statusCode, response.headers); response.pipe(res);
    });
    upstream.on('error', () => res.destroy());
    res.on('close', () => upstream.destroy());
    req.pipe(upstream);
  });
  proxyServer.on('connect', (req, client, head) => {
    tunnels.push(req.url);
    const allowed = req.url === `127.0.0.1:${apiPort}`;
    assert.ok(allowed || ['raw.githubusercontent.com:443', 'cdn.jsdelivr.net:443', 'github.com:443'].includes(req.url), 'Unexpected outbound target');
    const socket = net.connect(allowed ? apiPort : tlsPort, '127.0.0.1', () => { client.write('HTTP/1.1 200 Connection Established\r\n\r\n'); if (head.length) socket.write(head); client.pipe(socket); socket.pipe(client); });
    sockets.add(socket); socket.on('close', () => sockets.delete(socket));
    socket.on('error', () => client.destroy()); client.on('error', () => socket.destroy()); client.on('close', () => socket.destroy());
  });
  const proxyPort = await listen(proxyServer);
  const root = path.join(tmp, 'profile');
  const runtime = await start(root, `http://127.0.0.1:${proxyPort}`, `http://127.0.0.1:${apiPort}`);
  async function call(route, method = 'GET', body, base = runtime.base) {
    return fetch(base + route, { method, headers: { authorization: `Bearer ${key}`, 'content-type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(30000) });
  }
  for (const route of ['/healthz', '/v1/freebuff/status', '/v1/models', '/api/accounts/login', '/api/accounts/refresh']) assert.equal((await fetch(runtime.base + route)).status, 401);
  assert.equal((await call('/healthz')).status, 200);
  assert.equal((await call('/api/accounts/refresh', 'POST')).status, 200);
  assert.equal(seen.length, 0, 'startup and management must stay offline');
  const models = await (await call('/v1/models')).json();
  assert.deepEqual(models.data.map(m => m.id).sort(), ['deepseek/deepseek-v4-flash', 'fixture/entitlement-model', 'fixture/offline-model', 'mimo/mimo-v2.5'],
    'Discovery must exclude legacy/God-mode agent mappings outside the current picker');
  assert.equal(models.data.find(m => m.id === 'fixture/offline-model').display_name, 'Fixture v2 Current');
  assert.equal(models.data.find(m => m.id === 'deepseek/deepseek-v4-flash').display_name, 'DeepSeek V4.1 Flash', 'Keep legacy wire ID, expose current label');
  assert.ok(tunnels.includes('raw.githubusercontent.com:443'));
  const payload = name => ({ model: 'mimo/mimo-v2.5', messages: [{ role: 'user', content: name }] });
  const result = await (await call('/v1/chat/completions', 'POST', payload('json'))).json();
  assert.ok(result.choices, JSON.stringify({ result, seen, tunnels, errors }));
  assert.equal(result.choices[0].message.content, 'fixture answer'); assert.equal(result.usage.total_tokens, 5);
  const tools = [{ type: 'function', function: { name: 'fixture_tool', parameters: { type: 'object' } } }];
  const toolResult = await (await call('/v1/chat/completions', 'POST', { ...payload('tools'), tools })).json();
  assert.equal(toolResult.choices[0].message.tool_calls[0].function.name, 'fixture_tool');
  const sse = await (await call('/v1/chat/completions', 'POST', { ...payload('stream'), stream: true })).text();
  assert.ok(sse.includes('fixture answer') && sse.includes('[DONE]'));
  for (const name of ['cancel', 'early']) {
    const before = seen.filter(s => s.route === '/api/v1/chat/completions').length;
    const req = http.request(runtime.base + '/v1/chat/completions', { method: 'POST', headers: { authorization: `Bearer ${key}`, 'content-type': 'application/json' } });
    req.on('error', () => {});
    let receivedData = false;
    req.on('response', res => res.once('data', () => { receivedData = true; }));
    req.end(JSON.stringify({ ...payload(name), stream: true }));
    await until(() => seen.filter(s => s.route === '/api/v1/chat/completions').length > before, 'upstream chat must start');
    if (name === 'cancel') await until(() => receivedData, 'partial stream must arrive');
    req.destroy();
    await until(() => closed.has(name), 'disconnect must close exact upstream');
    const next = await (await call('/v1/chat/completions', 'POST', payload('following'))).json();
    assert.equal(next.choices[0].message.content, 'fixture answer');
  }
  const truncated = await (await call('/v1/chat/completions', 'POST', { ...payload('truncated'), stream: true })).text();
  assert.ok(!truncated.includes('[DONE]') && truncated.includes('incomplete_stream'));
  assert.equal(seen.filter(s => s.body.messages?.some(m => m.content === 'truncated')).length, 1, 'no generation replay after partial');
  const truncatedJSON = await call('/v1/chat/completions', 'POST', payload('truncated'));
  assert.equal(truncatedJSON.status, 502, 'truncated aggregation must fail');
  const noFinish = await call('/v1/chat/completions', 'POST', payload('no-finish'));
  assert.equal(noFinish.status, 502, 'DONE without a finish reason must not become fabricated success');
  assert.equal(seen.filter(s => s.body.messages?.some(m => m.content === 'truncated')).length, 2, 'one call per client request');
  const update = await call('/v1/chat/completions', 'POST', payload('update'));
  assert.equal(update.status, 410); assert.equal((await update.json()).error.code, 'freebuff_update_required');
  for (const [index, refusal] of [
    { status: 'banned', verificationReason: 'region_locked', pickerCountryCode: 'UA', message: 'secret must not escape' },
    { status: 'country_blocked', message: 'secret must not escape' },
    { status: 'banned', message: 'secret must not escape' },
  ].entries()) {
    sessionRefusal = refusal;
    const blocked = await start(path.join(tmp, 'blocked-' + index), `http://127.0.0.1:${proxyPort}`, `http://127.0.0.1:${apiPort}`);
    const before = seen.length;
    const denied = await call('/v1/chat/completions', 'POST', payload('blocked'), blocked.base);
    assert.equal(denied.status, 403, 'terminal account/region refusal must not become 502');
    const denial = await denied.json();
    assert.equal(denial.error.code, 'freebuff_access_blocked');
    assert.equal(denial.error.reason, refusal.verificationReason === 'region_locked' ? 'region_locked' : refusal.status);
    assert.ok(!JSON.stringify(denial).includes('secret must not escape'));
    const dispatched = seen.slice(before).filter(r => r.route.startsWith('/api/'));
    assert.deepEqual(dispatched.map(r => [r.method, r.route]), [['GET', '/api/v1/freebuff/session']], 'no admission, inference or retry after terminal rejection');
    blocked.child.stdin.end(); await once(blocked.child, 'exit');
  }
  sessionRefusal = undefined;
  const flow = (await (await call('/api/accounts/login', 'POST')).json()).flow;
  assert.equal(flow.status, 'pending'); assert.ok(!JSON.stringify(flow).includes('private-fixture-hash'));
  assert.equal((await (await call('/api/accounts/login/' + flow.id)).json()).flow.status, 'done');
  const count = fs.readdirSync(path.join(root, 'data/credentials')).length;
  loginMode = 'hold';
  const cancelFlow = (await (await call('/api/accounts/login', 'POST')).json()).flow;
  const pending = call('/api/accounts/login/' + cancelFlow.id);
  await until(() => statusReply, 'login poll started');
  assert.equal((await (await call('/api/accounts/login/' + cancelFlow.id + '/cancel', 'POST')).json()).flow.status, 'cancelled');
  reply(statusReply, { user: { id: 'late-user', authToken: 'late-synthetic-token' } }); statusReply = null;
  assert.equal((await (await pending).json()).flow.status, 'cancelled');
  assert.equal(fs.readdirSync(path.join(root, 'data/credentials')).length, count);
  loginMode = 'expire';
  const expiredFlow = (await (await call('/api/accounts/login', 'POST')).json()).flow;
  loginMode = 'hold';
  const expiring = call('/api/accounts/login/' + expiredFlow.id);
  await until(() => statusReply, 'expiry poll started');
  await new Promise(resolve => setTimeout(resolve, 1100));
  reply(statusReply, { user: { id: 'expired-user', authToken: 'expired-synthetic-token' } }); statusReply = null;
  assert.equal((await (await expiring).json()).flow.status, 'expired');
  assert.equal(fs.readdirSync(path.join(root, 'data/credentials')).length, count, 'late expired login must not save');
  loginMode = 'rotate';
  const rotating = (await (await call('/api/accounts/login', 'POST')).json()).flow;
  assert.equal((await (await call('/api/accounts/login/' + rotating.id)).json()).flow.status, 'done');
  const savedAccounts = fs.readdirSync(path.join(root, 'data/credentials')).map(file =>
    JSON.parse(fs.readFileSync(path.join(root, 'data/credentials', file), 'utf8')));
  assert.ok(savedAccounts.some(account => account.id === 'login-user' && account.authToken === 'rotated-fixture-token'), 'Re-login must replace the same account token, not silently retain the old token');
  assert.equal(savedAccounts.length, count, 'Re-login does not add a duplicate identity');
  const publicStatus = JSON.stringify(await (await call('/v1/freebuff/status')).json());
  assert.ok(!publicStatus.includes('authToken') && !publicStatus.includes(user.authToken));
  for (const file of fs.readdirSync(path.join(root, 'data/credentials'))) assert.equal(fs.statSync(path.join(root, 'data/credentials', file)).mode & 0o777, 0o600);
  runtime.child.stdin.end(); await until(() => runtime.child.exitCode !== null, 'EOF must stop runtime');
  assert.equal(runtime.child.exitCode, 0);
  const restarted = await start(root, `http://127.0.0.1:${proxyPort}`, `http://127.0.0.1:${apiPort}`);
  assert.equal((await (await call('/api/accounts/login/' + cancelFlow.id, 'GET', undefined, restarted.base)).json()).flow.status, 'cancelled');
  assert.equal(fs.readdirSync(path.join(root, 'data/credentials')).length, count, 'bootstrap is additive');
  restarted.child.stdin.end(); await once(restarted.child, 'exit');
  const direct = await start(path.join(tmp, 'direct'), null, `http://127.0.0.1:${apiPort}`);
  const tunnelCount = tunnels.length;
  assert.equal((await call('/v1/chat/completions', 'POST', payload('direct'), direct.base)).status, 200);
  assert.equal(tunnels.length, tunnelCount, 'null proxy ignores inherited proxy');
  direct.child.stdin.end(); await once(direct.child, 'exit');
  assert.ok(!output.includes(user.authToken) && !errors.includes(user.authToken));
  const invalid = spawn(process.execPath, [path.join(path.dirname(fileURLToPath(import.meta.url)), 'runtime.mjs')], { stdio: ['pipe', 'pipe', 'pipe'] });
  children.push(invalid);
  let invalidOut = '';
  invalid.stdout.on('data', data => { invalidOut += data; }); invalid.stderr.resume();
  const beforeInvalid = seen.length;
  invalid.stdin.write(JSON.stringify({ source, root: path.join(tmp, 'invalid'), token: key, proxy: 'socks5://127.0.0.1:1', accounts: [user] }) + '\n');
  await until(() => invalid.exitCode !== null, 'invalid proxy must fail closed');
  assert.equal(invalid.exitCode, 1); assert.equal(invalidOut, ''); assert.equal(seen.length, beforeInvalid);
  assert.equal(fs.statSync(root).mode & 0o777, 0o700);
  assert.equal(fs.statSync(path.join(root, 'data/login-flows.json')).mode & 0o777, 0o600);
  console.log('PASS: real worker JSON/SSE/tools; pinned proxy/catalog; direct mode; disconnect cancellation; terminal guard; safe 410; auth; login cancellation/persistence; private credentials; EOF shutdown.');
} finally {
  for (const child of children) if (child.exitCode === null) child.kill('SIGKILL');
  for (const socket of sockets) socket.destroy();
  for (const server of servers) server.close();
  fs.rmSync(tmp, { recursive: true, force: true });
}
