import React from "react";

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = "sm" }) => {
  const s = (status || "UNKNOWN").toUpperCase();

  let colors = "bg-slate-800/80 text-slate-300 border-slate-700/80";
  let dotColor = "bg-slate-400";
  let isHealthy = false;

  switch (s) {
    case "HEALTHY":
    case "SUCCESS":
    case "FALLBACK_SUCCESS":
    case "FUSION_SUCCESS":
      colors = "bg-emerald-500/10 text-emerald-300 border-emerald-500/30 shadow-xs shadow-emerald-950/20";
      dotColor = "bg-emerald-400";
      isHealthy = true;
      break;
    case "DEGRADED":
      colors = "bg-amber-500/10 text-amber-300 border-amber-500/30 shadow-xs shadow-amber-950/20";
      dotColor = "bg-amber-400";
      break;
    case "RATE_LIMITED":
      colors = "bg-orange-500/10 text-orange-300 border-orange-500/30 shadow-xs shadow-orange-950/20";
      dotColor = "bg-orange-400";
      break;
    case "COOLDOWN":
      colors = "bg-purple-500/10 text-purple-300 border-purple-500/30 shadow-xs shadow-purple-950/20";
      dotColor = "bg-purple-400";
      break;
    case "INVALID":
    case "FAILED":
    case "ERROR":
      colors = "bg-rose-500/10 text-rose-300 border-rose-500/30 shadow-xs shadow-rose-950/20";
      dotColor = "bg-rose-400";
      break;
    case "DISABLED":
      colors = "bg-slate-900/80 text-slate-500 border-slate-800";
      dotColor = "bg-slate-500";
      break;
  }

  const padding = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  return (
    <span className={`inline-flex items-center gap-1.5 font-mono font-semibold tracking-wide rounded-full border ${padding} ${colors}`}>
      <span className="relative flex h-1.5 w-1.5">
        {isHealthy && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />}
        <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${dotColor}`} />
      </span>
      <span>{s.replace(/_/g, " ")}</span>
    </span>
  );
};
