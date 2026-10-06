import React, { useEffect, useState, useCallback } from "react";
import {
  ScrollText,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Search,
  X,
  Key,
  Radio,
  Calendar,
  Download,
  FileSpreadsheet,
  FileJson,
  SlidersHorizontal,
  Filter,
  ArrowUpDown,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Zap,
  Coins,
  GitFork,
  Eye,
  Layers,
  Sparkles,
  Cpu,
  Boxes,
} from "lucide-react";
import { apiRequest, apiRequestWithMeta } from "../api/client";
import { RequestLog, LogsSummaryResponse, Provider, RouterApiKey } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { LogDetailDrawer } from "../components/LogDetailDrawer";
import { useI18n } from "../i18n";

export const LogsPage: React.FC<{ onReplay: () => void }> = ({ onReplay }) => {
  const { t } = useI18n();
  const [logs, setLogs] = useState<RequestLog[]>([]);
  const [summary, setSummary] = useState<LogsSummaryResponse | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [selectedLog, setSelectedLog] = useState<RequestLog | null>(null);

  // Reference data for filters
  const [providers, setProviders] = useState<Provider[]>([]);
  const [routerKeys, setRouterKeys] = useState<RouterApiKey[]>([]);

  // Time Period & Calendar Filters
  const [period, setPeriod] = useState<
    "all" | "today" | "yesterday" | "24h" | "7d" | "30d" | "custom"
  >("all");
  const [showCustomRange, setShowCustomRange] = useState(false);
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  // Quick Preset Chips: "" | "errors" | "fallback" | "stream" | "slow"
  const [quickPreset, setQuickPreset] = useState<string>("");

  // Advanced Filters
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [modeFilter, setModeFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [statusCodeFilter, setStatusCodeFilter] = useState<string>("");
  const [providerFilter, setProviderFilter] = useState<string>("");
  const [modelFilter, setModelFilter] = useState<string>("");
  const [keyFilter, setKeyFilter] = useState<string>("");

  // Search & Pagination
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchInput, setSearchInput] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);

  // Sorting
  const [sortBy, setSortBy] = useState<string>("created_at");
  const [sortOrder, setSortOrder] = useState<string>("desc");

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "desc" ? "asc" : "desc");
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
    setPage(1);
  };

  // Live Tail / Auto Refresh
  const [autoRefresh, setAutoRefresh] = useState<boolean>(false);
  const [showExportMenu, setShowExportMenu] = useState<boolean>(false);

  // Load reference data on mount
  useEffect(() => {
    const fetchRefs = async () => {
      try {
        const [p, k] = await Promise.all([
          apiRequest<Provider[]>("/api/admin/providers"),
          apiRequest<RouterApiKey[]>("/api/admin/keys"),
        ]);
        setProviders(p || []);
        setRouterKeys(k || []);
      } catch (e) {
        console.error("Failed to load filter references:", e);
      }
    };
    fetchRefs();
  }, []);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(searchInput);
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Compute actual date parameters based on selected period
  const getDateRangeParams = useCallback(() => {
    if (period === "custom") {
      return { start: startDate, end: endDate };
    }
    const now = new Date();
    if (period === "today") {
      const todayStr = now.toISOString().slice(0, 10);
      return { start: todayStr, end: todayStr };
    }
    if (period === "yesterday") {
      const yest = new Date(now.getTime() - 86400000);
      const yestStr = yest.toISOString().slice(0, 10);
      return { start: yestStr, end: yestStr };
    }
    if (period === "24h") {
      const d = new Date(now.getTime() - 24 * 3600 * 1000);
      return { start: d.toISOString(), end: "" };
    }
    if (period === "7d") {
      const d = new Date(now.getTime() - 7 * 86400000);
      return { start: d.toISOString(), end: "" };
    }
    if (period === "30d") {
      const d = new Date(now.getTime() - 30 * 86400000);
      return { start: d.toISOString(), end: "" };
    }
    return { start: "", end: "" };
  }, [period, startDate, endDate]);

  const buildQueryString = useCallback(
    (includePagination = true) => {
      const { start, end } = getDateRangeParams();
      let qs = "";
      if (includePagination) {
        const offset = (page - 1) * pageSize;
        qs += `limit=${pageSize}&offset=${offset}`;
      }
      if (start) qs += `&start_date=${encodeURIComponent(start)}`;
      if (end) qs += `&end_date=${encodeURIComponent(end)}`;
      if (modeFilter) qs += `&mode=${encodeURIComponent(modeFilter)}`;
      if (statusFilter) qs += `&status=${encodeURIComponent(statusFilter)}`;
      if (statusCodeFilter) qs += `&status_code=${encodeURIComponent(statusCodeFilter)}`;
      if (providerFilter) qs += `&provider_id=${encodeURIComponent(providerFilter)}`;
      if (modelFilter.trim()) qs += `&model=${encodeURIComponent(modelFilter.trim())}`;
      if (keyFilter) qs += `&router_key_id=${encodeURIComponent(keyFilter)}`;

      if (quickPreset === "errors") qs += `&has_error=true`;
      if (quickPreset === "fallback") qs += `&has_fallback=true`;
      if (quickPreset === "stream") qs += `&is_stream=true`;
      if (quickPreset === "slow") qs += `&min_latency=2000`;
      if (quickPreset === "fusion") qs += `&mode=FUSION`;

      if (searchQuery.trim()) qs += `&search=${encodeURIComponent(searchQuery.trim())}`;
      if (sortBy) qs += `&sort_by=${encodeURIComponent(sortBy)}`;
      if (sortOrder) qs += `&sort_order=${encodeURIComponent(sortOrder)}`;

      return qs.startsWith("&") ? qs.slice(1) : qs;
    },
    [
      getDateRangeParams,
      page,
      pageSize,
      modeFilter,
      statusFilter,
      statusCodeFilter,
      providerFilter,
      modelFilter,
      keyFilter,
      quickPreset,
      searchQuery,
      sortBy,
      sortOrder,
    ]
  );

  const loadLogs = useCallback(
    async (showLoading = true) => {
      if (showLoading) setLoading(true);
      try {
        const logsQs = buildQueryString(true);
        const summaryQs = buildQueryString(false);

        const [{ data, headers }, sumData] = await Promise.all([
          apiRequestWithMeta<RequestLog[]>(`/api/admin/logs?${logsQs}`),
          apiRequest<LogsSummaryResponse>(`/api/admin/logs/summary?${summaryQs}`).catch(() => null),
        ]);

        setLogs(data || []);
        setSummary(sumData);

        const countHeader = headers.get("x-total-count");
        if (countHeader) {
          setTotalCount(parseInt(countHeader, 10));
        } else {
          setTotalCount(data.length);
        }
      } catch (err) {
        console.error("Failed to load logs:", err);
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [buildQueryString]
  );

  // Initial and reactive load
  useEffect(() => {
    loadLogs(true);
  }, [loadLogs]);

  // Auto-refresh interval (Live Tail)
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadLogs(false);
    }, 4000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadLogs]);

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const startIdx = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const endIdx = Math.min(page * pageSize, totalCount);

  const formatDateTime = (isoString: string) => {
    if (!isoString) return "—";
    const d = new Date(isoString);
    return d.toLocaleString("sv-SE", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const handleReplayInPlayground = (log: RequestLog) => {
    sessionStorage.setItem(
      "replay_log_data",
      JSON.stringify({
        model: log.requested_model,
        prompt: log.prompt_content || "",
      })
    );
    onReplay();
  };

  const handleResetFilters = () => {
    setPeriod("all");
    setShowCustomRange(false);
    setStartDate("");
    setEndDate("");
    setQuickPreset("");
    setModeFilter("");
    setStatusFilter("");
    setStatusCodeFilter("");
    setProviderFilter("");
    setModelFilter("");
    setKeyFilter("");
    setSearchInput("");
    setSearchQuery("");
    setSortBy("created_at");
    setSortOrder("desc");
    setPage(1);
  };

  const hasActiveFilters =
    period !== "all" ||
    !!quickPreset ||
    !!modeFilter ||
    !!statusFilter ||
    !!statusCodeFilter ||
    !!providerFilter ||
    !!modelFilter ||
    !!keyFilter ||
    !!searchQuery;

  // Export functions
  const exportToCSV = () => {
    if (logs.length === 0) return;
    const headers = [
      "Request ID",
      "Timestamp",
      "Mode",
      "Requested Model",
      "Upstream Model",
      "Provider",
      "Credential",
      "Client Key",
      "Status Code",
      "Status",
      "Latency (ms)",
      "Prompt Tokens",
      "Completion Tokens",
      "Cached Tokens",
      "Reasoning Tokens",
      "Total Tokens",
      "Cost ($)",
      "Attempts Count",
      "Error Message",
    ];

    const rows = logs.map((l) => [
      l.request_id,
      l.created_at,
      l.mode,
      l.requested_model,
      l.upstream_model || "",
      l.resolved_provider_name || "",
      l.resolved_credential_name || "",
      l.router_key_name || "",
      l.status_code.toString(),
      l.status,
      l.latency_ms.toString(),
      l.input_tokens.toString(),
      l.output_tokens.toString(),
      l.cached_tokens.toString(),
      l.reasoning_tokens.toString(),
      (l.input_tokens + l.output_tokens).toString(),
      l.estimated_cost_usd.toString(),
      (l.attempts?.length || 1).toString(),
      (l.error_message || "").replace(/"/g, '""'),
    ]);

    const csvContent =
      "data:text/csv;charset=utf-8,\uFEFF" +
      [headers.join(","), ...rows.map((r) => r.map((cell) => `"${cell}"`).join(","))].join("\n");

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `request_logs_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setShowExportMenu(false);
  };

  const exportToJSON = () => {
    if (logs.length === 0) return;
    const jsonStr = JSON.stringify(logs, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `request_logs_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
  };

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <ScrollText className="text-indigo-400" size={22} />
              {t.logs.title}
            </h1>
            <span className="px-2 py-0.5 rounded-full text-xs font-mono font-semibold bg-indigo-950 text-indigo-300 border border-indigo-800/60">
              {totalCount.toLocaleString()} logs
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {t.logs.subtitle}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Live Tail Toggle */}
          <button
            type="button"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`btn-press flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-xl border transition-all cursor-pointer ${
              autoRefresh
                ? "bg-emerald-950/80 border-emerald-600/60 text-emerald-300 shadow-md shadow-emerald-950/50"
                : "bg-slate-900/80 border-white/[0.08] text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            }`}
            title="Auto-refresh request logs every 4 seconds (Live Tail)"
          >
            <Radio size={13} className={autoRefresh ? "animate-pulse text-emerald-400" : "text-slate-500"} />
            <span>Live Tail: {autoRefresh ? "ON" : "OFF"}</span>
          </button>

          {/* Export Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(!showExportMenu)}
              className="btn-press flex items-center gap-1.5 px-3 py-2 bg-slate-900/80 hover:bg-slate-800 border border-white/[0.08] text-slate-300 rounded-xl text-xs transition-colors cursor-pointer"
              title={t.common.export}
            >
              <Download size={13} className="text-indigo-400" />
              <span>{t.common.export}</span>
            </button>

            {showExportMenu && (
              <div className="absolute right-0 mt-1.5 w-44 glass-panel border border-white/[0.1] rounded-2xl shadow-2xl z-30 p-1.5 space-y-1">
                <button
                  onClick={exportToCSV}
                  className="btn-press w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors text-left cursor-pointer"
                >
                  <FileSpreadsheet size={14} className="text-emerald-400" />
                  <span>Export to CSV</span>
                </button>
                <button
                  onClick={exportToJSON}
                  className="btn-press w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors text-left cursor-pointer"
                >
                  <FileJson size={14} className="text-amber-400" />
                  <span>Export to JSON</span>
                </button>
              </div>
            )}
          </div>

          {/* Manual Refresh */}
          <button
            onClick={() => loadLogs(true)}
            disabled={loading}
            className="btn-press flex items-center gap-1.5 px-3 py-2 bg-slate-900/80 hover:bg-slate-800 text-slate-200 text-xs font-semibold rounded-xl border border-white/[0.08] transition-colors disabled:opacity-50 cursor-pointer"
            title={t.common.refresh}
          >
            <RefreshCw size={13} className={loading ? "animate-spin text-indigo-400" : ""} />
            <span>{t.common.refresh}</span>
          </button>
        </div>
      </div>

      {/* Summary Ribbon */}
      {summary && (
        <div className="glass-panel card-specular border border-white/[0.07] rounded-2xl p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs shadow-md">
          <div className="flex flex-wrap items-center gap-4 divide-x divide-white/[0.06]">
            {/* Filtered Count */}
            <div className="flex items-center gap-1.5">
              <span className="text-slate-400">Sample:</span>
              <span className="font-bold font-mono text-slate-100">{summary.total_requests.toLocaleString()}</span>
            </div>

            {/* Error Rate */}
            <div className="flex items-center gap-1.5 pl-4">
              <span className="text-slate-400">Errors:</span>
              <span
                className={`font-bold font-mono ${
                  summary.total_errors > 0 ? "text-rose-400" : "text-emerald-400"
                }`}
              >
                {summary.total_errors.toLocaleString()} ({summary.error_rate}%)
              </span>
            </div>

            {/* Fallback Rescued */}
            <div className="flex items-center gap-1.5 pl-4">
              <GitFork size={13} className="text-purple-400" />
              <span className="text-slate-400">Fallback Rescued:</span>
              <span className="font-bold font-mono text-purple-300">
                {summary.total_fallback_rescued.toLocaleString()}
              </span>
            </div>

            {/* Avg Latency */}
            <div className="flex items-center gap-1.5 pl-4">
              <Clock size={13} className="text-sky-400" />
              <span className="text-slate-400">Avg Latency:</span>
              <span className="font-bold font-mono text-sky-300">{summary.avg_latency_ms} ms</span>
            </div>

            {/* Total Tokens */}
            <div className="flex items-center gap-1.5 pl-4">
              <Zap size={13} className="text-amber-400" />
              <span className="text-slate-400">Tokens:</span>
              <span className="font-bold font-mono text-amber-300" title={`In: ${summary.total_prompt_tokens.toLocaleString()} • Out: ${summary.total_completion_tokens.toLocaleString()} • Cache: ${summary.total_cached_tokens.toLocaleString()}`}>
                {summary.total_tokens.toLocaleString()}
              </span>
            </div>

            {/* Estimated Cost */}
            <div className="flex items-center gap-1.5 pl-4">
              <Coins size={13} className="text-yellow-400" />
              <span className="text-slate-400">Cost:</span>
              <span className="font-bold font-mono text-yellow-300">${summary.total_cost_usd.toFixed(4)}</span>
            </div>
          </div>

          {hasActiveFilters && (
            <button
              onClick={handleResetFilters}
              className="btn-press text-[11px] text-slate-300 hover:text-white flex items-center gap-1 bg-white/[0.05] hover:bg-white/[0.08] px-2.5 py-1 rounded-xl border border-white/[0.08] transition-colors cursor-pointer"
            >
              <X size={12} />
              <span>Reset all filters</span>
            </button>
          )}
        </div>
      )}

      {/* Filter Toolbar: Quick Chips & Main Search */}
      <div className="glass-panel card-specular border border-white/[0.07] rounded-2xl p-4 space-y-3.5 shadow-md">
        {/* Row 1: Search, Time Periods, Quick Preset Chips, and Advanced Toggle */}
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          {/* Quick Preset Chips */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            {[
              { id: "", label: "All Requests" },
              { id: "fusion", label: "🧬 Fusion Ensemble" },
              { id: "errors", label: "🔴 Errors Only" },
              { id: "fallback", label: "🟣 Fallback Rescued" },
              { id: "stream", label: "⚡ Streaming" },
              { id: "slow", label: "⏳ Slow (>2s)" },
            ].map((chip) => (
              <button
                key={chip.id}
                onClick={() => {
                  setQuickPreset(chip.id);
                  setPage(1);
                }}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                  quickPreset === chip.id
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "bg-slate-950/80 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
              >
                {chip.label}
              </button>
            ))}
          </div>

          {/* Periods Tabs */}
          <div className="flex items-center bg-slate-950 border border-slate-800 rounded-xl p-1 text-xs">
            {[
              { id: "all", label: "All" },
              { id: "today", label: "Today" },
              { id: "yesterday", label: "Yesterday" },
              { id: "24h", label: "24h" },
              { id: "7d", label: "7d" },
              { id: "30d", label: "30d" },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setPeriod(p.id as any);
                  setShowCustomRange(false);
                  setPage(1);
                }}
                className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                  period === p.id && !showCustomRange
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {p.label}
              </button>
            ))}
            <button
              onClick={() => {
                setShowCustomRange(!showCustomRange);
                setPeriod("custom");
              }}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all flex items-center gap-1 ${
                period === "custom" || showCustomRange
                  ? "bg-indigo-600 text-white shadow-xs"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Calendar size={12} />
              <span>Calendar</span>
            </button>
          </div>
        </div>

        {/* Custom Calendar Accordion */}
        {showCustomRange && (
          <div className="p-2.5 bg-slate-950 rounded-lg border border-indigo-900/50 flex flex-wrap items-center gap-3 text-xs">
            <span className="text-slate-400 font-medium flex items-center gap-1.5">
              <Calendar size={13} className="text-indigo-400" />
              Date Range:
            </span>
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">From:</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">To:</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
              />
            </div>
            <button
              onClick={() => {
                setPeriod("custom");
                setPage(1);
                loadLogs(true);
              }}
              disabled={!startDate}
              className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
            >
              Apply
            </button>
          </div>
        )}

        {/* Row 2: Search Box + Sort + Advanced Toggle */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-slate-800/60">
          <div className="flex items-center gap-2 flex-1 min-w-[260px] max-w-lg">
            <div className="relative w-full">
              <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder={t.logs.searchPlaceholder}
                className="w-full pl-9 pr-8 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 text-xs placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              />
              {searchInput && (
                <button
                  onClick={() => setSearchInput("")}
                  className="absolute right-2.5 top-2.5 text-slate-500 hover:text-slate-300"
                >
                  <X size={13} />
                </button>
              )}
            </div>

            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors shrink-0 ${
                showAdvanced ||
                modeFilter ||
                statusFilter ||
                statusCodeFilter ||
                providerFilter ||
                modelFilter ||
                keyFilter
                  ? "bg-indigo-950/80 border-indigo-700 text-indigo-200"
                  : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              <SlidersHorizontal size={13} />
              <span>{t.common.filter}</span>
            </button>
          </div>

          {/* Sort Selector */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Sort by:</span>
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value);
                setPage(1);
              }}
              className="px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 text-xs focus:border-indigo-500 focus:outline-none"
            >
              <option value="created_at">Time (Created)</option>
              <option value="latency_ms">Latency (ms)</option>
              <option value="total_tokens">Tokens</option>
              <option value="estimated_cost_usd">Cost ($)</option>
            </select>

            <button
              onClick={() => {
                setSortOrder(sortOrder === "desc" ? "asc" : "desc");
                setPage(1);
              }}
              className="p-1.5 bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
              title={sortOrder === "desc" ? "Descending (Highest first)" : "Ascending (Lowest first)"}
            >
              <ArrowUpDown size={14} className={sortOrder === "asc" ? "rotate-180 text-indigo-400" : ""} />
            </button>

            {/* Page Size select */}
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="px-2 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 text-xs focus:border-indigo-500 focus:outline-none ml-2"
            >
              <option value={25}>25 rows</option>
              <option value={50}>50 rows</option>
              <option value={100}>100 rows</option>
              <option value={200}>200 rows</option>
            </select>
          </div>
        </div>

        {/* Collapsible Advanced Filters Tray */}
        {showAdvanced && (
          <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2.5 text-xs pt-3">
            {/* Mode Select */}
            <div>
              <label className="text-[10px] uppercase text-slate-400 block mb-1">Routing Mode</label>
              <select
                value={modeFilter}
                onChange={(e) => {
                  setModeFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 focus:border-indigo-500 focus:outline-none"
              >
                <option value="">All Modes</option>
                <option value="DIRECT">DIRECT</option>
                <option value="PRIORITY">PRIORITY (Fallback)</option>
                <option value="FUSION">FUSION (Ensemble)</option>
              </select>
            </div>

            {/* Status Code Select */}
            <div>
              <label className="text-[10px] uppercase text-slate-400 block mb-1">HTTP Status Code</label>
              <select
                value={statusCodeFilter}
                onChange={(e) => {
                  setStatusCodeFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 focus:border-indigo-500 focus:outline-none"
              >
                <option value="">All Codes</option>
                <option value="200">200 OK</option>
                <option value="429">429 Too Many Requests</option>
                <option value="500">500 Internal Error</option>
                <option value="502">502 Bad Gateway</option>
                <option value="503">503 Service Unavailable</option>
                <option value="504">504 Gateway Timeout</option>
                <option value="400">400 Bad Request</option>
              </select>
            </div>

            {/* Provider Select */}
            <div>
              <label className="text-[10px] uppercase text-slate-400 block mb-1">{t.common.provider}</label>
              <select
                value={providerFilter}
                onChange={(e) => {
                  setProviderFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 focus:border-indigo-500 focus:outline-none"
              >
                <option value="">All Providers</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Client Key Select */}
            <div>
              <label className="text-[10px] uppercase text-slate-400 block mb-1">Router API Key</label>
              <select
                value={keyFilter}
                onChange={(e) => {
                  setKeyFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 focus:border-indigo-500 focus:outline-none"
              >
                <option value="">All Keys</option>
                {routerKeys.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.name} ({k.key_prefix}••••)
                  </option>
                ))}
              </select>
            </div>

            {/* Model Text Filter */}
            <div>
              <label className="text-[10px] uppercase text-slate-400 block mb-1">Model Name</label>
              <input
                type="text"
                value={modelFilter}
                onChange={(e) => {
                  setModelFilter(e.target.value);
                  setPage(1);
                }}
                placeholder="Filter by model..."
                className="w-full px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>
        )}
      </div>

      {/* Main Logs Table */}
      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] overflow-hidden shadow-lg">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-white/[0.06] bg-slate-950/70 text-slate-400 font-semibold uppercase tracking-wider text-[10px] font-mono">
                <th
                  onClick={() => handleSort("created_at")}
                  className="py-2.5 px-3 cursor-pointer select-none group/th hover:text-slate-200 transition-colors w-32"
                >
                  <div className="flex items-center gap-1">
                    <span>Time & ID</span>
                    <ArrowUpDown
                      size={11}
                      className={
                        sortBy === "created_at"
                          ? `text-indigo-400 ${sortOrder === "asc" ? "rotate-180" : ""}`
                          : "text-slate-600 group-hover/th:text-slate-400"
                      }
                    />
                  </div>
                </th>
                <th className="py-2.5 px-3">Model & Upstream</th>
                <th className="py-2.5 px-3 w-28">Key & Mode</th>
                <th className="py-2.5 px-3 w-36">{t.common.status}</th>
                <th
                  onClick={() => handleSort("latency_ms")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none group/th hover:text-slate-200 transition-colors w-20"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Latency</span>
                    <ArrowUpDown
                      size={11}
                      className={
                        sortBy === "latency_ms"
                          ? `text-indigo-400 ${sortOrder === "asc" ? "rotate-180" : ""}`
                          : "text-slate-600 group-hover/th:text-slate-400"
                      }
                    />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("total_tokens")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none group/th hover:text-slate-200 transition-colors w-24"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>{t.common.tokens}</span>
                    <ArrowUpDown
                      size={11}
                      className={
                        sortBy === "total_tokens"
                          ? `text-indigo-400 ${sortOrder === "asc" ? "rotate-180" : ""}`
                          : "text-slate-600 group-hover/th:text-slate-400"
                      }
                    />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("estimated_cost_usd")}
                  className="py-2.5 px-3 text-right cursor-pointer select-none group/th hover:text-slate-200 transition-colors w-20"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Cost ($)</span>
                    <ArrowUpDown
                      size={11}
                      className={
                        sortBy === "estimated_cost_usd"
                          ? `text-indigo-400 ${sortOrder === "asc" ? "rotate-180" : ""}`
                          : "text-slate-600 group-hover/th:text-slate-400"
                      }
                    />
                  </div>
                </th>
                <th className="py-2.5 px-2 w-8 text-center">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-slate-400">
                    {loading ? "Loading request logs..." : t.logs.noLogsFound}
                  </td>
                </tr>
              ) : (
                logs.map((l) => {
                  const totalTokens = (l.input_tokens || 0) + (l.output_tokens || 0);
                  const isSuccess = l.status_code >= 200 && l.status_code < 300;
                  const is429 = l.status_code === 429;
                  const is5xx = l.status_code >= 500;
                  const isStream = !!l.metadata_json?.stream;
                  const attemptsCount = l.attempts?.length || 1;

                  return (
                    <tr
                      key={l.id}
                      onClick={() => setSelectedLog(l)}
                      className="hover:bg-slate-800/40 cursor-pointer transition-colors group"
                    >
                      {/* Timestamp & Request ID */}
                      <td className="py-2 px-3">
                        <div className="text-[11px] font-mono text-slate-200 font-medium whitespace-nowrap">
                          {formatDateTime(l.created_at)}
                        </div>
                        <div
                          className="text-[10px] font-mono text-slate-500 truncate max-w-[110px]"
                          title={l.request_id}
                        >
                          {l.request_id}
                        </div>
                      </td>

                      {/* Requested Model & Upstream Provider */}
                      <td className="py-2 px-3 min-w-0">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span
                            className="font-mono text-[11px] text-indigo-300 font-semibold truncate"
                            title={l.requested_model}
                          >
                            {l.requested_model}
                          </span>
                          {isStream && (
                            <span className="text-amber-400 text-[10px] shrink-0" title="Streaming request (stream: true)">
                              ⚡
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-slate-400 truncate flex items-center gap-1 mt-0.5">
                          {l.mode === "FUSION" ? (
                            <span className="inline-flex items-center gap-1 font-mono text-purple-300 truncate">
                              <span className="px-1 py-0.2 rounded bg-purple-950/80 text-purple-300 border border-purple-800/60 text-[9px] font-bold shrink-0">
                                Judge
                              </span>
                              <span className="truncate" title={l.upstream_model || l.resolved_provider_name || "Ensemble"}>
                                {l.upstream_model || l.resolved_provider_name || "Ensemble"}
                              </span>
                            </span>
                          ) : l.resolved_provider_name ? (
                            <>
                              <span className="font-semibold text-purple-300 shrink-0">
                                {l.resolved_provider_name}
                              </span>
                              {l.upstream_model && (
                                <span className="text-slate-500 font-mono truncate" title={l.upstream_model}>
                                  /{l.upstream_model}
                                </span>
                              )}
                            </>
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </div>
                      </td>

                      {/* Client Key & Mode */}
                      <td className="py-2 px-3">
                        <div className="truncate max-w-[110px]">
                          {l.router_key_name ? (
                            <span
                              className="inline-flex items-center gap-1 text-[10px] font-mono text-indigo-300 truncate"
                              title={l.router_key_name}
                            >
                              <Key size={9} className="shrink-0" />
                              <span className="truncate">{l.router_key_name}</span>
                            </span>
                          ) : (
                            <span className="text-slate-500 font-mono text-[10px]">Admin/Direct</span>
                          )}
                        </div>
                        <div className="mt-0.5">
                          <span
                            className={`inline-block px-1.5 py-0.2 rounded text-[9px] font-semibold font-mono border ${
                              l.mode === "PRIORITY"
                                ? "bg-purple-950/60 text-purple-300 border-purple-800/60"
                                : l.mode === "FUSION"
                                ? "bg-amber-950/60 text-amber-300 border-amber-800/60"
                                : "bg-slate-800 text-slate-300 border-slate-700/60"
                            }`}
                          >
                            {l.mode}
                          </span>
                        </div>
                      </td>

                      {/* Status & HTTP Code */}
                      <td className="py-2 px-3">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span
                            className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold border ${
                              isSuccess
                                ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/60"
                                : is429
                                ? "bg-amber-950/60 text-amber-300 border-amber-800/60"
                                : is5xx
                                ? "bg-rose-950/60 text-rose-300 border-rose-800/60"
                                : "bg-slate-950/60 text-slate-300 border-slate-700/60"
                            }`}
                          >
                            {l.status_code}
                          </span>
                          <StatusBadge status={l.status} size="sm" />
                          {attemptsCount > 1 && (
                            <span
                              className="px-1 py-0.2 rounded text-[9px] font-mono bg-purple-950 text-purple-300 border border-purple-800"
                              title={`Attempts made: ${attemptsCount}`}
                            >
                              🔁 {attemptsCount}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Latency */}
                      <td className="py-2 px-3 text-right font-mono text-[11px] text-sky-300 font-medium whitespace-nowrap">
                        {l.latency_ms.toFixed(0)} ms
                      </td>

                      {/* Tokens */}
                      <td
                        className="py-2 px-3 text-right font-mono text-amber-300 text-[11px] whitespace-nowrap"
                        title={`Prompt: ${l.input_tokens.toLocaleString()} | Output: ${l.output_tokens.toLocaleString()} | Cache: ${l.cached_tokens.toLocaleString()}`}
                      >
                        {totalTokens > 0 ? (
                          <div>
                            <span>{totalTokens.toLocaleString()}</span>
                            {l.cached_tokens > 0 && (
                              <span className="text-[9px] text-emerald-400 ml-1">⚡cache</span>
                            )}
                          </div>
                        ) : (
                          "—"
                        )}
                      </td>

                      {/* Cost */}
                      <td className="py-2 px-3 text-right font-mono text-yellow-300 text-[11px] whitespace-nowrap">
                        ${l.estimated_cost_usd.toFixed(4)}
                      </td>

                      {/* Inspect Action */}
                      <td className="py-2 px-2 text-center text-slate-500 group-hover:text-indigo-400 w-8">
                        <Eye size={14} className="mx-auto" />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 bg-slate-950/60 border-t border-white/[0.06] text-xs text-slate-400">
          <div>
            Showing <span className="font-semibold text-slate-200">{startIdx}</span> to{" "}
            <span className="font-semibold text-slate-200">{endIdx}</span> of{" "}
            <span className="font-semibold text-slate-200">{totalCount.toLocaleString()}</span> logs
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="btn-press flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-200 rounded-xl border border-white/[0.06] disabled:opacity-40 disabled:pointer-events-none transition-colors cursor-pointer"
            >
              <ChevronLeft size={14} />
              <span>{t.common.back}</span>
            </button>

            <span className="px-2 py-1 font-mono text-slate-300">
              Page {page} of {totalPages}
            </span>

            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              className="btn-press flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-200 rounded-xl border border-white/[0.06] disabled:opacity-40 disabled:pointer-events-none transition-colors cursor-pointer"
            >
              <span>{t.common.next}</span>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Slide-over Deep Request Inspector Drawer */}
      <LogDetailDrawer
        log={selectedLog}
        onClose={() => setSelectedLog(null)}
        onReplayInPlayground={handleReplayInPlayground}
      />
    </div>
  );
};
