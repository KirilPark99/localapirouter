import React, { useEffect, useState } from "react";
import { Plus, Edit2, Trash2, Cpu, Globe, KeyRound, Boxes, CheckCircle2, Download, Upload } from "lucide-react";
import { apiRequest } from "../api/client";
import { Provider, ProviderCreate } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { Modal } from "../components/Modal";
import { BackupExportModal, BackupImportModal } from "../components/BackupModals";
import { useI18n } from "../i18n/context";

export const ProvidersPage: React.FC = () => {
  const { t } = useI18n();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);

  const [formName, setFormName] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formAdapterType, setFormAdapterType] = useState("generic_openai");
  const [formBaseUrl, setFormBaseUrl] = useState("https://api.openai.com/v1");
  const [formModelsEndpoint, setFormModelsEndpoint] = useState("/models");
  const [formChatEndpoint, setFormChatEndpoint] = useState("/chat/completions");
  const [formAuthType, setFormAuthType] = useState<"bearer" | "x-api-key" | "custom_header" | "query_param" | "none">("bearer");
  const [formAuthHeader, setFormAuthHeader] = useState("Authorization");

  const loadProviders = async () => {
    setLoading(true);
    try {
      const data = await apiRequest<Provider[]>("/api/admin/providers");
      setProviders(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProviders();
  }, []);

  const openCreateModal = () => {
    setEditingProvider(null);
    setFormName("");
    setFormSlug("");
    setFormAdapterType("generic_openai");
    setFormBaseUrl("http://localhost:8000/v1");
    setFormModelsEndpoint("/models");
    setFormChatEndpoint("/chat/completions");
    setFormAuthType("bearer");
    setFormAuthHeader("Authorization");
    setIsModalOpen(true);
  };

  const applyPreset = (preset: {
    name: string;
    slug: string;
    adapter_type: string;
    base_url: string;
    models_endpoint: string;
    chat_endpoint: string;
    auth_type: "bearer" | "x-api-key" | "custom_header" | "query_param" | "none";
    auth_header: string;
  }) => {
    setFormName(preset.name);
    setFormSlug(preset.slug);
    setFormAdapterType(preset.adapter_type);
    setFormBaseUrl(preset.base_url);
    setFormModelsEndpoint(preset.models_endpoint);
    setFormChatEndpoint(preset.chat_endpoint);
    setFormAuthType(preset.auth_type);
    setFormAuthHeader(preset.auth_header);
  };

  const openEditModal = (provider: Provider) => {
    setEditingProvider(provider);
    setFormName(provider.name);
    setFormSlug(provider.slug);
    setFormAdapterType(provider.adapter_type);
    setFormBaseUrl(provider.base_url);
    setFormModelsEndpoint(provider.models_endpoint || "/models");
    setFormChatEndpoint(provider.chat_endpoint || "/chat/completions");
    setFormAuthType(provider.auth_type as any);
    setFormAuthHeader(provider.auth_header || "Authorization");
    setIsModalOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: ProviderCreate = {
        name: formName,
        slug: formSlug,
        adapter_type: formAdapterType,
        base_url: formBaseUrl,
        models_endpoint: formModelsEndpoint,
        chat_endpoint: formChatEndpoint,
        auth_type: formAuthType,
        auth_header: formAuthHeader,
      };

      if (editingProvider) {
        await apiRequest(`/api/admin/providers/${editingProvider.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiRequest("/api/admin/providers", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      setIsModalOpen(false);
      loadProviders();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`${t.common.confirmDelete} (${name})`)) return;
    try {
      await apiRequest(`/api/admin/providers/${id}`, { method: "DELETE" });
      loadProviders();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-100">{t.providers.title}</h2>
          <p className="text-xs text-slate-400">{t.providers.subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsExportModalOpen(true)}
            className="btn-press flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] text-slate-200 text-xs font-medium rounded-xl shadow-xs transition-colors border border-white/[0.08] cursor-pointer"
            title={t.common.export}
          >
            <Download size={14} className="text-indigo-400" />
            <span>{t.common.export}</span>
          </button>
          <button
            onClick={() => setIsImportModalOpen(true)}
            className="btn-press flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.08] text-slate-200 text-xs font-medium rounded-xl shadow-xs transition-colors border border-white/[0.08] cursor-pointer"
            title={t.common.import}
          >
            <Upload size={14} className="text-emerald-400" />
            <span>{t.common.import}</span>
          </button>
          <button
            onClick={openCreateModal}
            className="btn-press flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-indigo-600/25 transition-all cursor-pointer"
          >
            <Plus size={15} />
            {t.providers.addProvider}
          </button>
        </div>
      </div>

      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] overflow-hidden shadow-xl">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-white/[0.06] bg-white/[0.02] text-slate-400 font-semibold uppercase tracking-wider text-[10px] font-mono">
              <th className="py-3.5 px-4">{t.common.provider}</th>
              <th className="py-3.5 px-4">{t.providers.adapterType}</th>
              <th className="py-3.5 px-4">{t.providers.baseUrl}</th>
              <th className="py-3.5 px-4">{t.credentials.title}</th>
              <th className="py-3.5 px-4">{t.models.title}</th>
              <th className="py-3.5 px-4">{t.common.status}</th>
              <th className="py-3.5 px-4 text-right">{t.common.actions}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05] text-slate-300">
            {providers.map((p) => (
              <tr key={p.id} className="hover:bg-white/[0.03] transition-colors">
                <td className="py-3 px-4 font-medium text-slate-100 flex items-center gap-2">
                  <Cpu size={15} className="text-indigo-400 shrink-0" />
                  <div>
                    <div className="font-semibold">{p.name}</div>
                    <div className="text-[10px] text-slate-400 font-mono">{p.slug}</div>
                  </div>
                </td>
                <td className="py-3 px-4 font-mono text-[11px] text-indigo-300 font-medium">{p.adapter_type}</td>
                <td className="py-3 px-4 font-mono text-[11px] text-slate-400 max-w-xs truncate" title={p.base_url}>
                  {p.base_url}
                </td>
                <td className="py-3 px-4 font-medium">
                  <span className="text-slate-200">{p.credentials_count}</span>
                  {p.healthy_credentials_count > 0 && (
                    <span className="text-emerald-400 text-[10px] ml-1 font-mono">({p.healthy_credentials_count} ok)</span>
                  )}
                </td>
                <td className="py-3 px-4 font-medium text-slate-200">{p.models_count}</td>
                <td className="py-3 px-4">
                  <StatusBadge
                    status={
                      !p.enabled
                        ? "DISABLED"
                        : p.credentials_count > 0 && p.healthy_credentials_count > 0
                        ? "HEALTHY"
                        : p.credentials_count === 0
                        ? "UNKNOWN"
                        : "DEGRADED"
                    }
                  />
                </td>
                <td className="py-3 px-4 text-right space-x-1 whitespace-nowrap">
                  <button
                    onClick={() => openEditModal(p)}
                    className="btn-press text-slate-400 hover:text-slate-200 p-1.5 hover:bg-white/[0.06] rounded-lg transition-colors cursor-pointer"
                    title={t.common.edit}
                  >
                    <Edit2 size={14} />
                  </button>
                  <button
                    onClick={() => handleDelete(p.id, p.name)}
                    className="btn-press text-slate-400 hover:text-rose-400 p-1.5 hover:bg-rose-500/10 rounded-lg transition-colors cursor-pointer"
                    title={t.common.delete}
                  >
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal: Create/Edit Provider */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingProvider ? `${t.providers.editProvider}: ${editingProvider.name}` : t.providers.addProvider}
      >
        <form onSubmit={handleSave} className="space-y-4">
          {!editingProvider && (
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1.5">Presets / Templates:</label>
              <div className="flex flex-wrap gap-1.5">
                {[
                  {
                    name: "ModelScope",
                    slug: "modelscope",
                    adapter_type: "generic_openai",
                    base_url: "https://api-inference.modelscope.ai/v1",
                    models_endpoint: "/models",
                    chat_endpoint: "/chat/completions",
                    auth_type: "bearer" as const,
                    auth_header: "Authorization",
                  },
                  {
                    name: "Kilo Gateway",
                    slug: "kilo-ai",
                    adapter_type: "generic_openai",
                    base_url: "https://api.kilo.ai/api/gateway",
                    models_endpoint: "/models",
                    chat_endpoint: "/chat/completions",
                    auth_type: "none" as const,
                    auth_header: "Authorization",
                  },
                  {
                    name: "OpenCode Zen",
                    slug: "opencode-zen",
                    adapter_type: "generic_openai",
                    base_url: "https://opencode.ai/zen/v1",
                    models_endpoint: "/models",
                    chat_endpoint: "/chat/completions",
                    auth_type: "bearer" as const,
                    auth_header: "Authorization",
                  },
                  {
                    name: "Ollama (Local)",
                    slug: "ollama",
                    adapter_type: "generic_openai",
                    base_url: "http://localhost:11434/v1",
                    models_endpoint: "/models",
                    chat_endpoint: "/chat/completions",
                    auth_type: "none" as const,
                    auth_header: "Authorization",
                  },
                  {
                    name: "llm7",
                    slug: "llm7",
                    adapter_type: "generic_openai",
                    base_url: "https://api.llm7.io/v1",
                    models_endpoint: "/models",
                    chat_endpoint: "/chat/completions",
                    auth_type: "bearer" as const,
                    auth_header: "Authorization",
                  },
                  {
                    name: "NavyAI",
                    slug: "navyai",
                    adapter_type: "generic_openai",
                    base_url: "https://api.navy/v1",
                    models_endpoint: "/models",
                    chat_endpoint: "/chat/completions",
                    auth_type: "bearer" as const,
                    auth_header: "Authorization",
                  },
                  {
                    name: "LM Studio",
                    slug: "lm-studio",
                    adapter_type: "generic_openai",
                    base_url: "http://localhost:1234/v1",
                    models_endpoint: "/models",
                    chat_endpoint: "/chat/completions",
                    auth_type: "none" as const,
                    auth_header: "Authorization",
                  },
                ].map((p) => (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => applyPreset(p)}
                    className="btn-press px-2.5 py-1 bg-white/[0.04] hover:bg-indigo-500/15 hover:border-indigo-500/40 border border-white/[0.08] rounded-lg text-[11px] text-slate-300 hover:text-indigo-200 transition-colors cursor-pointer"
                  >
                    + {p.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">{t.providers.providerName}</label>
              <input
                type="text"
                required
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="My Local LLM"
                className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none transition-all"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">{t.common.slug}</label>
              <input
                type="text"
                disabled={!!editingProvider}
                value={formSlug}
                onChange={(e) => setFormSlug(e.target.value)}
                placeholder="my-local-llm"
                className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none disabled:opacity-40 transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">{t.providers.adapterType}</label>
              <select
                value={formAdapterType}
                onChange={(e) => setFormAdapterType(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none transition-all"
              >
                <option value="generic_openai">Generic OpenAI Compatible</option>
                <option value="google">Google AI Studio / Gemini</option>
                <option value="anthropic">Anthropic Messages</option>
                <option value="openrouter">OpenRouter</option>
                <option value="groq">Groq</option>
                <option value="deepseek">DeepSeek</option>
                <option value="mistral">Mistral AI</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">{t.providers.baseUrl}</label>
              <input
                type="text"
                required
                value={formBaseUrl}
                onChange={(e) => setFormBaseUrl(e.target.value)}
                placeholder="https://api.example.com/v1"
                className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none font-mono transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Models Endpoint</label>
              <input
                type="text"
                value={formModelsEndpoint}
                onChange={(e) => setFormModelsEndpoint(e.target.value)}
                placeholder="/models"
                className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none font-mono transition-all"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Chat Endpoint</label>
              <input
                type="text"
                value={formChatEndpoint}
                onChange={(e) => setFormChatEndpoint(e.target.value)}
                placeholder="/chat/completions"
                className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none font-mono transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Auth Type</label>
              <select
                value={formAuthType}
                onChange={(e) => setFormAuthType(e.target.value as any)}
                className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none transition-all"
              >
                <option value="bearer">Bearer Token</option>
                <option value="x-api-key">x-api-key</option>
                <option value="custom_header">Custom Header</option>
                <option value="query_param">Query Parameter (?key=...)</option>
                <option value="none">No Auth (Local LLM)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Auth Header Name</label>
              <input
                type="text"
                value={formAuthHeader}
                onChange={(e) => setFormAuthHeader(e.target.value)}
                placeholder="Authorization"
                className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none font-mono transition-all"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-4 border-t border-white/[0.08]">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="btn-press px-3.5 py-2 bg-white/[0.05] hover:bg-white/[0.08] text-slate-300 rounded-xl text-xs font-medium border border-white/10 transition-colors cursor-pointer"
            >
              {t.common.cancel}
            </button>
            <button
              type="submit"
              className="btn-press px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/25 transition-all cursor-pointer"
            >
              {editingProvider ? t.common.save : t.common.create}
            </button>
          </div>
        </form>
      </Modal>

      <BackupExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        providers={providers}
      />
      <BackupImportModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onSuccess={() => {
          loadProviders();
        }}
      />
    </div>
  );
};
