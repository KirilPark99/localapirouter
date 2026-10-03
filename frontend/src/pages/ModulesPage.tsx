import React, { useEffect, useState } from "react";
import {
  Puzzle,
  RefreshCw,
  Plus,
  Play,
  Trash2,
  Edit2,
  CheckCircle2,
  AlertCircle,
  Network,
  Eye,
  EyeOff,
  FolderCode,
  Layers,
  ChevronRight,
  Shield,
  HelpCircle,
  RotateCcw,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { Proxy } from "../types";
import { Modal } from "../components/Modal";
import { StatusBadge } from "../components/StatusBadge";
import { getCountryFlag } from "../utils/country";
import { useI18n } from "../i18n";

interface ModuleField {
  key: string;
  label: string;
  type: "text" | "password" | "textarea" | "number" | "select";
  required: boolean;
  default?: any;
  placeholder?: string;
  description?: string;
  options?: { label: string; value: string }[];
}

interface ModuleDefaultModel {
  id: string;
  name: string;
  context_length?: number;
  max_output_tokens?: number;
  reasoning_effort?: string;
}

interface ModuleManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  author?: string;
  icon?: string;
  auth_type: string;
  fields: ModuleField[];
  default_models: ModuleDefaultModel[];
  folder_path?: string;
}

interface LoadedModule {
  manifest: ModuleManifest;
  status: "ready" | "error";
  error?: string;
  profiles_count: number;
  models_count: number;
  provider_id?: number;
}

interface ModuleProfile {
  id: number;
  provider_id: number;
  module_id: string;
  name: string;
  enabled: boolean;
  status: string;
  priority: number;
  weight: number;
  proxy_id?: number | null;
  proxy?: {
    id: number;
    name: string;
    scheme: string;
    host: string;
    port: number;
    country?: string;
    country_code?: string;
  } | null;
  fields: Record<string, any>;
  source?: string;
  file_path?: string;
  last_checked_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  consecutive_failures: number;
}

