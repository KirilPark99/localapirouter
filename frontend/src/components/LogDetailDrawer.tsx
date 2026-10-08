import React, { useState, useEffect } from "react";
import {
  X,
  Copy,
  Check,
  Play,
  Terminal,
  FileCode,
  Clock,
  Zap,
  Coins,
  ShieldCheck,
  Cpu,
  Boxes,
  KeyRound,
  AlertTriangle,
  CheckCircle2,
  MessageSquare,
  Sparkles,
  Layers,
  User,
  Bot,
  ExternalLink,
  GitFork,
  Brain,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { RequestLog } from "../types";
import { StatusBadge } from "./StatusBadge";
import { LogWaterfallTrace } from "./LogWaterfallTrace";
import { formatLogCost, getRequestLogTelemetry, requestParameterNames, telemetryValue } from "../utils/requestLogTelemetry";

const usageLabels = [
  ["input_tokens", "Prompt (Input)"], ["output_tokens", "Completion (Output)"],
  ["new_tokens", "NEW · Noncached input"], ["cached_tokens", "CACHE · Upstream input"],
  ["reasoning_tokens", "Thinking / Reasoning"],
] as const;

const ParameterComparison = ({ requested, effective }: {
  requested: Record<string, unknown>; effective: Record<string, unknown>;
}) => (
  <div className="overflow-x-auto">
    <table className="w-full text-xs text-left">
      <thead className="text-[10px] uppercase text-slate-400">
        <tr><th className="py-1 pr-3">Parameter</th><th className="py-1 pr-3">Requested</th><th className="py-1">Routed · pre-adapter</th></tr>
      </thead>
      <tbody className="font-mono text-slate-300">
        {requestParameterNames.map((name) => (
          <tr key={name} className="border-t border-slate-800/60">
            <td className="py-1 pr-3">{name}</td>
            <td className="py-1 pr-3">{telemetryValue(requested[name])}</td>
            <td className="py-1 text-indigo-300">{telemetryValue(effective[name])}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

interface LogDetailDrawerProps {
  log: RequestLog | null;
  onClose: () => void;
  onReplayInPlayground?: (log: RequestLog) => void;
}

export const LogDetailDrawer: React.FC<LogDetailDrawerProps> = ({
  log,
  onClose,
  onReplayInPlayground,
}) => {
  const [activeTab, setActiveTab] = useState<"overview" | "messages" | "waterfall" | "json">("overview");
  const [copiedId, setCopiedId] = useState(false);
  const [copiedCurl, setCopiedCurl] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedResponse, setCopiedResponse] = useState(false);
  const [copiedCandidateIdx, setCopiedCandidateIdx] = useState<number | null>(null);
  const [copiedDeliberation, setCopiedDeliberation] = useState(false);
  const [expandedCandidates, setExpandedCandidates] = useState<Record<number, boolean>>({});

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!log) return null;
  const telemetry = getRequestLogTelemetry(log);
  const compression = telemetry.compression;
  const lastDispatch = telemetry.dispatches.at(-1);

  const handleCopyId = () => {
    navigator.clipboard.writeText(log.request_id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(log, null, 2));
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  const handleCopyCurl = () => {
    const host = window.location.origin;
    let bodyObj: any = {
      model: log.requested_model,
      messages: [{ role: "user", content: log.prompt_content || "Hello!" }],
      stream: !!log.metadata_json?.stream,
    };
    if (log.metadata_json?.temperature !== undefined) {
      bodyObj.temperature = log.metadata_json.temperature;
    }
    const curl = `curl -X POST "${host}/v1/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_ROUTER_API_KEY" \\
  -d '${JSON.stringify(bodyObj, null, 2)}'`;

    navigator.clipboard.writeText(curl);
    setCopiedCurl(true);
    setTimeout(() => setCopiedCurl(false), 2000);
  };

  // Helper for status code colors
  const getStatusCodeBadge = (code: number) => {
    const is2xx = code >= 200 && code < 300;
    const is429 = code === 429;
    const is5xx = code >= 500;
    const color = is2xx
      ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/60"
      : is429
      ? "bg-amber-950/60 text-amber-300 border-amber-800/60"
      : is5xx
      ? "bg-rose-950/60 text-rose-300 border-rose-800/60"
      : "bg-slate-950/60 text-slate-300 border-slate-700/60";

    return (
      <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold border ${color}`}>
        HTTP {code}
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end animate-in fade-in duration-200">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      {/* Slide-over Drawer Panel */}
      <div className="relative w-full max-w-3xl bg-slate-900 border-l border-slate-800 shadow-2xl z-50 flex flex-col h-full text-slate-200">
        {/* Header */}
        <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">
                Request Inspector
              </span>
              {getStatusCodeBadge(log.status_code)}
              <StatusBadge status={log.status} size="sm" />
              <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-indigo-950/60 text-indigo-300 border border-indigo-800/60">
                {log.mode}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="font-mono text-sm font-semibold text-white truncate" title={log.request_id}>
                {log.request_id}
              </span>
              <button
                onClick={handleCopyId}
                className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition-colors"
                title="Copy Request ID"
              >
                {copiedId ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
              </button>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors shrink-0"
            title="Close (Esc)"
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center px-4 bg-slate-950/40 border-b border-slate-800 text-xs gap-2">
          {[
            { id: "overview", label: "Overview", icon: <Layers size={13} /> },
            { id: "messages", label: "Messages", icon: <MessageSquare size={13} /> },
            {
              id: "waterfall",
              label: `Waterfall (${log.attempts?.length || 1})`,
              icon: <Clock size={13} />,
            },
            { id: "json", label: "Raw JSON", icon: <FileCode size={13} /> },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-1.5 py-2.5 px-3 border-b-2 font-medium transition-colors ${
                activeTab === tab.id
                  ? "border-indigo-500 text-white bg-slate-900/60"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/30"
              }`}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Tab Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Tab 1: Overview */}
          {activeTab === "overview" && (
            <div className="space-y-4">
              {/* Error Callout if error exists */}
              {log.error_message && (
                <div className="p-3 bg-rose-950/50 border border-rose-800/80 rounded-xl space-y-1">
                  <div className="flex items-center gap-2 text-rose-300 font-semibold text-xs">
                    <AlertTriangle size={15} />
                    <span>Request execution error [{log.error_category || "ERROR"}]</span>
                  </div>
                  <div className="font-mono text-xs text-rose-200/90 whitespace-pre-wrap break-words bg-rose-950/40 p-2 rounded border border-rose-900/40">
                    {log.error_message}
                  </div>
                </div>
              )}

              {/* Core Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-1">
                  <div className="text-[10px] uppercase text-slate-400 font-semibold">Latency</div>
                  <div className="text-base font-bold font-mono text-sky-300">
                    {log.latency_ms.toFixed(1)} ms
                  </div>
                </div>
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-1">
                  <div className="text-[10px] uppercase text-slate-400 font-semibold">Total Tokens</div>
                  <div className="text-base font-bold font-mono text-amber-300">
                    {telemetryValue(telemetry.usage.input_tokens != null && telemetry.usage.output_tokens != null
                      ? telemetry.usage.input_tokens + telemetry.usage.output_tokens : null)}
                  </div>
                </div>
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-1">
                  <div className="text-[10px] uppercase text-slate-400 font-semibold">Cost ($)</div>
                  <div className="text-base font-bold font-mono text-yellow-300">
                    {formatLogCost(log)}
                  </div>
                </div>
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-1">
                  <div className="text-[10px] uppercase text-slate-400 font-semibold">Rotation Attempts</div>
                  <div className="text-base font-bold font-mono text-purple-300">
                    {telemetry.localCacheHit ? 0 : log.attempts?.length || 1}
                  </div>
                </div>
              </div>

              {/* Routing & Models Breakdown */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3.5 space-y-3">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 border-b border-slate-800/80 pb-2">
                  <Boxes size={14} className="text-indigo-400" />
                  <span>Routing & Model Configuration</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-[10px] uppercase text-slate-400 block">Target Model</span>
                    <span className="font-mono font-semibold text-slate-100">{log.requested_model}</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase text-slate-400 block">Upstream Model</span>
                    <span className="font-mono text-slate-200">{log.upstream_model || "—"}</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase text-slate-400 block">Provider & Credential</span>
                    <span className="font-mono text-slate-200">
                      {log.resolved_provider_name ? (
                        <>
                          <span className="text-purple-300 font-semibold">{log.resolved_provider_name}</span>
                          {log.resolved_credential_name && (
                            <span className="text-slate-400"> ({log.resolved_credential_name})</span>
                          )}
                        </>
                      ) : (
                        "—"
                      )}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase text-slate-400 block">Client Router Key</span>
                    <span className="font-mono text-indigo-300">
                      {log.router_key_name || "Admin Direct Session"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Token Economics Detailed breakdown */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3.5 space-y-3">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 border-b border-slate-800/80 pb-2">
                  <Zap size={14} className="text-amber-400" />
                  <span>Token & Cache Breakdown</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  {usageLabels.map(([name, label]) => (
                    <div key={name} className="p-2 bg-slate-900/80 rounded-lg border border-slate-800">
                      <span className="text-[10px] text-slate-400 block">{label}</span>
                      <span className="font-mono font-bold text-slate-200">{telemetryValue(telemetry.usage[name])}</span>
                    </div>
                  ))}
                  <div className="p-2 bg-slate-900/80 rounded-lg border border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Local response cache</span>
                    <span className="font-mono font-bold text-emerald-400">{telemetry.responseCache}</span>
                  </div>
                </div>
                <p className="text-[11px] text-slate-400">
                  Usage source: {telemetryValue(telemetry.usage.source)}. NEW/CACHE split is unknown when upstream cache counts are unavailable.
                  Thinking tokens are a subset of output, not additional tokens.
                </p>
                {telemetry.usage.source === "upstream_partial" ? <p className="text-[11px] text-amber-300">Partial upstream totals: includes known usage from failed/cancelled calls; some dispatches did not report usage.</p> : null}
                {(log.mode === "JUDGE" || log.mode === "FUSION" || log.requested_model.startsWith("judge/")) && (
                  <p className="text-[11px] text-amber-300">Totals include judge/routing and participant calls, not just the final response. See individual dispatches below.</p>
                )}
                {telemetry.localCacheHit && (
                  <p className="text-[11px] text-emerald-300">Local response-cache HIT: no billed upstream call. Input/output are zero; this is not an upstream token-cache HIT.</p>
                )}
                {telemetry.localCacheHit && telemetry.savedResponseUsage != null && (
                  <details className="text-[11px] text-slate-400">
                    <summary className="cursor-pointer">Original cached response usage (not billed for this request)</summary>
                    <pre className="mt-2 font-mono whitespace-pre-wrap break-words">{JSON.stringify(telemetry.savedResponseUsage, null, 2)}</pre>
                  </details>
                )}
              </div>

              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3.5 space-y-3">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 border-b border-slate-800/80 pb-2">
                  <Layers size={14} className="text-sky-400" /><span>Context Compression · Local Estimate</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div><span className="text-[10px] text-slate-400 block">Original → After</span><span className="font-mono text-sky-300">{telemetryValue(compression?.tokens_before)} → {telemetryValue(compression?.tokens_after)}</span></div>
                  <div><span className="text-[10px] text-slate-400 block">Saved tokens</span><span className="font-mono text-sky-300">{telemetryValue(compression?.tokens_saved)}</span></div>
                  <div><span className="text-[10px] text-slate-400 block">Saved %</span><span className="font-mono text-sky-300">{telemetryValue(compression?.savings_percent)}{compression?.savings_percent != null ? "%" : ""}</span></div>
                  <div><span className="text-[10px] text-slate-400 block">Duration (ms)</span><span className="font-mono text-sky-300">{telemetryValue(compression?.duration_ms)}</span></div>
                </div>
                <p className="text-[11px] text-slate-400">
                  Compressed: {telemetryValue(compression?.compressed)}.
                  {compression?.disabled === true ? " Disabled." : ""}
                  {compression?.bypass === true ? " Bypassed." : ""}
                  {compression?.below_threshold === true ? " Below threshold." : ""}
                  {compression?.no_active_stages === true ? " No active stages." : ""}
                  {compression?.telemetry_disabled === true ? " Compression telemetry disabled." : ""}
                  {compression?.error ? ` Error: ${telemetryValue(compression.error)}.` : ""}
                  {" "}Counts are local estimates, separate from upstream usage and cache tokens.
                </p>
                {telemetry.stages.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[11px]">
                      <thead className="text-slate-400"><tr><th className="py-1 pr-2">Stage</th><th className="py-1 pr-2">Before → After</th><th className="py-1 pr-2">ms</th><th className="py-1">Advanced</th></tr></thead>
                      <tbody>
                        {telemetry.stages.map((stage, index) => (
                          <React.Fragment key={`${stage.stage_id ?? "stage"}-${index}`}>
                            <tr className="border-t border-slate-800/60 font-mono">
                              <td className="py-1 pr-2">{telemetryValue(stage.stage_name ?? stage.stage_id)}</td>
                              <td className="py-1 pr-2">{telemetryValue(stage.tokens_before)} → {telemetryValue(stage.tokens_after)}</td>
                              <td className="py-1 pr-2">{telemetryValue(stage.duration_ms)}</td>
                              <td className="py-1">{telemetryValue(stage.advanced)}</td>
                            </tr>
                            {stage.note || stage.warning ? <tr><td colSpan={4} className="pb-2 text-slate-400 break-words">{stage.note ? telemetryValue(stage.note) : ""}{stage.warning ? ` Warning: ${telemetryValue(stage.warning)}` : ""}</td></tr> : null}
                          </React.Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <p className="text-[11px] text-slate-500">Stage breakdown: —</p>}
              </div>

              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3.5 space-y-3">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 border-b border-slate-800/80 pb-2">
                  <Brain size={14} className="text-purple-400" /><span>Requested vs Routed Parameters</span>
                </div>
                <p className="text-[11px] text-slate-400">Routing parameters for the last dispatch, before provider-specific translation. Adapters may omit sampling values or adjust thinking/output budgets. These are not confirmation of the upstream's internal reasoning level. Missing values are unknown or unspecified.</p>
                <ParameterComparison requested={telemetry.requested} effective={lastDispatch ? { ...lastDispatch.parameters, stream: lastDispatch.stream } : {}} />
                <p className="text-[11px] text-slate-400">Reasoning source: {telemetryValue(lastDispatch?.parameters.reasoning_source)} · {telemetryValue(lastDispatch?.provider)} / {telemetryValue(lastDispatch?.model)}</p>
              </div>

              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3.5 space-y-3">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 border-b border-slate-800/80 pb-2">
                  <GitFork size={14} className="text-purple-400" /><span>Per-provider Dispatches ({telemetry.localCacheHit || telemetry.dispatchesKnown ? telemetry.dispatches.length : "—"})</span>
                </div>
                {telemetry.dispatches.length > 0 ? telemetry.dispatches.map((dispatch, index) => (
                  <div key={index} className="p-3 bg-slate-900/80 rounded-lg border border-slate-800 space-y-2">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="font-mono text-purple-300">#{index + 1} {telemetryValue(dispatch.provider)} / {telemetryValue(dispatch.model)}</span>
                      <StatusBadge status={dispatch.status || "UNKNOWN"} size="sm" />
                      <span className="font-mono text-sky-300">{telemetryValue(dispatch.latency_ms)} ms</span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                      {usageLabels.map(([name, label]) => (
                        <div key={name}><span className="text-[10px] text-slate-400 block">{label}</span><span className="font-mono">{telemetryValue(dispatch.usage?.[name])}</span></div>
                      ))}
                    </div>
                    <p className="text-[11px] text-slate-400">Reasoning source: {telemetryValue(dispatch.parameters.reasoning_source)}</p>
                    <details className="text-xs">
                      <summary className="cursor-pointer text-indigo-300">Requested vs routed parameters · pre-adapter</summary>
                      <div className="mt-2"><ParameterComparison requested={telemetry.requested} effective={{ ...dispatch.parameters, stream: dispatch.stream }} /></div>
                    </details>
                  </div>
                )) : <p className="text-[11px] text-slate-400">{telemetry.localCacheHit ? "No upstream dispatch: served from local response cache." : "Dispatch telemetry: — (not recorded for this request)."}</p>}
              </div>

              {/* Metadata & Client info */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3.5 space-y-3">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 border-b border-slate-800/80 pb-2">
                  <Terminal size={14} className="text-slate-400" />
                  <span>Client Metadata & Params</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs font-mono">
                  <div>
                    <span className="text-[10px] uppercase text-slate-400 block font-sans">Streaming Mode</span>
                    <span className="text-slate-300">
                      stream: {telemetryValue(telemetry.requested.stream ?? log.metadata_json?.stream)}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase text-slate-400 block font-sans">Created At</span>
                    <span className="text-slate-300">{new Date(log.created_at).toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase text-slate-400 block font-sans">HTTP Status</span>
                    <span className="text-slate-300 font-bold">{log.status_code}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Messages Dialog */}
          {activeTab === "messages" && (() => {
            const isFusion = log.mode === "FUSION" || !!log.metadata_json?.participants;
            const participants = log.metadata_json?.participants || [];
            const deliberation = log.metadata_json?.deliberation;
            const judge = log.metadata_json?.judge;

            if (!log.prompt_content && !log.response_content && (!isFusion || participants.length === 0)) {
              return (
                <div className="p-6 bg-slate-950/60 border border-slate-800 rounded-xl text-center space-y-2">
                  <MessageSquare size={24} className="text-slate-500 mx-auto" />
                  <div className="text-xs font-medium text-slate-300">
                    Request and response bodies not stored in database
                  </div>
                  <div className="text-[11px] text-slate-400 max-w-md mx-auto">
                    Request content logging is disabled in current router configuration (
                    <code className="text-indigo-400 font-mono">LOG_REQUEST_CONTENT=false</code>) to protect
                    user data privacy.
                  </div>
                </div>
              );
            }

            return (
              <div className="space-y-3">
                {/* Prompt Box */}
                {log.prompt_content && (
                  <div className="bg-slate-950/80 border border-slate-800 rounded-xl overflow-hidden">
                    <div className="px-3.5 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-300">
                        <User size={13} />
                        <span>User Prompt</span>
                      </div>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(log.prompt_content || "");
                          setCopiedPrompt(true);
                          setTimeout(() => setCopiedPrompt(false), 2000);
                        }}
                        className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white px-2 py-0.5 rounded hover:bg-slate-800 transition-colors cursor-pointer"
                      >
                        {copiedPrompt ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        <span>{copiedPrompt ? "Copied" : "Copy"}</span>
                      </button>
                    </div>
                    <div className="p-3 text-xs font-mono whitespace-pre-wrap break-words text-slate-200 max-h-72 overflow-y-auto select-text">
                      {log.prompt_content}
                    </div>
                  </div>
                )}

                {/* Fusion Ensemble Deliberation Section */}
                {isFusion && participants.length > 0 && (
                  <div className="bg-slate-950/80 border border-amber-900/50 rounded-xl overflow-hidden p-3.5 space-y-3">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-2.5 flex-wrap gap-2">
                      <div className="flex items-center gap-2">
                        <GitFork size={15} className="text-amber-400" />
                        <span className="text-xs font-semibold text-amber-300">
                          Ensemble Candidate Drafts (Fusion)
                        </span>
                        {log.metadata_json?.strategy && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-amber-950/80 text-amber-300 border border-amber-800/60 font-medium">
                            Strategy: {log.metadata_json.strategy}
                          </span>
                        )}
                      </div>
                      {judge && (
                        <span className="text-[11px] font-mono text-purple-300 flex items-center gap-1">
                          <span>⚖️ Judge:</span>
                          <strong className="text-purple-200">{judge.model_name || log.upstream_model}</strong>
                          {judge.latency_ms !== undefined && (
                            <span className="text-purple-400/80">({judge.latency_ms} ms)</span>
                          )}
                        </span>
                      )}
                    </div>

                    {/* Participant Cards */}
                    <div className="space-y-2.5">
                      {participants.map((p: any, idx: number) => {
                        const isExpanded = expandedCandidates[idx] !== false; // expanded by default
                        return (
                          <div key={idx} className="bg-slate-900/90 border border-slate-800 rounded-lg overflow-hidden text-xs">
                            <div className="px-3 py-2 bg-slate-950 border-b border-slate-800/80 flex items-center justify-between flex-wrap gap-2">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-amber-950/80 text-amber-300 border border-amber-800/60 font-bold">
                                  {p.label || `Candidate #${idx + 1}`}
                                </span>
                                <span className="font-mono text-slate-200 font-semibold">{p.model_name}</span>
                                {p.provider_name && (
                                  <span className="text-slate-400 text-[11px]">({p.provider_name})</span>
                                )}
                                {p.credential_name && (
                                  <span className="text-slate-500 text-[10px]">[{p.credential_name}]</span>
                                )}
                                {p.latency_ms !== undefined && (
                                  <span className="font-mono text-[11px] text-slate-400">{p.latency_ms} ms</span>
                                )}
                                <StatusBadge status={p.status || "UNKNOWN"} size="sm" />
                              </div>

                              <div className="flex items-center gap-1">
                                {p.content && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      navigator.clipboard.writeText(p.content || "");
                                      setCopiedCandidateIdx(idx);
                                      setTimeout(() => setCopiedCandidateIdx(null), 2000);
                                    }}
                                    className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white px-2 py-0.5 rounded hover:bg-slate-800 transition-colors cursor-pointer"
                                    title="Copy candidate draft"
                                  >
                                    {copiedCandidateIdx === idx ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                                    <span>{copiedCandidateIdx === idx ? "Copied" : "Copy"}</span>
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={() => setExpandedCandidates((prev) => ({ ...prev, [idx]: !isExpanded }))}
                                  className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition-colors cursor-pointer"
                                >
                                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                </button>
                              </div>
                            </div>

                            {isExpanded && (
                              <div className="p-3">
                                {p.content ? (
                                  <div className="font-mono whitespace-pre-wrap break-words text-slate-200 text-xs max-h-64 overflow-y-auto leading-relaxed select-text">
                                    {p.content}
                                  </div>
                                ) : p.error ? (
                                  <div className="text-rose-300 font-mono text-xs bg-rose-950/40 p-2 rounded border border-rose-900/40">
                                    ❌ Candidate error: {p.error}
                                  </div>
                                ) : (
                                  <div className="text-slate-500 text-[11px] italic">
                                    Candidate draft was not stored (enable request content logging in Settings).
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {/* Deliberation / Judge Reasoning */}
                    {(deliberation || judge?.reasoning) && (
                      <div className="bg-purple-950/20 border border-purple-900/50 rounded-lg overflow-hidden text-xs">
                        <div className="px-3 py-2 bg-purple-950/40 border-b border-purple-900/50 flex items-center justify-between">
                          <div className="flex items-center gap-1.5 text-purple-300 font-semibold">
                            <Brain size={13} className="text-purple-400" />
                            <span>Judge Deliberation & Synthesis</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              navigator.clipboard.writeText(deliberation || judge?.reasoning || "");
                              setCopiedDeliberation(true);
                              setTimeout(() => setCopiedDeliberation(false), 2000);
                            }}
                            className="flex items-center gap-1 text-[11px] text-purple-300 hover:text-white px-2 py-0.5 rounded hover:bg-purple-900/40 transition-colors cursor-pointer"
                          >
                            {copiedDeliberation ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                            <span>{copiedDeliberation ? "Copied" : "Copy"}</span>
                          </button>
                        </div>
                        <div className="p-3 font-mono whitespace-pre-wrap break-words text-purple-200 text-xs max-h-64 overflow-y-auto leading-relaxed select-text">
                          {deliberation || judge?.reasoning}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Assistant Response Box */}
                {log.response_content && (
                  <div className="bg-slate-950/80 border border-slate-800 rounded-xl overflow-hidden">
                    <div className="px-3.5 py-2 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-300">
                        <Bot size={13} />
                        <span>
                          {isFusion
                            ? "Final Verdict / Response"
                            : "Assistant Response"}
                        </span>
                      </div>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(log.response_content || "");
                          setCopiedResponse(true);
                          setTimeout(() => setCopiedResponse(false), 2000);
                        }}
                        className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white px-2 py-0.5 rounded hover:bg-slate-800 transition-colors cursor-pointer"
                      >
                        {copiedResponse ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        <span>{copiedResponse ? "Copied" : "Copy"}</span>
                      </button>
                    </div>
                    <div className="p-3 text-xs font-mono whitespace-pre-wrap break-words text-slate-200 max-h-72 overflow-y-auto select-text">
                      {log.response_content}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Tab 3: Waterfall Trace */}
          {activeTab === "waterfall" && (
            <LogWaterfallTrace
              attempts={log.attempts}
              totalLatencyMs={log.latency_ms}
              status={log.status}
              metadata={log.metadata_json}
            />
          )}

          {/* Tab 4: Raw JSON */}
          {activeTab === "json" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400 font-semibold">Complete Log Record JSON:</span>
                <button
                  onClick={handleCopyJson}
                  className="flex items-center gap-1 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 px-2.5 py-1 rounded-lg border border-slate-700 transition-colors"
                >
                  {copiedJson ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                  <span>{copiedJson ? "Copied!" : "Copy JSON"}</span>
                </button>
              </div>
              <pre className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl text-[11px] font-mono text-slate-300 overflow-x-auto max-h-[500px]">
                {JSON.stringify(log, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-3.5 bg-slate-950 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyCurl}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-800 text-xs font-medium transition-colors"
              title="Generate and copy curl command to replay request in terminal"
            >
              {copiedCurl ? <Check size={13} className="text-emerald-400" /> : <Terminal size={13} />}
              <span>{copiedCurl ? "cURL copied!" : "Copy cURL"}</span>
            </button>

            <button
              onClick={handleCopyJson}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white rounded-lg border border-slate-800 text-xs font-medium transition-colors"
            >
              <FileCode size={13} />
              <span>JSON</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (onReplayInPlayground) {
                  onReplayInPlayground(log);
                } else {
                  // Fallback redirect with query params
                  window.location.href = `/playground?model=${encodeURIComponent(log.requested_model)}`;
                }
              }}
              className="flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-colors"
              title="Open prompt and model in Playground for interactive testing"
            >
              <Play size={13} />
              <span>Replay in Playground</span>
            </button>

            <button
              onClick={onClose}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-medium transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
