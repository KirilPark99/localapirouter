// Offline logic smoke: node scripts/verify_freebuff_login.mjs (no browser/network).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
const ts = createRequire(import.meta.url)("typescript");
let hooks = [], cursor = 0, effects = [], tree, timers = new Map(), nextTimer = 0;
const react = {
  createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
  useState(initial) {
    const i = cursor++;
    if (!(i in hooks)) hooks[i] = initial;
    return [hooks[i], next => { hooks[i] = typeof next === "function" ? next(hooks[i]) : next; }];
  },
  useRef(current) { const i = cursor++; return hooks[i] ||= { current }; },
  useEffect(fn, deps) {
    const i = cursor++, prior = hooks[i];
    if (!prior || deps.some((dep, index) => !Object.is(dep, prior.deps[index]))) {
      hooks[i] = { deps, cleanup: prior?.cleanup };
      effects.push(() => { hooks[i].cleanup?.(); hooks[i].cleanup = fn(); });
    }
  },
};
const mod = { manifest: { id: "freebuff", name: "Freebuff", fields: [], version: "1", default_models: [] },
  status: "ready", provider_id: 1, profiles_count: 2, models_count: 0 };
const profiles = [1, 2].map(id => ({ id, provider_id: 1, module_id: "freebuff", name: `Profile ${id}`,
  status: "HEALTHY", fields: {}, priority: 1, weight: 1, enabled: true, consecutive_failures: 0 }));
let clock = 1_000_000, flowNumber = 0, pendingStart, pendingStatus, badUrl = false, status = "pending", startStatus = "pending", copied;
let loginOrigin = "https://freebuff.com";
const flow = () => ({ id: `00000000-0000-4000-8000-${String(++flowNumber).padStart(12, "0")}`,
  loginUrl: badUrl ? "javascript:alert(1)" : `${loginOrigin}/cli?code=synthetic`, status: startStatus, expiresAt: clock + 600_000 });