export const ModulesPage: React.FC = () => {
  const { t } = useI18n();
  const [modules, setModules] = useState<LoadedModule[]>([]);
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [loading, setLoading] = useState(true);
  const [rescanning, setRescanning] = useState(false);

  // Active module selected for profile management
  const [selectedModule, setSelectedModule] = useState<LoadedModule | null>(null);
  const [profiles, setProfiles] = useState<ModuleProfile[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState(false);

  // Create / Edit Profile Modal
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ModuleProfile | null>(null);
  const [formName, setFormName] = useState("");
  const [formProxyId, setFormProxyId] = useState<number | undefined>(undefined);
  const [formPriority, setFormPriority] = useState(1);
  const [formWeight, setFormWeight] = useState(1);
  const [formFields, setFormFields] = useState<Record<string, any>>({});
  const [showPasswordFields, setShowPasswordFields] = useState<Record<string, boolean>>({});
  const [savingProfile, setSavingProfile] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Test Profile state
  const [testingProfileId, setTestingProfileId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{
    profileId: number;
    ok: boolean;
    message: string;
    latency?: number;
    modelsFound?: number;
  } | null>(null);

  const fetchModules = async () => {
    try {
      const data = await apiRequest<LoadedModule[]>("/api/admin/modules");
      setModules(data || []);
      if (selectedModule) {
        const updated = (data || []).find((m) => m.manifest.id === selectedModule.manifest.id);
        if (updated) setSelectedModule(updated);
      }
    } catch (err) {
      console.error("Failed to load modules:", err);
    }
  };

  const fetchProxies = async () => {
    try {
      const data = await apiRequest<Proxy[]>("/api/admin/proxies");
      setProxies(data || []);
    } catch (err) {
      console.error("Failed to load proxies:", err);
    }
  };

  const fetchProfiles = async (moduleId: string) => {
    setLoadingProfiles(true);
    try {
      const data = await apiRequest<ModuleProfile[]>(`/api/admin/modules/${moduleId}/profiles`);
      setProfiles(data || []);
    } catch (err) {
      console.error("Failed to load module profiles:", err);
    } finally {
      setLoadingProfiles(false);
    }
  };

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([fetchModules(), fetchProxies()]);
      setLoading(false);
    };
    init();
  }, []);

  const handleRescan = async () => {
    setRescanning(true);
    try {
      await apiRequest("/api/admin/modules/reload", { method: "POST" });
      await fetchModules();
      if (selectedModule) {
        await fetchProfiles(selectedModule.manifest.id);
      }
    } catch (err: any) {
      alert(`Error rescanning modules: ${err.message}`);
    } finally {
      setRescanning(false);
    }
  };

  const openProfileDrawer = (mod: LoadedModule) => {
    setSelectedModule(mod);
    fetchProfiles(mod.manifest.id);
  };

  const openCreateModal = (mod: LoadedModule) => {
    setSelectedModule(mod);
    setEditingProfile(null);
    setFormName(`${mod.manifest.name} Profile`);
    setFormProxyId(undefined);
    setFormPriority(1);
    setFormWeight(1);
    const initialFields: Record<string, any> = {};
    for (const f of mod.manifest.fields) {
      initialFields[f.key] = f.default !== undefined ? f.default : "";
    }
    setFormFields(initialFields);
    setFormError(null);
    setIsProfileModalOpen(true);
  };

  const openEditModal = (profile: ModuleProfile) => {
    if (!selectedModule) return;
    setEditingProfile(profile);
    setFormName(profile.name);
    setFormProxyId(profile.proxy_id || undefined);
    setFormPriority(profile.priority);
    setFormWeight(profile.weight);
    setFormFields({ ...(profile.fields || {}) });
    setFormError(null);
    setIsProfileModalOpen(true);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedModule) return;
    setSavingProfile(true);
    setFormError(null);

    try {
      if (editingProfile) {
        // Update
        await apiRequest(`/api/admin/modules/${selectedModule.manifest.id}/profiles/${editingProfile.id}`, {
          method: "PUT",
          body: JSON.stringify({
            name: formName,
            proxy_id: formProxyId || null,
            priority: formPriority,
            weight: formWeight,
            fields: formFields,
          }),
        });
      } else {
        // Create
        await apiRequest(`/api/admin/modules/${selectedModule.manifest.id}/profiles`, {
          method: "POST",
          body: JSON.stringify({
            name: formName,
            proxy_id: formProxyId || null,
            priority: formPriority,
            weight: formWeight,
            fields: formFields,
          }),
        });
      }

      setIsProfileModalOpen(false);
      await fetchProfiles(selectedModule.manifest.id);
      await fetchModules();
    } catch (err: any) {
      setFormError(err.message || "Failed to save profile");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleDeleteProfile = async (profileId: number) => {
    if (!selectedModule) return;
    if (!window.confirm("Are you sure you want to delete this module profile?")) return;
    try {
      await apiRequest(`/api/admin/modules/${selectedModule.manifest.id}/profiles/${profileId}`, {
        method: "DELETE",
      });
      await fetchProfiles(selectedModule.manifest.id);
      await fetchModules();
    } catch (err: any) {
      alert(`Failed to delete profile: ${err.message}`);
    }
  };

  const handleTestProfile = async (profileId: number) => {
    if (!selectedModule) return;
    setTestingProfileId(profileId);
    setTestResult(null);

    try {
      const res = await apiRequest<{
        success: boolean;
        message: string;
        latency_ms?: number;
        models_count?: number;
      }>(`/api/admin/modules/${selectedModule.manifest.id}/profiles/${profileId}/test`, {
        method: "POST",
      });

      setTestResult({
        profileId,
        ok: res.success,
        message: res.message || (res.success ? "Connection successful" : "Validation failed"),
        latency: res.latency_ms,
        modelsFound: res.models_count,
      });

      await fetchProfiles(selectedModule.manifest.id);
    } catch (err: any) {
      setTestResult({
        profileId,
        ok: false,
        message: err.message || "Test request error",
      });
    } finally {
      setTestingProfileId(null);
    }
  };

  const handleSyncModels = async (profileId: number) => {
    if (!selectedModule) return;
    try {
      const res = await apiRequest<{
        success: boolean;
        models_discovered?: number;
      }>(`/api/admin/modules/${selectedModule.manifest.id}/profiles/${profileId}/sync-models`, {
        method: "POST",
      });
      alert(`Synchronized models: discovered ${res.models_discovered || 0} models.`);
      await fetchModules();
    } catch (err: any) {
      alert(`Failed to sync models: ${err.message}`);
    }
  };

  const handleExportProfile = async (profileId: number) => {
    if (!selectedModule) return;
    try {
      const res = await apiRequest<{ success: boolean; relative_path: string }>(
        `/api/admin/modules/${selectedModule.manifest.id}/profiles/${profileId}/export`,
        { method: "POST" }
      );
      if (res && res.success) {
        alert(`Профиль успешно экспортирован в файл:\nprofiles/${res.relative_path}\n\nЭтот файл защищён в .gitignore и никогда не попадёт в Git.`);
        await fetchProfiles(selectedModule.manifest.id);
      }
    } catch (err: any) {
      alert(`Ошибка экспорта: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-white/[0.06]">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-sm">
              <Puzzle size={19} />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-100 tracking-tight flex items-center gap-2">
                <span>Провайдерские модули</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono font-medium">
                  Custom Modules
                </span>
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Пользовательские адаптеры и расширения (OAuth, веб-сессии, обратные прокси). Модули размещаются в папке <code className="text-indigo-300 font-mono text-[11px] bg-slate-900 px-1.5 py-0.5 rounded border border-white/[0.06]">backend/modules/</code>.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleRescan}
            disabled={rescanning}
            className="btn-press flex items-center gap-1.5 px-3.5 py-2 bg-slate-900/80 hover:bg-slate-800 text-slate-200 border border-white/[0.08] rounded-xl text-xs font-medium transition-all shadow-xs disabled:opacity-50"
          >
            <RefreshCw size={13} className={rescanning ? "animate-spin text-indigo-400" : "text-slate-400"} />
            <span>{rescanning ? "Сканирование..." : "Сканировать модули"}</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="p-12 text-center text-slate-500 text-xs">Загрузка установленных модулей...</div>
      ) : modules.length === 0 ? (
        /* Empty State */
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-2xl p-8 text-center max-w-2xl mx-auto shadow-xl">
          <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mx-auto mb-4">
            <FolderCode size={28} />
          </div>
          <h3 className="text-base font-semibold text-slate-200">Пользовательские модули не обнаружены</h3>
          <p className="text-xs text-slate-400 mt-1.5 leading-relaxed max-w-lg mx-auto">
            Вы можете добавлять собственные провайдеры (например, Codex OAuth, сессии веб-чатов или сторонние мосты), создав папку в директории <span className="font-mono text-indigo-300">backend/modules/</span>.
          </p>

          <div className="mt-6 text-left bg-slate-950/80 border border-white/[0.06] rounded-xl p-4 text-xs font-mono text-slate-300 space-y-2">
            <div className="text-slate-500 font-sans text-[11px] font-semibold uppercase tracking-wider">
              Быстрый старт из шаблона:
            </div>
            <div className="text-indigo-400 bg-slate-900/80 p-2.5 rounded-lg border border-indigo-500/10 select-all overflow-x-auto">
              cp -r backend/modules/_template backend/modules/my_module
            </div>
            <p className="font-sans text-[11px] text-slate-400 pt-1">
              Отредактируйте <span className="text-slate-200">manifest.json</span> и <span className="text-slate-200">handler.py</span> в созданной папке, затем нажмите <strong>«Сканировать модули»</strong>.
            </p>
          </div>

          <div className="mt-6">
            <button
              onClick={handleRescan}
              disabled={rescanning}
              className="btn-press inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all"
            >
              <RefreshCw size={13} className={rescanning ? "animate-spin" : ""} />
              <span>Проверить папку модулей</span>
            </button>
          </div>
        </div>
      ) : (
        /* Modules Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {modules.map((mod) => (
            <div
              key={mod.manifest.id}
              className="bg-slate-900/50 backdrop-blur-md border border-white/[0.08] hover:border-indigo-500/30 rounded-2xl p-5 flex flex-col justify-between transition-all group shadow-sm hover:shadow-indigo-500/5"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shadow-xs">
                      <Puzzle size={20} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-100 text-sm group-hover:text-indigo-300 transition-colors">
                        {mod.manifest.name}
                      </h3>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-950 px-1.5 py-0.5 rounded border border-white/[0.06]">
                          v{mod.manifest.version}
                        </span>
                        {mod.manifest.author && (
                          <span className="text-[10px] text-slate-500 font-sans">
                            от {mod.manifest.author}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {mod.status === "ready" ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Активен
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20" title={mod.error}>
                      <AlertCircle size={10} />
                      Ошибка
                    </span>
                  )}
                </div>

                <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed mb-4">
                  {mod.manifest.description || "Модуль интеграции с внешним источником."}
                </p>

                {mod.error && (
                  <div className="mb-4 p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-[11px] text-rose-300 font-mono break-all">
                    {mod.error}
                  </div>
                )}

                {/* Metrics Badges */}
                <div className="flex items-center gap-2 mb-4 text-xs">
                  <div className="flex-1 bg-slate-950/60 rounded-xl p-2 border border-white/[0.04] text-center">
                    <div className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider">Профилей</div>
                    <div className="text-sm font-bold text-slate-200 mt-0.5 font-mono">{mod.profiles_count}</div>
                  </div>
                  <div className="flex-1 bg-slate-950/60 rounded-xl p-2 border border-white/[0.04] text-center">
                    <div className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider">Моделей</div>
                    <div className="text-sm font-bold text-slate-200 mt-0.5 font-mono">{mod.models_count}</div>
                  </div>
                </div>
              </div>

              {/* Actions Footer */}
              <div className="flex items-center gap-2 pt-3 border-t border-white/[0.06]">
                <button
                  onClick={() => openProfileDrawer(mod)}
                  className="flex-1 btn-press flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800/80 hover:bg-slate-800 text-slate-200 rounded-xl text-xs font-medium border border-white/[0.06] transition-all"
                >
                  <Layers size={13} className="text-indigo-400" />
                  <span>Профили ({mod.profiles_count})</span>
                </button>
                <button
                  onClick={() => openCreateModal(mod)}
                  disabled={mod.status !== "ready"}
                  className="btn-press flex items-center justify-center gap-1 px-3 py-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-xl text-xs font-medium transition-all disabled:opacity-40"
                  title="Добавить профиль для этого модуля"
                >
                  <Plus size={14} />
                  <span>Профиль</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Profiles Drawer Modal */}
      {selectedModule && (
        <Modal
          isOpen={!isProfileModalOpen && !!selectedModule}
          onClose={() => setSelectedModule(null)}
          title={`Профили модуля: ${selectedModule.manifest.name}`}
          maxWidth="xl"
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
              <div>
                <p className="text-xs text-slate-400">
                  Учетные записи и сессии для модуля <code className="text-indigo-300 font-mono">{selectedModule.manifest.id}</code>. Каждому профилю можно назначить собственный прокси.
                </p>
              </div>
              <button
                onClick={() => openCreateModal(selectedModule)}
                className="btn-press flex items-center gap-1 px-3 py-1.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-xs font-semibold shadow-xs transition-all"
              >
                <Plus size={13} />
                <span>Новый профиль</span>
              </button>
            </div>

            {/* Git Isolation Notice */}
            <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-300 flex items-start gap-2.5">
              <Shield size={16} className="shrink-0 mt-0.5 text-indigo-400" />
              <div className="leading-relaxed">
                <strong>Изоляция от Git:</strong> Механизмы модулей (<code className="text-slate-200">backend/modules/</code>) отделены от личных профилей. Профили сохраняются в локальной зашифрованной БД или в файлах в папке <code className="bg-slate-900 px-1 py-0.5 rounded text-slate-200">profiles/</code>, которая полностью исключена из Git (<code className="text-slate-400 font-mono">.gitignore</code>) и никогда не попадёт на GitHub.
              </div>
            </div>

            {loadingProfiles ? (
              <div className="p-8 text-center text-slate-500 text-xs">Загрузка профилей...</div>
            ) : profiles.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-white/[0.08] rounded-xl text-xs text-slate-400">
                У этого модуля пока нет созданных профилей. Нажмите кнопку выше, чтобы добавить профиль, либо поместите файл в папку <code className="text-indigo-300 font-mono">profiles/{selectedModule.manifest.id}/</code>.
              </div>
            ) : (
              <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
                {profiles.map((p) => {
                  const isTesting = testingProfileId === p.id;
                  const res = testResult && testResult.profileId === p.id ? testResult : null;

                  return (
                    <div
                      key={p.id}
                      className="bg-slate-950/70 border border-white/[0.08] hover:border-white/[0.12] rounded-xl p-4 transition-all"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-100 text-sm">{p.name}</span>
                            <StatusBadge status={p.status} />
                            {p.source === "file" ? (
                              <span
                                className="text-[10px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20 flex items-center gap-1 font-mono"
                                title={`Файл: profiles/${p.file_path || ''}`}
                              >
                                <FolderCode size={10} />
                                <span>Файл: {p.file_path}</span>
                              </span>
                            ) : (
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800/80 text-slate-400 border border-white/[0.06]">
                                UI
                              </span>
                            )}
                            {!p.enabled && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                                Отключен
                              </span>
                            )}
                          </div>

                          {/* Proxy info */}
                          <div className="flex items-center gap-2 text-xs text-slate-400 mt-1">
                            <Network size={12} className={p.proxy ? "text-indigo-400" : "text-slate-600"} />
                            {p.proxy ? (
                              <span className="inline-flex items-center gap-1 font-mono text-[11px] text-slate-300">
                                <span>{getCountryFlag(p.proxy.country_code || "")}</span>
                                <span className="uppercase text-indigo-300 font-bold">{p.proxy.scheme}</span>
                                <span>{p.proxy.host}:{p.proxy.port}</span>
                                {p.proxy.country && (
                                  <span className="text-slate-500 font-sans">({p.proxy.country})</span>
                                )}
                              </span>
                            ) : (
                              <span className="text-slate-500 font-sans text-[11px]">Direct (без прокси)</span>
                            )}
                          </div>

                          {/* Priority and Failures */}
                          <div className="flex items-center gap-3 text-[11px] text-slate-500 pt-1">
                            <span>Приоритет: <strong className="text-slate-300">{p.priority}</strong></span>
                            <span>Вес: <strong className="text-slate-300">{p.weight}</strong></span>
                            {p.consecutive_failures > 0 && (
                              <span className="text-rose-400">Сбоев подряд: {p.consecutive_failures}</span>
                            )}
                            {p.last_success_at && (
                              <span>Успех: {new Date(p.last_success_at).toLocaleTimeString()}</span>
                            )}
                          </div>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => handleTestProfile(p.id)}
                            disabled={isTesting}
                            className="btn-press flex items-center gap-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-white/[0.06] transition-all disabled:opacity-50"
                            title="Протестировать соединение через назначенный прокси"
                          >
                            <Play size={11} className={isTesting ? "animate-spin text-indigo-400" : "text-emerald-400"} />
                            <span>{isTesting ? "Тест..." : "Тест"}</span>
                          </button>
                          <button
                            onClick={() => handleExportProfile(p.id)}
                            className="btn-press p-1.5 bg-slate-800 hover:bg-slate-700 text-sky-400 rounded-lg text-xs border border-white/[0.06] transition-all"
                            title="Экспортировать профиль в папку profiles/ (в файл вне Git)"
                          >
                            <FolderCode size={13} />
                          </button>
                          <button
                            onClick={() => handleSyncModels(p.id)}
                            className="btn-press p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs border border-white/[0.06] transition-all"
                            title="Синхронизировать список моделей из профиля"
                          >
                            <RotateCcw size={13} />
                          </button>
                          <button
                            onClick={() => openEditModal(p)}
                            className="btn-press p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs border border-white/[0.06] transition-all"
                            title="Редактировать профиль"
                          >
                            <Edit2 size={13} />
                          </button>
                          <button
                            onClick={() => handleDeleteProfile(p.id)}
                            className="btn-press p-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-lg text-xs border border-rose-500/20 transition-all"
                            title="Удалить профиль"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>

                      {/* Test feedback banner */}
                      {res && (
                        <div
                          className={`mt-3 p-2.5 rounded-lg text-xs flex items-center justify-between border ${
                            res.ok
                              ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                              : "bg-rose-500/10 border-rose-500/20 text-rose-300"
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            {res.ok ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                            <span>{res.message}</span>
                          </div>
                          {res.latency !== undefined && (
                            <span className="font-mono text-[11px] font-semibold">{res.latency} ms</span>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* Create / Edit Profile Modal */}
      {selectedModule && (
        <Modal
          isOpen={isProfileModalOpen}
          onClose={() => setIsProfileModalOpen(false)}
          title={editingProfile ? `Редактирование профиля: ${editingProfile.name}` : `Новый профиль для ${selectedModule.manifest.name}`}
          maxWidth="lg"
        >
          <form onSubmit={handleSaveProfile} className="space-y-4">
            {formError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-300 flex items-center gap-2">
                <AlertCircle size={14} className="shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            {/* Profile Name */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Название профиля <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                required
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="например, Codex Work Account или DeepSeek US Session"
                className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-xs text-slate-200 placeholder-slate-600 focus:outline-hidden"
              />
            </div>

            {/* Proxy Selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Network size={13} className="text-indigo-400" />
                  <span>Привязанный прокси</span>
                </span>
                <span className="text-[11px] text-slate-500 font-normal">
                  Все вызовы модуля пойдут через этот прокси
                </span>
              </label>
              <select
                value={formProxyId || ""}
                onChange={(e) => setFormProxyId(e.target.value ? Number(e.target.value) : undefined)}
                className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-xs text-slate-200 focus:outline-hidden"
              >
                <option value="">Direct / Без прокси (прямое соединение с сервера)</option>
                {proxies.map((px) => (
                  <option key={px.id} value={px.id}>
                    {getCountryFlag(px.country_code || "")} [{px.scheme.toUpperCase()}] {px.name} — {px.host}:{px.port} {px.country ? `(${px.country})` : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Priority & Weight */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Приоритет (1 = высший)</label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={formPriority}
                  onChange={(e) => setFormPriority(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-xs text-slate-200 focus:outline-hidden"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Вес (Round-Robin)</label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={formWeight}
                  onChange={(e) => setFormWeight(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-xs text-slate-200 focus:outline-hidden"
                />
              </div>
            </div>

            {/* Dynamic Module Fields defined in manifest.json */}
            {selectedModule.manifest.fields && selectedModule.manifest.fields.length > 0 && (
              <div className="pt-2 border-t border-white/[0.06] space-y-3">
                <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Shield size={13} className="text-indigo-400" />
                  <span>Параметры авторизации модуля</span>
                </div>

                {selectedModule.manifest.fields.map((field) => {
                  const isPassword = field.type === "password";
                  const showPass = !!showPasswordFields[field.key];
                  const value = formFields[field.key] ?? "";

                  return (
                    <div key={field.key} className="space-y-1">
                      <label className="block text-xs text-slate-300 flex items-center justify-between">
                        <span>
                          {field.label} {field.required && <span className="text-rose-400">*</span>}
                        </span>
                        {field.description && (
                          <span className="text-[11px] text-slate-500">{field.description}</span>
                        )}
                      </label>

                      {field.type === "textarea" ? (
                        <textarea
                          rows={3}
                          required={field.required}
                          value={value}
                          onChange={(e) => setFormFields({ ...formFields, [field.key]: e.target.value })}
                          placeholder={field.placeholder || ""}
                          className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-xs text-slate-200 font-mono placeholder-slate-600 focus:outline-hidden"
                        />
                      ) : field.type === "select" && field.options ? (
                        <select
                          required={field.required}
                          value={value}
                          onChange={(e) => setFormFields({ ...formFields, [field.key]: e.target.value })}
                          className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-xs text-slate-200 focus:outline-hidden"
                        >
                          <option value="">Выберите значение...</option>
                          {field.options.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <div className="relative">
                          <input
                            type={isPassword ? (showPass ? "text" : "password") : field.type === "number" ? "number" : "text"}
                            required={field.required}
                            value={value}
                            onChange={(e) => setFormFields({ ...formFields, [field.key]: e.target.value })}
                            placeholder={field.placeholder || ""}
                            className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-xs text-slate-200 font-mono placeholder-slate-600 focus:outline-hidden pr-8"
                          />
                          {isPassword && (
                            <button
                              type="button"
                              onClick={() =>
                                setShowPasswordFields({
                                  ...showPasswordFields,
                                  [field.key]: !showPass,
                                })
                              }
                              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                            >
                              {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-2 pt-4 border-t border-white/[0.06]">
              <button
                type="button"
                onClick={() => setIsProfileModalOpen(false)}
                className="btn-press px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium border border-white/[0.06]"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={savingProfile}
                className="btn-press px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/20 disabled:opacity-50"
              >
                {savingProfile ? "Сохранение..." : editingProfile ? "Обновить профиль" : "Создать профиль"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
