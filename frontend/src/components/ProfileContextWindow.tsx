import { Maximize2 } from "lucide-react";
import { useI18n } from "../i18n/context";

export const ROUTE_CONTEXT_PRESETS = [
  { id: "auto", label: "Auto", value: null },
  { id: "8192", label: "8K", value: 8192 },
  { id: "16384", label: "16K", value: 16384 },
  { id: "32768", label: "32K", value: 32768 },
  { id: "65536", label: "64K", value: 65536 },
  { id: "131072", label: "128K", value: 131072 },
  { id: "200000", label: "200K", value: 200000 },
  { id: "1048576", label: "1M", value: 1048576 },
  { id: "2097152", label: "2M", value: 2097152 },
  { id: "custom", label: "Custom ✏️", value: null },
];

export const contextPresetFor = (value?: number | null): string =>
  !value ? "auto" : ROUTE_CONTEXT_PRESETS.find((p) => p.value === value)?.id || "custom";

export function ProfileContextWindow({ preset, customValue, onPresetChange, onCustomChange }: {
  preset: string;
  customValue: string;
  onPresetChange: (value: string) => void;
  onCustomChange: (value: string) => void;
}) {
  const { t } = useI18n();
  return (
          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <Maximize2 size={13} className="text-cyan-400" />
                Context Window ({t.models.contextLength})
              </label>
              <span className="text-[10px] text-slate-400 font-mono">
                {preset === "auto"
                  ? "Auto (model default)"
                  : preset === "custom"
                  ? `${customValue ? Number(customValue).toLocaleString() : "..."} tokens`
                  : `${Number(preset).toLocaleString()} tokens`}
              </span>
            </div>
            <div className="grid grid-cols-5 sm:grid-cols-10 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px] font-medium text-slate-300">
              {ROUTE_CONTEXT_PRESETS.map((opt) => (
                <button
                  key={opt.id}
                  aria-pressed={preset === opt.id}
                  type="button"
                  onClick={() => onPresetChange(opt.id)}
                  className={`py-1 rounded text-center transition-all ${
                    preset === opt.id
                      ? opt.id === "auto"
                        ? "bg-slate-700 text-white font-semibold shadow-xs"
                        : opt.id === "custom"
                        ? "bg-indigo-600 text-white font-semibold shadow-xs"
                        : "bg-cyan-600 text-white font-semibold shadow-xs"
                      : "hover:bg-slate-800 text-slate-400"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {preset === "custom" && (
              <div className="flex items-center gap-2 pt-1">
                <span className="text-[11px] text-cyan-300 font-medium shrink-0">Tokens:</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  required
                  aria-label="Context Window tokens"
                  value={customValue}
                  onChange={(e) => onCustomChange(e.target.value)}
                  placeholder="e.g. 128000 or 1000000"
                  className="flex-1 px-2.5 py-1 bg-slate-900 border border-cyan-500/50 rounded-md text-xs text-cyan-100 font-mono focus:border-cyan-400 focus:outline-none"
                />
              </div>
            )}
          </div>
  );
}
