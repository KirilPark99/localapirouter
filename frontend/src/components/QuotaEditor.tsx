import React from "react";
import { PeriodQuotaRule, PeriodQuotaUsage } from "../types";
import { quotaTranslations } from "../i18n/quotaTranslations";

export const quotaSummary = (rule: PeriodQuotaRule, q: typeof quotaTranslations.en) => {
    const limits = [
      rule.requests != null ? `${q.requests}: ${rule.requests}` : null,
      rule.tokens != null ? `${q.tokens}: ${rule.tokens}` : null,
      rule.usd != null ? `$${rule.usd}` : null,
    ].filter(Boolean).join(" · ");
    const window = rule.period === "custom" ? `${rule.duration_seconds} ${q.seconds}` : rule.period === "interval" ? `${rule.start} → ${rule.end}` : q.periods[rule.period];
    return `${rule.scope === "key" ? q.key : rule.model} · ${limits} / ${window}${rule.enabled ? "" : ` · ${q.disabled}`}`;
  };

interface QuotaEditorProps {
  q: typeof quotaTranslations.en;
  formQuotas: PeriodQuotaRule[];
  setFormQuotas: React.Dispatch<React.SetStateAction<PeriodQuotaRule[]>>;
  quotaUsage: PeriodQuotaUsage[];
  usageError: string;
  quotaCatalog: { models: string[]; profiles: string[] };
  catalogError: boolean;
  allowProfiles?: boolean;
  onRefresh?: () => void;
}