const requests = [];
const apiRequest = async (path, options = {}) => {
  requests.push({ path, ...options });
  if (path.endsWith("/cancel")) return { flow: { ...flow(), status: "cancelled" } };
  if (path.endsWith("/sync-models")) return { success: true, models_discovered: 2 };
  if (path.endsWith("/login")) return pendingStart ? await new Promise(resolve => { pendingStart = resolve; }) : { flow: flow() };
  if (/\/login\//.test(path)) {
    if (pendingStatus) return await new Promise(resolve => { pendingStatus = resolve; });
    return { flow: { id: path.split("/").at(-1), loginUrl: `${loginOrigin}/cli?code=synthetic`, status } };
  }
  if (path === "/api/admin/modules") return [mod];
  if (path === "/api/admin/modules/groups") return { groups: [], assignments: {}, revision: 0 };
  if (path.endsWith("/profiles")) return profiles;
  return [];
};
const imports = { react, "lucide-react": {}, "../api/client": { apiRequest },
  "../i18n": { useI18n: () => ({ language: "ru" }) },
  "../i18n/quotaTranslations": { credentialQuotaTranslations: { ru: {} } },
  "../components/Modal": { Modal: "Modal" }, "../components/NotesModal": { NotesModal: "NotesModal" },
  "../components/QuotaEditor": {}, "../components/StatusBadge": {}, "../components/SubscriptionLimitsBadge": {},
  "../utils/country": { getCountryFlag: () => "" },
};
const exports = {};
vm.runInNewContext(ts.transpileModule(readFileSync(new URL("../src/pages/ModulesPage.tsx", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
}).outputText, { exports, require: name => imports[name], console, URL, AbortController, AbortSignal,
  Date: class extends Date { static now() { return clock; } },
  setTimeout: fn => { const id = ++nextTimer; timers.set(id, fn); return id; }, clearTimeout: id => timers.delete(id),
  navigator: { clipboard: { writeText: async text => { copied = text; } } },
  window: { open() { throw Error("Automatic browser opening forbidden"); } },
});
function render() { cursor = 0; effects = []; tree = exports.ModulesPage(); effects.forEach(fn => fn()); }
async function settle() { for (let i = 0; i < 4; i++) { await new Promise(resolve => setImmediate(resolve)); render(); } }
function nodes(node = tree) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(child => nodes(child ?? null));
  if (node.type === "Modal" && !node.props.isOpen) return [];
  return [node, ...nodes(node.props?.children ?? null)];
}
const text = node => typeof node === "string" ? node : Array.isArray(node) ? node.map(text).join("") : text(node?.props?.children || "");
const button = label => nodes().find(node => node.type === "button" && text(node).includes(label));
const loginModal = () => nodes().find(node => node.type === "Modal" && node.props.title.startsWith("Вход в Freebuff:"));
async function tick() { const batch = [...timers.values()]; timers.clear(); await Promise.all(batch.map(fn => fn())); await settle(); }
render(); await settle();
button("Профили (").props.onClick(); await settle();
const loginButtons = nodes().filter(n => n.type === "button" && text(n) === "Войти в Freebuff");
assert.equal(loginButtons.length, 2);
// Exercise the same first-party origins accepted by the runtime/admin API.
for (const origin of ["https://www.codebuff.com", "https://codebuff.com", "https://www.freebuff.com", "https://freebuff.com"]) {
  loginOrigin = origin;
  loginButtons[0].props.onClick(); await settle();
  assert(nodes().some(n => n.props.id === "freebuff-login-url" && n.props.value.startsWith(origin + "/")), `login start rejected ${origin}`);
  await tick();
  assert(!nodes().some(n => n.props.role === "alert"), `login poll rejected ${origin}`);
  button("Отменить вход").props.onClick(); await settle();
}
for (const origin of ["http://codebuff.com", "https://codebuff.com.evil.invalid", "https://user:pass@codebuff.com", "https://codebuff.com:444"]) {
  loginOrigin = origin;
  loginButtons[0].props.onClick(); await settle();
  assert(nodes().some(n => n.props.role === "alert"), `unsafe login accepted ${origin}`);
  assert(!nodes().some(n => n.props.id === "freebuff-login-url"));
  button("Отменить вход").props.onClick(); await settle();
}
loginOrigin = "https://freebuff.com";
button("Войти в Freebuff").props.onClick(); await settle();
assert(loginModal());
const input = nodes().find(n => n.props.id === "freebuff-login-url");
assert(input.props.readOnly && input.props.value.startsWith("https://"));
const link = nodes().find(n => n.type === "a" && text(n) === "Открыть ссылку");
assert.equal(link.props.href, input.props.value); assert.equal(link.props.rel, "noopener noreferrer");
await button("Скопировать ссылку").props.onClick(); assert.equal(copied, input.props.value);
await tick(); assert(!requests.some(r => r.path.endsWith("/sync-models")));
status = "done"; await tick();
assert.equal(requests.filter(r => r.path.endsWith("/sync-models")).length, 1);
assert(nodes().some(n => n.props.role === "status" && text(n).includes("модели синхронизированы")));
assert.equal(timers.size, 0);
button("Закрыть").props.onClick(); await settle();
status = "pending"; button("Войти в Freebuff").props.onClick(); await settle();
pendingStatus = true;
const poll = [...timers.values()][0]; timers.clear(); const inFlight = poll(); await settle();
const statusRequest = requests.at(-1); assert(statusRequest.signal && !statusRequest.signal.aborted);
button("Отменить вход").props.onClick(); await settle();
assert(statusRequest.signal.aborted); assert(requests.at(-1).path.endsWith("/cancel"));
pendingStatus({ flow: { id: statusRequest.path.split("/").at(-1), loginUrl: "https://freebuff.com", status: "done" } });
pendingStatus = null; await inFlight; await settle();
assert.equal(requests.filter(r => r.path.endsWith("/sync-models")).length, 1, "late completion cannot sync");
pendingStart = true; button("Войти в Freebuff").props.onClick(); await settle();
button("Отменить вход").props.onClick(); await settle();
const late = flow(); pendingStart({ flow: late }); pendingStart = null; await settle();
assert(requests.some(r => r.path.endsWith(`/login/${late.id}/cancel`)), "late start must be cancelled");
button("Войти в Freebuff").props.onClick(); await settle();
clock += 600_001; await tick();
assert.equal(timers.size, 0); assert(!nodes().some(n => n.props.id === "freebuff-login-url"));
button("Отменить вход").props.onClick(); await settle();
badUrl = true; button("Войти в Freebuff").props.onClick(); await settle();
assert(nodes().some(n => n.props.role === "alert"));
assert(!nodes().some(n => n.type === "a" && text(n) === "Открыть ссылку"));
button("Отменить вход").props.onClick(); await settle();
assert.equal(timers.size, 0);
badUrl = false;
startStatus = "done";
loginButtons[0].props.onClick(); await settle();
assert.equal(requests.filter(r => r.path.endsWith("/sync-models")).length, 2, "initial done also syncs models");
assert.equal(timers.size, 0);
button("Закрыть").props.onClick(); await settle(); startStatus = "pending";
loginButtons[0].props.onClick(); await settle();
const oldFlow = requests.findLast(r => /\/1\/login$/.test(r.path));
assert(oldFlow);
const cancellations = requests.filter(r => r.path.endsWith("/cancel")).length;
loginButtons[1].props.onClick(); await settle();
assert.equal(requests.filter(r => r.path.endsWith("/cancel")).length, cancellations + 1, "profile switch cancels old flow");
assert(requests.some(r => /\/2\/login$/.test(r.path)), "new profile starts its own flow");
pendingStatus = true;
const unmountPoll = [...timers.values()][0]; timers.clear(); const unmountFlight = unmountPoll(); await settle();
const unmountRequest = requests.at(-1);
for (const hook of hooks) hook?.cleanup?.();
assert(unmountRequest.signal.aborted, "unmount aborts status request");
assert(requests.at(-1).path.includes("/profiles/2/login/") && requests.at(-1).path.endsWith("/cancel"));
pendingStatus({ flow: { id: unmountRequest.path.split("/").at(-1), loginUrl: "https://freebuff.com", status: "done" } });
pendingStatus = null; await unmountFlight;
assert.equal(requests.filter(r => r.path.endsWith("/sync-models")).length, 2);
assert.equal(timers.size, 0);
console.log("PASS: real ModulesPage TSX: nested flow, explicit HTTPS/copy link, bounded polling, success sync, cancel/abort, late start/status cleanup, profile switch/unmount, unsafe URL refusal");
