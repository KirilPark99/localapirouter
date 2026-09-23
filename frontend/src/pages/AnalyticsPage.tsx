import React, { useEffect, useState, useMemo } from "react";
import {
  BarChart3,
  TrendingUp,
  KeyRound,
  ShieldCheck,
  Cpu,
  Boxes,
  GitFork,
  Coins,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Search,
  Zap,
  ChevronDown,
  ChevronRight,
  Filter,
  X,
  Calendar,
  Download,
  FileSpreadsheet,
  FileJson,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Layers,
  Sparkles,
  ChevronLeft,
  ChevronsLeft,
  ChevronsRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { DetailedAnalyticsResponse } from "../types";
import { ActivityChart } from "../components/ActivityChart";
import { useI18n } from "../i18n";

export type ModelSortField =
  | "model_name"
  | "provider_name"
  | "requests_count"
  | "success_rate"
  | "input_tokens"
  | "output_tokens"
  | "cached_tokens"
  | "reasoning_tokens"
  | "total_tokens"
  | "latency"
  | "tokens_per_sec"
  | "estimated_cost_usd";

export const MODEL_SORT_LABELS: Record<ModelSortField, string> = {
  model_name: "Model",
  provider_name: "Provider",
  requests_count: "Requests",
  success_rate: "Success Rate",
  input_tokens: "Input Tokens",
  output_tokens: "Output Tokens",
  cached_tokens: "Cached Tokens",
  reasoning_tokens: "Reasoning (CoT)",
  total_tokens: "Total Tokens",
  latency: "Latency (p50/p90)",
  tokens_per_sec: "Speed (tok/s)",
  estimated_cost_usd: "Cost ($)",
};

export type ProviderSortField =
  | "name"
  | "slug"
  | "requests_count"
  | "success_count"
  | "failure_count"
  | "success_rate"
  | "total_tokens"
  | "latency"
  | "tokens_per_sec"
  | "estimated_cost_usd";

export const PROVIDER_SORT_LABELS: Record<ProviderSortField, string> = {
  name: "Provider",
  slug: "Slug",
  requests_count: "Requests",
  success_count: "Success",
  failure_count: "Failures",
  success_rate: "Success Rate",
  total_tokens: "Total Tokens",
  latency: "Latency (p50/p90)",
  tokens_per_sec: "Speed (tok/s)",
  estimated_cost_usd: "Cost ($)",
};

export type KeySortField =
  | "name"
  | "prefix"
  | "requests_count"
  | "success_count"
  | "failure_count"
  | "success_rate"
  | "total_tokens"
  | "latency"
  | "tokens_per_sec"
  | "estimated_cost_usd";

export const KEY_SORT_LABELS: Record<KeySortField, string> = {
  name: "Key Name",
  prefix: "Prefix",
  requests_count: "Requests",
  success_count: "Success",
  failure_count: "Errors",
  success_rate: "Success Rate",
  total_tokens: "Total Tokens",
  latency: "Latency (p50/p90)",
  tokens_per_sec: "Speed (tok/s)",
  estimated_cost_usd: "Cost ($)",
};

export type CredentialSortField =
  | "name"
  | "provider_name"
  | "status"
  | "requests_count"
  | "fallback_success_count"
  | "failure_count"
  | "success_rate"
  | "total_tokens"
  | "latency"
  | "tokens_per_sec";

export const CREDENTIAL_SORT_LABELS: Record<CredentialSortField, string> = {
  name: "Provider Key",
  provider_name: "Provider",
  status: "Status",
  requests_count: "Requests",
  fallback_success_count: "Fallback Rescued",
  failure_count: "Failures",
  success_rate: "Success Rate",
  total_tokens: "Total Tokens",
  latency: "Latency (p50/p90)",
  tokens_per_sec: "Speed (tok/s)",
};

export type ProfileSortField =
  | "name"
  | "mode"
  | "requests_count"
  | "first_candidate_success_count"
  | "fallback_success_count"
  | "failure_count"
  | "fallback_rate"
  | "total_tokens"
  | "latency"
  | "tokens_per_sec";

export const PROFILE_SORT_LABELS: Record<ProfileSortField, string> = {
  name: "Profile Name",
  mode: "Mode",
  requests_count: "Requests",
  first_candidate_success_count: "Primary Candidate",
  fallback_success_count: "Fallback Rescued",
  failure_count: "Chain Failures",
  fallback_rate: "Fallback Rate",
  total_tokens: "Total Tokens",
  latency: "Latency (p50/p90)",
  tokens_per_sec: "Speed (tok/s)",
};

// Reusable Pagination Bar Component for all tabs
const TablePagination: React.FC<{
  currentPage: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
  itemName: string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}> = ({
  currentPage,
  pageSize,
  totalItems,
  totalPages,
  itemName,
  onPageChange,
  onPageSizeChange,
}) => {
  if (totalItems === 0) return null;

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 bg-slate-950/60 border-t border-slate-800 text-xs text-slate-400">
      {/* Left: Range and Page Size */}
      <div className="flex flex-wrap items-center gap-3">
        <div>
          Showing{" "}
          <span className="font-semibold text-slate-200 font-mono">
            {(currentPage - 1) * pageSize + 1}
          </span>
          –
          <span className="font-semibold text-slate-200 font-mono">
            {Math.min(currentPage * pageSize, totalItems)}
          </span>{" "}
          of{" "}
          <span className="font-semibold text-slate-200 font-mono">
            {totalItems}
          </span>{" "}
          {itemName}
        </div>

        <div className="flex items-center gap-1.5 text-slate-400 pl-3 border-l border-slate-800">
          <span>Per page:</span>
          <select
            value={pageSize}
            onChange={(e) => {
              onPageSizeChange(Number(e.target.value));
              onPageChange(1);
            }}
            className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-indigo-500 font-mono text-[11px]"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={10000}>All</option>
          </select>
        </div>
      </div>

      {/* Right: Page Navigation Buttons */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage <= 1}
          className="p-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-lg border border-slate-800 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          title="First page"
        >
          <ChevronsLeft size={14} />
        </button>
        <button
          onClick={() => onPageChange(Math.max(1, currentPage - 1))}
          disabled={currentPage <= 1}
          className="p-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-lg border border-slate-800 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          title="Previous page"
        >
          <ChevronLeft size={14} />
        </button>

        <div className="flex items-center gap-1 px-1">
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter((p) => {
              if (totalPages <= 7) return true;
              if (p === 1 || p === totalPages) return true;
              return Math.abs(p - currentPage) <= 1;
            })
            .reduce<(number | string)[]>((acc, p, idx, arr) => {
              if (idx > 0 && (p as number) - (arr[idx - 1] as number) > 1) {
                acc.push(`dots-${p}`);
              }
              acc.push(p);
              return acc;
            }, [])
            .map((p) => {
              if (typeof p === "string") {
                return (
                  <span key={p} className="px-1 text-slate-500 select-none">
                    …
                  </span>
                );
              }
              const isCurrent = p === currentPage;
              return (
                <button
                  key={p}
                  onClick={() => onPageChange(p)}
                  className={`min-w-[28px] h-7 px-1.5 rounded-lg text-xs font-mono transition-colors ${
                    isCurrent
                      ? "bg-indigo-600 text-white font-bold shadow-xs"
                      : "bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800"
                  }`}
                >
                  {p}
                </button>
              );
            })}
        </div>

        <button
          onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
          disabled={currentPage >= totalPages}
          className="p-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-lg border border-slate-800 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          title="Next page"
        >
          <ChevronRight size={14} />
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage >= totalPages}
          className="p-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 rounded-lg border border-slate-800 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          title="Last page"
        >
          <ChevronsRight size={14} />
        </button>
      </div>
    </div>
  );
};

// Reusable Top Sort Ribbon Component
const TableSortRibbon: React.FC<{
  currentSortLabel: string;
  sortOrder: "asc" | "desc";
  totalCount: number;
  totalLabel: string;
  onToggleOrder: () => void;
}> = ({ currentSortLabel, sortOrder, totalCount, totalLabel, onToggleOrder }) => (
  <div className="px-4 py-2.5 bg-slate-950/50 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
    <div className="flex items-center flex-wrap gap-2">
      <span className="text-slate-400">Sort:</span>
      <button
        onClick={onToggleOrder}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-indigo-950/70 border border-indigo-700/60 rounded-lg text-indigo-300 font-medium hover:bg-indigo-900/60 transition-colors shadow-xs"
        title="Click to toggle sort direction (ascending / descending)"
      >
        <span>{currentSortLabel}</span>
        {sortOrder === "desc" ? (
          <ArrowDown size={12} className="text-indigo-400" />
        ) : (
          <ArrowUp size={12} className="text-indigo-400" />
        )}
        <span className="text-[10px] text-indigo-400/80 uppercase tracking-wider">
          {sortOrder === "desc" ? "descending" : "ascending"}
        </span>
      </button>
      <span className="text-slate-500 text-[11px] hidden md:inline">
        • Click any table cell or column header to re-sort
      </span>
    </div>
    <div className="text-slate-400 text-xs flex items-center gap-2">
      <span>
        {totalLabel}:{" "}
        <span className="font-semibold text-slate-200 font-mono">
          {totalCount}
        </span>
      </span>
    </div>
  </div>
);

// Generic Sortable Header helper
function renderSortHeader<T extends string>(
  field: T,
  label: string,
  currentSortField: T,
  currentSortOrder: "asc" | "desc",
  onSort: (field: T) => void,
  align: "left" | "right" = "left",
  padding: string = "px-3"
) {
  const isActive = currentSortField === field;
  return (
    <th
      onClick={() => onSort(field)}
      className={`${padding} py-2.5 uppercase text-[10px] font-semibold transition-colors cursor-pointer select-none group/th ${
        isActive
          ? "text-indigo-300 bg-indigo-950/40"
          : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
      } ${align === "right" ? "text-right" : "text-left"}`}
      title={`Sort by "${label}" (${
        isActive
          ? currentSortOrder === "desc"
            ? "ascending"
            : "descending"
          : "descending"
      })`}
    >
      <div
        className={`flex items-center gap-1 ${
          align === "right" ? "justify-end" : "justify-start"
        }`}
      >
        <span>{label}</span>
        {isActive ? (
          currentSortOrder === "desc" ? (
            <ArrowDown size={11} className="text-indigo-400 shrink-0" />
          ) : (
            <ArrowUp size={11} className="text-indigo-400 shrink-0" />
          )
        ) : (
          <ArrowUpDown
            size={11}
            className="text-slate-500 opacity-0 group-hover/th:opacity-100 transition-opacity shrink-0"
          />
        )}
      </div>
    </th>
  );
}

// Helpers for clickable cell styling & tooltips
function getSortCellClass<T extends string>(
  field: T,
  activeField: T,
  extra: string = ""
) {
  const isActive = activeField === field;
  return `px-3 py-2.5 cursor-pointer transition-colors select-none group/cell ${
    isActive
      ? "bg-indigo-950/30 font-semibold ring-1 ring-inset ring-indigo-500/20 text-indigo-200"
      : "hover:bg-slate-800/60"
  } ${extra}`;
}

function getSortCellTitle<T extends string>(
  field: T,
  label: string,
  activeField: T,
  sortOrder: "asc" | "desc"
) {
  const isCur = activeField === field;
  const nextDir = isCur && sortOrder === "desc" ? "ascending" : "descending";
  return `Click to sort by "${label}" (${nextDir})`;
}

