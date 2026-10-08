import React, { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { apiRequest } from "../api/client";
import { SubscriptionLimit, SubscriptionLimits, SubscriptionResetResult } from "../types";
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
    resets: "Сбросы", actions: "Действия ключа", applyReset: "Использовать сброс лимитов", retryReset: "Повторить предыдущую попытку", resetting: "Сброс…",
    confirmReset: "Использовать один сохранённый сброс для этого аккаунта Codex? Он восстановит доступные окна 5 часов и недели и изменит дату недельного сброса. Локальные квоты роутера не изменятся.",
    confirmRetry: "Повторить предыдущую попытку с тем же идентификатором? Уже выполненный сброс не будет списан повторно.",
    resetDone: "Лимиты сброшены. Сохранённый сброс использован.", nothing_to_reset: "Сбрасывать нечего — сброс не потрачен.",
    no_credit: "Доступных сохранённых сбросов нет.", already_redeemed: "Эта попытка уже выполнена; повторного списания нет.",
    resetError: "Результат сброса не подтверждён. Обновлены лимиты; повторное нажатие использует тот же идентификатор попытки.",
  } : {
    title: "Subscription limits", week: "Week", month: "Month", included: "Subscription credits", prepaid: "Purchased credits", onDemand: "On-demand", unknown: "Unknown",
    remaining: "Remaining", used: "Used", limit: "Limit", reset: "Reset", window: "Window",
    loading: "Loading…", unavailable: "Unavailable", unsupported: "Unsupported", refresh: "Refresh",
    plan: "Plan", checked: "Checked", seconds: "sec.", hours: "h", close: "Close",
    note: "Provider limits, not router quotas. Missing periods are not calculated.",
    resets: "Resets", actions: "Credential actions", applyReset: "Use a banked limit reset", retryReset: "Retry the previous attempt", resetting: "Resetting…",
    confirmReset: "Use one banked reset for this Codex account? It refreshes eligible 5-hour and weekly windows and changes the weekly reset date. Local router quotas are unchanged.",
    confirmRetry: "Retry the previous attempt with the same ID? A completed reset will not be charged again.",
    resetDone: "Limits reset. One banked reset was used.", nothing_to_reset: "Nothing to reset — no banked reset was used.",
    no_credit: "No banked resets are available.", already_redeemed: "This attempt already completed; no additional reset was used.",
    resetError: "Reset result is unconfirmed. Usage was refreshed; retrying reuses the same attempt ID.",
  };
  const enabled = supportedModules.includes(moduleId);
  const [data, setData] = useState<SubscriptionLimits | undefined>(() => {
    return session === localStorage.getItem("myairouter_token") ? cache.get(`${moduleId}:${credentialId}`)?.data : undefined;
  });
  const [loading, setLoading] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetMessage, setResetMessage] = useState("");
  const attemptKey = `myairouter_codex_reset:${credentialId}`;
  const [pendingReset, setPendingReset] = useState(() => typeof sessionStorage !== "undefined" && !!sessionStorage.getItem(attemptKey));
  const resetInFlight = useRef(false);
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
  const resetSubscription = async () => {
    if (moduleId !== "codex_cli" || resetInFlight.current || loading) return;
    const previous = sessionStorage.getItem(attemptKey);
    if (!previous && !(data?.reset_credits_available != null && data.reset_credits_available > 0)) return;
    if (!window.confirm(`${name || credentialId}

${previous ? s.confirmRetry : s.confirmReset}`)) return;
    resetInFlight.current = true; setResetting(true); setResetMessage("");
    const version = ++requestVersion.current;
    try {
      // getRandomValues supports the router's plain-HTTP LAN origin too.
      const bytes = crypto.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 0x0f) | 0x40; bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
      const requestId = previous || `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
      // Keep ambiguous attempts across list navigation/reloads; only a terminal reply clears the ID.
      sessionStorage.setItem(attemptKey, requestId); setPendingReset(true);
      const result = await apiRequest<SubscriptionResetResult>(`/api/admin/credentials/${credentialId}/subscription-limits/reset`, {
        method: "POST", signal: AbortSignal.timeout(35000),
        body: JSON.stringify({ redeem_request_id: requestId, confirmed: true }),
      });
      sessionStorage.removeItem(attemptKey);
      if (version === requestVersion.current) { setPendingReset(false); setResetMessage(result.code === "reset" ? s.resetDone : s[result.code]); }
    } catch {
      if (version === requestVersion.current) setResetMessage(s.resetError);
    } finally {
      // Refresh reads only, even after a lost reply. Never retry the consuming POST automatically.
      cache.delete(`${moduleId}:${credentialId}`);
      if (version === requestVersion.current) await load(true);
      resetInFlight.current = false; setResetting(false);
    }
  };
  useEffect(() => {
    setResetMessage(""); setPendingReset(!!sessionStorage.getItem(attemptKey));
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
  const open = () => { keep(); setRect(trigger.current!.getBoundingClientRect()); if (!resetInFlight.current) void load(); };
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
      {moduleId === "codex_cli" && <span>{s.resets}: <strong>{data?.reset_credits_available ?? s.unknown}</strong></span>}
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
        <button type="button" disabled={loading || resetting} onClick={() => void load(true)} className="px-2 py-1 rounded border border-indigo-500/30 text-indigo-300 disabled:opacity-50">{loading ? s.loading : s.refresh}</button>
      </div>
      {moduleId === "codex_cli" && <div className="flex items-center justify-between gap-2">
        <span>{s.resets}: <strong>{data?.reset_credits_available ?? s.unknown}</strong></span>
        <details className="relative">
          <summary aria-label={s.actions} className="cursor-pointer px-2 py-1 rounded border border-indigo-500/30">⋯</summary>
          <button type="button" onClick={() => void resetSubscription()}
            disabled={loading || resetting || (!pendingReset && !(data?.reset_credits_available != null && data.reset_credits_available > 0))}
            className="mt-1 px-2 py-1 rounded border border-amber-500/30 text-amber-200 disabled:opacity-50">
            {resetting ? s.resetting : pendingReset ? s.retryReset : s.applyReset}
          </button>
        </details>
      </div>}
      {resetMessage && <p role="status" className="text-amber-200">{resetMessage}</p>}
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
