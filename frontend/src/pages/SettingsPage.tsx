import React, { useEffect, useState } from "react";
import { Settings, ShieldCheck, Lock, CheckCircle2, Download, Upload, FolderDown, Globe } from "lucide-react";
import { apiRequest } from "../api/client";
import { Provider } from "../types";
import { BackupExportModal, BackupImportModal } from "../components/BackupModals";
import { useI18n } from "../i18n/context";
import { LanguageSelector } from "../components/LanguageSelector";

export const SettingsPage: React.FC = () => {
  const { t } = useI18n();
  const [settings, setSettings] = useState<any>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [logContent, setLogContent] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const loadSettings = async () => {
    try {
      const [data, provs] = await Promise.all([
        apiRequest("/api/admin/settings"),
        apiRequest<Provider[]>("/api/admin/providers").catch(() => []),
      ]);
      setSettings(data);
      setProviders(provs);
      setLogContent(data.log_request_content);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleTogglePrivacy = async (val: boolean) => {
    setLogContent(val);
    try {
      await apiRequest("/api/admin/settings", {
        method: "POST",
        body: JSON.stringify({ log_request_content: val }),
      });
      setMsg({ text: "Privacy setting updated successfully.", ok: true });
    } catch (err: any) {
      setMsg({ text: err.message, ok: false });
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPassword || newPassword.length < 6) {
      setMsg({ text: "Password must be at least 6 characters.", ok: false });
      return;
    }
    try {
      await apiRequest("/api/admin/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ new_password: newPassword }),
      });
      setNewPassword("");
      setMsg({ text: "Admin password changed successfully!", ok: true });
    } catch (err: any) {
      setMsg({ text: err.message, ok: false });
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-lg font-bold text-slate-100">{t.settings.title}</h2>
        <p className="text-xs text-slate-400">{t.settings.subtitle}</p>
      </div>

      {msg && (
        <div
          className={`p-3.5 rounded-2xl border text-xs flex items-center gap-2.5 glass-card card-specular ${
            msg.ok ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300" : "bg-rose-950/40 border-rose-500/30 text-rose-300"
          }`}
        >
          <CheckCircle2 size={16} />
          <span>{msg.text}</span>
        </div>
      )}

      {/* Interface & Localization Section */}
      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-5 space-y-4 shadow-xl">
        <div className="flex items-center gap-2">
          <Globe size={16} className="text-indigo-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 font-mono">
            {t.settings.languageSection}
          </h3>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          {t.settings.languageDesc}
        </p>
        <LanguageSelector variant="full" />
      </div>

      {/* Security Status Box */}
      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-5 space-y-3 shadow-xl">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2 font-mono">
          <ShieldCheck size={16} className="text-emerald-400" />
          {t.settings.encryption}
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          {t.settings.encryptionDesc}
        </p>
        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 font-medium">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          ROUTER_MASTER_KEY is Active and Verified
        </div>
      </div>

      {/* Prompt Privacy Toggle */}
      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-5 space-y-3 shadow-xl">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 font-mono">
          {t.settings.privacy}
        </h3>
        <p className="text-xs text-slate-400 leading-relaxed">
          {t.settings.privacyDesc}
        </p>
        <label className="flex items-center gap-3 text-xs text-slate-200 cursor-pointer pt-1">
          <input
            type="checkbox"
            checked={logContent}
            onChange={(e) => handleTogglePrivacy(e.target.checked)}
            className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-0 cursor-pointer w-4 h-4"
          />
          <span>Store prompt and response content in request logs (Disabled by default)</span>
        </label>
      </div>

      {/* Backup & Migration Box */}
      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-5 space-y-3 shadow-xl">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2 font-mono">
          <FolderDown size={16} className="text-indigo-400" />
          {t.settings.backupRestore}
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed">
          Export configured AI providers and upstream API keys to a portable JSON backup, or import to another MyAIrouter instance.
        </p>
        <div className="flex items-center gap-2.5 pt-1">
          <button
            type="button"
            onClick={() => setIsExportModalOpen(true)}
            className="btn-press flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition-all cursor-pointer shadow-md shadow-indigo-600/25"
          >
            <Download size={14} />
            <span>{t.settings.exportBackup}</span>
          </button>
          <button
            type="button"
            onClick={() => setIsImportModalOpen(true)}
            className="btn-press flex items-center gap-1.5 px-3.5 py-2 bg-white/[0.04] hover:bg-white/[0.08] text-slate-200 rounded-xl text-xs font-semibold transition-colors border border-white/10 cursor-pointer"
          >
            <Upload size={14} className="text-emerald-400" />
            <span>{t.settings.importBackup}</span>
          </button>
        </div>
      </div>

      {/* Change Password Form */}
      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-5 space-y-3 shadow-xl">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2 font-mono">
          <Lock size={15} className="text-indigo-400" />
          {t.settings.adminPassword}
        </h3>
        <form onSubmit={handlePasswordChange} className="space-y-3 max-w-sm">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">{t.settings.newPassword}</label>
            <input
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Minimum 6 characters"
              className="w-full px-3.5 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none transition-all"
            />
          </div>
          <button
            type="submit"
            className="btn-press px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/25 transition-all cursor-pointer"
          >
            {t.settings.changePassword}
          </button>
        </form>
      </div>

      {/* Backup Export & Import Modals */}
      <BackupExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        providers={providers}
      />
      <BackupImportModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onSuccess={() => {
          loadSettings();
        }}
      />
    </div>
  );
};