export const AnalyticsPage: React.FC = () => {
  const { t } = useI18n();
  const [period, setPeriod] = useState<
    "today" | "yesterday" | "24h" | "7d" | "30d" | "this_month" | "custom" | "all"
  >("all");
  const [granularity, setGranularity] = useState<"hour" | "day" | undefined>(undefined);
  const [showCustomRange, setShowCustomRange] = useState<boolean>(false);
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  const [drillFilter, setDrillFilter] = useState<{
    type: string;
    value: string;
    label: string;
  } | null>(null);

  const [data, setData] = useState<DetailedAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeSubTab, setActiveSubTab] = useState<
    "models" | "providers" | "router_keys" | "credentials" | "profiles"
  >("models");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [expandedProfileSlugs, setExpandedProfileSlugs] = useState<Record<string, boolean>>({});
  const [showExportMenu, setShowExportMenu] = useState<boolean>(false);

  // 1. Models Table Sorting & Pagination states
  const [modelSortField, setModelSortField] = useState<ModelSortField>("requests_count");
  const [modelSortOrder, setModelSortOrder] = useState<"asc" | "desc">("desc");
  const [modelPage, setModelPage] = useState<number>(1);
  const [modelPageSize, setModelPageSize] = useState<number>(10);

  // 2. Providers Table Sorting & Pagination states
  const [providerSortField, setProviderSortField] = useState<ProviderSortField>("requests_count");
  const [providerSortOrder, setProviderSortOrder] = useState<"asc" | "desc">("desc");
  const [providerPage, setProviderPage] = useState<number>(1);
  const [providerPageSize, setProviderPageSize] = useState<number>(10);

  // 3. Router Keys Table Sorting & Pagination states
  const [keySortField, setKeySortField] = useState<KeySortField>("requests_count");
  const [keySortOrder, setKeySortOrder] = useState<"asc" | "desc">("desc");
  const [keyPage, setKeyPage] = useState<number>(1);
  const [keyPageSize, setKeyPageSize] = useState<number>(10);

  // 4. Credentials Table Sorting & Pagination states
  const [credSortField, setCredSortField] = useState<CredentialSortField>("requests_count");
  const [credSortOrder, setCredSortOrder] = useState<"asc" | "desc">("desc");
  const [credPage, setCredPage] = useState<number>(1);
  const [credPageSize, setCredPageSize] = useState<number>(10);

  // 5. Profiles Table Sorting & Pagination states
  const [profileSortField, setProfileSortField] = useState<ProfileSortField>("requests_count");
  const [profileSortOrder, setProfileSortOrder] = useState<"asc" | "desc">("desc");
  const [profilePage, setProfilePage] = useState<number>(1);
  const [profilePageSize, setProfilePageSize] = useState<number>(10);

  const handleSortModel = (field: ModelSortField) => {
    if (modelSortField === field) {
      setModelSortOrder((prev) => (prev === "desc" ? "asc" : "desc"));
    } else {
      setModelSortField(field);
      setModelSortOrder(
        field === "model_name" || field === "provider_name" ? "asc" : "desc"
      );
    }
    setModelPage(1);
  };

  const handleSortProvider = (field: ProviderSortField) => {
    if (providerSortField === field) {
      setProviderSortOrder((prev) => (prev === "desc" ? "asc" : "desc"));
    } else {
      setProviderSortField(field);
      setProviderSortOrder(
        field === "name" || field === "slug" ? "asc" : "desc"
      );
    }
    setProviderPage(1);
  };

  const handleSortKey = (field: KeySortField) => {
    if (keySortField === field) {
      setKeySortOrder((prev) => (prev === "desc" ? "asc" : "desc"));
    } else {
      setKeySortField(field);
      setKeySortOrder(
        field === "name" || field === "prefix" ? "asc" : "desc"
      );
    }
    setKeyPage(1);
  };

  const handleSortCred = (field: CredentialSortField) => {
    if (credSortField === field) {
      setCredSortOrder((prev) => (prev === "desc" ? "asc" : "desc"));
    } else {
      setCredSortField(field);
      setCredSortOrder(
        field === "name" || field === "provider_name" || field === "status" ? "asc" : "desc"
      );
    }
    setCredPage(1);
  };

  const handleSortProfile = (field: ProfileSortField) => {
    if (profileSortField === field) {
      setProfileSortOrder((prev) => (prev === "desc" ? "asc" : "desc"));
    } else {
      setProfileSortField(field);
      setProfileSortOrder(
        field === "name" || field === "mode" ? "asc" : "desc"
      );
    }
    setProfilePage(1);
  };

  const toggleProfileExpand = (slug: string) => {
    setExpandedProfileSlugs((prev) => ({
      ...prev,
      [slug]: !prev[slug],
    }));
  };

  const loadStats = async (
    selectedPeriod: string,
    selectedGranularity?: "hour" | "day",
    start?: string,
    end?: string,
    filter?: { type: string; value: string } | null
  ) => {
    setLoading(true);
    try {
      let url = `/api/admin/dashboard/detailed-stats?period=${selectedPeriod}`;
      if (selectedGranularity) {
        url += `&granularity=${selectedGranularity}`;
      }
      if (selectedPeriod === "custom" && start && end) {
        url += `&start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`;
      }
      if (filter && filter.type && filter.value) {
        url += `&filter_type=${encodeURIComponent(filter.type)}&filter_value=${encodeURIComponent(filter.value)}`;
      }
      const res = await apiRequest<DetailedAnalyticsResponse>(url);
      setData(res);
      setGranularity(res.granularity || "hour");
    } catch (err) {
      console.error("Failed to load analytics:", err);
    } finally {
      setLoading(false);
    }
  };

  const handlePeriodChange = (
    p: "today" | "yesterday" | "24h" | "7d" | "30d" | "this_month" | "custom" | "all"
  ) => {
    if (p === "custom") {
      setShowCustomRange(true);
      return;
    }
    setShowCustomRange(false);
    setPeriod(p);
    setGranularity(undefined);
    loadStats(p, undefined, undefined, undefined, drillFilter);
  };

  const handleApplyCustomRange = () => {
    if (!startDate || !endDate) return;
    setPeriod("custom");
    loadStats("custom", granularity, startDate, endDate, drillFilter);
  };

  const handleGranularityChange = (g: "hour" | "day") => {
    setGranularity(g);
    loadStats(period, g, startDate, endDate, drillFilter);
  };

  const handleApplyDrillFilter = (type: string, value: string, label: string) => {
    const newFilter = { type, value, label };
    setDrillFilter(newFilter);
    loadStats(period, granularity, startDate, endDate, newFilter);
  };

  const handleClearDrillFilter = () => {
    setDrillFilter(null);
    loadStats(period, granularity, startDate, endDate, null);
  };

  useEffect(() => {
    loadStats(period);
  }, []);

  const summary = data?.summary;
  const comparison = data?.comparison;
  const funnel = data?.fallback_funnel;

  // Filtered lists based on search query
  const filteredModels = useMemo(() => {
    if (!data) return [];
    if (!searchQuery) return data.by_models;
    const q = searchQuery.toLowerCase();
    return data.by_models.filter(
      (m) =>
        m.model_name.toLowerCase().includes(q) ||
        m.provider_name.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  // Reset pagination to page 1 on filter/search change
  useEffect(() => {
    setModelPage(1);
    setProviderPage(1);
    setKeyPage(1);
    setCredPage(1);
    setProfilePage(1);
  }, [searchQuery, period, drillFilter]);

  // 1. Models sorting & pagination
  const sortedModels = useMemo(() => {
    return [...filteredModels].sort((a, b) => {
      let valA: any = 0;
      let valB: any = 0;

      switch (modelSortField) {
        case "model_name":
          valA = a.model_name.toLowerCase();
          valB = b.model_name.toLowerCase();
          return modelSortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "provider_name":
          valA = a.provider_name.toLowerCase();
          valB = b.provider_name.toLowerCase();
          return modelSortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "requests_count":
          valA = a.requests_count;
          valB = b.requests_count;
          break;
        case "success_rate":
          valA = a.success_rate;
          valB = b.success_rate;
          break;
        case "input_tokens":
          valA = a.input_tokens;
          valB = b.input_tokens;
          break;
        case "output_tokens":
          valA = a.output_tokens;
          valB = b.output_tokens;
          break;
        case "cached_tokens":
          valA = a.cached_tokens;
          valB = b.cached_tokens;
          break;
        case "reasoning_tokens":
          valA = a.reasoning_tokens;
          valB = b.reasoning_tokens;
          break;
        case "total_tokens":
          valA = a.total_tokens;
          valB = b.total_tokens;
          break;
        case "latency":
          valA = a.p50_latency_ms ?? a.avg_latency_ms ?? 0;
          valB = b.p50_latency_ms ?? b.avg_latency_ms ?? 0;
          break;
        case "tokens_per_sec":
          valA = a.tokens_per_sec ?? 0;
          valB = b.tokens_per_sec ?? 0;
          break;
        case "estimated_cost_usd":
          valA = a.estimated_cost_usd;
          valB = b.estimated_cost_usd;
          break;
        default:
          valA = a.requests_count;
          valB = b.requests_count;
      }

      if (valA < valB) return modelSortOrder === "asc" ? -1 : 1;
      if (valA > valB) return modelSortOrder === "asc" ? 1 : -1;
      return 0;
    });
  }, [filteredModels, modelSortField, modelSortOrder]);

  const totalModelPages = Math.max(1, Math.ceil(sortedModels.length / modelPageSize));
  const paginatedModels = useMemo(() => {
    if (modelPageSize >= sortedModels.length) return sortedModels;
    const start = (modelPage - 1) * modelPageSize;
    return sortedModels.slice(start, start + modelPageSize);
  }, [sortedModels, modelPage, modelPageSize]);

  // 2. Providers sorting & pagination
  const filteredProviders = useMemo(() => {
    if (!data) return [];
    if (!searchQuery) return data.by_providers;
    const q = searchQuery.toLowerCase();
    return data.by_providers.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.slug.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  const sortedProviders = useMemo(() => {
    return [...filteredProviders].sort((a, b) => {
      let valA: any = 0;
      let valB: any = 0;

      switch (providerSortField) {
        case "name":
          valA = a.name.toLowerCase();
          valB = b.name.toLowerCase();
          return providerSortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "slug":
          valA = a.slug.toLowerCase();
          valB = b.slug.toLowerCase();
          return providerSortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "requests_count":
          valA = a.requests_count;
          valB = b.requests_count;
          break;
        case "success_count":
          valA = a.success_count;
          valB = b.success_count;
          break;
        case "failure_count":
          valA = a.failure_count;
          valB = b.failure_count;
          break;
        case "success_rate":
          valA = a.success_rate;
          valB = b.success_rate;
          break;
        case "total_tokens":
          valA = a.total_tokens;
          valB = b.total_tokens;
          break;
        case "latency":
          valA = a.p50_latency_ms ?? a.avg_latency_ms ?? 0;
          valB = b.p50_latency_ms ?? b.avg_latency_ms ?? 0;
          break;
        case "tokens_per_sec":
          valA = a.tokens_per_sec ?? 0;
          valB = b.tokens_per_sec ?? 0;
          break;
        case "estimated_cost_usd":
          valA = a.estimated_cost_usd;
          valB = b.estimated_cost_usd;
          break;
        default:
          valA = a.requests_count;
          valB = b.requests_count;
      }

      if (valA < valB) return providerSortOrder === "asc" ? -1 : 1;
      if (valA > valB) return providerSortOrder === "asc" ? 1 : -1;
      return 0;
    });
  }, [filteredProviders, providerSortField, providerSortOrder]);

  const totalProviderPages = Math.max(1, Math.ceil(sortedProviders.length / providerPageSize));
  const paginatedProviders = useMemo(() => {
    if (providerPageSize >= sortedProviders.length) return sortedProviders;
    const start = (providerPage - 1) * providerPageSize;
    return sortedProviders.slice(start, start + providerPageSize);
  }, [sortedProviders, providerPage, providerPageSize]);

  // 3. Router Keys sorting & pagination
  const filteredRouterKeys = useMemo(() => {
    if (!data) return [];
    if (!searchQuery) return data.by_router_keys;
    const q = searchQuery.toLowerCase();
    return data.by_router_keys.filter(
      (k) =>
        k.name.toLowerCase().includes(q) ||
        k.prefix.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  const sortedKeys = useMemo(() => {
    return [...filteredRouterKeys].sort((a, b) => {
      let valA: any = 0;
      let valB: any = 0;

      switch (keySortField) {
        case "name":
          valA = a.name.toLowerCase();
          valB = b.name.toLowerCase();
          return keySortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "prefix":
          valA = a.prefix.toLowerCase();
          valB = b.prefix.toLowerCase();
          return keySortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "requests_count":
          valA = a.requests_count;
          valB = b.requests_count;
          break;
        case "success_count":
          valA = a.success_count;
          valB = b.success_count;
          break;
        case "failure_count":
          valA = a.failure_count;
          valB = b.failure_count;
          break;
        case "success_rate":
          valA = a.success_rate;
          valB = b.success_rate;
          break;
        case "total_tokens":
          valA = a.total_tokens;
          valB = b.total_tokens;
          break;
        case "latency":
          valA = a.p50_latency_ms ?? a.avg_latency_ms ?? 0;
          valB = b.p50_latency_ms ?? b.avg_latency_ms ?? 0;
          break;
        case "tokens_per_sec":
          valA = a.tokens_per_sec ?? 0;
          valB = b.tokens_per_sec ?? 0;
          break;
        case "estimated_cost_usd":
          valA = a.estimated_cost_usd;
          valB = b.estimated_cost_usd;
          break;
        default:
          valA = a.requests_count;
          valB = b.requests_count;
      }

      if (valA < valB) return keySortOrder === "asc" ? -1 : 1;
      if (valA > valB) return keySortOrder === "asc" ? 1 : -1;
      return 0;
    });
  }, [filteredRouterKeys, keySortField, keySortOrder]);

  const totalKeyPages = Math.max(1, Math.ceil(sortedKeys.length / keyPageSize));
  const paginatedKeys = useMemo(() => {
    if (keyPageSize >= sortedKeys.length) return sortedKeys;
    const start = (keyPage - 1) * keyPageSize;
    return sortedKeys.slice(start, start + keyPageSize);
  }, [sortedKeys, keyPage, keyPageSize]);

  // 4. Credentials sorting & pagination
  const filteredCredentials = useMemo(() => {
    if (!data) return [];
    if (!searchQuery) return data.by_credentials;
    const q = searchQuery.toLowerCase();
    return data.by_credentials.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.provider_name.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  const sortedCreds = useMemo(() => {
    return [...filteredCredentials].sort((a, b) => {
      let valA: any = 0;
      let valB: any = 0;

      switch (credSortField) {
        case "name":
          valA = a.name.toLowerCase();
          valB = b.name.toLowerCase();
          return credSortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "provider_name":
          valA = a.provider_name.toLowerCase();
          valB = b.provider_name.toLowerCase();
          return credSortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "status":
          valA = a.status.toLowerCase();
          valB = b.status.toLowerCase();
          return credSortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "requests_count":
          valA = a.requests_count;
          valB = b.requests_count;
          break;
        case "fallback_success_count":
          valA = a.fallback_success_count;
          valB = b.fallback_success_count;
          break;
        case "failure_count":
          valA = a.failure_count;
          valB = b.failure_count;
          break;
        case "success_rate":
          valA = a.success_rate;
          valB = b.success_rate;
          break;
        case "total_tokens":
          valA = a.total_tokens;
          valB = b.total_tokens;
          break;
        case "latency":
          valA = a.p50_latency_ms ?? a.avg_latency_ms ?? 0;
          valB = b.p50_latency_ms ?? b.avg_latency_ms ?? 0;
          break;
        case "tokens_per_sec":
          valA = a.tokens_per_sec ?? 0;
          valB = b.tokens_per_sec ?? 0;
          break;
        default:
          valA = a.requests_count;
          valB = b.requests_count;
      }

      if (valA < valB) return credSortOrder === "asc" ? -1 : 1;
      if (valA > valB) return credSortOrder === "asc" ? 1 : -1;
      return 0;
    });
  }, [filteredCredentials, credSortField, credSortOrder]);

  const totalCredPages = Math.max(1, Math.ceil(sortedCreds.length / credPageSize));
  const paginatedCreds = useMemo(() => {
    if (credPageSize >= sortedCreds.length) return sortedCreds;
    const start = (credPage - 1) * credPageSize;
    return sortedCreds.slice(start, start + credPageSize);
  }, [sortedCreds, credPage, credPageSize]);

  // 5. Profiles sorting & pagination
  const filteredProfiles = useMemo(() => {
    if (!data) return [];
    if (!searchQuery) return data.by_profiles;
    const q = searchQuery.toLowerCase();
    return data.by_profiles.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.slug.toLowerCase().includes(q)
    );
  }, [data, searchQuery]);

  const sortedProfiles = useMemo(() => {
    return [...filteredProfiles].sort((a, b) => {
      let valA: any = 0;
      let valB: any = 0;

      switch (profileSortField) {
        case "name":
          valA = a.name.toLowerCase();
          valB = b.name.toLowerCase();
          return profileSortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "mode":
          valA = a.mode.toLowerCase();
          valB = b.mode.toLowerCase();
          return profileSortOrder === "asc"
            ? valA.localeCompare(valB)
            : valB.localeCompare(valA);
        case "requests_count":
          valA = a.requests_count;
          valB = b.requests_count;
          break;
        case "first_candidate_success_count":
          valA = a.first_candidate_success_count;
          valB = b.first_candidate_success_count;
          break;
        case "fallback_success_count":
          valA = a.fallback_success_count;
          valB = b.fallback_success_count;
          break;
        case "failure_count":
          valA = a.failure_count;
          valB = b.failure_count;
          break;
        case "fallback_rate":
          valA = a.fallback_rate;
          valB = b.fallback_rate;
          break;
        case "total_tokens":
          valA = a.total_tokens;
          valB = b.total_tokens;
          break;
        case "latency":
          valA = a.p50_latency_ms ?? a.avg_latency_ms ?? 0;
          valB = b.p50_latency_ms ?? b.avg_latency_ms ?? 0;
          break;
        case "tokens_per_sec":
          valA = a.tokens_per_sec ?? 0;
          valB = b.tokens_per_sec ?? 0;
          break;
        default:
          valA = a.requests_count;
          valB = b.requests_count;
      }

      if (valA < valB) return profileSortOrder === "asc" ? -1 : 1;
      if (valA > valB) return profileSortOrder === "asc" ? 1 : -1;
      return 0;
    });
  }, [filteredProfiles, profileSortField, profileSortOrder]);

  const totalProfilePages = Math.max(1, Math.ceil(sortedProfiles.length / profilePageSize));
  const paginatedProfiles = useMemo(() => {
    if (profilePageSize >= sortedProfiles.length) return sortedProfiles;
    const start = (profilePage - 1) * profilePageSize;
    return sortedProfiles.slice(start, start + profilePageSize);
  }, [sortedProfiles, profilePage, profilePageSize]);

  const formatNum = (num: number) => {
    return new Intl.NumberFormat().format(num);
  };

  const renderComparisonBadge = (
    changePct: number | null | undefined,
    reverseGood: boolean = false
  ) => {
    if (changePct === null || changePct === undefined) return null;
    const isZero = changePct === 0;
    const isPositive = changePct > 0;
    const isGood = reverseGood ? !isPositive : isPositive;

    const colorClass = isZero
      ? "text-slate-400 bg-slate-800/80 border-slate-700/60"
      : isGood
      ? "text-emerald-300 bg-emerald-950/60 border-emerald-800/50"
      : "text-rose-300 bg-rose-950/60 border-rose-800/50";

    const Icon = isZero ? Minus : isPositive ? ArrowUpRight : ArrowDownRight;

    return (
      <span
        className={`inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.2 rounded border font-mono font-medium ${colorClass}`}
        title="Comparison with previous period"
      >
        <Icon size={11} />
        <span>{isPositive ? `+${changePct}%` : `${changePct}%`}</span>
      </span>
    );
  };

  const exportToCSV = () => {
    if (!data) return;
    const rows: string[][] = [];
    const filename = `analytics_${period}_${new Date().toISOString().slice(0, 10)}.csv`;

    if (activeSubTab === "models") {
      rows.push([
        "Model",
        "Provider",
        "Requests",
        "Success Rate (%)",
        "Input Tokens",
        "Output Tokens",
        "Cached Tokens",
        "Reasoning Tokens",
        "Total Tokens",
        "Avg Latency (ms)",
        "p50 Latency (ms)",
        "p90 Latency (ms)",
        "Tokens/sec",
        "Estimated Cost ($)",
      ]);
      data.by_models.forEach((m) => {
        rows.push([
          m.model_name,
          m.provider_name,
          m.requests_count.toString(),
          m.success_rate.toString(),
          m.input_tokens.toString(),
          m.output_tokens.toString(),
          (m.cached_tokens || 0).toString(),
          (m.reasoning_tokens || 0).toString(),
          m.total_tokens.toString(),
          m.avg_latency_ms.toString(),
          (m.p50_latency_ms || 0).toString(),
          (m.p90_latency_ms || 0).toString(),
          (m.tokens_per_sec || 0).toString(),
          m.estimated_cost_usd.toString(),
        ]);
      });
    } else if (activeSubTab === "providers") {
      rows.push([
        "Provider",
        "Slug",
        "Requests",
        "Success Rate (%)",
        "Total Tokens",
        "Avg Latency (ms)",
        "p50 (ms)",
        "p90 (ms)",
        "Tokens/sec",
        "Estimated Cost ($)",
      ]);
      data.by_providers.forEach((p) => {
        rows.push([
          p.name,
          p.slug,
          p.requests_count.toString(),
          p.success_rate.toString(),
          p.total_tokens.toString(),
          p.avg_latency_ms.toString(),
          (p.p50_latency_ms || 0).toString(),
          (p.p90_latency_ms || 0).toString(),
          (p.tokens_per_sec || 0).toString(),
          p.estimated_cost_usd.toString(),
        ]);
      });
    } else if (activeSubTab === "router_keys") {
      rows.push([
        "Key Name",
        "Prefix",
        "Requests",
        "Success Rate (%)",
        "Total Tokens",
        "Avg Latency (ms)",
        "p50 (ms)",
        "p90 (ms)",
        "Tokens/sec",
        "Estimated Cost ($)",
      ]);
      data.by_router_keys.forEach((k) => {
        rows.push([
          k.name,
          k.prefix,
          k.requests_count.toString(),
          k.success_rate.toString(),
          k.total_tokens.toString(),
          k.avg_latency_ms.toString(),
          (k.p50_latency_ms || 0).toString(),
          (k.p90_latency_ms || 0).toString(),
          (k.tokens_per_sec || 0).toString(),
          k.estimated_cost_usd.toString(),
        ]);
      });
    } else if (activeSubTab === "credentials") {
      rows.push([
        "Credential",
        "Provider",
        "Status",
        "Requests",
        "Fallback Rescued",
        "Failures",
        "Success Rate (%)",
        "Total Tokens",
        "Avg Latency (ms)",
        "p50 (ms)",
        "p90 (ms)",
        "Tokens/sec",
      ]);
      data.by_credentials.forEach((c) => {
        rows.push([
          c.name,
          c.provider_name,
          c.status,
          c.requests_count.toString(),
          c.fallback_success_count.toString(),
          c.failure_count.toString(),
          c.success_rate.toString(),
          c.total_tokens.toString(),
          c.avg_latency_ms.toString(),
          (c.p50_latency_ms || 0).toString(),
          (c.p90_latency_ms || 0).toString(),
          (c.tokens_per_sec || 0).toString(),
        ]);
      });
    } else if (activeSubTab === "profiles") {
      rows.push([
        "Profile",
        "Mode",
        "Requests",
        "Primary Success",
        "Fallback Rescued",
        "Chain Failures",
        "Fallback Rate (%)",
        "Total Tokens",
        "Avg Latency (ms)",
        "p50 (ms)",
        "p90 (ms)",
        "Tokens/sec",
      ]);
      data.by_profiles.forEach((p) => {
        rows.push([
          p.name,
          p.mode,
          p.requests_count.toString(),
          p.first_candidate_success_count.toString(),
          p.fallback_success_count.toString(),
          p.failure_count.toString(),
          p.fallback_rate.toString(),
          p.total_tokens.toString(),
          p.avg_latency_ms.toString(),
          (p.p50_latency_ms || 0).toString(),
          (p.p90_latency_ms || 0).toString(),
          (p.tokens_per_sec || 0).toString(),
        ]);
      });
    }

    const csvContent =
      "data:text/csv;charset=utf-8,\uFEFF" +
      rows.map((e) => e.map((val) => `"${val.replace(/"/g, '""')}"`).join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setShowExportMenu(false);
  };

  const exportToJSON = () => {
    if (!data) return;
    const jsonStr = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `analytics_${period}_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setShowExportMenu(false);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header & Period Selector */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <BarChart3 className="text-indigo-400" size={22} />
            {t.analytics.title}
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            {t.analytics.subtitle}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Period Selector Tabs */}
          <div className="flex flex-wrap items-center bg-slate-950/80 border border-white/[0.08] rounded-xl p-1 text-xs shadow-xs">
            {[
              { id: "today", label: "Today" },
              { id: "yesterday", label: "Yesterday" },
              { id: "24h", label: "24h" },
              { id: "7d", label: "7d" },
              { id: "30d", label: "30d" },
              { id: "this_month", label: "This Month" },
              { id: "all", label: "All Time" },
            ].map((p) => (
              <button
                key={p.id}
                onClick={() => handlePeriodChange(p.id as any)}
                className={`btn-press px-3 py-1 rounded-lg font-medium transition-all cursor-pointer ${
                  period === p.id && !showCustomRange
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {p.label}
              </button>
            ))}
            <button
              onClick={() => setShowCustomRange(!showCustomRange)}
              className={`btn-press px-3 py-1 rounded-lg font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                period === "custom" || showCustomRange
                  ? "bg-indigo-600 text-white shadow-xs"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Calendar size={12} />
              <span>Calendar</span>
            </button>
          </div>

          {/* Export Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(!showExportMenu)}
              className="btn-press flex items-center gap-1.5 px-3 py-2 bg-slate-900/80 hover:bg-slate-800 border border-white/[0.08] text-slate-300 rounded-xl text-xs transition-colors cursor-pointer"
              title="Export data"
            >
              <Download size={13} className="text-indigo-400" />
              <span>Export</span>
              <ChevronDown size={12} className="text-slate-500" />
            </button>

            {showExportMenu && (
              <div className="absolute right-0 mt-1.5 w-44 glass-panel border border-white/[0.1] rounded-2xl shadow-2xl z-30 p-1.5 space-y-1">
                <button
                  onClick={exportToCSV}
                  className="btn-press w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors text-left cursor-pointer"
                >
                  <FileSpreadsheet size={14} className="text-emerald-400" />
                  <span>Export CSV</span>
                </button>
                <button
                  onClick={exportToJSON}
                  className="btn-press w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-white/[0.06] transition-colors text-left cursor-pointer"
                >
                  <FileJson size={14} className="text-amber-400" />
                  <span>Export JSON</span>
                </button>
              </div>
            )}
          </div>

          {/* Refresh Button */}
          <button
            onClick={() => loadStats(period, granularity, startDate, endDate, drillFilter)}
            disabled={loading}
            className="btn-press p-2 bg-slate-900/80 hover:bg-slate-800 border border-white/[0.08] text-slate-300 rounded-xl transition-colors disabled:opacity-50 cursor-pointer"
            title="Refresh data"
          >
            <RefreshCw size={15} className={loading ? "animate-spin text-indigo-400" : ""} />
          </button>
        </div>
      </div>

      {/* Custom Date Range Picker Accordion */}
      {showCustomRange && (
        <div className="bg-slate-900/90 border border-indigo-900/50 rounded-xl p-3 flex flex-wrap items-center gap-3 text-xs shadow-md">
          <div className="flex items-center gap-1.5 text-slate-300">
            <Calendar size={14} className="text-indigo-400" />
            <span className="font-semibold">Date Range:</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">From:</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">To:</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button
            onClick={handleApplyCustomRange}
            disabled={!startDate || !endDate}
            className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
          >
            {t.common.filter || "Apply"}
          </button>
          <button
            onClick={() => setShowCustomRange(false)}
            className="px-2.5 py-1 text-slate-400 hover:text-slate-200"
          >
            {t.common.close}
          </button>
        </div>
      )}

      {/* Active Drill-Down Filter Banner */}
      {drillFilter && (
        <div className="flex items-center justify-between bg-indigo-950/40 border border-indigo-800/60 rounded-xl px-4 py-2.5 text-xs text-indigo-200 shadow-sm">
          <div className="flex items-center gap-2 flex-wrap">
            <Filter size={14} className="text-indigo-400 shrink-0" />
            <span className="text-slate-400">Active Entity Filter:</span>
            <span className="font-semibold text-white bg-indigo-900/80 px-2.5 py-0.5 rounded border border-indigo-700/60 font-mono">
              {drillFilter.label}
            </span>
            <span className="text-[11px] text-indigo-300/80">
              (All charts, status codes and SLA funnel recalculated for this entity only)
            </span>
          </div>
          <button
            onClick={handleClearDrillFilter}
            className="flex items-center gap-1 text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-700/80 px-2.5 py-1 rounded-lg transition-colors border border-slate-700 text-xs shrink-0"
          >
            <X size={13} />
            <span>Reset</span>
          </button>
        </div>
      )}

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {/* Total Requests */}
        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 space-y-2 hover:border-white/[0.12] transition-all duration-200">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="font-medium">Total Requests</span>
            <div className="flex items-center gap-1.5">
              {renderComparisonBadge(comparison?.requests_change_pct)}
              <div className="w-6 h-6 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <TrendingUp size={13} />
              </div>
            </div>
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100 tracking-tight">
            {summary ? formatNum(summary.total_requests) : "..."}
          </div>
          <div className="text-[11px] text-slate-400 flex items-center justify-between pt-0.5">
            <span className="text-emerald-400 font-medium font-mono">
              ✓ {summary?.successful_requests || 0}
            </span>
            <span className="text-rose-400 font-medium font-mono">
              ✗ {summary?.failed_requests || 0}
            </span>
          </div>
        </div>

        {/* Success Rate */}
        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 space-y-2 hover:border-white/[0.12] transition-all duration-200">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="font-medium">Success Rate</span>
            <div className="flex items-center gap-1.5">
              {renderComparisonBadge(comparison?.success_rate_change_pct)}
              <div className="w-6 h-6 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                <CheckCircle2 size={13} />
              </div>
            </div>
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-300 tracking-tight">
            {summary ? `${summary.success_rate}%` : "..."}
          </div>
          <div className="w-full bg-slate-800/80 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-emerald-500 h-full rounded-full transition-all duration-500"
              style={{ width: `${summary?.success_rate || 0}%` }}
            />
          </div>
          <div className="text-[10px] text-slate-400 font-mono truncate">
            {summary?.successful_requests || 0} of {summary?.total_requests || 0}
          </div>
        </div>

        {/* Total Tokens & Prompt Caching */}
        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 space-y-2 hover:border-white/[0.12] transition-all duration-200">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="font-medium">Tokens & Cache</span>
            <div className="flex items-center gap-1.5">
              {renderComparisonBadge(comparison?.tokens_change_pct)}
              <div className="w-6 h-6 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                <Zap size={13} />
              </div>
            </div>
          </div>
          <div className="text-2xl font-bold font-mono text-amber-300 tracking-tight">
            {summary ? formatNum(summary.total_tokens) : "..."}
          </div>
          <div className="text-[10px] text-slate-400 truncate font-mono">
            {summary ? `In: ${formatNum(summary.total_prompt_tokens)} • Out: ${formatNum(summary.total_completion_tokens)}` : "..."}
          </div>
          <div className="text-[10px] text-slate-400 truncate flex items-center justify-between font-mono">
            {summary && summary.total_cached_tokens > 0 ? (
              <>
                <span className="text-emerald-400 font-medium">Cache: {formatNum(summary.total_cached_tokens)}</span>
                {summary.cached_tokens_cost_saved_usd ? (
                  <span className="text-emerald-300">~${summary.cached_tokens_cost_saved_usd.toFixed(4)} saved</span>
                ) : null}
              </>
            ) : summary && summary.total_reasoning_tokens > 0 ? (
              <span className="text-purple-300">CoT: {formatNum(summary.total_reasoning_tokens)}</span>
            ) : (
              <span className="text-slate-500">Cache: 0 tokens</span>
            )}
          </div>
        </div>

        {/* Latency & Speed Percentiles */}
        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 space-y-2 hover:border-white/[0.12] transition-all duration-200">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="font-medium">Latency</span>
            <div className="flex items-center gap-1.5">
              {renderComparisonBadge(comparison?.latency_change_pct, true)}
              <div className="w-6 h-6 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
                <Clock size={13} />
              </div>
            </div>
          </div>
          <div className="text-2xl font-bold font-mono text-sky-300 tracking-tight">
            {summary ? `${summary.avg_latency_ms} ms` : "..."}
          </div>
          <div className="text-[10px] text-sky-300/90 font-mono truncate">
            p50: {summary?.p50_latency_ms || 0}ms • p90: {summary?.p90_latency_ms || 0}ms
          </div>
          <div className="text-[10px] text-slate-400 truncate">
            Speed: <span className="text-sky-200 font-semibold font-mono">{summary?.tokens_per_sec || 0}</span> tok/s
          </div>
        </div>

        {/* Estimated Cost & Projections */}
        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 space-y-2 hover:border-white/[0.12] transition-all duration-200">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="font-medium">Estimated Cost</span>
            <div className="flex items-center gap-1.5">
              {renderComparisonBadge(comparison?.cost_change_pct, true)}
              <div className="w-6 h-6 rounded-lg bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center text-yellow-400">
                <Coins size={13} />
              </div>
            </div>
          </div>
          <div className="text-2xl font-bold font-mono text-yellow-300 tracking-tight">
            {summary ? `$${summary.estimated_cost_usd.toFixed(4)}` : "..."}
          </div>
          <div className="text-[10px] text-slate-400 truncate font-mono">
            {summary && summary.total_requests > 0
              ? `$${(summary.estimated_cost_usd / summary.total_requests).toFixed(5)} / req`
              : "$0.00"}
          </div>
          <div className="text-[10px] text-slate-400 truncate font-mono">
            {summary && (summary.projected_daily_cost_usd || summary.projected_monthly_cost_usd) ? (
              <span>~${(summary.projected_daily_cost_usd || 0).toFixed(2)}/day • ~${(summary.projected_monthly_cost_usd || 0).toFixed(2)}/mo</span>
            ) : (
              <span>Projected: $0.00</span>
            )}
          </div>
        </div>

        {/* Fallbacks Recovered & SLA Boost */}
        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 space-y-2 hover:border-white/[0.12] transition-all duration-200">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span className="font-medium">Fallback</span>
            <div className="w-6 h-6 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
              <GitFork size={13} />
            </div>
          </div>
          <div className="text-2xl font-bold font-mono text-purple-300 tracking-tight">
            {summary ? formatNum(summary.fallback_requests) : "..."}
          </div>
          <div className="text-[10px] text-purple-400/90 truncate font-mono">
            {summary && summary.total_requests > 0
              ? `${Math.round((summary.fallback_requests / summary.total_requests) * 100)}% of all requests`
              : "0% requests"}
          </div>
          <div className="text-[10px] truncate">
            {funnel && funnel.reliability_gain_pct > 0 ? (
              <span className="text-emerald-400 font-semibold flex items-center gap-1 font-mono">
                <Sparkles size={11} className="shrink-0" />
                +{funnel.reliability_gain_pct}% SLA Boost
              </span>
            ) : (
              <span className="text-slate-500">Resilience SLA</span>
            )}
          </div>
        </div>
      </div>

      {/* Activity Timeline Chart */}
      {data && (
        <ActivityChart
          timeline={data.timeline || []}
          period={period}
          granularity={granularity || data.granularity || "hour"}
          onGranularityChange={handleGranularityChange}
          formatNum={formatNum}
        />
      )}

      {/* Analytics Widgets Grid: 1. Status Codes & Error Insights | 2. Fallback Reliability Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Widget 1: Status Codes & Error Insights */}
        <div className="glass-panel card-specular rounded-2xl border border-white/[0.07] p-5 space-y-4 shadow-md">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-400" />
              <h3 className="text-sm font-semibold text-slate-200">HTTP Status Codes & Errors</h3>
            </div>
            <span className="text-[11px] text-slate-400 font-mono">
              Total: {formatNum(summary?.total_requests || 0)}
            </span>
          </div>

          {/* Segmented Distribution Bar */}
          <div className="w-full h-3.5 bg-slate-950 rounded-full overflow-hidden flex border border-slate-800">
            {data?.status_codes && data.status_codes.length > 0 ? (
              data.status_codes.map((sc, idx) => {
                const color =
                  sc.code >= 200 && sc.code < 300
                    ? "bg-emerald-500"
                    : sc.code === 429
                    ? "bg-amber-500"
                    : sc.code >= 500
                    ? "bg-rose-500"
                    : sc.code >= 400
                    ? "bg-sky-500"
                    : "bg-slate-500";
                return (
                  <div
                    key={idx}
                    className={`${color} h-full transition-all hover:opacity-80`}
                    style={{ width: `${Math.max(sc.percentage, 0.5)}%` }}
                    title={`HTTP ${sc.code}: ${formatNum(sc.count)} (${sc.percentage}%)`}
                  />
                );
              })
            ) : (
              <div className="w-full h-full bg-slate-800" />
            )}
          </div>

          {/* Status Code Pills */}
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {data?.status_codes && data.status_codes.length > 0 ? (
              data.status_codes.map((sc, idx) => {
                const is2xx = sc.code >= 200 && sc.code < 300;
                const is429 = sc.code === 429;
                const is5xx = sc.code >= 500;
                const badgeStyle = is2xx
                  ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/60"
                  : is429
                  ? "bg-amber-950/60 text-amber-300 border-amber-800/60"
                  : is5xx
                  ? "bg-rose-950/60 text-rose-300 border-rose-800/60"
                  : "bg-slate-950/60 text-slate-300 border-slate-700/60";

                return (
                  <span
                    key={idx}
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono border ${badgeStyle}`}
                  >
                    <span className="font-bold">{sc.code}</span>
                    <span>{formatNum(sc.count)}</span>
                    <span className="opacity-70 text-[10px]">({sc.percentage}%)</span>
                  </span>
                );
              })
            ) : (
              <span className="text-xs text-slate-500">No status code data for this period</span>
            )}
          </div>

          {/* Top Errors Section */}
          <div className="pt-2 border-t border-slate-800/80">
            <div className="text-xs font-semibold text-slate-300 mb-2 flex items-center justify-between">
              <span>Top Failure Causes:</span>
              <span className="text-[10px] text-slate-500">Count</span>
            </div>
            {!data?.top_errors || data.top_errors.length === 0 ? (
              <div className="text-xs text-emerald-400/90 flex items-center gap-1.5 py-1.5">
                <CheckCircle2 size={14} className="shrink-0" />
                <span>All requests completed without errors</span>
              </div>
            ) : (
              <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                {data.top_errors.map((err, idx) => (
                  <div
                    key={idx}
                    className="flex items-start justify-between gap-2 p-2 bg-slate-950/60 border border-slate-800/60 rounded-lg text-xs hover:border-slate-700 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-rose-950/80 text-rose-300 border border-rose-800/60 font-semibold">
                          {err.error_category || "ERROR"}
                        </span>
                        <span className="text-slate-300 font-mono truncate text-[11px]" title={err.error_message}>
                          {err.error_message}
                        </span>
                      </div>
                      {err.last_seen && (
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          Last error: {new Date(err.last_seen).toLocaleTimeString()}
                        </div>
                      )}
                    </div>
                    <span className="font-mono font-bold text-rose-400 text-xs shrink-0 pt-0.5">
                      {formatNum(err.count)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Widget 2: Fallback Funnel & SLA Boost */}
        <div className="glass-panel card-specular rounded-2xl border border-white/[0.07] p-5 space-y-4 shadow-md">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <GitFork size={16} className="text-purple-400" />
              <h3 className="text-sm font-semibold text-slate-200">Fault-Tolerance Funnel (Fallback SLA)</h3>
            </div>
            {funnel && funnel.reliability_gain_pct > 0 && (
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-mono shadow-xs">
                <Sparkles size={12} />
                +{funnel.reliability_gain_pct}% SLA Boost
              </span>
            )}
          </div>

          {/* SLA Benchmark Scoreboard */}
          <div className="grid grid-cols-3 gap-2 bg-slate-950/60 border border-slate-800/80 rounded-lg p-2.5 text-center">
            <div>
              <div className="text-[10px] text-slate-400">Base SLA (Primary)</div>
              <div className="text-base font-bold font-mono text-slate-300">
                {funnel ? `${funnel.baseline_success_rate}%` : "-"}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-slate-400">Resilient SLA (with Fallback)</div>
              <div className="text-base font-bold font-mono text-emerald-400">
                {funnel ? `${funnel.final_success_rate}%` : "-"}
              </div>
            </div>
            <div>
              <div className="text-[10px] text-slate-400">Reliability Gain</div>
              <div className="text-base font-bold font-mono text-purple-300">
                {funnel && funnel.reliability_gain_pct > 0 ? `+${funnel.reliability_gain_pct}%` : "0%"}
              </div>
            </div>
          </div>

          {/* Funnel Steps */}
          <div className="space-y-2 pt-0.5 text-xs">
            {/* Step 1: Total Profile Requests */}
            <div className="p-2 bg-slate-950/40 rounded-lg border border-slate-800/60">
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-300 font-medium">1. Total Profile Requests</span>
                <span className="font-mono font-bold text-slate-200">{formatNum(funnel?.total_profile_requests || 0)}</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div className="bg-indigo-500 h-full rounded-full" style={{ width: "100%" }} />
              </div>
            </div>

            {/* Step 2: Primary Direct Success */}
            <div className="p-2 bg-slate-950/40 rounded-lg border border-slate-800/60">
              <div className="flex items-center justify-between mb-1">
                <span className="text-emerald-300 flex items-center gap-1.5">
                  <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
                  2. Primary Candidate Responded
                </span>
                <span className="font-mono font-bold text-emerald-400">
                  {formatNum(funnel?.primary_direct_success || 0)}
                  {funnel && funnel.total_profile_requests > 0 && (
                    <span className="text-[10px] text-slate-400 font-normal ml-1">
                      ({Math.round((funnel.primary_direct_success / funnel.total_profile_requests) * 100)}%)
                    </span>
                  )}
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-emerald-500 h-full rounded-full"
                  style={{
                    width: `${
                      funnel && funnel.total_profile_requests > 0
                        ? (funnel.primary_direct_success / funnel.total_profile_requests) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>

            {/* Step 3: Key Rotation Failover */}
            <div className="p-2 bg-slate-950/40 rounded-lg border border-slate-800/60">
              <div className="flex items-center justify-between mb-1">
                <span className="text-amber-300 flex items-center gap-1.5">
                  <KeyRound size={13} className="text-amber-400 shrink-0" />
                  3. Rescued by Key Rotation
                </span>
                <span className="font-mono font-bold text-amber-300">
                  +{formatNum(funnel?.primary_key_failover_success || 0)}
                  {funnel && funnel.total_profile_requests > 0 && (
                    <span className="text-[10px] text-slate-400 font-normal ml-1">
                      ({Math.round((funnel.primary_key_failover_success / funnel.total_profile_requests) * 100)}%)
                    </span>
                  )}
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-amber-500 h-full rounded-full"
                  style={{
                    width: `${
                      funnel && funnel.total_profile_requests > 0
                        ? (funnel.primary_key_failover_success / funnel.total_profile_requests) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>

            {/* Step 4: Fallback Model Rescue */}
            <div className="p-2 bg-slate-950/40 rounded-lg border border-slate-800/60">
              <div className="flex items-center justify-between mb-1">
                <span className="text-purple-300 flex items-center gap-1.5">
                  <GitFork size={13} className="text-purple-400 shrink-0" />
                  4. Rescued by Fallback Model
                </span>
                <span className="font-mono font-bold text-purple-300">
                  +{formatNum(funnel?.fallback_model_success || 0)}
                  {funnel && funnel.total_profile_requests > 0 && (
                    <span className="text-[10px] text-slate-400 font-normal ml-1">
                      ({Math.round((funnel.fallback_model_success / funnel.total_profile_requests) * 100)}%)
                    </span>
                  )}
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-purple-500 h-full rounded-full"
                  style={{
                    width: `${
                      funnel && funnel.total_profile_requests > 0
                        ? (funnel.fallback_model_success / funnel.total_profile_requests) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>

            {/* Step 5: Chain Failures */}
            <div className="p-2 bg-slate-950/40 rounded-lg border border-slate-800/60">
              <div className="flex items-center justify-between mb-1">
                <span className="text-rose-300 flex items-center gap-1.5">
                  <AlertTriangle size={13} className="text-rose-400 shrink-0" />
                  5. Chain Failures
                </span>
                <span className="font-mono font-bold text-rose-400">
                  {formatNum(funnel?.chain_failures || 0)}
                  {funnel && funnel.total_profile_requests > 0 && (
                    <span className="text-[10px] text-slate-400 font-normal ml-1">
                      ({Math.round((funnel.chain_failures / funnel.total_profile_requests) * 100)}%)
                    </span>
                  )}
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-rose-500 h-full rounded-full"
                  style={{
                    width: `${
                      funnel && funnel.total_profile_requests > 0
                        ? (funnel.chain_failures / funnel.total_profile_requests) * 100
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Breakdown Section with Sub-tabs */}
      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] overflow-hidden shadow-lg">
        {/* Sub-tabs Header & Filter Bar */}
        <div className="p-4 bg-slate-950/60 border-b border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-3 flex-wrap">
          {/* Navigation Pills */}
          <div className="flex flex-wrap gap-1.5 text-xs">
            {[
              { id: "models", label: "By Models", icon: <Boxes size={14} />, count: data?.by_models.length },
              { id: "providers", label: "By Providers", icon: <Cpu size={14} />, count: data?.by_providers.length },
              { id: "router_keys", label: "By API Keys", icon: <ShieldCheck size={14} />, count: data?.by_router_keys.length },
              { id: "credentials", label: "By Upstream Keys", icon: <KeyRound size={14} />, count: data?.by_credentials.length },
              { id: "profiles", label: "By Fallback Profiles", icon: <GitFork size={14} />, count: data?.by_profiles.length },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveSubTab(tab.id as any)}
                className={`btn-press flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl font-medium transition-all cursor-pointer ${
                  activeSubTab === tab.id
                    ? "bg-gradient-to-r from-indigo-500 to-indigo-600 text-white font-semibold shadow-md shadow-indigo-500/25 border border-white/10"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] border border-transparent"
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
                {typeof tab.count === "number" && (
                  <span className={`text-[10px] font-mono px-2 py-0.2 rounded-full ${
                    activeSubTab === tab.id ? "bg-white/20 text-white font-bold" : "bg-slate-800 text-slate-400"
                  }`}>
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Quick Search */}
          <div className="relative w-full sm:w-64">
            <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Filter by name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-slate-950/80 border border-white/[0.08] rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Tab Content: 1. By Models */}
        {activeSubTab === "models" && (
          <div>
            {/* Sorting Info Ribbon */}
            <div className="px-4 py-2.5 bg-slate-950/50 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex items-center flex-wrap gap-2">
                <span className="text-slate-400">Sort:</span>
                <button
                  onClick={() => setModelSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-indigo-950/70 border border-indigo-700/60 rounded-lg text-indigo-300 font-medium hover:bg-indigo-900/60 transition-colors shadow-xs"
                  title="Click to toggle sort direction (ascending / descending)"
                >
                  <span>{MODEL_SORT_LABELS[modelSortField]}</span>
                  {modelSortOrder === "desc" ? (
                    <ArrowDown size={12} className="text-indigo-400" />
                  ) : (
                    <ArrowUp size={12} className="text-indigo-400" />
                  )}
                  <span className="text-[10px] text-indigo-400/80 uppercase tracking-wider">
                    {modelSortOrder === "desc" ? "descending" : "ascending"}
                  </span>
                </button>
                <span className="text-slate-500 text-[11px] hidden md:inline">
                  • Click any table cell or column header to re-sort
                </span>
              </div>
              <div className="text-slate-400 text-xs flex items-center gap-2">
                <span>
                  Total models:{" "}
                  <span className="font-semibold text-slate-200 font-mono">
                    {sortedModels.length}
                  </span>
                </span>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] font-semibold border-b border-slate-800">
                  <tr>
                    {renderSortHeader("model_name", "Model", modelSortField, modelSortOrder, handleSortModel, "left", "px-4")}
                    {renderSortHeader("provider_name", "Provider", modelSortField, modelSortOrder, handleSortModel, "left", "px-3")}
                    {renderSortHeader("requests_count", "Requests", modelSortField, modelSortOrder, handleSortModel, "right", "px-3")}
                    {renderSortHeader("success_rate", "Success Rate", modelSortField, modelSortOrder, handleSortModel, "right", "px-3")}
                    {renderSortHeader("input_tokens", "Prompt", modelSortField, modelSortOrder, handleSortModel, "right", "px-3")}
                    {renderSortHeader("output_tokens", "Completion", modelSortField, modelSortOrder, handleSortModel, "right", "px-3")}
                    {renderSortHeader("cached_tokens", "Cached", modelSortField, modelSortOrder, handleSortModel, "right", "px-3")}
                    {renderSortHeader("reasoning_tokens", "Reasoning (CoT)", modelSortField, modelSortOrder, handleSortModel, "right", "px-3")}
                    {renderSortHeader("total_tokens", "Total Tokens", modelSortField, modelSortOrder, handleSortModel, "right", "px-3")}
                    {renderSortHeader("latency", "p50 / p90", modelSortField, modelSortOrder, handleSortModel, "right", "px-3")}
                    {renderSortHeader("tokens_per_sec", "Speed", modelSortField, modelSortOrder, handleSortModel, "right", "px-3")}
                    {renderSortHeader("estimated_cost_usd", "Cost", modelSortField, modelSortOrder, handleSortModel, "right", "px-4")}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {paginatedModels.length === 0 ? (
                    <tr>
                      <td colSpan={12} className="px-4 py-8 text-center text-slate-400 font-sans text-xs">
                        No model metrics for this period
                      </td>
                    </tr>
                  ) : (
                    paginatedModels.map((m, idx) => {
                      const getCellClass = (field: ModelSortField, extra: string = "") => {
                        const isActive = modelSortField === field;
                        return `px-3 py-2.5 cursor-pointer transition-colors select-none group/cell ${
                          isActive
                            ? "bg-indigo-950/30 font-semibold ring-1 ring-inset ring-indigo-500/20 text-indigo-200"
                            : "hover:bg-slate-800/60"
                        } ${extra}`;
                      };

                      const getCellTitle = (field: ModelSortField) => {
                        const isCur = modelSortField === field;
                        const nextDir = isCur && modelSortOrder === "desc" ? "ascending" : "descending";
                        return `Click to sort by "${MODEL_SORT_LABELS[field]}" (${nextDir})`;
                      };

                      return (
                        <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                          {/* 1. Model Name */}
                          <td
                            onClick={() => handleSortModel("model_name")}
                            className={getCellClass("model_name", "px-4 font-semibold text-slate-100")}
                            title={getCellTitle("model_name")}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-1.5 min-w-0">
                                <Boxes size={13} className="text-indigo-400 shrink-0" />
                                <span
                                  className="truncate max-w-[200px] group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors"
                                  title={m.model_name}
                                >
                                  {m.model_name}
                                </span>
                              </div>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleApplyDrillFilter("model", m.model_name, m.model_name);
                                }}
                                className="text-slate-500 hover:text-indigo-400 p-1 rounded hover:bg-slate-800 transition-all shrink-0"
                                title={`Filter all statistics by model ${m.model_name}`}
                              >
                                <Filter size={12} />
                              </button>
                            </div>
                          </td>

                          {/* 2. Provider Name */}
                          <td
                            onClick={() => handleSortModel("provider_name")}
                            className={getCellClass("provider_name", "font-sans")}
                            title={getCellTitle("provider_name")}
                          >
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700/60 group-hover/cell:border-indigo-500/60 transition-colors">
                              {m.provider_name}
                            </span>
                          </td>

                          {/* 3. Requests Count */}
                          <td
                            onClick={() => handleSortModel("requests_count")}
                            className={getCellClass("requests_count", "text-right font-bold text-slate-100")}
                            title={getCellTitle("requests_count")}
                          >
                            <span className="group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                              {formatNum(m.requests_count)}
                            </span>
                          </td>

                          {/* 4. Success Rate */}
                          <td
                            onClick={() => handleSortModel("success_rate")}
                            className={getCellClass("success_rate", "text-right")}
                            title={getCellTitle("success_rate")}
                          >
                            <span
                              className={`group-hover/cell:underline transition-colors ${
                                m.success_rate >= 90
                                  ? "text-emerald-400"
                                  : m.success_rate >= 70
                                  ? "text-amber-400"
                                  : "text-rose-400"
                              }`}
                            >
                              {m.success_rate}%
                            </span>
                          </td>

                          {/* 5. Input Tokens */}
                          <td
                            onClick={() => handleSortModel("input_tokens")}
                            className={getCellClass("input_tokens", "text-right text-slate-400")}
                            title={getCellTitle("input_tokens")}
                          >
                            <span className="group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                              {formatNum(m.input_tokens)}
                            </span>
                          </td>

                          {/* 6. Output Tokens */}
                          <td
                            onClick={() => handleSortModel("output_tokens")}
                            className={getCellClass("output_tokens", "text-right text-slate-400")}
                            title={getCellTitle("output_tokens")}
                          >
                            <span className="group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                              {formatNum(m.output_tokens)}
                            </span>
                          </td>

                          {/* 7. Cached Tokens */}
                          <td
                            onClick={() => handleSortModel("cached_tokens")}
                            className={getCellClass("cached_tokens", "text-right text-emerald-400")}
                            title={getCellTitle("cached_tokens")}
                          >
                            <span className="group-hover/cell:underline transition-colors">
                              {m.cached_tokens > 0 ? formatNum(m.cached_tokens) : "-"}
                            </span>
                          </td>

                          {/* 8. Reasoning Tokens */}
                          <td
                            onClick={() => handleSortModel("reasoning_tokens")}
                            className={getCellClass("reasoning_tokens", "text-right text-purple-300")}
                            title={getCellTitle("reasoning_tokens")}
                          >
                            <span className="group-hover/cell:underline transition-colors">
                              {m.reasoning_tokens > 0 ? formatNum(m.reasoning_tokens) : "-"}
                            </span>
                          </td>

                          {/* 9. Total Tokens */}
                          <td
                            onClick={() => handleSortModel("total_tokens")}
                            className={getCellClass("total_tokens", "text-right font-bold text-amber-300")}
                            title={getCellTitle("total_tokens")}
                          >
                            <span className="group-hover/cell:underline transition-colors">
                              {formatNum(m.total_tokens)}
                            </span>
                          </td>

                          {/* 10. Latency (p50 / p90) */}
                          <td
                            onClick={() => handleSortModel("latency")}
                            className={getCellClass("latency", "text-right text-sky-300 font-sans text-[11px]")}
                            title={getCellTitle("latency")}
                          >
                            <span className="group-hover/cell:underline transition-colors">
                              {m.p50_latency_ms || 0} / {m.p90_latency_ms || 0} ms
                            </span>
                          </td>

                          {/* 11. Tokens/sec */}
                          <td
                            onClick={() => handleSortModel("tokens_per_sec")}
                            className={getCellClass("tokens_per_sec", "text-right text-sky-200 font-sans text-[11px]")}
                            title={getCellTitle("tokens_per_sec")}
                          >
                            <span className="group-hover/cell:underline transition-colors">
                              {m.tokens_per_sec || 0} tok/s
                            </span>
                          </td>

                          {/* 12. Estimated Cost */}
                          <td
                            onClick={() => handleSortModel("estimated_cost_usd")}
                            className={getCellClass("estimated_cost_usd", "px-4 text-right text-yellow-300 font-semibold")}
                            title={getCellTitle("estimated_cost_usd")}
                          >
                            <span className="group-hover/cell:underline transition-colors">
                              ${m.estimated_cost_usd.toFixed(4)}
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls Bar */}
            <TablePagination
              currentPage={modelPage}
              pageSize={modelPageSize}
              totalItems={sortedModels.length}
              totalPages={totalModelPages}
              itemName="models"
              onPageChange={setModelPage}
              onPageSizeChange={setModelPageSize}
            />
          </div>
        )}

        {/* Tab Content: 2. By Providers */}
        {activeSubTab === "providers" && (
          <div>
            {/* Sorting Info Ribbon */}
            <TableSortRibbon
              currentSortLabel={PROVIDER_SORT_LABELS[providerSortField]}
              sortOrder={providerSortOrder}
              totalCount={sortedProviders.length}
              totalLabel="Total Providers"
              onToggleOrder={() => setProviderSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))}
            />

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] font-semibold border-b border-slate-800">
                  <tr>
                    {renderSortHeader("name", "Provider", providerSortField, providerSortOrder, handleSortProvider, "left", "px-4")}
                    {renderSortHeader("slug", "Slug", providerSortField, providerSortOrder, handleSortProvider, "left", "px-3")}
                    {renderSortHeader("requests_count", "Requests", providerSortField, providerSortOrder, handleSortProvider, "right", "px-3")}
                    {renderSortHeader("success_count", "Success", providerSortField, providerSortOrder, handleSortProvider, "right", "px-3")}
                    {renderSortHeader("failure_count", "Failures", providerSortField, providerSortOrder, handleSortProvider, "right", "px-3")}
                    {renderSortHeader("success_rate", "Success Rate", providerSortField, providerSortOrder, handleSortProvider, "right", "px-3")}
                    {renderSortHeader("total_tokens", "Total Tokens", providerSortField, providerSortOrder, handleSortProvider, "right", "px-3")}
                    {renderSortHeader("latency", "p50 / p90", providerSortField, providerSortOrder, handleSortProvider, "right", "px-3")}
                    {renderSortHeader("tokens_per_sec", "Speed", providerSortField, providerSortOrder, handleSortProvider, "right", "px-3")}
                    {renderSortHeader("estimated_cost_usd", "Cost", providerSortField, providerSortOrder, handleSortProvider, "right", "px-4")}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {paginatedProviders.length === 0 ? (
                    <tr>
                      <td colSpan={10} className="px-4 py-8 text-center text-slate-400 font-sans text-xs">
                        No provider metrics for this period
                      </td>
                    </tr>
                  ) : (
                    paginatedProviders.map((p, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                        {/* 1. Provider Name */}
                        <td
                          onClick={() => handleSortProvider("name")}
                          className={getSortCellClass("name", providerSortField, "px-4 font-semibold text-slate-100 font-sans")}
                          title={getSortCellTitle("name", PROVIDER_SORT_LABELS.name, providerSortField, providerSortOrder)}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <Cpu size={14} className="text-purple-400 shrink-0" />
                              <span className="truncate group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                                {p.name}
                              </span>
                            </div>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleApplyDrillFilter("provider", p.slug, p.name);
                              }}
                              className="text-slate-500 hover:text-indigo-400 p-1 rounded hover:bg-slate-800 transition-all shrink-0"
                              title={`Filter all statistics by provider ${p.name}`}
                            >
                              <Filter size={12} />
                            </button>
                          </div>
                        </td>

                        {/* 2. Slug */}
                        <td
                          onClick={() => handleSortProvider("slug")}
                          className={getSortCellClass("slug", providerSortField, "text-slate-400 text-[11px] font-mono")}
                          title={getSortCellTitle("slug", PROVIDER_SORT_LABELS.slug, providerSortField, providerSortOrder)}
                        >
                          <span className="group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                            {p.slug}
                          </span>
                        </td>

                        {/* 3. Requests Count */}
                        <td
                          onClick={() => handleSortProvider("requests_count")}
                          className={getSortCellClass("requests_count", providerSortField, "text-right font-bold text-slate-100")}
                          title={getSortCellTitle("requests_count", PROVIDER_SORT_LABELS.requests_count, providerSortField, providerSortOrder)}
                        >
                          <span className="group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                            {formatNum(p.requests_count)}
                          </span>
                        </td>

                        {/* 4. Success Count */}
                        <td
                          onClick={() => handleSortProvider("success_count")}
                          className={getSortCellClass("success_count", providerSortField, "text-right text-emerald-400")}
                          title={getSortCellTitle("success_count", PROVIDER_SORT_LABELS.success_count, providerSortField, providerSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {formatNum(p.success_count)}
                          </span>
                        </td>

                        {/* 5. Failure Count */}
                        <td
                          onClick={() => handleSortProvider("failure_count")}
                          className={getSortCellClass("failure_count", providerSortField, "text-right text-rose-400")}
                          title={getSortCellTitle("failure_count", PROVIDER_SORT_LABELS.failure_count, providerSortField, providerSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {formatNum(p.failure_count)}
                          </span>
                        </td>

                        {/* 6. Success Rate */}
                        <td
                          onClick={() => handleSortProvider("success_rate")}
                          className={getSortCellClass("success_rate", providerSortField, "text-right")}
                          title={getSortCellTitle("success_rate", PROVIDER_SORT_LABELS.success_rate, providerSortField, providerSortOrder)}
                        >
                          <span
                            className={`group-hover/cell:underline transition-colors ${
                              p.success_rate >= 90
                                ? "text-emerald-400"
                                : p.success_rate >= 70
                                ? "text-amber-400"
                                : "text-rose-400"
                            }`}
                          >
                            {p.success_rate}%
                          </span>
                        </td>

                        {/* 7. Total Tokens */}
                        <td
                          onClick={() => handleSortProvider("total_tokens")}
                          className={getSortCellClass("total_tokens", providerSortField, "text-right font-bold text-amber-300")}
                          title={getSortCellTitle("total_tokens", PROVIDER_SORT_LABELS.total_tokens, providerSortField, providerSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {formatNum(p.total_tokens)}
                          </span>
                        </td>

                        {/* 8. Latency */}
                        <td
                          onClick={() => handleSortProvider("latency")}
                          className={getSortCellClass("latency", providerSortField, "text-right text-sky-300 font-sans text-[11px]")}
                          title={getSortCellTitle("latency", PROVIDER_SORT_LABELS.latency, providerSortField, providerSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {p.p50_latency_ms || 0} / {p.p90_latency_ms || 0} ms
                          </span>
                        </td>

                        {/* 9. Tokens/sec */}
                        <td
                          onClick={() => handleSortProvider("tokens_per_sec")}
                          className={getSortCellClass("tokens_per_sec", providerSortField, "text-right text-sky-200 font-sans text-[11px]")}
                          title={getSortCellTitle("tokens_per_sec", PROVIDER_SORT_LABELS.tokens_per_sec, providerSortField, providerSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {p.tokens_per_sec || 0} tok/s
                          </span>
                        </td>

                        {/* 10. Estimated Cost */}
                        <td
                          onClick={() => handleSortProvider("estimated_cost_usd")}
                          className={getSortCellClass("estimated_cost_usd", providerSortField, "px-4 text-right text-yellow-300 font-semibold")}
                          title={getSortCellTitle("estimated_cost_usd", PROVIDER_SORT_LABELS.estimated_cost_usd, providerSortField, providerSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            ${p.estimated_cost_usd.toFixed(4)}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls Bar */}
            <TablePagination
              currentPage={providerPage}
              pageSize={providerPageSize}
              totalItems={sortedProviders.length}
              totalPages={totalProviderPages}
              itemName="providers"
              onPageChange={setProviderPage}
              onPageSizeChange={setProviderPageSize}
            />
          </div>
        )}

        {/* Tab Content: 3. By Router API Keys */}
        {activeSubTab === "router_keys" && (
          <div>
            {/* Sorting Info Ribbon */}
            <TableSortRibbon
              currentSortLabel={KEY_SORT_LABELS[keySortField]}
              sortOrder={keySortOrder}
              totalCount={sortedKeys.length}
              totalLabel="Total Keys"
              onToggleOrder={() => setKeySortOrder((prev) => (prev === "desc" ? "asc" : "desc"))}
            />

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] font-semibold border-b border-slate-800">
                  <tr>
                    {renderSortHeader("name", "Key Name", keySortField, keySortOrder, handleSortKey, "left", "px-4")}
                    {renderSortHeader("prefix", "Prefix", keySortField, keySortOrder, handleSortKey, "left", "px-3")}
                    {renderSortHeader("requests_count", "Requests", keySortField, keySortOrder, handleSortKey, "right", "px-3")}
                    {renderSortHeader("success_count", "Success", keySortField, keySortOrder, handleSortKey, "right", "px-3")}
                    {renderSortHeader("failure_count", "Errors", keySortField, keySortOrder, handleSortKey, "right", "px-3")}
                    {renderSortHeader("success_rate", "Success Rate", keySortField, keySortOrder, handleSortKey, "right", "px-3")}
                    {renderSortHeader("total_tokens", "Total Tokens", keySortField, keySortOrder, handleSortKey, "right", "px-3")}
                    {renderSortHeader("latency", "p50 / p90", keySortField, keySortOrder, handleSortKey, "right", "px-3")}
                    {renderSortHeader("tokens_per_sec", "Speed", keySortField, keySortOrder, handleSortKey, "right", "px-3")}
                    {renderSortHeader("estimated_cost_usd", "Cost", keySortField, keySortOrder, handleSortKey, "right", "px-4")}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {paginatedKeys.length === 0 ? (
                    <tr>
                      <td colSpan={10} className="px-4 py-8 text-center text-slate-400 font-sans text-xs">
                        No API key metrics for this period
                      </td>
                    </tr>
                  ) : (
                    paginatedKeys.map((k, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                        {/* 1. Key Name */}
                        <td
                          onClick={() => handleSortKey("name")}
                          className={getSortCellClass("name", keySortField, "px-4 font-semibold text-slate-100 font-sans")}
                          title={getSortCellTitle("name", KEY_SORT_LABELS.name, keySortField, keySortOrder)}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <ShieldCheck size={14} className="text-emerald-400 shrink-0" />
                              <span className="truncate group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                                {k.name}
                              </span>
                            </div>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleApplyDrillFilter("router_key", k.name, k.name);
                              }}
                              className="text-slate-500 hover:text-indigo-400 p-1 rounded hover:bg-slate-800 transition-all shrink-0"
                              title={`Filter all statistics by key ${k.name}`}
                            >
                              <Filter size={12} />
                            </button>
                          </div>
                        </td>

                        {/* 2. Prefix */}
                        <td
                          onClick={() => handleSortKey("prefix")}
                          className={getSortCellClass("prefix", keySortField, "font-mono text-[11px] text-slate-400")}
                          title={getSortCellTitle("prefix", KEY_SORT_LABELS.prefix, keySortField, keySortOrder)}
                        >
                          <span className="bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800 group-hover/cell:border-indigo-500/60 transition-colors">
                            {k.prefix}••••
                          </span>
                        </td>

                        {/* 3. Requests Count */}
                        <td
                          onClick={() => handleSortKey("requests_count")}
                          className={getSortCellClass("requests_count", keySortField, "text-right font-bold text-slate-100")}
                          title={getSortCellTitle("requests_count", KEY_SORT_LABELS.requests_count, keySortField, keySortOrder)}
                        >
                          <span className="group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                            {formatNum(k.requests_count)}
                          </span>
                        </td>

                        {/* 4. Success Count */}
                        <td
                          onClick={() => handleSortKey("success_count")}
                          className={getSortCellClass("success_count", keySortField, "text-right text-emerald-400")}
                          title={getSortCellTitle("success_count", KEY_SORT_LABELS.success_count, keySortField, keySortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {formatNum(k.success_count)}
                          </span>
                        </td>

                        {/* 5. Failure Count */}
                        <td
                          onClick={() => handleSortKey("failure_count")}
                          className={getSortCellClass("failure_count", keySortField, "text-right text-rose-400")}
                          title={getSortCellTitle("failure_count", KEY_SORT_LABELS.failure_count, keySortField, keySortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {formatNum(k.failure_count)}
                          </span>
                        </td>

                        {/* 6. Success Rate */}
                        <td
                          onClick={() => handleSortKey("success_rate")}
                          className={getSortCellClass("success_rate", keySortField, "text-right")}
                          title={getSortCellTitle("success_rate", KEY_SORT_LABELS.success_rate, keySortField, keySortOrder)}
                        >
                          <span
                            className={`group-hover/cell:underline transition-colors ${
                              k.success_rate >= 90 ? "text-emerald-400" : "text-amber-400"
                            }`}
                          >
                            {k.success_rate}%
                          </span>
                        </td>

                        {/* 7. Total Tokens */}
                        <td
                          onClick={() => handleSortKey("total_tokens")}
                          className={getSortCellClass("total_tokens", keySortField, "text-right font-bold text-amber-300")}
                          title={getSortCellTitle("total_tokens", KEY_SORT_LABELS.total_tokens, keySortField, keySortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {formatNum(k.total_tokens)}
                          </span>
                        </td>

                        {/* 8. Latency */}
                        <td
                          onClick={() => handleSortKey("latency")}
                          className={getSortCellClass("latency", keySortField, "text-right text-sky-300 font-sans text-[11px]")}
                          title={getSortCellTitle("latency", KEY_SORT_LABELS.latency, keySortField, keySortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {k.p50_latency_ms || 0} / {k.p90_latency_ms || 0} ms
                          </span>
                        </td>

                        {/* 9. Tokens/sec */}
                        <td
                          onClick={() => handleSortKey("tokens_per_sec")}
                          className={getSortCellClass("tokens_per_sec", keySortField, "text-right text-sky-200 font-sans text-[11px]")}
                          title={getSortCellTitle("tokens_per_sec", KEY_SORT_LABELS.tokens_per_sec, keySortField, keySortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {k.tokens_per_sec || 0} tok/s
                          </span>
                        </td>

                        {/* 10. Estimated Cost */}
                        <td
                          onClick={() => handleSortKey("estimated_cost_usd")}
                          className={getSortCellClass("estimated_cost_usd", keySortField, "px-4 text-right text-yellow-300 font-semibold")}
                          title={getSortCellTitle("estimated_cost_usd", KEY_SORT_LABELS.estimated_cost_usd, keySortField, keySortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            ${k.estimated_cost_usd.toFixed(4)}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls Bar */}
            <TablePagination
              currentPage={keyPage}
              pageSize={keyPageSize}
              totalItems={sortedKeys.length}
              totalPages={totalKeyPages}
              itemName="keys"
              onPageChange={setKeyPage}
              onPageSizeChange={setKeyPageSize}
            />
          </div>
        )}

        {/* Tab Content: 4. By Upstream Credentials */}
        {activeSubTab === "credentials" && (
          <div>
            {/* Sorting Info Ribbon */}
            <TableSortRibbon
              currentSortLabel={CREDENTIAL_SORT_LABELS[credSortField]}
              sortOrder={credSortOrder}
              totalCount={sortedCreds.length}
              totalLabel="Total Upstream Keys"
              onToggleOrder={() => setCredSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))}
            />

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] font-semibold border-b border-slate-800">
                  <tr>
                    {renderSortHeader("name", "Key Name", credSortField, credSortOrder, handleSortCred, "left", "px-4")}
                    {renderSortHeader("provider_name", "Provider", credSortField, credSortOrder, handleSortCred, "left", "px-3")}
                    {renderSortHeader("status", "Status", credSortField, credSortOrder, handleSortCred, "left", "px-3")}
                    {renderSortHeader("requests_count", "Requests", credSortField, credSortOrder, handleSortCred, "right", "px-3")}
                    {renderSortHeader("fallback_success_count", "Fallback Rescued", credSortField, credSortOrder, handleSortCred, "right", "px-3")}
                    {renderSortHeader("failure_count", "Failures", credSortField, credSortOrder, handleSortCred, "right", "px-3")}
                    {renderSortHeader("success_rate", "Success Rate", credSortField, credSortOrder, handleSortCred, "right", "px-3")}
                    {renderSortHeader("total_tokens", "Total Tokens", credSortField, credSortOrder, handleSortCred, "right", "px-3")}
                    {renderSortHeader("latency", "p50 / p90", credSortField, credSortOrder, handleSortCred, "right", "px-3")}
                    {renderSortHeader("tokens_per_sec", "Speed", credSortField, credSortOrder, handleSortCred, "right", "px-4")}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {paginatedCreds.length === 0 ? (
                    <tr>
                      <td colSpan={10} className="px-4 py-8 text-center text-slate-400 font-sans text-xs">
                        No upstream key metrics for this period
                      </td>
                    </tr>
                  ) : (
                    paginatedCreds.map((c, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                        {/* 1. Credential Name */}
                        <td
                          onClick={() => handleSortCred("name")}
                          className={getSortCellClass("name", credSortField, "px-4 font-semibold text-slate-100 font-sans")}
                          title={getSortCellTitle("name", CREDENTIAL_SORT_LABELS.name, credSortField, credSortOrder)}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <KeyRound size={13} className="text-amber-400 shrink-0" />
                              <span className="truncate group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                                {c.name}
                              </span>
                            </div>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleApplyDrillFilter("credential", c.name, c.name);
                              }}
                              className="text-slate-500 hover:text-indigo-400 p-1 rounded hover:bg-slate-800 transition-all shrink-0"
                              title={`Filter all statistics by upstream key ${c.name}`}
                            >
                              <Filter size={12} />
                            </button>
                          </div>
                        </td>

                        {/* 2. Provider Name */}
                        <td
                          onClick={() => handleSortCred("provider_name")}
                          className={getSortCellClass("provider_name", credSortField, "font-sans")}
                          title={getSortCellTitle("provider_name", CREDENTIAL_SORT_LABELS.provider_name, credSortField, credSortOrder)}
                        >
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700/60 group-hover/cell:border-indigo-500/60 transition-colors">
                            {c.provider_name}
                          </span>
                        </td>

                        {/* 3. Status */}
                        <td
                          onClick={() => handleSortCred("status")}
                          className={getSortCellClass("status", credSortField, "font-sans")}
                          title={getSortCellTitle("status", CREDENTIAL_SORT_LABELS.status, credSortField, credSortOrder)}
                        >
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-semibold border ${
                              c.status === "HEALTHY"
                                ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/60"
                                : c.status === "DEGRADED"
                                ? "bg-amber-950/60 text-amber-300 border-amber-800/60"
                                : "bg-rose-950/60 text-rose-300 border-rose-800/60"
                            }`}
                          >
                            {c.status}
                          </span>
                        </td>

                        {/* 4. Requests Count */}
                        <td
                          onClick={() => handleSortCred("requests_count")}
                          className={getSortCellClass("requests_count", credSortField, "text-right font-bold text-slate-100")}
                          title={getSortCellTitle("requests_count", CREDENTIAL_SORT_LABELS.requests_count, credSortField, credSortOrder)}
                        >
                          <span className="group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                            {formatNum(c.requests_count)}
                          </span>
                        </td>

                        {/* 5. Fallback Success Count */}
                        <td
                          onClick={() => handleSortCred("fallback_success_count")}
                          className={getSortCellClass("fallback_success_count", credSortField, "text-right text-purple-300")}
                          title={getSortCellTitle("fallback_success_count", CREDENTIAL_SORT_LABELS.fallback_success_count, credSortField, credSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {c.fallback_success_count > 0 ? `+${c.fallback_success_count}` : "-"}
                          </span>
                        </td>

                        {/* 6. Failure Count */}
                        <td
                          onClick={() => handleSortCred("failure_count")}
                          className={getSortCellClass("failure_count", credSortField, "text-right text-rose-400")}
                          title={getSortCellTitle("failure_count", CREDENTIAL_SORT_LABELS.failure_count, credSortField, credSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {formatNum(c.failure_count)}
                          </span>
                        </td>

                        {/* 7. Success Rate */}
                        <td
                          onClick={() => handleSortCred("success_rate")}
                          className={getSortCellClass("success_rate", credSortField, "text-right")}
                          title={getSortCellTitle("success_rate", CREDENTIAL_SORT_LABELS.success_rate, credSortField, credSortOrder)}
                        >
                          <span
                            className={`group-hover/cell:underline transition-colors ${
                              c.success_rate >= 90 ? "text-emerald-400" : "text-amber-400"
                            }`}
                          >
                            {c.success_rate}%
                          </span>
                        </td>

                        {/* 8. Total Tokens */}
                        <td
                          onClick={() => handleSortCred("total_tokens")}
                          className={getSortCellClass("total_tokens", credSortField, "text-right font-bold text-amber-300")}
                          title={getSortCellTitle("total_tokens", CREDENTIAL_SORT_LABELS.total_tokens, credSortField, credSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {formatNum(c.total_tokens)}
                          </span>
                        </td>

                        {/* 9. Latency */}
                        <td
                          onClick={() => handleSortCred("latency")}
                          className={getSortCellClass("latency", credSortField, "text-right text-sky-300 font-sans text-[11px]")}
                          title={getSortCellTitle("latency", CREDENTIAL_SORT_LABELS.latency, credSortField, credSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {c.p50_latency_ms || 0} / {c.p90_latency_ms || 0} ms
                          </span>
                        </td>

                        {/* 10. Tokens/sec */}
                        <td
                          onClick={() => handleSortCred("tokens_per_sec")}
                          className={getSortCellClass("tokens_per_sec", credSortField, "px-4 text-right text-sky-200 font-sans text-[11px]")}
                          title={getSortCellTitle("tokens_per_sec", CREDENTIAL_SORT_LABELS.tokens_per_sec, credSortField, credSortOrder)}
                        >
                          <span className="group-hover/cell:underline transition-colors">
                            {c.tokens_per_sec || 0} tok/s
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls Bar */}
            <TablePagination
              currentPage={credPage}
              pageSize={credPageSize}
              totalItems={sortedCreds.length}
              totalPages={totalCredPages}
              itemName="upstream keys"
              onPageChange={setCredPage}
              onPageSizeChange={setCredPageSize}
            />
          </div>
        )}

        {/* Tab Content: 5. By Profiles (Fallback / Routing & Fusion) */}
        {activeSubTab === "profiles" && (
          <div>
            {/* Sorting Info Ribbon */}
            <TableSortRibbon
              currentSortLabel={PROFILE_SORT_LABELS[profileSortField]}
              sortOrder={profileSortOrder}
              totalCount={sortedProfiles.length}
              totalLabel="Total Profiles"
              onToggleOrder={() => setProfileSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))}
            />

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] font-semibold border-b border-slate-800">
                  <tr>
                    {renderSortHeader("name", "Routing Profile", profileSortField, profileSortOrder, handleSortProfile, "left", "px-4")}
                    {renderSortHeader("mode", "Mode", profileSortField, profileSortOrder, handleSortProfile, "left", "px-3")}
                    {renderSortHeader("requests_count", "Requests", profileSortField, profileSortOrder, handleSortProfile, "right", "px-3")}
                    {renderSortHeader("first_candidate_success_count", "Primary Candidate", profileSortField, profileSortOrder, handleSortProfile, "right", "px-3")}
                    {renderSortHeader("fallback_success_count", "Fallback Rescued", profileSortField, profileSortOrder, handleSortProfile, "right", "px-3")}
                    {renderSortHeader("failure_count", "Chain Failures", profileSortField, profileSortOrder, handleSortProfile, "right", "px-3")}
                    {renderSortHeader("fallback_rate", "Fallback Rate", profileSortField, profileSortOrder, handleSortProfile, "right", "px-3")}
                    {renderSortHeader("total_tokens", "Total Tokens", profileSortField, profileSortOrder, handleSortProfile, "right", "px-3")}
                    {renderSortHeader("latency", "p50 / p90", profileSortField, profileSortOrder, handleSortProfile, "right", "px-3")}
                    {renderSortHeader("tokens_per_sec", "Speed", profileSortField, profileSortOrder, handleSortProfile, "right", "px-4")}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {paginatedProfiles.length === 0 ? (
                    <tr>
                      <td colSpan={10} className="px-4 py-8 text-center text-slate-400 font-sans text-xs">
                        No Fallback / Fusion profiles recorded for this period
                      </td>
                    </tr>
                  ) : (
                    paginatedProfiles.map((p, idx) => {
                      const isExpanded = !!expandedProfileSlugs[p.slug];
                      const hasCandidates = p.candidates && p.candidates.length > 0;
                      return (
                        <React.Fragment key={idx}>
                          <tr className="hover:bg-slate-800/30 transition-colors">
                            {/* 1. Profile Name */}
                            <td
                              onClick={() => handleSortProfile("name")}
                              className={getSortCellClass("name", profileSortField, "px-4 font-semibold text-slate-100 font-sans")}
                              title={getSortCellTitle("name", PROFILE_SORT_LABELS.name, profileSortField, profileSortOrder)}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2 min-w-0">
                                  {hasCandidates ? (
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        toggleProfileExpand(p.slug);
                                      }}
                                      className="text-slate-400 hover:text-slate-200 p-0.5 rounded transition-colors"
                                      title="Show / hide candidates"
                                    >
                                      {isExpanded ? (
                                        <ChevronDown size={14} className="text-purple-400" />
                                      ) : (
                                        <ChevronRight size={14} />
                                      )}
                                    </button>
                                  ) : (
                                    <span className="w-4 inline-block" />
                                  )}
                                  <GitFork size={14} className="text-purple-400 shrink-0" />
                                  <div>
                                    <div className="flex items-center gap-1.5 flex-wrap">
                                      <span className="group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                                        {p.name}
                                      </span>
                                      {p.is_active ? (
                                        <span className="px-1.5 py-0.2 rounded text-[10px] bg-emerald-950/60 text-emerald-300 border border-emerald-800/60 font-sans">
                                          Active
                                        </span>
                                      ) : (
                                        <span className="px-1.5 py-0.2 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700/60 font-sans">
                                          Disabled
                                        </span>
                                      )}
                                      <span className="text-[10px] text-purple-300/80 bg-purple-950/40 px-1 py-0.2 rounded border border-purple-900/40 font-sans">
                                        {p.candidates_count || p.candidates?.length || 0} cand.
                                      </span>
                                    </div>
                                    <div className="font-mono text-[10px] text-purple-300/80">
                                      {p.mode === "PRIORITY" ? `route/${p.slug}` : `fusion/${p.slug}`}
                                    </div>
                                  </div>
                                </div>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleApplyDrillFilter("profile", p.slug, p.name);
                                  }}
                                  className="opacity-0 group-hover/opacity-100 text-slate-400 hover:text-indigo-400 p-1 rounded hover:bg-slate-800 transition-all shrink-0"
                                  title={`Filter all statistics by profile ${p.name}`}
                                >
                                  <Filter size={12} />
                                </button>
                              </div>
                            </td>

                            {/* 2. Mode */}
                            <td
                              onClick={() => handleSortProfile("mode")}
                              className={getSortCellClass("mode", profileSortField, "font-sans")}
                              title={getSortCellTitle("mode", PROFILE_SORT_LABELS.mode, profileSortField, profileSortOrder)}
                            >
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700/60 group-hover/cell:border-indigo-500/60 transition-colors">
                                {p.mode}
                              </span>
                            </td>

                            {/* 3. Requests Count */}
                            <td
                              onClick={() => handleSortProfile("requests_count")}
                              className={getSortCellClass("requests_count", profileSortField, "text-right font-bold text-slate-100")}
                              title={getSortCellTitle("requests_count", PROFILE_SORT_LABELS.requests_count, profileSortField, profileSortOrder)}
                            >
                              <span className="group-hover/cell:underline group-hover/cell:text-indigo-300 transition-colors">
                                {formatNum(p.requests_count)}
                              </span>
                            </td>

                            {/* 4. Primary candidate success */}
                            <td
                              onClick={() => handleSortProfile("first_candidate_success_count")}
                              className={getSortCellClass("first_candidate_success_count", profileSortField, "text-right text-emerald-400")}
                              title={getSortCellTitle("first_candidate_success_count", PROFILE_SORT_LABELS.first_candidate_success_count, profileSortField, profileSortOrder)}
                            >
                              <div className="group-hover/cell:underline">{formatNum(p.first_candidate_success_count)}</div>
                              {p.key_failover_count > 0 && (
                                <div
                                  className="text-[10px] text-amber-300 font-sans font-normal"
                                  title="Requests where primary candidate succeeded after key rotation"
                                >
                                  +{p.key_failover_count} key rot.
                                </div>
                              )}
                            </td>

                            {/* 5. Fallback success */}
                            <td
                              onClick={() => handleSortProfile("fallback_success_count")}
                              className={getSortCellClass("fallback_success_count", profileSortField, "text-right text-purple-300 font-bold")}
                              title={getSortCellTitle("fallback_success_count", PROFILE_SORT_LABELS.fallback_success_count, profileSortField, profileSortOrder)}
                            >
                              <span className="group-hover/cell:underline transition-colors">
                                {p.fallback_success_count > 0 ? `+${formatNum(p.fallback_success_count)}` : "0"}
                              </span>
                            </td>

                            {/* 6. Chain failures */}
                            <td
                              onClick={() => handleSortProfile("failure_count")}
                              className={getSortCellClass("failure_count", profileSortField, "text-right text-rose-400")}
                              title={getSortCellTitle("failure_count", PROFILE_SORT_LABELS.failure_count, profileSortField, profileSortOrder)}
                            >
                              <span className="group-hover/cell:underline transition-colors">
                                {formatNum(p.failure_count)}
                              </span>
                            </td>

                            {/* 7. Fallback rate */}
                            <td
                              onClick={() => handleSortProfile("fallback_rate")}
                              className={getSortCellClass("fallback_rate", profileSortField, "text-right")}
                              title={getSortCellTitle("fallback_rate", PROFILE_SORT_LABELS.fallback_rate, profileSortField, profileSortOrder)}
                            >
                              <span className="text-purple-400 font-semibold group-hover/cell:underline transition-colors">
                                {p.fallback_rate}%
                              </span>
                            </td>

                            {/* 8. Total Tokens */}
                            <td
                              onClick={() => handleSortProfile("total_tokens")}
                              className={getSortCellClass("total_tokens", profileSortField, "text-right font-bold text-amber-300")}
                              title={getSortCellTitle("total_tokens", PROFILE_SORT_LABELS.total_tokens, profileSortField, profileSortOrder)}
                            >
                              <span className="group-hover/cell:underline transition-colors">
                                {formatNum(p.total_tokens)}
                              </span>
                            </td>

                            {/* 9. Latency */}
                            <td
                              onClick={() => handleSortProfile("latency")}
                              className={getSortCellClass("latency", profileSortField, "text-right text-sky-300 font-sans text-[11px]")}
                              title={getSortCellTitle("latency", PROFILE_SORT_LABELS.latency, profileSortField, profileSortOrder)}
                            >
                              <span className="group-hover/cell:underline transition-colors">
                                {p.p50_latency_ms || 0} / {p.p90_latency_ms || 0} ms
                              </span>
                            </td>

                            {/* 10. Tokens/sec */}
                            <td
                              onClick={() => handleSortProfile("tokens_per_sec")}
                              className={getSortCellClass("tokens_per_sec", profileSortField, "px-4 text-right text-sky-200 font-sans text-[11px]")}
                              title={getSortCellTitle("tokens_per_sec", PROFILE_SORT_LABELS.tokens_per_sec, profileSortField, profileSortOrder)}
                            >
                              <span className="group-hover/cell:underline transition-colors">
                                {p.tokens_per_sec || 0} tok/s
                              </span>
                            </td>
                          </tr>

                          {/* Expandable Candidate Breakdown */}
                          {isExpanded && hasCandidates && (
                            <tr className="bg-slate-950/70 border-b border-slate-800/80 font-sans text-xs">
                              <td colSpan={10} className="px-6 py-3">
                                <div className="text-[11px] font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
                                  <GitFork size={12} className="text-purple-400" />
                                  Profile Candidate Chain:
                                </div>
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                                  {p.candidates.map((c, cIdx) => (
                                    <div
                                      key={cIdx}
                                      className="p-2.5 bg-slate-900/90 border border-slate-800/90 rounded-lg flex items-center justify-between gap-3 shadow-xs"
                                    >
                                      <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-1.5">
                                          <span
                                            className={`w-4 h-4 rounded-full text-[10px] font-bold font-mono flex items-center justify-center shrink-0 ${
                                              cIdx === 0
                                                ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                                                : "bg-purple-950 text-purple-300 border border-purple-800"
                                            }`}
                                          >
                                            #{cIdx + 1}
                                          </span>
                                          <span className="font-semibold text-slate-200 text-xs truncate" title={c.name}>
                                            {c.name}
                                          </span>
                                        </div>
                                        <div className="text-[10px] font-mono text-slate-400 pl-5.5 truncate" title={c.model_id || ""}>
                                          {cIdx === 0 ? "Primary Candidate" : "Fallback Candidate"}
                                        </div>
                                      </div>
                                      <div className="text-right shrink-0">
                                        <div className="font-bold text-slate-200 text-xs font-mono">
                                          {formatNum(c.requests_count)}{" "}
                                          <span className="text-[10px] font-normal text-slate-400 font-sans">req.</span>
                                        </div>
                                        <div className="text-[10px] text-emerald-400 font-mono">
                                          {formatNum(c.success_count)} success
                                        </div>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls Bar */}
            <TablePagination
              currentPage={profilePage}
              pageSize={profilePageSize}
              totalItems={sortedProfiles.length}
              totalPages={totalProfilePages}
              itemName="profiles"
              onPageChange={setProfilePage}
              onPageSizeChange={setProfilePageSize}
            />
          </div>
        )}
      </div>
    </div>
  );
};
