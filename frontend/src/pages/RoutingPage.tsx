import React, { useEffect, useState, useMemo } from "react";
import { Plus, ArrowUp, ArrowDown, Trash2, Edit2, GitFork, ShieldCheck, Check, Brain, Zap, Maximize2, Shuffle, Key, Folder, Thermometer } from "lucide-react";
import { apiRequest } from "../api/client";
import { RoutingProfile, Provider, Credential, DiscoveredModel, RoutingCandidate, DetailedAnalyticsResponse, ProfileStatsItem } from "../types";
import { Modal } from "../components/Modal";
import { getHiddenModelIds, isModelVisible } from "../utils/models";
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

export const ROUTE_TEMP_PRESETS = [
  { id: "inherit", label: "Inherit", value: null },
  { id: "0.0", label: "0.0", value: 0.0, desc: "Strict / Code" },
  { id: "0.2", label: "0.2", value: 0.2, desc: "Precise" },
  { id: "0.5", label: "0.5", value: 0.5, desc: "Balanced" },
  { id: "0.7", label: "0.7", value: 0.7, desc: "Standard" },
  { id: "1.0", label: "1.0", value: 1.0, desc: "Creative" },
  { id: "1.5", label: "1.5", value: 1.5, desc: "Experimental" },
  { id: "custom", label: "Custom ✏️", value: null },
];

interface FormCandidate {
  candidate_type?: "model" | "profile";
  target_profile_id?: number | null;
  provider_id?: number | null;
  credential_id?: number | null;
  credential_group?: string | null;
  model_id?: number | null;
  is_active: boolean;
  thinking_effort?: string | null;
  temperature?: number | null;
}

