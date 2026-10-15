// Run: node scripts/check_playground_codex.mjs (Codex/Grok; offline, no real fetch).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";

const source = ts.createSourceFile("PlaygroundPage.tsx", readFileSync(new URL("../src/pages/PlaygroundPage.tsx", import.meta.url), "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const declarations = new Map();
function visit(node) {
  if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) declarations.set(node.name.text, node.initializer);
  ts.forEachChild(node, visit);
}
visit(source);
function bind(name, context) {
  const expression = declarations.get(name);
  assert.ok(expression, `Missing production function: ${name}`);
  const javascript = ts.transpileModule(`const productionFunction = (${expression.getText(source)});`, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return Function(...Object.keys(context), `${javascript}\nreturn productionFunction;`)(...Object.values(context));
}
const models = [
  { canonical_slug: "renamed/luna", provider_model_id: "gpt-6-luna", provider_id: 49 },
  { canonical_slug: "renamed/grok", provider_model_id: "grok-4.7", provider_id: 50 },
  { canonical_slug: "renamed/qoder", provider_model_id: "Auto", provider_id: 51, capabilities: { reasoning: false } },
  { canonical_slug: 'renamed/freebuff', provider_model_id: 'Solar-Mini-4', provider_id: 56 },
];
const providers = [
  { id: 49, configuration: { module_id: "codex_cli" } },
  { id: 50, configuration: { module_id: "grok_builder_cli" } },
  { id: 51, configuration: { module_id: "qoder" } },
  { id: 56, configuration: { module_id: 'freebuff' } },
];
const getTargetModule = bind('getTargetModule', { models, providers });
const supportsSampling = bind("supportsSampling", { getTargetModule });
const supportsOutputLimit = bind('supportsOutputLimit', { getTargetModule });
for (const target of ['qoder/Auto', 'module_qoder/Auto', 'renamed/qoder', 'Auto']) assert.equal(supportsSampling(target), false);
for (const target of ['freebuff/Solar-Mini-4', 'module_freebuff/Solar-Mini-4', 'renamed/freebuff', 'Solar-Mini-4']) assert.equal(supportsSampling(target), false);
for (const target of ["codex_cli/gpt-6-luna", "module_codex_cli/gpt-6-luna", "renamed/luna", "gpt-6-luna", "grok_builder_cli/grok-4.7", "module_grok_builder_cli/grok-4.7", "renamed/grok", "grok-4.7"]) assert.equal(supportsSampling(target), false);
for (const target of ["google-ai/gemini", "route/mixed", "judge/mixed", "fusion/mixed"]) assert.equal(supportsSampling(target), true);
const noop = () => {};
let checkedRequests = 0;
for (const isStream of [false, true]) {
  for (const mode of ["single", "chat", "compare"]) {
    for (const cliTarget of ["codex_cli/gpt-6-luna", "renamed/luna", "grok_builder_cli/grok-4.7", "renamed/grok", 'renamed/qoder', 'renamed/freebuff', 'module_freebuff/Solar-Mini-4']) {
      const captured = [];
      const context = {
        supportsSampling, supportsOutputLimit, getTargetModule, checkModelSupportsThinking: (target) => target !== 'renamed/qoder',
        thinkingEffortA: "high", thinkingEffortB: "low", customThinkingA: "8192", customThinkingB: "8192",
        temperature: 0.7, topP: 1, maxTokens: 4096, isStream,
        abortControllerRefA: { current: null }, abortControllerRefB: { current: null },
        requestHeaders: () => ({ "Content-Type": "application/json" }), expireSession: noop,
        fetch: async (url, options) => {
          assert.equal(url, "/v1/chat/completions");
          captured.push(JSON.parse(options.body));
          const choice = isStream ? { delta: { content: "Synthetic offline response" }, finish_reason: "stop" } : { message: { content: "Synthetic offline response" } };
          return new Response(isStream ? `data: ${JSON.stringify({ choices: [choice] })}\n\ndata: [DONE]\n\n` : JSON.stringify({ choices: [choice] }), { headers: { "Content-Type": isStream ? "text/event-stream" : "application/json" } });
        },
      };
      for (const setter of ["setLoading", "setResponseContent", "setReasoningContent", "setResponseMeta", "setError"]) {
        context[setter + "A"] = noop;
        context[setter + "B"] = noop;
      }
      const executeTargetRequest = bind("executeTargetRequest", context);
      const state = {
        mode, targetA: cliTarget, targetB: "google-ai/gemini", userPrompt: "Synthetic input", chatInput: "Synthetic input",
        loadingA: false, systemPrompt: "Synthetic system", chatMessages: [{ role: "assistant", content: "Synthetic history" }],
        setChatInput: noop, setChatMessages: noop, executeTargetRequest,
      };
      const handler = bind(mode === "chat" ? "handleChatSubmit" : "handleSingleSubmit", state);
      await handler({ preventDefault: noop });
      assert.equal(captured.length, mode === "compare" ? 2 : 1);
      const first = captured[0];
      assert.equal(first.model, cliTarget);
      assert.equal(Object.hasOwn(first, "temperature"), false);
      assert.equal(Object.hasOwn(first, "top_p"), false);
      assert.equal(first.max_tokens, getTargetModule(cliTarget) === 'freebuff' ? undefined : 4096);
      assert.equal(first.reasoning_effort, cliTarget === 'renamed/qoder' ? undefined : 'high');
      assert.equal(first.stream, isStream);
      if (isStream && getTargetModule(cliTarget) !== 'freebuff') assert.equal(first.stream_options.include_usage, true);
      if (getTargetModule(cliTarget) === 'freebuff') {
        assert.equal(Object.hasOwn(first, 'stream_options'), false);
        const allowed = new Set(['model','messages','stream','reasoning_effort']);
        assert.ok(Object.keys(first).every(key => allowed.has(key)), 'Freebuff request must match native accepted fields');
      }
      if (mode === "compare") {
        assert.equal(captured[1].temperature, 0.7);
        assert.equal(captured[1].top_p, 1);
        assert.equal(captured[1].reasoning_effort, "low");
      }
      checkedRequests += captured.length;
      if (mode === "compare") {
        captured.length = 0;
        state.targetA = "google-ai/gemini";
        state.targetB = cliTarget;
        await bind("handleSingleSubmit", state)({ preventDefault: noop });
        assert.equal(captured.length, 2);
        assert.equal(captured[0].temperature, 0.7);
        assert.equal(captured[0].top_p, 1);
        assert.equal(captured[1].model, cliTarget);
        assert.equal(Object.hasOwn(captured[1], "temperature"), false);
        assert.equal(Object.hasOwn(captured[1], "top_p"), false);
        assert.equal(captured[1].max_tokens, getTargetModule(cliTarget) === 'freebuff' ? undefined : 4096);
        if (getTargetModule(cliTarget) === 'freebuff') assert.equal(Object.hasOwn(captured[1], 'stream_options'), false);
        checkedRequests += captured.length;
      }
    }
  }
}
for (const [mode, targetA, targetB, expected] of [
  ["single", "grok_builder_cli/grok-4.7", "google-ai/gemini", true],
  ["compare", "codex_cli/gpt-6-luna", "grok_builder_cli/grok-4.7", true],
  ["compare", "grok_builder_cli/grok-4.7", "google-ai/gemini", false],
  ["compare", "google-ai/gemini", "grok_builder_cli/grok-4.7", false],
]) assert.equal(bind("samplingDisabled", { supportsSampling, mode, targetA, targetB }), expected);
for (const [mode, targetA, targetB, expected] of [
  ['single', 'renamed/freebuff', 'google-ai/gemini', true],
  ['compare', 'renamed/freebuff', 'module_freebuff/Solar-Mini-4', true],
  ['compare', 'renamed/freebuff', 'google-ai/gemini', false],
  ['compare', 'google-ai/gemini', 'renamed/freebuff', false],
  ['single', 'renamed/qoder', '', false],
]) assert.equal(bind('outputLimitDisabled', { supportsOutputLimit, mode, targetA, targetB }), expected);
let checkedExports = 0;
for (const targetA of ["codex_cli/gpt-6-luna", "renamed/luna", "grok_builder_cli/grok-4.7", "renamed/grok", "google-ai/gemini", 'renamed/freebuff', 'module_freebuff/Solar-Mini-4']) {
  for (const codeTab of ["python", "curl", "node"]) {
    const code = bind("getExportCode", {
      supportsSampling, supportsOutputLimit, targetA, mode: "chat", chatInput: "Synthetic input", userPrompt: "", systemPrompt: "Synthetic system",
      supportsThinkingA: true, thinkingEffortA: "high", customThinkingA: "8192", codeTab,
      temperature: 0.7, maxTokens: 4096, isStream: false,
    })();
    assert.equal(code.includes("temperature"), supportsSampling(targetA));
    assert.equal(code.includes("top_p"), false);
    assert.equal(code.includes('max_tokens'), supportsOutputLimit(targetA));
    assert.equal(code.includes('4096'), supportsOutputLimit(targetA));
    assert.ok(code.includes('high'));
    checkedExports++;
  }
}
console.log(`PASS: ${checkedRequests} captured offline requests; chat/single/compare, stream/JSON, Codex/Grok/Qoder/Freebuff aliases, other-provider parameters preserved, ${checkedExports} export examples.`);
