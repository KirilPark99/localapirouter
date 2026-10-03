import React, { useEffect, useState, useMemo } from "react";
import {
  Plus,
  Trash2,
  Edit2,
  Scale,
  Sparkles,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  Search,
  ArrowUp,
  ArrowDown,
  Tag,
  Gauge,
  Brain,
  Layers,
  Cpu,
  Key,
  Folder,
  Thermometer,
  Play,
  RotateCcw,
  Zap,
  MessageSquare,
} from "lucide-react";
import { apiRequest } from "../api/client";
import {
  JudgeProfile,
  JudgeCandidate,
  JudgeTestResponse,
  Provider,
  Credential,
  DiscoveredModel,
  RoutingProfile,
} from "../types";
import { Modal } from "../components/Modal";
import { useI18n } from "../i18n/context";
import { getHiddenModelIds, isModelVisible } from "../utils/models";

export const JUDGE_TEMP_PRESETS = [
  { id: "0.0", label: "0.0", value: 0.0, desc: "Строгий / Детерминированный" },
  { id: "0.1", label: "0.1", value: 0.1, desc: "Рекомендуемый для судьи" },
  { id: "0.3", label: "0.3", value: 0.3, desc: "Сбалансированный" },
  { id: "0.7", label: "0.7", value: 0.7, desc: "Стандартный" },
  { id: "inherit", label: "Inherit", value: null, desc: "По умолчанию" },
];

export const REASONING_EFFORT_PRESETS = [
  { id: "inherit", label: "Inherit", desc: "По умолчанию модели / запроса" },
  { id: "none", label: "none (off)", desc: "Отключить рассуждения" },
  { id: "low", label: "low", desc: "Низкий уровень" },
  { id: "medium", label: "medium", desc: "Средний уровень" },
  { id: "high", label: "high", desc: "Высокий уровень" },
  { id: "auto", label: "auto", desc: "Автоматический выбор" },
  { id: "custom", label: "Custom...", desc: "Свой вариант" },
];

export const COMPLEXITY_PRESETS = [
  { id: "all", label: "Любая сложность (All)", desc: "Все типы запросов" },
  { id: "low", label: "Низкая сложность (Low)", desc: "Простые вопросы, быстрый чат" },
  { id: "medium", label: "Средняя сложность (Medium)", desc: "Аналитика, стандартный код" },
  { id: "high", label: "Высокая сложность (High)", desc: "Глубокая логика, сложные алгоритмы" },
  { id: "custom", label: "Свой уровень сложности (Custom)...", desc: "Пользовательский" },
];

export const TASK_TYPE_PRESETS = [
  "code",
  "math",
  "reasoning",
  "chat",
  "creative",
  "translation",
  "analysis",
  "summary",
  "agentic",
  "fast",
];

