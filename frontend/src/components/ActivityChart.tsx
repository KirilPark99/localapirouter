import React, { useState, useMemo, useRef } from "react";
import {
  TrendingUp,
  BarChart2,
  Activity,
  Zap,
  AlertTriangle,
  Clock,
  Sparkles,
} from "lucide-react";
import { TimeBucketStatsItem } from "../types";

interface ActivityChartProps {
  timeline: TimeBucketStatsItem[];
  period: string;
  granularity?: "hour" | "day";
  onGranularityChange?: (g: "hour" | "day") => void;
  formatNum: (n: number) => string;
}

type ChartType = "area" | "bar";
type MetricType = "requests" | "tokens" | "issues" | "latency";

export const ActivityChart: React.FC<ActivityChartProps> = ({
  timeline,
  period,
  granularity = "hour",
  onGranularityChange,
  formatNum,
}) => {
  const [chartType, setChartType] = useState<ChartType>("area");
  const [metric, setMetric] = useState<MetricType>("requests");
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Colors & Configuration per metric
  const metricConfig = useMemo(() => {
    switch (metric) {
      case "tokens":
        return {
          title: "Tokens",
          unit: "tok",
          color: "#f59e0b", // amber-500
          gradientFrom: "rgba(245, 158, 11, 0.45)",
          gradientTo: "rgba(245, 158, 11, 0.0)",
          stroke: "#fbbf24",
          badgeBg: "bg-amber-500/10 text-amber-300 border-amber-500/30",
          getValue: (t: TimeBucketStatsItem) => t.tokens,
        };
      case "issues":
        return {
          title: "Errors & Fallbacks",
          unit: "events",
          color: "#f43f5e", // rose-500
          gradientFrom: "rgba(244, 63, 94, 0.45)",
          gradientTo: "rgba(244, 63, 94, 0.0)",
          stroke: "#fb7185",
          badgeBg: "bg-rose-500/10 text-rose-300 border-rose-500/30",
          getValue: (t: TimeBucketStatsItem) => t.errors + t.fallbacks,
        };
      case "latency":
        return {
          title: "Latency (ms)",
          unit: "ms",
          color: "#38bdf8", // sky-400
          gradientFrom: "rgba(56, 189, 248, 0.45)",
          gradientTo: "rgba(56, 189, 248, 0.0)",
          stroke: "#38bdf8",
          badgeBg: "bg-sky-500/10 text-sky-300 border-sky-500/30",
          getValue: (t: TimeBucketStatsItem) => Math.round(t.avg_latency_ms || 0),
        };
      case "requests":
      default:
        return {
          title: "Requests",
          unit: "req",
          color: "#6366f1", // indigo-500
          gradientFrom: "rgba(99, 102, 241, 0.45)",
          gradientTo: "rgba(99, 102, 241, 0.0)",
          stroke: "#818cf8",
          badgeBg: "bg-indigo-500/10 text-indigo-300 border-indigo-500/30",
          getValue: (t: TimeBucketStatsItem) => t.requests,
        };
    }
  }, [metric]);

  // Metric values list
  const values = useMemo(() => {
    return timeline.map((t) => metricConfig.getValue(t));
  }, [timeline, metricConfig]);

  // Max value calculation
  const maxVal = useMemo(() => {
    const rawMax = Math.max(...values, 0);
    if (rawMax <= 5) return 5;
    if (rawMax <= 10) return 10;
    // Round up to clean ceiling (e.g. 45 -> 50, 82 -> 100)
    const magnitude = Math.pow(10, Math.floor(Math.log10(rawMax)));
    return Math.ceil(rawMax / magnitude) * magnitude;
  }, [values]);

  // Aggregated summary stats for the strip
  const statsSummary = useMemo(() => {
    const totalRequests = timeline.reduce((s, t) => s + t.requests, 0);
    const totalTokens = timeline.reduce((s, t) => s + t.tokens, 0);
    const totalErrors = timeline.reduce((s, t) => s + t.errors, 0);
    const totalFallbacks = timeline.reduce((s, t) => s + t.fallbacks, 0);

    let peakIdx = 0;
    let peakVal = 0;
    values.forEach((v, idx) => {
      if (v > peakVal) {
        peakVal = v;
        peakIdx = idx;
      }
    });

    const activePoints = values.filter((v) => v > 0).length;
    const avgValue = values.length > 0 ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : 0;

    return {
      totalRequests,
      totalTokens,
      totalErrors,
      totalFallbacks,
      peakVal,
      peakTime: timeline[peakIdx]?.time_label || "—",
      activePoints,
      avgValue,
    };
  }, [timeline, values]);

  // SVG Chart Geometry
  const svgWidth = 1000;
  const svgHeight = 220;
  const padLeft = 45;
  const padRight = 20;
  const padTop = 20;
  const padBottom = 30;
  const chartW = svgWidth - padLeft - padRight;
  const chartH = svgHeight - padTop - padBottom;

  // Compute (x, y) coordinates for area/line chart
  const points = useMemo(() => {
    if (timeline.length === 0) return [];
    if (timeline.length === 1) {
      const y = padTop + chartH - (values[0] / maxVal) * chartH;
      return [{ x: padLeft + chartW / 2, y, val: values[0], item: timeline[0], idx: 0 }];
    }
    const step = chartW / (timeline.length - 1);
    return timeline.map((item, idx) => {
      const x = padLeft + idx * step;
      const y = padTop + chartH - (values[idx] / maxVal) * chartH;
      return { x, y, val: values[idx], item, idx };
    });
  }, [timeline, values, maxVal, chartW, chartH]);

  // Build smooth SVG Bézier path
  const { linePath, areaPath } = useMemo(() => {
    if (points.length === 0) return { linePath: "", areaPath: "" };
    if (points.length === 1) {
      const pt = points[0];
      return {
        linePath: `M ${pt.x - 20} ${pt.y} L ${pt.x + 20} ${pt.y}`,
        areaPath: `M ${pt.x - 20} ${pt.y} L ${pt.x + 20} ${pt.y} L ${pt.x + 20} ${padTop + chartH} L ${pt.x - 20} ${padTop + chartH} Z`,
      };
    }

    // Build smooth cubic bezier curve
    let d = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const curr = points[i];
      const next = points[i + 1];
      const mx = (curr.x + next.x) / 2;
      d += ` C ${mx} ${curr.y}, ${mx} ${next.y}, ${next.x} ${next.y}`;
    }

    const firstX = points[0].x;
    const lastX = points[points.length - 1].x;
    const bottomY = padTop + chartH;
    const aPath = `${d} L ${lastX} ${bottomY} L ${firstX} ${bottomY} Z`;

    return { linePath: d, areaPath: aPath };
  }, [points, chartH]);

  // Handle mouse move over SVG to find nearest hovered point
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement | HTMLDivElement>) => {
    if (!containerRef.current || points.length === 0) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, (mouseX - (padLeft * rect.width) / svgWidth) / ((chartW * rect.width) / svgWidth)));
    const targetIdx = Math.round(ratio * (points.length - 1));
    if (targetIdx >= 0 && targetIdx < points.length) {
      setHoveredIdx(targetIdx);
    }
  };

  const handleMouseLeave = () => {
    setHoveredIdx(null);
  };

  // Select evenly spaced X-axis labels (max 8 labels)
  const xLabels = useMemo(() => {
    if (points.length === 0) return [];
    if (points.length <= 8) return points;
    const step = Math.ceil(points.length / 8);
    return points.filter((_, idx) => idx % step === 0 || idx === points.length - 1);
  }, [points]);

  // Current active hovered item
  const activeItem = hoveredIdx !== null && timeline[hoveredIdx] ? timeline[hoveredIdx] : null;

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-3.5 shadow-sm">
      {/* Top Header Controls Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-950/80 border border-indigo-800/80 flex items-center justify-center text-indigo-400">
            <TrendingUp size={16} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-slate-100">
                Activity Timeline
              </h3>
              <span className="text-[10px] bg-slate-800 text-indigo-300 font-mono px-2 py-0.5 rounded-full border border-slate-700">
                {timeline.length} {granularity === "hour" ? "hours" : "days"}
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Continuous timeline of requests, tokens, and errors
            </p>
          </div>
        </div>

        {/* Action Controls: Granularity, Chart Type, Metric */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Granularity Switcher */}
          {onGranularityChange && (
            <div className="flex items-center bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[11px] font-medium">
              <button
                type="button"
                onClick={() => onGranularityChange("hour")}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  granularity === "hour"
                    ? "bg-indigo-600 text-white font-semibold shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
                title="Group by hours"
              >
                Hourly
              </button>
              <button
                type="button"
                onClick={() => onGranularityChange("day")}
                className={`px-2.5 py-1 rounded-md transition-colors ${
                  granularity === "day"
                    ? "bg-indigo-600 text-white font-semibold shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
                title="Group by days"
              >
                Daily
              </button>
            </div>
          )}

          {/* Chart Type Toggle */}
          <div className="flex items-center bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[11px]">
            <button
              type="button"
              onClick={() => setChartType("area")}
              className={`p-1.5 rounded-md flex items-center gap-1 transition-colors ${
                chartType === "area"
                  ? "bg-slate-800 text-indigo-300 font-medium"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Spline Area Chart"
            >
              <Activity size={13} />
              <span className="hidden sm:inline">Line</span>
            </button>
            <button
              type="button"
              onClick={() => setChartType("bar")}
              className={`p-1.5 rounded-md flex items-center gap-1 transition-colors ${
                chartType === "bar"
                  ? "bg-slate-800 text-indigo-300 font-medium"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Bar Chart"
            >
              <BarChart2 size={13} />
              <span className="hidden sm:inline">Bars</span>
            </button>
          </div>

          {/* Metric Selector Buttons */}
          <div className="flex items-center bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[11px] font-medium">
            <button
              type="button"
              onClick={() => setMetric("requests")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                metric === "requests"
                  ? "bg-indigo-600 text-white font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Requests
            </button>
            <button
              type="button"
              onClick={() => setMetric("tokens")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                metric === "tokens"
                  ? "bg-amber-600 text-white font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Tokens
            </button>
            <button
              type="button"
              onClick={() => setMetric("issues")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                metric === "issues"
                  ? "bg-rose-600 text-white font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Issues
            </button>
            <button
              type="button"
              onClick={() => setMetric("latency")}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                metric === "latency"
                  ? "bg-sky-600 text-white font-semibold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Latency
            </button>
          </div>
        </div>
      </div>

      {/* Mini Stats Summary Cards Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-0.5">
        <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-400 font-medium">Period Total</div>
            <div className="text-sm font-bold font-mono text-slate-100">
              {metric === "tokens"
                ? formatNum(statsSummary.totalTokens)
                : metric === "latency"
                ? `${statsSummary.avgValue} ms`
                : formatNum(statsSummary.totalRequests)}
            </div>
          </div>
          <div className="p-1.5 rounded-md bg-indigo-950/60 text-indigo-400 border border-indigo-800/40">
            <Zap size={13} />
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-400 font-medium">Activity Peak</div>
            <div className="text-sm font-bold font-mono text-amber-300">
              {formatNum(statsSummary.peakVal)} {metricConfig.unit}
            </div>
            <div className="text-[9px] text-slate-400 truncate max-w-[120px]">
              {statsSummary.peakTime}
            </div>
          </div>
          <div className="p-1.5 rounded-md bg-amber-950/60 text-amber-400 border border-amber-800/40">
            <Sparkles size={13} />
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-400 font-medium">Avg / Step</div>
            <div className="text-sm font-bold font-mono text-slate-200">
              {formatNum(statsSummary.avgValue)} {metricConfig.unit}
            </div>
            <div className="text-[9px] text-slate-400">
              {statsSummary.activePoints} active intervals
            </div>
          </div>
          <div className="p-1.5 rounded-md bg-slate-900 text-slate-400 border border-slate-800">
            <Clock size={13} />
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-400 font-medium">Errors / Fallbacks</div>
            <div className="text-sm font-bold font-mono text-rose-300">
              {statsSummary.totalErrors} / {statsSummary.totalFallbacks}
            </div>
            <div className="text-[9px] text-purple-300">
              {statsSummary.totalRequests > 0
                ? `${Math.round((statsSummary.totalFallbacks / statsSummary.totalRequests) * 100)}% fallback`
                : "0% fallback"}
            </div>
          </div>
          <div className="p-1.5 rounded-md bg-rose-950/60 text-rose-400 border border-rose-800/40">
            <AlertTriangle size={13} />
          </div>
        </div>
      </div>

      {/* Main Chart Canvas Container */}
      <div
        ref={containerRef}
        className="relative bg-slate-950/80 border border-slate-800/80 rounded-xl p-2 select-none overflow-hidden"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {timeline.length === 0 ? (
          <div className="h-56 flex flex-col items-center justify-center text-xs text-slate-500">
            <Activity size={24} className="mb-2 opacity-40 text-slate-400" />
            <span>No activity data for the selected period</span>
          </div>
        ) : chartType === "area" ? (
          /* ================= MODE 1: SMOOTH SVG AREA CHART ================= */
          <div className="relative w-full h-56">
            <svg
              viewBox={`0 0 ${svgWidth} ${svgHeight}`}
              className="w-full h-full overflow-visible"
              preserveAspectRatio="none"
            >
              <defs>
                <linearGradient id="metricAreaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={metricConfig.color} stopOpacity="0.45" />
                  <stop offset="85%" stopColor={metricConfig.color} stopOpacity="0.05" />
                  <stop offset="100%" stopColor={metricConfig.color} stopOpacity="0.0" />
                </linearGradient>
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              {/* Horizontal Grid Lines & Y-Axis Labels */}
              {[0, 0.25, 0.5, 0.75, 1.0].map((frac, i) => {
                const y = padTop + chartH - frac * chartH;
                const labelVal = Math.round(frac * maxVal);
                return (
                  <g key={`grid-${i}`}>
                    <line
                      x1={padLeft}
                      y1={y}
                      x2={svgWidth - padRight}
                      y2={y}
                      stroke="#334155"
                      strokeDasharray={i === 0 ? "none" : "3 3"}
                      strokeOpacity={i === 0 ? "0.6" : "0.35"}
                      strokeWidth="1"
                    />
                    <text
                      x={padLeft - 8}
                      y={y + 3.5}
                      textAnchor="end"
                      fill="#64748b"
                      fontSize="9"
                      fontFamily="monospace"
                    >
                      {formatNum(labelVal)}
                    </text>
                  </g>
                );
              })}

              {/* X-Axis Horizontal Baseline */}
              <line
                x1={padLeft}
                y1={padTop + chartH}
                x2={svgWidth - padRight}
                y2={padTop + chartH}
                stroke="#475569"
                strokeWidth="1"
              />

              {/* Area Gradient Fill */}
              {areaPath && (
                <path d={areaPath} fill="url(#metricAreaGradient)" />
              )}

              {/* Line Curve */}
              {linePath && (
                <path
                  d={linePath}
                  fill="none"
                  stroke={metricConfig.stroke}
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  filter="url(#glow)"
                />
              )}

              {/* Data Point Dots (shown if not too many points) */}
              {points.length <= 48 &&
                points.map((pt, i) => (
                  <circle
                    key={`dot-${i}`}
                    cx={pt.x}
                    cy={pt.y}
                    r={hoveredIdx === i ? 5 : pt.val > 0 ? 2.5 : 1}
                    fill={hoveredIdx === i ? "#ffffff" : metricConfig.stroke}
                    stroke={hoveredIdx === i ? metricConfig.color : "#0f172a"}
                    strokeWidth="1.5"
                    className="transition-all duration-150"
                  />
                ))}

              {/* Hover Crosshair Vertical Line */}
              {hoveredIdx !== null && points[hoveredIdx] && (
                <g>
                  <line
                    x1={points[hoveredIdx].x}
                    y1={padTop}
                    x2={points[hoveredIdx].x}
                    y2={padTop + chartH}
                    stroke="#94a3b8"
                    strokeWidth="1"
                    strokeDasharray="3 3"
                    strokeOpacity="0.8"
                  />
                  <circle
                    cx={points[hoveredIdx].x}
                    cy={points[hoveredIdx].y}
                    r="6"
                    fill={metricConfig.stroke}
                    stroke="#ffffff"
                    strokeWidth="2"
                    filter="url(#glow)"
                  />
                </g>
              )}

              {/* X-Axis Time Labels */}
              {xLabels.map((pt, i) => (
                <text
                  key={`xlabel-${i}`}
                  x={pt.x}
                  y={svgHeight - 8}
                  textAnchor={i === 0 ? "start" : i === xLabels.length - 1 ? "end" : "middle"}
                  fill="#94a3b8"
                  fontSize="9"
                  fontFamily="monospace"
                >
                  {pt.item.time_label}
                </text>
              ))}
            </svg>
          </div>
        ) : (
          /* ================= MODE 2: STACKED BAR CHART ================= */
          <div className="h-56 flex flex-col justify-between pt-3 pb-1">
            {/* Bars container */}
            <div className="flex-1 flex items-end gap-1 px-2 overflow-x-auto">
              {timeline.map((tb, idx) => {
                const totalReq = Math.max(tb.requests, 1);
                const isHovered = hoveredIdx === idx;
                const val = values[idx];
                const heightPct = Math.max((val / maxVal) * 100, val > 0 ? 6 : 2);

                return (
                  <div
                    key={idx}
                    onMouseEnter={() => setHoveredIdx(idx)}
                    className="flex-1 min-w-[14px] max-w-[32px] h-full flex flex-col justify-end items-center group cursor-pointer"
                  >
                    <div
                      className={`w-full rounded-t-sm flex flex-col justify-end overflow-hidden transition-all ${
                        isHovered ? "ring-2 ring-indigo-400 brightness-125" : "hover:brightness-110"
                      }`}
                      style={{ height: `${heightPct}%` }}
                    >
                      {metric === "requests" ? (
                        <>
                          {/* Errors top */}
                          {tb.errors > 0 && (
                            <div
                              className="bg-rose-500 w-full"
                              style={{ height: `${(tb.errors / totalReq) * 100}%` }}
                              title={`Errors: ${tb.errors}`}
                            />
                          )}
                          {/* Fallback middle */}
                          {tb.fallbacks > 0 && (
                            <div
                              className="bg-purple-500 w-full"
                              style={{ height: `${(tb.fallbacks / totalReq) * 100}%` }}
                              title={`Fallback: ${tb.fallbacks}`}
                            />
                          )}
                          {/* Success bottom */}
                          <div
                            className="bg-indigo-600 w-full min-h-[3px] flex-1"
                            title={`Success: ${tb.requests - tb.errors}`}
                          />
                        </>
                      ) : (
                        <div
                          className="w-full h-full rounded-t-sm"
                          style={{ backgroundColor: metricConfig.color }}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* X-Axis bottom labels for bar mode */}
            <div className="flex justify-between px-2 pt-2 border-t border-slate-800 text-[9px] font-mono text-slate-400">
              <span>{timeline[0]?.time_label}</span>
              {timeline.length > 2 && (
                <span>{timeline[Math.floor(timeline.length / 2)]?.time_label}</span>
              )}
              <span>{timeline[timeline.length - 1]?.time_label}</span>
            </div>
          </div>
        )}

        {/* Rich Floating Interactive Tooltip */}
        {activeItem && (
          <div
            className="absolute top-3 right-3 bg-slate-950/95 border border-slate-700/80 rounded-xl p-3 shadow-2xl backdrop-blur-md text-xs pointer-events-none z-30 space-y-1.5 min-w-[200px] animate-in fade-in zoom-in-95 duration-100"
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-1.5 font-mono">
              <span className="font-semibold text-slate-200">
                {activeItem.timestamp || activeItem.time_label}
              </span>
              <span className="text-[10px] text-slate-400">
                #{hoveredIdx! + 1}
              </span>
            </div>

            <div className="space-y-1 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  Requests:
                </span>
                <span className="font-mono font-bold text-slate-100">
                  {activeItem.requests}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-slate-400 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  Tokens:
                </span>
                <span className="font-mono font-semibold text-amber-300">
                  {formatNum(activeItem.tokens)}
                </span>
              </div>

              {activeItem.fallbacks > 0 && (
                <div className="flex items-center justify-between text-purple-300">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-purple-500" />
                    Fallback triggered:
                  </span>
                  <span className="font-mono font-bold">
                    {activeItem.fallbacks}
                  </span>
                </div>
              )}

              {activeItem.errors > 0 && (
                <div className="flex items-center justify-between text-rose-400">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-rose-500" />
                    Errors (4xx/5xx):
                  </span>
                  <span className="font-mono font-bold">
                    {activeItem.errors}
                  </span>
                </div>
              )}

              {activeItem.avg_latency_ms !== undefined && activeItem.avg_latency_ms > 0 && (
                <div className="flex items-center justify-between text-sky-300 pt-1 border-t border-slate-800/80">
                  <span className="text-slate-400">Average latency:</span>
                  <span className="font-mono font-semibold">
                    {Math.round(activeItem.avg_latency_ms)} ms
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Bottom Chart Legend */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-slate-400">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500 inline-block" />
            Requests ({statsSummary.totalRequests})
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-purple-500 inline-block" />
            Fallback ({statsSummary.totalFallbacks})
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-500 inline-block" />
            Errors ({statsSummary.totalErrors})
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-500 inline-block" />
            Tokens ({formatNum(statsSummary.totalTokens)})
          </span>
        </div>

        <span className="text-[10px] text-slate-500 font-mono">
          Period: {period.toUpperCase()} • Step: {granularity === "hour" ? "1 hour" : "1 day"}
        </span>
      </div>
    </div>
  );
};
