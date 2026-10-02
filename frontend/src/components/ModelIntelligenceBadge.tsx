import React, { useState, useRef, useEffect, useCallback } from "react";
import { Brain, ExternalLink, Code2, Zap, Bot, Sparkles, CheckCircle2, Gauge, RefreshCw } from "lucide-react";
import { ModelRatingInfo, ModelLimitsInfo } from "../types";
import { apiRequest } from "../api/client";

interface ModelIntelligenceBadgeProps {
  modelId?: number;
  rating?: ModelRatingInfo;
  capabilities?: Record<string, any>;
  contextLength?: number;
  maxOutputTokens?: number;
  initialLimits?: ModelLimitsInfo;
  compact?: boolean;
  onLimitsFetched?: (limits: ModelLimitsInfo) => void;
}

function formatTokensCompact(tokens?: number): string {
  if (!tokens) return "—";
  if (tokens >= 1_000_000) {
    const m = (tokens / 1_000_000).toFixed(1).replace(/\.0$/, "");
    return `${m}M tokens`;
  }
  if (tokens >= 1_000) {
    const k = Math.round(tokens / 1_000);
    return `${k}k tokens`;
  }
  return `${tokens.toLocaleString()} tokens`;
}

export const ModelIntelligenceBadge: React.FC<ModelIntelligenceBadgeProps> = ({
  modelId,
  rating,
  capabilities,
  contextLength,
  maxOutputTokens,
  initialLimits,
  compact = false,
  onLimitsFetched,
}) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const badgeRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const closeTimerRef = useRef<number | null>(null);

  // Live limits state (loaded immediately from initialLimits provided by backend)
  const [limits, setLimits] = useState<ModelLimitsInfo | null>(initialLimits || null);
  const [loadingLimits, setLoadingLimits] = useState(false);
  const hasAttemptedFetch = useRef(false);

  const [coords, setCoords] = useState<{
    top: number;
    left: number;
    maxHeight: number;
    placeAbove: boolean;
  } | null>(null);

  const isReasoning =
    rating?.is_reasoning ||
    capabilities?.reasoning === true;

  const intel = rating?.intelligence_index;
  const coding = rating?.coding_index;
  const agentic = rating?.agentic_index;
  const speed = rating?.speed_tokens_per_sec;

  // Effective context and max output (favor fresh live API limits)
  const effContext = limits?.context_length ?? contextLength;
  const effMaxOutput = limits?.max_output_tokens ?? maxOutputTokens;

  const hasContext = effContext !== undefined && effContext !== null && effContext > 0;
  const hasMaxOutput = effMaxOutput !== undefined && effMaxOutput !== null && effMaxOutput > 0;
  const hasRateLimits = Boolean(
    (limits?.rate_limit_rpm !== undefined && limits?.rate_limit_rpm !== null) ||
    (limits?.rate_limit_tpm !== undefined && limits?.rate_limit_tpm !== null) ||
    (limits?.rate_limit_rpd !== undefined && limits?.rate_limit_rpd !== null) ||
    (limits?.remaining_requests !== undefined && limits?.remaining_requests !== null) ||
    (limits?.account_usage !== undefined && limits?.account_usage !== null) ||
    limits?.reset_requests
  );

  const hasAnyLimits = hasContext || hasMaxOutput || hasRateLimits;

  const computePosition = useCallback(() => {
    if (!badgeRef.current) return null;
    const rect = badgeRef.current.getBoundingClientRect();
    const tooltipWidth = 320;
    const gap = 8;
    const estimatedHeight = hasAnyLimits ? 380 : 260;

    const spaceAbove = rect.top;
    const spaceBelow = window.innerHeight - rect.bottom;
    const placeAbove = spaceBelow < estimatedHeight + 20 && spaceAbove > spaceBelow;

    let left = rect.left;
    if (left + tooltipWidth > window.innerWidth - 16) {
      left = window.innerWidth - tooltipWidth - 16;
    }
    if (left < 16) {
      left = 16;
    }

    const top = placeAbove ? rect.top - gap : rect.bottom + gap;
    const availableHeight = placeAbove ? rect.top - gap - 16 : window.innerHeight - top - 16;
    const maxHeight = Math.max(160, Math.min(500, availableHeight));

    return {
      top,
      left,
      maxHeight,
      placeAbove,
    };
  }, [hasAnyLimits]);

  const fetchLiveLimits = async () => {
    if (!modelId || loadingLimits) return;
    setLoadingLimits(true);
    try {
      const data = await apiRequest<ModelLimitsInfo>(`/api/admin/models/${modelId}/limits`);
      setLimits(data);
      if (onLimitsFetched) {
        onLimitsFetched(data);
      }
    } catch (err) {
      console.warn(`Could not fetch live API limits for model ${modelId}:`, err);
    } finally {
      setLoadingLimits(false);
    }
  };

  const handleMouseEnter = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    const nextCoords = computePosition();
    if (nextCoords) {
      setCoords(nextCoords);
      setShowTooltip(true);
    }

    // Only auto-probe if model had zero limits initially
    if (modelId && !hasAttemptedFetch.current && !limits && !hasAnyLimits) {
      hasAttemptedFetch.current = true;
      fetchLiveLimits();
    }
  };

  const keepTooltip = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  };

  const handleMouseLeave = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
    }
    closeTimerRef.current = window.setTimeout(() => {
      setShowTooltip(false);
    }, 250);
  };

  const handleToggleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    if (!showTooltip) {
      const nextCoords = computePosition();
      if (nextCoords) {
        setCoords(nextCoords);
        setShowTooltip(true);
      }
    } else {
      setShowTooltip(false);
    }
  };

  useEffect(() => {
    if (initialLimits) {
      setLimits(initialLimits);
    }
  }, [initialLimits]);

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  // Dismiss immediately on page/table scroll or window resize (matching ProxiesPage pattern)
  useEffect(() => {
    if (!showTooltip) return;

    const handleDismiss = () => {
      setShowTooltip(false);
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (
        badgeRef.current &&
        !badgeRef.current.contains(e.target as Node) &&
        tooltipRef.current &&
        !tooltipRef.current.contains(e.target as Node)
      ) {
        setShowTooltip(false);
      }
    };

    window.addEventListener("scroll", handleDismiss, true);
    window.addEventListener("resize", handleDismiss);
    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      window.removeEventListener("scroll", handleDismiss, true);
      window.removeEventListener("resize", handleDismiss);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showTooltip]);

  if (!rating || intel === undefined || intel === null) {
    if (isReasoning) {
      return (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono bg-amber-950/40 text-amber-300 border border-amber-500/30"
          title="Reasoning / Thinking Model"
        >
          <Sparkles size={11} className="text-amber-400" />
          <span>Reasoning</span>
        </span>
      );
    }
    return <span className="text-slate-600 font-mono text-[11px]">—</span>;
  }

  // Determine tier color based on Artificial Analysis intelligence index
  let badgeColor = "bg-slate-800/80 text-slate-300 border-slate-700/60";
  let dotColor = "bg-slate-400";
  let tierLabel = "Standard";

  if (intel >= 55) {
    badgeColor = "bg-emerald-950/60 text-emerald-300 border-emerald-500/40 shadow-xs shadow-emerald-950/40";
    dotColor = "bg-emerald-400";
    tierLabel = "Frontier / S-Tier";
  } else if (intel >= 35) {
    badgeColor = "bg-cyan-950/60 text-cyan-300 border-cyan-500/40 shadow-xs shadow-cyan-950/40";
    dotColor = "bg-cyan-400";
    tierLabel = "High / A-Tier";
  } else if (intel >= 15) {
    badgeColor = "bg-indigo-950/60 text-indigo-300 border-indigo-500/40 shadow-xs shadow-indigo-950/40";
    dotColor = "bg-indigo-400";
    tierLabel = "Medium / B-Tier";
  } else {
    badgeColor = "bg-amber-950/40 text-amber-300 border-amber-500/30";
    dotColor = "bg-amber-400";
    tierLabel = "Compact / Fast";
  }

  return (
    <>
      <div
        ref={badgeRef}
        className="inline-flex items-center gap-1.5 cursor-pointer select-none"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onClick={handleToggleClick}
      >
        {/* Intelligence index pill */}
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-mono font-semibold border transition-all hover:scale-105 ${badgeColor}`}
          title={`Artificial Analysis Intelligence Index: ${intel}`}
        >
          <Brain size={12} className="shrink-0 opacity-80" />
          <span>{intel.toFixed(1)}</span>
        </span>

        {/* Coding pill if available */}
        {!compact && coding !== undefined && coding !== null && (
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-900/90 border border-slate-700/60 text-slate-300 text-[10px] font-mono hover:border-slate-600 transition-colors"
            title={`Artificial Analysis Coding Index: ${coding}`}
          >
            <Code2 size={10} className="text-emerald-400 shrink-0" />
            <span>{coding.toFixed(1)}</span>
          </span>
        )}

        {/* Agentic Thinking pill (styled uniformly with coding pill) */}
        {!compact && agentic !== undefined && agentic !== null && (
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-900/90 border border-slate-700/60 text-slate-300 text-[10px] font-mono hover:border-slate-600 transition-colors"
            title={`Artificial Analysis Agentic Index: ${agentic}`}
          >
            <Bot size={10} className="text-purple-400 shrink-0" />
            <span>{agentic.toFixed(1)}</span>
          </span>
        )}

        {/* If no exact agentic score, but is a reasoning model, show reasoning badge */}
        {!compact && (agentic === undefined || agentic === null) && isReasoning && (
          <span
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-900/90 border border-slate-700/60 text-slate-300 text-[10px] font-mono"
            title="Reasoning / Thinking Model (CoT)"
          >
            <Sparkles size={10} className="text-amber-400 shrink-0" />
            <span>Thinking</span>
          </span>
        )}
      </div>

      {/* Floating Tooltip: Fixed position in viewport, immune to table overflow clipping, zero lag */}
      {showTooltip && coords && (
        <div
          ref={tooltipRef}
          className="w-[320px] max-w-[calc(100vw-24px)] pointer-events-auto"
          style={{
            position: "fixed",
            top: `${coords.top}px`,
            left: `${coords.left}px`,
            transform: coords.placeAbove ? "translateY(-100%)" : "none",
            zIndex: 99999,
          }}
          onMouseEnter={keepTooltip}
          onMouseLeave={handleMouseLeave}
        >
          {/* Hover bridge spanning gap between badge and tooltip */}
          <div
            className={`absolute left-0 right-0 h-3 pointer-events-auto ${
              coords.placeAbove ? "top-full" : "-top-3"
            }`}
          />

          {/* Inner scrollable card */}
          <div
            className="w-full p-3.5 rounded-xl bg-slate-900/98 backdrop-blur-md border border-slate-700/80 shadow-2xl text-xs text-slate-200 overflow-y-auto overscroll-contain custom-scrollbar relative"
            style={{
              maxHeight: `${coords.maxHeight}px`,
            }}
          >
            {/* Header */}
            <div className="sticky top-0 bg-slate-900/95 backdrop-blur-md -mx-3.5 -mt-3.5 px-3.5 pt-3.5 pb-2 mb-2.5 border-b border-slate-800/80 flex items-center justify-between z-10">
              <div className="flex items-center gap-2">
                <div className={`w-2.5 h-2.5 rounded-full ${dotColor} shadow-xs`} />
                <span className="font-semibold text-slate-100 text-sm">Artificial Analysis</span>
              </div>
              <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                {tierLabel}
              </span>
            </div>

            {/* Benchmark metrics: all styled consistently */}
            <div className="space-y-2.5">
              {/* Intelligence Index */}
              <div>
                <div className="flex justify-between items-center text-[11px] mb-1">
                  <span className="text-slate-400 flex items-center gap-1.5 font-medium">
                    <Brain size={12} className="text-indigo-400" />
                    Intelligence Index (Intel)
                  </span>
                  <span className="font-mono font-bold text-slate-100">{intel.toFixed(1)} / 100</span>
                </div>
                <div className="w-full bg-slate-800/80 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-indigo-500 h-full rounded-full transition-all"
                    style={{ width: `${Math.min(100, Math.max(0, intel))}%` }}
                  />
                </div>
              </div>

              {/* Coding Index */}
              {coding !== undefined && coding !== null && (
                <div>
                  <div className="flex justify-between items-center text-[11px] mb-1">
                    <span className="text-slate-400 flex items-center gap-1.5 font-medium">
                      <Code2 size={12} className="text-emerald-400" />
                      Coding Index (Coding)
                    </span>
                    <span className="font-mono font-bold text-slate-100">{coding.toFixed(1)} / 100</span>
                  </div>
                  <div className="w-full bg-slate-800/80 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-emerald-500 h-full rounded-full transition-all"
                      style={{ width: `${Math.min(100, Math.max(0, coding))}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Agentic Thinking (displayed consistently like other metrics) */}
              {agentic !== undefined && agentic !== null && (
                <div>
                  <div className="flex justify-between items-center text-[11px] mb-1">
                    <span className="text-slate-400 flex items-center gap-1.5 font-medium">
                      <Bot size={12} className="text-purple-400" />
                      Agentic Thinking (Agentic)
                    </span>
                    <span className="font-mono font-bold text-slate-100">{agentic.toFixed(1)} / 100</span>
                  </div>
                  <div className="w-full bg-slate-800/80 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-purple-500 h-full rounded-full transition-all"
                      style={{ width: `${Math.min(100, Math.max(0, agentic))}%` }}
                    />
                  </div>
                </div>
              )}

              {/* If no exact agentic score, but is a reasoning model */}
              {isReasoning && (agentic === undefined || agentic === null) && (
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-slate-400 flex items-center gap-1.5 font-medium">
                    <Sparkles size={12} className="text-amber-400" />
                    Reasoning Type
                  </span>
                  <span className="font-mono text-[10px] text-amber-300 bg-amber-950/40 px-1.5 py-0.5 rounded border border-amber-800/40">
                    Reasoning (CoT)
                  </span>
                </div>
              )}

              {/* Speed */}
              {speed !== undefined && speed !== null && (
                <div className="flex justify-between items-center text-[11px] pt-0.5">
                  <span className="text-slate-400 flex items-center gap-1.5">
                    <Zap size={11} className="text-amber-400" />
                    Generation Speed
                  </span>
                  <span className="font-mono text-slate-200">{speed.toFixed(0)} tokens/sec</span>
                </div>
              )}
            </div>

            {/* Model Limits Section: ONLY displayed if at least one limit is available */}
            {hasAnyLimits && (
              <div className="mt-3 pt-2.5 border-t border-slate-800/80 space-y-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-300 font-semibold flex items-center gap-1.5">
                    <Gauge size={12} className="text-indigo-400" />
                    Model Limits
                  </span>
                  <div className="flex items-center gap-1.5">
                    {loadingLimits ? (
                      <span className="text-[10px] text-indigo-400 animate-pulse flex items-center gap-1 font-mono">
                        <RefreshCw size={9} className="animate-spin" />
                        Querying API...
                      </span>
                    ) : limits?.source === "direct_api" ? (
                      <span className="text-[10px] text-emerald-400 font-mono flex items-center gap-1">
                        <CheckCircle2 size={10} />
                        Live API
                      </span>
                    ) : modelId ? (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          fetchLiveLimits();
                        }}
                        className="text-[10px] text-slate-400 hover:text-indigo-300 transition-colors flex items-center gap-0.5 cursor-pointer"
                        title="Query live limits from API"
                      >
                        <RefreshCw size={9} />
                        <span>Refresh API</span>
                      </button>
                    ) : null}
                  </div>
                </div>

                {/* Context & Max Output: Only render if at least one is known */}
                {(hasContext || hasMaxOutput) && (
                  <div
                    className={`grid ${
                      hasContext && hasMaxOutput ? "grid-cols-2" : "grid-cols-1"
                    } gap-2 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80 text-[11px]`}
                  >
                    {hasContext && (
                      <div>
                        <span className="text-slate-500 block text-[10px] mb-0.5">Context (Input)</span>
                        <span className="font-mono font-medium text-slate-200 block text-[11px]">
                          {formatTokensCompact(effContext)}
                        </span>
                        {effContext && effContext >= 1_000 && (
                          <span className="text-[9px] text-slate-400 font-mono block">
                            {effContext.toLocaleString()}
                          </span>
                        )}
                      </div>
                    )}
                    {hasMaxOutput && (
                      <div>
                        <span className="text-slate-500 block text-[10px] mb-0.5">Max Output</span>
                        <span className="font-mono font-medium text-slate-200 block text-[11px]">
                          {formatTokensCompact(effMaxOutput)}
                        </span>
                        {effMaxOutput && effMaxOutput >= 1_000 && (
                          <span className="text-[9px] text-slate-400 font-mono block">
                            {effMaxOutput.toLocaleString()}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Live Rate Limits from API / Verified Catalog */}
                {hasRateLimits && (
                  <div className="space-y-1 bg-slate-950/40 p-2 rounded-lg border border-slate-800/60 text-[10px] font-mono">
                    {limits?.rate_limit_rpm !== undefined && limits?.rate_limit_rpm !== null && (
                      <div className="flex justify-between items-center text-slate-300">
                        <span className="text-slate-400 flex items-center gap-1">
                          <Zap size={10} className="text-amber-400" />
                          RPM Limit (minute):
                        </span>
                        <span className="text-amber-300 font-semibold">
                          {limits.rate_limit_rpm.toLocaleString()} RPM
                          {limits.remaining_requests !== undefined && limits.remaining_requests !== null && (
                            <span className="text-slate-400 font-normal ml-1">
                              (rem. {limits.remaining_requests})
                            </span>
                          )}
                        </span>
                      </div>
                    )}

                    {limits?.rate_limit_rpd !== undefined && limits?.rate_limit_rpd !== null && (
                      <div className="flex justify-between items-center text-slate-300">
                        <span className="text-slate-400 flex items-center gap-1">
                          <span>📅</span>
                          Daily Limit (RPD):
                        </span>
                        <span className="text-indigo-300 font-semibold">
                          {limits.rate_limit_rpd.toLocaleString()} RPD
                        </span>
                      </div>
                    )}

                    {limits?.rate_limit_tpm !== undefined && limits?.rate_limit_tpm !== null && (
                      <div className="flex justify-between items-center text-slate-300">
                        <span className="text-slate-400">TPM Limit (tokens):</span>
                        <span className="text-cyan-300 font-semibold">
                          {limits.rate_limit_tpm.toLocaleString()} TPM
                        </span>
                      </div>
                    )}

                    {limits?.reset_requests && (
                      <div className="flex justify-between items-center text-slate-400">
                        <span>Limit Reset:</span>
                        <span className="text-slate-300">{limits.reset_requests}</span>
                      </div>
                    )}

                    {limits?.account_usage !== undefined && limits?.account_usage !== null && (
                      <div className="flex justify-between items-center text-slate-400">
                        <span>Account Usage:</span>
                        <span className="text-emerald-400">
                          ${limits.account_usage.toFixed(2)}
                          {limits.account_limit ? ` / $${limits.account_limit}` : ""}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Model Creator & External Link */}
            <div className="sticky bottom-0 bg-slate-900/95 backdrop-blur-md -mx-3.5 -mb-3.5 px-3.5 pb-3.5 pt-2 mt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[10px]">
              {rating.model_creator ? (
                <span className="text-slate-400">
                  Provider: <span className="text-slate-200 font-medium">{rating.model_creator}</span>
                </span>
              ) : (
                <span className="text-slate-500">Artificial Analysis</span>
              )}

              {rating.source_url && (
                <a
                  href={rating.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
                >
                  <span>Benchmarks</span>
                  <ExternalLink size={10} />
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
