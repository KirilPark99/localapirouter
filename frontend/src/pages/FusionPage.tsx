import React, { useEffect, useState, useMemo } from "react";
import { Plus, Trash2, Edit2, Merge, Sparkles, Scale, CheckCircle2, GitFork, Key, Cpu, Layers, Play, Brain, Thermometer, Folder, ArrowUp, ArrowDown, Zap } from "lucide-react";
import { apiRequest } from "../api/client";
import { FusionProfile, Provider, Credential, DiscoveredModel, RoutingProfile, FusionParticipant } from "../types";
import { Modal } from "../components/Modal";
import { ProfileContextWindow, contextPresetFor } from "../components/ProfileContextWindow";
import { getHiddenModelIds, isModelVisible } from "../utils/models";
import { useI18n } from "../i18n/context";

export const FUSION_TEMP_PRESETS = [
  { id: "inherit", label: "Inherit", value: null },
  { id: "0.0", label: "0.0", value: 0.0, desc: "Strict / Code" },
  { id: "0.2", label: "0.2", value: 0.2, desc: "Precise" },
  { id: "0.5", label: "0.5", value: 0.5, desc: "Balanced" },
  { id: "0.7", label: "0.7", value: 0.7, desc: "Standard" },
  { id: "1.0", label: "1.0", value: 1.0, desc: "Creative" },
  { id: "1.5", label: "1.5", value: 1.5, desc: "Experimental" },
  { id: "custom", label: "Custom ✏️", value: null },
];

