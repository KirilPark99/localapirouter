import React, { useEffect, useState } from "react";
import {
  Zap,
  Sparkles,
  Sliders,
  Layers,
  Terminal,
  Table,
  Filter,
  MessageSquareDashed,
  History,
  BrainCircuit,
  Flame,
  Image,
  CopyMinus,
  Archive,
  Wrench,
  ArrowUp,
  ArrowDown,
  Settings,
  Plus,
  Trash2,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ShieldCheck,
  Database,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { Modal } from "../components/Modal";
import {
  CompressionStageItem,
  CompressionGlobalSettings,
  CompressionPreviewResponse,
  StageConfigField,
  CacheStats,
} from "../types";

export const CompressionPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"pipeline" | "playground">("pipeline");
  const [loading, setLoading] = useState<boolean>(true);
  const [savingGlobal, setSavingGlobal] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Cache stats & operations
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [loadingCache, setLoadingCache] = useState<boolean>(false);
  const [clearingCache, setClearingCache] = useState<boolean>(false);

  // Global settings
  const [globalSettings, setGlobalSettings] = useState<CompressionGlobalSettings>({
    enabled: true,
    trigger_token_threshold: 1000,
    min_savings_bailout_percent: 0.0,
    preserve_recent_turns: 1,
    enable_telemetry: true,
    fail_open: true,
    preserve_system_prompt_mode: "when_caching",
  });

  // Stages
  const [stages, setStages] = useState<CompressionStageItem[]>([]);

  // Configure modal
  const [configModalStage, setConfigModalStage] = useState<CompressionStageItem | null>(null);
  const [editingConfig, setEditingConfig] = useState<Record<string, any>>({});

  // Add custom stage modal
  const [showAddCustomModal, setShowAddCustomModal] = useState<boolean>(false);
  const [newStageName, setNewStageName] = useState<string>("");
  const [newStageId, setNewStageId] = useState<string>("");
  const [newStageDesc, setNewStageDesc] = useState<string>("");
  const [newStageRules, setNewStageRules] = useState<Array<{ pattern: string; replacement: string; case_sensitive: boolean }>>([
    { pattern: "\\b(foo)\\b", replacement: "bar", case_sensitive: false },
  ]);
  const [newStageGuardCode, setNewStageGuardCode] = useState<boolean>(true);

  // Playground state
  const [playgroundMessages, setPlaygroundMessages] = useState<string>(
    JSON.stringify(
      [
        { role: "system", content: "You are a helpful coding assistant." },
        {
          role: "user",
          content: "Hello! Could you please kindly help me with reading and writing files in Python?",
        },
        {
          role: "assistant",
          content:
            "Sure! Certainly, I would be glad to help you with that.\n\nHere is the code in order to read a file:\n```python\nwith open('data.txt', 'r') as f:\n    content = f.read()\n    print(content)\n```\nNote that it is important to remember to handle exceptions.\n\n```json\n[\n  {\"id\": 1, \"status\": \"ok\", \"code\": 200},\n  {\"id\": 2, \"status\": \"ok\", \"code\": 200},\n  {\"id\": 3, \"status\": \"ok\", \"code\": 200},\n  {\"id\": 4, \"status\": \"ok\", \"code\": 200},\n  {\"id\": 5, \"status\": \"ok\", \"code\": 200},\n  {\"id\": 6, \"status\": \"ok\", \"code\": 200}\n]\n```\n\nHope this helps!",
        },
        { role: "user", content: "Could you show an example of writing as well?" },
      ],
      null,
      2
    )
  );
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [previewResult, setPreviewResult] = useState<CompressionPreviewResponse | null>(null);

  const fetchAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [settingsData, stagesData, statsData] = await Promise.all([
        apiRequest<CompressionGlobalSettings>("/api/admin/compression/settings"),
        apiRequest<CompressionStageItem[]>("/api/admin/compression/stages"),
        apiRequest<CacheStats>("/api/admin/cache/stats").catch(() => null),
      ]);
      setGlobalSettings(settingsData);
      setStages(stagesData);
      if (statsData) setCacheStats(statsData);
    } catch (err: any) {
      setError(err?.message || "Ошибка загрузки настроек оптимизации");
    } finally {
      setLoading(false);
    }
  };

  const fetchCacheStats = async () => {
    try {
      setLoadingCache(true);
      const data = await apiRequest<CacheStats>("/api/admin/cache/stats");
      setCacheStats(data);
    } catch (err: any) {
      console.error("Failed to load cache stats", err);
    } finally {
      setLoadingCache(false);
    }
  };

  const handleClearCache = async () => {
    if (!window.confirm("Очистить все записи из L1 памяти и L2 SQLite базы кэша ответов?")) {
      return;
    }
    try {
      setClearingCache(true);
      const res = await apiRequest<{ message: string; l1_cleared: boolean; l2_cleared_entries: number }>(
        "/api/admin/cache/clear",
        { method: "POST" }
      );
      setSuccessMsg(res.message || "Кэш ответов успешно очищен");
      setTimeout(() => setSuccessMsg(null), 3000);
      await fetchCacheStats();
    } catch (err: any) {
      setError(err?.message || "Ошибка очистки кэша");
    } finally {
      setClearingCache(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const handleSaveGlobal = async (updated: Partial<CompressionGlobalSettings>) => {
    try {
      setSavingGlobal(true);
      setError(null);
      const res = await apiRequest<{ message: string; settings: CompressionGlobalSettings }>(
        "/api/admin/compression/settings",
        {
          method: "PUT",
          body: JSON.stringify(updated),
        }
      );
      setGlobalSettings(res.settings);
      setSuccessMsg("Глобальные настройки сохранены");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.message || "Ошибка сохранения настроек");
    } finally {
      setSavingGlobal(false);
    }
  };

  const handleToggleStage = async (stage: CompressionStageItem) => {
    try {
      const nextEnabled = !stage.enabled;
      await apiRequest(`/api/admin/compression/stages/${stage.id}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: nextEnabled }),
      });
      setStages((prev) =>
        prev.map((s) => (s.id === stage.id ? { ...s, enabled: nextEnabled } : s))
      );
    } catch (err: any) {
      setError(err?.message || "Ошибка переключения этапа");
    }
  };

  const handleMoveStage = async (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= stages.length) return;

    const newStages = [...stages];
    const [moved] = newStages.splice(index, 1);
    newStages.splice(targetIndex, 0, moved);

    // Update locally first for snappy UI
    setStages(newStages);

    try {
      const orderedIds = newStages.map((s) => s.id);
      await apiRequest("/api/admin/compression/stages/reorder", {
        method: "PUT",
        body: JSON.stringify({ ordered_ids: orderedIds }),
      });
    } catch (err: any) {
      setError(err?.message || "Ошибка сохранения порядка");
      fetchAll();
    }
  };

  const handleOpenConfig = (stage: CompressionStageItem) => {
    setConfigModalStage(stage);
    setEditingConfig({ ...stage.config_json });
  };

  const handleSaveStageConfig = async () => {
    if (!configModalStage) return;
    try {
      await apiRequest(`/api/admin/compression/stages/${configModalStage.id}`, {
        method: "PUT",
        body: JSON.stringify({ config_json: editingConfig }),
      });
      setStages((prev) =>
        prev.map((s) =>
          s.id === configModalStage.id ? { ...s, config_json: editingConfig } : s
        )
      );
      setConfigModalStage(null);
      setSuccessMsg(`Настройки этапа ${configModalStage.name} сохранены`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.message || "Ошибка сохранения конфигурации этапа");
    }
  };

  const handleDeleteStage = async (stageId: string) => {
    if (!window.confirm("Вы уверены, что хотите удалить этот пользовательский этап?")) return;
    try {
      await apiRequest(`/api/admin/compression/stages/${stageId}`, {
        method: "DELETE",
      });
      setStages((prev) => prev.filter((s) => s.id !== stageId));
      setSuccessMsg("Этап удален");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err?.message || "Ошибка удаления этапа");
    }
  };

  const handleCreateCustomStage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStageName.trim()) {
      setError("Укажите название этапа");
      return;
    }
    const slug = (newStageId.trim() || `custom_${Date.now()}`)
      .toLowerCase()
      .replace(/[^a-z0-9_]/g, "_");

    try {
      await apiRequest("/api/admin/compression/stages", {
        method: "POST",
        body: JSON.stringify({
          id: slug,
          name: newStageName.trim(),
          description: newStageDesc.trim(),
          priority_order: stages.length + 1,
          guard_code_blocks: newStageGuardCode,
          rules: newStageRules,
        }),
      });
      setShowAddCustomModal(false);
      setNewStageName("");
      setNewStageId("");
      setNewStageDesc("");
      setNewStageRules([{ pattern: "\\b(foo)\\b", replacement: "bar", case_sensitive: false }]);
      setSuccessMsg("Пользовательский этап создан");
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchAll();
    } catch (err: any) {
      setError(err?.message || "Ошибка создания этапа");
    }
  };

  const handleRunPlayground = async () => {
    try {
      setPreviewLoading(true);
      setError(null);
      let parsedMsgs;
      try {
        parsedMsgs = JSON.parse(playgroundMessages);
        if (!Array.isArray(parsedMsgs)) throw new Error("Промпт должен быть массивом сообщений");
      } catch (jsonErr: any) {
        throw new Error(`Ошибка в JSON сообщений: ${jsonErr.message}`);
      }

      const res = await apiRequest<CompressionPreviewResponse>(
        "/api/admin/compression/preview",
        {
          method: "POST",
          body: JSON.stringify({ messages: parsedMsgs }),
        }
      );
      setPreviewResult(res);
    } catch (err: any) {
      setError(err?.message || "Ошибка тестирования сжатия");
    } finally {
      setPreviewLoading(false);
    }
  };

  const getStageIcon = (iconName: string) => {
    switch (iconName) {
      case "CopyMinus":
        return <CopyMinus size={18} className="text-cyan-400" />;
      case "Archive":
        return <Archive size={18} className="text-blue-400" />;
      case "Sparkles":
        return <Sparkles size={18} className="text-amber-400" />;
      case "Terminal":
        return <Terminal size={18} className="text-emerald-400" />;
      case "Wrench":
        return <Wrench size={18} className="text-orange-400" />;
      case "Table":
        return <Table size={18} className="text-purple-400" />;
      case "Filter":
        return <Filter size={18} className="text-sky-400" />;
      case "MessageSquareDashed":
        return <MessageSquareDashed size={18} className="text-yellow-400" />;
      case "History":
        return <History size={18} className="text-rose-400" />;
      case "BrainCircuit":
        return <BrainCircuit size={18} className="text-indigo-400" />;
      case "Flame":
        return <Flame size={18} className="text-red-400" />;
      case "Image":
        return <Image size={18} className="text-pink-400" />;
      default:
        return <Zap size={18} className="text-indigo-400" />;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/[0.06] pb-5">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-lg shadow-indigo-500/10">
              <Zap size={22} />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                Оптимизация контекста
                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 font-mono font-medium">
                  Token Compression
                </span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Многоэтапный конвейер сокращения расхода токенов и очистки промптов (12 модульных этапов)
              </p>
            </div>
          </div>
        </div>

        {/* Global Master Switch */}
        <div className="flex items-center gap-4 bg-slate-900/60 border border-white/[0.08] px-4 py-2.5 rounded-2xl backdrop-blur-md">
          <div className="flex flex-col text-right">
            <span className="text-xs font-semibold text-slate-200">
              {globalSettings.enabled ? "Оптимизация активна" : "Оптимизация отключена"}
            </span>
            <span className="text-[11px] text-slate-400">
              {globalSettings.enabled
                ? `Порог: от ${globalSettings.trigger_token_threshold} токенов`
                : "Все запросы идут без сжатия"}
            </span>
          </div>
          <button
            onClick={() => handleSaveGlobal({ enabled: !globalSettings.enabled })}
            disabled={savingGlobal}
            className={`w-12 h-6 rounded-full transition-colors relative focus:outline-none ${
              globalSettings.enabled ? "bg-emerald-500" : "bg-slate-700"
            }`}
          >
            <span
              className={`block w-4 h-4 rounded-full bg-white transition-transform ${
                globalSettings.enabled ? "translate-x-7" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="flex items-center justify-between p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-white">
            ✕
          </button>
        </div>
      )}
      {successMsg && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs">
          <CheckCircle2 size={16} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Global Configuration Parameters Bar */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 bg-slate-900/40 border border-white/[0.06] p-4 rounded-2xl backdrop-blur-md">
        <div>
          <label className="text-[11px] font-medium text-slate-400 block mb-1.5">
            Порог активации (токенов)
          </label>
          <input
            type="number"
            min={0}
            max={128000}
            step={100}
            value={globalSettings.trigger_token_threshold}
            onChange={(e) =>
              setGlobalSettings({
                ...globalSettings,
                trigger_token_threshold: parseInt(e.target.value) || 0,
              })
            }
            onBlur={() =>
              handleSaveGlobal({ trigger_token_threshold: globalSettings.trigger_token_threshold })
            }
            className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
          />
          <span className="text-[10px] text-slate-500 mt-1 block">
            Сжимать только если промпт длиннее N токенов (0 = всегда)
          </span>
        </div>

        <div>
          <label className="text-[11px] font-medium text-slate-400 block mb-1.5">
            Защита последних реплик
          </label>
          <input
            type="number"
            min={1}
            max={10}
            value={globalSettings.preserve_recent_turns}
            onChange={(e) =>
              setGlobalSettings({
                ...globalSettings,
                preserve_recent_turns: parseInt(e.target.value) || 1,
              })
            }
            onBlur={() =>
              handleSaveGlobal({ preserve_recent_turns: globalSettings.preserve_recent_turns })
            }
            className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
          />
          <span className="text-[10px] text-slate-500 mt-1 block">
            Сколько последних ходов диалога сохранять 1-в-1
          </span>
        </div>

        <div>
          <label className="text-[11px] font-medium text-slate-400 block mb-1.5 flex items-center gap-1">
            <Zap size={12} className="text-emerald-400" />
            <span>Защита системного промпта</span>
          </label>
          <select
            value={globalSettings.preserve_system_prompt_mode || "when_caching"}
            onChange={(e) => {
              const val = e.target.value as any;
              setGlobalSettings({
                ...globalSettings,
                preserve_system_prompt_mode: val,
              });
              handleSaveGlobal({ preserve_system_prompt_mode: val });
            }}
            className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
          >
            <option value="when_caching">Авто (при кэшировании у провайдера)</option>
            <option value="always">Всегда сохранять (байт-в-байт)</option>
            <option value="never">Сжимать наравне с остальными</option>
          </select>
          <span className="text-[10px] text-slate-500 mt-1 block">
            Защита для KV-кэша (Anthropic, DeepSeek, OpenAI, Gemini)
          </span>
        </div>

        <div>
          <label className="text-[11px] font-medium text-slate-400 block mb-1.5">
            Мин. экономия отката (Bailout %)
          </label>
          <input
            type="number"
            min={0}
            max={50}
            step={0.5}
            value={globalSettings.min_savings_bailout_percent}
            onChange={(e) =>
              setGlobalSettings({
                ...globalSettings,
                min_savings_bailout_percent: parseFloat(e.target.value) || 0,
              })
            }
            onBlur={() =>
              handleSaveGlobal({
                min_savings_bailout_percent: globalSettings.min_savings_bailout_percent,
              })
            }
            className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
          />
          <span className="text-[10px] text-slate-500 mt-1 block">
            Откатывать этап, если экономия меньше X%
          </span>
        </div>

        <div className="flex flex-col justify-between pt-1">
          <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
            <input
              type="checkbox"
              checked={globalSettings.enable_telemetry}
              onChange={(e) => handleSaveGlobal({ enable_telemetry: e.target.checked })}
              className="rounded bg-slate-900 border-white/[0.1] text-indigo-600 focus:ring-0"
            />
            <span>Заголовки метрик (X-Tokens-Saved)</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300 mt-2">
            <input
              type="checkbox"
              checked={globalSettings.fail_open}
              onChange={(e) => handleSaveGlobal({ fail_open: e.target.checked })}
              className="rounded bg-slate-900 border-white/[0.1] text-indigo-600 focus:ring-0"
            />
            <span>Безопасный пропуск сбоев (Fail-Open)</span>
          </label>
        </div>
      </div>

      {/* Response Cache & KV-Affinity Stats Bar */}
      <div className="bg-slate-900/40 border border-white/[0.06] p-4 rounded-2xl backdrop-blur-md space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400 shrink-0">
              <Zap size={16} />
            </div>
            <div>
              <h3 className="text-xs font-bold text-slate-100 flex items-center gap-2">
                Двухуровневый кэш ответов (L1 Memory + L2 SQLite)
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-emerald-950/70 border border-emerald-800/60 text-emerald-300">
                  temperature ≤ 0.05
                </span>
              </h3>
              <p className="text-[11px] text-slate-400">
                Детерминированный кэш для мгновенных синтетических SSE-ответов и синхронизация KV-кэша с провайдерами
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchCacheStats}
              disabled={loadingCache}
              className="px-2.5 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 text-xs border border-white/[0.06] transition-all flex items-center gap-1.5 cursor-pointer"
              title="Обновить метрики кэша"
            >
              <RotateCcw size={13} className={loadingCache ? "animate-spin" : ""} />
              <span>Обновить</span>
            </button>
            <button
              onClick={handleClearCache}
              disabled={clearingCache}
              className="px-2.5 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs border border-rose-500/30 transition-all flex items-center gap-1.5 cursor-pointer"
              title="Очистить память L1 и базу L2"
            >
              <Trash2 size={13} />
              <span>{clearingCache ? "Очистка..." : "Очистить кэш ответов"}</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-1">
          <div className="bg-slate-950/50 border border-white/[0.05] p-2.5 rounded-xl">
            <span className="text-[10px] text-slate-400 uppercase font-mono block">L1 RAM Кэш</span>
            <div className="text-sm font-bold text-slate-100 font-mono mt-0.5">
              {cacheStats ? `${cacheStats.l1_memory_entries} / ${cacheStats.l1_max_size}` : "—"}
            </div>
            <span className="text-[10px] text-slate-500">LRU в памяти</span>
          </div>
          <div className="bg-slate-950/50 border border-white/[0.05] p-2.5 rounded-xl">
            <span className="text-[10px] text-slate-400 uppercase font-mono block">L2 SQLite Кэш</span>
            <div className="text-sm font-bold text-slate-100 font-mono mt-0.5">
              {cacheStats ? `${cacheStats.l2_db_entries} записей` : "—"}
            </div>
            <span className="text-[10px] text-slate-500">Дисковый кэш</span>
          </div>
          <div className="bg-slate-950/50 border border-white/[0.05] p-2.5 rounded-xl">
            <span className="text-[10px] text-slate-400 uppercase font-mono block">Hit Rate</span>
            <div className="text-sm font-bold text-emerald-400 font-mono mt-0.5">
              {cacheStats ? `${cacheStats.hit_rate_pct}%` : "0%"}
            </div>
            <span className="text-[10px] text-slate-500">
              {cacheStats ? `${cacheStats.total_hits} hit / ${cacheStats.total_misses} miss` : "0 hit / 0 miss"}
            </span>
          </div>
          <div className="bg-slate-950/50 border border-white/[0.05] p-2.5 rounded-xl">
            <span className="text-[10px] text-slate-400 uppercase font-mono block">Всего попаданий</span>
            <div className="text-sm font-bold text-slate-100 font-mono mt-0.5">
              {cacheStats ? cacheStats.total_hits : 0}
            </div>
            <span className="text-[10px] text-slate-500">Мгновенный ответ</span>
          </div>
          <div className="bg-slate-950/50 border border-white/[0.05] p-2.5 rounded-xl">
            <span className="text-[10px] text-slate-400 uppercase font-mono block">Сэкономлено токенов</span>
            <div className="text-sm font-bold text-indigo-400 font-mono mt-0.5">
              {cacheStats ? Number(cacheStats.tokens_saved).toLocaleString() : 0}
            </div>
            <span className="text-[10px] text-slate-500">Без запроса к LLM</span>
          </div>
          <div className="bg-slate-950/50 border border-white/[0.05] p-2.5 rounded-xl">
            <span className="text-[10px] text-slate-400 uppercase font-mono block">Экономия средств</span>
            <div className="text-sm font-bold text-emerald-300 font-mono mt-0.5">
              {cacheStats ? `$${cacheStats.cost_saved_usd.toFixed(4)}` : "$0.0000"}
            </div>
            <span className="text-[10px] text-slate-500">Оценка в USD</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center justify-between border-b border-white/[0.08]">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("pipeline")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-all ${
              activeTab === "pipeline"
                ? "border-indigo-500 text-white bg-indigo-500/10 rounded-t-xl"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Layers size={15} />
            <span>Этапы конвейера ({stages.length})</span>
          </button>
          <button
            onClick={() => setActiveTab("playground")}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-all ${
              activeTab === "playground"
                ? "border-indigo-500 text-white bg-indigo-500/10 rounded-t-xl"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Play size={15} />
            <span>Песочница / Тестирование</span>
          </button>
        </div>

        {activeTab === "pipeline" && (
          <button
            onClick={() => setShowAddCustomModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/20 border border-indigo-400/20 transition-all mb-1"
          >
            <Plus size={14} />
            <span>Добавить свой этап</span>
          </button>
        )}
      </div>

      {/* Tab 1: Pipeline Stages List */}
      {activeTab === "pipeline" && (
        <div className="space-y-3">
          <div className="text-xs text-slate-400 bg-indigo-500/[0.04] border border-indigo-500/10 px-4 py-2.5 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-indigo-400" />
              <span>
                Блоки кода (```), формулы LaTeX ($$), ссылки и JSON автоматически защищены сентинелями во всех этапах.
              </span>
            </div>
            <span className="text-[11px] text-slate-500">
              Порядок выполнения: сверху вниз (используйте стрелки для смены очередности)
            </span>
          </div>

          <div className="grid grid-cols-1 gap-2.5">
            {stages.map((stage, idx) => (
              <div
                key={stage.id}
                className={`flex items-center justify-between p-3.5 rounded-2xl border transition-all ${
                  stage.enabled
                    ? "bg-slate-900/60 border-white/[0.08] hover:border-white/[0.15]"
                    : "bg-slate-950/40 border-white/[0.03] opacity-60"
                }`}
              >
                {/* Left: Reorder, Icon, Title */}
                <div className="flex items-center gap-3.5 min-w-0">
                  {/* Order Controls */}
                  <div className="flex flex-col items-center gap-0.5">
                    <button
                      onClick={() => handleMoveStage(idx, "up")}
                      disabled={idx === 0}
                      className="p-1 text-slate-400 hover:text-white disabled:opacity-20 transition-colors"
                      title="Поднять выше"
                    >
                      <ArrowUp size={12} />
                    </button>
                    <span className="text-[10px] font-mono font-bold text-slate-500 px-1.5 py-0.5 rounded bg-white/[0.03]">
                      #{idx + 1}
                    </span>
                    <button
                      onClick={() => handleMoveStage(idx, "down")}
                      disabled={idx === stages.length - 1}
                      className="p-1 text-slate-400 hover:text-white disabled:opacity-20 transition-colors"
                      title="Опустить ниже"
                    >
                      <ArrowDown size={12} />
                    </button>
                  </div>

                  {/* Icon */}
                  <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center shrink-0">
                    {getStageIcon(stage.icon)}
                  </div>

                  {/* Details */}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-xs font-bold text-white tracking-tight">{stage.name}</h3>
                      <span className="text-[10px] font-mono text-slate-500">({stage.id})</span>
                      {stage.is_builtin ? (
                        <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 border border-white/[0.04]">
                          Встроенный
                        </span>
                      ) : (
                        <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
                          Пользовательский
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5 truncate max-w-2xl">
                      {stage.description}
                    </p>
                  </div>
                </div>

                {/* Right: Actions and Toggle */}
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  {stage.config_schema && stage.config_schema.length > 0 && (
                    <button
                      onClick={() => handleOpenConfig(stage)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 hover:text-white border border-white/[0.06] text-xs transition-colors"
                    >
                      <Settings size={13} />
                      <span>Параметры</span>
                    </button>
                  )}

                  {!stage.is_builtin && (
                    <button
                      onClick={() => handleDeleteStage(stage.id)}
                      className="p-1.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 transition-colors"
                      title="Удалить пользовательский этап"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}

                  {/* On/Off Toggle */}
                  <button
                    onClick={() => handleToggleStage(stage)}
                    className={`w-10 h-5 rounded-full transition-colors relative focus:outline-none ${
                      stage.enabled ? "bg-indigo-600" : "bg-slate-800"
                    }`}
                  >
                    <span
                      className={`block w-3.5 h-3.5 rounded-full bg-white transition-transform ${
                        stage.enabled ? "translate-x-5" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 2: Playground & Preview */}
      {activeTab === "playground" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Input Panel */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-200">
                Входные сообщения диалога (JSON)
              </label>
              <button
                onClick={() => {
                  setPlaygroundMessages(
                    JSON.stringify(
                      [
                        { role: "system", content: "You are an assistant." },
                        { role: "user", content: "Check git status and output logs" },
                        {
                          role: "assistant",
                          content:
                            "Certainly! Here is the terminal log:\n```bash\n[2026-10-04 10:00:01] \x1b[32mSUCCESS\x1b[0m Starting build...\nLine 1\nLine 1\nLine 1\nLine 1\nLine 1\nError: unexpected EOF\nBuild finished with code 1\n```",
                        },
                      ],
                      null,
                      2
                    )
                  );
                }}
                className="text-[11px] text-indigo-400 hover:text-indigo-300"
              >
                Пример с терминальными логами
              </button>
            </div>
            <textarea
              rows={16}
              value={playgroundMessages}
              onChange={(e) => setPlaygroundMessages(e.target.value)}
              className="w-full bg-slate-950/80 border border-white/[0.08] rounded-2xl p-4 font-mono text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 resize-y"
            />
            <button
              onClick={handleRunPlayground}
              disabled={previewLoading}
              className="w-full py-2.5 bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-indigo-600/20 border border-indigo-400/20 transition-all flex items-center justify-center gap-2"
            >
              <Play size={14} />
              <span>{previewLoading ? "Сжатие..." : "Протестировать конвейер сжатия"}</span>
            </button>
          </div>

          {/* Results Panel */}
          <div className="space-y-4">
            {previewResult ? (
              <>
                {/* Stats Cards */}
                <div className="grid grid-cols-4 gap-2.5">
                  <div className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.06] text-center">
                    <span className="text-[10px] text-slate-400 block">Было</span>
                    <span className="text-sm font-bold text-slate-200 font-mono">
                      {previewResult.initial_tokens}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.06] text-center">
                    <span className="text-[10px] text-slate-400 block">Стало</span>
                    <span className="text-sm font-bold text-emerald-400 font-mono">
                      {previewResult.final_tokens}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.06] text-center">
                    <span className="text-[10px] text-slate-400 block">Сэкономлено</span>
                    <span className="text-sm font-bold text-indigo-400 font-mono">
                      -{previewResult.tokens_saved}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900/60 border border-white/[0.06] text-center">
                    <span className="text-[10px] text-slate-400 block">Экономия</span>
                    <span className="text-sm font-bold text-purple-400 font-mono">
                      {previewResult.savings_percent}%
                    </span>
                  </div>
                </div>

                {/* Step Breakdown Table */}
                <div className="rounded-2xl border border-white/[0.08] bg-slate-900/40 overflow-hidden">
                  <div className="px-4 py-2.5 bg-white/[0.02] border-b border-white/[0.06] text-xs font-semibold text-slate-200">
                    Пошаговая разбивка этапов
                  </div>
                  <div className="divide-y divide-white/[0.04]">
                    {previewResult.steps.map((st) => (
                      <div
                        key={st.stage_id}
                        className="px-4 py-2.5 flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-2.5">
                          {getStageIcon(st.icon)}
                          <span className="font-medium text-slate-300">{st.stage_name}</span>
                          {st.rules && st.rules.length > 0 && (
                            <span className="text-[10px] text-indigo-300 font-mono bg-indigo-500/10 px-1.5 py-0.5 rounded">
                              {st.rules.join(", ")}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 font-mono">
                          {st.compressed ? (
                            <span className="text-emerald-400 font-semibold">
                              -{st.tokens_before - st.tokens_after} ток. ({st.savings_percent}%)
                            </span>
                          ) : (
                            <span className="text-slate-500 text-[11px]">без изменений</span>
                          )}
                          <span className="text-[10px] text-slate-500">{st.duration_ms}мс</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Output Inspection */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-200 block">
                    Результат после сжатия
                  </label>
                  <pre className="p-3.5 rounded-2xl bg-slate-950/80 border border-white/[0.08] text-xs font-mono text-slate-300 overflow-x-auto max-h-72">
                    {JSON.stringify(previewResult.compressed_messages, null, 2)}
                  </pre>
                </div>
              </>
            ) : (
              <div className="h-full min-h-[350px] flex flex-col items-center justify-center border border-dashed border-white/[0.08] rounded-2xl p-6 text-center text-slate-500">
                <Play size={28} className="mb-2 text-slate-600" />
                <span className="text-xs font-medium text-slate-400">
                  Нажмите кнопку запуска для проверки работы конвейера сжатия
                </span>
                <span className="text-[11px] text-slate-600 mt-1">
                  Вы увидите, сколько токенов сэкономил каждый этап и итоговый текст.
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stage Settings Modal */}
      {configModalStage && (
        <Modal
          isOpen={true}
          onClose={() => setConfigModalStage(null)}
          title={`Настройка: ${configModalStage.name}`}
        >
          <div className="space-y-4">
            <p className="text-xs text-slate-400">{configModalStage.description}</p>
            <div className="space-y-3.5">
              {configModalStage.config_schema.map((field) => (
                <div key={field.key} className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-slate-300">{field.label}</label>
                    <span className="text-[10px] font-mono text-slate-500">{field.key}</span>
                  </div>

                  {field.type === "boolean" ? (
                    <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={
                          editingConfig[field.key] !== undefined
                            ? editingConfig[field.key]
                            : field.default_value
                        }
                        onChange={(e) =>
                          setEditingConfig({ ...editingConfig, [field.key]: e.target.checked })
                        }
                        className="rounded bg-slate-900 border-white/[0.1] text-indigo-600 focus:ring-0"
                      />
                      <span>Включено</span>
                    </label>
                  ) : field.type === "select" ? (
                    <select
                      value={editingConfig[field.key] || field.default_value}
                      onChange={(e) =>
                        setEditingConfig({ ...editingConfig, [field.key]: e.target.value })
                      }
                      className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
                    >
                      {field.options?.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : field.type === "number" ? (
                    <input
                      type="number"
                      min={field.min_value}
                      max={field.max_value}
                      value={
                        editingConfig[field.key] !== undefined
                          ? editingConfig[field.key]
                          : field.default_value
                      }
                      onChange={(e) =>
                        setEditingConfig({
                          ...editingConfig,
                          [field.key]: parseFloat(e.target.value) || 0,
                        })
                      }
                      className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
                    />
                  ) : field.type === "textarea" ? (
                    <textarea
                      rows={3}
                      value={
                        editingConfig[field.key] !== undefined
                          ? typeof editingConfig[field.key] === "object"
                            ? JSON.stringify(editingConfig[field.key])
                            : editingConfig[field.key]
                          : field.default_value
                      }
                      onChange={(e) =>
                        setEditingConfig({ ...editingConfig, [field.key]: e.target.value })
                      }
                      className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 font-mono"
                    />
                  ) : (
                    <input
                      type="text"
                      value={
                        editingConfig[field.key] !== undefined
                          ? editingConfig[field.key]
                          : field.default_value
                      }
                      onChange={(e) =>
                        setEditingConfig({ ...editingConfig, [field.key]: e.target.value })
                      }
                      className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
                    />
                  )}

                  {field.description && (
                    <span className="text-[10px] text-slate-500 block">{field.description}</span>
                  )}
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-white/[0.06]">
              <button
                onClick={() => setConfigModalStage(null)}
                className="px-3.5 py-1.5 text-xs text-slate-400 hover:text-white"
              >
                Отмена
              </button>
              <button
                onClick={handleSaveStageConfig}
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold"
              >
                Сохранить параметры
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Add Custom Stage Modal */}
      {showAddCustomModal && (
        <Modal
          isOpen={true}
          onClose={() => setShowAddCustomModal(false)}
          title="Добавить пользовательский этап сжатия"
        >
          <form onSubmit={handleCreateCustomStage} className="space-y-4">
            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1">
                Название этапа *
              </label>
              <input
                type="text"
                required
                placeholder="например: Очистка корпоративных дисклеймеров"
                value={newStageName}
                onChange={(e) => setNewStageName(e.target.value)}
                className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1">
                Идентификатор (Slug)
              </label>
              <input
                type="text"
                placeholder="corporate_disclaimers"
                value={newStageId}
                onChange={(e) => setNewStageId(e.target.value)}
                className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50 font-mono"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1">Описание</label>
              <textarea
                rows={2}
                placeholder="Что делает этот этап..."
                value={newStageDesc}
                onChange={(e) => setNewStageDesc(e.target.value)}
                className="w-full bg-slate-950/60 border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
              />
            </div>

            <div>
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300 mb-3">
                <input
                  type="checkbox"
                  checked={newStageGuardCode}
                  onChange={(e) => setNewStageGuardCode(e.target.checked)}
                  className="rounded bg-slate-900 border-white/[0.1] text-indigo-600 focus:ring-0"
                />
                <span>Защищать блоки кода от этих правил</span>
              </label>
            </div>

            {/* Rules editor */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-slate-300">
                  Правила замены (Regex / Текст)
                </label>
                <button
                  type="button"
                  onClick={() =>
                    setNewStageRules([
                      ...newStageRules,
                      { pattern: "", replacement: "", case_sensitive: false },
                    ])
                  }
                  className="text-[11px] text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                >
                  <Plus size={12} />
                  <span>Добавить правило</span>
                </button>
              </div>

              {newStageRules.map((rule, rIdx) => (
                <div
                  key={rIdx}
                  className="p-3 rounded-xl bg-slate-950/40 border border-white/[0.04] space-y-2"
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      placeholder="Regex паттерн (например: \\b(Confidential)\\b)"
                      value={rule.pattern}
                      onChange={(e) => {
                        const copy = [...newStageRules];
                        copy[rIdx].pattern = e.target.value;
                        setNewStageRules(copy);
                      }}
                      className="flex-1 bg-slate-900 border border-white/[0.08] rounded-lg px-2.5 py-1 text-xs text-slate-200 font-mono"
                    />
                    <input
                      type="text"
                      placeholder="Замена (пусто = удалить)"
                      value={rule.replacement}
                      onChange={(e) => {
                        const copy = [...newStageRules];
                        copy[rIdx].replacement = e.target.value;
                        setNewStageRules(copy);
                      }}
                      className="w-1/3 bg-slate-900 border border-white/[0.08] rounded-lg px-2.5 py-1 text-xs text-slate-200 font-mono"
                    />
                    {newStageRules.length > 1 && (
                      <button
                        type="button"
                        onClick={() => setNewStageRules(newStageRules.filter((_, i) => i !== rIdx))}
                        className="text-red-400 p-1 hover:text-red-300"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-white/[0.06]">
              <button
                type="button"
                onClick={() => setShowAddCustomModal(false)}
                className="px-3.5 py-1.5 text-xs text-slate-400 hover:text-white"
              >
                Отмена
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold"
              >
                Создать этап
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
