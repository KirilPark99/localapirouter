// Managed transport only: upstream protocol and client tool calls stay in worker.js.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { randomUUID, createHash, timingSafeEqual } from 'node:crypto';
import { AsyncLocalStorage } from 'node:async_hooks';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import readline from 'node:readline';

process.umask(0o077);
for (const key of ['log', 'info', 'warn', 'error', 'debug', 'trace']) console[key] = () => {};
let server, dispatcher;
const active = new Set();
function stop() {
  for (const controller of active) controller.abort();
  server?.close();
  server?.closeAllConnections();
  dispatcher?.destroy();
  process.exit(0);
}
process.on('SIGTERM', stop);
process.on('SIGINT', stop);
const lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
lines.on('close', stop);
const configLine = await new Promise(resolve => lines.once('line', resolve));
try {
  const cfg = JSON.parse(configLine);
  if (typeof cfg.source !== 'string' || !path.isAbsolute(cfg.source) ||
      typeof cfg.root !== 'string' || !path.isAbsolute(cfg.root) ||
      typeof cfg.token !== 'string' || cfg.token.length < 16 || /[\s\x00-\x1f]/.test(cfg.token)) throw Error();
  function origin(value) {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || !url.hostname ||
        url.search || url.hash || !['', '/'].includes(url.pathname) || /[\s\x00-\x1f]/.test(value)) throw Error();
    return url;
  }
  const apiBase = origin(cfg.apiBase || 'https://www.codebuff.com');
  if (apiBase.username || apiBase.password) throw Error();
  if (cfg.proxy !== null && typeof cfg.proxy !== 'string') throw Error();
  const proxy = cfg.proxy === null ? null : origin(cfg.proxy);
  const { Agent, ProxyAgent, fetch } = createRequire(path.join(cfg.source, 'package.json'))('undici');
  dispatcher = proxy ? new ProxyAgent(proxy.href) : new Agent();
  const context = new AsyncLocalStorage();
  function transportEvidence(record) {
    try {
      fs.appendFileSync(path.join(cfg.root, 'transport-errors.jsonl'), JSON.stringify({ ...record,
        time: new Date().toISOString() }) + '\n', { mode: 0o600 });
    } catch { /* Evidence failure must not replace the actual upstream refusal. */ }
  }
  async function outbound(input, init = {}) {
    const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url);
    const providerRequest = url.origin === 'https://www.codebuff.com';
    if (providerRequest) {
      url.protocol = apiBase.protocol;
      url.host = apiBase.host;
    }
    const signals = [context.getStore()?.signal, init.signal, input?.signal].filter(Boolean);
    const signal = signals.length ? AbortSignal.any(signals) : undefined;
    signal?.throwIfAborted();
    if (context.getStore()?.streamFailure || context.getStore()?.updateRequired ||
        providerRequest && context.getStore()?.accessBlocked) throw Error('Upstream request cannot be replayed');
    let response;
    try { response = await fetch(url, { ...init, dispatcher, signal, redirect: providerRequest ? 'error' : 'follow' }); }
    catch (error) {
      if (providerRequest && context.getStore() && !signal?.aborted) transportEvidence({ stage: url.pathname,
        error_type: error.name, cause_code: /^[A-Z_0-9]+$/.test(error.cause?.code || '') ? error.cause.code : null });
      throw error;
    }
    const requestContext = context.getStore();
    if (requestContext && providerRequest && !response.ok) {
      // Owner-only evidence: never put upstream text or credentials into public errors/logs.
      const raw = await response.clone().text();
      let safe = raw;
      const authorization = new Headers(init.headers).get('authorization');
      if (authorization) safe = safe.split(authorization.replace(/^Bearer /, '')).join('[TOKEN]');
      safe = safe.replace(/https?:\/\/\S+/g, '[URL]').replace(/[\w.+-]+@[\w.-]+/g, '[EMAIL]')
        .replace(/\b[A-Za-z0-9_+/=-]{50,}\b/g, '[LONG_TOKEN]');
      transportEvidence({ status: response.status, stage: url.pathname, body: safe.slice(0, 2000) });
    }
    if (requestContext && providerRequest && response.status === 403 && url.pathname.startsWith('/api/v1/freebuff/')) {
      const rejection = await response.clone().json().catch(() => null);
      if (['banned', 'country_blocked'].includes(rejection?.status)) {
        // A terminal account/region refusal is not a retryable worker failure.
        requestContext.accessBlocked = rejection.verificationReason === 'region_locked' ? 'region_locked' : rejection.status;
      }
    }
    if (requestContext && response.status === 410) {
      const rejection = await response.clone().json().catch(() => null);
      const isUpdate = value => value === 'freebuff_update_required' || value && typeof value === 'object' && Object.values(value).some(isUpdate);
      if (isUpdate(rejection)) requestContext.updateRequired = true;
    }
    if (url.pathname === '/api/v1/chat/completions' && requestContext) {
      if (response.ok && response.body) {
        let buffer = '', terminal = false, finished = false;
        const decoder = new TextDecoder();
        const guarded = response.body.pipeThrough(new TransformStream({
          transform(chunk, controller) {
            buffer += decoder.decode(chunk, { stream: true });
            let end;
            while ((end = buffer.indexOf('\n')) >= 0) {
              const line = buffer.slice(0, end).trim();
              if (line.startsWith('data:')) {
                const payload = line.slice(5).trim();
                if (payload === '[DONE]') {
                  if (!finished) { requestContext.streamFailure = true; throw Error('Missing upstream finish reason'); }
                  terminal = true;
                } else if (payload) {
                  const event = JSON.parse(payload);
                  const frame = event.data && typeof event.data === 'object' ? event.data : event;
                  if (frame.error) { requestContext.streamFailure = true; throw Error('Upstream stream error'); }
                  finished ||= frame.choices?.some(choice => typeof choice.finish_reason === 'string' && choice.finish_reason.length > 0) || false;
                }
              }
              buffer = buffer.slice(end + 1);
            }
            controller.enqueue(chunk);
          },
          flush() {
            if (!terminal) { requestContext.streamFailure = true; throw Error('Incomplete upstream stream'); }
          },
        }));
        // Preserve transport errors even when stock worker catches its reader error.
        const reader = guarded.getReader();
        const body = new ReadableStream({
          async pull(controller) {
            try { const next = await reader.read(); if (next.done) controller.close(); else controller.enqueue(next.value); }
            catch (error) { requestContext.streamFailure = true; controller.error(error); }
          },
          cancel(reason) { return reader.cancel(reason); },
        });
        return new Response(body, { status: response.status, headers: response.headers });
      }
    }
    return response;
  }
  globalThis.fetch = outbound;
  const { default: worker, setOutboundFetch } = await import(pathToFileURL(path.join(cfg.source, 'worker.js')));
  setOutboundFetch(outbound);
  const data = path.join(cfg.root, 'data');
  const credentials = path.join(data, 'credentials');
  for (const dir of [cfg.root, data, credentials]) {
    if (fs.existsSync(dir) && (!fs.lstatSync(dir).isDirectory() || fs.lstatSync(dir).isSymbolicLink())) throw Error();
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
    fs.chmodSync(dir, 0o700);
  }
  function read(file, fallback) {
    try {
      if (!fs.lstatSync(file).isFile() || fs.lstatSync(file).isSymbolicLink()) throw Error();
      return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch (error) { if (error.code === 'ENOENT') return fallback; throw error; }
  }
  function write(file, value, additive = false) {
    const tmp = `${file}.${randomUUID()}.tmp`;
    try {
      fs.writeFileSync(tmp, JSON.stringify(value), { mode: 0o600, flag: 'wx' });
      if (additive) fs.linkSync(tmp, file); else fs.renameSync(tmp, file);
    } finally { if (fs.existsSync(tmp)) fs.unlinkSync(tmp); }
  }
  function validAccount(user) {
    return user && typeof user.authToken === 'string' && user.authToken.length > 8 &&
      !/[\s,:\x00-\x1f]/.test(user.authToken) &&
      (user.id == null || typeof user.id === 'string' && !/[\s,:\x00-\x1f]/.test(user.id));
  }
  const accounts = [];
  const accountFiles = new WeakMap();
  for (const name of fs.readdirSync(credentials).filter(name => name.endsWith('.json'))) {
    const user = read(path.join(credentials, name));
    if (!validAccount(user)) throw Error();
    if (!accounts.some(a => a.authToken === user.authToken || user.id && a.id === user.id)) {
      accounts.push(user); accountFiles.set(user, path.join(credentials, name));
    }
  }
  function saveAccount(user, replace = false) {
    if (!validAccount(user)) throw Error();
    const index = accounts.findIndex(a => a.authToken === user.authToken || user.id && a.id === user.id || user.email && a.email === user.email);
    if (index !== -1) {
      if (!replace) return;
      const current = accounts[index], file = accountFiles.get(current);
      const updated = { ...current, ...user };
      write(file, updated);
      accounts[index] = updated; accountFiles.set(updated, file);
      return;
    }
    const key = createHash('sha256').update(user.id || user.authToken).digest('hex');
    const file = path.join(credentials, `${key}.json`);
    write(file, user, true);
    accounts.push(user); accountFiles.set(user, file);
  }
  if (cfg.accounts !== undefined && !Array.isArray(cfg.accounts)) throw Error();
  for (const user of cfg.accounts || []) saveAccount(user);
  const flowFile = path.join(data, 'login-flows.json');
  const flowState = read(flowFile, { version: 1, flows: [] });
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  function loginURL(value) {
    const u = new URL(value);
    if (u.protocol !== 'https:' || !['freebuff.com', 'www.freebuff.com', 'codebuff.com', 'www.codebuff.com'].includes(u.hostname) ||
        u.username || u.password || u.port && u.port !== '443') throw Error();
    return value;
  }
  if (!Array.isArray(flowState.flows)) throw Error();
  for (const flow of flowState.flows) {
    if (!flow || !uuid.test(flow.id) || !['pending', 'done', 'cancelled', 'expired'].includes(flow.status) ||
        typeof flow.fingerprintId !== 'string' || !flow.fingerprintId || !Number.isFinite(Date.parse(flow.createdAt))) throw Error();
    loginURL(flow.loginUrl);
  }
  const flows = new Map(flowState.flows.map(flow => [flow.id, flow]));
  if (flows.size !== flowState.flows.length) throw Error();
  const saveFlows = () => write(flowFile, { ...flowState, flows: [...flows.values()] });
  const fingerprintFile = path.join(data, 'runtime-fingerprint.json');
  let fingerprint = read(fingerprintFile, null);
  if (!fingerprint) { fingerprint = { fingerprintId: `runtime-${randomUUID()}` }; write(fingerprintFile, fingerprint); }
  if (typeof fingerprint.fingerprintId !== 'string' || !fingerprint.fingerprintId) throw Error();
  function expiry(value) {
    return typeof value === 'number' || /^\d+$/.test(String(value)) ? Number(value) : Date.parse(value);
  }
  function expire(flow) {
    if (flow.status === 'pending' && Date.now() >= Math.min(Date.parse(flow.createdAt) + 300000, expiry(flow.expiresAt) || 0)) {
      flow.status = 'expired'; saveFlows();
    }
  }
  const publicFlow = flow => ({ flow: Object.fromEntries(['id', 'status', 'loginUrl', 'createdAt', 'expiresAt'].map(k => [k, flow[k]])) });
  // Cached management views never probe or admit an upstream session.
  const status = () => ({ upstream: { pinnedEgress: true }, accounts: accounts.map(a => ({
    id: a.id || null, email: typeof a.email === 'string' ? a.email : null, state: 'unknown', quota: null,
  })) });
  async function authAPI(route, init = {}) {
    const response = await outbound(`https://www.codebuff.com/api/auth/cli/${route}`, {
      ...init, signal: AbortSignal.timeout(15000),
    });
    if (response.status === 401 && route.startsWith('status?')) return { pending: true };
    if (!response.ok) throw Error();
    return response.json();
  }
  const polls = new Set();
  function authorized(req) {
    const value = req.headers.authorization?.startsWith('Bearer ') ? req.headers.authorization.slice(7) : req.headers['x-api-key'];
    const a = Buffer.from(typeof value === 'string' ? value : '');
    const b = Buffer.from(cfg.token);
    return a.length === b.length && timingSafeEqual(a, b);
  }
  function json(res, value, code = 200) {
    res.writeHead(code, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(JSON.stringify(value));
  }
  server = http.createServer((req, res) => {
    const controller = new AbortController();
    active.add(controller);
    req.on('aborted', () => controller.abort());
    res.on('close', () => { if (!res.writableFinished) controller.abort(); active.delete(controller); });
    context.run(controller, async () => {
      try {
        if (!authorized(req)) { json(res, { error: { message: 'Unauthorized' } }, 401); return; }
        const url = new URL(req.url, 'http://127.0.0.1');
        let size = 0;
        const chunks = [];
        for await (const chunk of req) {
          size += chunk.length;
          if (size > 25 * 1024 * 1024) { json(res, { error: { message: 'Request too large' } }, 413); return; }
          chunks.push(chunk);
        }
        controller.signal.throwIfAborted();
        const body = Buffer.concat(chunks);
        if (req.method === 'GET' && ['/v1/freebuff/status', '/healthz', '/health'].includes(url.pathname) ||
            req.method === 'POST' && url.pathname === '/api/accounts/refresh') { json(res, status()); return; }
        if (req.method === 'POST' && url.pathname === '/api/accounts/login') {
          const code = await authAPI('code', { method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ fingerprintId: fingerprint.fingerprintId }) });
          controller.signal.throwIfAborted();
          const deadline = Math.min(Date.now() + 300000, expiry(code.expiresAt));
          if (!Number.isFinite(deadline) || deadline <= Date.now() || typeof code.fingerprintHash !== 'string' || !code.fingerprintHash) throw Error();
          const flow = { id: randomUUID(), status: 'pending', loginUrl: loginURL(code.loginUrl),
            fingerprintId: fingerprint.fingerprintId, fingerprintHash: code.fingerprintHash,
            upstreamExpiresAt: code.expiresAt, createdAt: new Date().toISOString(), expiresAt: new Date(deadline).toISOString() };
          flows.set(flow.id, flow); saveFlows(); json(res, publicFlow(flow)); return;
        }
        const match = /^\/api\/accounts\/login\/([^/]+)(\/cancel)?$/.exec(url.pathname);
        if (match && uuid.test(match[1])) {
          const flow = flows.get(match[1]);
          if (!flow) { json(res, { error: { message: 'Not found' } }, 404); return; }
          expire(flow);
          if (req.method === 'POST' && match[2]) {
            if (flow.status === 'pending') { flow.status = 'cancelled'; saveFlows(); }
          } else if (req.method === 'GET' && !match[2]) {
            if (flow.status === 'pending' && !polls.has(flow.id)) {
              polls.add(flow.id);
              try {
                const query = new URLSearchParams({ fingerprintId: flow.fingerprintId,
                  fingerprintHash: flow.fingerprintHash || '', expiresAt: String(flow.upstreamExpiresAt ?? flow.expiresAt) });
                const result = await authAPI(`status?${query}`);
                controller.signal.throwIfAborted();
                expire(flow);
                if (flow.status === 'pending' && result.user?.authToken) {
                  saveAccount(result.user, true); flow.status = 'done'; saveFlows();
                }
              } catch { controller.signal.throwIfAborted(); expire(flow); }
              finally { polls.delete(flow.id); }
            }
          } else { json(res, { error: { message: 'Not found' } }, 404); return; }
          json(res, publicFlow(flow)); return;
        }
        if (!(req.method === 'GET' && url.pathname === '/v1/models' ||
              req.method === 'POST' && url.pathname === '/v1/chat/completions')) {
          json(res, { error: { message: 'Not found' } }, 404); return;
        }
        const response = await worker.fetch(new Request(url, { method: req.method,
          headers: { authorization: `Bearer ${cfg.token}`, 'content-type': 'application/json' },
          ...(req.method === 'POST' ? { body } : {}), signal: controller.signal }), {
          API_KEY: cfg.token, FREEBUFF_TOKEN: accounts.map(a => a.authToken + (a.id ? `:${a.id}` : '')).join('\n'),
          FREEBUFF_DEBUG: 'false',
        });
        controller.signal.throwIfAborted();
        if (controller.accessBlocked) { await response.body?.cancel(); json(res, { error: {
          message: 'Freebuff blocked access for this account or region', code: 'freebuff_access_blocked', reason: controller.accessBlocked,
        } }, 403); return; }
        if (controller.updateRequired) { await response.body?.cancel(); json(res, { error: { message: 'Freebuff client update required', code: 'freebuff_update_required' } }, 410); return; }
        // Worker errors can quote raw upstream bodies; do not expose their secrets.
        if (response.status >= 400 || controller.streamFailure) { await response.body?.cancel(); json(res, { error: { message: 'Freebuff request failed' } }, controller.streamFailure ? 502 : response.status); return; }
        res.writeHead(response.status, { 'content-type': response.headers.get('content-type') || 'application/json', 'cache-control': 'no-store' });
        res.flushHeaders();
        if (response.body) {
          await pipeline(Readable.fromWeb(response.body), res, { signal: controller.signal, end: false });
          if (controller.streamFailure) res.write('data: {"error":{"message":"Incomplete Freebuff stream","code":"incomplete_stream"}}\n\n');
        }
        res.end();
      } catch {
        if (!res.headersSent && !res.destroyed) json(res, { error: { message: 'Freebuff request failed' } }, 502);
        else res.destroy();
      }
    });
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  process.stdout.write(JSON.stringify({ msg: 'freebuff2api listening', port: server.address().port }) + '\n');
} catch {
  process.stderr.write('Freebuff runtime initialization failed\n');
  dispatcher?.destroy();
  process.exit(1);
}
