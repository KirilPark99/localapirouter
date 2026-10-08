import React, { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { apiRequest } from "../api/client";
import { SubscriptionLimit, SubscriptionLimits } from "../types";
import { useI18n } from "../i18n";

const supportedModules = ["codex_cli", "agy_cli", "grok_builder_cli"];
let session: string | null = null;
const cache = new Map<string, { time: number; data?: SubscriptionLimits; pending?: Promise<SubscriptionLimits> }>();

export function loadSubscriptionLimits(id: number, moduleId: string, refresh = false): Promise<SubscriptionLimits> {
  const token = localStorage.getItem("myairouter_token");
  if (session !== token) { cache.clear(); session = token; }
  const key = `${moduleId}:${id}`;
  const existing = cache.get(key);
  if (existing?.pending) return existing.pending;
  if (!refresh && existing?.data && Date.now() - existing.time < 60000) return Promise.resolve(existing.data);
  // ponytail: refresh on list entry/hover, no background polling; add it if live counters are needed.
  const entry: { time: number; data?: SubscriptionLimits; pending?: Promise<SubscriptionLimits> } = { time: 0 };
  cache.set(key, entry);
  entry.pending = apiRequest<SubscriptionLimits>(`/api/admin/credentials/${id}/subscription-limits`, { signal: AbortSignal.timeout(35000) })
    .catch((error: Error): SubscriptionLimits => ({ status: "unavailable", limits: [], message: error.message }))
    .then(data => { entry.data = data; entry.time = Date.now(); entry.pending = undefined; return data; });
  return entry.pending;
}

export function subscriptionPeriod(limit: SubscriptionLimit): "week" | "month" | null {
  if (limit.window_seconds != null) {
    if (limit.window_seconds === 604800) return "week";
    if ([28, 29, 30, 31].some(days => limit.window_seconds === days * 86400)) return "month";
    return null;
  }
  if (/\b(weekly|week)\b/i.test(limit.name)) return "week";
  if (/\b(monthly|month)\b/i.test(limit.name)) return "month";
  return null;
}

export function subscriptionAmount(value: number, unit?: string | null): string {
  return unit === "USD cents" ? (value / 100).toLocaleString(undefined, { style: "currency", currency: "USD" })
    : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit ?? ""}`.trim();
}

export function subscriptionRemaining(limit: SubscriptionLimit, labels: { unknown: string }): string {
  const number = (value: number) => value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (limit.remaining_percent != null) return `${number(limit.remaining_percent)}%`;
  if (limit.remaining != null) return subscriptionAmount(limit.remaining, limit.unit);
  if (limit.used_percent != null) return `${number(Math.max(0, 100 - limit.used_percent))}%`;
  if (limit.limit != null && limit.used != null) return subscriptionAmount(Math.max(0, limit.limit - limit.used), limit.unit);
  return labels.unknown;
}

export const SubscriptionLimitsBadge: React.FC<{ credentialId: number; moduleId?: string; name?: string }> = ({ credentialId, moduleId = "", name = "" }) => {
  const { language } = useI18n();
  const s = language === "ru" ? {
    title: "Лимиты подписки", week: "Неделя", month: "Месяц", included: "Кредиты подписки", prepaid: "Купленные кредиты", onDemand: "Дополнительный лимит", unknown: "Неизвестно",
    remaining: "Осталось", used: "Использовано", limit: "Лимит", reset: "Сброс", window: "Окно",
    loading: "Загрузка…", unavailable: "Недоступно", unsupported: "Не поддерживается", refresh: "Обновить",
    plan: "Подписка", checked: "Проверено", seconds: "сек.", hours: "ч", close: "Закрыть",
    note: "Лимиты провайдера, не квоты роутера. Отсутствующие периоды не рассчитываются.",
  } : {
    title: "Subscription limits", week: "Week", month: "Month", included: "Subscription credits", prepaid: "Purchased credits", onDemand: "On-demand", unknown: "Unknown",
    remaining: "Remaining", used: "Used", limit: "Limit", reset: "Reset", window: "Window",
    loading: "Loading…", unavailable: "Unavailable", unsupported: "Unsupported", refresh: "Refresh",
    plan: "Plan", checked: "Checked", seconds: "sec.", hours: "h", close: "Close",
    note: "Provider limits, not router quotas. Missing periods are not calculated.",
  };
  const enabled = supportedModules.includes(moduleId);
  const [data, setData] = useState<SubscriptionLimits | undefined>(() => {
    return session === localStorage.getItem("myairouter_token") ? cache.get(`${moduleId}:${credentialId}`)?.data : undefined;
  });
  const [loading, setLoading] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const requestVersion = useRef(0);
  const popupId = useId();
  const keep = () => clearTimeout(hideTimer.current);
  const hide = () => { keep(); hideTimer.current = setTimeout(() => {
    if (document.activeElement !== trigger.current && !popup.current?.contains(document.activeElement)) setRect(null);
  }, 150); };
  const load = async (refresh = false) => {
    if (!enabled) return;
    const version = ++requestVersion.current;
    setLoading(true);
    const result = await loadSubscriptionLimits(credentialId, moduleId, refresh);
    if (version === requestVersion.current) { setData(result); setLoading(false); }
  };
  useEffect(() => {
    setData(undefined); setRect(null); void load();
    return () => { requestVersion.current++; keep(); };
  }, [credentialId, moduleId]);
  useEffect(() => {
    if (!rect) return;
    const dismiss = (event: Event) => {
      if (!popup.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) setRect(null);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); trigger.current?.focus(); setRect(null); }
    };
    const scroll = (event: Event) => {
      if (popup.current?.contains(event.target as Node)) return;
      if (document.activeElement === trigger.current) setRect(trigger.current!.getBoundingClientRect());
      else setRect(null);
    };
    const resize = () => setRect(null);
    document.addEventListener("pointerdown", dismiss);
    window.addEventListener("scroll", scroll, true);
    window.addEventListener("resize", resize);
    window.addEventListener("keydown", escape, true);
    return () => {
      document.removeEventListener("pointerdown", dismiss);
      window.removeEventListener("scroll", scroll, true);
      window.removeEventListener("resize", resize);
      window.removeEventListener("keydown", escape, true);
    };
  }, [rect]);
  if (!enabled) return null;
  const open = () => { keep(); setRect(trigger.current!.getBoundingClientRect()); void load(); };
  const time = (value?: string | null) => value && Number.isFinite(Date.parse(value))
    ? new Date(value).toLocaleString(language === "ru" ? "ru-RU" : "en-US") : s.unknown;
  const limits = data?.status === "ok" ? data.limits : [];
  const label = (limit: SubscriptionLimit) => {
    if (moduleId === "grok_builder_cli") {
      if (limit.name === "Included credits") return s.included;
      if (limit.name === "Prepaid credits") return s.prepaid;
      if (limit.name === "On-demand") return s.onDemand;
      return limit.name;
    }
    const period = subscriptionPeriod(limit);
    return period ? s[period] : limit.window_seconds && limit.window_seconds % 3600 === 0
      ? `${limit.window_seconds / 3600} ${s.hours}` : limit.name;
  };
  const status = data?.status === "unsupported" ? s.unsupported : data?.status === "unavailable" ? s.unavailable : loading && !data ? s.loading : "";
  // Fixed portals live outside .content-pane; convert viewport pixels through the root's CSS zoom.
  const scale = rect ? (parseFloat(getComputedStyle(document.documentElement).zoom) || 1) * (parseFloat(getComputedStyle(document.body).zoom) || 1) : 1;
  const viewportWidth = rect ? window.innerWidth / scale : 0;
  const viewportHeight = rect ? window.innerHeight / scale : 0;
  const width = Math.min(420, viewportWidth - 16);
  const height = Math.min(480, viewportHeight - 24);
  return <>
    <button ref={trigger} type="button" data-subscription-key={credentialId} aria-label={`${s.title} — ${name || credentialId}`}
      aria-haspopup="dialog" aria-expanded={!!rect} aria-controls={rect ? popupId : undefined}
      onMouseEnter={open} onMouseLeave={hide} onFocus={open} onBlur={event => {
        if (!popup.current?.contains(event.relatedTarget)) hide();
      }} onClick={open}
      className="inline-flex flex-wrap gap-x-2 gap-y-1 mt-1 text-left text-[11px] text-indigo-200 border border-indigo-500/20 bg-indigo-500/5 rounded-lg px-2 py-1 focus-visible:outline-2 focus-visible:outline-indigo-400">
      <span className="text-slate-400">{s.remaining}:</span>
      {limits.slice(0, moduleId === "grok_builder_cli" ? 3 : 2).map((limit, index) => <span key={index}>{label(limit)}: <strong>{subscriptionRemaining(limit, s)}</strong></span>)}
      {!limits.length && !status && <span>{s.unknown}</span>}
      {status && <span role="status" className="text-slate-400">{status}</span>}
    </button>
    {rect && createPortal(<div ref={popup} id={popupId} role="dialog" aria-label={`${s.title} — ${name || credentialId}`}
      onMouseEnter={keep} onMouseLeave={hide} onFocus={keep} onBlur={event => {
        if (!event.currentTarget.contains(event.relatedTarget) && !trigger.current?.contains(event.relatedTarget)) hide();
      }} className="fixed z-[100] overflow-y-auto rounded-xl border border-indigo-500/30 bg-slate-900 p-3 text-xs text-slate-200 shadow-2xl space-y-2 break-words"
      style={{ width, maxHeight: height, left: Math.max(8, Math.min(rect.left / scale, viewportWidth - width - 8)),
        top: Math.max(8, Math.min(rect.bottom / scale + 4, viewportHeight - height - 8)) }}>
      <div className="flex items-center justify-between gap-2">
        <strong>{s.title} — {name || credentialId}</strong>
        <button type="button" aria-label={s.close} onClick={() => { trigger.current?.focus(); setRect(null); }} className="px-2 py-1 rounded hover:bg-white/10">×</button>
      </div>
      <p className="text-slate-400 text-[11px]">{s.note}</p>
      <div className="flex items-center justify-between gap-2">
        <span>{s.plan}: <strong>{data?.plan ?? s.unknown}</strong></span>
        <button type="button" disabled={loading} onClick={() => void load(true)} className="px-2 py-1 rounded border border-indigo-500/30 text-indigo-300 disabled:opacity-50">{loading ? s.loading : s.refresh}</button>
      </div>
      {status && <p role="status" className="text-amber-300">{status}</p>}
      {data?.message && <p className="text-slate-400">{data.message}</p>}
      {limits.map((limit, index) => <div key={index} className="border border-white/10 rounded-lg p-2 space-y-1">
        <strong>{label(limit)}</strong>{limit.model && limit.model !== limit.name && <p className="text-slate-400">{limit.model}</p>}
        <p className="text-emerald-300">{s.remaining}: <strong>{subscriptionRemaining(limit, s)}</strong></p>
        <p>{s.used}: {limit.used_percent != null ? `${limit.used_percent.toLocaleString()}%` : limit.used != null ? subscriptionAmount(limit.used, limit.unit) : s.unknown}</p>
        {limit.limit != null && <p>{s.limit}: {subscriptionAmount(limit.limit, limit.unit)}</p>}
        {limit.window_seconds != null && <p>{s.window}: {limit.window_seconds.toLocaleString()} {s.seconds}</p>}
        <p>{s.reset}: {time(limit.reset_at)}</p>
      </div>)}
      <p className="text-slate-400 text-[11px]">{s.checked}: {time(data?.checked_at)}</p>
    </div>, document.body)}
  </>;
};