export const FusionPage: React.FC = () => {
  const { t } = useI18n();
  const [fusions, setFusions] = useState<FusionProfile[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [models, setModels] = useState<DiscoveredModel[]>([]);
  const [routingProfiles, setRoutingProfiles] = useState<RoutingProfile[]>([]);
  const [loading, setLoading] = useState(true);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingFusion, setEditingFusion] = useState<FusionProfile | null>(null);

  const [formName, setFormName] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formStrategy, setFormStrategy] = useState<"synthesize" | "best_of_n" | "consensus" | "critique_and_rewrite">("synthesize");
  const [formTempPreset, setFormTempPreset] = useState<string>("inherit");
  const [formCustomTemp, setFormCustomTemp] = useState<string>("");
  const [formContextPreset, setFormContextPreset] = useState("auto");
  const [formCustomContext, setFormCustomContext] = useState("");
  
  // Judge state
  const [formJudgeType, setFormJudgeType] = useState<"model" | "profile">("model");
  const [formJudgeRoutingProfileId, setFormJudgeRoutingProfileId] = useState<number | undefined>(undefined);
  const [formJudgeProviderId, setFormJudgeProviderId] = useState<number>(1);
  const [formJudgeCredTarget, setFormJudgeCredTarget] = useState<string>("all");
  const [formJudgeModelId, setFormJudgeModelId] = useState<number>(1);
  const [formJudgeThinkingEffort, setFormJudgeThinkingEffort] = useState<string>("inherit");
  const [formJudgeCustomThinking, setFormJudgeCustomThinking] = useState<string>("");
  const [formJudgeTempPreset, setFormJudgeTempPreset] = useState<string>("inherit");
  const [formJudgeCustomTemp, setFormJudgeCustomTemp] = useState<string>("");
  
  const [formMinSuccess, setFormMinSuccess] = useState(2);
  const [formTimeout, setFormTimeout] = useState(120.0);
  const [formSystemPrompt, setFormSystemPrompt] = useState("");

  const [formParticipants, setFormParticipants] = useState<
    {
      participant_type: "model" | "profile";
      target_profile_id?: number | null;
      provider_id?: number | null;
      credential_id?: number | null;
      credential_group?: string | null;
      model_id?: number | null;
      label: string;
      thinking_effort?: string | null;
      temperature?: number | null;
      is_active: boolean;
    }[]
  >([]);

  // Participant adder state
  const [partType, setPartType] = useState<"model" | "profile">("model");
  const [partTargetProfileId, setPartTargetProfileId] = useState<number>(1);
  const [partProviderId, setPartProviderId] = useState<number>(1);
  const [partCredTarget, setPartCredTarget] = useState<string>("all");
  const [partModelId, setPartModelId] = useState<number>(1);
  const [partLabel, setPartLabel] = useState("");
  const [partThinkingEffort, setPartThinkingEffort] = useState<string>("inherit");
  const [partCustomThinking, setPartCustomThinking] = useState<string>("");
  const [partTempPreset, setPartTempPreset] = useState<string>("inherit");
  const [partCustomTemp, setPartCustomTemp] = useState<string>("");

  const loadData = async () => {
    setLoading(true);
    try {
      const [f, p, c, m, r] = await Promise.all([
        apiRequest<FusionProfile[]>("/api/admin/fusion"),
        apiRequest<Provider[]>("/api/admin/providers"),
        apiRequest<Credential[]>("/api/admin/credentials"),
        apiRequest<DiscoveredModel[]>("/api/admin/models"),
        apiRequest<RoutingProfile[]>("/api/admin/routes"),
      ]);
      setFusions(f || []);
      setProviders(p || []);
      setCredentials(c || []);
      setModels(m || []);
      setRoutingProfiles(r || []);

      if (p && p.length > 0) {
        setFormJudgeProviderId(p[0].id);
        setPartProviderId(p[0].id);
      }
      if (m && m.length > 0) {
        setFormJudgeModelId(m[0].id);
        setPartModelId(m[0].id);
      }
      if (r && r.length > 0) {
        setFormJudgeRoutingProfileId(r[0].id);
        setPartTargetProfileId(r[0].id);
      }
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
    setEditingFusion(null);
    setFormName("");
    setFormSlug("");
    setFormStrategy("synthesize");
    setFormContextPreset("auto");
    setFormCustomContext("");
    setFormTempPreset("inherit");
    setFormCustomTemp("");
    setFormJudgeType("model");
    if (routingProfiles.length > 0) setFormJudgeRoutingProfileId(routingProfiles[0].id);
    if (providers.length > 0) setFormJudgeProviderId(providers[0].id);
    if (models.length > 0) setFormJudgeModelId(models[0].id);
    setFormJudgeCredTarget("all");
    setFormJudgeThinkingEffort("inherit");
    setFormJudgeCustomThinking("");
    setFormJudgeTempPreset("inherit");
    setFormJudgeCustomTemp("");
    setFormMinSuccess(2);
    setFormTimeout(120.0);
    setFormSystemPrompt("");
    setFormParticipants([]);
    setPartType("model");
    setPartCredTarget("all");
    setPartThinkingEffort("inherit");
    setPartCustomThinking("");
    setPartTempPreset("inherit");
    setPartCustomTemp("");
    setIsModalOpen(true);
  };

  const openEditModal = (f: FusionProfile) => {
    setEditingFusion(f);
    setFormName(f.name);
    setFormSlug(f.slug);
    setFormStrategy(f.strategy);
    setFormContextPreset(contextPresetFor(f.context_length));
    setFormCustomContext(f.context_length ? String(f.context_length) : "");

    // Profile temperature
    if (f.temperature !== null && f.temperature !== undefined) {
      const match = FUSION_TEMP_PRESETS.find(
        (pr) => pr.value !== null && Math.abs(pr.value - f.temperature!) < 0.001
      );
      if (match) {
        setFormTempPreset(match.id);
        setFormCustomTemp("");
      } else {
        setFormTempPreset("custom");
        setFormCustomTemp(String(f.temperature));
      }
    } else {
      setFormTempPreset("inherit");
      setFormCustomTemp("");
    }

    setFormJudgeType(f.judge_type || "model");
    setFormJudgeRoutingProfileId(f.judge_routing_profile_id || (routingProfiles[0]?.id ?? undefined));
    setFormJudgeProviderId(f.judge_provider_id || (providers[0]?.id ?? 1));

    // Judge credential target
    if (f.judge_credential_id) {
      setFormJudgeCredTarget(`key:${f.judge_credential_id}`);
    } else if (f.judge_credential_group) {
      setFormJudgeCredTarget(`group:${f.judge_credential_group}`);
    } else {
      setFormJudgeCredTarget("all");
    }

    setFormJudgeModelId(f.judge_model_id || (models[0]?.id ?? 1));

    // Judge thinking effort
    if (f.judge_thinking_effort) {
      if (["auto", "low", "medium", "high", "off"].includes(f.judge_thinking_effort)) {
        setFormJudgeThinkingEffort(f.judge_thinking_effort);
        setFormJudgeCustomThinking("");
      } else {
        setFormJudgeThinkingEffort("custom");
        setFormJudgeCustomThinking(f.judge_thinking_effort);
      }
    } else {
      setFormJudgeThinkingEffort("inherit");
      setFormJudgeCustomThinking("");
    }

    // Judge temperature
    if (f.judge_temperature !== null && f.judge_temperature !== undefined) {
      const match = FUSION_TEMP_PRESETS.find(
        (pr) => pr.value !== null && Math.abs(pr.value - f.judge_temperature!) < 0.001
      );
      if (match) {
        setFormJudgeTempPreset(match.id);
        setFormJudgeCustomTemp("");
      } else {
        setFormJudgeTempPreset("custom");
        setFormJudgeCustomTemp(String(f.judge_temperature));
      }
    } else {
      setFormJudgeTempPreset("inherit");
      setFormJudgeCustomTemp("");
    }

    setFormMinSuccess(f.min_successful_candidates);
    setFormTimeout(f.timeout_seconds);
    setFormSystemPrompt(f.system_prompt || "");
    setFormParticipants(
      f.participants.map((p) => ({
        participant_type: p.participant_type || (p.target_profile_id ? "profile" : "model"),
        target_profile_id: p.target_profile_id || null,
        provider_id: p.provider_id || null,
        credential_id: p.credential_id || null,
        credential_group: p.credential_group || null,
        model_id: p.model_id || null,
        label: p.label,
        thinking_effort: p.thinking_effort || null,
        temperature: p.temperature !== undefined ? p.temperature : null,
        is_active: p.is_active,
      }))
    );

    setPartType("model");
    setPartCredTarget("all");
    setPartThinkingEffort("inherit");
    setPartCustomThinking("");
    setPartTempPreset("inherit");
    setPartCustomTemp("");
    setIsModalOpen(true);
  };

  function chr(code: number) {
    return String.fromCharCode(code);
  }

  const addParticipant = () => {
    const effCandidateThinking =
      partThinkingEffort === "custom"
        ? (partCustomThinking.trim() || "4096")
        : partThinkingEffort === "inherit"
        ? null
        : partThinkingEffort;

    let candResolvedTemp: number | null = null;
    if (partTempPreset === "custom") {
      const parsed = parseFloat(partCustomTemp.trim());
      if (!isNaN(parsed)) candResolvedTemp = Math.min(Math.max(parsed, 0), 2.0);
    } else if (partTempPreset !== "inherit") {
      const parsed = parseFloat(partTempPreset);
      if (!isNaN(parsed)) candResolvedTemp = parsed;
    }

    if (partType === "profile") {
      if (!partTargetProfileId) return;
      const targetRoute = routingProfiles.find((r) => r.id === partTargetProfileId);
      const label = partLabel || (targetRoute ? `route/${targetRoute.slug}` : `Candidate ${chr(65 + formParticipants.length)}`);
      setFormParticipants([
        ...formParticipants,
        {
          participant_type: "profile",
          target_profile_id: partTargetProfileId,
          provider_id: null,
          credential_id: null,
          credential_group: null,
          model_id: null,
          label,
          thinking_effort: effCandidateThinking,
          temperature: candResolvedTemp,
          is_active: true,
        },
      ]);
    } else {
      if (!partModelId) return;
      let credId: number | null = null;
      let credGroup: string | null = null;
      if (partCredTarget.startsWith("key:")) {
        credId = parseInt(partCredTarget.slice(4));
      } else if (partCredTarget.startsWith("group:")) {
        credGroup = partCredTarget.slice(6);
      }
      const label = partLabel || `Candidate ${chr(65 + formParticipants.length)}`;
      setFormParticipants([
        ...formParticipants,
        {
          participant_type: "model",
          target_profile_id: null,
          provider_id: partProviderId,
          credential_id: credId,
          credential_group: credGroup,
          model_id: partModelId,
          label,
          thinking_effort: effCandidateThinking,
          temperature: candResolvedTemp,
          is_active: true,
        },
      ]);
    }
    setPartLabel("");
  };

  const removeParticipant = (index: number) => {
    setFormParticipants(formParticipants.filter((_, idx) => idx !== index));
  };

  const moveParticipant = (index: number, direction: "up" | "down") => {
    const newIdx = direction === "up" ? index - 1 : index + 1;
    if (newIdx < 0 || newIdx >= formParticipants.length) return;
    const items = [...formParticipants];
    const [moved] = items.splice(index, 1);
    items.splice(newIdx, 0, moved);
    setFormParticipants(items);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const isJudgeProfile = formJudgeType === "profile";
      let effJudgeCredId: number | null = null;
      let effJudgeCredGroup: string | null = null;
      if (!isJudgeProfile) {
        if (formJudgeCredTarget.startsWith("key:")) {
          effJudgeCredId = parseInt(formJudgeCredTarget.slice(4));
        } else if (formJudgeCredTarget.startsWith("group:")) {
          effJudgeCredGroup = formJudgeCredTarget.slice(6);
        }
      }

      const effJudgeThinking =
        formJudgeThinkingEffort === "custom"
          ? (formJudgeCustomThinking.trim() || "4096")
          : formJudgeThinkingEffort === "inherit"
          ? null
          : formJudgeThinkingEffort;

      let effJudgeTemp: number | null = null;
      if (formJudgeTempPreset === "custom") {
        const parsed = parseFloat(formJudgeCustomTemp.trim());
        if (!isNaN(parsed)) effJudgeTemp = Math.min(Math.max(parsed, 0), 2.0);
      } else if (formJudgeTempPreset !== "inherit") {
        const parsed = parseFloat(formJudgeTempPreset);
        if (!isNaN(parsed)) effJudgeTemp = parsed;
      }

      let effProfileTemp: number | null = null;
      if (formTempPreset === "custom") {
        const parsed = parseFloat(formCustomTemp.trim());
        if (!isNaN(parsed)) effProfileTemp = Math.min(Math.max(parsed, 0), 2.0);
      } else if (formTempPreset !== "inherit") {
        const parsed = parseFloat(formTempPreset);
        if (!isNaN(parsed)) effProfileTemp = parsed;
      }

      const payload = {
        name: formName,
        slug: formSlug || formName.toLowerCase().replace(/[^a-z0-9]/g, "-"),
        strategy: formStrategy,
        judge_type: formJudgeType,
        judge_routing_profile_id: isJudgeProfile ? formJudgeRoutingProfileId : null,
        judge_provider_id: !isJudgeProfile ? formJudgeProviderId : null,
        judge_credential_id: effJudgeCredId,
        judge_credential_group: effJudgeCredGroup,
        judge_model_id: !isJudgeProfile ? formJudgeModelId : null,
        judge_thinking_effort: effJudgeThinking,
        judge_temperature: effJudgeTemp,
        temperature: effProfileTemp,
        context_length: formContextPreset === "auto" ? null : Number(formContextPreset === "custom" ? formCustomContext : formContextPreset),
        min_successful_candidates: formMinSuccess,
        max_parallelism: 5,
        timeout_seconds: formTimeout,
        system_prompt: formSystemPrompt || null,
        participants: formParticipants.map((p, idx) => ({
          participant_type: p.participant_type,
          target_profile_id: p.participant_type === "profile" ? p.target_profile_id : null,
          provider_id: p.participant_type === "model" ? p.provider_id : null,
          credential_id: p.participant_type === "model" ? (p.credential_id || null) : null,
          credential_group: p.participant_type === "model" ? (p.credential_group || null) : null,
          model_id: p.participant_type === "model" ? p.model_id : null,
          label: p.label,
          thinking_effort: p.thinking_effort || null,
          temperature: p.temperature !== undefined ? p.temperature : null,
          priority_order: idx,
          is_active: p.is_active,
        })),
      };

      if (editingFusion) {
        await apiRequest(`/api/admin/fusion/${editingFusion.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiRequest("/api/admin/fusion", {
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
    if (!confirm(`Delete fusion profile "${name}"?`)) return;
    try {
      await apiRequest(`/api/admin/fusion/${id}`, { method: "DELETE" });
      loadData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // Models filtered for judge
  const judgeModels = useMemo(() => {
    const hiddenIds = getHiddenModelIds();
    const filtered = models.filter(
      (m) => m.provider_id === formJudgeProviderId && isModelVisible(m, hiddenIds)
    );
    const map = new Map<string, DiscoveredModel>();
    filtered.forEach((m) => {
      if (!map.has(m.provider_model_id)) {
        map.set(m.provider_model_id, m);
      }
    });
    return Array.from(map.values()).sort((a, b) => a.provider_model_id.localeCompare(b.provider_model_id));
  }, [models, formJudgeProviderId]);

  const judgeCreds = credentials.filter((c) => c.provider_id === formJudgeProviderId);
  const judgeGroups = useMemo(() => {
    const groups = new Set<string>();
    credentials
      .filter((c) => c.provider_id === formJudgeProviderId && c.group_name && c.group_name.trim())
      .forEach((c) => groups.add(c.group_name!.trim()));
    return Array.from(groups).sort();
  }, [credentials, formJudgeProviderId]);

  // Models filtered for participant
  const partModels = useMemo(() => {
    const hiddenIds = getHiddenModelIds();
    const filtered = models.filter(
      (m) => m.provider_id === partProviderId && isModelVisible(m, hiddenIds)
    );
    const map = new Map<string, DiscoveredModel>();
    filtered.forEach((m) => {
      if (!map.has(m.provider_model_id)) {
        map.set(m.provider_model_id, m);
      }
    });
    return Array.from(map.values()).sort((a, b) => a.provider_model_id.localeCompare(b.provider_model_id));
  }, [models, partProviderId]);

  const partCreds = credentials.filter((c) => c.provider_id === partProviderId);
  const partGroups = useMemo(() => {
    const groups = new Set<string>();
    credentials
      .filter((c) => c.provider_id === partProviderId && c.group_name && c.group_name.trim())
      .forEach((c) => groups.add(c.group_name!.trim()));
    return Array.from(groups).sort();
  }, [credentials, partProviderId]);

  useEffect(() => {
    if (judgeModels.length > 0 && !judgeModels.some((m) => m.id === formJudgeModelId)) {
      setFormJudgeModelId(judgeModels[0].id);
    }
  }, [judgeModels, formJudgeModelId]);

  useEffect(() => {
    if (partType === "model" && !partModels.some((m) => m.id === partModelId)) {
      setPartModelId(partModels[0]?.id ?? 0);
    }
  }, [partModels, partModelId, partType]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <Merge size={20} className="text-amber-400" />
            {t.fusion.title}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {t.fusion.subtitle}
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="btn-press flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-amber-500/20 border border-white/10 cursor-pointer"
        >
          <Plus size={15} />
          <span>{t.fusion.createFusion}</span>
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {fusions.length === 0 ? (
          <div className="p-12 text-center glass-panel card-specular rounded-2xl border border-white/[0.06] text-xs text-slate-400">
            No ensemble profiles created yet. Create an ensemble (e.g. fusion/powerful-coding) combining Gemini, Claude and GPT!
          </div>
        ) : (
          fusions.map((f) => (
            <div key={f.id} className="glass-card card-specular rounded-2xl border border-white/[0.07] p-5 space-y-4 hover:border-white/[0.12] transition-all duration-200">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-300 shadow-sm shrink-0">
                    <Merge size={17} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-slate-100 text-sm tracking-tight">{f.name}</span>
                      <span className="font-mono text-xs text-amber-300 bg-amber-950/60 px-2 py-0.5 rounded-lg border border-amber-800/60 shadow-xs">
                        fusion/{f.slug}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] font-mono text-slate-400 bg-slate-950/40 px-2.5 py-1 rounded-lg border border-white/[0.04]">
                    Strategy: <span className="text-slate-200 uppercase font-medium">{f.strategy}</span> • Min. success: {f.min_successful_candidates} of {f.participants.length}
                  </span>
                  {f.temperature !== null && f.temperature !== undefined && (
                    <span className="text-[11px] font-mono text-amber-300 bg-amber-950/60 px-2.5 py-1 rounded-lg border border-amber-800/60 flex items-center gap-1 shadow-xs">
                      <Thermometer size={12} className="text-amber-400" />
                      temp: {f.temperature}
                    </span>
                  )}
                  <a
                    href={`/playground?model=fusion/${encodeURIComponent(f.slug)}`}
                    className="btn-press flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-purple-200 hover:text-white bg-purple-950/70 hover:bg-purple-900/90 border border-purple-800/60 rounded-xl transition-all shadow-xs"
                    title="Open and test in Playground"
                  >
                    <Play size={11} className="fill-current" />
                    <span>{t.common.test}</span>
                  </a>
                  <button
                    onClick={() => openEditModal(f)}
                    className="btn-press p-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] rounded-lg border border-white/[0.04] transition-colors cursor-pointer"
                    title={t.common.edit}
                  >
                    <Edit2 size={14} />
                  </button>
                  <button
                    onClick={() => handleDelete(f.id, f.name)}
                    className="btn-press p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg border border-white/[0.04] transition-colors cursor-pointer"
                    title={t.common.delete}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {/* Ensemble diagram visualizer */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {/* Participants */}
                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
                    <Layers size={13} className="text-indigo-400" />
                    {t.fusion.participants} ({f.participants.length})
                  </div>
                  {f.participants.map((p) => {
                    const isProfile = (p.participant_type === "profile") || !!p.target_profile_id;
                    return (
                      <div
                        key={p.id}
                        className="flex items-center justify-between p-2.5 bg-slate-950/60 border border-white/[0.05] hover:border-white/[0.1] rounded-xl text-xs transition-all flex-wrap gap-2"
                      >
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="px-2 py-0.5 rounded-lg bg-indigo-950/80 text-indigo-300 font-mono text-[10px] border border-indigo-800/50 shadow-xs">
                            {p.label}
                          </span>
                          {isProfile ? (
                            <div className="flex items-center gap-1.5">
                              <GitFork size={12} className="text-purple-400" />
                              <span className="font-semibold text-purple-200">{p.target_profile_name || p.model_name}</span>
                              <span className="text-slate-500 font-mono text-[11px]">({p.canonical_slug})</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5">
                              <Cpu size={12} className="text-sky-400" />
                              <span className="font-semibold text-slate-200">{p.provider_name}</span>
                              <span className="text-slate-500 font-mono text-[11px]">({p.canonical_slug})</span>
                            </div>
                          )}

                          {p.thinking_effort ? (
                            <span className="text-[10px] bg-purple-900/60 text-purple-200 border border-purple-700/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                              <Brain size={10} className="text-purple-300" />
                              CoT: {p.thinking_effort}
                            </span>
                          ) : null}

                          {p.temperature !== null && p.temperature !== undefined ? (
                            <span className="text-[10px] bg-amber-950/60 text-amber-300 border border-amber-800/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                              <Thermometer size={10} className="text-amber-400" />
                              temp: {p.temperature}
                            </span>
                          ) : null}
                        </div>

                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-lg border flex items-center gap-1 ${
                          isProfile
                            ? "bg-purple-950/70 text-purple-300 border-purple-800/40"
                            : p.credential_group
                            ? "bg-blue-950/70 text-blue-300 border-blue-800/40"
                            : p.credential_id
                            ? "bg-slate-900/90 text-slate-400 border-white/[0.05]"
                            : "bg-emerald-950/70 text-emerald-300 border-emerald-800/40"
                        }`}>
                          {isProfile ? (
                            "Fallback Route Chain"
                          ) : p.credential_group ? (
                            <>
                              <Folder size={10} className="text-blue-400" />
                              Group: {p.credential_group}
                            </>
                          ) : p.credential_name ? (
                            <>
                              <Key size={10} className="text-slate-400" />
                              {p.credential_name}
                            </>
                          ) : (
                            <>
                              <Zap size={10} className="text-emerald-400" />
                              All keys (auto-balance)
                            </>
                          )}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* Judge */}
                <div className="space-y-2">
                  <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider font-mono flex items-center gap-1.5">
                    <Scale size={13} className="text-amber-400" />
                    {t.fusion.judge} (Judge)
                  </div>
                  <div className="p-3 bg-amber-950/15 border border-amber-500/20 rounded-xl text-xs space-y-2 shadow-xs">
                    {f.judge_type === "profile" ? (
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-1.5">
                          <GitFork size={13} className="text-purple-400" />
                          <span className="font-semibold text-purple-200">{f.judge_routing_profile_name || f.judge_model_name}</span>
                        </div>
                        <span className="font-mono text-purple-300 text-[11px] bg-purple-950/60 px-2 py-0.5 rounded-lg border border-purple-800/50">
                          route/{f.judge_routing_profile_slug || f.judge_model_name}
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <span className="font-semibold text-slate-100">{f.judge_provider_name}</span>
                        <span className="font-mono text-amber-300 text-[11px] bg-amber-950/50 px-2 py-0.5 rounded-lg border border-amber-800/50">{f.judge_model_name}</span>
                      </div>
                    )}

                    <div className="flex items-center gap-2 flex-wrap">
                      {f.judge_thinking_effort ? (
                        <span className="text-[10px] bg-purple-900/60 text-purple-200 border border-purple-700/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                          <Brain size={10} className="text-purple-300" />
                          Judge CoT: {f.judge_thinking_effort}
                        </span>
                      ) : null}
                      {f.judge_temperature !== null && f.judge_temperature !== undefined ? (
                        <span className="text-[10px] bg-amber-950/60 text-amber-300 border border-amber-800/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                          <Thermometer size={10} className="text-amber-400" />
                          Judge temp: {f.judge_temperature}
                        </span>
                      ) : null}
                    </div>

                    <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1 border-t border-amber-500/15">
                      <span>
                        Strategy: <span className="text-indigo-300 font-mono font-medium">{f.strategy}</span>
                      </span>
                      <span className="text-slate-400 text-[10px] font-mono flex items-center gap-1">
                        Key:{" "}
                        {f.judge_type === "profile"
                          ? "Auto (Route)"
                          : f.judge_credential_group
                          ? `📁 Group: ${f.judge_credential_group}`
                          : (f.judge_credential_name || "⚡ All keys (auto-balance)")}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modal: Create/Edit Fusion Profile */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingFusion ? `Edit Fusion: fusion/${editingFusion.slug}` : t.fusion.createFusion}
        maxWidth="2xl"
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">{t.fusion.fusionName}</label>
              <input
                type="text"
                required
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="e.g. Powerful Coding"
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">{t.common.slug}</label>
              <input
                type="text"
                value={formSlug}
                onChange={(e) => setFormSlug(e.target.value)}
                placeholder="powerful-coding"
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">{t.fusion.strategy}</label>
            <select
              value={formStrategy}
              onChange={(e) => setFormStrategy(e.target.value as any)}
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
            >
              <option value="synthesize">Synthesize (Judge synthesizes the strongest parts of all responses)</option>
              <option value="best_of_n">Best of N (Judge selects the single best candidate response)</option>
              <option value="consensus">Consensus (Judge builds consensus and reconciles differences)</option>
              <option value="critique_and_rewrite">Critique & Rewrite (Judge critiques flaws and writes optimal response)</option>
            </select>
          </div>

          <ProfileContextWindow preset={formContextPreset} customValue={formCustomContext}
            onPresetChange={setFormContextPreset} onCustomChange={setFormCustomContext} />

          {/* Profile Default Temperature */}
          <div className="p-3 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Thermometer size={14} className="text-amber-400" />
                {t.routing.defaultTemperature}
              </label>
              <span className="text-[10px] font-mono text-amber-400">
                {formTempPreset === "inherit"
                  ? "Client request"
                  : formTempPreset === "custom"
                  ? (formCustomTemp ? `${formCustomTemp}` : "custom")
                  : formTempPreset}
              </span>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {FUSION_TEMP_PRESETS.map((pr) => (
                <button
                  key={pr.id}
                  type="button"
                  onClick={() => setFormTempPreset(pr.id)}
                  className={`px-2.5 py-1 text-xs rounded-lg font-mono transition-all cursor-pointer ${
                    formTempPreset === pr.id
                      ? "bg-amber-600 text-white font-bold shadow-sm shadow-amber-600/30"
                      : "bg-slate-800 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {pr.label}
                </button>
              ))}
              {formTempPreset === "custom" && (
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="2"
                  placeholder="0.0 - 2.0"
                  value={formCustomTemp}
                  onChange={(e) => setFormCustomTemp(e.target.value)}
                  className="w-24 px-2 py-0.5 text-xs bg-slate-950 border border-amber-500/50 rounded-lg text-slate-100 font-mono focus:outline-none"
                />
              )}
            </div>
            <p className="text-[10px] text-slate-500">
              Default base temperature for ensemble. Applied to judge and candidates unless overridden.
            </p>
          </div>

          {/* Judge Selector with Model vs Fallback Profile toggle */}
          <div className="p-3 bg-amber-950/20 border border-amber-800/40 rounded-xl space-y-2.5">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-amber-300 flex items-center gap-1.5">
                <Scale size={14} />
                {t.fusion.judge}
              </h4>
              <div className="flex items-center gap-2 text-xs bg-slate-950 border border-slate-800 rounded-lg p-0.5">
                <button
                  type="button"
                  onClick={() => setFormJudgeType("model")}
                  className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors cursor-pointer ${
                    formJudgeType === "model" ? "bg-amber-600 text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {t.fusion.judgeModel}
                </button>
                <button
                  type="button"
                  onClick={() => setFormJudgeType("profile")}
                  className={`px-2.5 py-0.5 rounded text-[11px] font-medium transition-colors flex items-center gap-1 cursor-pointer ${
                    formJudgeType === "profile" ? "bg-purple-600 text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <GitFork size={11} />
                  {t.fusion.judgeRoute}
                </button>
              </div>
            </div>

            {formJudgeType === "profile" ? (
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">Select Fallback Route Profile</label>
                {routingProfiles.length === 0 ? (
                  <p className="text-xs text-rose-400">No routing profiles found. Create one in Routing Profiles.</p>
                ) : (
                  <select
                    value={formJudgeRoutingProfileId ?? ""}
                    onChange={(e) => setFormJudgeRoutingProfileId(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
                  >
                    {routingProfiles.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} (route/{r.slug}) • {r.candidates?.length || 0} candidates
                      </option>
                    ))}
                  </select>
                )}
                <p className="text-[10px] text-slate-400 mt-1">
                  Judge requests are routed through this resilience fallback chain with its configured credentials and priority.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">1. Judge Provider</label>
                    <select
                      value={formJudgeProviderId}
                      onChange={(e) => {
                        setFormJudgeProviderId(parseInt(e.target.value));
                        setFormJudgeCredTarget("all");
                      }}
                      className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs focus:border-amber-500 focus:outline-none"
                    >
                      {providers.map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="block text-[10px] text-slate-400">2. Credentials / Group</label>
                      <span className="text-[9px] text-amber-400 font-medium truncate max-w-[100px]" title={
                        formJudgeCredTarget === "all"
                          ? "⚡ All keys"
                          : formJudgeCredTarget.startsWith("group:")
                          ? `📁 ${formJudgeCredTarget.slice(6)}`
                          : "Single key"
                      }>
                        {formJudgeCredTarget === "all"
                          ? "⚡ All keys"
                          : formJudgeCredTarget.startsWith("group:")
                          ? `📁 ${formJudgeCredTarget.slice(6)}`
                          : "Single key"}
                      </span>
                    </div>
                    <select
                      value={formJudgeCredTarget}
                      onChange={(e) => setFormJudgeCredTarget(e.target.value)}
                      className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs focus:border-amber-500 focus:outline-none"
                    >
                      <option value="all">⚡ All provider keys (full fallback)</option>
                      {judgeGroups.length > 0 && (
                        <optgroup label="Key Groups">
                          {judgeGroups.map((g) => (
                            <option key={`group:${g}`} value={`group:${g}`}>
                              📁 Group: {g} ({credentials.filter((c) => c.provider_id === formJudgeProviderId && c.group_name === g).length} keys)
                            </option>
                          ))}
                        </optgroup>
                      )}
                      <optgroup label="Single Keys">
                        {judgeCreds.map((c) => (
                          <option key={`key:${c.id}`} value={`key:${c.id}`}>
                            🔑 {c.name} {c.group_name ? `[${c.group_name}]` : ""}
                          </option>
                        ))}
                      </optgroup>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">3. Judge Model</label>
                    <select
                      value={formJudgeModelId}
                      onChange={(e) => setFormJudgeModelId(parseInt(e.target.value))}
                      className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs focus:border-amber-500 focus:outline-none font-mono"
                    >
                      {judgeModels.map((m) => (
                        <option key={m.id} value={m.id}>{m.provider_model_id}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Judge Reasoning & Temperature */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2 border-t border-amber-500/15">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-medium text-slate-300 flex items-center gap-1">
                        <Brain size={11} className="text-purple-400" />
                        {t.fusion.judgeThinking}:
                      </label>
                      <span className="text-[9px] font-mono text-purple-400">
                        {formJudgeThinkingEffort === "inherit"
                          ? "Inherit"
                          : formJudgeThinkingEffort === "custom"
                          ? (formJudgeCustomThinking || "Custom")
                          : formJudgeThinkingEffort.toUpperCase()}
                      </span>
                    </div>
                    <div className="grid grid-cols-4 sm:grid-cols-7 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px]">
                      {[
                        { id: "inherit", label: "Auto" },
                        { id: "auto", label: "Auto" },
                        { id: "low", label: "Low" },
                        { id: "medium", label: "Medium" },
                        { id: "high", label: "High" },
                        { id: "off", label: "Off" },
                        { id: "custom", label: "✏️" },
                      ].map((opt) => (
                        <button
                          key={opt.id}
                          type="button"
                          onClick={() => setFormJudgeThinkingEffort(opt.id)}
                          className={`py-0.5 rounded text-center transition-colors cursor-pointer ${
                            formJudgeThinkingEffort === opt.id
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
                    {formJudgeThinkingEffort === "custom" && (
                      <input
                        type="text"
                        placeholder="tokens (e.g. 4096)"
                        value={formJudgeCustomThinking}
                        onChange={(e) => setFormJudgeCustomThinking(e.target.value)}
                        className="w-full px-2 py-0.5 text-[10px] bg-slate-950 border border-purple-500/50 rounded text-slate-100 font-mono focus:outline-none"
                      />
                    )}
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-medium text-slate-300 flex items-center gap-1">
                        <Thermometer size={11} className="text-amber-400" />
                        {t.fusion.judgeTemperature}:
                      </label>
                      <span className="text-[9px] font-mono text-amber-400">
                        {formJudgeTempPreset === "inherit"
                          ? "Inherit"
                          : formJudgeTempPreset === "custom"
                          ? `temp: ${formJudgeCustomTemp || "Custom"}`
                          : `temp: ${formJudgeTempPreset}`}
                      </span>
                    </div>
                    <div className="grid grid-cols-4 sm:grid-cols-8 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px]">
                      {FUSION_TEMP_PRESETS.map((opt) => (
                        <button
                          key={opt.id}
                          type="button"
                          onClick={() => setFormJudgeTempPreset(opt.id)}
                          className={`py-0.5 rounded text-center transition-colors cursor-pointer ${
                            formJudgeTempPreset === opt.id
                              ? opt.id === "inherit"
                                ? "bg-slate-700 text-white font-semibold"
                                : opt.id === "custom"
                                ? "bg-indigo-600 text-white font-semibold"
                                : "bg-amber-600 text-white font-semibold"
                              : "text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                    {formJudgeTempPreset === "custom" && (
                      <input
                        type="number"
                        step="0.05"
                        min="0"
                        max="2"
                        placeholder="0.0 - 2.0"
                        value={formJudgeCustomTemp}
                        onChange={(e) => setFormJudgeCustomTemp(e.target.value)}
                        className="w-full px-2 py-0.5 text-[10px] bg-slate-950 border border-amber-500/50 rounded text-slate-100 font-mono focus:outline-none"
                      />
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Add Participant Sub-section with Model vs Fallback Profile toggle */}
          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2.5">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-200">{t.fusion.addParticipant}</h4>
              <div className="flex items-center gap-2 text-xs bg-slate-900 border border-slate-800 rounded-lg p-0.5">
                <button
                  type="button"
                  onClick={() => setPartType("model")}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors cursor-pointer ${
                    partType === "model" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {t.common.model}
                </button>
                <button
                  type="button"
                  onClick={() => setPartType("profile")}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors flex items-center gap-1 cursor-pointer ${
                    partType === "profile" ? "bg-purple-600 text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <GitFork size={11} />
                  {t.fusion.judgeRoute}
                </button>
              </div>
            </div>

            {partType === "profile" ? (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">Fallback Profile (Route)</label>
                  <select
                    value={partTargetProfileId}
                    onChange={(e) => setPartTargetProfileId(parseInt(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs"
                  >
                    {routingProfiles.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} (route/{r.slug})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">Label</label>
                  <input
                    type="text"
                    value={partLabel}
                    onChange={(e) => setPartLabel(e.target.value)}
                    placeholder="e.g. Fast Fallback Chain"
                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs font-mono"
                  />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">1. {t.common.provider}</label>
                  <select
                    value={partProviderId}
                    onChange={(e) => {
                      setPartProviderId(parseInt(e.target.value));
                      setPartCredTarget("all");
                    }}
                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs"
                  >
                    {providers.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-[10px] text-slate-400">2. Keys / Group</label>
                    <span className="text-[9px] text-amber-400 font-medium truncate max-w-[100px]" title={
                      partCredTarget === "all"
                        ? "⚡ All keys"
                        : partCredTarget.startsWith("group:")
                        ? `📁 ${partCredTarget.slice(6)}`
                        : "Single key"
                    }>
                      {partCredTarget === "all"
                        ? "⚡ All keys"
                        : partCredTarget.startsWith("group:")
                        ? `📁 ${partCredTarget.slice(6)}`
                        : "Single key"}
                    </span>
                  </div>
                  <select
                    value={partCredTarget}
                    onChange={(e) => setPartCredTarget(e.target.value)}
                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs"
                  >
                    <option value="all">⚡ All keys (full fallback)</option>
                    {partGroups.length > 0 && (
                      <optgroup label="Key Groups">
                        {partGroups.map((g) => (
                          <option key={`group:${g}`} value={`group:${g}`}>
                            📁 Group: {g} ({credentials.filter((c) => c.provider_id === partProviderId && c.group_name === g).length} keys)
                          </option>
                        ))}
                      </optgroup>
                    )}
                    <optgroup label="Single Keys">
                      {partCreds.map((c) => (
                        <option key={`key:${c.id}`} value={`key:${c.id}`}>
                          🔑 {c.name} {c.group_name ? `[${c.group_name}]` : ""}
                        </option>
                      ))}
                    </optgroup>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">3. {t.common.model}</label>
                  <select
                    value={partModelId}
                    onChange={(e) => setPartModelId(parseInt(e.target.value))}
                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs font-mono"
                  >
                    {partModels.map((m) => (
                      <option key={m.id} value={m.id}>{m.provider_model_id}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1">4. Label</label>
                  <input
                    type="text"
                    value={partLabel}
                    onChange={(e) => setPartLabel(e.target.value)}
                    placeholder="Candidate A"
                    className="w-full px-2 py-1 bg-slate-900 border border-slate-800 rounded text-slate-100 text-xs font-mono"
                  />
                </div>
              </div>
            )}

            {/* Candidate Reasoning & Temperature overrides */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2 border-t border-slate-800/80">
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-medium text-slate-300 flex items-center gap-1">
                    <Brain size={11} className="text-purple-400" />
                    Candidate Reasoning:
                  </label>
                  <span className="text-[9px] font-mono text-purple-400">
                    {partThinkingEffort === "inherit"
                      ? "Inherit"
                      : partThinkingEffort === "custom"
                      ? (partCustomThinking || "Custom")
                      : partThinkingEffort.toUpperCase()}
                  </span>
                </div>
                <div className="grid grid-cols-4 sm:grid-cols-7 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px]">
                  {[
                    { id: "inherit", label: "Auto" },
                    { id: "auto", label: "Auto" },
                    { id: "low", label: "Low" },
                    { id: "medium", label: "Medium" },
                    { id: "high", label: "High" },
                    { id: "off", label: "Off" },
                    { id: "custom", label: "✏️" },
                  ].map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => setPartThinkingEffort(opt.id)}
                      className={`py-0.5 rounded text-center transition-colors cursor-pointer ${
                        partThinkingEffort === opt.id
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
                {partThinkingEffort === "custom" && (
                  <input
                    type="text"
                    placeholder="tokens (e.g. 4096)"
                    value={partCustomThinking}
                    onChange={(e) => setPartCustomThinking(e.target.value)}
                    className="w-full px-2 py-0.5 text-[10px] bg-slate-950 border border-purple-500/50 rounded text-slate-100 font-mono focus:outline-none"
                  />
                )}
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-medium text-slate-300 flex items-center gap-1">
                    <Thermometer size={11} className="text-amber-400" />
                    Candidate Temperature:
                  </label>
                  <span className="text-[9px] font-mono text-amber-400">
                    {partTempPreset === "inherit"
                      ? "Inherit"
                      : partTempPreset === "custom"
                      ? `temp: ${partCustomTemp || "Custom"}`
                      : `temp: ${partTempPreset}`}
                  </span>
                </div>
                <div className="grid grid-cols-4 sm:grid-cols-8 gap-1 p-0.5 bg-slate-900 rounded-lg border border-slate-800 text-[10px]">
                  {FUSION_TEMP_PRESETS.map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => setPartTempPreset(opt.id)}
                      className={`py-0.5 rounded text-center transition-colors cursor-pointer ${
                        partTempPreset === opt.id
                          ? opt.id === "inherit"
                            ? "bg-slate-700 text-white font-semibold"
                            : opt.id === "custom"
                            ? "bg-indigo-600 text-white font-semibold"
                            : "bg-amber-600 text-white font-semibold"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {partTempPreset === "custom" && (
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="2"
                    placeholder="0.0 - 2.0"
                    value={partCustomTemp}
                    onChange={(e) => setPartCustomTemp(e.target.value)}
                    className="w-full px-2 py-0.5 text-[10px] bg-slate-950 border border-amber-500/50 rounded text-slate-100 font-mono focus:outline-none"
                  />
                )}
              </div>
            </div>

            <button
              type="button"
              onClick={addParticipant}
              className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-sm shadow-indigo-600/20 transition-colors cursor-pointer"
            >
              + {t.fusion.addParticipant}
            </button>
          </div>

          {/* Participant list */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300">
              {t.fusion.participants} ({formParticipants.length})
            </label>
            {formParticipants.length === 0 ? (
              <p className="text-xs text-slate-500 italic p-2 bg-slate-950 rounded border border-slate-800/80">
                No candidates added yet. Add at least 2 candidates above.
              </p>
            ) : (
              formParticipants.map((p, idx) => {
                const isProfile = p.participant_type === "profile" || !!p.target_profile_id;
                const targetRoute = routingProfiles.find((r) => r.id === p.target_profile_id);
                const pObj = providers.find((prov) => prov.id === p.provider_id);
                const mObj = models.find((m) => m.id === p.model_id);
                const cObj = credentials.find((cr) => cr.id === p.credential_id);

                return (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 bg-slate-950 border border-slate-800 rounded-lg text-xs"
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="w-5 h-5 rounded-full bg-slate-800 text-slate-300 text-[10px] font-mono flex items-center justify-center font-bold">
                        #{idx + 1}
                      </span>
                      <span className="font-mono text-indigo-300 font-semibold">{p.label}</span>
                      <span className="text-slate-500">:</span>
                      {isProfile ? (
                        <div className="flex items-center gap-1.5">
                          <GitFork size={12} className="text-purple-400" />
                          <span className="text-purple-200 font-medium">Route: {targetRoute?.name || `ID ${p.target_profile_id}`}</span>
                          <span className="text-slate-400 font-mono text-[10px]">(route/{targetRoute?.slug})</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <span className="text-slate-200">{pObj?.name}</span>
                          <span className="text-slate-500">→</span>
                          <span className="font-mono text-slate-300">{mObj?.provider_model_id}</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded flex items-center gap-1 ${
                            p.credential_group
                              ? "text-blue-300 bg-blue-950/60 border border-blue-800/40"
                              : cObj
                              ? "text-slate-400 bg-slate-900 border border-slate-800"
                              : "text-emerald-300 bg-emerald-950/60 border border-emerald-800/40"
                          }`}>
                            {p.credential_group ? (
                              <>
                                <Folder size={10} className="text-blue-400" />
                                Group: {p.credential_group}
                              </>
                            ) : cObj ? (
                              <>
                                <Key size={10} className="text-slate-400" />
                                {cObj.name}
                              </>
                            ) : (
                              <>
                                <Zap size={10} className="text-emerald-400" />
                                All keys
                              </>
                            )}
                          </span>
                        </div>
                      )}

                      {p.thinking_effort && (
                        <span className="text-[10px] bg-purple-900/60 text-purple-200 border border-purple-700/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                          <Brain size={10} className="text-purple-300" />
                          CoT: {p.thinking_effort}
                        </span>
                      )}

                      {p.temperature !== null && p.temperature !== undefined && (
                        <span className="text-[10px] bg-amber-950/60 text-amber-300 border border-amber-800/60 px-1.5 py-0.5 rounded font-mono flex items-center gap-1">
                          <Thermometer size={10} className="text-amber-400" />
                          temp: {p.temperature}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        disabled={idx === 0}
                        onClick={() => moveParticipant(idx, "up")}
                        className="p-1 text-slate-400 hover:text-slate-200 disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed"
                        title="Move up"
                      >
                        <ArrowUp size={13} />
                      </button>
                      <button
                        type="button"
                        disabled={idx === formParticipants.length - 1}
                        onClick={() => moveParticipant(idx, "down")}
                        className="p-1 text-slate-400 hover:text-slate-200 disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed"
                        title="Move down"
                      >
                        <ArrowDown size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeParticipant(idx)}
                        className="p-1 text-slate-400 hover:text-rose-400 cursor-pointer"
                        title="Delete candidate"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                {t.fusion.minSuccess} (Quorum)
              </label>
              <input
                type="number"
                min={1}
                value={formMinSuccess}
                onChange={(e) => setFormMinSuccess(parseInt(e.target.value) || 1)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                {t.fusion.timeout} (s)
              </label>
              <input
                type="number"
                value={formTimeout}
                onChange={(e) => setFormTimeout(parseFloat(e.target.value) || 120)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Custom Judge System Prompt (optional)
            </label>
            <textarea
              rows={2}
              value={formSystemPrompt}
              onChange={(e) => setFormSystemPrompt(e.target.value)}
              placeholder="Leave empty to use standard prompt for selected strategy..."
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none resize-none font-mono"
            />
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
              className="btn-press px-5 py-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-amber-500/20 border border-white/10 transition-all cursor-pointer"
            >
              {t.common.save}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
