// Run: node scripts/check_playground_codex.mjs (offline; no real fetch).
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
const models = [{ canonical_slug: "renamed/luna", provider_model_id: "gpt-6-luna", provider_id: 49 }];
const providers = [{ id: 49, configuration: { module_id: "codex_cli" } }];
const supportsSampling = bind("supportsSampling", { models, providers });
for (const target of ["codex_cli/gpt-6-luna", "renamed/luna", "gpt-6-luna"]) assert.equal(supportsSampling(target), false);
for (const target of ["google-ai/gemini", "route/mixed", "judge/mixed", "fusion/mixed", "grok_builder_cli/grok"]) assert.equal(supportsSampling(target), true);
const noop = () => {};
let checkedRequests = 0;
for (const isStream of [false, true]) {
  for (const mode of ["single", "chat", "compare"]) {
    for (const codexTarget of ["codex_cli/gpt-6-luna", "renamed/luna"]) {
      const captured = [];
      const context = {
        supportsSampling, checkModelSupportsThinking: () => true,
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
        mode, targetA: codexTarget, targetB: "google-ai/gemini", userPrompt: "Synthetic input", chatInput: "Synthetic input",
        loadingA: false, systemPrompt: "Synthetic system", chatMessages: [{ role: "assistant", content: "Synthetic history" }],
        setChatInput: noop, setChatMessages: noop, executeTargetRequest,
      };
      const handler = bind(mode === "chat" ? "handleChatSubmit" : "handleSingleSubmit", state);
      await handler({ preventDefault: noop });
      assert.equal(captured.length, mode === "compare" ? 2 : 1);
      const first = captured[0];
      assert.equal(first.model, codexTarget);
      assert.equal(Object.hasOwn(first, "temperature"), false);
      assert.equal(Object.hasOwn(first, "top_p"), false);
      assert.equal(first.max_tokens, 4096);
      assert.equal(first.reasoning_effort, "high");
      assert.equal(first.stream, isStream);
      if (isStream) assert.equal(first.stream_options.include_usage, true);
      if (mode === "compare") {
        assert.equal(captured[1].temperature, 0.7);
        assert.equal(captured[1].top_p, 1);
        assert.equal(captured[1].reasoning_effort, "low");
      }
      checkedRequests += captured.length;
    }
  }
}
for (const targetA of ["codex_cli/gpt-6-luna", "renamed/luna", "google-ai/gemini"]) {
  for (const codeTab of ["python", "curl", "node"]) {
    const code = bind("getExportCode", {
      supportsSampling, targetA, mode: "chat", chatInput: "Synthetic input", userPrompt: "", systemPrompt: "Synthetic system",
      supportsThinkingA: true, thinkingEffortA: "high", customThinkingA: "8192", codeTab,
      temperature: 0.7, maxTokens: 4096, isStream: false,
    })();
    assert.equal(code.includes("temperature"), supportsSampling(targetA));
    assert.equal(code.includes("top_p"), false);
    assert.ok(code.includes("4096") && code.includes("high"));
  }
}
console.log(`PASS: ${checkedRequests} captured offline requests; chat/single/compare, stream/JSON, renamed Codex, other-provider parameters, 9 export examples.`);
