import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, Clock, GitFork, ArrowRight, Zap, RefreshCw, ChevronDown, ChevronRight } from "lucide-react";
import { RequestAttempt } from "../types";
import { StatusBadge } from "./StatusBadge";

interface LogWaterfallTraceProps {
  attempts: RequestAttempt[];
  totalLatencyMs: number;
  status: string;
  metadata?: Record<string, any>;
}

export const LogWaterfallTrace: React.FC<LogWaterfallTraceProps> = ({
  attempts,
  totalLatencyMs,
  status,
  metadata,
}) => {
  const [expandedDrafts, setExpandedDrafts] = useState<Record<string, boolean>>({});
  const isFusion = !!metadata?.participants;
  const participants = metadata?.participants || [];

  // If Fusion mode
  if (isFusion && participants.length > 0) {
    const judge = metadata?.judge;
    const maxParticipantLatency = Math.max(
      ...participants.map((p: any) => p.latency_ms || 0),
      judge?.latency_ms || 0,
      totalLatencyMs || 1
    );

    return (
      <div className="space-y-3 bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitFork size={15} className="text-amber-400" />
            <span className="text-xs font-semibold text-slate-200">
              Fusion Parallel Execution (Strategy: {metadata.strategy || "ensemble"})
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Total: {totalLatencyMs.toFixed(0)} ms
          </span>
        </div>

        <div className="space-y-2 pt-1">
          {participants.map((p: any, idx: number) => {
            const lat = p.latency_ms || 0;
            const pct = Math.max(8, Math.min(100, Math.round((lat / maxParticipantLatency) * 100)));
            const isSuccess = p.status === "SUCCESS";

            return (
              <div
                key={idx}
                className="bg-slate-900/80 border border-slate-800 rounded-lg p-2.5 space-y-1.5 text-xs"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-amber-950/60 text-amber-300 border border-amber-800/60 font-bold">
                      {p.label || `Candidate #${idx + 1}`}
                    </span>
                    <span className="font-mono text-slate-200">{p.model_name || p.canonical_slug || "Model"}</span>
                    {p.provider_name && (
                      <span className="text-slate-400 text-[11px]">({p.provider_name})</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-slate-300">{lat} ms</span>
                    <StatusBadge status={p.status || "UNKNOWN"} size="sm" />
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      isSuccess ? "bg-amber-500" : "bg-rose-500"
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>

                {p.content && (
                  <div className="pt-0.5">
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedDrafts((prev) => ({
                          ...prev,
                          [`cand_${idx}`]: !prev[`cand_${idx}`],
                        }))
                      }
                      className="text-[11px] text-amber-400 hover:text-amber-300 flex items-center gap-1 font-medium transition-colors cursor-pointer"
                    >
                      {expandedDrafts[`cand_${idx}`] ? (
                        <ChevronDown size={12} />
                      ) : (
                        <ChevronRight size={12} />
                      )}
                      <span>
                        {expandedDrafts[`cand_${idx}`]
                          ? "Hide response draft"
                          : "Show candidate response draft"}
                      </span>
                    </button>
                    {expandedDrafts[`cand_${idx}`] && (
                      <div className="mt-1.5 p-2.5 bg-slate-950 rounded-lg border border-slate-800 font-mono text-[11px] text-slate-200 whitespace-pre-wrap max-h-56 overflow-y-auto leading-relaxed select-text">
                        {p.content}
                      </div>
                    )}
                  </div>
                )}

                {p.error && (
                  <div className="mt-1 text-[11px] text-rose-300 font-mono bg-rose-950/40 px-2 py-0.5 rounded border border-rose-900/40 truncate" title={p.error}>
                    {p.error}
                  </div>
                )}
              </div>
            );
          })}

          {judge && (
            <div className="bg-purple-950/30 border border-purple-800/60 rounded-lg p-2.5 space-y-1.5 text-xs mt-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-purple-900/60 text-purple-200 border border-purple-700/60 font-bold">
                    ⚖️ Judge (Synthesis)
                  </span>
                  <span className="font-mono text-purple-100 font-semibold">{judge.model_name || "Judge"}</span>
                  {judge.provider_name && (
                    <span className="text-purple-300/70 text-[11px]">({judge.provider_name})</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-purple-200">{judge.latency_ms || 0} ms</span>
                  <StatusBadge status={judge.status || "UNKNOWN"} size="sm" />
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    judge.status === "SUCCESS" ? "bg-purple-500" : "bg-rose-500"
                  }`}
                  style={{ width: `${Math.max(8, Math.min(100, Math.round(((judge.latency_ms || 0) / maxParticipantLatency) * 100)))}%` }}
                />
              </div>

              {(metadata?.deliberation || judge.reasoning) && (
                <div className="pt-0.5">
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedDrafts((prev) => ({
                        ...prev,
                        judge: !prev.judge,
                      }))
                    }
                    className="text-[11px] text-purple-300 hover:text-purple-200 flex items-center gap-1 font-medium transition-colors cursor-pointer"
                  >
                    {expandedDrafts.judge ? (
                      <ChevronDown size={12} />
                    ) : (
                      <ChevronRight size={12} />
                    )}
                    <span>
                      {expandedDrafts.judge
                        ? "Hide reasoning & synthesis"
                        : "Show judge reasoning & synthesis"}
                    </span>
                  </button>
                  {expandedDrafts.judge && (
                    <div className="mt-1.5 p-2.5 bg-slate-950 rounded-lg border border-purple-900/60 font-mono text-[11px] text-purple-200 whitespace-pre-wrap max-h-56 overflow-y-auto leading-relaxed select-text">
                      {metadata?.deliberation || judge.reasoning}
                    </div>
                  )}
                </div>
              )}

              {judge.error && (
                <div className="mt-1 text-[11px] text-rose-300 font-mono bg-rose-950/40 px-2 py-0.5 rounded border border-rose-900/40 truncate" title={judge.error}>
                  {judge.error}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // If no attempts logged
  if (!attempts || attempts.length === 0) {
    return (
      <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 text-xs text-slate-400 text-center">
        Direct request without recorded intermediate rotation attempts.
      </div>
    );
  }

  // Priority / Direct routing attempts waterfall
  const maxAttemptLatency = Math.max(
    ...attempts.map((a) => a.latency_ms || 0),
    totalLatencyMs || 1
  );

  const successfulAttempt = attempts.find((a) => a.status === "SUCCESS");
  const hasFallbackRescue = attempts.length > 1 && !!successfulAttempt;

  return (
    <div className="space-y-3 bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock size={15} className="text-indigo-400" />
          <span className="text-xs font-semibold text-slate-200">
            Waterfall Attempt Timeline ({attempts.length}{" "}
            {attempts.length === 1 ? "attempt" : "attempts"})
          </span>
        </div>
        <span className="text-[11px] font-mono text-slate-400">
          Total Latency: <strong className="text-slate-200">{totalLatencyMs.toFixed(0)} ms</strong>
        </span>
      </div>

      {/* Fallback rescue notice */}
      {hasFallbackRescue && (
        <div className="flex items-center gap-2 px-3 py-2 bg-purple-950/40 border border-purple-800/60 rounded-lg text-xs text-purple-200">
          <RefreshCw size={14} className="text-purple-400 shrink-0" />
          <span>
            Request successfully recovered on <strong>attempt #{successfulAttempt.attempt_number}</strong> (
            {successfulAttempt.model_name}) after {successfulAttempt.attempt_number - 1} failed steps.
          </span>
        </div>
      )}

      {/* Steps List */}
      <div className="space-y-2">
        {attempts.map((att, idx) => {
          const lat = att.latency_ms || 0;
          const pct = Math.max(6, Math.min(100, Math.round((lat / maxAttemptLatency) * 100)));
          const isSuccess = att.status === "SUCCESS";
          const isRateLimit =
            att.http_status === 429 || att.error_category === "RATE_LIMITED";
          const isSkipped = att.status === "SKIPPED";

          const barColor = isSuccess
            ? "bg-emerald-500"
            : isRateLimit
            ? "bg-amber-500"
            : isSkipped
            ? "bg-purple-500"
            : "bg-rose-500";

          return (
            <div
              key={att.id || idx}
              className={`p-2.5 rounded-lg border text-xs transition-colors ${
                isSuccess
                  ? "bg-slate-900/90 border-emerald-900/40"
                  : isRateLimit
                  ? "bg-slate-900/90 border-amber-900/40"
                  : "bg-slate-900/90 border-rose-950/60"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className={`w-5 h-5 rounded-full text-[10px] font-mono font-bold flex items-center justify-center shrink-0 ${
                      isSuccess
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-700"
                        : "bg-rose-950 text-rose-300 border border-rose-800"
                    }`}
                  >
                    #{att.attempt_number}
                  </span>

                  <span className="font-semibold text-slate-100 font-mono truncate" title={att.model_name}>
                    {att.model_name}
                  </span>

                  <span className="text-slate-400 text-[11px] truncate">
                    {att.provider_name} • {att.credential_name}
                  </span>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                  {att.http_status && (
                    <span
                      className={`px-1.5 py-0.2 rounded text-[10px] font-mono border ${
                        att.http_status === 200
                          ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/60"
                          : att.http_status === 429
                          ? "bg-amber-950/60 text-amber-300 border-amber-800/60"
                          : "bg-rose-950/60 text-rose-300 border-rose-800/60"
                      }`}
                    >
                      HTTP {att.http_status}
                    </span>
                  )}
                  <span className="font-mono text-slate-300 font-medium">{lat} ms</span>
                  <StatusBadge status={att.status} size="sm" />
                </div>
              </div>

              {/* Progress visual bar */}
              <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${barColor}`}
                  style={{ width: `${pct}%` }}
                />
              </div>

              {/* Error reason if present */}
              {att.error_message && (
                <div className="mt-1.5 text-[11px] text-rose-300/90 font-mono bg-rose-950/30 px-2 py-1 rounded border border-rose-900/30 truncate" title={att.error_message}>
                  {att.error_category && <strong className="text-rose-400 mr-1">[{att.error_category}]</strong>}
                  {att.error_message}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