export const RoutingPage: React.FC = () => {
  const { t } = useI18n();
  const [profiles, setProfiles] = useState<RoutingProfile[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [models, setModels] = useState<DiscoveredModel[]>([]);
  const [profileStats, setProfileStats] = useState<Record<string, ProfileStatsItem>>({});
  const [loading, setLoading] = useState(true);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<RoutingProfile | null>(null);

  const [formName, setFormName] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formStrategy, setFormStrategy] = useState<"priority" | "cache-optimized" | "round_robin" | "least_latency">("priority");
  const [formRetryCount, setFormRetryCount] = useState(3);
  const [formTimeout, setFormTimeout] = useState(60.0);
  const [formThinkingEffort, setFormThinkingEffort] = useState<string>("inherit");
  const [formCustomThinking, setFormCustomThinking] = useState<string>("");
  const [formTempPreset, setFormTempPreset] = useState<string>("inherit");
  const [formCustomTemp, setFormCustomTemp] = useState<string>("");
  const [formContextPreset, setFormContextPreset] = useState<string>("auto");
  const [formCustomContext, setFormCustomContext] = useState<string>("");
  const [formCandidates, setFormCandidates] = useState<FormCandidate[]>([]);
  const [formRandomizeCandidates, setFormRandomizeCandidates] = useState(false);

  // Candidate adder state
  const [candTargetType, setCandTargetType] = useState<"model" | "profile">("model");
  const [candTargetProfileId, setCandTargetProfileId] = useState<number | null>(null);
  const [candProviderId, setCandProviderId] = useState<number>(1);
  const [candCredTarget, setCandCredTarget] = useState<string>("all");
  const [candModelId, setCandModelId] = useState<number>(1);
  const [candThinkingEffort, setCandThinkingEffort] = useState<string>("inherit");
  const [candCustomThinking, setCandCustomThinking] = useState<string>("");
  const [candTempPreset, setCandTempPreset] = useState<string>("inherit");
  const [candCustomTemp, setCandCustomTemp] = useState<string>("");

  const availableSubProfiles = useMemo(() => {
    return profiles.filter((p) => !editingProfile || p.id !== editingProfile.id);
  }, [profiles, editingProfile]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [r, p, c, m, statsRes] = await Promise.all([
        apiRequest<RoutingProfile[]>("/api/admin/routes"),
        apiRequest<Provider[]>("/api/admin/providers"),
        apiRequest<Credential[]>("/api/admin/credentials"),
        apiRequest<DiscoveredModel[]>("/api/admin/models"),
        apiRequest<DetailedAnalyticsResponse>("/api/admin/dashboard/detailed-stats?period=all").catch(() => null),
      ]);
      setProfiles(r);
      setProviders(p);
      setCredentials(c);
      setModels(m);

      if (statsRes && statsRes.by_profiles) {
        const statsMap: Record<string, ProfileStatsItem> = {};
        for (const item of statsRes.by_profiles) {
          statsMap[item.slug] = item;
        }
        setProfileStats(statsMap);
      }

      const hiddenIds = getHiddenModelIds();
      const firstWithVisible = p.find((pr) =>
        m.some((model) => model.provider_id === pr.id && isModelVisible(model, hiddenIds))
      );
      if (firstWithVisible) {
        setCandProviderId(firstWithVisible.id);
      } else if (p.length > 0) {
        setCandProviderId(p[0].id);
      }

      const firstVisibleModel = m.find((model) => isModelVisible(model, hiddenIds));
      if (firstVisibleModel) {
        setCandModelId(firstVisibleModel.id);
      } else if (m.length > 0) {
        setCandModelId(m[0].id);
      }

      if (r.length > 0 && !candTargetProfileId) setCandTargetProfileId(r[0].id);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openCreateModal = () => {
    setEditingProfile(null);
    setFormName("");
    setFormSlug("");
    setFormStrategy("priority");
    setFormRetryCount(3);
    setFormTimeout(60.0);
    setFormThinkingEffort("inherit");
    setFormCustomThinking("");
    setFormTempPreset("inherit");
    setFormCustomTemp("");
    setCandThinkingEffort("inherit");
    setCandCustomThinking("");
    setCandTempPreset("inherit");
    setCandCustomTemp("");
    setFormContextPreset("auto");
    setFormCustomContext("");
    setFormRandomizeCandidates(false);
    setFormCandidates([]);
    setCandTargetType("model");
    setCandCredTarget("all");
    const hiddenIds = getHiddenModelIds();
    const firstWithVisible = providers.find((p) =>
      models.some((m) => m.provider_id === p.id && isModelVisible(m, hiddenIds))
    );
    if (firstWithVisible) {
      setCandProviderId(firstWithVisible.id);
    }
    if (profiles.length > 0) {
      setCandTargetProfileId(profiles[0].id);
    }
    setIsModalOpen(true);
  };

  const openEditModal = (p: RoutingProfile) => {
    setEditingProfile(p);
    setFormName(p.name);
    setFormSlug(p.slug);
    setFormStrategy((p.strategy as any) || "priority");
    setFormRetryCount(p.retry_count);
    setFormTimeout(p.timeout_seconds);

    if (p.thinking_effort) {
      if (["auto", "low", "medium", "high", "off"].includes(p.thinking_effort)) {
        setFormThinkingEffort(p.thinking_effort);
        setFormCustomThinking("");
      } else {
        setFormThinkingEffort("custom");
        setFormCustomThinking(p.thinking_effort);
      }
    } else {
      setFormThinkingEffort("inherit");
      setFormCustomThinking("");
    }

    if (p.temperature !== null && p.temperature !== undefined) {
      const match = ROUTE_TEMP_PRESETS.find(
        (pr) => pr.value !== null && Math.abs(pr.value - p.temperature!) < 0.001
      );
      if (match) {
        setFormTempPreset(match.id);
        setFormCustomTemp("");
      } else {
        setFormTempPreset("custom");
        setFormCustomTemp(String(p.temperature));
      }
    } else {
      setFormTempPreset("inherit");
      setFormCustomTemp("");
    }

    if (p.context_length) {
      const match = ROUTE_CONTEXT_PRESETS.find((pr) => pr.value === p.context_length);
      if (match && match.value !== null) {
        setFormContextPreset(String(match.value));
        setFormCustomContext("");
      } else {
        setFormContextPreset("custom");
        setFormCustomContext(String(p.context_length));
      }
    } else {
      setFormContextPreset("auto");
      setFormCustomContext("");
    }

    setCandThinkingEffort("inherit");
    setCandCustomThinking("");
    setCandTempPreset("inherit");
    setCandCustomTemp("");
    setCandCredTarget("all");
    setFormRandomizeCandidates(p.randomize_candidates ?? false);

    setFormCandidates(
      p.candidates.map((c) => ({
        candidate_type: c.candidate_type || (c.target_profile_id ? "profile" : "model"),
        target_profile_id: c.target_profile_id || null,
        provider_id: c.provider_id || null,
        credential_id: c.credential_id || null,
        credential_group: c.credential_group || null,
        model_id: c.model_id || null,
        is_active: c.is_active,
        thinking_effort: c.thinking_effort || null,
        temperature: c.temperature !== undefined ? c.temperature : null,
      }))
    );
    setCandTargetType("model");
    const hiddenIds = getHiddenModelIds();
    const firstWithVisible = providers.find((pr) =>
      models.some((m) => m.provider_id === pr.id && isModelVisible(m, hiddenIds))
    );
    if (firstWithVisible) {
      setCandProviderId(firstWithVisible.id);
    }
    const otherProfiles = profiles.filter((prof) => prof.id !== p.id);
    if (otherProfiles.length > 0) {
      setCandTargetProfileId(otherProfiles[0].id);
    }
    setIsModalOpen(true);
  };

  const addCandidate = () => {
    const effCandidateThinking =
      candThinkingEffort === "custom"
        ? (candCustomThinking.trim() || "4096")
        : candThinkingEffort === "inherit"
        ? null
        : candThinkingEffort;

    let candResolvedTemp: number | null = null;
    if (candTempPreset === "custom") {
      const parsed = parseFloat(candCustomTemp.trim());
      if (!isNaN(parsed)) candResolvedTemp = Math.min(Math.max(parsed, 0), 2.0);
    } else if (candTempPreset !== "inherit") {
      const parsed = parseFloat(candTempPreset);
      if (!isNaN(parsed)) candResolvedTemp = parsed;
    }

    if (candTargetType === "profile") {
      if (!candTargetProfileId) return;
      if (editingProfile && candTargetProfileId === editingProfile.id) {
        alert("Cannot nest a profile inside itself.");
        return;
      }
      setFormCandidates([
        ...formCandidates,
        {
          candidate_type: "profile",
          target_profile_id: candTargetProfileId,
          is_active: true,
          thinking_effort: effCandidateThinking,
          temperature: candResolvedTemp,
        },
      ]);
    } else {
      if (!candModelId) return;
      let credId: number | null = null;
      let credGroup: string | null = null;
      if (candCredTarget.startsWith("key:")) {
        credId = parseInt(candCredTarget.slice(4));
      } else if (candCredTarget.startsWith("group:")) {
        credGroup = candCredTarget.slice(6);
      }

      setFormCandidates([
        ...formCandidates,
        {
          candidate_type: "model",
          provider_id: candProviderId,
          credential_id: credId,
          credential_group: credGroup,
          model_id: candModelId,
          is_active: true,
          thinking_effort: effCandidateThinking,
          temperature: candResolvedTemp,
        },
      ]);
    }
  };

  const removeCandidate = (index: number) => {
    setFormCandidates(formCandidates.filter((_, idx) => idx !== index));
  };

  const moveCandidate = (index: number, direction: "up" | "down") => {
    const newIdx = direction === "up" ? index - 1 : index + 1;
    if (newIdx < 0 || newIdx >= formCandidates.length) return;
    const items = [...formCandidates];
    const [moved] = items.splice(index, 1);
    items.splice(newIdx, 0, moved);
    setFormCandidates(items);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const effProfileThinking =
        formThinkingEffort === "custom"
          ? (formCustomThinking.trim() || "4096")
          : formThinkingEffort === "inherit"
          ? null
          : formThinkingEffort;

      let effProfileTemp: number | null = null;
      if (formTempPreset === "custom") {
        const parsed = parseFloat(formCustomTemp.trim());
        if (!isNaN(parsed)) effProfileTemp = Math.min(Math.max(parsed, 0), 2.0);
      } else if (formTempPreset !== "inherit") {
        const parsed = parseFloat(formTempPreset);
        if (!isNaN(parsed)) effProfileTemp = parsed;
      }

      let effContextLength: number | null = null;
      if (formContextPreset === "custom") {
        const parsed = parseInt(formCustomContext.trim());
        if (!isNaN(parsed) && parsed > 0) {
          effContextLength = parsed;
        }
      } else if (formContextPreset !== "auto") {
        const parsed = parseInt(formContextPreset);
        if (!isNaN(parsed) && parsed > 0) {
          effContextLength = parsed;
        }
      }

      const payload = {
        name: formName,
        slug: formSlug || formName.toLowerCase().replace(/[^a-z0-9]/g, "-"),
        strategy: formStrategy,
        retry_count: formRetryCount,
        timeout_seconds: formTimeout,
        thinking_effort: effProfileThinking,
        temperature: effProfileTemp,
        context_length: effContextLength,
        randomize_candidates: formRandomizeCandidates,
        randomize_keys: true,
        candidates: formCandidates.map((c, idx) => ({
          candidate_type: c.candidate_type || "model",
          target_profile_id: c.candidate_type === "profile" ? c.target_profile_id : null,
          provider_id: c.candidate_type === "model" ? c.provider_id : null,
          credential_id: c.candidate_type === "model" ? (c.credential_id || null) : null,
          credential_group: c.candidate_type === "model" ? (c.credential_group || null) : null,
          model_id: c.candidate_type === "model" ? c.model_id : null,
          priority_order: idx,
          is_active: c.is_active,
          thinking_effort: c.thinking_effort || null,
          temperature: c.temperature !== undefined ? c.temperature : null,
        })),
      };

      if (editingProfile) {
        await apiRequest(`/api/admin/routes/${editingProfile.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiRequest("/api/admin/routes", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete routing profile "${name}"?`)) return;
    try {
      await apiRequest(`/api/admin/routes/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // Filtered models based on candProviderId: only visible (is_visible === true), enabled, available, and deduplicated
  const availableModelsForProvider = useMemo(() => {
    const hiddenIds = getHiddenModelIds();
    const filtered = models.filter(
      (m) => m.provider_id === candProviderId && isModelVisible(m, hiddenIds)
    );
    const map = new Map<string, DiscoveredModel>();
    filtered.forEach((m) => {
      if (!map.has(m.provider_model_id)) {
        map.set(m.provider_model_id, m);
      }
    });
    return Array.from(map.values()).sort((a, b) => a.provider_model_id.localeCompare(b.provider_model_id));
  }, [models, candProviderId]);

  const availableCredsForProvider = credentials.filter((c) => c.provider_id === candProviderId);

  const availableGroupsForProvider = useMemo(() => {
    const groups = new Set<string>();
    credentials
      .filter((c) => c.provider_id === candProviderId && c.group_name && c.group_name.trim())
      .forEach((c) => groups.add(c.group_name!.trim()));
    return Array.from(groups).sort();
  }, [credentials, candProviderId]);

  useEffect(() => {
    if (availableModelsForProvider.length > 0 && !availableModelsForProvider.some((m) => m.id === candModelId)) {
      setCandModelId(availableModelsForProvider[0].id);
    }
  }, [availableModelsForProvider, candModelId]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <GitFork size={20} className="text-purple-400" />
            {t.routing.title}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {t.routing.subtitle}
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="btn-press flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-500/20 border border-white/10 cursor-pointer"
        >
          <Plus size={15} />
          <span>{t.routing.createRoute}</span>
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {profiles.length === 0 ? (
          <div className="p-12 text-center glass-panel card-specular rounded-2xl border border-white/[0.06] text-xs text-slate-400">
            No routing profiles created yet. Click "{t.routing.createRoute}" to create a fallback queue (e.g. route/coding).
          </div>
        ) : (
          profiles.map((p) => (
            <div key={p.id} className="glass-card card-specular rounded-2xl border border-white/[0.07] p-5 space-y-4 hover:border-white/[0.12] transition-all duration-200">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-purple-500/10 border border-purple-500/25 flex items-center justify-center text-purple-300 shadow-sm shrink-0">
                    <GitFork size={17} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-slate-100 text-sm tracking-tight">{p.name}</span>
                      <span className="font-mono text-xs text-purple-300 bg-purple-950/60 px-2 py-0.5 rounded-lg border border-purple-800/60 shadow-xs">
                        route/{p.slug}
                      </span>
                      {p.thinking_effort && (
                        <span className="flex items-center gap-1 text-[10px] bg-purple-500/15 text-purple-300 px-2 py-0.5 rounded-lg border border-purple-500/30 font-mono" title="Default Thinking Level for profile">
                          <Brain size={11} /> CoT: {p.thinking_effort}
                        </span>
                      )}
                      {p.temperature !== null && p.temperature !== undefined && (
                        <span className="flex items-center gap-1 text-[10px] bg-rose-500/15 text-rose-300 px-2 py-0.5 rounded-lg border border-rose-500/30 font-mono" title="Default Temperature for profile">
                          <Thermometer size={11} /> temp: {p.temperature}
                        </span>
                      )}
                      {p.context_length ? (
                        <span className="flex items-center gap-1 text-[10px] bg-cyan-500/15 text-cyan-300 px-2 py-0.5 rounded-lg border border-cyan-500/30 font-mono" title="Route context window">
                          <Maximize2 size={10} /> {p.context_length >= 1000000 ? `${p.context_length / 1000000}M` : p.context_length >= 1000 ? `${Math.round(p.context_length / 1000)}k` : p.context_length}
                        </span>
                      ) : null}
                      {p.randomize_candidates && (
                        <span className="flex items-center gap-1 text-[10px] bg-amber-500/15 text-amber-300 px-2 py-0.5 rounded-lg border border-amber-500/30 font-mono" title="Random selection of fallback models">
                          <Shuffle size={10} /> {t.routing.randomize}
                        </span>
                      )}
                      {p.strategy === "cache-optimized" && (
                        <span className="flex items-center gap-1 text-[10px] bg-emerald-500/15 text-emerald-300 px-2 py-0.5 rounded-lg border border-emerald-500/30 font-mono" title="Prompt Cache Affinity (Rendezvous Hashing)">
                          <Zap size={10} className="text-emerald-400" /> Cache-Optimized
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-slate-400 bg-slate-950/40 px-2.5 py-1 rounded-lg border border-white/[0.04]">
                    {p.candidates.length} candidates • {p.retry_count} retries • {p.timeout_seconds}s timeout
                    {p.context_length ? ` • ${Number(p.context_length).toLocaleString()} ctx` : " • auto ctx"}
                  </span>
                  <button
                    onClick={() => openEditModal(p)}
                    className="btn-press p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] rounded-lg border border-white/[0.04] transition-colors cursor-pointer"
                    title={t.common.edit}
                  >
                    <Edit2 size={14} />
                  </button>
                  <button
                    onClick={() => handleDelete(p.id, p.name)}
                    className="btn-press p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg border border-white/[0.04] transition-colors cursor-pointer"
                    title={t.common.delete}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Profile Live Stats Bar */}
              {(() => {
                const st = profileStats[p.slug];
                if (!st) return null;
                return (
                  <div className="flex items-center gap-3.5 flex-wrap text-xs px-3.5 py-2 glass-panel rounded-xl border border-white/[0.06]">
                    <span className="text-slate-400">
                      Total requests: <strong className="text-slate-100 font-mono">{st.requests_count}</strong>
                    </span>
                    <span className="text-emerald-400">
                      1st candidate: <strong className="font-mono">{st.first_candidate_success_count}</strong>
                    </span>
                    {st.key_failover_count > 0 && (
                      <span className="text-amber-300">
                        (+{st.key_failover_count} key rotations)
                      </span>
                    )}
                    {st.fallback_success_count > 0 && (
                      <span className="text-purple-300 font-semibold">
                        +{st.fallback_success_count} saved by Fallback ({st.fallback_rate}%)
                      </span>
                    )}
                    {st.failure_count > 0 && (
                      <span className="text-rose-400">
                        Failures: <strong className="font-mono">{st.failure_count}</strong>
                      </span>
                    )}
                    {st.requests_count > 0 && (
                      <span className="text-sky-300 text-[11px] font-mono ml-auto">
                        Avg latency: {st.avg_latency_ms}ms
                      </span>
                    )}
                  </div>
                );
              })()}

              {/* Priority Fallback Chain Visualizer */}
              <div className="space-y-2 pt-1">
                {p.candidates.map((c, idx) => {
                  const st = profileStats[p.slug];
                  const candStat = st?.candidates?.find((cs) => cs.priority_order === c.priority_order) || st?.candidates?.[idx];
                  return (
                    <div
                      key={c.id}
                      className="flex items-center gap-3 p-2.5 bg-slate-950/60 border border-white/[0.05] hover:border-white/[0.1] rounded-xl text-xs transition-all"
                    >
                      <span className="w-6 h-6 rounded-lg bg-white/[0.04] text-slate-300 text-[11px] font-mono flex items-center justify-center font-bold border border-white/[0.06] shrink-0">
                        #{idx + 1}
                      </span>
                      {c.candidate_type === "profile" || c.target_profile_id ? (
                        <div className="flex-1 flex items-center justify-between gap-2 flex-wrap">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="px-2 py-0.5 rounded-lg text-[10px] font-medium bg-purple-950/80 text-purple-300 border border-purple-800/60 flex items-center gap-1 shadow-xs">
                              <GitFork size={11} />
                              Nested Profile
                            </span>
                            <span className="font-semibold text-slate-100">{c.target_profile_name || "Profile"}</span>
                            <span className="text-slate-500 text-[11px]">→</span>
                            <span className="font-mono text-purple-300 bg-purple-950/40 px-2 py-0.5 rounded-lg border border-purple-900/40 text-[11px]">
                              route/{c.target_profile_slug}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            {candStat && candStat.requests_count > 0 && (
                              <span className="text-[10px] font-mono text-slate-300 bg-slate-900/90 border border-white/[0.06] px-2 py-0.5 rounded-lg font-medium shrink-0">
                                {candStat.requests_count} reqs ({candStat.success_count} success)
                              </span>
                            )}
                            {c.thinking_effort ? (
                              <span className="text-[10px] bg-purple-900/50 text-purple-200 border border-purple-700/50 px-2 py-0.5 rounded-lg font-mono flex items-center gap-1 shrink-0" title="Candidate Thinking Level">
                                <Brain size={10} /> CoT: {c.thinking_effort}
                              </span>
                            ) : p.thinking_effort ? (
                              <span className="text-[10px] text-purple-400/60 font-mono shrink-0" title="Inherited from profile">
                                (CoT: {p.thinking_effort})
                              </span>
                            ) : null}
                            {c.temperature !== null && c.temperature !== undefined ? (
                              <span className="text-[10px] bg-rose-900/50 text-rose-200 border border-rose-700/50 px-2 py-0.5 rounded-lg font-mono flex items-center gap-1 shrink-0" title="Candidate Temperature">
                                <Thermometer size={10} /> temp: {c.temperature}
                              </span>
                            ) : p.temperature !== null && p.temperature !== undefined ? (
                              <span className="text-[10px] text-rose-400/60 font-mono shrink-0" title="Inherited from profile">
                                (temp: {p.temperature})
                              </span>
                            ) : null}
                          </div>
                        </div>
                      ) : (
                        <div className="flex-1 flex items-center justify-between gap-2 flex-wrap">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-slate-200">{c.provider_name}</span>
                            <span className="text-slate-500 text-[11px]">→</span>
                            <span className="font-mono text-indigo-300 text-[11px] bg-indigo-950/40 px-1.5 py-0.5 rounded border border-indigo-900/30">{c.canonical_slug}</span>
                            <span className="text-slate-500 text-[11px]">via</span>
                            {c.credential_id ? (
                              <span className="text-[11px] bg-slate-900/90 border border-white/[0.06] px-2 py-0.5 rounded-lg text-slate-300">
                                {c.credential_name || "Key"}
                              </span>
                            ) : c.credential_group ? (
                              <span className="text-[11px] bg-blue-950/60 border border-blue-800/60 px-2 py-0.5 rounded-lg text-blue-300 font-medium flex items-center gap-1 shadow-xs">
                                <Folder size={10} className="text-blue-400" />
                                Group: {c.credential_group} (Fallback)
                              </span>
                            ) : (
                              <span className="text-[11px] bg-amber-950/60 border border-amber-800/60 px-2 py-0.5 rounded-lg text-amber-300 font-medium flex items-center gap-1 shadow-xs">
                                <Zap size={10} className="text-amber-400" />
                                All keys (Fallback)
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {candStat && candStat.requests_count > 0 && (
                              <span className="text-[10px] font-mono text-slate-300 bg-slate-900/90 border border-white/[0.06] px-2 py-0.5 rounded-lg font-medium shrink-0">
                                {candStat.requests_count} reqs ({candStat.success_count} success)
                              </span>
                            )}
                            {c.thinking_effort ? (
                              <span className="text-[10px] bg-purple-900/50 text-purple-200 border border-purple-700/50 px-2 py-0.5 rounded-lg font-mono flex items-center gap-1 shrink-0" title="Candidate Thinking Level">
                                <Brain size={10} /> CoT: {c.thinking_effort}
                              </span>
                            ) : p.thinking_effort ? (
                              <span className="text-[10px] text-purple-400/60 font-mono shrink-0" title="Inherited from profile">
                                (CoT: {p.thinking_effort})
                              </span>
                            ) : null}
                            {c.temperature !== null && c.temperature !== undefined ? (
                              <span className="text-[10px] bg-rose-900/50 text-rose-200 border border-rose-700/50 px-2 py-0.5 rounded-lg font-mono flex items-center gap-1 shrink-0" title="Candidate Temperature">
                                <Thermometer size={10} /> temp: {c.temperature}
                              </span>
                            ) : p.temperature !== null && p.temperature !== undefined ? (
                              <span className="text-[10px] text-rose-400/60 font-mono shrink-0" title="Inherited from profile">
                                (temp: {p.temperature})
                              </span>
                            ) : null}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modal: Create/Edit Routing Profile */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingProfile ? `Edit Route: route/${editingProfile.slug}` : "Create Routing Profile"}
        maxWidth="xl"
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Route Name</label>
              <input
                type="text"
                required
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Coding Priority"
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Route Slug</label>
              <input
                type="text"
                value={formSlug}
                onChange={(e) => setFormSlug(e.target.value)}
                placeholder="coding"
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Стратегия маршрутизации</label>
              <select
                value={formStrategy}
                onChange={(e) => setFormStrategy(e.target.value as any)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              >
                <option value="priority">Priority (По цепочке)</option>
                <option value="cache-optimized">⚡ Cache-Optimized (Prompt Affinity)</option>
                <option value="round_robin">Round Robin</option>
                <option value="least_latency">Least Latency</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Max Retries</label>
              <input
                type="number"
                value={formRetryCount}
                onChange={(e) => setFormRetryCount(parseInt(e.target.value) || 3)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Timeout (seconds)</label>
              <input
                type="number"
                value={formTimeout}
                onChange={(e) => setFormTimeout(parseFloat(e.target.value) || 60)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          {formStrategy === "cache-optimized" && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-emerald-950/30 border border-emerald-800/40 text-xs text-emerald-300">
              <Zap size={15} className="shrink-0 text-emerald-400 mt-0.5" />
              <div className="leading-relaxed">
                <span className="font-semibold text-emerald-200">Prompt Cache Affinity (Rendezvous Hashing):</span>{" "}
                Запросы с одинаковым системным промптом или префиксом автоматически направляются к одному и тому же кандидату и API-ключу для 100% утилизации KV-кэша (Anthropic Prompt Caching, DeepSeek Context Caching, OpenAI, Gemini).
              </div>
            </div>
          )}

          {/* Profile-level Thinking Effort */}
          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <Brain size={13} className="text-purple-400" />
                Default Reasoning Effort ({t.routing.reasoningEffort})
              </label>
              <span className="text-[10px] text-slate-400 font-mono">reasoning_effort</span>
            </div>
            <div className="grid grid-cols-4 sm:grid-cols-7 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px] font-medium text-slate-300">
              {[
                { id: "inherit", label: "Inherit" },
                { id: "auto", label: "Auto" },
                { id: "low", label: "Low" },
                { id: "medium", label: "Medium" },
                { id: "high", label: "High" },
                { id: "off", label: "Off" },
                { id: "custom", label: "Custom ✏️" },
              ].map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setFormThinkingEffort(opt.id)}
                  className={`py-1 rounded text-center transition-all ${
                    formThinkingEffort === opt.id
                      ? opt.id === "off"
                        ? "bg-rose-900/70 text-rose-200 font-semibold"
                        : opt.id === "custom"
                        ? "bg-indigo-600 text-white font-semibold"
                        : "bg-purple-600 text-white font-semibold shadow-xs"
                      : "hover:bg-slate-800 text-slate-400"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {formThinkingEffort === "custom" && (
              <div className="flex items-center gap-2 pt-1">
                <span className="text-[11px] text-purple-300 font-medium shrink-0">Effort value:</span>
                <input
                  type="text"
                  value={formCustomThinking}
                  onChange={(e) => setFormCustomThinking(e.target.value)}
                  placeholder="minimal, max, xhigh or 8192"
                  className="flex-1 px-2.5 py-1 bg-slate-900 border border-purple-500/50 rounded-md text-xs text-purple-100 font-mono focus:border-purple-400 focus:outline-none"
                />
              </div>
            )}
          </div>

          {/* Profile-level Temperature */}
          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <Thermometer size={13} className="text-rose-400" />
                {t.routing.defaultTemperature}
              </label>
              <span className="text-[10px] text-slate-400 font-mono">
                {formTempPreset === "inherit"
                  ? "Inherit from request"
                  : formTempPreset === "custom"
                  ? `temp: ${formCustomTemp || "..."}`
                  : `temp: ${formTempPreset}`}
              </span>
            </div>
            <div className="grid grid-cols-4 sm:grid-cols-8 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px] font-medium text-slate-300">
              {ROUTE_TEMP_PRESETS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setFormTempPreset(opt.id)}
                  className={`py-1 rounded text-center transition-all ${
                    formTempPreset === opt.id
                      ? opt.id === "inherit"
                        ? "bg-slate-700 text-white font-semibold shadow-xs"
                        : opt.id === "custom"
                        ? "bg-indigo-600 text-white font-semibold shadow-xs"
                        : "bg-rose-600 text-white font-semibold shadow-xs"
                      : "hover:bg-slate-800 text-slate-400"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {formTempPreset === "custom" && (
              <div className="flex items-center gap-2 pt-1">
                <span className="text-[11px] text-rose-300 font-medium shrink-0">Value (0.0 - 2.0):</span>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="2"
                  value={formCustomTemp}
                  onChange={(e) => setFormCustomTemp(e.target.value)}
                  placeholder="0.7"
                  className="flex-1 px-2.5 py-1 bg-slate-900 border border-rose-500/50 rounded-md text-xs text-rose-100 font-mono focus:border-rose-400 focus:outline-none"
                />
              </div>
            )}
          </div>

          {/* Profile-level Context Window (context_length) */}
          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <Maximize2 size={13} className="text-cyan-400" />
                Context Window ({t.models.contextLength})
              </label>
              <span className="text-[10px] text-slate-400 font-mono">
                {formContextPreset === "auto"
                  ? "Auto (model default)"
                  : formContextPreset === "custom"
                  ? `${formCustomContext ? Number(formCustomContext).toLocaleString() : "..."} tokens`
                  : `${Number(formContextPreset).toLocaleString()} tokens`}
              </span>
            </div>
            <div className="grid grid-cols-5 sm:grid-cols-10 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px] font-medium text-slate-300">
              {ROUTE_CONTEXT_PRESETS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setFormContextPreset(opt.id)}
                  className={`py-1 rounded text-center transition-all ${
                    formContextPreset === opt.id
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
            {formContextPreset === "custom" && (
              <div className="flex items-center gap-2 pt-1">
                <span className="text-[11px] text-cyan-300 font-medium shrink-0">Tokens:</span>
                <input
                  type="number"
                  value={formCustomContext}
                  onChange={(e) => setFormCustomContext(e.target.value)}
                  placeholder="e.g. 128000 or 1000000"
                  className="flex-1 px-2.5 py-1 bg-slate-900 border border-cyan-500/50 rounded-md text-xs text-cyan-100 font-mono focus:border-cyan-400 focus:outline-none"
                />
              </div>
            )}
          </div>

          {/* Fallback Model Distribution */}
          <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <Shuffle size={13} className="text-amber-400" />
                Model Distribution
              </label>
              <span className="text-[10px] text-slate-400 font-mono">randomize_candidates</span>
            </div>

            {/* Randomize Candidates Toggle */}
            <label className={`flex items-start gap-2.5 p-2.5 rounded-lg border transition-all cursor-pointer ${
              formRandomizeCandidates
                ? "bg-amber-950/30 border-amber-600/50 text-amber-200 shadow-xs"
                : "bg-slate-900/60 border-slate-800 text-slate-300 hover:bg-slate-800/60"
            }`}>
              <input
                type="checkbox"
                checked={formRandomizeCandidates}
                onChange={(e) => setFormRandomizeCandidates(e.target.checked)}
                className="mt-0.5 rounded border-slate-700 text-amber-500 focus:ring-amber-500 bg-slate-900"
              />
              <div className="flex-1 text-xs">
                <div className="font-semibold flex items-center gap-1.5">
                  <span>{t.routing.randomize}</span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5 leading-snug">
                  Randomly choose the primary candidate in the fallback chain instead of a fixed priority (subsequent retries also shuffled)
                </div>
              </div>
            </label>

            {/* Built-in Key Randomization Note */}
            <div className="flex items-center gap-2 px-2.5 py-1.5 bg-emerald-950/20 border border-emerald-800/40 rounded-lg text-[11px] text-emerald-300">
              <Key size={12} className="shrink-0 text-emerald-400" />
              <span>
                <strong>Key Load Balancing:</strong> built-in by default across all router modes — requests are automatically balanced across all active keys for a provider.
              </span>
            </div>
          </div>

          {/* Add Candidate Sub-section */}
          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-200">{t.routing.addCandidate}</h4>
              <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-[11px]">
                <button
                  type="button"
                  onClick={() => setCandTargetType("model")}
                  className={`px-2.5 py-0.5 rounded font-medium transition-colors ${
                    candTargetType === "model"
                      ? "bg-indigo-600 text-white"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Provider Model
                </button>
                <button
                  type="button"
                  onClick={() => setCandTargetType("profile")}
                  className={`px-2.5 py-0.5 rounded font-medium flex items-center gap-1 transition-colors ${
                    candTargetType === "profile"
                      ? "bg-purple-600 text-white"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <GitFork size={11} />
                  Nested Profile
                </button>
              </div>
            </div>

            {candTargetType === "model" ? (
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">1. {t.common.provider}</label>
                  <select
                    value={candProviderId}
                    onChange={(e) => {
                      setCandProviderId(parseInt(e.target.value));
                      setCandCredTarget("all");
                    }}
                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
                  >
                    {providers.map((p) => {
                      const hiddenIds = getHiddenModelIds();
                      const visibleCount = models.filter(
                        (m) => m.provider_id === p.id && isModelVisible(m, hiddenIds)
                      ).length;
                      return (
                        <option key={p.id} value={p.id}>
                          {p.name} ({visibleCount} {visibleCount === 1 ? "model" : "models"})
                        </option>
                      );
                    })}
                  </select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-[10px] text-slate-400">2. Keys / Group</label>
                    <span className="text-[9px] text-amber-400 font-medium truncate max-w-[120px]" title={
                      candCredTarget === "all"
                        ? "⚡ Full Fallback"
                        : candCredTarget.startsWith("group:")
                        ? `📁 ${candCredTarget.slice(6)}`
                        : "Single Key"
                    }>
                      {candCredTarget === "all"
                        ? "⚡ Full Fallback"
                        : candCredTarget.startsWith("group:")
                        ? `📁 ${candCredTarget.slice(6)}`
                        : "Single Key"}
                    </span>
                  </div>
                  <select
                    value={candCredTarget}
                    onChange={(e) => setCandCredTarget(e.target.value)}
                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="all">⚡ All provider keys (full fallback)</option>
                    {availableGroupsForProvider.length > 0 && (
                      <optgroup label="Key Groups (Fallback by group)">
                        {availableGroupsForProvider.map((g) => (
                          <option key={`group:${g}`} value={`group:${g}`}>
                            📁 Group: {g} ({credentials.filter((c) => c.provider_id === candProviderId && c.group_name === g).length} keys)
                          </option>
                        ))}
                      </optgroup>
                    )}
                    <optgroup label="Single Keys">
                      {availableCredsForProvider.map((c) => (
                        <option key={`key:${c.id}`} value={`key:${c.id}`}>
                          🔑 {c.name} {c.group_name ? `[${c.group_name}]` : ""}
                        </option>
                      ))}
                    </optgroup>
                  </select>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-[10px] text-slate-400">3. {t.common.model}</label>
                    <span className="text-[10px] text-indigo-400">
                      {availableModelsForProvider.length > 0
                        ? `${availableModelsForProvider.length} ${availableModelsForProvider.length === 1 ? "visible" : "visible"}`
                        : "none visible"}
                    </span>
                  </div>
                  {availableModelsForProvider.length === 0 ? (
                    <div className="w-full px-2 py-1 bg-slate-900/60 border border-slate-800 rounded text-amber-400/90 text-xs font-sans">
                      No visible models
                    </div>
                  ) : (
                    <select
                      value={candModelId}
                      onChange={(e) => setCandModelId(parseInt(e.target.value))}
                      className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
                    >
                      {availableModelsForProvider.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.provider_model_id} {m.display_name && m.display_name !== m.provider_model_id ? `(${m.display_name})` : ""}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
            ) : (
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">Select routing profile to embed:</label>
                {availableSubProfiles.length === 0 ? (
                  <p className="text-xs text-amber-400 py-1">
                    No other available profiles to embed. Create another profile first.
                  </p>
                ) : (
                  <select
                    value={candTargetProfileId ?? (availableSubProfiles[0]?.id || "")}
                    onChange={(e) => setCandTargetProfileId(parseInt(e.target.value))}
                    className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-purple-500 focus:outline-none font-mono"
                  >
                    {availableSubProfiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} (route/{p.slug}) • {p.candidates.length} candidates
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {/* Candidate-specific thinking effort */}
            <div className="pt-2 border-t border-slate-800/80 space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-medium text-slate-300 flex items-center gap-1">
                  <Brain size={12} className="text-purple-400" />
                  Candidate reasoning_effort ({t.routing.reasoningEffort}):
                </label>
                <span className="text-[10px] text-slate-400 font-mono">
                  {candThinkingEffort === "inherit"
                    ? "Inherit"
                    : candThinkingEffort === "custom"
                    ? (candCustomThinking || "Custom")
                    : candThinkingEffort.toUpperCase()}
                </span>
              </div>
              <div className="grid grid-cols-4 sm:grid-cols-7 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px]">
                {[
                  { id: "inherit", label: "Inherit" },
                  { id: "auto", label: "Auto" },
                  { id: "low", label: "Low" },
                  { id: "medium", label: "Medium" },
                  { id: "high", label: "High" },
                  { id: "off", label: "Off" },
                  { id: "custom", label: "Custom ✏️" },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setCandThinkingEffort(opt.id)}
                    className={`py-1 rounded text-center transition-colors ${
                      candThinkingEffort === opt.id
                        ? opt.id === "off"
                          ? "bg-rose-900/70 text-rose-200 font-semibold"
                          : opt.id === "custom"
                          ? "bg-indigo-600 text-white font-semibold"
                          : "bg-purple-600 text-white font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              {candThinkingEffort === "custom" && (
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-[10px] text-purple-300 font-medium shrink-0">Effort value:</span>
                  <input
                    type="text"
                    value={candCustomThinking}
                    onChange={(e) => setCandCustomThinking(e.target.value)}
                    placeholder="minimal, max, xhigh or 8192"
                    className="flex-1 px-2 py-0.5 bg-slate-900 border border-purple-500/50 rounded text-[11px] text-purple-100 font-mono focus:border-purple-400 focus:outline-none"
                  />
                </div>
              )}
            </div>

            {/* Candidate-specific temperature override */}
            <div className="pt-2 border-t border-slate-800/80 space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-medium text-slate-300 flex items-center gap-1">
                  <Thermometer size={12} className="text-rose-400" />
                  Candidate temperature ({t.routing.tempOverride}):
                </label>
                <span className="text-[10px] text-slate-400 font-mono">
                  {candTempPreset === "inherit"
                    ? "Inherit"
                    : candTempPreset === "custom"
                    ? `temp: ${candCustomTemp || "Custom"}`
                    : `temp: ${candTempPreset}`}
                </span>
              </div>
              <div className="grid grid-cols-4 sm:grid-cols-8 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px]">
                {ROUTE_TEMP_PRESETS.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setCandTempPreset(opt.id)}
                    className={`py-1 rounded text-center transition-colors ${
                      candTempPreset === opt.id
                        ? opt.id === "inherit"
                          ? "bg-slate-700 text-white font-semibold"
                          : opt.id === "custom"
                          ? "bg-indigo-600 text-white font-semibold"
                          : "bg-rose-600 text-white font-semibold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {opt.id === "inherit" ? "Inherit" : opt.label}
                  </button>
                ))}
              </div>
              {candTempPreset === "custom" && (
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-[10px] text-rose-300 font-medium shrink-0">Value (0.0 - 2.0):</span>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="2"
                    value={candCustomTemp}
                    onChange={(e) => setCandCustomTemp(e.target.value)}
                    placeholder="0.7"
                    className="flex-1 px-2 py-0.5 bg-slate-900 border border-rose-500/50 rounded text-[11px] text-rose-100 font-mono focus:border-rose-400 focus:outline-none"
                  />
                </div>
              )}
            </div>

            <button
              type="button"
              disabled={
                (candTargetType === "profile" && availableSubProfiles.length === 0) ||
                (candTargetType === "model" && availableModelsForProvider.length === 0)
              }
              onClick={addCandidate}
              className={`px-3 py-1 text-xs font-medium rounded border transition-colors ${
                candTargetType === "profile"
                  ? "bg-purple-900/60 hover:bg-purple-800/80 text-purple-200 border-purple-700/60 cursor-pointer"
                  : availableModelsForProvider.length === 0
                  ? "bg-slate-800/50 text-slate-500 border-slate-800 cursor-not-allowed"
                  : "bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 cursor-pointer"
              }`}
            >
              + {t.routing.addCandidate}
            </button>
          </div>

          {/* Candidates Order List */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300">
              {t.routing.priorityChain} ({formCandidates.length})
            </label>
            {formCandidates.map((c, idx) => {
              if (c.candidate_type === "profile") {
                const targetProf = profiles.find((p) => p.id === c.target_profile_id);
                return (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 bg-slate-950 border border-purple-900/50 rounded-lg text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-purple-900/60 text-purple-200 text-[10px] font-mono flex items-center justify-center font-bold">
                        #{idx + 1}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-950 text-purple-300 border border-purple-800/60 flex items-center gap-1">
                        <GitFork size={10} />
                        Nested Profile
                      </span>
                      <span className="font-semibold text-slate-100">{targetProf?.name || `Profile #${c.target_profile_id}`}</span>
                      <span className="font-mono text-purple-300">route/{targetProf?.slug}</span>
                      {c.thinking_effort ? (
                        <span className="text-[10px] bg-purple-900/60 text-purple-200 border border-purple-700/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                          <Brain size={10} /> CoT: {c.thinking_effort}
                        </span>
                      ) : null}
                      {c.temperature !== null && c.temperature !== undefined ? (
                        <span className="text-[10px] bg-rose-950/60 text-rose-300 border border-rose-800/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                          <Thermometer size={10} /> temp: {c.temperature}
                        </span>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        disabled={idx === 0}
                        onClick={() => moveCandidate(idx, "up")}
                        className="p-1 text-slate-400 hover:text-slate-200 disabled:opacity-30"
                      >
                        <ArrowUp size={13} />
                      </button>
                      <button
                        type="button"
                        disabled={idx === formCandidates.length - 1}
                        onClick={() => moveCandidate(idx, "down")}
                        className="p-1 text-slate-400 hover:text-slate-200 disabled:opacity-30"
                      >
                        <ArrowDown size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeCandidate(idx)}
                        className="p-1 text-slate-400 hover:text-rose-400"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                );
              }

              const pObj = providers.find((p) => p.id === c.provider_id);
              const mObj = models.find((m) => m.id === c.model_id);
              const credObj = credentials.find((cr) => cr.id === c.credential_id);
              return (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-slate-800 text-slate-300 text-[10px] font-mono flex items-center justify-center font-bold">
                      #{idx + 1}
                    </span>
                    <span className="font-semibold text-slate-200">{pObj?.name}</span>
                    <span className="text-slate-400">→</span>
                    <span className="font-mono text-indigo-300">{mObj?.provider_model_id || "Model"}</span>
                    {mObj && (mObj.is_visible === false || !mObj.available) && (
                      <span className="text-[10px] text-amber-400 font-sans italic bg-amber-950/40 border border-amber-800/40 px-1 py-0.5 rounded">
                        (hidden)
                      </span>
                    )}
                    {c.credential_id ? (
                      <span className="text-slate-400 text-[10px]">({credObj?.name || "Key"})</span>
                    ) : c.credential_group ? (
                      <span className="text-blue-300 font-medium text-[10px] flex items-center gap-1 bg-blue-950/50 border border-blue-800/50 px-1.5 py-0.5 rounded">
                        <Folder size={10} className="text-blue-400" /> Group: {c.credential_group} (Fallback)
                      </span>
                    ) : (
                      <span className="text-amber-300 font-medium text-[10px] flex items-center gap-1 bg-amber-950/50 border border-amber-800/50 px-1.5 py-0.5 rounded">
                        <Zap size={10} className="text-amber-400" /> All keys (Fallback)
                      </span>
                    )}
                    {c.thinking_effort ? (
                      <span className="text-[10px] bg-purple-900/60 text-purple-200 border border-purple-700/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                        <Brain size={10} /> CoT: {c.thinking_effort}
                      </span>
                    ) : null}
                    {c.temperature !== null && c.temperature !== undefined ? (
                      <span className="text-[10px] bg-rose-950/60 text-rose-300 border border-rose-800/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                        <Thermometer size={10} /> temp: {c.temperature}
                      </span>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={idx === 0}
                      onClick={() => moveCandidate(idx, "up")}
                      className="p-1 text-slate-400 hover:text-slate-200 disabled:opacity-30"
                    >
                      <ArrowUp size={13} />
                    </button>
                    <button
                      type="button"
                      disabled={idx === formCandidates.length - 1}
                      onClick={() => moveCandidate(idx, "down")}
                      className="p-1 text-slate-400 hover:text-slate-200 disabled:opacity-30"
                    >
                      <ArrowDown size={13} />
                    </button>
                    <button
                      type="button"
                      onClick={() => removeCandidate(idx)}
                      className="p-1 text-slate-400 hover:text-rose-400"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-white/[0.06]">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="btn-press px-4 py-2 bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 rounded-xl text-xs font-medium border border-white/[0.06] transition-colors cursor-pointer"
            >
              {t.common.cancel}
            </button>
            <button
              type="submit"
              className="btn-press px-5 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-indigo-500/20 border border-white/10 transition-all cursor-pointer"
            >
              {t.common.save}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
