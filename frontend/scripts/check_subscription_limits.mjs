import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { createServer } = await import(path.join(root, 'node_modules/vite/dist/node/index.js'));
for (const page of ['CredentialsPage', 'ModulesPage']) {
  assert.ok(fs.readFileSync(`${root}/src/pages/${page}.tsx`, 'utf8').includes('<SubscriptionLimitsBadge'), `${page}: remaining limits must be beside each key`);
}
const scratch = fs.mkdtempSync(path.join(process.env.TMPDIR || os.tmpdir(), 'subscription-check-'));
let token = 'synthetic-session', calls = 0, release;
globalThis.localStorage = { getItem: key => key === 'myairouter_token' ? token : 'ru' };
globalThis.fetch = async url => {
  calls++;
  assert.match(url, /^\/api\/admin\/credentials\/\d+\/subscription-limits$/);
  if (release) await new Promise(resolve => { release = resolve; });
  return new Response(JSON.stringify({ status: 'ok', limits: [{ name: 'Codex', remaining_percent: 0, window_seconds: 604800 }] }), { headers: { 'Content-Type': 'application/json' } });
};
const server = await createServer({ root, configFile: false, cacheDir: scratch, server: { middlewareMode: true } });
try {
  const { subscriptionPeriod, subscriptionRemaining, subscriptionAmount, loadSubscriptionLimits, SubscriptionLimitsBadge } = await server.ssrLoadModule('/src/components/SubscriptionLimitsBadge.tsx');
  const { I18nProvider } = await server.ssrLoadModule('/src/i18n/context.tsx');
  const labels = { unknown: 'Unknown' };
  assert.equal(subscriptionPeriod({ name: 'primary', window_seconds: 18000 }), null, '5h is not a day');
  assert.equal(subscriptionPeriod({ name: 'daily', window_seconds: 18000 }), null, 'Reported duration outranks label');
  assert.equal(subscriptionPeriod({ name: 'primary', window_seconds: 86400 }), null, 'No day bucket');
  assert.equal(subscriptionPeriod({ name: 'secondary', window_seconds: 604800 }), 'week');
  assert.equal(subscriptionPeriod({ name: 'Monthly credits' }), 'month');
  assert.equal(subscriptionPeriod({ name: 'Included credits', reset_at: '2026-10-15T00:00:00Z' }), null, 'Reset date alone cannot establish a period');
  assert.equal(subscriptionRemaining({ name: 'zero', remaining_percent: 0 }, labels), '0%');
  assert.equal(subscriptionRemaining({ name: 'overage', used_percent: 105 }, labels), '0%');
  assert.equal(subscriptionRemaining({ name: 'absolute', limit: 10, used: 10, unit: 'credits' }, labels), '0 credits');
  assert.equal(subscriptionRemaining({ name: 'unknown' }, labels), 'Unknown');
  release = true;
  const a = loadSubscriptionLimits(7, 'codex_cli'), b = loadSubscriptionLimits(7, 'codex_cli');
  assert.equal(calls, 1, 'Concurrent consumers share one request');
  release(); release = null;
  assert.deepEqual(await a, await b);
  await loadSubscriptionLimits(7, 'codex_cli'); assert.equal(calls, 1, 'Navigation uses fresh data');
  await loadSubscriptionLimits(8, 'codex_cli'); assert.equal(calls, 2, 'Different key is isolated');
  await loadSubscriptionLimits(7, 'codex_cli', true); assert.equal(calls, 3, 'Explicit refresh bypasses cache');
  token = 'another-synthetic-session'; await loadSubscriptionLimits(7, 'codex_cli'); assert.equal(calls, 4, 'Session changes invalidate data');
  const before = calls;
  const html = renderToStaticMarkup(React.createElement(I18nProvider, null, React.createElement(SubscriptionLimitsBadge, { credentialId: 7, moduleId: 'codex_cli' })));
  for (const label of ['Неделя', '0%', 'aria-haspopup="dialog"']) assert.ok(html.includes(label), label);
  assert.ok(!html.includes('День') && !html.includes('Месяц'), 'Do not show absent calendar periods');
  assert.equal(subscriptionAmount(1234, 'USD cents'), (12.34).toLocaleString(undefined, { style: 'currency', currency: 'USD' }));
  globalThis.fetch = async () => new Response(JSON.stringify({ status: 'ok', limits: [
    { name: 'Included credits', remaining_percent: 62, used_percent: 38 },
    { name: 'On-demand', remaining: 0, unit: 'USD cents' },
    { name: 'Prepaid credits', remaining: 1234, unit: 'USD cents' },
  ] }), { headers: { 'Content-Type': 'application/json' } });
  await loadSubscriptionLimits(79, 'grok_builder_cli');
  const grok = renderToStaticMarkup(React.createElement(I18nProvider, null, React.createElement(SubscriptionLimitsBadge, { credentialId: 79, moduleId: 'grok_builder_cli' })));
  for (const label of ['Кредиты подписки', 'Купленные кредиты', 'Дополнительный лимит', '62%', subscriptionAmount(1234, 'USD cents')]) assert.ok(grok.includes(label), label);
  for (const label of ['День', 'Неделя', 'Месяц', 'USD cents']) assert.ok(!grok.includes(label), label);
  assert.equal(calls, before, 'Server rendering performs no requests');
  globalThis.fetch = async () => { throw new Error('synthetic unavailable'); };
  const failure = await loadSubscriptionLimits(9, 'grok_builder_cli');
  assert.equal(failure.status, 'unavailable'); assert.deepEqual(failure.limits, []);
  console.log('PASS: both list callers, exact periods/no fake windows, zero/unknown/overage, cache/singleflight/key/session isolation, refresh/error, actual RU badge; synthetic fetch only.');
} finally { await server.close(); fs.rmSync(scratch, { recursive: true, force: true }); }