export const QuotaEditor: React.FC<QuotaEditorProps> = ({ q, formQuotas, setFormQuotas, quotaUsage, usageError, quotaCatalog, catalogError, allowProfiles = true, onRefresh }) => {
  const changeQuota = (index: number, patch: Partial<PeriodQuotaRule>) => {
    setFormQuotas(previous => previous.map((rule, i) => i === index ? { ...rule, ...patch } : rule));
  };
  return (
          <section className="space-y-3 rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-3" aria-label="Period quotas">
            <h3 className="text-sm font-semibold text-slate-100">{q.title}</h3>
            <p className="text-xs text-slate-400">{q.hint}</p>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <button type="button" disabled={formQuotas.length >= 64} onClick={() => setFormQuotas(previous => [...previous, { enabled: true, scope: "key", period: "day", requests: null, tokens: null, usd: null }])} className="btn-press px-3 py-2 rounded-lg bg-indigo-600 text-white font-semibold disabled:opacity-40">{q.add}</button>
              {formQuotas.length > 0 && <button type="button" onClick={() => setFormQuotas([])} className="text-rose-300">{q.clear}</button>}
              {onRefresh && <button type="button" onClick={onRefresh} className="text-indigo-300">{q.refresh}</button>}
            </div>
            {!formQuotas.length && <p className="text-xs text-slate-300">{q.empty}</p>}
            {usageError && <p role="alert" className="text-xs text-rose-300">{usageError}</p>}
            {catalogError && <p role="status" className="text-xs text-amber-300">{q.catalogError}</p>}
            <datalist id="quota-model-options">{quotaCatalog.models.map(model => <option key={model} value={model} />)}</datalist>
            {allowProfiles && <datalist id="quota-profile-options">{quotaCatalog.profiles.map(profile => <option key={profile} value={profile} />)}</datalist>}
            {formQuotas.map((rule, index) => {
              const current = quotaUsage.find(item => item.rule_id === rule.id);
              const locked = Boolean(rule.id);
              return <fieldset key={rule.id || index} className="min-w-0 space-y-3 p-3 rounded-xl border border-white/10 bg-slate-950/50">
                <legend className="text-xs text-slate-300">{q.rule} {index + 1}</legend>
                <div className="flex items-center justify-between gap-2">
                  <label className="text-xs text-slate-300"><input type="checkbox" checked={rule.enabled} onChange={e => changeQuota(index, { enabled: e.target.checked })} /> {q.enabled}</label>
                  <button type="button" onClick={() => setFormQuotas(previous => previous.filter((_, i) => i !== index))} className="text-xs text-rose-300">{q.remove}</button>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {(["requests", "tokens", "usd"] as const).map(field => <label key={field} className="min-w-0 text-xs text-slate-300">{q[field]}
                    <input aria-label={`Quota ${index + 1} ${field}`} type="number" min={field === "usd" ? "5e-324" : "1"} max={field === "usd" ? "1000000000000" : field === "requests" ? "2147483647" : "9007199254740991"} step={field === "usd" ? "any" : "1"} value={rule[field] ?? ""} onChange={e => changeQuota(index, {[field]: e.target.value ? Number(e.target.value) : null})} placeholder={q.noLimit} className="min-w-0 w-full p-2 rounded bg-slate-900" />
                  </label>)}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label className="min-w-0 block text-xs text-slate-300">{q.scope}
                    <select aria-label={`Quota ${index + 1} scope`} value={rule.scope} disabled={locked} onChange={e => changeQuota(index, {scope: e.target.value as PeriodQuotaRule["scope"], model: null})} className="w-full p-2 rounded bg-slate-900">
                      <option value="key">{q.key}</option><option value="model">{q.model}</option>{allowProfiles && <option value="profile">{q.profile}</option>}
                    </select>
                  </label>
                  <label className="min-w-0 block text-xs text-slate-300">{q.period}
                    <select aria-label={`Quota ${index + 1} period`} value={rule.period} disabled={locked} onChange={e => changeQuota(index, {period: e.target.value as PeriodQuotaRule["period"], duration_seconds: null, anchor: null, start: null, end: null})} className="w-full p-2 rounded bg-slate-900">
                      {(Object.keys(q.periods) as PeriodQuotaRule["period"][]).map(period => <option key={period} value={period}>{q.periods[period]}</option>)}
                    </select>
                  </label>
                </div>
                {rule.scope !== "key" && <label className="block text-xs text-slate-300">{rule.scope === "model" ? q.modelLabel : q.profileLabel}
                  <input aria-label={`Quota ${index + 1} model`} required disabled={locked} list={rule.scope === "model" ? "quota-model-options" : "quota-profile-options"} pattern="[^\s*\/]+/[^\s*]+" placeholder={q.pick} value={rule.model || ""} onChange={e => changeQuota(index, {model: e.target.value})} className="w-full p-2 rounded bg-slate-900" />
                </label>}
                {rule.period === "custom" && <>
                  <label className="block text-xs text-slate-300">{q.duration}<input required type="number" min="1" max="315360000" step="1" disabled={locked} value={rule.duration_seconds ?? ""} onChange={e => changeQuota(index, {duration_seconds: e.target.value ? Number(e.target.value) : null})} className="w-full p-2 rounded bg-slate-900" /></label>
                  <label className="block text-xs text-slate-300">{q.anchor}<input required type="datetime-local" step="1" disabled={locked} value={rule.anchor ? rule.anchor.slice(0,19) : ""} onChange={e => changeQuota(index, {anchor: e.target.value ? new Date(e.target.value + "Z").toISOString() : null})} className="w-full p-2 rounded bg-slate-900" /></label>
                </>}
                {rule.period === "interval" && (["start", "end"] as const).map(field => <label key={field} className="block text-xs text-slate-300">{q[field]}<input required type="datetime-local" step="1" disabled={locked} value={rule[field] ? rule[field]!.slice(0,19) : ""} onChange={e => changeQuota(index, {[field]: e.target.value ? new Date(e.target.value + "Z").toISOString() : null})} className="w-full p-2 rounded bg-slate-900" /></label>)}
                {locked && <p className="text-xs text-slate-400">{q.identity}</p>}
                {current && <div className="text-xs text-slate-300 space-y-1 break-words">
                  <div>{current.active ? q.current : q.inactive}: {current.start} → {current.end}</div>
                  <div>{q.used}: {q.requests} {current.used.requests} · {q.tokens} {current.used.tokens} · ${current.used.usd.toFixed(8)}</div>
                  <div>{q.remaining}: {q.requests} {current.remaining.requests ?? "∞"} · {q.tokens} {current.remaining.tokens ?? "∞"} · {current.remaining.usd == null ? "∞ USD" : `$${current.remaining.usd.toFixed(8)}`}</div>
                </div>}
              </fieldset>;
            })}
            <details className="text-xs text-slate-400">
              <summary className="cursor-pointer text-slate-300">{q.help}</summary>
              <p className="mt-2">{q.counting}</p>
              <p className="mt-2">{q.windows}</p>
            </details>
          </section>
  );
};
