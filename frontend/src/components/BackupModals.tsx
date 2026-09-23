import React, { useState, useRef } from "react";
import {
  Download,
  Upload,
  FileDown,
  FileUp,
  KeyRound,
  Cpu,
  Layers,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Lock,
  Eye,
  EyeOff,
  Folder,
  Network,
  Check,
  RefreshCw,
  X,
  FileJson,
} from "lucide-react";
import { Modal } from "./Modal";
import { apiRequest } from "../api/client";
import {
  Provider,
  BackupExportRequest,
  BackupPreviewResponse,
  BackupImportRequest,
  BackupImportResponse,
} from "../types";

// ==========================================
// EXPORT MODAL
// ==========================================

interface BackupExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  providers: Provider[];
}

export const BackupExportModal: React.FC<BackupExportModalProps> = ({
  isOpen,
  onClose,
  providers,
}) => {
  const [selectedProviderIds, setSelectedProviderIds] = useState<number[]>(() =>
    providers.map((p) => p.id)
  );
  const [includeProxies, setIncludeProxies] = useState(true);
  const [passphrase, setPassphrase] = useState("");
  const [showPassphrase, setShowPassphrase] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Sync selected providers when modal opens or providers change
  React.useEffect(() => {
    if (isOpen) {
      setSelectedProviderIds(providers.map((p) => p.id));
      setErrorMsg(null);
      setIsExporting(false);
    }
  }, [isOpen, providers]);

  const toggleProvider = (id: number) => {
    setSelectedProviderIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const selectAll = () => setSelectedProviderIds(providers.map((p) => p.id));
  const deselectAll = () => setSelectedProviderIds([]);

  const handleExport = async () => {
    if (selectedProviderIds.length === 0) {
      setErrorMsg("Please select at least one provider to export");
      return;
    }
    if (passphrase.trim().length < 12) {
      setErrorMsg("Use an encryption passphrase of at least 12 characters");
      return;
    }

    setIsExporting(true);
    setErrorMsg(null);

    try {
      const payload: BackupExportRequest = {
        provider_ids: selectedProviderIds.length === providers.length ? undefined : selectedProviderIds,
        include_proxies: includeProxies,
        passphrase: passphrase.trim(),
      };

      const result = await apiRequest<any>("/api/admin/backup/export", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      // Prepare JSON file download
      const jsonStr = JSON.stringify(result, null, 2);
      const blob = new Blob([jsonStr], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const now = new Date();
      const pad = (n: number) => String(n).padStart(2, "0");
      const dateTag = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`;
      const filename = `myairouter-keys-backup-${dateTag}-encrypted.json`;

      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to generate export file");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Export Configuration (Keys + Providers)"
      maxWidth="lg"
    >
      <div className="space-y-4 text-xs">
        {/* Banner */}
        <div className="p-3 bg-indigo-950/40 border border-indigo-800/60 rounded-xl text-indigo-200 flex items-start gap-2.5">
          <FileDown size={18} className="text-indigo-400 shrink-0 mt-0.5" />
          <div className="leading-relaxed">
            <span className="font-semibold text-indigo-100">Migration to another server: </span>
            The export file contains provider settings and decrypted API keys.
            When imported on a new server, keys will automatically be re-encrypted with that server's own master key.
          </div>
        </div>

        {errorMsg && (
          <div className="p-2.5 bg-rose-950/60 border border-rose-800/80 rounded-lg text-rose-300 flex items-center gap-2">
            <AlertTriangle size={15} className="shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Scope Selection */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold text-slate-200">
              Providers to export ({selectedProviderIds.length} of {providers.length}):
            </span>
            <div className="flex items-center gap-2 text-[11px]">
              <button
                type="button"
                onClick={selectAll}
                className="text-indigo-400 hover:text-indigo-300 transition-colors"
              >
                Select all
              </button>
              <span className="text-slate-600">|</span>
              <button
                type="button"
                onClick={deselectAll}
                className="text-slate-400 hover:text-slate-300 transition-colors"
              >
                Deselect all
              </button>
            </div>
          </div>

          <div className="max-h-48 overflow-y-auto space-y-1.5 p-2 bg-slate-950/60 border border-slate-800/80 rounded-lg">
            {providers.map((p) => {
              const isSelected = selectedProviderIds.includes(p.id);
              return (
                <label
                  key={p.id}
                  className={`flex items-center justify-between p-2 rounded-lg border transition-colors cursor-pointer ${
                    isSelected
                      ? "bg-slate-900/90 border-indigo-500/40 text-slate-200"
                      : "bg-slate-900/30 border-slate-800 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleProvider(p.id)}
                      className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-950 cursor-pointer"
                    />
                    <div className="truncate">
                      <span className="font-medium text-slate-200">{p.name}</span>
                      <span className="text-[11px] text-slate-500 font-mono ml-1.5">
                        ({p.slug})
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[11px] px-2 py-0.5 bg-slate-800 text-slate-400 rounded-full flex items-center gap-1 font-mono">
                      <KeyRound size={11} className="text-indigo-400" />
                      {p.credentials_count} keys
                    </span>
                  </div>
                </label>
              );
            })}
          </div>
        </div>

        {/* Proxies toggle */}
        <label className="flex items-center gap-2.5 p-2.5 bg-slate-950/40 border border-slate-800/80 rounded-lg cursor-pointer">
          <input
            type="checkbox"
            checked={includeProxies}
            onChange={(e) => setIncludeProxies(e.target.checked)}
            className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-950 cursor-pointer"
          />
          <div>
            <div className="font-medium text-slate-200 flex items-center gap-1.5">
              <Network size={14} className="text-cyan-400" />
              Include proxy configurations
            </div>
            <div className="text-[11px] text-slate-400">
              Saves linked and configured proxies alongside credentials
            </div>
          </div>
        </label>

        {/* Encryption is mandatory because exports contain decrypted provider secrets. */}
        <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-2.5">
          <div className="font-medium text-slate-200 flex items-center gap-1.5">
            <Lock size={14} className="text-amber-400" />
            Encrypted backup (required)
          </div>
          <div className="relative">
            <input
              type={showPassphrase ? "text" : "password"}
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              placeholder="Enter at least 12 characters..."
              minLength={12}
              required
              className="w-full px-3 py-1.5 pr-9 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setShowPassphrase(!showPassphrase)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
            >
              {showPassphrase ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          <p className="text-[10px] text-amber-300/80">
            Keep this passphrase safe: it is required when importing the backup.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-lg transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={isExporting || selectedProviderIds.length === 0}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-lg shadow-xs transition-colors cursor-pointer"
          >
            {isExporting ? (
              <RefreshCw size={14} className="animate-spin" />
            ) : (
              <Download size={14} />
            )}
            <span>{isExporting ? "Generating..." : "Download file (.json)"}</span>
          </button>
        </div>
      </div>
    </Modal>
  );
};

// ==========================================
// IMPORT MODAL
// ==========================================

interface BackupImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const BackupImportModal: React.FC<BackupImportModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [fileContent, setFileContent] = useState<any>(null);
  const [isEncrypted, setIsEncrypted] = useState(false);
  const [passphrase, setPassphrase] = useState("");
  const [showPassphrase, setShowPassphrase] = useState(false);

  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewData, setPreviewData] = useState<BackupPreviewResponse | null>(null);

  // Import options
  const [updateExistingProviders, setUpdateExistingProviders] = useState(true);
  const [skipDuplicateCredentials, setSkipDuplicateCredentials] = useState(true);
  const [autoDiscoverModels, setAutoDiscoverModels] = useState(true);

  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState<BackupImportResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (isOpen) {
      resetState();
    }
  }, [isOpen]);

  const resetState = () => {
    setFile(null);
    setFileContent(null);
    setIsEncrypted(false);
    setPassphrase("");
    setShowPassphrase(false);
    setIsLoadingPreview(false);
    setPreviewData(null);
    setIsImporting(false);
    setImportResult(null);
    setErrorMsg(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    processSelectedFile(selected);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (!dropped) return;
    processSelectedFile(dropped);
  };

  const processSelectedFile = (selectedFile: File) => {
    setErrorMsg(null);
    setFile(selectedFile);
    setImportResult(null);
    setPreviewData(null);

    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const text = event.target?.result as string;
        const parsed = JSON.parse(text);
        setFileContent(parsed);

        const encrypted = parsed.encrypted === true;
        setIsEncrypted(encrypted);

        if (!encrypted) {
          setErrorMsg("Only encrypted backup files are accepted");
        }
      } catch (err: any) {
        setErrorMsg("Failed to parse JSON file: " + err.message);
      }
    };
    reader.onerror = () => {
      setErrorMsg("Failed to read file from disk");
    };
    reader.readAsText(selectedFile);
  };

  const fetchPreview = async (payload: any, pass?: string) => {
    setIsLoadingPreview(true);
    setErrorMsg(null);
    try {
      const preview = await apiRequest<BackupPreviewResponse>("/api/admin/backup/preview", {
        method: "POST",
        body: JSON.stringify({
          raw_payload: payload,
          passphrase: pass,
        }),
      });
      setPreviewData(preview);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to analyze backup file");
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const handleDecryptAndPreview = async () => {
    if (passphrase.trim().length < 12) {
      setErrorMsg("Enter the backup passphrase (at least 12 characters)");
      return;
    }
    await fetchPreview(fileContent, passphrase.trim());
  };

  const handleExecuteImport = async () => {
    if (!fileContent) return;
    setIsImporting(true);
    setErrorMsg(null);

    try {
      const payload: BackupImportRequest = {
        raw_payload: fileContent,
        passphrase: passphrase.trim(),
        update_existing_providers: updateExistingProviders,
        skip_duplicate_credentials: skipDuplicateCredentials,
        auto_discover_models: autoDiscoverModels,
      };

      const result = await apiRequest<BackupImportResponse>("/api/admin/backup/import", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setImportResult(result);
      onSuccess();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to execute import");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Import Configuration (Keys + Providers)"
      maxWidth="xl"
    >
      <div className="space-y-4 text-xs">
        {errorMsg && (
          <div className="p-2.5 bg-rose-950/60 border border-rose-800/80 rounded-lg text-rose-300 flex items-center gap-2">
            <AlertTriangle size={15} className="shrink-0 text-rose-400" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* STEP 3: RESULT REPORT */}
        {importResult ? (
          <div className="space-y-4 py-2">
            <div className="p-4 bg-emerald-950/40 border border-emerald-800/60 rounded-xl flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-emerald-900/60 border border-emerald-700/60 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
                <CheckCircle2 size={22} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-emerald-200">
                  Import Completed Successfully!
                </h4>
                <p className="text-xs text-emerald-300/80 mt-0.5">
                  Configuration has been applied. All keys are encrypted with this server's local master key.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg text-center">
                <div className="text-[11px] text-slate-400">New Providers</div>
                <div className="text-lg font-bold text-slate-100 mt-0.5">
                  {importResult.imported_providers}
                </div>
              </div>
              <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg text-center">
                <div className="text-[11px] text-slate-400">Updated Providers</div>
                <div className="text-lg font-bold text-slate-100 mt-0.5">
                  {importResult.updated_providers}
                </div>
              </div>
              <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg text-center">
                <div className="text-[11px] text-slate-400">Imported Keys</div>
                <div className="text-lg font-bold text-emerald-400 mt-0.5">
                  +{importResult.imported_credentials}
                </div>
              </div>
              <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg text-center">
                <div className="text-[11px] text-slate-400">Skipped Duplicates</div>
                <div className="text-lg font-bold text-slate-400 mt-0.5">
                  {importResult.skipped_credentials}
                </div>
              </div>
            </div>

            {importResult.discovery_triggered && (
              <div className="p-2.5 bg-indigo-950/40 border border-indigo-800/60 rounded-lg text-indigo-300 flex items-center gap-2">
                <RefreshCw size={14} className="text-indigo-400 shrink-0" />
                <span>Model discovery started for new keys (model catalog updated).</span>
              </div>
            )}

            {importResult.errors && importResult.errors.length > 0 && (
              <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-lg space-y-1">
                <div className="font-semibold text-amber-300 flex items-center gap-1.5">
                  <AlertTriangle size={14} />
                  Import Warnings:
                </div>
                <ul className="list-disc list-inside text-[11px] text-amber-200/80 space-y-0.5">
                  {importResult.errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg shadow-xs transition-colors cursor-pointer"
              >
                Close & Refresh
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* STEP 1: FILE PICKER */}
            {!previewData && (
              <div className="space-y-3">
                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className="p-8 border-2 border-dashed border-slate-700 hover:border-indigo-500 bg-slate-950/40 hover:bg-slate-900/40 rounded-xl flex flex-col items-center justify-center gap-3 text-center cursor-pointer transition-colors"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".json"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <div className="w-12 h-12 rounded-xl bg-indigo-950/60 border border-indigo-800/60 flex items-center justify-center text-indigo-400">
                    <FileUp size={24} />
                  </div>
                  <div>
                    <div className="font-semibold text-slate-200 text-sm">
                      {file ? file.name : "Select or drag & drop backup file"}
                    </div>
                    <div className="text-slate-400 text-xs mt-0.5">
                      Supports MyAIrouter .json export files
                    </div>
                  </div>
                </div>

                {/* Password input if file is encrypted */}
                {isEncrypted && (
                  <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-xl space-y-2.5">
                    <div className="flex items-center gap-2 text-amber-300 font-semibold">
                      <Lock size={15} />
                      File is password protected
                    </div>
                    <div className="relative">
                      <input
                        type={showPassphrase ? "text" : "password"}
                        value={passphrase}
                        onChange={(e) => setPassphrase(e.target.value)}
                        placeholder="Enter passphrase to decrypt..."
                        className="w-full px-3 py-1.5 pr-9 bg-slate-900 border border-slate-700 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassphrase(!showPassphrase)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                      >
                        {showPassphrase ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={handleDecryptAndPreview}
                      disabled={isLoadingPreview || !passphrase.trim()}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-medium rounded-lg transition-colors cursor-pointer"
                    >
                      {isLoadingPreview && <RefreshCw size={13} className="animate-spin" />}
                      <span>Decrypt & Inspect</span>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* STEP 2: PREVIEW & OPTIONS */}
            {previewData && (
              <div className="space-y-3.5">
                {/* File info bar */}
                <div className="flex items-center justify-between p-2.5 bg-slate-950/60 border border-slate-800 rounded-lg">
                  <div className="flex items-center gap-2">
                    <FileJson size={16} className="text-indigo-400" />
                    <span className="font-semibold text-slate-200">{file?.name}</span>
                    {previewData.exported_at && (
                      <span className="text-slate-500 text-[11px]">
                        (exported: {new Date(previewData.exported_at).toLocaleString()})
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={resetState}
                    className="text-slate-400 hover:text-slate-200 text-[11px] underline"
                  >
                    Choose different file
                  </button>
                </div>

                {/* Stat Badges */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">Providers</div>
                    <div className="text-base font-bold text-slate-100 mt-0.5">
                      {previewData.total_providers}
                    </div>
                    <div className="text-[10px] text-slate-500">
                      {previewData.new_providers} new / {previewData.existing_providers} existing
                    </div>
                  </div>

                  <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">API Keys</div>
                    <div className="text-base font-bold text-slate-100 mt-0.5">
                      {previewData.total_credentials}
                    </div>
                    <div className="text-[10px] text-emerald-400">
                      +{previewData.new_credentials} new
                    </div>
                  </div>

                  <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">Folders / Groups</div>
                    <div className="text-base font-bold text-slate-100 mt-0.5">
                      {previewData.groups.length}
                    </div>
                    <div className="text-[10px] text-slate-500 truncate" title={previewData.groups.join(", ")}>
                      {previewData.groups.slice(0, 2).join(", ") || "No groups"}
                    </div>
                  </div>

                  <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg">
                    <div className="text-[10px] text-slate-400 uppercase font-semibold">Proxies</div>
                    <div className="text-base font-bold text-slate-100 mt-0.5">
                      {previewData.total_proxies}
                    </div>
                    <div className="text-[10px] text-slate-500">in file</div>
                  </div>
                </div>

                {/* Providers List in Backup */}
                <div className="space-y-1.5">
                  <div className="text-slate-300 font-semibold text-[11px]">
                    Backup Contents:
                  </div>
                  <div className="max-h-40 overflow-y-auto space-y-1 p-2 bg-slate-950/60 border border-slate-800 rounded-lg">
                    {previewData.providers_summary.map((p, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-1.5 rounded bg-slate-900/60 border border-slate-800/80 text-[11px]"
                      >
                        <div className="flex items-center gap-2 truncate">
                          <span className="font-semibold text-slate-200">{p.name}</span>
                          <span className="text-slate-500 font-mono">({p.slug})</span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-slate-400 font-mono">
                            {p.keys_count} keys
                          </span>
                          {p.exists_in_target ? (
                            <span className="px-1.5 py-0.5 bg-amber-950/60 border border-amber-800/60 text-amber-300 rounded text-[10px]">
                              Existing
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 rounded text-[10px]">
                              New
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Import Options */}
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl space-y-2">
                  <div className="font-semibold text-slate-200 text-xs">Import Options:</div>

                  <label className="flex items-center gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={updateExistingProviders}
                      onChange={(e) => setUpdateExistingProviders(e.target.checked)}
                      className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-950 cursor-pointer"
                    />
                    <div>
                      <span className="text-slate-200 font-medium">
                        Update existing provider settings
                      </span>
                      <p className="text-[10px] text-slate-400">
                        Updates base_url, endpoints and merges group folders
                      </p>
                    </div>
                  </label>

                  <label className="flex items-center gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={skipDuplicateCredentials}
                      onChange={(e) => setSkipDuplicateCredentials(e.target.checked)}
                      className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-950 cursor-pointer"
                    />
                    <div>
                      <span className="text-slate-200 font-medium">
                        Skip duplicate credentials
                      </span>
                      <p className="text-[10px] text-slate-400">
                        Prevents creating identical API keys for the same provider
                      </p>
                    </div>
                  </label>

                  <label className="flex items-center gap-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoDiscoverModels}
                      onChange={(e) => setAutoDiscoverModels(e.target.checked)}
                      className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-950 cursor-pointer"
                    />
                    <div>
                      <span className="text-slate-200 font-medium">
                        Automatically run Model Discovery
                      </span>
                      <p className="text-[10px] text-slate-400">
                        Immediately fetches available models for new keys into the catalog
                      </p>
                    </div>
                  </label>
                </div>

                {/* Import Action Buttons */}
                <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={resetState}
                    className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-lg transition-colors cursor-pointer"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    onClick={handleExecuteImport}
                    disabled={isImporting}
                    className="flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-lg shadow-xs transition-colors cursor-pointer"
                  >
                    {isImporting ? (
                      <RefreshCw size={14} className="animate-spin" />
                    ) : (
                      <Upload size={14} />
                    )}
                    <span>{isImporting ? "Importing..." : "Import to Server"}</span>
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
};