export const JudgeRoutingPage: React.FC = () => {
  const { t } = useI18n();
  const [profiles, setProfiles] = useState<JudgeProfile[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [models, setModels] = useState<DiscoveredModel[]>([]);
  const [routingProfiles, setRoutingProfiles] = useState<RoutingProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [strategyFilter, setStrategyFilter] = useState<string>("all");

  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);

  // Modal create/edit state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<JudgeProfile | null>(null);

  const [formName, setFormName] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formStrategy, setFormStrategy] = useState<"auto" | "complexity" | "task_type">("auto");
  const [formTimeout, setFormTimeout] = useState(60.0);
  const [formEnabled, setFormEnabled] = useState(true);

  // Judge model configuration
  const [formJudgeType, setFormJudgeType] = useState<"model" | "profile">("model");
  const [formJudgeRoutingProfileId, setFormJudgeRoutingProfileId] = useState<number | undefined>(undefined);
  const [formJudgeProviderId, setFormJudgeProviderId] = useState<number>(1);
  const [formJudgeCredTarget, setFormJudgeCredTarget] = useState<string>("all");
  const [formJudgeModelId, setFormJudgeModelId] = useState<number>(1);
  const [formJudgeThinkingPreset, setFormJudgeThinkingPreset] = useState<string>("inherit");
  const [formJudgeCustomThinking, setFormJudgeCustomThinking] = useState<string>("");
  const [formJudgeTempPreset, setFormJudgeTempPreset] = useState<string>("0.1");
  const [formJudgeCustomTemp, setFormJudgeCustomTemp] = useState<string>("");
  const [formSystemPrompt, setFormSystemPrompt] = useState("");
  const [formFallbackCandidateId, setFormFallbackCandidateId] = useState<number | undefined>(undefined);

  // Candidates list state in modal
  const [formCandidates, setFormCandidates] = useState<JudgeCandidate[]>([]);

  // Candidate adder state
  const [candType, setCandType] = useState<"model" | "profile">("model");
  const [candTargetProfileId, setCandTargetProfileId] = useState<number>(1);
  const [candProviderId, setCandProviderId] = useState<number>(1);
  const [candCredTarget, setCandCredTarget] = useState<string>("all");
  const [candModelId, setCandModelId] = useState<number>(1);
  const [candLabel, setCandLabel] = useState("");
  const [candTaskTypes, setCandTaskTypes] = useState<string[]>([]);
  const [customTagInput, setCustomTagInput] = useState("");
  const [candComplexityPreset, setCandComplexityPreset] = useState<string>("all");
  const [candCustomComplexity, setCandCustomComplexity] = useState<string>("");
  const [candDescription, setCandDescription] = useState("");
  const [candThinkingPreset, setCandThinkingPreset] = useState<string>("inherit");
  const [candCustomThinking, setCandCustomThinking] = useState<string>("");
  const [candTempPreset, setCandTempPreset] = useState<string>("inherit");
  const [candCustomTemp, setCandCustomTemp] = useState<string>("");

  // Test Evaluation modal state
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [testingProfile, setTestingProfile] = useState<JudgeProfile | null>(null);
  const [testPrompt, setTestPrompt] = useState("");
  const [testResult, setTestResult] = useState<JudgeTestResponse | null>(null);
  const [testingInProgress, setTestingInProgress] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [j, p, c, m, r] = await Promise.all([
        apiRequest<JudgeProfile[]>("/api/admin/judges"),
        apiRequest<Provider[]>("/api/admin/providers"),
        apiRequest<Credential[]>("/api/admin/credentials"),
        apiRequest<DiscoveredModel[]>("/api/admin/models"),
        apiRequest<RoutingProfile[]>("/api/admin/routes"),
      ]);
      setProfiles(j || []);
      setProviders(p || []);
      setCredentials(c || []);
      setModels(m || []);
      setRoutingProfiles(r || []);

      if (p && p.length > 0) {
        setFormJudgeProviderId(p[0].id);
        setCandProviderId(p[0].id);
      }
      if (m && m.length > 0) {
        setFormJudgeModelId(m[0].id);
        setCandModelId(m[0].id);
      }
      if (r && r.length > 0) {
        setFormJudgeRoutingProfileId(r[0].id);
        setCandTargetProfileId(r[0].id);
      }
    } catch (err) {
      console.error("Failed to load judge routing data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSlug(id);
    setTimeout(() => setCopiedSlug(null), 2000);
  };

  const filteredProfiles = useMemo(() => {
    return profiles.filter((p) => {
      const matchesSearch =
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.slug.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase())) ||
        p.candidates.some(
          (c) =>
            c.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
            c.task_types.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()))
        );
      const matchesStrategy = strategyFilter === "all" || p.strategy === strategyFilter;
      return matchesSearch && matchesStrategy;
    });
  }, [profiles, searchQuery, strategyFilter]);

  // Helper to count visible models for a provider
  const getProviderVisibleCount = (provId: number): number => {
    const hiddenIds = getHiddenModelIds();
    const countMap = new Set<string>();
    models
      .filter((m) => m.provider_id === provId && isModelVisible(m, hiddenIds))
      .forEach((m) => countMap.add(m.provider_model_id));
    return countMap.size;
  };

  // Only providers that have visible models (or currently selected provider)
  const visibleJudgeProviders = useMemo(() => {
    const hiddenIds = getHiddenModelIds();
    return providers.filter(
      (p) => p.id === formJudgeProviderId || models.some((m) => m.provider_id === p.id && isModelVisible(m, hiddenIds))
    );
  }, [providers, models, formJudgeProviderId]);

  const visibleCandProviders = useMemo(() => {
    const hiddenIds = getHiddenModelIds();
    return providers.filter(
      (p) => p.id === candProviderId || models.some((m) => m.provider_id === p.id && isModelVisible(m, hiddenIds))
    );
  }, [providers, models, candProviderId]);

  // Visible models filtered by selected provider (deduplicated by provider_model_id)
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
    return Array.from(map.values()).sort((a, b) =>
      (a.display_name || a.provider_model_id).localeCompare(b.display_name || b.provider_model_id)
    );
  }, [models, formJudgeProviderId]);

  const candModels = useMemo(() => {
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
    return Array.from(map.values()).sort((a, b) =>
      (a.display_name || a.provider_model_id).localeCompare(b.display_name || b.provider_model_id)
    );
  }, [models, candProviderId]);

  // Auto-sync selected model if not in filtered list
  useEffect(() => {
    if (judgeModels.length > 0 && !judgeModels.some((m) => m.id === formJudgeModelId)) {
      setFormJudgeModelId(judgeModels[0].id);
    }
  }, [judgeModels, formJudgeModelId]);

  useEffect(() => {
    if (candModels.length > 0 && !candModels.some((m) => m.id === candModelId)) {
      setCandModelId(candModels[0].id);
    }
  }, [candModels, candModelId]);

  // Credentials and groups for Judge
  const judgeCredentials = useMemo(() => {
    return credentials.filter((c) => c.provider_id === formJudgeProviderId && c.enabled);
  }, [credentials, formJudgeProviderId]);

  const judgeGroups = useMemo(() => {
    const s = new Set<string>();
    credentials.forEach((c) => {
      if (c.provider_id === formJudgeProviderId && c.group_name) s.add(c.group_name);
    });
    return Array.from(s);
  }, [credentials, formJudgeProviderId]);

  // Credentials and groups for Candidate Adder
  const candCredentials = useMemo(() => {
    return credentials.filter((c) => c.provider_id === candProviderId && c.enabled);
  }, [credentials, candProviderId]);

  const candGroups = useMemo(() => {
    const s = new Set<string>();
    credentials.forEach((c) => {
      if (c.provider_id === candProviderId && c.group_name) s.add(c.group_name);
    });
    return Array.from(s);
  }, [credentials, candProviderId]);

  const openCreateModal = () => {
    setEditingProfile(null);
    setFormName("");
    setFormSlug("");
    setFormDescription("");
    setFormStrategy("auto");
    setFormTimeout(60.0);
    setFormEnabled(true);
    setFormJudgeType("model");

    const hiddenIds = getHiddenModelIds();
    const firstProv = providers.find((p) =>
      models.some((m) => m.provider_id === p.id && isModelVisible(m, hiddenIds))
    ) || providers[0];

    const firstJudgeModel = firstProv
      ? models.find((m) => m.provider_id === firstProv.id && isModelVisible(m, hiddenIds))
      : models.find((m) => isModelVisible(m, hiddenIds));

    if (firstProv) {
      setFormJudgeProviderId(firstProv.id);
      setCandProviderId(firstProv.id);
    }
    if (firstJudgeModel) {
      setFormJudgeModelId(firstJudgeModel.id);
      setCandModelId(firstJudgeModel.id);
    }
    if (routingProfiles.length > 0) setFormJudgeRoutingProfileId(routingProfiles[0].id);
    setFormJudgeCredTarget("all");
    setFormJudgeThinkingPreset("inherit");
    setFormJudgeCustomThinking("");
    setFormJudgeTempPreset("0.1");
    setFormJudgeCustomTemp("");
    setFormSystemPrompt("");
    setFormFallbackCandidateId(undefined);
    setFormCandidates([]);

    setCandComplexityPreset("all");
    setCandCustomComplexity("");
    setCandThinkingPreset("inherit");
    setCandCustomThinking("");
    setCandTempPreset("inherit");
    setCandCustomTemp("");
    setIsModalOpen(true);
  };

  const openEditModal = (p: JudgeProfile) => {
    setEditingProfile(p);
    setFormName(p.name);
    setFormSlug(p.slug);
    setFormDescription(p.description || "");
    setFormStrategy((p.strategy as any) || "auto");
    setFormTimeout(p.timeout_seconds || 60.0);
    setFormEnabled(p.enabled);
    setFormJudgeType((p.judge_type as any) || "model");
    setFormJudgeRoutingProfileId(p.judge_routing_profile_id || undefined);
    setFormJudgeProviderId(p.judge_provider_id || (providers[0]?.id || 1));
    setFormJudgeModelId(p.judge_model_id || (models[0]?.id || 1));

    const hiddenIds = getHiddenModelIds();
    const firstCandProv = providers.find((pr) =>
      models.some((m) => m.provider_id === pr.id && isModelVisible(m, hiddenIds))
    ) || providers[0];
    if (firstCandProv) {
      setCandProviderId(firstCandProv.id);
      const firstCandM = models.find((m) => m.provider_id === firstCandProv.id && isModelVisible(m, hiddenIds));
      if (firstCandM) setCandModelId(firstCandM.id);
    }

    if (p.judge_credential_id) {
      setFormJudgeCredTarget(`cred_${p.judge_credential_id}`);
    } else if (p.judge_credential_group) {
      setFormJudgeCredTarget(`group_${p.judge_credential_group}`);
    } else {
      setFormJudgeCredTarget("all");
    }

    if (p.judge_thinking_effort) {
      const match = REASONING_EFFORT_PRESETS.find((pr) => pr.id === p.judge_thinking_effort);
      if (match && match.id !== "custom") {
        setFormJudgeThinkingPreset(match.id);
        setFormJudgeCustomThinking("");
      } else {
        setFormJudgeThinkingPreset("custom");
        setFormJudgeCustomThinking(p.judge_thinking_effort);
      }
    } else {
      setFormJudgeThinkingPreset("inherit");
      setFormJudgeCustomThinking("");
    }

    if (p.judge_temperature !== null && p.judge_temperature !== undefined) {
      const match = JUDGE_TEMP_PRESETS.find((pr) => pr.value === p.judge_temperature);
      if (match) {
        setFormJudgeTempPreset(match.id);
        setFormJudgeCustomTemp("");
      } else {
        setFormJudgeTempPreset("custom");
        setFormJudgeCustomTemp(String(p.judge_temperature));
      }
    } else {
      setFormJudgeTempPreset("inherit");
      setFormJudgeCustomTemp("");
    }

    setFormSystemPrompt(p.system_prompt || "");
    setFormFallbackCandidateId(p.fallback_candidate_id || undefined);
    setFormCandidates([...p.candidates]);

    setCandComplexityPreset("all");
    setCandCustomComplexity("");
    setCandThinkingPreset("inherit");
    setCandCustomThinking("");
    setCandTempPreset("inherit");
    setCandCustomTemp("");
    setIsModalOpen(true);
  };

  const handleAddCandidate = () => {
    if (candType === "model" && (!candModelId || candModels.length === 0)) {
      alert("Выберите видимую модель кандидата из каталога");
      return;
    }
    let credId: number | null = null;
    let credGroup: string | null = null;
    if (candCredTarget.startsWith("cred_")) {
      credId = parseInt(candCredTarget.replace("cred_", ""), 10);
    } else if (candCredTarget.startsWith("group_")) {
      credGroup = candCredTarget.replace("group_", "");
    }

    let effTemp: number | null = null;
    if (candTempPreset === "custom" && candCustomTemp) {
      const val = parseFloat(candCustomTemp);
      if (!isNaN(val)) effTemp = val;
    } else if (candTempPreset !== "inherit") {
      const pr = JUDGE_TEMP_PRESETS.find((p) => p.id === candTempPreset);
      if (pr && pr.value !== null) effTemp = pr.value;
    }

    let effComplexity = "all";
    if (candComplexityPreset === "custom") {
      effComplexity = candCustomComplexity.trim() || "all";
    } else {
      effComplexity = candComplexityPreset;
    }

    let effThinking: string | null = null;
    if (candThinkingPreset === "custom") {
      effThinking = candCustomThinking.trim() || null;
    } else if (candThinkingPreset !== "inherit") {
      effThinking = candThinkingPreset;
    }

    const selectedModel = models.find((m) => m.id === candModelId);
    const selectedRoute = routingProfiles.find((r) => r.id === candTargetProfileId);
    const selectedProv = providers.find((pr) => pr.id === candProviderId);
    const selectedCred = credentials.find((c) => c.id === credId);

    const defaultLabel =
      candType === "profile"
        ? selectedRoute?.name || "Target Route"
        : selectedModel?.display_name || selectedModel?.provider_model_id || "Target Model";

    const newCand: JudgeCandidate = {
      candidate_type: candType,
      target_profile_id: candType === "profile" ? candTargetProfileId : null,
      target_profile_name: selectedRoute?.name,
      target_profile_slug: selectedRoute?.slug,
      provider_id: candType === "model" ? candProviderId : null,
      provider_name: selectedProv?.name,
      credential_id: candType === "model" ? credId : null,
      credential_name: selectedCred?.name,
      credential_group: candType === "model" ? credGroup : null,
      model_id: candType === "model" ? candModelId : null,
      model_name: selectedModel?.display_name || selectedModel?.provider_model_id,
      canonical_slug: selectedModel?.canonical_slug,
      label: candLabel.trim() || defaultLabel,
      task_types: [...candTaskTypes],
      complexity_level: effComplexity,
      description: candDescription.trim() || null,
      thinking_effort: effThinking,
      temperature: effTemp,
      priority_order: formCandidates.length,
      is_active: true,
    };

    setFormCandidates([...formCandidates, newCand]);
    setCandLabel("");
    setCandTaskTypes([]);
    setCandDescription("");
    setCandComplexityPreset("all");
    setCandCustomComplexity("");
    setCandThinkingPreset("inherit");
    setCandCustomThinking("");
    setCandTempPreset("inherit");
    setCandCustomTemp("");
  };

  const handleEditCandidate = (index: number) => {
    const c = formCandidates[index];
    if (!c) return;

    setCandType(c.candidate_type);
    if (c.target_profile_id) setCandTargetProfileId(c.target_profile_id);
    if (c.provider_id) setCandProviderId(c.provider_id);
    if (c.model_id) setCandModelId(c.model_id);
    if (c.credential_id) {
      setCandCredTarget(`cred_${c.credential_id}`);
    } else if (c.credential_group) {
      setCandCredTarget(`group_${c.credential_group}`);
    } else {
      setCandCredTarget("all");
    }

    setCandLabel(c.label);
    setCandTaskTypes([...(c.task_types || [])]);
    setCandDescription(c.description || "");

    // Complexity
    const compPreset = COMPLEXITY_PRESETS.find((p) => p.id === c.complexity_level);
    if (compPreset && compPreset.id !== "custom") {
      setCandComplexityPreset(compPreset.id);
      setCandCustomComplexity("");
    } else {
      setCandComplexityPreset("custom");
      setCandCustomComplexity(c.complexity_level);
    }

    // Thinking Effort
    if (c.thinking_effort) {
      const thPreset = REASONING_EFFORT_PRESETS.find((p) => p.id === c.thinking_effort);
      if (thPreset && thPreset.id !== "custom") {
        setCandThinkingPreset(thPreset.id);
        setCandCustomThinking("");
      } else {
        setCandThinkingPreset("custom");
        setCandCustomThinking(c.thinking_effort);
      }
    } else {
      setCandThinkingPreset("inherit");
      setCandCustomThinking("");
    }

    // Temperature
    if (c.temperature !== null && c.temperature !== undefined) {
      const tMatch = JUDGE_TEMP_PRESETS.find((p) => p.value === c.temperature);
      if (tMatch) {
        setCandTempPreset(tMatch.id);
        setCandCustomTemp("");
      } else {
        setCandTempPreset("custom");
        setCandCustomTemp(String(c.temperature));
      }
    } else {
      setCandTempPreset("inherit");
      setCandCustomTemp("");
    }

    setFormCandidates(formCandidates.filter((_, i) => i !== index));
  };

  const handleRemoveCandidate = (index: number) => {
    setFormCandidates(formCandidates.filter((_, i) => i !== index));
  };

  const handleMoveCandidate = (index: number, direction: "up" | "down") => {
    const targetIdx = direction === "up" ? index - 1 : index + 1;
    if (targetIdx < 0 || targetIdx >= formCandidates.length) return;
    const nextList = [...formCandidates];
    const temp = nextList[index];
    nextList[index] = nextList[targetIdx];
    nextList[targetIdx] = temp;
    // Update priority orders
    nextList.forEach((c, idx) => (c.priority_order = idx));
    setFormCandidates(nextList);
  };

  const toggleTaskTag = (tag: string) => {
    if (candTaskTypes.includes(tag)) {
      setCandTaskTypes(candTaskTypes.filter((t) => t !== tag));
    } else {
      setCandTaskTypes([...candTaskTypes, tag]);
    }
  };

  const handleAddCustomTag = () => {
    const clean = customTagInput.trim().toLowerCase();
    if (clean && !candTaskTypes.includes(clean)) {
      setCandTaskTypes([...candTaskTypes, clean]);
      setCustomTagInput("");
    }
  };

  const handleSaveProfile = async () => {
    if (!formName.trim()) {
      alert("Пожалуйста, укажите название профиля");
      return;
    }
    const cleanSlug = formSlug.trim() || formName.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-");

    if (formCandidates.length === 0) {
      alert("Необходимо добавить хотя бы одного кандидата");
      return;
    }

    if (formJudgeType === "model" && (!formJudgeModelId || judgeModels.length === 0)) {
      alert("Выберите видимую модель-судью из каталога");
      return;
    }

    let judgeCredId: number | null = null;
    let judgeCredGroup: string | null = null;
    if (formJudgeCredTarget.startsWith("cred_")) {
      judgeCredId = parseInt(formJudgeCredTarget.replace("cred_", ""), 10);
    } else if (formJudgeCredTarget.startsWith("group_")) {
      judgeCredGroup = formJudgeCredTarget.replace("group_", "");
    }

    let effJudgeTemp: number | null = null;
    if (formJudgeTempPreset === "custom" && formJudgeCustomTemp) {
      const val = parseFloat(formJudgeCustomTemp);
      if (!isNaN(val)) effJudgeTemp = val;
    } else if (formJudgeTempPreset !== "inherit") {
      const pr = JUDGE_TEMP_PRESETS.find((p) => p.id === formJudgeTempPreset);
      if (pr && pr.value !== null) effJudgeTemp = pr.value;
    }

    let effJudgeThinking: string | null = null;
    if (formJudgeThinkingPreset === "custom" && formJudgeCustomThinking) {
      effJudgeThinking = formJudgeCustomThinking.trim() || null;
    } else if (formJudgeThinkingPreset !== "inherit") {
      effJudgeThinking = formJudgeThinkingPreset;
    }

    const payload = {
      name: formName.trim(),
      slug: cleanSlug,
      description: formDescription.trim() || null,
      strategy: formStrategy,
      judge_type: formJudgeType,
      judge_routing_profile_id: formJudgeType === "profile" ? formJudgeRoutingProfileId : null,
      judge_provider_id: formJudgeType === "model" ? formJudgeProviderId : null,
      judge_credential_id: formJudgeType === "model" ? judgeCredId : null,
      judge_credential_group: formJudgeType === "model" ? judgeCredGroup : null,
      judge_model_id: formJudgeType === "model" ? formJudgeModelId : null,
      judge_thinking_effort: formJudgeType === "model" ? effJudgeThinking : null,
      judge_temperature: effJudgeTemp,
      system_prompt: formSystemPrompt.trim() || null,
      fallback_candidate_id: formFallbackCandidateId || null,
      timeout_seconds: formTimeout,
      enabled: formEnabled,
      candidates: formCandidates.map((c, idx) => ({
        candidate_type: c.candidate_type,
        target_profile_id: c.target_profile_id,
        provider_id: c.provider_id,
        credential_id: c.credential_id,
        credential_group: c.credential_group,
        model_id: c.model_id,
        thinking_effort: c.thinking_effort,
        temperature: c.temperature,
        priority_order: idx,
        label: c.label,
        task_types: c.task_types,
        complexity_level: c.complexity_level,
        description: c.description,
        is_active: c.is_active,
      })),
    };

    try {
      if (editingProfile) {
        await apiRequest(`/api/admin/judges/${editingProfile.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiRequest("/api/admin/judges", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      setIsModalOpen(false);
      await loadData();
    } catch (err: any) {
      alert(`Ошибка сохранения: ${err.message || err}`);
    }
  };

  const handleDeleteProfile = async (id: number, name: string) => {
    if (!confirm(`Удалить профиль судейской маршрутизации "${name}"?`)) return;
    try {
      await apiRequest(`/api/admin/judges/${id}`, { method: "DELETE" });
      await loadData();
    } catch (err: any) {
      alert(`Ошибка удаления: ${err.message || err}`);
    }
  };

  const handleToggleEnabled = async (p: JudgeProfile) => {
    try {
      await apiRequest(`/api/admin/judges/${p.id}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: !p.enabled }),
      });
      await loadData();
    } catch (err: any) {
      alert(`Ошибка изменения статуса: ${err.message || err}`);
    }
  };

  const openTestModal = (p: JudgeProfile) => {
    setTestingProfile(p);
    setTestPrompt("Напиши быстрый скрипт для парсинга логов на Python с обработкой регулярных выражений.");
    setTestResult(null);
    setTestError(null);
    setIsTestModalOpen(true);
  };

  const runTestEvaluation = async () => {
    if (!testingProfile || !testPrompt.trim()) return;
    setTestingInProgress(true);
    setTestError(null);
    setTestResult(null);
    try {
      const res = await apiRequest<JudgeTestResponse>(`/api/admin/judges/${testingProfile.id}/test`, {
        method: "POST",
        body: JSON.stringify({ prompt: testPrompt.trim() }),
      });
      setTestResult(res);
    } catch (err: any) {
      setTestError(err.message || String(err));
    } finally {
      setTestingInProgress(false);
    }
  };

  const getComplexityBadge = (level: string) => {
    switch (level) {
      case "high":
        return <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">Сложные (High)</span>;
      case "medium":
        return <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">Средние (Medium)</span>;
      case "low":
        return <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Простые (Low)</span>;
      case "all":
        return <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">Любая (All)</span>;
      default:
        return (
          <span
            className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-purple-500/15 text-purple-300 border border-purple-500/30 flex items-center gap-1"
            title={`Пользовательский уровень сложности: ${level}`}
          >
            <Tag size={9} className="text-purple-400 shrink-0" />
            <span className="truncate max-w-[120px]">{level}</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-gradient-to-tr from-amber-500/20 via-orange-500/15 to-violet-500/10 border border-amber-500/20 text-amber-400 shadow-lg shadow-amber-500/5">
              <Scale size={24} />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Судейская маршрутизация
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400">
                  AI Classifier
                </span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Модель-судья оценивает сложность и специфику запроса, перенаправляя его подходящему кандидату
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={openCreateModal}
          className="btn-press flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 hover:from-amber-400 hover:to-orange-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-amber-500/20 border border-amber-400/20 transition-all cursor-pointer"
        >
          <Plus size={16} />
          <span>Создать профиль судьи</span>
        </button>
      </div>

      {/* Control Bar: Search & Strategy Filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по названию, slug, кандидатам или описанию..."
            className="w-full bg-slate-900/60 border border-white/[0.08] rounded-xl pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500/50"
          />
        </div>
        <div className="flex items-center gap-2">
          <select
            value={strategyFilter}
            onChange={(e) => setStrategyFilter(e.target.value)}
            className="bg-slate-900/60 border border-white/[0.08] rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-amber-500/50"
          >
            <option value="all">Все стратегии</option>
            <option value="auto">Авто (Сложность + Тип задач)</option>
            <option value="complexity">Только сложность (Complexity)</option>
            <option value="task_type">Только тип задач (Task Type)</option>
          </select>
          <button
            onClick={loadData}
            className="p-2 bg-slate-900/60 hover:bg-slate-800 border border-white/[0.08] rounded-xl text-slate-400 hover:text-white transition-colors"
            title="Обновить список"
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {/* Profile Cards Grid */}
      {loading ? (
        <div className="p-12 text-center text-xs text-slate-500">Загрузка судейских профилей...</div>
      ) : filteredProfiles.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-slate-900/30 border border-white/[0.06] text-slate-400 space-y-3">
          <Scale size={32} className="mx-auto text-slate-600 opacity-60" />
          <div className="text-sm font-medium text-slate-300">Профили судейской маршрутизации не найдены</div>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Создайте первый профиль, выберите модель-судью (обычный LLM или JEV) и настройте кандидатов под разные типы задач и сложность.
          </p>
          <button
            onClick={openCreateModal}
            className="px-3.5 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 rounded-xl text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer"
          >
            <Plus size={14} /> Создать профиль
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredProfiles.map((p) => {
            const judgeIsJev = p.judge_model_type === "jev";
            return (
              <div
                key={p.id}
                className="bg-slate-900/70 border border-white/[0.07] hover:border-amber-500/30 rounded-2xl p-5 shadow-xl transition-all space-y-4"
              >
                {/* Top Row: Name, Slug, Status, Actions */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.06] pb-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2.5">
                      <h3 className="font-bold text-slate-100 text-sm">{p.name}</h3>
                      <button
                        onClick={() => copyToClipboard(`judge/${p.slug}`, `p_${p.id}`)}
                        className="flex items-center gap-1 px-2 py-0.5 bg-slate-950/70 hover:bg-white/[0.08] text-slate-300 hover:text-white rounded-lg text-[11px] font-mono border border-white/[0.06] transition-colors"
                        title="Скопировать модель для API запросов"
                      >
                        {copiedSlug === `p_${p.id}` ? (
                          <>
                            <Check size={12} className="text-emerald-400" />
                            <span className="text-emerald-400">Скопировано</span>
                          </>
                        ) : (
                          <>
                            <Copy size={12} className="text-slate-400" />
                            <span>judge/{p.slug}</span>
                          </>
                        )}
                      </button>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20">
                        {p.strategy === "auto" ? "Авто (Сложность + Тип)" : p.strategy}
                      </span>
                    </div>
                    {p.description && <p className="text-xs text-slate-400">{p.description}</p>}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <a
                      href={`/playground?model=judge/${encodeURIComponent(p.slug)}`}
                      className="btn-press flex items-center gap-1.5 px-3 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 hover:text-amber-200 border border-amber-500/20 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
                      title="Открыть и протестировать в Playground"
                    >
                      <MessageSquare size={13} />
                      <span>Playground</span>
                    </a>
                    <button
                      onClick={() => openTestModal(p)}
                      className="btn-press flex items-center gap-1.5 px-3 py-1.5 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 hover:text-indigo-200 border border-indigo-500/20 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
                      title="Протестировать решение судьи на тестовом промпте"
                    >
                      <Play size={13} />
                      <span>Тест судьи</span>
                    </button>
                    <button
                      onClick={() => handleToggleEnabled(p)}
                      className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold border flex items-center gap-1.5 transition-colors cursor-pointer ${
                        p.enabled
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/20"
                          : "bg-slate-800 text-slate-400 border-white/[0.06] hover:bg-slate-700"
                      }`}
                    >
                      {p.enabled ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                      <span>{p.enabled ? "Активен" : "Отключен"}</span>
                    </button>
                    <button
                      onClick={() => openEditModal(p)}
                      className="p-1.5 text-slate-400 hover:text-white bg-slate-800/80 hover:bg-slate-700 border border-white/[0.06] rounded-xl transition-colors cursor-pointer"
                      title="Редактировать"
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      onClick={() => handleDeleteProfile(p.id, p.name)}
                      className="p-1.5 text-rose-400 hover:text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 rounded-xl transition-colors cursor-pointer"
                      title="Удалить"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {/* Judge Engine Section */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 bg-slate-950/50 p-3 rounded-xl border border-white/[0.04] text-xs">
                  <div className="space-y-1">
                    <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                      <Scale size={13} className="text-amber-400" /> Модель-Судья
                    </span>
                    <div className="font-medium text-slate-200 flex items-center gap-1.5">
                      {p.judge_type === "profile" ? (
                        <span className="text-indigo-300 flex items-center gap-1">
                          <Folder size={12} /> route/{p.judge_routing_profile_slug}
                        </span>
                      ) : (
                        <>
                          <span>{p.judge_model_name || p.judge_canonical_slug || "Не выбрана"}</span>
                          {judgeIsJev && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                              JEV
                            </span>
                          )}
                        </>
                      )}
                    </div>
                    {p.judge_type === "model" && p.judge_provider_name && (
                      <div className="text-[11px] text-slate-400">Провайдер: {p.judge_provider_name}</div>
                    )}
                  </div>

                  <div className="space-y-1">
                    <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                      <Thermometer size={13} className="text-amber-400" /> Параметры Судьи
                    </span>
                    <div className="text-slate-300">
                      Температура: <span className="font-mono text-amber-300">{p.judge_temperature ?? "default"}</span>
                      {p.judge_thinking_effort && (
                        <span className="ml-2 font-mono text-purple-300">effort: {p.judge_thinking_effort}</span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400">Таймаут: {p.timeout_seconds}s</div>
                  </div>

                  <div className="space-y-1">
                    <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                      <Zap size={13} className="text-amber-400" /> Кандидатов в пуле
                    </span>
                    <div className="text-slate-300 font-semibold flex items-center gap-2">
                      <span>{p.candidates.length} активных</span>
                      {p.fallback_candidate_id && (
                        <span className="text-[10px] text-emerald-400 font-normal">
                          (Резерв: ID #{p.fallback_candidate_id})
                        </span>
                      )}
                    </div>
                    {p.system_prompt && (
                      <div className="text-[11px] text-slate-400 truncate max-w-xs" title={p.system_prompt}>
                        Промпт: "{p.system_prompt}"
                      </div>
                    )}
                  </div>
                </div>

                {/* Candidates List Preview */}
                <div className="space-y-2">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
                    <span>Кандидаты для маршрутизации:</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                    {p.candidates.map((c, idx) => (
                      <div
                        key={c.id || idx}
                        className="bg-slate-950/60 border border-white/[0.05] rounded-xl p-3 space-y-2 hover:border-white/[0.12] transition-colors"
                      >
                        <div className="flex items-center justify-between gap-1 flex-wrap">
                          <span className="font-semibold text-slate-200 text-xs flex items-center gap-1.5 truncate">
                            <span className="w-4 h-4 rounded-full bg-slate-800 text-slate-400 text-[10px] flex items-center justify-center font-mono shrink-0">
                              {idx + 1}
                            </span>
                            <span className="truncate">{c.label}</span>
                          </span>
                          <div className="flex items-center gap-1 shrink-0">
                            {c.thinking_effort && (
                              <span
                                className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-purple-500/15 text-purple-300 border border-purple-500/25 flex items-center gap-1"
                                title={`Уровень размышления кандидата: ${c.thinking_effort}`}
                              >
                                <Brain size={10} className="text-purple-400 shrink-0" />
                                <span>{c.thinking_effort}</span>
                              </span>
                            )}
                            {getComplexityBadge(c.complexity_level)}
                          </div>
                        </div>

                        <div className="text-[11px] text-slate-400 truncate font-mono">
                          {c.candidate_type === "profile" ? (
                            <span className="text-indigo-300">route/{c.target_profile_slug}</span>
                          ) : (
                            <span>{c.model_name || c.canonical_slug}</span>
                          )}
                        </div>

                        {c.task_types && c.task_types.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {c.task_types.map((tag) => (
                              <span
                                key={tag}
                                className="px-1.5 py-0.5 bg-slate-800/80 text-slate-300 rounded text-[10px] font-mono border border-white/[0.05]"
                              >
                                #{tag}
                              </span>
                            ))}
                          </div>
                        )}

                        {c.description && (
                          <p className="text-[11px] text-slate-400 line-clamp-2 italic">{c.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal Create / Edit Profile */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingProfile ? `Редактирование: ${editingProfile.name}` : "Новый профиль судейской маршрутизации"}
        maxWidth="2xl"
      >
        <div className="space-y-5 text-xs">
          {/* Main Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Название профиля *</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="например: Smart Routing Expert"
                className="w-full bg-slate-950 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 font-medium mb-1">Slug (URL / API ID) *</label>
              <div className="flex items-center">
                <span className="px-2.5 py-2 bg-slate-800 text-slate-400 border border-r-0 border-white/[0.09] rounded-l-xl font-mono text-xs">
                  judge/
                </span>
                <input
                  type="text"
                  value={formSlug}
                  onChange={(e) => setFormSlug(e.target.value)}
                  placeholder="smart-expert"
                  className="w-full bg-slate-950 border border-white/[0.09] rounded-r-xl px-3 py-2 text-white font-mono focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-slate-400 font-medium mb-1">Описание (опционально)</label>
            <input
              type="text"
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Например: Маршрутизирует сложный код в Sonnet, а легкие диалоги в Mini"
              className="w-full bg-slate-950 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500"
            />
          </div>

          {/* Strategy, Timeout & Active */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Стратегия оценки</label>
              <select
                value={formStrategy}
                onChange={(e) => setFormStrategy(e.target.value as any)}
                className="w-full bg-slate-950 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500"
              >
                <option value="auto">Авто (Сложность + Тип задач)</option>
                <option value="complexity">Только сложность (Complexity)</option>
                <option value="task_type">Только тип задач (Task Type)</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-400 font-medium mb-1">Таймаут (сек)</label>
              <input
                type="number"
                value={formTimeout}
                onChange={(e) => setFormTimeout(parseFloat(e.target.value) || 30.0)}
                className="w-full bg-slate-950 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500"
              />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formEnabled}
                  onChange={(e) => setFormEnabled(e.target.checked)}
                  className="rounded bg-slate-950 border-white/[0.09] text-amber-500 focus:ring-0"
                />
                <span className="text-slate-300 font-medium">Профиль активен</span>
              </label>
            </div>
          </div>

          {/* Section: Judge Model Configuration */}
          <div className="p-4 bg-slate-950/60 border border-amber-500/20 rounded-2xl space-y-3">
            <h4 className="font-bold text-amber-400 text-xs flex items-center gap-2">
              <Scale size={15} /> Конфигурация Модели-Судьи (Judge Model)
            </h4>
            <p className="text-[11px] text-slate-400">
              Модель-судья получает запрос пользователя, классифицирует его и решает, какому кандидату отдать выполнение.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-400 font-medium mb-1">Тип судьи</label>
                <select
                  value={formJudgeType}
                  onChange={(e) => setFormJudgeType(e.target.value as any)}
                  className="w-full bg-slate-900 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500"
                >
                  <option value="model">Прямая модель (LLM или JEV SystemOne)</option>
                  <option value="profile">Профиль маршрутизации (Fallback Route)</option>
                </select>
              </div>

              {formJudgeType === "profile" ? (
                <div>
                  <label className="block text-slate-400 font-medium mb-1">Профиль маршрутизации</label>
                  <select
                    value={formJudgeRoutingProfileId || ""}
                    onChange={(e) => setFormJudgeRoutingProfileId(parseInt(e.target.value, 10))}
                    className="w-full bg-slate-900 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500"
                  >
                    {routingProfiles.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} (route/{r.slug})
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div>
                  <label className="block text-slate-400 font-medium mb-1">Провайдер судьи</label>
                  <select
                    value={formJudgeProviderId}
                    onChange={(e) => {
                      const pid = parseInt(e.target.value, 10);
                      setFormJudgeProviderId(pid);
                      const hiddenIds = getHiddenModelIds();
                      const pm = models.find((m) => m.provider_id === pid && isModelVisible(m, hiddenIds));
                      if (pm) setFormJudgeModelId(pm.id);
                    }}
                    className="w-full bg-slate-900 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500"
                  >
                    {visibleJudgeProviders.map((pr) => {
                      const count = getProviderVisibleCount(pr.id);
                      return (
                        <option key={pr.id} value={pr.id}>
                          {pr.name} ({count} {count === 1 ? "модель" : count >= 2 && count <= 4 ? "модели" : "моделей"})
                        </option>
                      );
                    })}
                  </select>
                </div>
              )}
            </div>

            {formJudgeType === "model" && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 font-medium mb-1">
                    Модель судьи ({judgeModels.length} видимых)
                  </label>
                  <select
                    value={formJudgeModelId}
                    onChange={(e) => setFormJudgeModelId(parseInt(e.target.value, 10))}
                    className="w-full bg-slate-900 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500 font-mono text-xs"
                    disabled={judgeModels.length === 0}
                  >
                    {judgeModels.length === 0 ? (
                      <option value="">Нет видимых моделей из каталога для этого провайдера</option>
                    ) : (
                      judgeModels.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.display_name || m.provider_model_id} {m.model_type === "jev" ? "⚡ [JEV]" : ""}
                        </option>
                      ))
                    )}
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 font-medium mb-1">Учетные данные (Ключ / Группа)</label>
                  <select
                    value={formJudgeCredTarget}
                    onChange={(e) => setFormJudgeCredTarget(e.target.value)}
                    className="w-full bg-slate-900 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500"
                  >
                    <option value="all">Авто (Любой активный ключ провайдера)</option>
                    {judgeGroups.map((g) => (
                      <option key={g} value={`group_${g}`}>
                        Группа: {g}
                      </option>
                    ))}
                    {judgeCredentials.map((c) => (
                      <option key={c.id} value={`cred_${c.id}`}>
                        Ключ: {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {formJudgeType === "model" && (
                <div>
                  <label className="block text-slate-400 font-medium mb-1 flex items-center gap-1.5">
                    <Brain size={12} className="text-purple-400" />
                    <span>Размышление судьи</span>
                  </label>
                  <div className="flex gap-2">
                    <select
                      value={formJudgeThinkingPreset}
                      onChange={(e) => setFormJudgeThinkingPreset(e.target.value)}
                      className="flex-1 bg-slate-900 border border-white/[0.09] rounded-xl px-2.5 py-2 text-white text-xs focus:outline-none focus:border-amber-500"
                    >
                      {REASONING_EFFORT_PRESETS.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                    {formJudgeThinkingPreset === "custom" && (
                      <input
                        type="text"
                        value={formJudgeCustomThinking}
                        onChange={(e) => setFormJudgeCustomThinking(e.target.value)}
                        placeholder="e.g. high"
                        className="w-24 bg-slate-900 border border-purple-500/40 rounded-xl px-2 py-2 text-purple-200 font-mono text-xs"
                      />
                    )}
                  </div>
                </div>
              )}

              <div>
                <label className="block text-slate-400 font-medium mb-1">Температура судьи</label>
                <div className="flex gap-2">
                  <select
                    value={formJudgeTempPreset}
                    onChange={(e) => setFormJudgeTempPreset(e.target.value)}
                    className="flex-1 bg-slate-900 border border-white/[0.09] rounded-xl px-2.5 py-2 text-white text-xs focus:outline-none focus:border-amber-500"
                  >
                    {JUDGE_TEMP_PRESETS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label} - {p.desc}
                      </option>
                    ))}
                    <option value="custom">Пользовательская...</option>
                  </select>
                  {formJudgeTempPreset === "custom" && (
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="2"
                      value={formJudgeCustomTemp}
                      onChange={(e) => setFormJudgeCustomTemp(e.target.value)}
                      placeholder="0.1"
                      className="w-20 bg-slate-900 border border-white/[0.09] rounded-xl px-2 py-2 text-white font-mono text-xs"
                    />
                  )}
                </div>
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">Резервный кандидат</label>
                <select
                  value={formFallbackCandidateId || ""}
                  onChange={(e) => setFormFallbackCandidateId(e.target.value ? parseInt(e.target.value, 10) : undefined)}
                  className="w-full bg-slate-900 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500 text-xs"
                >
                  <option value="">По умолчанию (Кандидат #1)</option>
                  {formCandidates.map((c, idx) => (
                    <option key={c.id || idx} value={c.id || idx}>
                      #{idx + 1}: {c.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-slate-400 font-medium mb-1">
                Инструкция / Системный промпт для судьи (опционально)
              </label>
              <textarea
                rows={2}
                value={formSystemPrompt}
                onChange={(e) => setFormSystemPrompt(e.target.value)}
                placeholder="Например: Для запросов по базам данных SQL отдавай предпочтение Кандидату А, а для креативного копирайтинга Кандидату Б."
                className="w-full bg-slate-900 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500 text-xs"
              />
            </div>
          </div>

          {/* Section: Candidates Manager */}
          <div className="p-4 bg-slate-950/60 border border-white/[0.08] rounded-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-bold text-slate-200 text-xs flex items-center gap-2">
                  <Layers size={15} className="text-amber-400" /> Пул кандидатов ({formCandidates.length})
                </h4>
                <p className="text-[11px] text-slate-400">
                  Добавьте модели с указанием их специализаций и уровня сложности
                </p>
              </div>
            </div>

            {/* Configured Candidates List */}
            {formCandidates.length > 0 ? (
              <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                {formCandidates.map((c, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 bg-slate-900 border border-white/[0.06] rounded-xl text-xs"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="w-5 h-5 rounded-full bg-slate-800 text-slate-300 font-mono text-[10px] flex items-center justify-center shrink-0">
                        {idx + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="font-semibold text-slate-200 flex items-center gap-2 flex-wrap">
                          <span className="truncate">{c.label}</span>
                          {c.thinking_effort && (
                            <span
                              className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-purple-500/15 text-purple-300 border border-purple-500/25 flex items-center gap-1"
                              title={`Уровень размышления: ${c.thinking_effort}`}
                            >
                              <Brain size={10} className="text-purple-400 shrink-0" />
                              <span>{c.thinking_effort}</span>
                            </span>
                          )}
                          {getComplexityBadge(c.complexity_level)}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono truncate">
                          {c.candidate_type === "profile"
                            ? `route/${c.target_profile_slug}`
                            : c.model_name || c.canonical_slug}
                        </div>
                        {c.task_types && c.task_types.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {c.task_types.map((t) => (
                              <span key={t} className="px-1.5 py-0.2 bg-slate-800 text-slate-300 rounded text-[9px]">
                                #{t}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-1 shrink-0 ml-2">
                      <button
                        type="button"
                        onClick={() => handleEditCandidate(idx)}
                        className="p-1 hover:bg-amber-500/20 text-slate-400 hover:text-amber-300 rounded transition-colors"
                        title="Редактировать кандидата"
                      >
                        <Edit2 size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleMoveCandidate(idx, "up")}
                        disabled={idx === 0}
                        className="p-1 hover:bg-slate-800 disabled:opacity-30 rounded text-slate-400 hover:text-white"
                        title="Поднять выше"
                      >
                        <ArrowUp size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleMoveCandidate(idx, "down")}
                        disabled={idx === formCandidates.length - 1}
                        className="p-1 hover:bg-slate-800 disabled:opacity-30 rounded text-slate-400 hover:text-white"
                        title="Опустить ниже"
                      >
                        <ArrowDown size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveCandidate(idx)}
                        className="p-1 hover:bg-rose-500/20 text-rose-400 rounded transition-colors"
                        title="Удалить кандидата"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 text-center text-xs text-slate-500 border border-dashed border-white/[0.08] rounded-xl">
                Кандидаты еще не добавлены. Заполните форму ниже для добавления первого кандидата.
              </div>
            )}

            {/* Add Candidate Form Box */}
            <div className="p-3.5 bg-slate-900/90 border border-white/[0.07] rounded-xl space-y-3">
              <span className="font-semibold text-slate-300 text-xs flex items-center gap-1.5">
                <Plus size={13} className="text-amber-400" /> Добавить кандидата
              </span>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Тип цели</label>
                  <select
                    value={candType}
                    onChange={(e) => setCandType(e.target.value as any)}
                    className="w-full bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-white"
                  >
                    <option value="model">Модель (Прямой вызов)</option>
                    <option value="profile">Профиль (Fallback Route)</option>
                  </select>
                </div>

                {candType === "profile" ? (
                  <div className="sm:col-span-2">
                    <label className="block text-[11px] text-slate-400 mb-1">Маршрут</label>
                    <select
                      value={candTargetProfileId}
                      onChange={(e) => setCandTargetProfileId(parseInt(e.target.value, 10))}
                      className="w-full bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-white"
                    >
                      {routingProfiles.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} (route/{r.slug})
                        </option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <>
                    <div>
                      <label className="block text-[11px] text-slate-400 mb-1">Провайдер</label>
                      <select
                        value={candProviderId}
                        onChange={(e) => {
                          const pid = parseInt(e.target.value, 10);
                          setCandProviderId(pid);
                          const hiddenIds = getHiddenModelIds();
                          const m = models.find((mod) => mod.provider_id === pid && isModelVisible(mod, hiddenIds));
                          if (m) setCandModelId(m.id);
                        }}
                        className="w-full bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-white"
                      >
                        {visibleCandProviders.map((pr) => {
                          const count = getProviderVisibleCount(pr.id);
                          return (
                            <option key={pr.id} value={pr.id}>
                              {pr.name} ({count} {count === 1 ? "модель" : count >= 2 && count <= 4 ? "модели" : "моделей"})
                            </option>
                          );
                        })}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] text-slate-400 mb-1">
                        Модель ({candModels.length} видимых)
                      </label>
                      <select
                        value={candModelId}
                        onChange={(e) => setCandModelId(parseInt(e.target.value, 10))}
                        className="w-full bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-white font-mono text-xs"
                        disabled={candModels.length === 0}
                      >
                        {candModels.length === 0 ? (
                          <option value="">Нет видимых моделей из каталога для этого провайдера</option>
                        ) : (
                          candModels.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.display_name || m.provider_model_id}
                            </option>
                          ))
                        )}
                      </select>
                    </div>
                  </>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Метка (Label)</label>
                  <input
                    type="text"
                    value={candLabel}
                    onChange={(e) => setCandLabel(e.target.value)}
                    placeholder="Например: Senior Coder / Fast Chat"
                    className="w-full bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-white text-xs"
                  />
                </div>

                <div>
                  <label className="block text-[11px] text-slate-400 mb-1 flex items-center justify-between">
                    <span>Подходящая сложность запроса</span>
                    {candComplexityPreset === "custom" && (
                      <span className="text-[10px] text-amber-400 font-mono">Свой вариант</span>
                    )}
                  </label>
                  <div className="space-y-1.5">
                    <select
                      value={candComplexityPreset}
                      onChange={(e) => setCandComplexityPreset(e.target.value)}
                      className="w-full bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-white text-xs"
                    >
                      {COMPLEXITY_PRESETS.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.label} {p.desc ? `— ${p.desc}` : ""}
                        </option>
                      ))}
                    </select>

                    {candComplexityPreset === "custom" && (
                      <input
                        type="text"
                        value={candCustomComplexity}
                        onChange={(e) => setCandCustomComplexity(e.target.value)}
                        placeholder="Впишите свой уровень сложности (e.g. выше среднего, hard)..."
                        className="w-full bg-slate-950 border border-amber-500/40 focus:border-amber-400 rounded-lg px-2.5 py-1.5 text-amber-200 text-xs font-medium placeholder:text-slate-500"
                        autoFocus
                      />
                    )}
                  </div>
                </div>
              </div>

              {/* Candidate Model Parameters: Reasoning Effort & Temperature */}
              {candType === "model" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 p-2.5 bg-slate-950/40 rounded-xl border border-white/[0.04]">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1 flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-slate-300">
                        <Brain size={12} className="text-purple-400" />
                        <span>Уровень размышления (Reasoning Effort)</span>
                      </span>
                      {candThinkingPreset === "custom" && (
                        <span className="text-[10px] text-purple-400 font-mono">Custom</span>
                      )}
                    </label>
                    <div className="space-y-1.5">
                      <select
                        value={candThinkingPreset}
                        onChange={(e) => setCandThinkingPreset(e.target.value)}
                        className="w-full bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-white text-xs"
                      >
                        {REASONING_EFFORT_PRESETS.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.label} — {p.desc}
                          </option>
                        ))}
                      </select>
                      {candThinkingPreset === "custom" && (
                        <input
                          type="text"
                          value={candCustomThinking}
                          onChange={(e) => setCandCustomThinking(e.target.value)}
                          placeholder="Впишите свой уровень (e.g. minimal, maximum, budget:2048)..."
                          className="w-full bg-slate-950 border border-purple-500/40 focus:border-purple-400 rounded-lg px-2.5 py-1.5 text-purple-200 text-xs font-mono placeholder:text-slate-500"
                          autoFocus
                        />
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1 flex items-center gap-1.5 text-slate-300">
                      <Thermometer size={12} className="text-orange-400" />
                      <span>Температура кандидата (опционально)</span>
                    </label>
                    <div className="flex gap-2">
                      <select
                        value={candTempPreset}
                        onChange={(e) => setCandTempPreset(e.target.value)}
                        className="flex-1 bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-white text-xs"
                      >
                        {JUDGE_TEMP_PRESETS.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.label} — {p.desc}
                          </option>
                        ))}
                        <option value="custom">Пользовательская...</option>
                      </select>
                      {candTempPreset === "custom" && (
                        <input
                          type="number"
                          step="0.05"
                          min="0"
                          max="2"
                          value={candCustomTemp}
                          onChange={(e) => setCandCustomTemp(e.target.value)}
                          placeholder="0.7"
                          className="w-20 bg-slate-950 border border-white/[0.08] rounded-lg px-2 py-1.5 text-white font-mono text-xs"
                        />
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Task Types Tags */}
              <div className="space-y-1.5">
                <label className="block text-[11px] text-slate-400 font-medium">
                  Подходящие типы задач (теги для судьи)
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {TASK_TYPE_PRESETS.map((preset) => {
                    const active = candTaskTypes.includes(preset);
                    return (
                      <button
                        type="button"
                        key={preset}
                        onClick={() => toggleTaskTag(preset)}
                        className={`px-2 py-0.5 rounded-lg text-[10px] font-mono transition-colors cursor-pointer border ${
                          active
                            ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                            : "bg-slate-950 text-slate-400 border-white/[0.06] hover:bg-slate-800 hover:text-white"
                        }`}
                      >
                        #{preset}
                      </button>
                    );
                  })}
                </div>
                <div className="flex gap-2 pt-1">
                  <input
                    type="text"
                    value={customTagInput}
                    onChange={(e) => setCustomTagInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddCustomTag();
                      }
                    }}
                    placeholder="Добавить свой тег (e.g. rust, sql)..."
                    className="flex-1 bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1 text-white text-xs"
                  />
                  <button
                    type="button"
                    onClick={handleAddCustomTag}
                    className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs"
                  >
                    Добавить тег
                  </button>
                </div>
              </div>

              {/* Candidate Description for Judge */}
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">
                  Описание для судьи (подсказка, когда выбирать именно этого кандидата)
                </label>
                <textarea
                  rows={2}
                  value={candDescription}
                  onChange={(e) => setCandDescription(e.target.value)}
                  placeholder="Например: Выбирать для задач по архитектуре ПО, компиляторам и сложной математике."
                  className="w-full bg-slate-950 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-white text-xs"
                />
              </div>

              <div className="flex justify-end pt-1">
                <button
                  type="button"
                  onClick={handleAddCandidate}
                  disabled={candType === "model" && (!candModelId || candModels.length === 0)}
                  className="btn-press px-4 py-1.5 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed text-slate-950 rounded-xl font-bold text-xs flex items-center gap-1.5 cursor-pointer shadow-md shadow-amber-500/10"
                >
                  <Plus size={14} /> Включить в пул кандидатов
                </button>
              </div>
            </div>
          </div>

          {/* Modal Footer */}
          <div className="flex justify-end gap-2 pt-2 border-t border-white/[0.07]">
            <button
              onClick={() => setIsModalOpen(false)}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl font-medium"
            >
              Отмена
            </button>
            <button
              onClick={handleSaveProfile}
              className="btn-press px-5 py-2 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 hover:from-amber-400 hover:to-orange-500 text-white rounded-xl font-semibold shadow-lg shadow-amber-500/20"
            >
              Сохранить профиль
            </button>
          </div>
        </div>
      </Modal>

      {/* Live Test Judge Modal */}
      <Modal
        isOpen={isTestModalOpen}
        onClose={() => setIsTestModalOpen(false)}
        title={`Тестирование судьи: ${testingProfile?.name || ""}`}
        maxWidth="lg"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-400 text-[11px]">
            Введите пример запроса, чтобы проверить, как модель-судья оценивает сложность и какого кандидата она выбирает.
          </p>

          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() =>
                setTestPrompt("Напиши реализацию распределенного алгоритма Paxos на Rust с потокобезопасными очередями.")
              }
              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px]"
            >
              🔥 Сложный код (Rust / Paxos)
            </button>
            <button
              type="button"
              onClick={() => setTestPrompt("Привет! Расскажи короткую шутку про программистов.")}
              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px]"
            >
              💬 Простой чат (Привет / Шутка)
            </button>
            <button
              type="button"
              onClick={() =>
                setTestPrompt("Докажи теорему Ферма для частного случая n=4 с математическими выкладками.")
              }
              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px]"
            >
              📐 Математика & Теоремы
            </button>
            <button
              type="button"
              onClick={() =>
                setTestPrompt("Переведи данный юридический договор с английского на русский язык.")
              }
              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px]"
            >
              🌐 Перевод текста
            </button>
          </div>

          <div>
            <textarea
              rows={4}
              value={testPrompt}
              onChange={(e) => setTestPrompt(e.target.value)}
              placeholder="Введите любой промпт для классификации судьей..."
              className="w-full bg-slate-950 border border-white/[0.09] rounded-xl px-3 py-2 text-white focus:outline-none focus:border-amber-500 text-xs"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={runTestEvaluation}
              disabled={testingInProgress || !testPrompt.trim()}
              className="btn-press px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 disabled:opacity-50 text-white rounded-xl font-semibold flex items-center gap-2 cursor-pointer shadow-lg shadow-amber-500/20"
            >
              <Scale size={14} className={testingInProgress ? "animate-spin" : ""} />
              <span>{testingInProgress ? "Оценка запроса..." : "Выполнить оценку судьей"}</span>
            </button>
          </div>

          {testError && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-xs">
              ❌ Ошибка тестирования: {testError}
            </div>
          )}

          {testResult && (
            <div className="p-4 bg-slate-950/80 border border-amber-500/30 rounded-2xl space-y-3">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                <span className="font-bold text-amber-400 text-xs flex items-center gap-1.5">
                  <CheckCircle2 size={14} className="text-emerald-400" /> Вердикт судьи ({testResult.status})
                </span>
                <span className="text-[11px] font-mono text-slate-400">{testResult.latency_ms} ms</span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <span className="text-slate-400 block text-[11px]">Выбранный кандидат:</span>
                  <span className="font-bold text-slate-100 text-sm">{testResult.selected_candidate_label}</span>
                  <div className="text-[11px] font-mono text-indigo-300">{testResult.selected_target}</div>
                </div>
                <div>
                  <span className="text-slate-400 block text-[11px]">Оценка сложности & Тип:</span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    {getComplexityBadge(testResult.estimated_complexity)}
                    {testResult.detected_task_type && (
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-mono bg-slate-800 text-slate-300 border border-white/[0.06]">
                        #{testResult.detected_task_type}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {testResult.judge_reasoning && (
                <div className="bg-slate-900/90 p-3 rounded-xl border border-white/[0.05] text-[11px] space-y-1">
                  <span className="font-semibold text-slate-400 uppercase tracking-wider block text-[10px]">
                    Обоснование решения судьи:
                  </span>
                  <p className="text-slate-200 italic">{testResult.judge_reasoning}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default JudgeRoutingPage;
