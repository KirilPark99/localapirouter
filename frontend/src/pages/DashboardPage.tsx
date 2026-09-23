import React, { useEffect, useState } from "react";
import {
  Cpu,
  KeyRound,
  Boxes,
  GitFork,
  Merge,
  Activity,
  Zap,
  DollarSign,
  Clock,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { DashboardStats, Provider, RequestLog } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { useI18n } from "../i18n/context";

export const DashboardPage: React.FC = () => {
  const { t } = useI18n();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [recentLogs, setRecentLogs] = useState<RequestLog[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [s, p, l] = await Promise.all([
        apiRequest<DashboardStats>("/api/admin/dashboard/stats"),
        apiRequest<Provider[]>("/api/admin/providers"),
        apiRequest<RequestLog[]>("/api/admin/logs?limit=5"),
      ]);
      setStats(s);
      setProviders(p);
      setRecentLogs(l);
    } catch (err) {
      console.error("Dashboard error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const statCards = [
    {
      title: t.dashboard.activeProviders,
      value: stats?.total_providers ?? 0,
      sub: `${providers.filter((p) => p.enabled).length} ${t.common.enabled}`,
      icon: <Cpu size={18} className="text-indigo-400" />,
    },
    {
      title: t.credentials.title,
      value: stats?.total_credentials ?? 0,
      sub: `${stats?.healthy_credentials ?? 0} ${t.common.active}`,
      icon: <KeyRound size={18} className="text-emerald-400" />,
    },
    {
      title: t.dashboard.totalModels,
      value: stats?.total_models ?? 0,
      sub: t.models.canonicalSlug,
      icon: <Boxes size={18} className="text-cyan-400" />,
    },
    {
      title: t.nav.routing,
      value: stats?.total_routes ?? 0,
      sub: t.routing.priorityChain,
      icon: <GitFork size={18} className="text-purple-400" />,
    },
    {
      title: t.nav.fusion,
      value: stats?.total_fusions ?? 0,
      sub: t.fusion.strategy,
      icon: <Merge size={18} className="text-amber-400" />,
    },
    {
      title: t.dashboard.totalRequests,
      value: stats?.requests_24h ?? 0,
      sub: `${stats?.success_rate_24h ?? 100}% ${t.common.success} · ${stats?.fallbacks_24h ?? 0} Fallbacks`,
      icon: <Activity size={18} className="text-blue-400" />,
    },
    {
      title: t.analytics.avgLatency,
      value: `${stats?.avg_latency_24h ?? 0}ms`,
      sub: "Gateway + Upstream",
      icon: <Clock size={18} className="text-rose-400" />,
    },
    {
      title: `${t.analytics.totalCalls} / Cost`,
      value: `$${(stats?.estimated_cost_24h ?? 0).toFixed(4)}`,
      sub: `${((stats?.total_tokens_24h ?? 0) / 1000).toFixed(1)}k ${t.common.tokens}`,
      icon: <DollarSign size={18} className="text-emerald-400" />,
    },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Title & Refresh */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-white/[0.05]">
        <div>
          <h2 className="text-xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
            {t.dashboard.title}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">{t.dashboard.subtitle}</p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="btn-press flex items-center gap-2 px-3.5 py-2 bg-white/[0.05] hover:bg-white/[0.1] text-slate-200 text-xs font-semibold rounded-xl border border-white/[0.1] transition-all shadow-xs"
        >
          <RefreshCw size={14} className={loading ? "animate-spin text-indigo-400" : "text-slate-400"} />
          <span>{t.common.refresh}</span>
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map((card, i) => (
          <div
            key={i}
            className="group relative overflow-hidden glass-card card-specular rounded-2xl p-4 border border-white/[0.07] hover:border-indigo-500/30 transition-all duration-200 hover:shadow-lg hover:shadow-indigo-950/20 active:scale-[0.99] flex flex-col justify-between"
          >
            <div className="flex items-center justify-between text-slate-400 text-xs font-semibold">
              <span className="tracking-tight text-slate-300">{card.title}</span>
              <div className="w-8 h-8 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center group-hover:scale-105 transition-transform">
                {card.icon}
              </div>
            </div>
            <div className="mt-3 text-2xl font-extrabold tracking-tight text-white font-mono">
              {card.value}
            </div>
            <div className="mt-1 text-[11px] text-slate-400 font-medium">
              {card.sub}
            </div>
          </div>
        ))}
      </div>

      {/* Two columns: Providers health & Recent requests */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Providers Overview */}
        <div className="glass-panel card-specular rounded-2xl p-5 border border-white/[0.07] shadow-xl">
          <div className="flex items-center justify-between pb-3.5 border-b border-white/[0.06] mb-3.5">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                {t.providers.title}
              </h3>
              <p className="text-[11px] text-slate-400 mt-0.5">{t.providers.subtitle}</p>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-white/[0.05] border border-white/[0.08] text-slate-300">
              {providers.length} {t.common.total}
            </span>
          </div>
          <div className="space-y-2.5">
            {providers.slice(0, 6).map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between p-3 bg-slate-950/50 border border-white/[0.05] hover:border-white/[0.12] rounded-xl text-xs transition-colors"
              >
                <div>
                  <div className="font-semibold text-slate-100 flex items-center gap-2">
                    <span>{p.name}</span>
                    <span className="text-slate-400 font-mono text-[10px] uppercase px-1.5 py-0.5 rounded bg-white/[0.05] border border-white/[0.06]">
                      {p.adapter_type}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[11px] text-slate-400 font-mono">
                    {p.credentials_count} {t.providers.credentialsCount} • {p.models_count} {t.providers.modelsCount}
                  </span>
                  <StatusBadge
                    status={
                      !p.enabled
                        ? "DISABLED"
                        : p.credentials_count > 0 && p.healthy_credentials_count > 0
                        ? "HEALTHY"
                        : p.credentials_count === 0
                        ? "UNKNOWN"
                        : "DEGRADED"
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Request Stream */}
        <div className="glass-panel card-specular rounded-2xl p-5 border border-white/[0.07] shadow-xl">
          <div className="flex items-center justify-between pb-3.5 border-b border-white/[0.06] mb-3.5">
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                {t.dashboard.recentActivity}
              </h3>
              <p className="text-[11px] text-slate-400 mt-0.5">{t.logs.subtitle}</p>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-white/[0.05] border border-white/[0.08] text-slate-300">
              {recentLogs.length} {t.common.details}
            </span>
          </div>
          {recentLogs.length === 0 ? (
            <div className="text-xs text-slate-400 py-10 text-center font-mono">{t.dashboard.noRecentActivity}</div>
          ) : (
            <div className="space-y-2.5">
              {recentLogs.map((l) => (
                <div
                  key={l.id}
                  className="flex items-center justify-between p-3 bg-slate-950/50 border border-white/[0.05] hover:border-white/[0.12] rounded-xl text-xs transition-colors"
                >
                  <div className="overflow-hidden pr-2">
                    <div className="font-mono text-xs font-semibold text-slate-100 truncate">
                      {l.requested_model}
                    </div>
                    <div className="text-[10px] text-slate-400 flex items-center gap-2 mt-1 font-mono">
                      <span className="px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-bold">
                        {l.mode}
                      </span>
                      <span>•</span>
                      <span className="text-emerald-400">{l.latency_ms}ms</span>
                      <span>•</span>
                      <span>{l.input_tokens + l.output_tokens} tok</span>
                    </div>
                  </div>
                  <StatusBadge status={l.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
