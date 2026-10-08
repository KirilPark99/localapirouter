import type { RequestLog } from "../types";

type Parameters = Record<string, unknown>;
export interface LogUsage {
  input_tokens?: number | null;
  output_tokens?: number | null;
  cached_tokens?: number | null;
  new_tokens?: number | null;
  reasoning_tokens?: number | null;
  source?: string;
}
interface Dispatch {
  provider?: string;
  model?: string;
  stream?: boolean;
  parameters: Parameters;
  status?: string;
  latency_ms?: number;
  usage: LogUsage | null;
}
interface CompressionStage {
  stage_id?: string;
  stage_name?: string;
  tokens_before?: number;
  tokens_after?: number;
  duration_ms?: number;
  advanced?: boolean;
  note?: string;
  warning?: string;
}
interface Compression {
  telemetry_disabled?: boolean;
  compressed?: boolean;
  disabled?: boolean;
  bypass?: boolean;
  below_threshold?: boolean;
  no_active_stages?: boolean;
  error?: string;
  tokens_before?: number;
  tokens_after?: number;
  tokens_saved?: number;
  savings_percent?: number;
  duration_ms?: number;
  token_count_is_estimate?: boolean;
  breakdown?: CompressionStage[];
}

const record = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
export const tokenCount = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
export const telemetryValue = (value: unknown): string => {
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : "—";
  if (typeof value === "boolean") return String(value);
  return typeof value === "string" && value.length > 0 ? value : "—";
};

export const requestParameterNames = [
  "stream", "reasoning_effort", "temperature", "top_p", "max_tokens",
  "thinking_budget_tokens", "tools_count", "messages_count",
  "seed", "parallel_tool_calls",
] as const;

export function formatLogCost(log: RequestLog, digits = 6): string {
  const cost = record(record(record(log.metadata_json).telemetry).cost);
  if (cost.complete === false) {
    return log.estimated_cost_usd > 0 ? `≥ $${log.estimated_cost_usd.toFixed(digits)} (partial)` : "Unknown";
  }
  return `$${log.estimated_cost_usd.toFixed(digits)}`;
}

export function getRequestLogTelemetry(log: RequestLog) {
  const telemetry = record(record(log.metadata_json).telemetry);
  const dispatches: Dispatch[] = Array.isArray(telemetry.dispatches)
    ? telemetry.dispatches.map((value) => {
        const dispatch = record(value);
        return {
          ...dispatch,
          status: typeof dispatch.status === "string" ? dispatch.status : undefined,
          parameters: record(dispatch.parameters),
          usage: dispatch.usage && typeof dispatch.usage === "object"
            ? record(dispatch.usage) as LogUsage : null,
        } as Dispatch;
      }) : [];
  const usage = record(telemetry.usage) as LogUsage;
  const hasUsage = Object.keys(usage).length > 0;
  const localCacheHit = telemetry.response_cache === "HIT" || log.mode === "CACHE";
  // Old zero counters do not distinguish unreported usage from a real zero.
  const cached = hasUsage ? tokenCount(usage.cached_tokens)
    : log.cached_tokens > 0 ? tokenCount(log.cached_tokens) : null;
  const input = tokenCount(hasUsage ? usage.input_tokens : log.input_tokens);
  const output = tokenCount(hasUsage ? usage.output_tokens : log.output_tokens);
  const reasoning = hasUsage ? tokenCount(usage.reasoning_tokens)
    : log.reasoning_tokens > 0 ? tokenCount(log.reasoning_tokens) : null;
  const compression = Object.keys(record(telemetry.compression)).length
    ? record(telemetry.compression) as Compression : null;
  const stages: CompressionStage[] = Array.isArray(compression?.breakdown)
    ? compression.breakdown.map((stage) => record(stage) as CompressionStage) : [];
  const efforts = [...new Set(dispatches.map((dispatch) => telemetryValue(dispatch.parameters.reasoning_effort)))];
  return {
    requested: record(telemetry.requested_parameters),
    dispatches,
    dispatchesKnown: Array.isArray(telemetry.dispatches),
    compression,
    stages,
    usage: {
      input_tokens: localCacheHit ? 0 : input,
      output_tokens: localCacheHit ? 0 : output,
      cached_tokens: localCacheHit ? null : cached,
      new_tokens: localCacheHit ? null : hasUsage ? tokenCount(usage.new_tokens) : null,
      reasoning_tokens: localCacheHit ? null : reasoning,
      source: localCacheHit ? "local_response_cache" : usage.source,
    },
    savedResponseUsage: telemetry.saved_response_usage,
    localCacheHit,
    responseCache: localCacheHit ? "HIT" : telemetryValue(telemetry.response_cache),
    effectiveEffort: efforts.length ? efforts.join(" / ") : "—",
  };
}
