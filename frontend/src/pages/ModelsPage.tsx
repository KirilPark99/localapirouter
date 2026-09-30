import React, { useEffect, useState, useMemo, useRef } from "react";
import {
  Boxes,
  RefreshCw,
  Search,
  Plus,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Cpu,
  CheckCircle2,
  XCircle,
  Eye,
  EyeOff,
  Filter,
  CheckSquare,
  Square,
  MinusSquare,
  Sparkles,
  Brain,
  Thermometer,
  ArrowUpDown,
  SlidersHorizontal,
  Copy,
  Check,
  Play,
  X,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { DiscoveredModel, Provider } from "../types";
import { Modal } from "../components/Modal";
import { ModelIntelligenceBadge } from "../components/ModelIntelligenceBadge";
import { useI18n } from "../i18n";

export const CONTEXT_PRESETS = [
  { label: "4K", value: 4096 },
  { label: "8K", value: 8192 },
  { label: "16K", value: 16384 },
  { label: "32K", value: 32768 },
  { label: "64K", value: 65536 },
  { label: "128K", value: 131072 },
  { label: "200K", value: 200000 },
  { label: "256K", value: 262144 },
  { label: "512K", value: 524288 },
  { label: "1M", value: 1048576 },
  { label: "2M", value: 2097152 },
];

export const REASONING_PRESETS = [
  { label: "none", title: "none (off)", desc: "No reasoning" },
  { label: "low", title: "low", desc: "Low effort" },
  { label: "medium", title: "medium", desc: "Medium effort" },
  { label: "high", title: "high", desc: "High effort" },
  { label: "auto", title: "auto", desc: "Automatic" },
];

export const TEMPERATURE_PRESETS = [
  { label: "default", value: null, title: "Default", desc: "Provider default" },
  { label: "0.0", value: 0.0, title: "0.0", desc: "Deterministic / Code" },
  { label: "0.2", value: 0.2, title: "0.2", desc: "Precise" },
  { label: "0.5", value: 0.5, title: "0.5", desc: "Balanced" },
  { label: "0.7", value: 0.7, title: "0.7", desc: "Standard (Chat)" },
  { label: "1.0", value: 1.0, title: "1.0", desc: "Creative" },
  { label: "1.5", value: 1.5, title: "1.5", desc: "Experimental" },
];

interface ProviderGroup {
  provider: Provider;
  models: DiscoveredModel[];
}

export const ModelsPage: React.FC = () => {
  const { t } = useI18n();
  const [models, setModels] = useState<DiscoveredModel[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchingAll, setFetchingAll] = useState(false);
  const [refreshingProviderId, setRefreshingProviderId] = useState<number | null>(null);

  // Search query
  const [search, setSearch] = useState("");

  // Display filter: "visible" | "all" | "hidden"
  const [visibilityFilter, setVisibilityFilter] = useState<"visible" | "all" | "hidden">("visible");

  // Intelligence & Rating filter: "all" | "rated" | "high-intel" | "top-coding" | "top-agentic"
  const [ratingFilter, setRatingFilter] = useState<"all" | "rated" | "high-intel" | "top-coding" | "top-agentic">("all");

  // Sorting state
  const [sortBy, setSortBy] = useState<"default" | "intel-desc" | "coding-desc" | "agentic-desc" | "context-desc" | "name-asc">("default");

  // Syncing Artificial Analysis ratings state
  const [syncingRatings, setSyncingRatings] = useState(false);

  // Selection set of model IDs
  const [selectedModelIds, setSelectedModelIds] = useState<Set<number>>(new Set());
  const lastSelectedModelIdRef = useRef<number | null>(null);
  const [isTopActionsOpen, setIsTopActionsOpen] = useState(false);

  // Collapsible state for each provider group
  const [collapsedProviders, setCollapsedProviders] = useState<Record<number, boolean>>({});

  // Batch action processing state
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; ok: boolean } | null>(null);

  // Newly discovered models after refresh
  const [newlyDiscoveredModels, setNewlyDiscoveredModels] = useState<DiscoveredModel[]>([]);
  const [isNewModelsCollapsed, setIsNewModelsCollapsed] = useState(false);
  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);

  // Manual model modal state
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [manualProviderId, setManualProviderId] = useState<number>(1);
  const [manualModelId, setManualModelId] = useState("");
  const [manualDisplayName, setManualDisplayName] = useState("");
  const [manualContextLength, setManualContextLength] = useState("128000");

  // Context length modal state
  const [contextModalModel, setContextModalModel] = useState<DiscoveredModel | null>(null);
  const [isBatchContextModalOpen, setIsBatchContextModalOpen] = useState(false);
  const [selectedContextPreset, setSelectedContextPreset] = useState<number | "custom">("custom");
  const [customContextInput, setCustomContextInput] = useState<string>("");
  const [savingContext, setSavingContext] = useState(false);

  // Reasoning effort modal state
  const [reasoningModalModel, setReasoningModalModel] = useState<DiscoveredModel | null>(null);
  const [isBatchReasoningModalOpen, setIsBatchReasoningModalOpen] = useState(false);
  const [selectedReasoningPreset, setSelectedReasoningPreset] = useState<string>("custom");
  const [customReasoningInput, setCustomReasoningInput] = useState<string>("");
  const [reasoningValidationError, setReasoningValidationError] = useState<string | null>(null);
  const [savingReasoning, setSavingReasoning] = useState(false);

  // Temperature modal state
  const [tempModalModel, setTempModalModel] = useState<DiscoveredModel | null>(null);
  const [isBatchTempModalOpen, setIsBatchTempModalOpen] = useState(false);
  const [selectedTempPreset, setSelectedTempPreset] = useState<string>("custom");
  const [customTempInput, setCustomTempInput] = useState<string>("");
  const [tempValidationError, setTempValidationError] = useState<string | null>(null);
  const [savingTemp, setSavingTemp] = useState(false);

  const loadModels = async (): Promise<DiscoveredModel[]> => {
    setLoading(true);
    try {
      let [m, p] = await Promise.all([
        apiRequest<DiscoveredModel[]>("/api/admin/models"),
        apiRequest<Provider[]>("/api/admin/providers"),
      ]);

      // One-time migration of legacy localStorage hidden models to backend
      const storedHidden = localStorage.getItem("myairouter_hidden_model_ids");
      if (storedHidden) {
        try {
          const ids: number[] = JSON.parse(storedHidden);
          if (Array.isArray(ids) && ids.length > 0) {
            await apiRequest("/api/admin/models/batch-update", {
              method: "POST",
              body: JSON.stringify({ model_ids: ids, is_visible: false }),
            });
            m = await apiRequest<DiscoveredModel[]>("/api/admin/models");
          }
          localStorage.removeItem("myairouter_hidden_model_ids");
        } catch (migErr) {
          console.error("Failed to migrate localStorage hidden models:", migErr);
        }
      }

      setModels(m);
      setProviders(p);
      if (p.length > 0 && !manualProviderId) {
        setManualProviderId(p[0].id);
      }

      // Restore session new models if available
      const savedNewRaw = sessionStorage.getItem("myairouter_new_models");
      if (savedNewRaw) {
        try {
          const savedSlugs: string[] = JSON.parse(savedNewRaw);
          if (Array.isArray(savedSlugs) && savedSlugs.length > 0) {
            const matched = m.filter((item) => savedSlugs.includes(item.canonical_slug));
            if (matched.length > 0) {
              setNewlyDiscoveredModels(matched);
            }
          }
        } catch (e) {
          console.error("Failed to parse saved new models from sessionStorage", e);
        }
      }

      return m;
    } catch (err) {
      console.error(err);
      return [];
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadModels();
  }, []);

  const toggleHideModel = async (model: DiscoveredModel) => {
    const nextVisible = model.is_visible === false;
    try {
      await apiRequest(`/api/admin/models/${model.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_visible: nextVisible }),
      });
      setModels((prev) =>
        prev.map((item) => (item.id === model.id ? { ...item, is_visible: nextVisible } : item))
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((item) => (item.id === model.id ? { ...item, is_visible: nextVisible } : item))
      );
    } catch (err: any) {
      console.error("Failed to toggle model visibility:", err);
      setStatusMessage({ text: err.message || "Failed to update visibility", ok: false });
    }
  };

  // Refresh models for ALL providers
  const handleFetchAll = async () => {
    setFetchingAll(true);
    setStatusMessage(null);
    try {
      const prevSlugs = new Set(models.map((m) => m.canonical_slug));
      const prevIds = new Set(models.map((m) => m.id));

      const res = await apiRequest<{
        total_credentials?: number;
        success?: number;
        failed?: number;
        errors?: Record<string, string>;
        new_models_count?: number;
        new_models?: string[];
      }>("/api/admin/models/fetch-all", { method: "POST" });

      const refreshed = await loadModels();

      const serverNewSlugs = new Set(res.new_models || []);
      const newFound = (refreshed || []).filter(
        (m) =>
          !prevSlugs.has(m.canonical_slug) ||
          !prevIds.has(m.id) ||
          serverNewSlugs.has(m.canonical_slug)
      );

      if (newFound.length > 0) {
        setNewlyDiscoveredModels(newFound);
        setIsNewModelsCollapsed(false);
        sessionStorage.setItem(
          "myairouter_new_models",
          JSON.stringify(newFound.map((m) => m.canonical_slug))
        );
        setStatusMessage({
          text: `Catalog update complete: found ${newFound.length} new models! List displayed at the top.`,
          ok: true,
        });
      } else {
        setStatusMessage({
          text: `Sync complete (${res.success || 0} providers synced). No new models found (all ${refreshed.length} models up to date).`,
          ok: true,
        });
      }
    } catch (err: any) {
      setStatusMessage({ text: err.message || "Failed to fetch all models", ok: false });
    } finally {
      setFetchingAll(false);
    }
  };

  // Sync latest intelligence ratings from Artificial Analysis
  const handleSyncRatings = async () => {
    setSyncingRatings(true);
    setStatusMessage(null);
    try {
      const res = await apiRequest<{ models_count: number; updated_at?: string }>("/api/admin/models/sync-ratings", {
        method: "POST",
      });
      await loadModels();
      setStatusMessage({
        text: `Ratings successfully synced from Artificial Analysis (${res.models_count || 0} models indexed)!`,
        ok: true,
      });
    } catch (err: any) {
      setStatusMessage({ text: err.message || "Failed to sync ratings from Artificial Analysis", ok: false });
    } finally {
      setSyncingRatings(false);
    }
  };

  // Refresh models for a SINGLE provider only
  const handleFetchProvider = async (providerId: number, providerName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRefreshingProviderId(providerId);
    setStatusMessage(null);
    try {
      const prevSlugs = new Set(models.map((m) => m.canonical_slug));
      const prevIds = new Set(models.map((m) => m.id));

      const res = await apiRequest<{
        total_credentials?: number;
        success?: number;
        failed?: number;
        errors?: Record<string, string>;
        new_models_count?: number;
        new_models?: string[];
      }>(`/api/admin/models/fetch-provider/${providerId}`, { method: "POST" });

      const refreshed = await loadModels();

      const serverNewSlugs = new Set(res.new_models || []);
      const newFound = (refreshed || []).filter(
        (m) =>
          m.provider_id === providerId &&
          (!prevSlugs.has(m.canonical_slug) ||
            !prevIds.has(m.id) ||
            serverNewSlugs.has(m.canonical_slug))
      );

      if (newFound.length > 0) {
        setNewlyDiscoveredModels((prev) => {
          const existingSlugs = new Set(prev.map((m) => m.canonical_slug));
          const merged = [...newFound.filter((m) => !existingSlugs.has(m.canonical_slug)), ...prev];
          sessionStorage.setItem(
            "myairouter_new_models",
            JSON.stringify(merged.map((m) => m.canonical_slug))
          );
          return merged;
        });
        setIsNewModelsCollapsed(false);
        setStatusMessage({
          text: `Found ${newFound.length} new models for ${providerName}! Added to top of catalog.`,
          ok: true,
        });
      } else {
        setStatusMessage({
          text: `Models checked for ${providerName}. No new models found.`,
          ok: true,
        });
      }
    } catch (err: any) {
      setStatusMessage({ text: `Failed to refresh ${providerName}: ${err.message}`, ok: false });
    } finally {
      setRefreshingProviderId(null);
    }
  };

  const handleToggleEnabled = async (m: DiscoveredModel) => {
    try {
      await apiRequest(`/api/admin/models/${m.id}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: !m.enabled }),
      });
      setModels((prev) =>
        prev.map((item) => (item.id === m.id ? { ...item, enabled: !m.enabled } : item))
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((item) => (item.id === m.id ? { ...item, enabled: !m.enabled } : item))
      );
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleAddManual = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const created = await apiRequest<DiscoveredModel>("/api/admin/models/manual", {
        method: "POST",
        body: JSON.stringify({
          provider_id: manualProviderId,
          provider_model_id: manualModelId,
          display_name: manualDisplayName || manualModelId,
          context_length: parseInt(manualContextLength) || null,
        }),
      });
      setIsManualModalOpen(false);
      setManualModelId("");
      setManualDisplayName("");
      const refreshed = await loadModels();
      if (created) {
        const found = (refreshed || []).find(
          (m) => m.id === created.id || m.canonical_slug === created.canonical_slug
        );
        if (found) {
          setNewlyDiscoveredModels((prev) => [found, ...prev.filter((m) => m.id !== found.id)]);
        }
      }
      setStatusMessage({ text: "Model added manually successfully!", ok: true });
    } catch (err: any) {
      alert(err.message);
    }
  };

  const dismissNewModels = () => {
    setNewlyDiscoveredModels([]);
    sessionStorage.removeItem("myairouter_new_models");
  };

  const selectAllNewModels = () => {
    setSelectedModelIds((prev) => {
      const next = new Set(prev);
      newlyDiscoveredModels.forEach((m) => next.add(m.id));
      return next;
    });
  };

  const handleCopySlug = (slug: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    navigator.clipboard.writeText(slug);
    setCopiedSlug(slug);
    setTimeout(() => setCopiedSlug(null), 2000);
  };

  const jumpToModelInCatalog = (m: DiscoveredModel) => {
    setCollapsedProviders((prev) => ({ ...prev, [m.provider_id]: false }));
    setTimeout(() => {
      const el = document.getElementById(`model-row-${m.id}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("ring-2", "ring-indigo-500", "bg-indigo-950/50");
        setTimeout(() => {
          el.classList.remove("ring-2", "ring-indigo-500", "bg-indigo-950/50");
        }, 2500);
      }
    }, 120);
  };

  const openContextModal = (model: DiscoveredModel) => {
    setContextModalModel(model);
    const currentVal = model.context_length;
    if (currentVal) {
      const match = CONTEXT_PRESETS.find((p) => p.value === currentVal);
      setSelectedContextPreset(match ? match.value : "custom");
      setCustomContextInput(currentVal.toString());
    } else {
      setSelectedContextPreset(131072);
      setCustomContextInput("131072");
    }
  };

  const openBatchContextModal = () => {
    setIsBatchContextModalOpen(true);
    setSelectedContextPreset(131072);
    setCustomContextInput("131072");
  };

  const handleSelectPreset = (val: number | "custom") => {
    setSelectedContextPreset(val);
    if (typeof val === "number") {
      setCustomContextInput(val.toString());
    }
  };

  const handleCustomInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setCustomContextInput(val);
    const num = parseInt(val, 10);
    const match = CONTEXT_PRESETS.find((p) => p.value === num);
    setSelectedContextPreset(match ? match.value : "custom");
  };

  const handleSaveModelContext = async (resetToDefault = false) => {
    if (!contextModalModel) return;
    setSavingContext(true);
    try {
      const parsedValue = resetToDefault ? 0 : (parseInt(customContextInput, 10) || null);
      const res = await apiRequest<DiscoveredModel>(`/api/admin/models/${contextModalModel.id}`, {
        method: "PUT",
        body: JSON.stringify({ context_length: parsedValue }),
      });
      setModels((prev) =>
        prev.map((item) =>
          item.id === contextModalModel.id ? { ...item, context_length: res.context_length } : item
        )
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((item) =>
          item.id === contextModalModel.id ? { ...item, context_length: res.context_length } : item
        )
      );
      setStatusMessage({
        text: resetToDefault
          ? `Context window for ${contextModalModel.canonical_slug} reset to default.`
          : `Context window for ${contextModalModel.canonical_slug} set to ${parsedValue?.toLocaleString()} tokens.`,
        ok: true,
      });
      setContextModalModel(null);
    } catch (err: any) {
      alert("Failed to save context length: " + err.message);
    } finally {
      setSavingContext(false);
    }
  };

  const handleSaveBatchContext = async (resetToDefault = false) => {
    if (selectedModelIds.size === 0) return;
    setSavingContext(true);
    try {
      const parsedValue = resetToDefault ? 0 : (parseInt(customContextInput, 10) || null);
      await apiRequest("/api/admin/models/batch-update", {
        method: "POST",
        body: JSON.stringify({
          model_ids: Array.from(selectedModelIds),
          context_length: parsedValue,
        }),
      });
      setModels((prev) =>
        prev.map((item) =>
          selectedModelIds.has(item.id)
            ? { ...item, context_length: parsedValue ? parsedValue : undefined }
            : item
        )
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((item) =>
          selectedModelIds.has(item.id)
            ? { ...item, context_length: parsedValue ? parsedValue : undefined }
            : item
        )
      );
      setStatusMessage({
        text: resetToDefault
          ? `Context window reset to default for ${selectedModelIds.size} models.`
          : `Context window set to ${parsedValue?.toLocaleString()} tokens for ${selectedModelIds.size} models.`,
        ok: true,
      });
      setIsBatchContextModalOpen(false);
    } catch (err: any) {
      alert("Batch update failed: " + err.message);
    } finally {
      setSavingContext(false);
    }
  };

  const openReasoningModal = (model: DiscoveredModel) => {
    setReasoningModalModel(model);
    setReasoningValidationError(null);
    const currentVal = model.reasoning_effort?.toLowerCase().trim();
    if (currentVal) {
      const match = REASONING_PRESETS.find((p) => p.label === currentVal);
      if (match) {
        setSelectedReasoningPreset(match.label);
        setCustomReasoningInput(match.label);
      } else {
        setSelectedReasoningPreset("custom");
        setCustomReasoningInput(currentVal);
      }
    } else {
      setSelectedReasoningPreset("none");
      setCustomReasoningInput("none");
    }
  };

  const openBatchReasoningModal = () => {
    setIsBatchReasoningModalOpen(true);
    setReasoningValidationError(null);
    setSelectedReasoningPreset("medium");
    setCustomReasoningInput("medium");
  };

  const handleSelectReasoningPreset = (val: string) => {
    setSelectedReasoningPreset(val);
    setReasoningValidationError(null);
    if (val !== "custom") {
      setCustomReasoningInput(val);
    }
  };

  const handleCustomReasoningInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const rawVal = e.target.value;
    if (/\d/.test(rawVal)) {
      setReasoningValidationError("Must be a single word with letters only, no numbers!");
    } else {
      setReasoningValidationError(null);
    }
    // Strictly strip digits and punctuation except hyphens/underscores
    const sanitized = rawVal.replace(/[0-9]/g, "").replace(/[^a-zA-Z_-]/g, "").toLowerCase();
    setCustomReasoningInput(sanitized);
    const match = REASONING_PRESETS.find((p) => p.label === sanitized);
    setSelectedReasoningPreset(match ? match.label : "custom");
  };

  const handleSaveModelReasoning = async (resetToDefault = false) => {
    if (!reasoningModalModel) return;
    setSavingReasoning(true);
    setReasoningValidationError(null);
    try {
      const targetVal = resetToDefault ? null : (customReasoningInput.trim() || null);
      if (!resetToDefault && targetVal && /\d/.test(targetVal)) {
        setReasoningValidationError("Must be a single word with letters only, no numbers!");
        setSavingReasoning(false);
        return;
      }
      const res = await apiRequest<DiscoveredModel>(`/api/admin/models/${reasoningModalModel.id}`, {
        method: "PUT",
        body: JSON.stringify({ reasoning_effort: targetVal }),
      });
      setModels((prev) =>
        prev.map((item) =>
          item.id === reasoningModalModel.id ? { ...item, reasoning_effort: res.reasoning_effort } : item
        )
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((item) =>
          item.id === reasoningModalModel.id ? { ...item, reasoning_effort: res.reasoning_effort } : item
        )
      );
      setStatusMessage({
        text: resetToDefault
          ? `Reasoning effort for ${reasoningModalModel.canonical_slug} reset to default.`
          : `Reasoning effort for ${reasoningModalModel.canonical_slug} set to "${targetVal}".`,
        ok: true,
      });
      setReasoningModalModel(null);
    } catch (err: any) {
      alert("Failed to save reasoning effort: " + err.message);
    } finally {
      setSavingReasoning(false);
    }
  };

  const handleSaveBatchReasoning = async (resetToDefault = false) => {
    if (selectedModelIds.size === 0) return;
    setSavingReasoning(true);
    setReasoningValidationError(null);
    try {
      const targetVal = resetToDefault ? null : (customReasoningInput.trim() || null);
      if (!resetToDefault && targetVal && /\d/.test(targetVal)) {
        setReasoningValidationError("Must be a single word with letters only, no numbers!");
        setSavingReasoning(false);
        return;
      }
      await apiRequest("/api/admin/models/batch-update", {
        method: "POST",
        body: JSON.stringify({
          model_ids: Array.from(selectedModelIds),
          reasoning_effort: targetVal,
        }),
      });
      setModels((prev) =>
        prev.map((item) =>
          selectedModelIds.has(item.id)
            ? { ...item, reasoning_effort: targetVal || undefined }
            : item
        )
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((item) =>
          selectedModelIds.has(item.id)
            ? { ...item, reasoning_effort: targetVal || undefined }
            : item
        )
      );
      setStatusMessage({
        text: resetToDefault
          ? `Reasoning effort reset to default for ${selectedModelIds.size} models.`
          : `Reasoning effort set to "${targetVal}" for ${selectedModelIds.size} models.`,
        ok: true,
      });
      setIsBatchReasoningModalOpen(false);
    } catch (err: any) {
      alert("Batch update failed: " + err.message);
    } finally {
      setSavingReasoning(false);
    }
  };

  const openTempModal = (model: DiscoveredModel) => {
    setTempModalModel(model);
    setTempValidationError(null);
    if (model.temperature === null || model.temperature === undefined) {
      setSelectedTempPreset("default");
      setCustomTempInput("");
    } else {
      const match = TEMPERATURE_PRESETS.find(
        (p) => p.value !== null && Math.abs(p.value - model.temperature!) < 0.001
      );
      setSelectedTempPreset(match ? match.label : "custom");
      setCustomTempInput(model.temperature.toString());
    }
  };

  const openBatchTempModal = () => {
    setIsBatchTempModalOpen(true);
    setTempValidationError(null);
    setSelectedTempPreset("0.7");
    setCustomTempInput("0.7");
  };

  const handleSelectTempPreset = (presetLabel: string) => {
    setSelectedTempPreset(presetLabel);
    setTempValidationError(null);
    const found = TEMPERATURE_PRESETS.find((p) => p.label === presetLabel);
    if (found) {
      if (found.value === null) {
        setCustomTempInput("");
      } else {
        setCustomTempInput(found.value.toString());
      }
    }
  };

  const handleCustomTempInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setCustomTempInput(val);
    setTempValidationError(null);
    if (val.trim() !== "") {
      const parsed = parseFloat(val);
      if (isNaN(parsed) || parsed < 0.0 || parsed > 2.0) {
        setTempValidationError("Temperature must be a valid number between 0.0 and 2.0");
      }
      const match = TEMPERATURE_PRESETS.find(
        (p) => p.value !== null && Math.abs(p.value - parsed) < 0.001
      );
      setSelectedTempPreset(match ? match.label : "custom");
    } else {
      setSelectedTempPreset("default");
    }
  };

  const handleSaveModelTemp = async (resetToDefault = false) => {
    if (!tempModalModel) return;
    setSavingTemp(true);
    setTempValidationError(null);
    try {
      let targetVal: number | null = null;
      if (!resetToDefault) {
        if (customTempInput.trim() !== "") {
          const parsed = parseFloat(customTempInput);
          if (isNaN(parsed) || parsed < 0.0 || parsed > 2.0) {
            setTempValidationError("Temperature must be in range 0.0 to 2.0");
            setSavingTemp(false);
            return;
          }
          targetVal = Math.round(parsed * 1000) / 1000;
        }
      }
      const res = await apiRequest<DiscoveredModel>(`/api/admin/models/${tempModalModel.id}`, {
        method: "PUT",
        body: JSON.stringify({ temperature: targetVal }),
      });
      setModels((prev) =>
        prev.map((item) =>
          item.id === tempModalModel.id ? { ...item, temperature: res.temperature } : item
        )
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((item) =>
          item.id === tempModalModel.id ? { ...item, temperature: res.temperature } : item
        )
      );
      setStatusMessage({
        text: resetToDefault || targetVal === null
          ? `Temperature for ${tempModalModel.canonical_slug} reset to default.`
          : `Temperature for ${tempModalModel.canonical_slug} set to ${targetVal}.`,
        ok: true,
      });
      setTempModalModel(null);
    } catch (err: any) {
      alert("Failed to save temperature: " + err.message);
    } finally {
      setSavingTemp(false);
    }
  };

  const handleSaveBatchTemp = async (resetToDefault = false) => {
    if (selectedModelIds.size === 0) return;
    setSavingTemp(true);
    setTempValidationError(null);
    try {
      let targetVal: number | null = null;
      if (!resetToDefault) {
        if (customTempInput.trim() !== "") {
          const parsed = parseFloat(customTempInput);
          if (isNaN(parsed) || parsed < 0.0 || parsed > 2.0) {
            setTempValidationError("Temperature must be in range 0.0 to 2.0");
            setSavingTemp(false);
            return;
          }
          targetVal = Math.round(parsed * 1000) / 1000;
        }
      }
      await apiRequest("/api/admin/models/batch-update", {
        method: "POST",
        body: JSON.stringify({
          model_ids: Array.from(selectedModelIds),
          temperature: targetVal,
        }),
      });
      setModels((prev) =>
        prev.map((item) =>
          selectedModelIds.has(item.id)
            ? { ...item, temperature: targetVal }
            : item
        )
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((item) =>
          selectedModelIds.has(item.id)
            ? { ...item, temperature: targetVal }
            : item
        )
      );
      setStatusMessage({
        text: resetToDefault || targetVal === null
          ? `Temperature reset to default for ${selectedModelIds.size} models.`
          : `Temperature set to ${targetVal} for ${selectedModelIds.size} models.`,
        ok: true,
      });
      setIsBatchTempModalOpen(false);
    } catch (err: any) {
      alert("Batch temperature update failed: " + err.message);
    } finally {
      setSavingTemp(false);
    }
  };

  const toggleGroup = (providerId: number) => {
    setCollapsedProviders((prev) => ({
      ...prev,
      [providerId]: !prev[providerId],
    }));
  };

  const expandAll = () => setCollapsedProviders({});
  const collapseAll = () => {
    const all: Record<number, boolean> = {};
    providers.forEach((p) => {
      all[p.id] = true;
    });
    setCollapsedProviders(all);
  };

  // Selection helpers
  const toggleSelectModel = (modelId: number) => {
    const next = new Set(selectedModelIds);
    if (next.has(modelId)) {
      next.delete(modelId);
    } else {
      next.add(modelId);
    }
    lastSelectedModelIdRef.current = modelId;
    setSelectedModelIds(next);
  };

  const toggleSelectProviderModels = (providerModels: DiscoveredModel[]) => {
    const next = new Set(selectedModelIds);
    const allSelected = providerModels.length > 0 && providerModels.every((m) => next.has(m.id));

    if (allSelected) {
      providerModels.forEach((m) => next.delete(m.id));
    } else {
      providerModels.forEach((m) => next.add(m.id));
    }
    setSelectedModelIds(next);
  };

  const clearSelection = () => {
    setSelectedModelIds(new Set());
    lastSelectedModelIdRef.current = null;
    setIsTopActionsOpen(false);
  };

  // Batch action handlers
  const handleBatchEnable = async (enable: boolean) => {
    if (selectedModelIds.size === 0) return;
    setBatchProcessing(true);
    try {
      const ids = Array.from(selectedModelIds);
      await apiRequest("/api/admin/models/batch-update", {
        method: "POST",
        body: JSON.stringify({ model_ids: ids, enabled: enable }),
      });
      setModels((prev) =>
        prev.map((m) => (selectedModelIds.has(m.id) ? { ...m, enabled: enable } : m))
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((m) => (selectedModelIds.has(m.id) ? { ...m, enabled: enable } : m))
      );
      setStatusMessage({
        text: `${ids.length} models ${enable ? "enabled" : "disabled"} successfully.`,
        ok: true,
      });
    } catch (err: any) {
      setStatusMessage({ text: err.message || "Batch update failed", ok: false });
    } finally {
      setBatchProcessing(false);
    }
  };

  const handleBatchHide = async (hide: boolean) => {
    if (selectedModelIds.size === 0) return;
    const ids = Array.from(selectedModelIds);
    setBatchProcessing(true);
    try {
      await apiRequest("/api/admin/models/batch-update", {
        method: "POST",
        body: JSON.stringify({ model_ids: ids, is_visible: !hide }),
      });
      const idsSet = new Set(ids);
      setModels((prev) =>
        prev.map((m) => (idsSet.has(m.id) ? { ...m, is_visible: !hide } : m))
      );
      setNewlyDiscoveredModels((prev) =>
        prev.map((m) => (idsSet.has(m.id) ? { ...m, is_visible: !hide } : m))
      );
      setStatusMessage({
        text: `${ids.length} models ${hide ? "hidden from API & catalog" : "unhidden"}.`,
        ok: true,
      });
      clearSelection();
    } catch (err: any) {
      setStatusMessage({ text: err.message || "Batch update failed", ok: false });
    } finally {
      setBatchProcessing(false);
    }
  };

  // Keep only selected models visible (hide all other models)
  const handleKeepOnlySelectedVisible = async () => {
    if (selectedModelIds.size === 0) return;
    const ids = Array.from(selectedModelIds);
    setBatchProcessing(true);
    try {
      await apiRequest("/api/admin/models/set-visible-only", {
        method: "POST",
        body: JSON.stringify({ model_ids: ids }),
      });
      const idsSet = new Set(ids);
      setModels((prev) =>
        prev.map((m) => ({ ...m, is_visible: idsSet.has(m.id) }))
      );
      setStatusMessage({
        text: `Kept only ${ids.length} selected models visible (all others hidden from API).`,
        ok: true,
      });
      clearSelection();
    } catch (err: any) {
      setStatusMessage({ text: err.message || "Failed to update visibility", ok: false });
    } finally {
      setBatchProcessing(false);
    }
  };

  // Set visibility for all models of a single provider
  const handleSetProviderVisibility = async (providerId: number, isVisible: boolean, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiRequest("/api/admin/models/visibility-all", {
        method: "POST",
        body: JSON.stringify({ is_visible: isVisible, provider_id: providerId }),
      });
      setModels((prev) =>
        prev.map((m) => (m.provider_id === providerId ? { ...m, is_visible: isVisible } : m))
      );
      setStatusMessage({
        text: `All models for provider ${isVisible ? "shown" : "hidden"}.`,
        ok: true,
      });
    } catch (err: any) {
      setStatusMessage({ text: err.message || "Failed to update visibility", ok: false });
    }
  };

  // Set visibility for ALL models across entire catalog
  const handleSetAllVisibility = async (isVisible: boolean) => {
    if (!confirm(isVisible ? "Make ALL models visible in API?" : "Hide ALL models from API? (you can then selectively enable only the ones you need)")) return;
    try {
      await apiRequest("/api/admin/models/visibility-all", {
        method: "POST",
        body: JSON.stringify({ is_visible: isVisible }),
      });
      setModels((prev) => prev.map((m) => ({ ...m, is_visible: isVisible })));
      setStatusMessage({
        text: isVisible ? "All models are now visible in API." : "All models hidden from API. Select and enable the ones you need.",
        ok: true,
      });
    } catch (err: any) {
      setStatusMessage({ text: err.message || "Error", ok: false });
    }
  };

  // Group models strictly by Provider (Providers NEVER repeat)
  // Deduplicate models within each provider by provider_model_id
  const providerGroups: ProviderGroup[] = useMemo(() => {
    const q = search.trim().toLowerCase();

    // Map provider_id -> Provider object
    const providerMap = new Map<number, Provider>();
    providers.forEach((p) => providerMap.set(p.id, p));

    // Group models by provider_id with deduplication
    const groupMap = new Map<number, Map<string, DiscoveredModel>>();

    models.forEach((m) => {
      const isHidden = m.is_visible === false;

      // Visibility filter check
      if (visibilityFilter === "visible" && isHidden) return;
      if (visibilityFilter === "hidden" && !isHidden) return;

      // Search filter check
      if (
        q &&
        !m.canonical_slug.toLowerCase().includes(q) &&
        !m.display_name.toLowerCase().includes(q) &&
        !m.provider_name.toLowerCase().includes(q) &&
        !m.provider_model_id.toLowerCase().includes(q) &&
        !Object.keys(m.capabilities || {}).some(
          (k) => m.capabilities[k] === true && k.toLowerCase().includes(q)
        )
      ) {
        return;
      }

      if (!groupMap.has(m.provider_id)) {
        groupMap.set(m.provider_id, new Map());
      }
      const pModels = groupMap.get(m.provider_id)!;
      // Deduplicate by provider_model_id
      if (!pModels.has(m.provider_model_id)) {
        pModels.set(m.provider_model_id, m);
      }
    });

    const sortedProviders = [...providers].sort((a, b) => a.name.localeCompare(b.name));
    const groups: ProviderGroup[] = [];

    sortedProviders.forEach((p) => {
      const pModelsMap = groupMap.get(p.id);
      let pModels = pModelsMap ? Array.from(pModelsMap.values()) : [];

      // Rating filter check
      if (ratingFilter === "rated") {
        pModels = pModels.filter((m) => m.rating?.intelligence_index !== undefined && m.rating?.intelligence_index !== null);
      } else if (ratingFilter === "high-intel") {
        pModels = pModels.filter((m) => (m.rating?.intelligence_index ?? 0) >= 35);
      } else if (ratingFilter === "top-coding") {
        pModels = pModels.filter((m) => (m.rating?.coding_index ?? 0) >= 50);
      } else if (ratingFilter === "top-agentic") {
        pModels = pModels.filter(
          (m) => (m.rating?.agentic_index ?? 0) >= 20 || m.capabilities?.reasoning === true
        );
      }

      // Sort models within provider group
      pModels.sort((a, b) => {
        if (sortBy === "default") {
          return a.canonical_slug.localeCompare(b.canonical_slug);
        } else if (sortBy === "intel-desc") {
          const scoreA = a.rating?.intelligence_index ?? -1;
          const scoreB = b.rating?.intelligence_index ?? -1;
          if (scoreB !== scoreA) return scoreB - scoreA;
          return a.canonical_slug.localeCompare(b.canonical_slug);
        } else if (sortBy === "coding-desc") {
          const scoreA = a.rating?.coding_index ?? -1;
          const scoreB = b.rating?.coding_index ?? -1;
          if (scoreB !== scoreA) return scoreB - scoreA;
          return a.canonical_slug.localeCompare(b.canonical_slug);
        } else if (sortBy === "agentic-desc") {
          const scoreA = a.rating?.agentic_index ?? -1;
          const scoreB = b.rating?.agentic_index ?? -1;
          if (scoreB !== scoreA) return scoreB - scoreA;
          return a.canonical_slug.localeCompare(b.canonical_slug);
        } else if (sortBy === "context-desc") {
          const ctxA = a.context_length ?? 0;
          const ctxB = b.context_length ?? 0;
          if (ctxB !== ctxA) return ctxB - ctxA;
          return a.canonical_slug.localeCompare(b.canonical_slug);
        } else if (sortBy === "name-asc") {
          return a.display_name.localeCompare(b.display_name);
        }
        return 0;
      });

      // If user is searching or filtered, only show providers that have matching models
      if ((q || visibilityFilter === "hidden" || ratingFilter !== "all") && pModels.length === 0) {
        return;
      }
      groups.push({
        provider: p,
        models: pModels,
      });
    });

    return groups;
  }, [models, providers, search, visibilityFilter, ratingFilter, sortBy]);

  const allVisibleModels = useMemo(() => {
    return providerGroups.flatMap((g) => g.models);
  }, [providerGroups]);

  const allVisibleSelected = useMemo(() => {
    return allVisibleModels.length > 0 && allVisibleModels.every((m) => selectedModelIds.has(m.id));
  }, [allVisibleModels, selectedModelIds]);

  const someVisibleSelected = useMemo(() => {
    return allVisibleModels.some((m) => selectedModelIds.has(m.id));
  }, [allVisibleModels, selectedModelIds]);

  const toggleSelectAllVisible = () => {
    const next = new Set(selectedModelIds);
    if (allVisibleSelected) {
      allVisibleModels.forEach((m) => next.delete(m.id));
    } else {
      allVisibleModels.forEach((m) => next.add(m.id));
    }
    setSelectedModelIds(next);
  };

  const handleModelCheckboxClick = (modelId: number, event: React.MouseEvent) => {
    event.stopPropagation();
    const next = new Set(selectedModelIds);

    if (event.shiftKey && lastSelectedModelIdRef.current !== null && lastSelectedModelIdRef.current !== modelId) {
      const allList = allVisibleModels;
      const idx1 = allList.findIndex((m) => m.id === lastSelectedModelIdRef.current);
      const idx2 = allList.findIndex((m) => m.id === modelId);

      if (idx1 !== -1 && idx2 !== -1) {
        const start = Math.min(idx1, idx2);
        const end = Math.max(idx1, idx2);
        const shouldSelect = !selectedModelIds.has(modelId);
        for (let i = start; i <= end; i++) {
          if (shouldSelect) {
            next.add(allList[i].id);
          } else {
            next.delete(allList[i].id);
          }
        }
        setSelectedModelIds(next);
        lastSelectedModelIdRef.current = modelId;
        return;
      }
    }

    if (next.has(modelId)) {
      next.delete(modelId);
    } else {
      next.add(modelId);
    }
    lastSelectedModelIdRef.current = modelId;
    setSelectedModelIds(next);
  };

  const totalUniqueModels = useMemo(() => {
    const unique = new Set<string>();
    models.forEach((m) => unique.add(`${m.provider_id}:${m.provider_model_id}`));
    return unique.size;
  }, [models]);

  const totalRatedModels = useMemo(() => {
    const unique = new Set<string>();
    let count = 0;
    models.forEach((m) => {
      const key = `${m.provider_id}:${m.provider_model_id}`;
      if (!unique.has(key)) {
        unique.add(key);
        if (m.rating?.intelligence_index !== undefined && m.rating?.intelligence_index !== null) {
          count++;
        }
      }
    });
    return count;
  }, [models]);

  const hiddenCount = useMemo(() => {
    let count = 0;
    const seen = new Set<string>();
    models.forEach((m) => {
      const key = `${m.provider_id}:${m.provider_model_id}`;
      if (!seen.has(key)) {
        seen.add(key);
        if (m.is_visible === false) count++;
      }
    });
    return count;
  }, [models]);

  const newModelSlugsSet = useMemo(
    () => new Set(newlyDiscoveredModels.map((m) => m.canonical_slug)),
    [newlyDiscoveredModels]
  );

  return (
    <div className="space-y-6">
      {/* Top Header & Global Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2 flex-wrap">
            <Boxes size={22} className="text-indigo-400" />
            <span>{t.models.title}</span>
            <span className="text-xs font-mono font-normal bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 px-2.5 py-0.5 rounded-full shadow-xs">
              {totalUniqueModels} models
            </span>
            {totalRatedModels > 0 && (
              <span className="text-xs font-mono font-normal bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 px-2.5 py-0.5 rounded-full flex items-center gap-1 shadow-xs" title="Models with Artificial Analysis benchmark scores">
                <Brain size={12} />
                {totalRatedModels} benchmarked
              </span>
            )}
            {hiddenCount > 0 && (
              <span className="text-xs font-mono font-normal bg-slate-800/80 text-slate-400 border border-white/[0.06] px-2.5 py-0.5 rounded-full flex items-center gap-1">
                <EyeOff size={12} />
                {hiddenCount} {t.models.showHidden.toLowerCase()}
              </span>
            )}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {t.models.subtitle}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleSyncRatings}
            disabled={syncingRatings}
            className="btn-press flex items-center gap-1.5 px-3 py-2 bg-slate-900/80 hover:bg-slate-800 text-slate-200 text-xs font-semibold rounded-xl border border-white/[0.08] shadow-sm transition-all disabled:opacity-50 cursor-pointer"
            title="Sync intelligence benchmark ratings from artificialanalysis.ai"
          >
            <Brain size={14} className={syncingRatings ? "animate-pulse text-indigo-400" : "text-indigo-400"} />
            <span>{syncingRatings ? "Syncing..." : "Sync Ratings"}</span>
          </button>
          <button
            onClick={() => setIsManualModalOpen(true)}
            className="btn-press flex items-center gap-1.5 px-3 py-2 bg-slate-900/80 hover:bg-slate-800 text-slate-200 text-xs font-semibold rounded-xl border border-white/[0.08] shadow-sm transition-all cursor-pointer"
          >
            <Plus size={14} />
            <span>Add Manually</span>
          </button>
          <button
            onClick={handleFetchAll}
            disabled={fetchingAll}
            className="btn-press flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-500/20 border border-white/10 transition-all disabled:opacity-50 cursor-pointer"
            title="Fetch models across all enabled providers and credentials"
          >
            <RefreshCw size={14} className={fetchingAll ? "animate-spin" : ""} />
            <span>{fetchingAll ? t.common.loading : t.models.syncModels}</span>
          </button>
        </div>
      </div>

      {/* Notification status banner */}
      {statusMessage && (
        <div
          className={`p-3 rounded-xl border text-xs flex items-center justify-between gap-2 ${
            statusMessage.ok
              ? "bg-emerald-950/60 border-emerald-800 text-emerald-300"
              : "bg-rose-950/60 border-rose-800 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-2">
            {statusMessage.ok ? <CheckCircle2 size={15} /> : <XCircle size={15} />}
            <span>{statusMessage.text}</span>
          </div>
          <button
            onClick={() => setStatusMessage(null)}
            className="text-slate-400 hover:text-slate-200 text-xs px-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Newly Discovered Models Section (Displayed at the very top after refresh) */}
      {newlyDiscoveredModels.length > 0 && (
        <div className="bg-gradient-to-r from-emerald-950/40 via-slate-900 to-indigo-950/40 border border-emerald-500/40 rounded-xl overflow-hidden shadow-lg transition-all">
          {/* Header */}
          <div className="p-3 sm:p-3.5 bg-slate-950/80 border-b border-emerald-500/20 flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-300 shrink-0">
                <Sparkles size={17} className="animate-pulse text-emerald-400" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
                    <span>Newly Discovered Models</span>
                    <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-emerald-500/25 text-emerald-300 border border-emerald-500/40 animate-pulse">
                      +{newlyDiscoveredModels.length}
                    </span>
                  </h3>
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  List of new models discovered during the latest provider sync.
                </p>
              </div>
            </div>

            {/* Quick Actions in Header */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={selectAllNewModels}
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-indigo-950/70 hover:bg-indigo-900 text-indigo-300 border border-indigo-700/50 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                title="Add all new models to batch selection"
              >
                <CheckSquare size={13} />
                <span>Select All</span>
              </button>

              <button
                type="button"
                onClick={() => setIsNewModelsCollapsed(!isNewModelsCollapsed)}
                className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg border border-slate-700/60 transition-colors cursor-pointer"
                title={isNewModelsCollapsed ? "Expand new models list" : "Collapse new models list"}
              >
                {isNewModelsCollapsed ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
              </button>

              <button
                type="button"
                onClick={dismissNewModels}
                className="p-1.5 text-slate-400 hover:text-rose-300 hover:bg-rose-950/40 rounded-lg border border-slate-700/60 transition-colors cursor-pointer"
                title="Dismiss new models banner"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          {/* Table of New Models */}
          {!isNewModelsCollapsed && (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800/80 bg-slate-950/50 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 px-4 w-10 text-center">
                      <button
                        type="button"
                        onClick={() => toggleSelectProviderModels(newlyDiscoveredModels)}
                        className="inline-flex items-center justify-center p-1 rounded hover:bg-white/[0.08] text-slate-400 hover:text-slate-200 cursor-pointer transition-colors"
                        title={
                          newlyDiscoveredModels.length > 0 && newlyDiscoveredModels.every((m) => selectedModelIds.has(m.id))
                            ? "Deselect all new models"
                            : "Select all new models"
                        }
                      >
                        {newlyDiscoveredModels.length > 0 && newlyDiscoveredModels.every((m) => selectedModelIds.has(m.id)) ? (
                          <CheckSquare size={15} className="text-indigo-400" />
                        ) : newlyDiscoveredModels.some((m) => selectedModelIds.has(m.id)) ? (
                          <MinusSquare size={15} className="text-indigo-400" />
                        ) : (
                          <Square size={15} className="text-slate-500" />
                        )}
                      </button>
                    </th>
                    <th className="py-2.5 px-4">Provider</th>
                    <th className="py-2.5 px-4">Model / Canonical Slug</th>
                    <th className="py-2.5 px-4">
                      <div className="flex items-center gap-1">
                        <Brain size={12} className="text-indigo-400" />
                        <span>Intelligence</span>
                      </div>
                    </th>
                    <th className="py-2.5 px-4">Capabilities</th>
                    <th className="py-2.5 px-4">Context & Limits</th>
                    <th className="py-2.5 px-4 text-center w-20">Visibility</th>
                    <th className="py-2.5 px-4 text-center w-24">Status</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50 text-slate-300">
                  {newlyDiscoveredModels.map((m) => {
                    const isSelected = selectedModelIds.has(m.id);
                    const isHidden = m.is_visible === false;

                    return (
                      <tr
                        key={`new-${m.id}`}
                        className={`hover:bg-slate-800/40 transition-colors ${
                          isSelected ? "bg-indigo-950/30" : isHidden ? "opacity-60 bg-slate-950/40" : ""
                        }`}
                      >
                        {/* Checkbox */}
                        <td
                          className="py-2.5 px-4 text-center cursor-pointer select-none"
                          onClick={(e) => handleModelCheckboxClick(m.id, e)}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-0 cursor-pointer pointer-events-none"
                          />
                        </td>

                        {/* Provider */}
                        <td className="py-2.5 px-4 whitespace-nowrap">
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-800/90 text-slate-200 border border-slate-700">
                            <Cpu size={12} className="text-indigo-400" />
                            <span>{m.provider_name}</span>
                          </span>
                        </td>

                        {/* Slug & Display Name */}
                        <td className="py-2.5 px-4 font-mono font-medium text-emerald-300">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-indigo-200 font-semibold">{m.canonical_slug}</span>
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-500/25 text-emerald-300 border border-emerald-500/40 animate-pulse flex items-center gap-0.5">
                              <Sparkles size={9} /> NEW
                            </span>
                            <button
                              type="button"
                              onClick={(e) => handleCopySlug(m.canonical_slug, e)}
                              className="p-0.5 text-slate-500 hover:text-slate-200 transition-colors cursor-pointer"
                              title="Copy model slug"
                            >
                              {copiedSlug === m.canonical_slug ? (
                                <Check size={11} className="text-emerald-400" />
                              ) : (
                                <Copy size={11} />
                              )}
                            </button>
                            {isHidden && (
                              <span className="text-[10px] text-amber-400/80 font-sans italic">
                                (hidden)
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-400 font-sans mt-0.5">
                            {m.display_name}
                          </div>
                        </td>

                        {/* Intelligence / Rating */}
                        <td className="py-2.5 px-4">
                          <ModelIntelligenceBadge
                            modelId={m.id}
                            rating={m.rating}
                            capabilities={m.capabilities}
                            contextLength={m.context_length}
                            maxOutputTokens={m.max_output_tokens}
                            initialLimits={m.limits}
                            onLimitsFetched={(newLimits) => {
                              setModels((prev) =>
                                prev.map((item) =>
                                  item.id === m.id
                                    ? {
                                        ...item,
                                        context_length: newLimits.context_length ?? item.context_length,
                                        max_output_tokens: newLimits.max_output_tokens ?? item.max_output_tokens,
                                        limits: newLimits,
                                      }
                                    : item
                                )
                              );
                              setNewlyDiscoveredModels((prev) =>
                                prev.map((item) =>
                                  item.id === m.id
                                    ? {
                                        ...item,
                                        context_length: newLimits.context_length ?? item.context_length,
                                        max_output_tokens: newLimits.max_output_tokens ?? item.max_output_tokens,
                                        limits: newLimits,
                                      }
                                    : item
                                )
                              );
                            }}
                          />
                        </td>

                        {/* Capabilities */}
                        <td className="py-2.5 px-4">
                          <div className="flex flex-wrap gap-1">
                            {m.capabilities?.streaming && (
                              <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300">
                                stream
                              </span>
                            )}
                            {m.capabilities?.vision === true && (
                              <span className="px-1.5 py-0.5 rounded bg-cyan-950 text-[10px] text-cyan-300 border border-cyan-800/60">
                                vision
                              </span>
                            )}
                            {m.capabilities?.tools === true && (
                              <span className="px-1.5 py-0.5 rounded bg-purple-950 text-[10px] text-purple-300 border border-purple-800/60">
                                tools
                              </span>
                            )}
                            {m.capabilities?.reasoning === true && (
                              <span className="px-1.5 py-0.5 rounded bg-amber-950 text-[10px] text-amber-300 border border-amber-800/60">
                                thinking
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Limits & Context */}
                        <td className="py-2.5 px-4 font-mono text-[11px]">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <button
                              type="button"
                              onClick={() => openContextModal(m)}
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-800/80 hover:bg-indigo-950/80 hover:border-indigo-600/60 border border-slate-700/60 text-slate-200 hover:text-indigo-200 transition-colors group cursor-pointer"
                              title="Click to configure context length"
                            >
                              <span className="font-semibold text-slate-200 group-hover:text-indigo-200">
                                {m.context_length
                                  ? m.context_length >= 1_000_000
                                    ? `${(m.context_length / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`
                                    : `${Math.round(m.context_length / 1000)}k`
                                  : "—"}
                              </span>
                              <SlidersHorizontal size={10} className="text-slate-500 group-hover:text-indigo-400 transition-colors" />
                            </button>
                            <button
                              type="button"
                              onClick={() => openReasoningModal(m)}
                              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border transition-colors cursor-pointer group ${
                                m.reasoning_effort
                                  ? "bg-amber-950/60 hover:bg-amber-900/80 border-amber-600/50 text-amber-200"
                                  : "bg-slate-800/80 hover:bg-slate-700/80 border-slate-700/60 text-slate-400 hover:text-slate-200"
                              }`}
                              title="Click to configure reasoning effort"
                            >
                              <Brain size={10} className={m.reasoning_effort ? "text-amber-400" : "text-slate-500 group-hover:text-slate-300"} />
                              <span>{m.reasoning_effort ? `effort: ${m.reasoning_effort}` : "effort: —"}</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => openTempModal(m)}
                              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border transition-colors cursor-pointer group ${
                                m.temperature !== null && m.temperature !== undefined
                                  ? "bg-rose-950/60 hover:bg-rose-900/80 border-rose-600/50 text-rose-200"
                                  : "bg-slate-800/80 hover:bg-slate-700/80 border-slate-700/60 text-slate-400 hover:text-slate-200"
                              }`}
                              title="Click to configure default temperature"
                            >
                              <Thermometer size={10} className={m.temperature !== null && m.temperature !== undefined ? "text-rose-400" : "text-slate-500 group-hover:text-slate-300"} />
                              <span>{m.temperature !== null && m.temperature !== undefined ? `temp: ${m.temperature}` : "temp: —"}</span>
                            </button>
                          </div>
                        </td>

                        {/* Visibility Toggle */}
                        <td className="py-2.5 px-4 text-center">
                          <button
                            type="button"
                            onClick={() => toggleHideModel(m)}
                            className={`p-1 rounded transition-colors cursor-pointer ${
                              isHidden
                                ? "text-amber-400 hover:bg-amber-950/60 hover:text-amber-300"
                                : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                            }`}
                            title={isHidden ? "Unhide model" : "Hide model"}
                          >
                            {isHidden ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                        </td>

                        {/* Status Toggle */}
                        <td className="py-2.5 px-4 text-center">
                          <button
                            type="button"
                            onClick={() => handleToggleEnabled(m)}
                            className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition-colors cursor-pointer ${
                              m.enabled
                                ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-600/30"
                                : "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700"
                            }`}
                          >
                            {m.enabled ? "Active" : "Disabled"}
                          </button>
                        </td>

                        {/* Actions */}
                        <td className="py-2.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <a
                              href={`/playground?model=${encodeURIComponent(m.canonical_slug)}`}
                              className="p-1.5 bg-indigo-950/60 hover:bg-indigo-800/80 text-indigo-300 border border-indigo-700/50 rounded-lg text-xs font-medium transition-colors flex items-center gap-1 cursor-pointer"
                              title="Test in Playground"
                            >
                              <Play size={11} />
                              <span className="hidden sm:inline">Play</span>
                            </a>
                            <button
                              type="button"
                              onClick={() => jumpToModelInCatalog(m)}
                              className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-medium transition-colors flex items-center gap-1 cursor-pointer"
                              title="Locate model in catalog below"
                            >
                              <ChevronDown size={12} />
                              <span className="hidden sm:inline">Locate</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Search and Filters Toolbar */}
      <div className="glass-panel card-specular border border-white/[0.07] p-4 rounded-2xl space-y-3.5 shadow-md">
        {/* Row 1: Search & Controls */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          {/* Search input */}
          <div className="flex items-center gap-2.5 px-3.5 py-2 bg-slate-950/80 border border-white/[0.08] focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500/30 rounded-xl w-full sm:max-w-md transition-all">
            <Search size={15} className="text-slate-400 shrink-0" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.models.searchModels}
              className="bg-transparent border-none text-xs text-slate-100 placeholder-slate-500 focus:outline-none w-full"
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="text-slate-400 hover:text-slate-200 text-xs px-1 cursor-pointer"
              >
                ✕
              </button>
            )}
          </div>

          {/* Visibility Filter & Collapse Controls */}
          <div className="flex items-center gap-2 flex-wrap text-xs">
            {/* Visibility filter tabs */}
            <div className="flex items-center bg-slate-950/80 p-1 rounded-xl border border-white/[0.06] shadow-xs">
              <button
                onClick={() => setVisibilityFilter("visible")}
                className={`btn-press px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                  visibilityFilter === "visible"
                    ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Visible Only
              </button>
              <button
                onClick={() => setVisibilityFilter("all")}
                className={`btn-press px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                  visibilityFilter === "all"
                    ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                All Models
              </button>
              <button
                onClick={() => setVisibilityFilter("hidden")}
                className={`btn-press px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                  visibilityFilter === "hidden"
                    ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Hidden ({hiddenCount})
              </button>
            </div>

            <button
              onClick={expandAll}
              className="btn-press px-3 py-1.5 bg-slate-950/80 hover:bg-slate-800 border border-white/[0.06] rounded-xl text-slate-300 transition-colors cursor-pointer"
            >
              Expand All
            </button>
            <button
              onClick={collapseAll}
              className="btn-press px-3 py-1.5 bg-slate-950/80 hover:bg-slate-800 border border-white/[0.06] rounded-xl text-slate-300 transition-colors cursor-pointer"
            >
              Collapse All
            </button>
            <button
              onClick={() => handleSetAllVisibility(false)}
              className="btn-press px-3 py-1.5 bg-slate-950/80 hover:bg-amber-950/40 border border-amber-800/60 rounded-xl text-amber-300 text-xs transition-colors cursor-pointer"
              title="Hide ALL models from API (to keep only needed ones)"
            >
              Hide All
            </button>
            <button
              onClick={() => handleSetAllVisibility(true)}
              className="btn-press px-3 py-1.5 bg-slate-950/80 hover:bg-slate-800 border border-white/[0.06] rounded-xl text-slate-300 text-xs transition-colors cursor-pointer"
              title="Make ALL models visible in API"
            >
              Show All
            </button>

            {/* Select All Visible models toggle */}
            <button
              type="button"
              onClick={toggleSelectAllVisible}
              className={`btn-press px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors cursor-pointer flex items-center gap-1.5 ${
                allVisibleSelected
                  ? "bg-indigo-600/30 text-indigo-300 border-indigo-500/50"
                  : someVisibleSelected
                  ? "bg-indigo-950/60 text-indigo-300 border-indigo-500/40"
                  : "bg-slate-950/80 hover:bg-slate-800 border-white/[0.06] text-slate-300"
              }`}
              title={
                allVisibleSelected
                  ? "Deselect all visible models"
                  : "Select all visible models (Shift+Click on rows to range select)"
              }
            >
              {allVisibleSelected ? (
                <CheckSquare size={14} className="text-indigo-400" />
              ) : someVisibleSelected ? (
                <MinusSquare size={14} className="text-indigo-400" />
              ) : (
                <Square size={14} className="text-slate-400" />
              )}
              <span>{allVisibleSelected ? "Deselect Visible" : `Select Visible (${allVisibleModels.length})`}</span>
            </button>

            {/* Top Actions dropdown when models are selected */}
            {selectedModelIds.size > 0 && (
              <div className="relative inline-block text-left">
                <button
                  type="button"
                  onClick={() => setIsTopActionsOpen((prev) => !prev)}
                  className="btn-press px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white border border-indigo-400/40 rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/20 transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  <span className="w-4 h-4 rounded-full bg-white/20 text-white text-[10px] font-bold flex items-center justify-center">
                    {selectedModelIds.size}
                  </span>
                  <span>Actions</span>
                  <ChevronDown
                    size={13}
                    className={`transition-transform duration-150 ${isTopActionsOpen ? "rotate-180" : ""}`}
                  />
                </button>

                {isTopActionsOpen && (
                  <div
                    className="absolute right-0 mt-2 w-56 rounded-xl bg-slate-900 border border-indigo-500/40 shadow-2xl shadow-black/80 py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="px-3 py-1.5 text-[11px] text-slate-400 font-semibold border-b border-slate-800 flex items-center justify-between">
                      <span>Selected: {selectedModelIds.size} models</span>
                      <button
                        type="button"
                        onClick={clearSelection}
                        className="text-indigo-400 hover:text-indigo-300 text-[10px] cursor-pointer"
                      >
                        Clear
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        handleBatchEnable(true);
                        setIsTopActionsOpen(false);
                      }}
                      disabled={batchProcessing}
                      className="w-full text-left px-3 py-2 text-xs text-emerald-300 hover:bg-slate-800/80 flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <CheckCircle2 size={14} className="text-emerald-400" />
                      <span>Enable Selected</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        handleBatchEnable(false);
                        setIsTopActionsOpen(false);
                      }}
                      disabled={batchProcessing}
                      className="w-full text-left px-3 py-2 text-xs text-slate-300 hover:bg-slate-800/80 flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <XCircle size={14} className="text-rose-400" />
                      <span>Disable Selected</span>
                    </button>

                    <div className="my-1 border-t border-slate-800" />

                    <button
                      type="button"
                      onClick={() => {
                        handleBatchHide(true);
                        setIsTopActionsOpen(false);
                      }}
                      disabled={batchProcessing}
                      className="w-full text-left px-3 py-2 text-xs text-amber-300 hover:bg-slate-800/80 flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <EyeOff size={14} className="text-amber-400" />
                      <span>Hide Selected</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        handleBatchHide(false);
                        setIsTopActionsOpen(false);
                      }}
                      disabled={batchProcessing}
                      className="w-full text-left px-3 py-2 text-xs text-slate-300 hover:bg-slate-800/80 flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <Eye size={14} className="text-slate-400" />
                      <span>Unhide Selected</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        handleKeepOnlySelectedVisible();
                        setIsTopActionsOpen(false);
                      }}
                      disabled={batchProcessing}
                      className="w-full text-left px-3 py-2 text-xs text-indigo-300 hover:bg-slate-800/80 flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <Sparkles size={14} className="text-indigo-400" />
                      <span>Keep Only Selected</span>
                    </button>

                    <div className="my-1 border-t border-slate-800" />

                    <button
                      type="button"
                      onClick={() => {
                        openBatchContextModal();
                        setIsTopActionsOpen(false);
                      }}
                      disabled={batchProcessing}
                      className="w-full text-left px-3 py-2 text-xs text-slate-200 hover:bg-slate-800/80 flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <SlidersHorizontal size={14} className="text-indigo-400" />
                      <span>Set Context Window...</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        openBatchReasoningModal();
                        setIsTopActionsOpen(false);
                      }}
                      disabled={batchProcessing}
                      className="w-full text-left px-3 py-2 text-xs text-amber-200 hover:bg-slate-800/80 flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <Brain size={14} className="text-amber-400" />
                      <span>Set Reasoning Effort...</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        openBatchTempModal();
                        setIsTopActionsOpen(false);
                      }}
                      disabled={batchProcessing}
                      className="w-full text-left px-3 py-2 text-xs text-rose-200 hover:bg-slate-800/80 flex items-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
                    >
                      <Thermometer size={14} className="text-rose-400" />
                      <span>Set Temperature...</span>
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Sub-bar: Intelligence Rating Filter & Sorting */}
        <div className="w-full flex items-center justify-between gap-3 flex-wrap pt-2.5 mt-0.5 border-t border-slate-800/80 text-xs">
          {/* Benchmark Rating Filter Chips */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-slate-400 font-medium flex items-center gap-1 mr-1">
              <Brain size={12} className="text-indigo-400" />
              <span>Rating (AA):</span>
            </span>
            <div className="flex items-center bg-slate-950 p-0.5 rounded-lg border border-slate-800">
              <button
                onClick={() => setRatingFilter("all")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  ratingFilter === "all"
                    ? "bg-slate-800 text-slate-100"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setRatingFilter("rated")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  ratingFilter === "rated"
                    ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/40"
                    : "text-slate-400 hover:text-slate-200"
                }`}
                title="Only models with Artificial Analysis rating"
              >
                Rated
              </button>
              <button
                onClick={() => setRatingFilter("high-intel")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  ratingFilter === "high-intel"
                    ? "bg-emerald-600/30 text-emerald-300 border border-emerald-500/40"
                    : "text-slate-400 hover:text-slate-200"
                }`}
                title="Models with intelligence score 35+"
              >
                🧠 Top Intellect (35+)
              </button>
              <button
                onClick={() => setRatingFilter("top-coding")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  ratingFilter === "top-coding"
                    ? "bg-cyan-600/30 text-cyan-300 border border-cyan-500/40"
                    : "text-slate-400 hover:text-slate-200"
                }`}
                title="Models with coding score 50+"
              >
                💻 Coding (50+)
              </button>
              <button
                onClick={() => setRatingFilter("top-agentic")}
                className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                  ratingFilter === "top-agentic"
                    ? "bg-purple-600/30 text-purple-300 border border-purple-500/40"
                    : "text-slate-400 hover:text-slate-200"
                }`}
                title="Models with agentic reasoning score 20+"
              >
                🤖 Agents (20+)
              </button>
            </div>
          </div>

          {/* Sorting Dropdown */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <ArrowUpDown size={12} className="text-slate-500" />
              <span>Sort:</span>
            </span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-indigo-500 cursor-pointer"
            >
              <option value="default">Default</option>
              <option value="intel-desc">🧠 Intelligence (Highest first)</option>
              <option value="coding-desc">💻 Coding (Highest first)</option>
              <option value="agentic-desc">🤖 Agentic Reasoning (Highest first)</option>
              <option value="context-desc">Context Window (Largest first)</option>
              <option value="name-asc">Model Name (A-Z)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Floating Batch Action Bar when models are selected (Fixed at bottom viewport, always visible) */}
      {selectedModelIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 max-w-[96vw] bg-slate-900/95 border border-indigo-500/60 shadow-2xl shadow-indigo-950/90 rounded-2xl px-4 py-3 backdrop-blur-md flex items-center justify-between gap-3 flex-wrap animate-in fade-in slide-in-from-bottom-5 duration-200">
          <div className="flex items-center gap-2.5 pr-3 border-r border-slate-700/60 text-xs text-indigo-200 font-medium whitespace-nowrap">
            <div className="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300">
              <CheckSquare size={15} />
            </div>
            <span>
              Selected: <strong className="text-white font-bold">{selectedModelIds.size}</strong>{" "}
              {selectedModelIds.size === 1 ? "model" : "models"}
            </span>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => handleBatchEnable(true)}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors cursor-pointer whitespace-nowrap"
            >
              <CheckCircle2 size={14} />
              <span>Enable Selected</span>
            </button>

            <button
              type="button"
              onClick={() => handleBatchEnable(false)}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 shadow-xs transition-colors cursor-pointer whitespace-nowrap"
            >
              <XCircle size={14} />
              <span>Disable Selected</span>
            </button>

            <button
              type="button"
              onClick={() => handleBatchHide(true)}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-amber-300 text-xs font-semibold rounded-lg border border-slate-700 shadow-xs transition-colors cursor-pointer whitespace-nowrap"
              title="Hide selected models from catalog and API"
            >
              <EyeOff size={14} />
              <span>Hide Selected</span>
            </button>

            <button
              type="button"
              onClick={() => handleBatchHide(false)}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 text-xs font-semibold rounded-lg border border-slate-700 shadow-xs transition-colors cursor-pointer whitespace-nowrap"
              title="Unhide selected models (show in catalog and API)"
            >
              <Eye size={14} />
              <span>Unhide Selected</span>
            </button>

            <button
              type="button"
              onClick={handleKeepOnlySelectedVisible}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors cursor-pointer whitespace-nowrap"
              title="Keep ONLY selected models visible in API and catalog (hide all others)"
            >
              <Sparkles size={14} />
              <span>Keep Only Selected</span>
            </button>

            <button
              type="button"
              onClick={openBatchContextModal}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-900/60 hover:bg-indigo-800 disabled:opacity-50 text-indigo-200 text-xs font-semibold rounded-lg border border-indigo-700 shadow-xs transition-colors cursor-pointer whitespace-nowrap"
              title="Set context window for selected models"
            >
              <SlidersHorizontal size={14} />
              <span>Set Context ({selectedModelIds.size})</span>
            </button>

            <button
              type="button"
              onClick={openBatchReasoningModal}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-950/60 hover:bg-amber-900 disabled:opacity-50 text-amber-200 text-xs font-semibold rounded-lg border border-amber-700/70 shadow-xs transition-colors cursor-pointer whitespace-nowrap"
              title="Set reasoning effort for selected models"
            >
              <Brain size={14} />
              <span>Set Reasoning ({selectedModelIds.size})</span>
            </button>

            <button
              type="button"
              onClick={openBatchTempModal}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-950/60 hover:bg-rose-900 disabled:opacity-50 text-rose-200 text-xs font-semibold rounded-lg border border-rose-700/70 shadow-xs transition-colors cursor-pointer whitespace-nowrap"
              title="Set temperature for selected models"
            >
              <Thermometer size={14} />
              <span>Set Temperature ({selectedModelIds.size})</span>
            </button>

            <button
              type="button"
              onClick={clearSelection}
              className="px-2.5 py-1.5 bg-transparent hover:bg-indigo-900/50 text-indigo-300 text-xs font-medium rounded-lg transition-colors ml-1 cursor-pointer whitespace-nowrap"
            >
              Deselect All
            </button>
          </div>
        </div>
      )}

      {/* Grouped Models by Provider */}
      <div className="space-y-4">
        {providerGroups.length === 0 ? (
          <div className="p-8 text-center bg-slate-900/90 border border-slate-800 rounded-xl text-xs text-slate-400">
            {models.length === 0
              ? "No models discovered yet. Go to Upstream Keys and click 'Fetch Models' to populate catalog!"
              : "No models matching your current search or visibility filters."}
          </div>
        ) : (
          providerGroups.map(({ provider, models: groupModels }) => {
            const isCollapsed = !!collapsedProviders[provider.id];

            // Calculate provider selection state
            const providerModelIds = groupModels.map((m) => m.id);
            const selectedCount = providerModelIds.filter((id) => selectedModelIds.has(id)).length;
            const allSelected = groupModels.length > 0 && selectedCount === groupModels.length;
            const isPartiallySelected = selectedCount > 0 && selectedCount < groupModels.length;

            const isRefreshing = refreshingProviderId === provider.id;

            return (
              <div
                key={provider.id}
                className="glass-card card-specular rounded-2xl border border-white/[0.07] overflow-hidden transition-all duration-200 hover:border-white/[0.12]"
              >
                {/* Single Provider Header (Never Repeats) */}
                <div
                  onClick={() => toggleGroup(provider.id)}
                  className="flex items-center justify-between p-4 bg-slate-950/60 border-b border-white/[0.06] cursor-pointer hover:bg-white/[0.02] select-none transition-colors flex-wrap gap-3"
                >
                  <div className="flex items-center gap-3">
                    <button className="text-slate-400 hover:text-slate-200 p-0.5 cursor-pointer">
                      {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                    </button>

                    {/* Select All Checkbox for this Provider */}
                    {groupModels.length > 0 && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSelectProviderModels(groupModels);
                        }}
                        className="flex items-center text-slate-400 hover:text-slate-200 cursor-pointer p-0.5 rounded hover:bg-white/[0.06] transition-colors"
                        title={allSelected ? "Deselect all models of this provider" : "Select all models of this provider"}
                      >
                        {allSelected ? (
                          <CheckSquare size={16} className="text-indigo-400" />
                        ) : isPartiallySelected ? (
                          <MinusSquare size={16} className="text-indigo-400" />
                        ) : (
                          <Square size={16} className="text-slate-500" />
                        )}
                      </button>
                    )}

                    <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-300 shrink-0 shadow-sm">
                      <Cpu size={16} />
                    </div>

                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-slate-100 text-sm tracking-tight">
                          {provider.name}
                        </span>
                        <span className="font-mono text-[10px] text-slate-400 bg-slate-900 border border-white/[0.06] px-2 py-0.5 rounded-lg">
                          {provider.slug}
                        </span>
                        <span className="font-mono text-[10px] text-indigo-400 bg-indigo-950/60 border border-indigo-800/40 px-2 py-0.5 rounded-lg">
                          {provider.adapter_type}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Refresh THIS provider only */}
                    <button
                      onClick={(e) => handleFetchProvider(provider.id, provider.name, e)}
                      disabled={isRefreshing}
                      className="btn-press flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-medium rounded-xl border border-white/[0.06] transition-colors cursor-pointer"
                      title={`Fetch and refresh models for ${provider.name} only`}
                    >
                      <RefreshCw size={12} className={isRefreshing ? "animate-spin text-indigo-400" : ""} />
                      <span className="hidden sm:inline">Refresh Models</span>
                    </button>

                    <button
                      onClick={(e) => handleSetProviderVisibility(provider.id, false, e)}
                      className="btn-press px-2.5 py-1.5 bg-slate-800/80 hover:bg-amber-950/50 text-amber-300 text-xs font-medium rounded-xl border border-white/[0.06] transition-colors cursor-pointer"
                      title={`Hide all ${provider.name} models from API and catalog`}
                    >
                      Hide
                    </button>
                    <button
                      onClick={(e) => handleSetProviderVisibility(provider.id, true, e)}
                      className="btn-press px-2.5 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-xl border border-white/[0.06] transition-colors cursor-pointer"
                      title={`Show all ${provider.name} models in API and catalog`}
                    >
                      Show
                    </button>

                    <span className="text-xs font-mono font-medium text-slate-300 bg-slate-800/80 border border-white/[0.06] px-2.5 py-1 rounded-xl shadow-xs">
                      {groupModels.length} {groupModels.length === 1 ? "model" : "models"}
                    </span>
                  </div>
                </div>

                {/* Provider Models Table */}
                {!isCollapsed && (
                  <div>
                    {groupModels.length === 0 ? (
                      <div className="py-6 text-center text-xs text-slate-500">
                        No models discovered yet for this provider. Add an API key and click "Refresh Models".
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="border-b border-slate-800/80 bg-slate-950/30 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                              <th className="py-2.5 px-4 w-10 text-center">
                                <button
                                  type="button"
                                  onClick={() => toggleSelectProviderModels(groupModels)}
                                  className="inline-flex items-center justify-center p-1 rounded hover:bg-white/[0.08] text-slate-400 hover:text-slate-200 cursor-pointer transition-colors"
                                  title={
                                    allSelected
                                      ? "Deselect all models in this provider"
                                      : "Select all models in this provider"
                                  }
                                >
                                  {allSelected ? (
                                    <CheckSquare size={14} className="text-indigo-400" />
                                  ) : isPartiallySelected ? (
                                    <MinusSquare size={14} className="text-indigo-400" />
                                  ) : (
                                    <Square size={14} className="text-slate-500" />
                                  )}
                                </button>
                              </th>
                              <th className="py-2.5 px-4">Canonical Slug & Display Name</th>
                              <th className="py-2.5 px-4">
                                <div className="flex items-center gap-1">
                                  <Brain size={12} className="text-indigo-400" />
                                  <span>Intelligence</span>
                                </div>
                              </th>
                              <th className="py-2.5 px-4">Capabilities</th>
                              <th className="py-2.5 px-4">Limits & Context</th>
                              <th className="py-2.5 px-4">Availability</th>
                              <th className="py-2.5 px-4 text-center w-24">Display</th>
                              <th className="py-2.5 px-4 text-right">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/50 text-slate-300">
                            {groupModels.map((m) => {
                              const isSelected = selectedModelIds.has(m.id);
                              const isHidden = m.is_visible === false;

                              return (
                                <tr
                                  key={m.id}
                                  id={`model-row-${m.id}`}
                                  className={`hover:bg-slate-800/25 transition-colors ${
                                    isSelected ? "bg-indigo-950/20" : isHidden ? "opacity-60 bg-slate-950/40" : ""
                                  }`}
                                >
                                  {/* Row Checkbox */}
                                  <td
                                    className="py-2.5 px-4 text-center cursor-pointer select-none"
                                    onClick={(e) => handleModelCheckboxClick(m.id, e)}
                                    title="Click to select/deselect (Hold Shift to select range)"
                                  >
                                    <input
                                      type="checkbox"
                                      checked={isSelected}
                                      readOnly
                                      className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-0 pointer-events-none"
                                    />
                                  </td>

                                {/* Canonical Slug & Display Name */}
                                <td className="py-2.5 px-4 font-mono font-medium text-indigo-300">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <span>{m.canonical_slug}</span>
                                    {newModelSlugsSet.has(m.canonical_slug) && (
                                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-500/25 text-emerald-300 border border-emerald-500/40 animate-pulse flex items-center gap-0.5">
                                        <Sparkles size={9} /> NEW
                                      </span>
                                    )}
                                    {isHidden && (
                                      <span className="text-[10px] text-amber-400/80 font-sans italic">
                                        (hidden)
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-[11px] text-slate-400 font-sans mt-0.5">
                                    {m.display_name}
                                  </div>
                                </td>

                                {/* Intelligence / Rating */}
                                <td className="py-2.5 px-4">
                                  <ModelIntelligenceBadge
                                    modelId={m.id}
                                    rating={m.rating}
                                    capabilities={m.capabilities}
                                    contextLength={m.context_length}
                                    maxOutputTokens={m.max_output_tokens}
                                    initialLimits={m.limits}
                                    onLimitsFetched={(newLimits) => {
                                      setModels((prev) =>
                                        prev.map((item) =>
                                          item.id === m.id
                                            ? {
                                                ...item,
                                                context_length: newLimits.context_length ?? item.context_length,
                                                max_output_tokens: newLimits.max_output_tokens ?? item.max_output_tokens,
                                                limits: newLimits,
                                              }
                                            : item
                                        )
                                      );
                                      setNewlyDiscoveredModels((prev) =>
                                        prev.map((item) =>
                                          item.id === m.id
                                            ? {
                                                ...item,
                                                context_length: newLimits.context_length ?? item.context_length,
                                                max_output_tokens: newLimits.max_output_tokens ?? item.max_output_tokens,
                                                limits: newLimits,
                                              }
                                            : item
                                        )
                                      );
                                    }}
                                  />
                                </td>

                                {/* Capabilities tags */}
                                <td className="py-2.5 px-4">
                                  <div className="flex flex-wrap gap-1">
                                    {m.capabilities?.streaming && (
                                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300">
                                        stream
                                      </span>
                                    )}
                                    {m.capabilities?.vision === true && (
                                      <span className="px-1.5 py-0.5 rounded bg-cyan-950 text-[10px] text-cyan-300 border border-cyan-800/60">
                                        vision
                                      </span>
                                    )}
                                    {m.capabilities?.tools === true && (
                                      <span className="px-1.5 py-0.5 rounded bg-purple-950 text-[10px] text-purple-300 border border-purple-800/60">
                                        tools
                                      </span>
                                    )}
                                    {m.capabilities?.reasoning === true && (
                                      <span className="px-1.5 py-0.5 rounded bg-amber-950 text-[10px] text-amber-300 border border-amber-800/60">
                                        thinking
                                      </span>
                                    )}
                                  </div>
                                </td>

                                {/* Limits & Context */}
                                <td className="py-2.5 px-4 font-mono text-[11px]">
                                  <div className="flex items-center gap-1.5 flex-wrap">
                                    <button
                                      onClick={() => openContextModal(m)}
                                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-800/80 hover:bg-indigo-950/80 hover:border-indigo-600/60 border border-slate-700/60 text-slate-200 hover:text-indigo-200 transition-colors group cursor-pointer"
                                      title="Click to configure model context length"
                                    >
                                      <span className="font-semibold text-slate-200 group-hover:text-indigo-200">
                                        {m.context_length
                                          ? m.context_length >= 1_000_000
                                            ? `${(m.context_length / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`
                                            : `${Math.round(m.context_length / 1000)}k`
                                          : "—"}
                                      </span>
                                      <SlidersHorizontal size={10} className="text-slate-500 group-hover:text-indigo-400 transition-colors" />
                                    </button>
                                    <button
                                      onClick={() => openReasoningModal(m)}
                                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border transition-colors cursor-pointer group ${
                                        m.reasoning_effort
                                          ? "bg-amber-950/60 hover:bg-amber-900/80 border-amber-600/50 text-amber-200"
                                          : "bg-slate-800/80 hover:bg-slate-700/80 border-slate-700/60 text-slate-400 hover:text-slate-200"
                                      }`}
                                      title="Click to configure default reasoning effort for model"
                                    >
                                      <Brain size={10} className={m.reasoning_effort ? "text-amber-400" : "text-slate-500 group-hover:text-slate-300"} />
                                      <span>{m.reasoning_effort ? `effort: ${m.reasoning_effort}` : "effort: —"}</span>
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => openTempModal(m)}
                                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border transition-colors cursor-pointer group ${
                                        m.temperature !== null && m.temperature !== undefined
                                          ? "bg-rose-950/60 hover:bg-rose-900/80 border-rose-600/50 text-rose-200"
                                          : "bg-slate-800/80 hover:bg-slate-700/80 border-slate-700/60 text-slate-400 hover:text-slate-200"
                                      }`}
                                      title="Click to configure default temperature for model"
                                    >
                                      <Thermometer size={10} className={m.temperature !== null && m.temperature !== undefined ? "text-rose-400" : "text-slate-500 group-hover:text-slate-300"} />
                                      <span>{m.temperature !== null && m.temperature !== undefined ? `temp: ${m.temperature}` : "temp: —"}</span>
                                    </button>
                                    {m.max_output_tokens ? (
                                      <span className="text-[10px] text-slate-500" title={`Max output: ${m.max_output_tokens.toLocaleString()} tokens`}>
                                        /{m.max_output_tokens >= 1000 ? `${Math.round(m.max_output_tokens / 1000)}k out` : `${m.max_output_tokens} out`}
                                      </span>
                                    ) : null}
                                    {m.limits?.rate_limit_rpm ? (
                                      <span
                                        className="px-1.5 py-0.5 rounded bg-amber-950/40 text-amber-300 border border-amber-500/30 text-[10px] inline-flex items-center gap-1"
                                        title={`Rate limit: ${m.limits.rate_limit_rpm} RPM${m.limits.rate_limit_rpd ? ` | ${m.limits.rate_limit_rpd.toLocaleString()} / day` : ""}`}
                                      >
                                        <span>⚡{m.limits.rate_limit_rpm} RPM</span>
                                        {m.limits.rate_limit_rpd ? (
                                          <span className="text-amber-400/80 font-normal">
                                            ({m.limits.rate_limit_rpd >= 1000 ? `${(m.limits.rate_limit_rpd / 1000).toFixed(1)}k` : m.limits.rate_limit_rpd}/d)
                                          </span>
                                        ) : null}
                                      </span>
                                    ) : null}
                                  </div>
                                </td>

                                {/* Available state */}
                                <td className="py-2.5 px-4">
                                  {m.available ? (
                                    <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px] font-medium">
                                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                                      Available
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 text-slate-500 text-[11px]">
                                      <span className="w-1.5 h-1.5 rounded-full bg-slate-600" />
                                      Unavailable
                                    </span>
                                  )}
                                </td>

                                {/* Hide / Unhide Toggle button */}
                                <td className="py-2.5 px-4 text-center">
                                  <button
                                    onClick={() => toggleHideModel(m)}
                                    className={`p-1 rounded transition-colors ${
                                      isHidden
                                        ? "text-amber-400 hover:bg-amber-950/60 hover:text-amber-300"
                                        : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                                    }`}
                                    title={isHidden ? "Unhide model (show in API & UI)" : "Hide model from API & UI"}
                                  >
                                    {isHidden ? <EyeOff size={14} /> : <Eye size={14} />}
                                  </button>
                                </td>

                                {/* Enabled toggle */}
                                <td className="py-2.5 px-4 text-right">
                                  <button
                                    onClick={() => handleToggleEnabled(m)}
                                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                                      m.enabled
                                        ? "bg-emerald-600/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-600/30"
                                        : "bg-slate-800 text-slate-500 border border-slate-700 hover:text-slate-300"
                                    }`}
                                  >
                                    {m.enabled ? "Active" : "Disabled"}
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Modal: Add Manual Model */}
      <Modal
        isOpen={isManualModalOpen}
        onClose={() => setIsManualModalOpen(false)}
        title="Add Model Manually"
      >
        <form onSubmit={handleAddManual} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Provider</label>
            <select
              value={manualProviderId}
              onChange={(e) => setManualProviderId(parseInt(e.target.value))}
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Provider Model ID</label>
            <input
              type="text"
              required
              value={manualModelId}
              onChange={(e) => setManualModelId(e.target.value)}
              placeholder="e.g. meta-llama/Llama-3-70b-instruct"
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Display Name</label>
            <input
              type="text"
              value={manualDisplayName}
              onChange={(e) => setManualDisplayName(e.target.value)}
              placeholder="e.g. Llama 3 70B"
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Context Length</label>
            <input
              type="number"
              value={manualContextLength}
              onChange={(e) => setManualContextLength(e.target.value)}
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
            />
          </div>

          <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={() => setIsManualModalOpen(false)}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs"
            >
              Add Model
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal: Single Model Context Configuration */}
      <Modal
        isOpen={!!contextModalModel}
        onClose={() => setContextModalModel(null)}
        title="Configure Model Context Window"
        maxWidth="lg"
      >
        {contextModalModel && (
          <div className="space-y-4">
            {/* Model Info Header */}
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg">
              <div className="text-xs font-mono font-semibold text-indigo-300 break-all">
                {contextModalModel.canonical_slug}
              </div>
              <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between flex-wrap gap-2">
                <span>
                  Provider: <span className="text-slate-200 font-medium">{contextModalModel.provider_name}</span>
                </span>
                <span>
                  Current Context:{" "}
                  <span className="text-indigo-400 font-mono font-medium">
                    {contextModalModel.context_length
                      ? `${contextModalModel.context_length.toLocaleString()} tokens (${
                          contextModalModel.context_length >= 1_000_000
                            ? (contextModalModel.context_length / 1_000_000).toFixed(1) + "M"
                            : Math.round(contextModalModel.context_length / 1000) + "K"
                        })`
                      : "Not set (default 131,072 in Hermes)"}
                  </span>
                </span>
              </div>
            </div>

            {/* Presets Grid */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">
                Quick Preset Selection:
              </label>
              <div className="grid grid-cols-4 sm:grid-cols-6 gap-1.5">
                {CONTEXT_PRESETS.map((preset) => {
                  const isSelected = selectedContextPreset === preset.value;
                  return (
                    <button
                      key={preset.value}
                      type="button"
                      onClick={() => handleSelectPreset(preset.value)}
                      className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                        isSelected
                          ? "bg-indigo-600/30 border-indigo-500 text-indigo-200 shadow-xs ring-1 ring-indigo-500/50"
                          : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                      }`}
                    >
                      <div className="font-bold">{preset.label}</div>
                      <div className="text-[10px] text-slate-400 opacity-80">
                        {preset.value >= 1_000_000
                          ? `${(preset.value / 1_000_000).toFixed(1)}M`
                          : `${Math.round(preset.value / 1000)}k`}
                      </div>
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => handleSelectPreset("custom")}
                  className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                    selectedContextPreset === "custom"
                      ? "bg-indigo-600/30 border-indigo-500 text-indigo-200 shadow-xs ring-1 ring-indigo-500/50"
                      : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                  }`}
                >
                  <div className="font-bold">Custom</div>
                  <div className="text-[10px] text-slate-400 opacity-80">custom value</div>
                </button>
              </div>
            </div>

            {/* Custom Input */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-medium text-slate-300">
                  Context Window (tokens):
                </label>
                {customContextInput && parseInt(customContextInput, 10) > 0 && (
                  <span className="text-[11px] font-mono text-indigo-400">
                    ≈{" "}
                    {parseInt(customContextInput, 10) >= 1_000_000
                      ? `${(parseInt(customContextInput, 10) / 1_000_000).toFixed(2)}M`
                      : `${Math.round(parseInt(customContextInput, 10) / 1000)}k`}{" "}
                    tokens ({parseInt(customContextInput, 10).toLocaleString()} tokens)
                  </span>
                )}
              </div>
              <input
                type="number"
                min="1"
                step="1"
                value={customContextInput}
                onChange={handleCustomInputChange}
                placeholder="e.g.: 32768, 64000, 128000, 1000000"
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
              />
            </div>

            {/* Hint & Hermes Documentation */}
            <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-lg text-[11px] space-y-1.5 text-slate-300">
              <div className="flex items-center gap-1.5 text-indigo-400 font-medium">
                <Sparkles size={13} />
                <span>Local Override Priority</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                Saved value is stored in the MyAIrouter database and takes top priority over provider defaults. It propagates to Hermes (<code className="text-indigo-300 font-mono text-[10px]">/api/show</code>), Ollama clients, and the OpenAI API.
              </p>
              <p className="text-amber-300/90">
                💡 <strong>For Hermes:</strong> If the model was previously used in Hermes, run <code className="bg-slate-900 border border-slate-800 px-1 py-0.5 rounded text-amber-200 font-mono text-[10px]">hermes model --refresh</code> in your terminal to refresh the context cache.
              </p>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <button
                type="button"
                disabled={savingContext}
                onClick={() => handleSaveModelContext(true)}
                className="px-3 py-1.5 bg-slate-800/80 hover:bg-amber-950/60 hover:text-amber-300 text-slate-400 rounded-lg text-xs font-medium border border-slate-700/60 transition-colors cursor-pointer"
                title="Reset to provider default / auto"
              >
                Reset to Provider Default
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={savingContext}
                  onClick={() => setContextModalModel(null)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={savingContext || !customContextInput || parseInt(customContextInput, 10) <= 0}
                  onClick={() => handleSaveModelContext(false)}
                  className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  {savingContext ? <RefreshCw size={13} className="animate-spin" /> : null}
                  <span>Save Context</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Modal: Batch Models Context Configuration */}
      <Modal
        isOpen={isBatchContextModalOpen}
        onClose={() => setIsBatchContextModalOpen(false)}
        title={`Batch Context Configuration (${selectedModelIds.size} models)`}
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="p-3 bg-indigo-950/40 border border-indigo-800/60 rounded-lg text-xs text-indigo-200">
            Selected models: <strong>{selectedModelIds.size}</strong>. The configured context length will be applied to all selected models.
          </div>

          {/* Presets Grid */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">
              Quick Preset Selection:
            </label>
            <div className="grid grid-cols-4 sm:grid-cols-6 gap-1.5">
              {CONTEXT_PRESETS.map((preset) => {
                const isSelected = selectedContextPreset === preset.value;
                return (
                  <button
                    key={preset.value}
                    type="button"
                    onClick={() => handleSelectPreset(preset.value)}
                    className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                      isSelected
                        ? "bg-indigo-600/30 border-indigo-500 text-indigo-200 shadow-xs ring-1 ring-indigo-500/50"
                        : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                    }`}
                  >
                    <div className="font-bold">{preset.label}</div>
                    <div className="text-[10px] text-slate-400 opacity-80">
                      {preset.value >= 1_000_000
                        ? `${(preset.value / 1_000_000).toFixed(1)}M`
                        : `${Math.round(preset.value / 1000)}k`}
                    </div>
                  </button>
                );
              })}
              <button
                type="button"
                onClick={() => handleSelectPreset("custom")}
                className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                  selectedContextPreset === "custom"
                    ? "bg-indigo-600/30 border-indigo-500 text-indigo-200 shadow-xs ring-1 ring-indigo-500/50"
                    : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                }`}
              >
                <div className="font-bold">Custom</div>
                <div className="text-[10px] text-slate-400 opacity-80">custom value</div>
              </button>
            </div>
          </div>

          {/* Custom Input */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-medium text-slate-300">
                Context Window (tokens):
              </label>
              {customContextInput && parseInt(customContextInput, 10) > 0 && (
                <span className="text-[11px] font-mono text-indigo-400">
                  ≈{" "}
                  {parseInt(customContextInput, 10) >= 1_000_000
                    ? `${(parseInt(customContextInput, 10) / 1_000_000).toFixed(2)}M`
                    : `${Math.round(parseInt(customContextInput, 10) / 1000)}k`}{" "}
                  tokens ({parseInt(customContextInput, 10).toLocaleString()} tokens)
                </span>
              )}
            </div>
            <input
              type="number"
              min="1"
              step="1"
              value={customContextInput}
              onChange={handleCustomInputChange}
              placeholder="e.g.: 32768, 64000, 128000, 1000000"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
            />
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-slate-800">
            <button
              type="button"
              disabled={savingContext}
              onClick={() => handleSaveBatchContext(true)}
              className="px-3 py-1.5 bg-slate-800/80 hover:bg-amber-950/60 hover:text-amber-300 text-slate-400 rounded-lg text-xs font-medium border border-slate-700/60 transition-colors cursor-pointer"
            >
              Reset for All
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={savingContext}
                onClick={() => setIsBatchContextModalOpen(false)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={savingContext || !customContextInput || parseInt(customContextInput, 10) <= 0}
                onClick={() => handleSaveBatchContext(false)}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                {savingContext ? <RefreshCw size={13} className="animate-spin" /> : null}
                <span>Apply to All ({selectedModelIds.size})</span>
              </button>
            </div>
          </div>
        </div>
      </Modal>

      {/* Modal: Single Model Reasoning Effort Configuration */}
      <Modal
        isOpen={!!reasoningModalModel}
        onClose={() => setReasoningModalModel(null)}
        title="Configure Model Reasoning Effort"
        maxWidth="lg"
      >
        {reasoningModalModel && (
          <div className="space-y-4">
            {/* Model Info Header */}
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg">
              <div className="text-xs font-mono font-semibold text-amber-300 break-all">
                {reasoningModalModel.canonical_slug}
              </div>
              <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between flex-wrap gap-2">
                <span>
                  Provider: <span className="text-slate-200 font-medium">{reasoningModalModel.provider_name}</span>
                </span>
                <span>
                  Current reasoning effort:{" "}
                  <span className="text-amber-400 font-mono font-semibold">
                    {reasoningModalModel.reasoning_effort || "Not set (default)"}
                  </span>
                </span>
              </div>
            </div>

            {/* Presets Grid */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">
                Quick Preset Selection:
              </label>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
                {REASONING_PRESETS.map((preset) => {
                  const isSelected = selectedReasoningPreset === preset.label;
                  return (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => handleSelectReasoningPreset(preset.label)}
                      className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                        isSelected
                          ? "bg-amber-600/30 border-amber-500 text-amber-200 shadow-xs ring-1 ring-amber-500/50"
                          : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                      }`}
                    >
                      <div className="font-bold font-mono">{preset.label}</div>
                      <div className="text-[10px] text-slate-400 opacity-80 mt-0.5 truncate">
                        {preset.title.split(" ")[0]}
                      </div>
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => handleSelectReasoningPreset("custom")}
                  className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                    selectedReasoningPreset === "custom"
                      ? "bg-amber-600/30 border-amber-500 text-amber-200 shadow-xs ring-1 ring-amber-500/50"
                      : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                  }`}
                >
                  <div className="font-bold">Custom</div>
                  <div className="text-[10px] text-slate-400 opacity-80 mt-0.5">custom word</div>
                </button>
              </div>
            </div>

            {/* Custom Input */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-medium text-slate-300">
                  Reasoning Effort Level (word only):
                </label>
                <span className="text-[11px] text-slate-400">
                  Letters only, no digits
                </span>
              </div>
              <input
                type="text"
                value={customReasoningInput}
                onChange={handleCustomReasoningInputChange}
                placeholder="e.g.: none, low, medium, high, auto, minimal, thorough..."
                className={`w-full px-3 py-2 bg-slate-950 border rounded-lg text-slate-100 text-xs focus:outline-none font-mono ${
                  reasoningValidationError ? "border-rose-500 focus:border-rose-500" : "border-slate-800 focus:border-amber-500"
                }`}
              />
              {reasoningValidationError && (
                <div className="mt-1 text-[11px] text-rose-400 flex items-center gap-1 font-medium">
                  <span>⚠️ {reasoningValidationError}</span>
                </div>
              )}
            </div>

            {/* Hint & Documentation */}
            <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-lg text-[11px] space-y-1.5 text-slate-300">
              <div className="flex items-center gap-1.5 text-amber-400 font-medium">
                <Brain size={13} />
                <span>Default Reasoning Effort</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                Default model value: used during API requests if client omits an explicit reasoning_effort parameter.
              </p>
              <p className="text-amber-300/90">
                🔒 <strong>Rule:</strong> Only words are allowed (e.g. <code className="bg-slate-900 border border-slate-800 px-1 py-0.5 rounded text-amber-200 font-mono text-[10px]">low</code>, <code className="bg-slate-900 border border-slate-800 px-1 py-0.5 rounded text-amber-200 font-mono text-[10px]">medium</code>, <code className="bg-slate-900 border border-slate-800 px-1 py-0.5 rounded text-amber-200 font-mono text-[10px]">high</code>, <code className="bg-slate-900 border border-slate-800 px-1 py-0.5 rounded text-amber-200 font-mono text-[10px]">none</code>, <code className="bg-slate-900 border border-slate-800 px-1 py-0.5 rounded text-amber-200 font-mono text-[10px]">minimal</code>). Numbers and digits are prohibited.
              </p>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <button
                type="button"
                disabled={savingReasoning}
                onClick={() => handleSaveModelReasoning(true)}
                className="px-3 py-1.5 bg-slate-800/80 hover:bg-amber-950/60 hover:text-amber-300 text-slate-400 rounded-lg text-xs font-medium border border-slate-700/60 transition-colors cursor-pointer"
                title="Reset to default value"
              >
                Reset to Default
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={savingReasoning}
                  onClick={() => setReasoningModalModel(null)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={savingReasoning || !customReasoningInput || /\d/.test(customReasoningInput)}
                  onClick={() => handleSaveModelReasoning(false)}
                  className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  {savingReasoning ? <RefreshCw size={13} className="animate-spin" /> : null}
                  <span>Save Reasoning</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Modal: Batch Models Reasoning Effort Configuration */}
      <Modal
        isOpen={isBatchReasoningModalOpen}
        onClose={() => setIsBatchReasoningModalOpen(false)}
        title={`Batch Reasoning Effort Configuration (${selectedModelIds.size} models)`}
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-lg text-xs text-amber-200">
            Selected models: <strong>{selectedModelIds.size}</strong>. The configured reasoning effort will be applied to all selected models.
          </div>

          {/* Presets Grid */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">
              Quick Preset Selection:
            </label>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
              {REASONING_PRESETS.map((preset) => {
                const isSelected = selectedReasoningPreset === preset.label;
                return (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => handleSelectReasoningPreset(preset.label)}
                    className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                      isSelected
                        ? "bg-amber-600/30 border-amber-500 text-amber-200 shadow-xs ring-1 ring-amber-500/50"
                        : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                    }`}
                  >
                    <div className="font-bold font-mono">{preset.label}</div>
                    <div className="text-[10px] text-slate-400 opacity-80 mt-0.5 truncate">
                      {preset.title.split(" ")[0]}
                    </div>
                  </button>
                );
              })}
              <button
                type="button"
                onClick={() => handleSelectReasoningPreset("custom")}
                className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                  selectedReasoningPreset === "custom"
                    ? "bg-amber-600/30 border-amber-500 text-amber-200 shadow-xs ring-1 ring-amber-500/50"
                    : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                }`}
              >
                <div className="font-bold">Custom</div>
                <div className="text-[10px] text-slate-400 opacity-80 mt-0.5">custom word</div>
              </button>
            </div>
          </div>

          {/* Custom Input */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-medium text-slate-300">
                Reasoning Effort Level (word only):
              </label>
              <span className="text-[11px] text-slate-400">
                Letters only, no digits
              </span>
            </div>
            <input
              type="text"
              value={customReasoningInput}
              onChange={handleCustomReasoningInputChange}
              placeholder="e.g.: none, low, medium, high, auto..."
              className={`w-full px-3 py-2 bg-slate-950 border rounded-lg text-slate-100 text-xs focus:outline-none font-mono ${
                reasoningValidationError ? "border-rose-500 focus:border-rose-500" : "border-slate-800 focus:border-amber-500"
              }`}
            />
            {reasoningValidationError && (
              <div className="mt-1 text-[11px] text-rose-400 flex items-center gap-1 font-medium">
                <span>⚠️ {reasoningValidationError}</span>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-slate-800">
            <button
              type="button"
              disabled={savingReasoning}
              onClick={() => handleSaveBatchReasoning(true)}
              className="px-3 py-1.5 bg-slate-800/80 hover:bg-amber-950/60 hover:text-amber-300 text-slate-400 rounded-lg text-xs font-medium border border-slate-700/60 transition-colors cursor-pointer"
            >
              Reset for All
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={savingReasoning}
                onClick={() => setIsBatchReasoningModalOpen(false)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={savingReasoning || !customReasoningInput || /\d/.test(customReasoningInput)}
                onClick={() => handleSaveBatchReasoning(false)}
                className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                {savingReasoning ? <RefreshCw size={13} className="animate-spin" /> : null}
                <span>Apply to {selectedModelIds.size} models</span>
              </button>
            </div>
          </div>
        </div>
      </Modal>

      {/* Modal: Single Model Temperature Configuration */}
      <Modal
        isOpen={!!tempModalModel}
        onClose={() => setTempModalModel(null)}
        title="Configure Model Temperature"
        maxWidth="lg"
      >
        {tempModalModel && (
          <div className="space-y-4">
            {/* Model Info Header */}
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg">
              <div className="text-xs font-mono font-semibold text-rose-300 break-all">
                {tempModalModel.canonical_slug}
              </div>
              <div className="text-[11px] text-slate-400 mt-1 flex items-center justify-between flex-wrap gap-2">
                <span>
                  Provider: <span className="text-slate-200 font-medium">{tempModalModel.provider_name}</span>
                </span>
                <span>
                  Current temperature:{" "}
                  <span className="text-rose-400 font-mono font-semibold">
                    {tempModalModel.temperature !== null && tempModalModel.temperature !== undefined
                      ? tempModalModel.temperature
                      : "Default (provider native)"}
                  </span>
                </span>
              </div>
            </div>

            {/* Presets Grid */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">
                Quick Preset Selection:
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                {TEMPERATURE_PRESETS.map((preset) => {
                  const isSelected = selectedTempPreset === preset.label;
                  return (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => handleSelectTempPreset(preset.label)}
                      className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                        isSelected
                          ? "bg-rose-600/30 border-rose-500 text-rose-200 shadow-xs ring-1 ring-rose-500/50"
                          : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                      }`}
                    >
                      <div className="font-bold font-mono">{preset.title}</div>
                      <div className="text-[10px] text-slate-400 opacity-80 mt-0.5 truncate">
                        {preset.desc}
                      </div>
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={() => handleSelectTempPreset("custom")}
                  className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                    selectedTempPreset === "custom"
                      ? "bg-rose-600/30 border-rose-500 text-rose-200 shadow-xs ring-1 ring-rose-500/50"
                      : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                  }`}
                >
                  <div className="font-bold">Custom</div>
                  <div className="text-[10px] text-slate-400 opacity-80 mt-0.5">slider / input</div>
                </button>
              </div>
            </div>

            {/* Slider & Custom Input */}
            <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-medium text-slate-300">
                  Temperature value (0.0 — 2.0):
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0"
                    max="2"
                    step="0.05"
                    value={customTempInput}
                    onChange={handleCustomTempInputChange}
                    placeholder="Provider default"
                    className={`w-28 px-2.5 py-1 bg-slate-900 border rounded-lg text-slate-100 text-xs font-mono text-right focus:outline-none ${
                      tempValidationError ? "border-rose-500 focus:border-rose-500" : "border-slate-700 focus:border-rose-500"
                    }`}
                  />
                  <span className="text-xs text-slate-400 font-mono">°T</span>
                </div>
              </div>

              {/* Range slider */}
              <div className="space-y-1">
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.05"
                  value={customTempInput !== "" && !isNaN(parseFloat(customTempInput)) ? parseFloat(customTempInput) : 0.7}
                  onChange={(e) => {
                    const val = e.target.value;
                    setCustomTempInput(val);
                    setTempValidationError(null);
                    const match = TEMPERATURE_PRESETS.find(
                      (p) => p.value !== null && Math.abs(p.value - parseFloat(val)) < 0.001
                    );
                    setSelectedTempPreset(match ? match.label : "custom");
                  }}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>0.0 (Strict)</span>
                  <span>0.7 (Chat)</span>
                  <span>1.0 (Creative)</span>
                  <span>2.0 (Max)</span>
                </div>
              </div>

              {tempValidationError && (
                <div className="text-[11px] text-rose-400 flex items-center gap-1 font-medium">
                  <span>⚠️ {tempValidationError}</span>
                </div>
              )}
            </div>

            {/* Hint & Documentation */}
            <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-lg text-[11px] space-y-1.5 text-slate-300">
              <div className="flex items-center gap-1.5 text-rose-400 font-medium">
                <Thermometer size={13} />
                <span>Model Default Temperature</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                Default temperature value: applied by the router if incoming client request omits explicit <code className="text-rose-300 font-mono">temperature</code>.
              </p>
              <p className="text-rose-300/90">
                🌡️ <strong>Behavior:</strong> Clicking <em>"Reset to Default"</em> clears local override and relies on upstream provider native defaults.
              </p>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <button
                type="button"
                disabled={savingTemp}
                onClick={() => handleSaveModelTemp(true)}
                className="px-3 py-1.5 bg-slate-800/80 hover:bg-rose-950/60 hover:text-rose-300 text-slate-400 rounded-lg text-xs font-medium border border-slate-700/60 transition-colors cursor-pointer"
                title="Reset to provider native default"
              >
                Reset to Default
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={savingTemp}
                  onClick={() => setTempModalModel(null)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={savingTemp || !!tempValidationError}
                  onClick={() => handleSaveModelTemp(false)}
                  className="px-4 py-1.5 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  {savingTemp ? <RefreshCw size={13} className="animate-spin" /> : null}
                  <span>Save Temperature</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Modal: Batch Models Temperature Configuration */}
      <Modal
        isOpen={isBatchTempModalOpen}
        onClose={() => setIsBatchTempModalOpen(false)}
        title={`Batch Temperature Configuration (${selectedModelIds.size} models)`}
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-lg text-xs text-rose-200">
            Selected models: <strong>{selectedModelIds.size}</strong>. The configured temperature will be applied to all selected models.
          </div>

          {/* Presets Grid */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">
              Quick Preset Selection:
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {TEMPERATURE_PRESETS.map((preset) => {
                const isSelected = selectedTempPreset === preset.label;
                return (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => handleSelectTempPreset(preset.label)}
                    className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                      isSelected
                        ? "bg-rose-600/30 border-rose-500 text-rose-200 shadow-xs ring-1 ring-rose-500/50"
                        : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                    }`}
                  >
                    <div className="font-bold font-mono">{preset.title}</div>
                    <div className="text-[10px] text-slate-400 opacity-80 mt-0.5 truncate">
                      {preset.desc}
                    </div>
                  </button>
                );
              })}
              <button
                type="button"
                onClick={() => handleSelectTempPreset("custom")}
                className={`px-2 py-2 rounded-lg text-xs font-medium transition-all text-center border cursor-pointer ${
                  selectedTempPreset === "custom"
                    ? "bg-rose-600/30 border-rose-500 text-rose-200 shadow-xs ring-1 ring-rose-500/50"
                    : "bg-slate-950/60 border-slate-800 text-slate-300 hover:bg-slate-800 hover:text-slate-100 hover:border-slate-700"
                }`}
              >
                <div className="font-bold">Custom</div>
                <div className="text-[10px] text-slate-400 opacity-80 mt-0.5">slider / input</div>
              </button>
            </div>
          </div>

          {/* Slider & Custom Input */}
          <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-3">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-medium text-slate-300">
                Temperature value (0.0 — 2.0):
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="0"
                  max="2"
                  step="0.05"
                  value={customTempInput}
                  onChange={handleCustomTempInputChange}
                  placeholder="Provider default"
                  className={`w-28 px-2.5 py-1 bg-slate-900 border rounded-lg text-slate-100 text-xs font-mono text-right focus:outline-none ${
                    tempValidationError ? "border-rose-500 focus:border-rose-500" : "border-slate-700 focus:border-rose-500"
                  }`}
                />
                <span className="text-xs text-slate-400 font-mono">°T</span>
              </div>
            </div>

            {/* Range slider */}
            <div className="space-y-1">
              <input
                type="range"
                min="0"
                max="2"
                step="0.05"
                value={customTempInput !== "" && !isNaN(parseFloat(customTempInput)) ? parseFloat(customTempInput) : 0.7}
                onChange={(e) => {
                  const val = e.target.value;
                  setCustomTempInput(val);
                  setTempValidationError(null);
                  const match = TEMPERATURE_PRESETS.find(
                    (p) => p.value !== null && Math.abs(p.value - parseFloat(val)) < 0.001
                  );
                  setSelectedTempPreset(match ? match.label : "custom");
                }}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-rose-500"
              />
              <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                <span>0.0 (Strict)</span>
                <span>0.7 (Chat)</span>
                <span>1.0 (Creative)</span>
                <span>2.0 (Max)</span>
              </div>
            </div>

            {tempValidationError && (
              <div className="text-[11px] text-rose-400 flex items-center gap-1 font-medium">
                <span>⚠️ {tempValidationError}</span>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-slate-800">
            <button
              type="button"
              disabled={savingTemp}
              onClick={() => handleSaveBatchTemp(true)}
              className="px-3 py-1.5 bg-slate-800/80 hover:bg-rose-950/60 hover:text-rose-300 text-slate-400 rounded-lg text-xs font-medium border border-slate-700/60 transition-colors cursor-pointer"
            >
              Reset for All
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={savingTemp}
                onClick={() => setIsBatchTempModalOpen(false)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={savingTemp || !!tempValidationError}
                onClick={() => handleSaveBatchTemp(false)}
                className="px-4 py-1.5 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
              >
                {savingTemp ? <RefreshCw size={13} className="animate-spin" /> : null}
                <span>Apply to {selectedModelIds.size} models</span>
              </button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
};
