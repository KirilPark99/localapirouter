// Offline regression check: node scripts/verify_audio.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import vm from "node:vm";
const require = createRequire(import.meta.url);
const ts = require("typescript");
const storage = { getItem: () => "test-token", removeItem() {} };
function load(file, imports, globals = {}) {
  const exports = {};
  const code = ts.transpileModule(readFileSync(new URL(file, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, esModuleInterop: true },
  }).outputText;
  vm.runInNewContext(code, { exports, require: (name) => imports[name], console, FormData, performance,
    URLSearchParams, localStorage: storage, sessionStorage: { getItem: () => null },
    window: { location: { search: "" } }, ...globals });
  return exports;
}
let request;
let failure = false;
const client = load("../src/api/client.ts", {}, {
  fetch: async (path, options) => {
    request = { path, ...options };
    return { ok: true, status: 200, json: async () => ({ text: "hello" }), headers: new Headers() };
  },
});
const body = new FormData();
body.append("file", new Blob(["audio"], { type: "audio/wav" }), "sample.wav");
await client.apiRequest("/transcribe", { method: "POST", body });
assert.equal(request.headers["Content-Type"], undefined);
assert.equal(request.headers.Authorization, "Bearer test-token");
await client.apiRequest("/json", { method: "POST", body: "{}" });
assert.equal(request.headers["Content-Type"], "application/json");

let states = [], effects = [], cursor = 0;
const react = {
  createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
  useState(initial) {
    const index = cursor++;
    if (!(index in states)) states[index] = typeof initial === "function" ? initial() : initial;
    return [states[index], (next) => { states[index] = typeof next === "function" ? next(states[index]) : next; }];
  },
  useRef: (current) => ({ current }),
  useMemo: (fn) => fn(),
  useEffect: (fn) => effects.push(fn),
};
const models = ["openai", "audio", "audio", "jev"].map((model_type, id) => ({
  id, provider_id: 1, provider_model_id: `model-${id}`, canonical_slug: `groq/model-${id}`,
  display_name: `Model ${id}`, is_visible: true, available: true, enabled: true, model_type,
}));
const utils = load("../src/utils/models.ts", {});
const textKeys = new Proxy({}, { get: (_, key) => String(key) });
const { PlaygroundPage } = load("../src/pages/PlaygroundPage.tsx", {
  react, "lucide-react": {}, "../utils/models": utils,
  "../i18n": { useI18n: () => ({ language: "en", t: { common: textKeys, playground: textKeys } }) },
  "../api/client": { apiRequest: async (path, options) => {
    if (options?.body instanceof FormData) {
      request = { path, ...options };
      if (failure) throw new Error("upstream rejected upload");
      return { text: "Transcribed speech" };
    }
    if (path.endsWith("/models")) return models;
    if (path.endsWith("/providers")) return [{ id: 1, name: "Groq" }];
    if (path.endsWith("/routes")) return [{ slug: "chat", enabled: true, candidates: [] }];
    return [];
  } },
});
// Prime the actual component's loaded data without a browser or a live server.
let tree;
function render() { cursor = 0; effects = []; tree = PlaygroundPage(); }
render();
effects[0]();
await new Promise((resolve) => setImmediate(resolve));
react.useEffect = (fn, deps) => { if (deps.length) effects.push(fn); };
function settle() { for (let i = 0; i < 3; i++) { render(); for (const effect of effects) effect(); } render(); }
function nodes(node = tree) {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap((child) => nodes(child ?? null));
  return [node, ...nodes(node.props?.children ?? null)];
}
const button = (label) => nodes().find((node) => node.type === "button" && node.props.children.includes(label));
const options = () => nodes().filter((node) => node.type === "option").map((node) => node.props.value);
settle();
assert(!options().includes("groq/model-1"), "audio must not appear in chat targets");
button("Audio (STT)").props.onClick();
settle();
assert(options().includes("groq/model-1"));
assert(options().includes("groq/model-2"));
assert(!options().includes("groq/model-0"));
assert(!options().includes("groq/model-3"));
assert(!options().includes("route/chat"), "no route profiles for audio");
const form = () => nodes().find((node) => node.type === "form");
await form().props.onSubmit({ preventDefault() {} });
assert.equal(request.path, "/json", "no file means no transcription request");
nodes().find((node) => node.type === "input" && node.props.type === "file").props.onChange({
  target: { files: [new Blob(["sample"], { type: "audio/wav" })] },
});
settle();
await form().props.onSubmit({ preventDefault() {} });
assert.equal(request.path, "/v1/audio/transcriptions");
assert.equal(request.method, "POST");
assert.equal(request.body.get("model"), "groq/model-1");
assert.equal(request.body.get("response_format"), "json");
assert(request.body.get("file") instanceof Blob);
assert(!request.body.has("language"));
assert.equal(request.headers["Content-Type"], undefined);
settle();
assert(nodes().some((node) => node.type === "pre" && node.props.children.includes("Transcribed speech")));
nodes().find((node) => node.type === "input" && node.props.placeholder === "Auto-detect").props.onChange({ target: { value: " ru " } });
settle();
await form().props.onSubmit({ preventDefault() {} });
assert.equal(request.body.get("language"), "ru");
failure = true;
settle();
await form().props.onSubmit({ preventDefault() {} });
settle();
assert(nodes().some((node) => node.props?.role === "alert" && node.props.children.includes("upstream rejected upload")));
const previousRequest = request;
nodes().find((node) => node.type === "input" && node.props.type === "file").props.onChange({
  target: { files: [new Blob([new Uint8Array(25_000_000 + 1)])] },
});
settle();
await form().props.onSubmit({ preventDefault() {} });
settle();
assert.equal(request, previousRequest, "oversized uploads must not be sent");
assert(nodes().some((node) => node.props?.role === "alert" && node.props.children.includes("Choose a nonempty audio file up to 25 MB.")));
button("Chat").props.onClick();
settle();
assert(!options().includes("groq/model-1"), "audio stays excluded after switching back");
button("Compare (x2)").props.onClick();
settle();
assert(!options().includes("groq/model-1"), "audio must not appear in either compare target");
models.splice(1, 2);
button("Audio (STT)").props.onClick();
settle();
assert(!options().includes("groq/model-0"), "empty audio catalog cannot retain a chat target");
assert(form() && nodes().find((node) => node.type === "button" && node.props.type === "submit").props.disabled);
console.log("PASS: multipart auth/headers, chat/audio target isolation, upload fields, optional language, response and error UI");
