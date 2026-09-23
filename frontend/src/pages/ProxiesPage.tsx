import React, { useEffect, useState, useMemo, useRef } from "react";
import {
  Plus,
  Play,
  Trash2,
  Edit2,
  Network,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Check,
  RefreshCw,
  Search,
  ExternalLink,
  Wand2,
  Info,
  ChevronDown,
  ChevronUp,
  Globe,
  Layers,
  KeyRound,
  CheckSquare,
  X,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { Proxy, ProxyCreate, ProxyTestResult, ProxyParseResult, Credential } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { Modal } from "../components/Modal";
import { getCountryFlag } from "../utils/country";
import { useI18n } from "../i18n/context";

export const ProxiesPage: React.FC = () => {
  const { t } = useI18n();
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [loading, setLoading] = useState(true);
  const [serverIp, setServerIp] = useState<string>("");
  const [copiedIp, setCopiedIp] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProxy, setEditingProxy] = useState<Proxy | null>(null);

  // Form State
  const [quickString, setQuickString] = useState("");
  const [formName, setFormName] = useState("");
  const [formScheme, setFormScheme] = useState<"http" | "https" | "socks5">("socks5");
  const [formHost, setFormHost] = useState("");
  const [formPort, setFormPort] = useState(1080);
  const [formUsername, setFormUsername] = useState("");
  const [formPassword, setFormPassword] = useState("");

  // Testing State
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testingAll, setTestingAll] = useState(false);
  const [testResult, setTestResult] = useState<{ id?: number; result: ProxyTestResult } | null>(null);
  const [modalTesting, setModalTesting] = useState(false);
  const [modalTestResult, setModalTestResult] = useState<ProxyTestResult | null>(null);
  const [expandedErrorId, setExpandedErrorId] = useState<number | null>(null);

  // Assign to credentials modal
  const [isAssignKeysModalOpen, setIsAssignKeysModalOpen] = useState(false);
  const [selectedProxyForKeys, setSelectedProxyForKeys] = useState<Proxy | null>(null);
  const [allCredentials, setAllCredentials] = useState<Credential[]>([]);
  const [selectedCredIdsForProxy, setSelectedCredIdsForProxy] = useState<number[]>([]);
  const [isSavingAssignKeys, setIsSavingAssignKeys] = useState(false);
  const [keysSearchQuery, setKeysSearchQuery] = useState("");

  const openAssignKeysModal = async (proxy: Proxy) => {
    setSelectedProxyForKeys(proxy);
    setIsAssignKeysModalOpen(true);
    setKeysSearchQuery("");
    try {
      const creds = await apiRequest<Credential[]>("/api/admin/credentials");
      setAllCredentials(creds);
      setSelectedCredIdsForProxy(creds.filter((c) => c.proxy_id === proxy.id).map((c) => c.id));
    } catch (err: any) {
      alert(`Error loading credentials: ${err.message || String(err)}`);
    }
  };

  const handleSaveAssignKeys = async () => {
    if (!selectedProxyForKeys) return;
    setIsSavingAssignKeys(true);
    try {
      const currentAssigned = allCredentials
        .filter((c) => c.proxy_id === selectedProxyForKeys.id)
        .map((c) => c.id);
      const toAssign = selectedCredIdsForProxy.filter((id) => !currentAssigned.includes(id));
      const toUnassign = currentAssigned.filter((id) => !selectedCredIdsForProxy.includes(id));

      if (toAssign.length > 0) {
        await apiRequest("/api/admin/credentials/bulk-assign-proxy", {
          method: "POST",
          body: JSON.stringify({ credential_ids: toAssign, proxy_id: selectedProxyForKeys.id }),
        });
      }
      if (toUnassign.length > 0) {
        await apiRequest("/api/admin/credentials/bulk-assign-proxy", {
          method: "POST",
          body: JSON.stringify({ credential_ids: toUnassign, proxy_id: null }),
        });
      }

      setIsAssignKeysModalOpen(false);
      loadData();
    } catch (err: any) {
      alert(`Error saving proxy assignment: ${err.message || String(err)}`);
    } finally {
      setIsSavingAssignKeys(false);
    }
  };

  const toggleProxyCred = (credId: number) => {
    setSelectedCredIdsForProxy((prev) =>
      prev.includes(credId) ? prev.filter((id) => id !== credId) : [...prev, credId]
    );
  };

  const toggleAllCredsForProvider = (providerCreds: Credential[]) => {
    const ids = providerCreds.map((c) => c.id);
    const allSelected = ids.every((id) => selectedCredIdsForProxy.includes(id));
    if (allSelected) {
      setSelectedCredIdsForProxy((prev) => prev.filter((id) => !ids.includes(id)));
    } else {
      setSelectedCredIdsForProxy((prev) => Array.from(new Set([...prev, ...ids])));
    }
  };

  // Floating Provider Tooltip State (Fixed Position to avoid table overflow clipping)
  const [providerTooltip, setProviderTooltip] = useState<{
    providers: string[];
    proxyName: string;
    rect: DOMRect;
  } | null>(null);
  const tooltipTimeoutRef = useRef<any>(null);

  const showProviderTooltip = (providers: string[], proxyName: string, rect: DOMRect) => {
    if (tooltipTimeoutRef.current) clearTimeout(tooltipTimeoutRef.current);
    setProviderTooltip({ providers, proxyName, rect });
  };

  const hideProviderTooltip = () => {
    tooltipTimeoutRef.current = setTimeout(() => {
      setProviderTooltip(null);
    }, 120);
  };

  const keepProviderTooltip = () => {
    if (tooltipTimeoutRef.current) clearTimeout(tooltipTimeoutRef.current);
  };

  useEffect(() => {
    const handleDismiss = () => setProviderTooltip(null);
    window.addEventListener("scroll", handleDismiss, true);
    window.addEventListener("resize", handleDismiss);
    return () => {
      window.removeEventListener("scroll", handleDismiss, true);
      window.removeEventListener("resize", handleDismiss);
    };
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [proxiesData, ipData] = await Promise.all([
        apiRequest<Proxy[]>("/api/admin/proxies"),
        apiRequest<{ server_ip: string }>("/api/admin/proxies/server-ip").catch(() => ({ server_ip: "" })),
      ]);
      setProxies(proxiesData);
      if (ipData?.server_ip) {
        setServerIp(ipData.server_ip);
      }
    } catch (err) {
      console.error("Failed to load proxies data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCopyIp = () => {
    if (!serverIp) return;
    navigator.clipboard.writeText(serverIp);
    setCopiedIp(true);
    setTimeout(() => setCopiedIp(false), 2000);
  };

  const handleQuickParse = async (rawInput?: string) => {
    const textToParse = (rawInput !== undefined ? rawInput : quickString).trim();
    if (!textToParse) return;

    try {
      const parsed = await apiRequest<ProxyParseResult>("/api/admin/proxies/parse", {
        method: "POST",
        body: JSON.stringify({ raw: textToParse }),
      });
      setFormScheme(parsed.scheme as any);
      setFormHost(parsed.host);
      setFormPort(parsed.port);
      if (parsed.username !== undefined && parsed.username !== null) {
        setFormUsername(parsed.username);
      }
      if (parsed.password !== undefined && parsed.password !== null) {
        setFormPassword(parsed.password);
      }
      if (!formName && parsed.suggested_name) {
        setFormName(parsed.suggested_name);
      }
    } catch (err: any) {
      console.warn("Parse error:", err);
    }
  };

  const openCreateModal = () => {
    setEditingProxy(null);
    setQuickString("");
    setFormName("");
    setFormScheme("socks5");
    setFormHost("");
    setFormPort(1080);
    setFormUsername("");
    setFormPassword("");
    setModalTestResult(null);
    setIsModalOpen(true);
  };

  const openEditModal = (p: Proxy) => {
    setEditingProxy(p);
    setQuickString("");
    setFormName(p.name);
    setFormScheme(p.scheme === "socks5h" ? "socks5" : (p.scheme as any));
    setFormHost(p.host);
    setFormPort(p.port);
    setFormUsername("");
    setFormPassword("");
    setModalTestResult(null);
    setIsModalOpen(true);
  };

  const handleModalTest = async () => {
    if (!formHost) return;
    setModalTesting(true);
    setModalTestResult(null);
    try {
      const payload: ProxyCreate = {
        name: formName || "Test",
        scheme: formScheme,
        host: formHost,
        port: formPort,
        username: formUsername || undefined,
        password: formPassword || undefined,
      };
      const res = await apiRequest<ProxyTestResult>("/api/admin/proxies/test-raw", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setModalTestResult(res);
    } catch (err: any) {
      setModalTestResult({
        success: false,
        latency_ms: 0,
        message: err.message || "Connection error",
        details: err.detail || String(err),
      });
    } finally {
      setModalTesting(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: ProxyCreate = {
      name: formName.trim(),
      scheme: formScheme,
      host: formHost.trim(),
      port: formPort,
      username: formUsername ? formUsername.trim() : undefined,
      password: formPassword ? formPassword.trim() : undefined,
    };

    try {
      if (editingProxy) {
        await apiRequest(`/api/admin/proxies/${editingProxy.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiRequest("/api/admin/proxies", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to save proxy");
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete proxy "${name}"?`)) return;
    try {
      await apiRequest(`/api/admin/proxies/${id}`, { method: "DELETE" });
      setProxies((prev) => prev.filter((p) => p.id !== id));
      if (testResult?.id === id) setTestResult(null);
    } catch (err: any) {
      alert(err.message || "Failed to delete proxy");
    }
  };

  const handleTest = async (id: number) => {
    setTestingId(id);
    try {
      const res = await apiRequest<ProxyTestResult>(`/api/admin/proxies/${id}/test`, {
        method: "POST",
      });
      setTestResult({ id, result: res });
      loadData();
    } catch (err: any) {
      setTestResult({
        id,
        result: {
          success: false,
          latency_ms: 0,
          message: err.message || "Test error",
          details: err.detail || String(err),
        },
      });
    } finally {
      setTestingId(null);
    }
  };

  const handleTestAll = async () => {
    if (proxies.length === 0) return;
    setTestingAll(true);
    try {
      await apiRequest("/api/admin/proxies/test-all", { method: "POST" });
      await loadData();
    } catch (err: any) {
      console.error("Test all failed:", err);
    } finally {
      setTestingAll(false);
    }
  };

  const filteredProxies = useMemo(() => {
    if (!searchQuery.trim()) return proxies;
    const q = searchQuery.toLowerCase();
    return proxies.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.host.toLowerCase().includes(q) ||
        p.scheme.toLowerCase().includes(q) ||
        (p.country && p.country.toLowerCase().includes(q)) ||
        (p.country_code && p.country_code.toLowerCase().includes(q)) ||
        (p.assigned_providers && p.assigned_providers.some((prov) => prov.toLowerCase().includes(q)))
    );
  }, [proxies, searchQuery]);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <Network className="text-indigo-400" size={22} />
            {t.proxies.title}
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            {t.proxies.subtitle}
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleTestAll}
            disabled={testingAll || proxies.length === 0}
            className="btn-press flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-slate-300 rounded-xl text-xs font-medium transition-colors disabled:opacity-50 cursor-pointer"
            title={t.proxies.testAll}
          >
            <RefreshCw size={14} className={testingAll ? "animate-spin text-indigo-400" : ""} />
            <span>{t.proxies.testAll}</span>
          </button>
          <button
            onClick={openCreateModal}
            className="btn-press flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/25 transition-all cursor-pointer"
          >
            <Plus size={15} />
            {t.proxies.addProxy}
          </button>
        </div>
      </div>

      {/* Server Outbound IP Banner (Critical for Whitelist / Auth) */}
      <div className="glass-card card-specular bg-gradient-to-r from-indigo-950/30 via-slate-900/50 to-purple-950/25 border border-indigo-500/20 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-bold text-slate-200">
              Router Outbound Server IP:
            </span>
            <span className="font-mono text-xs font-bold bg-slate-950/80 px-2 py-0.5 rounded-lg border border-white/10 text-indigo-300">
              {serverIp || "Detecting..."}
            </span>
            {serverIp && (
              <button
                onClick={handleCopyIp}
                className="btn-press flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.09] text-slate-300 transition-colors border border-white/10 cursor-pointer"
                title="Copy Server IP"
              >
                {copiedIp ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                <span>{copiedIp ? t.common.copied : t.common.copy}</span>
              </button>
            )}
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            💡 <strong>Important for proxy access:</strong> Many proxy services (Proxy-Seller, Webshare, ProxyLine, etc.) require IP whitelisting or return error <code className="text-amber-300 font-mono">407</code> / <code className="text-amber-300 font-mono">SOCKS5 Auth failed</code> if the router server IP is not added to the proxy provider's whitelist.
          </p>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative w-full sm:w-72">
          <Search size={14} className="absolute left-3 top-3 text-slate-400" />
          <input
            type="text"
            placeholder={t.common.search}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3.5 py-2 bg-slate-900/80 border border-white/10 rounded-xl text-xs text-slate-200 placeholder-slate-400 focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none transition-all"
          />
        </div>
        <div className="text-xs text-slate-400 font-mono">
          {t.common.total}: <span className="font-semibold text-slate-200">{proxies.length}</span>
        </div>
      </div>

      {/* Proxies Table */}
      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-white/[0.02] text-slate-400 font-semibold border-b border-white/[0.06] text-[10px] uppercase tracking-wider font-mono">
              <tr>
                <th className="py-3 px-4">{t.common.name}</th>
                <th className="py-3 px-4">{t.proxies.country}</th>
                <th className="py-3 px-4">Protocol</th>
                <th className="py-3 px-4">{t.proxies.host}:{t.proxies.port}</th>
                <th className="py-3 px-4">Auth</th>
                <th className="py-3 px-4">{t.common.provider}</th>
                <th className="py-3 px-4">{t.common.status}</th>
                <th className="py-3 px-4 text-right">{t.common.actions}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {filteredProxies.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-slate-400">
                    <Network size={32} className="mx-auto text-slate-600 mb-2 opacity-60" />
                    {searchQuery ? "No matching proxies found" : "No proxies configured yet. Click Add Proxy to configure one."}
                  </td>
                </tr>
              ) : (
                filteredProxies.map((p) => {
                  const isExpanded = expandedErrorId === p.id;
                  return (
                    <React.Fragment key={p.id}>
                      <tr className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-3 px-4 font-medium text-slate-100 flex items-center gap-2">
                          <Network size={15} className="text-indigo-400 shrink-0" />
                          <div>
                            <div
                              className="font-semibold cursor-help"
                              title={
                                p.assigned_providers && p.assigned_providers.length > 0
                                  ? `Assigned providers:\n• ${p.assigned_providers.join("\n• ")}`
                                  : "Proxy available (not bound to any provider)"
                              }
                            >
                              {p.name}
                            </div>
                            {p.last_check && (
                              <div className="text-[10px] text-slate-400">
                                Checked: {new Date(p.last_check).toLocaleTimeString()}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          {p.country ? (
                            <div
                              className="flex items-center gap-1.5"
                              title={`${p.country} (${p.country_code || ""})`}
                            >
                              <span className="text-base leading-none select-none" role="img" aria-label={p.country}>
                                {getCountryFlag(p.country_code)}
                              </span>
                              <span className="font-medium text-slate-200">{p.country}</span>
                              {p.country_code && (
                                <span className="text-[10px] font-mono font-semibold bg-slate-800 border border-slate-700/60 px-1.5 py-0.5 rounded text-slate-400">
                                  {p.country_code}
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-500 text-[11px] flex items-center gap-1">
                              <Globe size={13} className="text-slate-500" />
                              <span>Unknown</span>
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`uppercase font-mono font-bold text-[11px] px-2 py-0.5 rounded border ${
                            p.scheme.includes("socks")
                              ? "bg-purple-950/60 text-purple-300 border-purple-800/60"
                              : "bg-sky-950/60 text-sky-300 border-sky-800/60"
                          }`}>
                            {p.scheme}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-200">
                          {p.host}:{p.port}
                        </td>
                        <td className="py-3 px-4">
                          {p.has_auth ? (
                            <span className="text-[10px] bg-slate-800 border border-slate-700/80 px-2 py-0.5 rounded text-amber-300 font-mono">
                              User/Pass
                            </span>
                          ) : (
                            <span className="text-slate-400 text-[10px]">No Auth (IP Whitelist)</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {p.assigned_providers && p.assigned_providers.length > 0 ? (
                            <div
                              className="inline-flex items-center cursor-pointer"
                              title={`Assigned to providers:\n• ${p.assigned_providers.join("\n• ")}`}
                              onMouseEnter={(e) => {
                                const rect = e.currentTarget.getBoundingClientRect();
                                showProviderTooltip(p.assigned_providers || [], p.name, rect);
                              }}
                              onMouseLeave={hideProviderTooltip}
                            >
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-950/70 hover:bg-indigo-900/90 border border-indigo-700/50 hover:border-indigo-500/70 text-indigo-300 hover:text-indigo-200 font-semibold text-[11px] transition-all shadow-2xs">
                                <Layers size={12} className="text-indigo-400" />
                                <span>
                                  {p.assigned_providers.length} {p.assigned_providers.length === 1 ? "provider" : "providers"}
                                </span>
                              </span>
                            </div>
                          ) : (
                            <span
                              className="text-slate-500 text-[11px] flex items-center gap-1 select-none"
                              title="This proxy is not assigned to any provider yet"
                            >
                              <span className="w-1.5 h-1.5 rounded-full bg-slate-600" />
                              <span>Unassigned</span>
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <StatusBadge status={p.status} />
                            {p.status === "ERROR" && p.last_error && (
                              <button
                                onClick={() => setExpandedErrorId(isExpanded ? null : p.id)}
                                className="text-[10px] text-rose-400 hover:text-rose-300 underline flex items-center gap-0.5"
                                title="View error details"
                              >
                                <span>{t.common.details}</span>
                                {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                              </button>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right space-x-1 whitespace-nowrap">
                          <button
                            onClick={() => handleTest(p.id)}
                            disabled={testingId === p.id}
                            className="btn-press px-2.5 py-1 bg-white/[0.05] hover:bg-white/[0.09] text-slate-200 text-[11px] font-medium rounded-lg border border-white/10 transition-colors inline-flex items-center gap-1.5 shadow-2xs disabled:opacity-50 cursor-pointer"
                          >
                            <Play size={11} className={testingId === p.id ? "animate-spin text-indigo-400" : ""} />
                            <span>{testingId === p.id ? t.common.testing : t.common.test}</span>
                          </button>
                          <button
                            onClick={() => openAssignKeysModal(p)}
                            className="btn-press p-1.5 text-slate-400 hover:text-indigo-300 hover:bg-white/[0.06] rounded-lg transition-colors cursor-pointer"
                            title="Assign proxy to credentials"
                          >
                            <KeyRound size={13} />
                          </button>
                          <button
                            onClick={() => openEditModal(p)}
                            className="btn-press p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] rounded-lg transition-colors cursor-pointer"
                            title={t.common.edit}
                          >
                            <Edit2 size={13} />
                          </button>
                          <button
                            onClick={() => handleDelete(p.id, p.name)}
                            className="btn-press p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors cursor-pointer"
                            title={t.common.delete}
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>

                      {/* Expanded error row */}
                      {isExpanded && p.last_error && (
                        <tr className="bg-rose-950/20 border-b border-rose-900/30">
                          <td colSpan={8} className="py-2.5 px-4 text-xs">
                            <div className="flex items-start gap-2 text-rose-300">
                              <AlertTriangle size={15} className="text-rose-400 shrink-0 mt-0.5" />
                              <div className="space-y-1 font-sans">
                                <div className="font-semibold">Error reason:</div>
                                <div className="text-[11px] text-rose-200 whitespace-pre-wrap bg-slate-950/60 p-2.5 rounded-lg border border-rose-900/40 font-mono">
                                  {p.last_error}
                                </div>
                              </div>
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
      </div>

      {/* Global Test Result Banner */}
      {testResult && (
        <div
          className={`p-4 rounded-xl border text-xs flex flex-col gap-2 transition-all shadow-md ${
            testResult.result.success
              ? "bg-emerald-950/70 border-emerald-800 text-emerald-300"
              : "bg-rose-950/70 border-rose-800 text-rose-300"
          }`}
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2 font-semibold">
              {testResult.result.success ? (
                <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />
              ) : (
                <AlertTriangle size={18} className="text-rose-400 shrink-0" />
              )}
              <span>{testResult.result.message}</span>
            </div>
            <div className="flex items-center gap-2">
              {testResult.result.country && (
                <span className="text-[11px] font-medium text-slate-200 flex items-center gap-1 bg-slate-900/90 px-2 py-0.5 rounded border border-slate-700/80">
                  <span role="img" aria-label={testResult.result.country}>{getCountryFlag(testResult.result.country_code)}</span>
                  <span>{testResult.result.country}</span>
                  {testResult.result.country_code && <span className="text-slate-400 font-mono text-[10px]">({testResult.result.country_code})</span>}
                </span>
              )}
              <button
                onClick={() => setTestResult(null)}
                className="text-slate-400 hover:text-slate-200 text-xs px-2 py-0.5 rounded hover:bg-slate-800/40"
              >
                ✕
              </button>
            </div>
          </div>

          {testResult.result.details && (
            <div className="text-[11px] text-slate-200 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800 whitespace-pre-wrap font-sans mt-1">
              {testResult.result.details}
            </div>
          )}
        </div>
      )}

      {/* Modal: Add/Edit Proxy */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingProxy ? t.proxies.editProxy : t.proxies.addProxy}
      >
        <form onSubmit={handleSave} className="space-y-4">
          {/* Quick Paste Field */}
          {!editingProxy && (
            <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-2">
              <label className="block text-xs font-semibold text-slate-300 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Wand2 size={14} className="text-indigo-400" />
                  Quick Paste
                </span>
                <span className="text-[10px] text-slate-400 font-normal">
                  ip:port:user:pass or socks5://...
                </span>
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={quickString}
                  onChange={(e) => {
                    setQuickString(e.target.value);
                    handleQuickParse(e.target.value);
                  }}
                  placeholder="e.g.: 192.0.2.1:1080:login:password"
                  className="flex-1 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
                />
                <button
                  type="button"
                  onClick={() => handleQuickParse()}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition-colors"
                >
                  Parse
                </button>
              </div>
            </div>
          )}

          {/* Name */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              {t.common.name}
            </label>
            <input
              type="text"
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g.: Residential SOCKS5 Proxy"
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
            />
          </div>

          {/* Scheme & Host */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Protocol
              </label>
              <select
                value={formScheme}
                onChange={(e) => setFormScheme(e.target.value as any)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none uppercase font-mono font-semibold"
              >
                <option value="socks5">SOCKS5</option>
                <option value="http">HTTP</option>
                <option value="https">HTTPS</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-slate-300 mb-1">
                {t.proxies.host}
              </label>
              <input
                type="text"
                required
                value={formHost}
                onChange={(e) => {
                  const val = e.target.value;
                  // Auto-strip http:// or trailing ports if accidentally pasted
                  if (val.includes("://")) {
                    setFormHost(val.split("://")[1].split("/")[0].split(":")[0]);
                  } else if (val.includes(":")) {
                    const [h, p] = val.split(":");
                    setFormHost(h);
                    if (p && !isNaN(Number(p))) setFormPort(Number(p));
                  } else {
                    setFormHost(val);
                  }
                }}
                placeholder="e.g.: 192.0.2.1"
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
              />
            </div>
          </div>

          {/* Port */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              {t.proxies.port}
            </label>
            <input
              type="number"
              required
              value={formPort}
              onChange={(e) => setFormPort(parseInt(e.target.value) || 1080)}
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
            />
          </div>

          {/* Username & Password */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Username (optional)
              </label>
              <input
                type="text"
                value={formUsername}
                onChange={(e) => setFormUsername(e.target.value)}
                placeholder="If required"
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Password (optional)
              </label>
              <input
                type="password"
                value={formPassword}
                onChange={(e) => setFormPassword(e.target.value)}
                placeholder="If required"
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
              />
            </div>
          </div>

          {/* Modal Inline Test Result */}
          {modalTestResult && (
            <div
              className={`p-3 rounded-xl border text-xs space-y-1.5 ${
                modalTestResult.success
                  ? "bg-emerald-950/60 border-emerald-800 text-emerald-300"
                  : "bg-rose-950/60 border-rose-800 text-rose-300"
              }`}
            >
              <div className="flex items-center justify-between gap-2 flex-wrap font-semibold">
                <div className="flex items-center gap-1.5">
                  {modalTestResult.success ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                  <span>{modalTestResult.message}</span>
                </div>
                {modalTestResult.country && (
                  <span className="text-[11px] font-medium text-slate-200 flex items-center gap-1 bg-slate-900/90 px-2 py-0.5 rounded border border-slate-700/80">
                    <span role="img" aria-label={modalTestResult.country}>{getCountryFlag(modalTestResult.country_code)}</span>
                    <span>{modalTestResult.country}</span>
                    {modalTestResult.country_code && <span className="text-slate-400 font-mono text-[10px]">({modalTestResult.country_code})</span>}
                  </span>
                )}
              </div>
              {modalTestResult.details && (
                <div className="text-[11px] bg-slate-950/60 p-2 rounded border border-slate-800/80 text-slate-200 whitespace-pre-wrap font-sans">
                  {modalTestResult.details}
                </div>
              )}
            </div>
          )}

          {/* Modal Footer */}
          <div className="flex items-center justify-between pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={handleModalTest}
              disabled={modalTesting || !formHost}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              <Play size={12} className={modalTesting ? "animate-spin text-indigo-400" : ""} />
              <span>{modalTesting ? t.common.testing : t.proxies.testProxy}</span>
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium"
              >
                {t.common.cancel}
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs"
              >
                {t.common.save}
              </button>
            </div>
          </div>
        </form>
      </Modal>

      {/* Floating Provider Tooltip (Fixed Portal-style, never clipped by overflow-hidden/auto) */}
      {providerTooltip && (() => {
        const { rect, providers, proxyName } = providerTooltip;
        const tooltipWidth = 260;
        // Estimate height: header ~38px + items (each ~28px) + footer ~28px + padding ~24px
        const estimatedHeight = Math.min(320, 90 + providers.length * 28);

        // Check if there is enough space above the element without hitting top of window
        const spaceAbove = rect.top;
        const showBelow = spaceAbove < estimatedHeight + 20;

        const topPos = showBelow ? rect.bottom + 8 : rect.top - 8;
        const leftPos = Math.max(16, Math.min(window.innerWidth - tooltipWidth - 16, rect.left));

        return (
          <div
            style={{
              position: "fixed",
              top: `${topPos}px`,
              left: `${leftPos}px`,
              transform: showBelow ? "none" : "translateY(-100%)",
              width: `${tooltipWidth}px`,
              zIndex: 99999,
            }}
            onMouseEnter={keepProviderTooltip}
            onMouseLeave={hideProviderTooltip}
            className="p-3 bg-slate-950/98 border border-indigo-500/60 rounded-xl shadow-2xl shadow-indigo-950/60 backdrop-blur-xl transition-all duration-150 animate-in fade-in zoom-in-95 ring-1 ring-white/10"
          >
            <div className="text-[10px] uppercase font-bold text-indigo-400 tracking-wider mb-2 flex items-center justify-between border-b border-slate-800/80 pb-1.5">
              <span className="flex items-center gap-1.5">
                <Layers size={13} className="text-indigo-400" />
                <span>Providers ({providers.length}):</span>
              </span>
              <span className="text-[9px] text-slate-400 font-mono font-normal truncate max-w-[100px]" title={proxyName}>
                {proxyName}
              </span>
            </div>
            <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
              {providers.map((provName) => (
                <div
                  key={provName}
                  className="flex items-center gap-2 text-xs text-slate-100 font-medium bg-slate-900/80 px-2.5 py-1.5 rounded-lg border border-slate-800/90 hover:border-indigo-800/60 transition-colors"
                >
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0 shadow-xs shadow-emerald-400/50" />
                  <span className="truncate">{provName}</span>
                </div>
              ))}
            </div>
            <div className="mt-2 pt-1.5 border-t border-slate-800/80 text-[10px] text-slate-400 flex items-center justify-between">
              <span>Unique providers</span>
              <span className="text-emerald-400 text-[10px] font-semibold">Bound</span>
            </div>
          </div>
        );
      })()}

      {/* Modal: Assign Proxy to Credentials */}
      <Modal
        isOpen={isAssignKeysModalOpen}
        onClose={() => !isSavingAssignKeys && setIsAssignKeysModalOpen(false)}
        title={
          selectedProxyForKeys
            ? `Bind proxy "${selectedProxyForKeys.name}" to API Keys`
            : "Bind Proxy to Keys"
        }
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3 bg-slate-950/60 p-3 rounded-lg border border-slate-800">
            <div className="flex items-center gap-2">
              <Network size={16} className="text-indigo-400" />
              <div>
                <div className="text-xs font-semibold text-slate-200">
                  {selectedProxyForKeys?.name} ({selectedProxyForKeys?.scheme?.toUpperCase()}://
                  {selectedProxyForKeys?.host}:{selectedProxyForKeys?.port})
                </div>
                <div className="text-[11px] text-slate-400">
                  Select credentials that should route their outbound requests through this proxy
                </div>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs font-bold text-indigo-300">
                Selected: {selectedCredIdsForProxy.length}
              </span>
            </div>
          </div>

          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={keysSearchQuery}
              onChange={(e) => setKeysSearchQuery(e.target.value)}
              placeholder="Search by key name or provider..."
              className="w-full pl-8 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div className="max-h-80 overflow-y-auto space-y-3 pr-1">
            {(() => {
              const filtered = allCredentials.filter((c) => {
                if (!keysSearchQuery.trim()) return true;
                const q = keysSearchQuery.toLowerCase().trim();
                return (
                  c.name.toLowerCase().includes(q) ||
                  c.provider_name.toLowerCase().includes(q) ||
                  (c.group_name && c.group_name.toLowerCase().includes(q))
                );
              });

              const providerMap = new Map<string, Credential[]>();
              filtered.forEach((c) => {
                const list = providerMap.get(c.provider_name) || [];
                list.push(c);
                providerMap.set(c.provider_name, list);
              });

              if (providerMap.size === 0) {
                return (
                  <div className="p-6 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-lg">
                    No credentials found
                  </div>
                );
              }

              return Array.from(providerMap.entries()).map(([provName, creds]) => {
                const allSelected = creds.every((c) => selectedCredIdsForProxy.includes(c.id));
                const someSelected = creds.some((c) => selectedCredIdsForProxy.includes(c.id));

                return (
                  <div
                    key={provName}
                    className="bg-slate-950/80 border border-slate-800 rounded-lg overflow-hidden"
                  >
                    <div className="px-3 py-2 bg-slate-900/90 border-b border-slate-800/80 flex items-center justify-between">
                      <label className="flex items-center gap-2 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          ref={(el) => {
                            if (el) el.indeterminate = someSelected && !allSelected;
                          }}
                          onChange={() => toggleAllCredsForProvider(creds)}
                          className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 cursor-pointer w-3.5 h-3.5"
                        />
                        <span className="text-xs font-semibold text-slate-200">{provName}</span>
                        <span className="text-[10px] text-slate-400">({creds.length})</span>
                      </label>
                    </div>

                    <div className="p-2 divide-y divide-slate-800/50">
                      {creds.map((c) => {
                        const isChecked = selectedCredIdsForProxy.includes(c.id);
                        const isOtherProxy = c.proxy_id && c.proxy_id !== selectedProxyForKeys?.id;

                        return (
                          <label
                            key={c.id}
                            className={`flex items-center justify-between p-2 rounded hover:bg-slate-800/40 cursor-pointer transition-colors ${
                              isChecked ? "bg-indigo-950/20" : ""
                            }`}
                          >
                            <div className="flex items-center gap-2.5 min-w-0">
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => toggleProxyCred(c.id)}
                                className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 cursor-pointer w-3.5 h-3.5 shrink-0"
                              />
                              <div className="min-w-0">
                                <div className="text-xs font-medium text-slate-200 flex items-center gap-1.5">
                                  <span className="truncate">{c.name}</span>
                                  {c.group_name && (
                                    <span className="text-[9px] text-amber-300 bg-amber-950/50 border border-amber-800/50 px-1 py-0.2 rounded">
                                      {c.group_name}
                                    </span>
                                  )}
                                </div>
                                <div className="text-[10px] text-slate-400 font-mono">
                                  {c.masked_key}
                                </div>
                              </div>
                            </div>

                            <div className="text-right shrink-0 text-[10px]">
                              {isChecked ? (
                                <span className="text-emerald-400 font-medium bg-emerald-950/60 border border-emerald-800/60 px-1.5 py-0.5 rounded">
                                  Bound to this
                                </span>
                              ) : isOtherProxy ? (
                                <span className="text-slate-400 bg-slate-900 border border-slate-800 px-1.5 py-0.5 rounded">
                                  Assigned: {c.proxy_name}
                                </span>
                              ) : (
                                <span className="text-slate-500">DIRECT</span>
                              )}
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                );
              });
            })()}
          </div>

          <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-800">
            <button
              type="button"
              disabled={isSavingAssignKeys}
              onClick={() => setIsAssignKeysModalOpen(false)}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium cursor-pointer disabled:opacity-50"
            >
              {t.common.cancel}
            </button>
            <button
              type="button"
              disabled={isSavingAssignKeys}
              onClick={handleSaveAssignKeys}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
            >
              {isSavingAssignKeys ? (
                <>
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Check size={14} />
                  <span>{t.common.save}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
