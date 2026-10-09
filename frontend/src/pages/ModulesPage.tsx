import React, { useEffect, useRef, useState } from "react";
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
  StickyNote,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { Proxy, PeriodQuotaRule, PeriodQuotaUsage, DiscoveredModel } from "../types";
import { QuotaEditor } from "../components/QuotaEditor";
import { credentialQuotaTranslations } from "../i18n/quotaTranslations";
import { Modal } from "../components/Modal";
import { NotesModal } from "../components/NotesModal";
import { StatusBadge } from "../components/StatusBadge";
import { SubscriptionLimitsBadge } from "../components/SubscriptionLimitsBadge";
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
  notes?: string | null;
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
  group_name?: string | null;
  rpm_limit?: number | null;
  tpm_limit?: number | null;
  max_concurrency?: number | null;
  quota_rules?: PeriodQuotaRule[];
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
  notes?: string | null;
}

interface OAuthStatus {
  status: "pending" | "authorized" | "error";
  message?: string;
  expires_in: number;
}

interface OAuthSession extends OAuthStatus {
  session_id: string;
  auth_url: string;
  loopback: boolean;
  moduleId: string;
  proxyId: number | null;
  expiresAt: number;
}

export const ModulesPage: React.FC = () => {
  const { language } = useI18n();
  const q = credentialQuotaTranslations[language === "ru" ? "ru" : "en"];
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
  const [formGroupName, setFormGroupName] = useState("");
  const [formRpm, setFormRpm] = useState("");
  const [formTpm, setFormTpm] = useState("");
  const [formMaxConcurrency, setFormMaxConcurrency] = useState("");
  const [formQuotas, setFormQuotas] = useState<PeriodQuotaRule[]>([]);
  const [quotaUsage, setQuotaUsage] = useState<PeriodQuotaUsage[]>([]);
  const [usageError, setUsageError] = useState("");
  const [quotaModels, setQuotaModels] = useState<DiscoveredModel[]>([]);
  const [catalogError, setCatalogError] = useState(false);
  const [formFields, setFormFields] = useState<Record<string, any>>({});
  const [formProfileNotes, setFormProfileNotes] = useState("");
  const [showPasswordFields, setShowPasswordFields] = useState<Record<string, boolean>>({});
  const [savingProfile, setSavingProfile] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [oauthSession, setOAuthSession] = useState<OAuthSession | null>(null);
  const oauthRef = useRef<OAuthSession | null>(null);
  const oauthGeneration = useRef(0);
  const oauthRequestBusy = useRef(false);
  const [oauthStarting, setOAuthStarting] = useState(false);
  const [oauthCallbackBusy, setOAuthCallbackBusy] = useState(false);
  const [callbackUrl, setCallbackUrl] = useState("");
  const supportsBrowserOAuth = ["agy_cli", "codex_cli", "grok_builder_cli"].includes(selectedModule?.manifest.id || "");

  const quotaCatalog = {
    models: [...new Set(quotaModels.filter(model => model.provider_id === selectedModule?.provider_id).map(model => model.canonical_slug))].sort(),
    profiles: [],
  };

  useEffect(() => {
    if (!isProfileModalOpen) return;
    let cancelled = false;
    apiRequest<DiscoveredModel[]>("/api/admin/models").then(models => {
      if (!cancelled) setQuotaModels(models);
    }).catch(() => { if (!cancelled) setCatalogError(true); });
    return () => { cancelled = true; };
  }, [isProfileModalOpen, selectedModule?.provider_id]);

  const loadQuotaUsage = async (id: number) => {
    setUsageError("");
    try {
      setQuotaUsage(await apiRequest<PeriodQuotaUsage[]>(`/api/admin/credentials/${id}/usage`));
    } catch (err: any) {
      setUsageError(err.message);
    }
  };

  const updateOAuthSession = (session: OAuthSession | null) => {
    oauthRef.current = session;
    setOAuthSession(session);
  };

  const cancelOAuth = (reportError = false) => {
    oauthGeneration.current += 1;
    const session = oauthRef.current;
    updateOAuthSession(null);
    setOAuthStarting(false);
    setOAuthCallbackBusy(false);
    setCallbackUrl("");
    if (session) {
      void apiRequest(`/api/admin/modules/${session.moduleId}/oauth/${session.session_id}`, {
        method: "DELETE",
        keepalive: true,
      }).catch((err: Error) => {
        if (reportError) setFormError(`Не удалось отменить OAuth-сессию: ${err.message}`);
        else console.warn("Не удалось отменить OAuth-сессию:", err.message);
      });
    }
  };

  // Status updates must not cancel the session: only modal/module lifetime does.
  useEffect(() => {
    return () => cancelOAuth();
  }, [isProfileModalOpen, selectedModule?.manifest.id]);

  useEffect(() => {
    const sessionId = oauthSession?.session_id;
    if (!sessionId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const session = oauthRef.current;
      if (stopped || session?.session_id !== sessionId || session.status === "error") return;
      if (Date.now() >= session.expiresAt) {
        updateOAuthSession({ ...session, status: "error", message: "Срок OAuth-сессии истёк. Авторизуйтесь повторно." });
        return;
      }
      if (session.status === "pending" && !oauthRequestBusy.current) {
        oauthRequestBusy.current = true;
        try {
          const status = await apiRequest<OAuthStatus>(`/api/admin/modules/${session.moduleId}/oauth/${sessionId}`);
          if (!stopped && oauthRef.current?.session_id === sessionId) {
            updateOAuthSession({ ...session, ...status });
          }
        } catch (err: any) {
          if (!stopped && oauthRef.current?.session_id === sessionId) {
            updateOAuthSession({ ...session, status: "error", message: err.message || "Ошибка проверки авторизации" });
          }
        } finally {
          oauthRequestBusy.current = false;
        }
      }
      if (!stopped) timer = setTimeout(poll, 1500);
    };
    timer = setTimeout(poll, 1500);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [oauthSession?.session_id]);

  const handleStartOAuth = async () => {
    if (!selectedModule || !supportsBrowserOAuth || oauthStarting || savingProfile) return;
    cancelOAuth();
    const generation = oauthGeneration.current;
    const moduleId = selectedModule.manifest.id;
    const proxyId = formProxyId ?? null;
    // Open synchronously from the click; the visible link also works if blocked.
    const popup = window.open("about:blank", "_blank");
    if (popup) popup.opener = null;
    setOAuthStarting(true);
    setFormError(null);
    try {
      const result = await apiRequest<OAuthStatus & { session_id: string; auth_url: string; loopback: boolean }>(
        `/api/admin/modules/${moduleId}/oauth/start`,
        { method: "POST", body: JSON.stringify({ proxy_id: proxyId }) }
      );
      if (generation !== oauthGeneration.current) {
        popup?.close();
        await apiRequest(`/api/admin/modules/${moduleId}/oauth/${result.session_id}`, { method: "DELETE" });
        return;
      }
      const session = { ...result, moduleId, proxyId, expiresAt: Date.now() + result.expires_in * 1000 };
      updateOAuthSession(session);
      if (new URL(result.auth_url).protocol !== "https:") throw new Error("Некорректная ссылка авторизации");
      if (popup && !popup.closed) popup.location.replace(result.auth_url);
    } catch (err: any) {
      popup?.close();
      if (generation === oauthGeneration.current) {
        cancelOAuth();
        setFormError(err.message || "Не удалось начать авторизацию");
      }
    } finally {
      if (generation === oauthGeneration.current) setOAuthStarting(false);
    }
  };

  const handleOAuthCallback = async () => {
    const session = oauthRef.current;
    if (!session || session.status !== "pending" || !callbackUrl.trim()) return;
    if (oauthRequestBusy.current) {
      setFormError("Выполняется проверка авторизации. Повторите отправку URL через несколько секунд.");
      return;
    }
    oauthRequestBusy.current = true;
    setOAuthCallbackBusy(true);
    setFormError(null);
    try {
      const status = await apiRequest<OAuthStatus>(`/api/admin/modules/${session.moduleId}/oauth/${session.session_id}/callback`, {
        method: "POST",
        body: JSON.stringify({ callback_url: callbackUrl.trim() }),
      });
      if (oauthRef.current?.session_id === session.session_id) {
        updateOAuthSession({ ...session, ...status });
        setCallbackUrl("");
      }
    } catch (err: any) {
      if (oauthRef.current?.session_id === session.session_id) setFormError(err.message || "Ошибка обработки URL возврата");
    } finally {
      oauthRequestBusy.current = false;
      if (oauthRef.current?.session_id === session.session_id) setOAuthCallbackBusy(false);
    }
  };

  // Test Profile state
  const [testingProfileId, setTestingProfileId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{
    profileId: number;
    ok: boolean;
    message: string;
    latency?: number;
    modelsFound?: number;
  } | null>(null);

  // Module Notes modal
  const [notesModalOpen, setNotesModalOpen] = useState(false);
  const [notesModule, setNotesModule] = useState<LoadedModule | null>(null);

  // Profile Notes modal
  const [profileNotesModalOpen, setProfileNotesModalOpen] = useState(false);
  const [selectedProfileForNotes, setSelectedProfileForNotes] = useState<ModuleProfile | null>(null);

  const openNotesModal = (mod: LoadedModule) => {
    setNotesModule(mod);
    setNotesModalOpen(true);
  };

  const handleSaveNotes = async (notes: string) => {
    if (!notesModule) return;
    const trimmed = notes.trim();
    await apiRequest(`/api/admin/modules/${notesModule.manifest.id}/notes`, {
      method: "PUT",
      body: JSON.stringify({ notes: trimmed }),
    });
    setModules((prev) =>
      prev.map((m) =>
        m.manifest.id === notesModule.manifest.id ? { ...m, notes: trimmed || null } : m
      )
    );
    if (selectedModule && selectedModule.manifest.id === notesModule.manifest.id) {
      setSelectedModule({ ...selectedModule, notes: trimmed || null });
    }
  };

  const handleClearNotes = async () => {
    if (!notesModule) return;
    await apiRequest(`/api/admin/modules/${notesModule.manifest.id}/notes`, {
      method: "PUT",
      body: JSON.stringify({ notes: "" }),
    });
    setModules((prev) =>
      prev.map((m) =>
        m.manifest.id === notesModule.manifest.id ? { ...m, notes: null } : m
      )
    );
    if (selectedModule && selectedModule.manifest.id === notesModule.manifest.id) {
      setSelectedModule({ ...selectedModule, notes: null });
    }
  };

  const openProfileNotesModal = (p: ModuleProfile) => {
    setSelectedProfileForNotes(p);
    setProfileNotesModalOpen(true);
  };

  const handleSaveProfileNotes = async (notes: string) => {
    if (!selectedProfileForNotes || !selectedModule) return;
    const trimmed = notes.trim();
    await apiRequest(`/api/admin/modules/${selectedModule.manifest.id}/profiles/${selectedProfileForNotes.id}/notes`, {
      method: "PUT",
      body: JSON.stringify({ notes: trimmed }),
    });
    setProfiles((prev) =>
      prev.map((p) =>
        p.id === selectedProfileForNotes.id ? { ...p, notes: trimmed || null } : p
      )
    );
    setSelectedProfileForNotes((prev) => (prev ? { ...prev, notes: trimmed || null } : null));
    if (editingProfile && editingProfile.id === selectedProfileForNotes.id) {
      setEditingProfile({ ...editingProfile, notes: trimmed || null });
      setFormProfileNotes(trimmed);
    }
  };

  const handleClearProfileNotes = async () => {
    if (!selectedProfileForNotes || !selectedModule) return;
    await apiRequest(`/api/admin/modules/${selectedModule.manifest.id}/profiles/${selectedProfileForNotes.id}/notes`, {
      method: "PUT",
      body: JSON.stringify({ notes: "" }),
    });
    setProfiles((prev) =>
      prev.map((p) =>
        p.id === selectedProfileForNotes.id ? { ...p, notes: null } : p
      )
    );
    setSelectedProfileForNotes((prev) => (prev ? { ...prev, notes: null } : null));
    if (editingProfile && editingProfile.id === selectedProfileForNotes.id) {
      setEditingProfile({ ...editingProfile, notes: null });
      setFormProfileNotes("");
    }
  };

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
    cancelOAuth();
    setSelectedModule(mod);
    setEditingProfile(null);
    setFormName(`${mod.manifest.name} Profile`);
    setFormProxyId(undefined);
    setFormPriority(1);
    setFormWeight(1);
    setFormGroupName("");
    setFormRpm("");
    setFormTpm("");
    setFormMaxConcurrency("");
    setFormQuotas([]);
    setQuotaUsage([]);
    setUsageError("");
    setQuotaModels([]);
    setCatalogError(false);
    setShowPasswordFields({});
    setFormProfileNotes("");
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
    cancelOAuth();
    setEditingProfile(profile);
    setFormName(profile.name);
    setFormProxyId(profile.proxy_id || undefined);
    setFormPriority(profile.priority);
    setFormWeight(profile.weight);
    setFormGroupName(profile.group_name ?? "");
    setFormRpm(profile.rpm_limit?.toString() ?? "");
    setFormTpm(profile.tpm_limit?.toString() ?? "");
    setFormMaxConcurrency(profile.max_concurrency?.toString() ?? "");
    setFormQuotas((profile.quota_rules || []).map(rule => ({ ...rule })));
    setQuotaUsage([]);
    setUsageError("");
    setQuotaModels([]);
    setCatalogError(false);
    setShowPasswordFields({});
    void loadQuotaUsage(profile.id);
    setFormProfileNotes(profile.notes || "");
    setFormFields({ ...(profile.fields || {}) });
    setFormError(null);
    setIsProfileModalOpen(true);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedModule || savingProfile || oauthStarting) return;
    const session = oauthRef.current;
    if (session && (session.status !== "authorized" || Date.now() >= session.expiresAt)) {
      setFormError("Завершите авторизацию через браузер или отмените её для ручного ввода.");
      return;
    }
    setSavingProfile(true);
    setFormError(null);

    try {
      const finalNotes = formProfileNotes.trim() || null;
      const settings = {
        group_name: formGroupName.trim() || null,
        rpm_limit: formRpm === "" ? null : Number(formRpm),
        tpm_limit: formTpm === "" ? null : Number(formTpm),
        max_concurrency: formMaxConcurrency === "" ? null : Number(formMaxConcurrency),
        quota_rules: formQuotas,
      };
      // Text controls display JSON, but untouched and edited structured fields retain JSON types.
      const finalFields = Object.fromEntries(Object.entries(formFields).filter(([key]) => !session ||
        (selectedModule.manifest.fields.some(field => field.key === key && field.type !== "password") &&
          !["auth_json", "access_token", "refresh_token", "id_token"].includes(key))).map(([key, value]) => {
        const spec = selectedModule.manifest.fields.find(field => field.key === key);
        const initial = editingProfile && key in editingProfile.fields ? editingProfile.fields[key] : spec?.default;
        if (spec?.type === "number") {
          value = value === "" ? (spec.default ?? null) : Number(value);
          if (value !== null && !Number.isFinite(value)) throw new Error(`Некорректное число в поле ${key}`);
        } else if (typeof value === "string" && initial !== undefined && typeof initial !== "string") {
          try { value = JSON.parse(value); }
          catch { throw new Error(`Некорректный JSON в поле ${key}`); }
        }
        return [key, value];
      }).filter(([key, value]) => !editingProfile || session ||
        JSON.stringify(value) !== JSON.stringify(editingProfile.fields[key])));
      if (session) {
        if (session.proxyId !== (formProxyId ?? null)) throw new Error("Прокси изменён. Начните авторизацию заново.");
        const fields = finalFields;
        await apiRequest(`/api/admin/modules/${session.moduleId}/oauth/${session.session_id}/save`, {
          method: "POST",
          body: JSON.stringify({
            ...settings,
            profile_id: editingProfile?.id ?? null,
            name: formName,
            proxy_id: session.proxyId,
            priority: formPriority,
            weight: formWeight,
            fields,
            notes: finalNotes,
          }),
        });
        updateOAuthSession(null);
        setCallbackUrl("");
      } else if (editingProfile) {
        // Update
        await apiRequest(`/api/admin/modules/${selectedModule.manifest.id}/profiles/${editingProfile.id}`, {
          method: "PUT",
          body: JSON.stringify({
            name: formName,
            proxy_id: formProxyId || null,
            priority: formPriority,
            weight: formWeight,
            ...settings,
            fields: finalFields,
            notes: finalNotes,
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
            ...settings,
            fields: finalFields,
            notes: finalNotes,
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
    if (!window.confirm("Создать JSON в папке profiles/ на сервере? Файл содержит открытые секреты. Это не скачивание зашифрованного бэкапа и не полный снимок SQLite.")) return;
    try {
      const res = await apiRequest<{ success: boolean; relative_path: string }>(
        `/api/admin/modules/${selectedModule.manifest.id}/profiles/${profileId}/export`,
        { method: "POST" }
      );
      if (res && res.success) {
        alert(`JSON профиля создан на сервере:\nprofiles/${res.relative_path}\n\nСекреты в файле не зашифрованы. .gitignore исключает папку из обычного добавления в Git, но не защищает содержимое файла. Это не скачанный бэкап и не снимок SQLite.`);
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

                <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed mb-3">
                  {mod.manifest.description || "Модуль интеграции с внешним источником."}
                </p>

                {/* Notes Snippet on Card */}
                {mod.notes && (
                  <div
                    onClick={() => openNotesModal(mod)}
                    className="mb-3 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200/90 cursor-pointer hover:bg-amber-500/15 transition-all group/note"
                    title="Нажмите, чтобы просмотреть или изменить заметку"
                  >
                    <div className="flex items-center gap-1.5 text-[11px] font-semibold text-amber-400 mb-0.5">
                      <StickyNote size={12} className="group-hover/note:scale-110 transition-transform" />
                      <span>Заметка</span>
                    </div>
                    <p className="line-clamp-2 text-[11px] text-amber-100/80 whitespace-pre-wrap">
                      {mod.notes}
                    </p>
                  </div>
                )}

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
                  onClick={() => openNotesModal(mod)}
                  className={`btn-press flex items-center justify-center gap-1 px-2.5 py-2 rounded-xl text-xs font-medium border transition-all cursor-pointer ${
                    mod.notes
                      ? "bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25"
                      : "bg-slate-800/80 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border-white/[0.06]"
                  }`}
                  title={mod.notes ? "Редактировать заметку" : "Добавить заметку"}
                >
                  <StickyNote size={13} className={mod.notes ? "text-amber-400" : "text-slate-400"} />
                  <span>{mod.notes ? "Заметка" : "+ Заметка"}</span>
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
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => openNotesModal(selectedModule)}
                  className={`btn-press flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium border transition-all cursor-pointer ${
                    selectedModule.notes
                      ? "bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25"
                      : "bg-slate-800/80 hover:bg-slate-800 text-slate-300 border-white/[0.08]"
                  }`}
                  title="Заметка к этому модулю"
                >
                  <StickyNote size={13} className={selectedModule.notes ? "text-amber-400" : "text-slate-400"} />
                  <span>{selectedModule.notes ? "Заметка" : "+ Заметка"}</span>
                </button>
                <button
                  onClick={() => openCreateModal(selectedModule)}
                  className="btn-press flex items-center gap-1 px-3 py-1.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-xs font-semibold shadow-xs transition-all"
                >
                  <Plus size={13} />
                  <span>Новый профиль</span>
                </button>
              </div>
            </div>

            {/* Git Isolation Notice */}
            <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs text-indigo-300 flex items-start gap-2.5">
              <Shield size={16} className="shrink-0 mt-0.5 text-indigo-400" />
              <div className="leading-relaxed">
                <strong>Три разных формата:</strong> Экспорт профиля создаёт JSON с открытыми секретами в папке <code className="text-slate-200">profiles/</code> на сервере, без скачивания. Эта папка исключена из обычного добавления в Git, но файл не зашифрован. Экспорт конфигурации на странице ключей скачивает зашифрованный бэкап провайдеров, ключей и выбранных прокси. Для полного восстановления всех таблиц нужен отдельный снимок SQLite.
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

                          <SubscriptionLimitsBadge credentialId={p.id} moduleId={p.module_id} name={p.name} />

                          {/* Proxy info */}
                          <div className="flex items-center gap-2 text-xs text-slate-400 mt-1">
                            <Network size={12} className={p.proxy ? "text-indigo-400" : "text-slate-600"} />
                            {p.module_id === "lingling" ? (
                              <span className="font-mono text-[11px] text-slate-300">
                                {p.fields.transport_mode === "proxy" ? "Пул прокси" : p.fields.transport_mode === "mixed" ? "Tor + прокси" : "Tor"}
                                {p.fields.transport_mode !== "tor" && p.fields.transport_mode && Array.isArray(p.fields.proxy_ids) && p.fields.proxy_ids.length > 0 && ` · ${p.fields.proxy_ids.map((id: number) => proxies.find(px => px.id === id)?.name || `#${id} (недоступен)`).join(" → ")}`}
                                {p.proxy && ` · ${p.proxy.name}`}
                                {p.fields.transport_mode !== "tor" && p.fields.transport_mode && ` · ${p.fields.proxy_policy === "priority" ? "по приоритету" : "балансировка"}`}
                              </span>
                            ) : p.proxy ? (
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

                          {p.notes && (
                            <button
                              type="button"
                              onClick={() => openProfileNotesModal(p)}
                              className="mt-2 flex items-center gap-1.5 text-xs text-amber-300/90 hover:text-amber-200 cursor-pointer max-w-md text-left group/note p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20"
                              title={p.notes}
                            >
                              <StickyNote size={12} className="shrink-0 text-amber-400 group-hover/note:scale-110 transition-transform" />
                              <span className="truncate">{p.notes}</span>
                            </button>
                          )}
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
                            title="Создать JSON профиля на сервере (открытые секреты, не бэкап)"
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
                            type="button"
                            onClick={() => openProfileNotesModal(p)}
                            className={`btn-press p-1.5 rounded-lg text-xs border transition-all cursor-pointer ${
                              p.notes
                                ? "bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25"
                                : "bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border-white/[0.06]"
                            }`}
                            title={p.notes ? "Заметка" : "Добавить заметку"}
                          >
                            <StickyNote size={13} className={p.notes ? "text-amber-400" : "text-slate-400"} />
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
          onClose={() => { if (!savingProfile) setIsProfileModalOpen(false); }}
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

            <QuotaEditor q={q} formQuotas={formQuotas} setFormQuotas={setFormQuotas} quotaUsage={quotaUsage} usageError={usageError} quotaCatalog={quotaCatalog} catalogError={catalogError} allowProfiles={false} onRefresh={editingProfile ? () => loadQuotaUsage(editingProfile.id) : undefined} />

            <div>
              <label htmlFor="module-profile-group" className="block text-xs font-semibold text-slate-300 mb-1">Группа</label>
              <input id="module-profile-group" value={formGroupName} onChange={e => setFormGroupName(e.target.value)} className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] rounded-xl text-xs text-slate-200" />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {([["RPM", formRpm, setFormRpm], ["TPM", formTpm, setFormTpm], ["Параллельные запросы", formMaxConcurrency, setFormMaxConcurrency]] as const).map(([label, value, setValue]) => (
                <label key={label} className="block text-xs text-slate-300">{label}
                  <input type="number" min="1" step="1" value={value} onChange={e => setValue(e.target.value)} placeholder="Без лимита" className="w-full mt-1 px-3 py-2 bg-slate-950 border border-white/[0.08] rounded-xl text-xs text-slate-200" />
                </label>
              ))}
            </div>

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
                  <span>{selectedModule.manifest.id === "lingling" ? "Дополнительный одиночный прокси" : "Привязанный прокси"}</span>
                </span>
                <span className="text-[11px] text-slate-500 font-normal">
                  {selectedModule.manifest.id === "lingling" ? "Добавляется после выбранного пула" : "Все вызовы модуля пойдут через этот прокси"}
                </span>
              </label>
              <select
                value={formProxyId || ""}
                disabled={oauthStarting || !!oauthSession || savingProfile || (selectedModule.manifest.id === "lingling" && (formFields.transport_mode || "tor") === "tor")}
                onChange={(e) => setFormProxyId(e.target.value ? Number(e.target.value) : undefined)}
                className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-xs text-slate-200 focus:outline-hidden"
              >
                <option value="">{selectedModule.manifest.id === "lingling" ? "Не добавлять (прямого выхода нет)" : "Direct / Без прокси (прямое соединение с сервера)"}</option>
                {proxies.map((px) => (
                  <option key={px.id} value={px.id} disabled={selectedModule.manifest.id === "lingling" && !px.enabled}>
                    {getCountryFlag(px.country_code || "")} [{px.scheme.toUpperCase()}] {px.name} — {px.host}:{px.port} {px.country ? `(${px.country})` : ""}
                  </option>
                ))}
              </select>
            </div>

            {supportsBrowserOAuth && (
              <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 space-y-3 text-xs">
                <p className="text-slate-400 leading-relaxed">
                  Страница входа использует сеть вашего браузера. Выбранный прокси применяется на сервере для обмена токенами и вызовов моделей. Во время OAuth прокси изменить нельзя.
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={handleStartOAuth}
                    disabled={oauthStarting || savingProfile || (!!oauthSession && oauthSession.status !== "error")}
                    className="btn-press px-3 py-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-xl font-medium disabled:opacity-50"
                  >
                    {oauthStarting ? "Начало авторизации..." : oauthSession?.status === "error" ? "Повторить авторизацию" : "Авторизоваться через браузер"}
                  </button>
                  {(oauthSession || oauthStarting) && (
                    <button type="button" onClick={() => cancelOAuth(true)} disabled={savingProfile} className="btn-press px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl disabled:opacity-50">
                      Отменить OAuth
                    </button>
                  )}
                </div>
                {oauthSession && (
                  <>
                    <div role="status" aria-live="polite" className={oauthSession.status === "authorized" ? "text-emerald-300" : oauthSession.status === "error" ? "text-rose-300" : "text-indigo-300"}>
                      {oauthSession.status === "authorized" ? "Авторизация завершена. Нажмите «Создать профиль» или «Обновить профиль», чтобы сохранить." : oauthSession.status === "error" ? (oauthSession.message || "Ошибка авторизации. Попробуйте снова.") : "Ожидание входа в браузере… Сессия действует 10 минут."}
                    </div>
                    {oauthSession.status === "pending" && (
                      <>
                        <a href={oauthSession.auth_url} target="_blank" rel="noopener noreferrer" className="inline-block text-indigo-300 underline underline-offset-2">
                          Открыть страницу входа в новой вкладке (если она не открылась)
                        </a>
                        <p className="text-slate-400 leading-relaxed">
                          {oauthSession.loopback ? "Возврат может обработаться автоматически, если браузер и сервер находятся на одном компьютере. " : "Автоматический возврат недоступен. "}
                          Если вход не завершился здесь, скопируйте полный URL из адресной строки после входа (даже если страница localhost не открылась) и вставьте ниже. Не вставляйте токены.
                        </p>
                        <label htmlFor="module-oauth-callback" className="block text-slate-300">URL возврата после входа</label>
                        <input
                          id="module-oauth-callback"
                          type="text"
                          value={callbackUrl}
                          onChange={(e) => setCallbackUrl(e.target.value)}
                          autoComplete="off"
                          spellCheck={false}
                          placeholder="http://localhost:…/callback?code=…&state=…"
                          disabled={oauthCallbackBusy}
                          className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-slate-200 placeholder-slate-600 focus:outline-hidden"
                        />
                        <button type="button" onClick={handleOAuthCallback} disabled={oauthCallbackBusy || !callbackUrl.trim()} className="btn-press px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl disabled:opacity-50">
                          {oauthCallbackBusy ? "Обработка..." : "Отправить URL возврата"}
                        </button>
                      </>
                    )}
                  </>
                )}
              </div>
            )}

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

                {selectedModule.manifest.fields.filter((field) => (!oauthSession || (field.type !== "password" && !["auth_json", "access_token", "refresh_token", "id_token"].includes(field.key))) &&
                  (selectedModule.manifest.id !== "lingling" || !((formFields.transport_mode || "tor") === "proxy" && ["lanes", "countries", "fallback_countries", "preferred_countries", "tor_path"].includes(field.key))) &&
                  (selectedModule.manifest.id !== "lingling" || !((formFields.transport_mode || "tor") === "tor" && ["proxy_ids", "proxy_policy"].includes(field.key)))).map((field) => {
                  const isPassword = field.type === "password";
                  const showPass = !!showPasswordFields[field.key];
                  const rawValue = formFields[field.key] ?? field.default;
                  const pool = Array.isArray(rawValue) ? rawValue as number[] : [];
                  const value = rawValue === undefined ? "" : typeof rawValue === "string" ? rawValue : JSON.stringify(rawValue);

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

                      {selectedModule.manifest.id === "lingling" && field.key === "proxy_ids" ? (
                        <fieldset className="space-y-2" aria-label="Пул прокси Lingling">
                          <legend className="sr-only">Пул прокси Lingling</legend>
                          <p className="text-xs text-slate-400">Добавьте свой HTTP / HTTPS / SOCKS5-шлюз в разделе «Прокси», затем выберите его здесь. Прямого выхода нет.</p>
                          {proxies.length === 0 && <p role="status" className="text-xs text-amber-300">Сначала добавьте прокси в разделе «Прокси».</p>}
                          <div className="space-y-1">
                            {proxies.map(px => (
                              <label key={px.id} className="flex items-center gap-2 text-xs text-slate-300">
                                <input type="checkbox" checked={pool.includes(px.id)} disabled={!px.enabled && !pool.includes(px.id)}
                                  onChange={e => setFormFields({ ...formFields, proxy_ids: e.target.checked ? [...pool, px.id] : pool.filter(id => id !== px.id) })} />
                                {px.name} [{px.scheme.toUpperCase()}]{!px.enabled && " (отключён)"}
                              </label>
                            ))}
                          </div>
                          {pool.map((id, index) => (
                            <div key={id} className="flex items-center gap-2 text-xs text-slate-300">
                              <span className="flex-1">{index + 1}. {proxies.find(px => px.id === id)?.name || `#${id} (недоступен)`}</span>
                              <button type="button" disabled={index === 0} aria-label={`Поднять прокси ${id}`}
                                onClick={() => { const next = [...pool]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; setFormFields({ ...formFields, proxy_ids: next }); }}
                                className="px-2 py-1 rounded bg-slate-800 disabled:opacity-30">↑</button>
                              <button type="button" disabled={index === pool.length - 1} aria-label={`Опустить прокси ${id}`}
                                onClick={() => { const next = [...pool]; [next[index], next[index + 1]] = [next[index + 1], next[index]]; setFormFields({ ...formFields, proxy_ids: next }); }}
                                className="px-2 py-1 rounded bg-slate-800 disabled:opacity-30">↓</button>
                              <button type="button" aria-label={`Убрать прокси ${id}`} onClick={() => setFormFields({ ...formFields, proxy_ids: pool.filter(value => value !== id) })}
                                className="px-2 py-1 rounded bg-slate-800">×</button>
                            </div>
                          ))}
                        </fieldset>
                      ) : field.type === "textarea" ? (
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
                          aria-label={field.label}
                          required={field.required}
                          value={value}
                          onChange={(e) => {
                            setFormFields({ ...formFields, [field.key]: e.target.value });
                            if (selectedModule.manifest.id === "lingling" && field.key === "transport_mode" && e.target.value === "tor") setFormProxyId(undefined);
                          }}
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

            {/* Profile Notes */}
            <div className="pt-2 border-t border-white/[0.06] space-y-1">
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Заметки
              </label>
              <textarea
                value={formProfileNotes}
                onChange={(e) => setFormProfileNotes(e.target.value)}
                placeholder="Личные заметки к этому профилю / ключу модуля..."
                rows={3}
                className="w-full px-3 py-2 bg-slate-950 border border-white/[0.08] focus:border-indigo-500 rounded-xl text-xs text-slate-200 placeholder-slate-600 focus:outline-hidden resize-y"
              />
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-2 pt-4 border-t border-white/[0.06]">
              <button
                type="button"
                onClick={() => setIsProfileModalOpen(false)}
                disabled={savingProfile}
                className="btn-press px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium border border-white/[0.06]"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={savingProfile || oauthStarting || (!!oauthSession && oauthSession.status !== "authorized")}
                className="btn-press px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/20 disabled:opacity-50"
              >
                {savingProfile ? "Сохранение..." : editingProfile ? "Обновить профиль" : "Создать профиль"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Quick Notes Modal for Module */}
      <NotesModal
        isOpen={notesModalOpen}
        onClose={() => {
          setNotesModalOpen(false);
          setNotesModule(null);
        }}
        title={`Заметка: ${notesModule?.manifest.name || "Модуль"}`}
        subtitle={`Модуль ID: ${notesModule?.manifest.id || ""}`}
        entityType="module"
        initialNotes={notesModule?.notes || ""}
        onSave={handleSaveNotes}
        onClear={handleClearNotes}
      />

      {/* Quick Notes Modal for Module Profile */}
      <NotesModal
        isOpen={profileNotesModalOpen}
        onClose={() => {
          setProfileNotesModalOpen(false);
          setSelectedProfileForNotes(null);
        }}
        title={`Заметка: ${selectedProfileForNotes?.name || "Профиль"}`}
        subtitle={`Профиль ID: ${selectedProfileForNotes?.id || ""} • Модуль: ${selectedModule?.manifest.name || ""}`}
        entityType="module"
        initialNotes={selectedProfileForNotes?.notes || ""}
        onSave={handleSaveProfileNotes}
        onClear={handleClearProfileNotes}
      />
    </div>
  );
};
