import React, { useEffect, useState, useMemo } from "react";
import {
  Plus,
  Play,
  RefreshCw,
  Trash2,
  Edit2,
  KeyRound,
  ShieldAlert,
  CheckCircle2,
  RotateCcw,
  Folder,
  ChevronDown,
  ChevronRight,
  Search,
  X,
  Layers,
  Filter,
  Zap,
  FolderPlus,
  FolderDown,
  GripVertical,
  Check,
  Network,
  CheckSquare,
  Ban,
  FolderInput,
  Download,
  Upload,
} from "lucide-react";
import { apiRequest } from "../api/client";
import { Credential, Provider, Proxy, CredentialTestResult } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { Modal } from "../components/Modal";
import { getCountryFlag } from "../utils/country";
import { BackupExportModal, BackupImportModal } from "../components/BackupModals";
import { useI18n } from "../i18n";

export const CredentialsPage: React.FC = () => {
  const { t } = useI18n();
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [loading, setLoading] = useState(true);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [editingCred, setEditingCred] = useState<Credential | null>(null);

  const [formProviderId, setFormProviderId] = useState<number>(1);
  const [formName, setFormName] = useState("");
  const [formGroupName, setFormGroupName] = useState("");
  const [formApiKey, setFormApiKey] = useState("");
  const [formProxyId, setFormProxyId] = useState<number | undefined>(undefined);
  const [formPriority, setFormPriority] = useState(1);
  const [formWeight, setFormWeight] = useState(1);
  const [formRpm, setFormRpm] = useState<string>("");
  const [isKeyless, setIsKeyless] = useState(false);

  const [testingId, setTestingId] = useState<number | null>(null);
  const [fetchingId, setFetchingId] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<{
    id: number;
    name?: string;
    text: string;
    ok: boolean;
    status?: string;
    latency?: number;
    modelsFound?: number;
  } | null>(null);

  useEffect(() => {
    if (!actionMessage) return;
    const timer = setTimeout(() => {
      setActionMessage(null);
    }, 7000);
    return () => clearTimeout(timer);
  }, [actionMessage]);

  // Custom / Empty Folders per provider (providerId -> folderNames[])
  const [customFolders, setCustomFolders] = useState<Record<number, string[]>>(() => {
    try {
      const saved = localStorage.getItem("myairouter_custom_folders");
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });
  const [isFolderModalOpen, setIsFolderModalOpen] = useState(false);
  const [selectedProviderForFolder, setSelectedProviderForFolder] = useState<Provider | null>(null);
  const [newFolderName, setNewFolderName] = useState("");
  const [moveSelectedToNewFolder, setMoveSelectedToNewFolder] = useState(true);

  // Drag & Drop states
  const [draggedCred, setDraggedCred] = useState<Credential | null>(null);
  const [dragOverGroupKey, setDragOverGroupKey] = useState<string | null>(null);
  const [isMoving, setIsMoving] = useState<number | null>(null);

  // Inline Key Name Editing states
  const [editingNameId, setEditingNameId] = useState<number | null>(null);
  const [editingNameValue, setEditingNameValue] = useState<string>("");
  const [savingNameId, setSavingNameId] = useState<number | null>(null);

  // Multi-Selection and Bulk Actions states
  const [selectedCredIds, setSelectedCredIds] = useState<number[]>([]);
  const [isBulkProxyModalOpen, setIsBulkProxyModalOpen] = useState(false);
  const [bulkTargetProxyId, setBulkTargetProxyId] = useState<number | null>(null);
  const [isBulkSubmitting, setIsBulkSubmitting] = useState(false);

  // Bulk Move to Folder states
  const [isBulkGroupModalOpen, setIsBulkGroupModalOpen] = useState(false);
  const [bulkGroupMode, setBulkGroupMode] = useState<"existing" | "new">("existing");
  const [bulkTargetGroupName, setBulkTargetGroupName] = useState<string>("");
  const [bulkNewGroupName, setBulkNewGroupName] = useState<string>("");
  const [isBulkGroupSubmitting, setIsBulkGroupSubmitting] = useState(false);

  const toggleSelectCred = (id: number) => {
    setSelectedCredIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectGroupCreds = (creds: Credential[]) => {
    const credIds = creds.map((c) => c.id);
    if (credIds.length === 0) return;
    const allSelected = credIds.every((id) => selectedCredIds.includes(id));
    if (allSelected) {
      setSelectedCredIds((prev) => prev.filter((id) => !credIds.includes(id)));
    } else {
      setSelectedCredIds((prev) => Array.from(new Set([...prev, ...credIds])));
    }
  };

  const selectProviderCreds = (providerId: number) => {
    const provCreds = credentials.filter((c) => c.provider_id === providerId);
    const credIds = provCreds.map((c) => c.id);
    if (credIds.length === 0) return;
    const allSelected = credIds.every((id) => selectedCredIds.includes(id));
    if (allSelected) {
      setSelectedCredIds((prev) => prev.filter((id) => !credIds.includes(id)));
    } else {
      setSelectedCredIds((prev) => Array.from(new Set([...prev, ...credIds])));
    }
  };

  const clearSelection = () => {
    setSelectedCredIds([]);
  };

  const selectAllFiltered = () => {
    const allIds = filteredCredentials.map((c) => c.id);
    setSelectedCredIds(allIds);
  };

  const openBulkProxyModal = (defaultProxyId?: number | null) => {
    if (selectedCredIds.length === 0) return;
    setBulkTargetProxyId(
      defaultProxyId !== undefined ? defaultProxyId : (proxies.length > 0 ? proxies[0].id : null)
    );
    setIsBulkProxyModalOpen(true);
  };

  const handleApplyBulkProxy = async (targetProxyId: number | null) => {
    if (selectedCredIds.length === 0) return;
    setIsBulkSubmitting(true);
    try {
      const updatedCreds = await apiRequest<Credential[]>("/api/admin/credentials/bulk-assign-proxy", {
        method: "POST",
        body: JSON.stringify({
          credential_ids: selectedCredIds,
          proxy_id: targetProxyId,
        }),
      });

      const updatedMap = new Map(updatedCreds.map((c) => [c.id, c]));
      setCredentials((prev) => prev.map((c) => updatedMap.get(c.id) || c));

      const px = proxies.find((p) => p.id === targetProxyId);
      const proxyLabel = targetProxyId && px ? `"${px.name}"` : '"DIRECT (no proxy)"';

      setActionMessage({
        id: -1,
        text: `Proxy ${proxyLabel} successfully assigned to ${selectedCredIds.length} keys!`,
        ok: true,
      });

      setSelectedCredIds([]);
      setIsBulkProxyModalOpen(false);
    } catch (err: any) {
      alert(`Error assigning proxy: ${err.message || String(err)}`);
    } finally {
      setIsBulkSubmitting(false);
    }
  };

  const selectedCredsList = useMemo(
    () => credentials.filter((c) => selectedCredIds.includes(c.id)),
    [credentials, selectedCredIds]
  );

  const selectedProviderIds = useMemo(
    () => Array.from(new Set(selectedCredsList.map((c) => c.provider_id))),
    [selectedCredsList]
  );

  const selectedProviders = useMemo(
    () => providers.filter((p) => selectedProviderIds.includes(p.id)),
    [providers, selectedProviderIds]
  );

  const availableFoldersForSelected = useMemo(() => {
    const set = new Set<string>();
    selectedProviderIds.forEach((pid) => {
      // 1. From credentials
      credentials
        .filter((c) => c.provider_id === pid && c.group_name && c.group_name.trim())
        .forEach((c) => set.add(c.group_name!.trim()));
      // 2. From customFolders
      const custom = customFolders[pid] || [];
      custom.forEach((f) => {
        if (f && f.trim()) set.add(f.trim());
      });
      // 3. From provider config
      const prov = providers.find((p) => p.id === pid);
      if (Array.isArray(prov?.configuration?.folders)) {
        prov?.configuration.folders.forEach((f: string) => {
          if (f && f.trim()) set.add(f.trim());
        });
      }
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [selectedProviderIds, credentials, customFolders, providers]);

  const openBulkGroupModal = (defaultFolder?: string) => {
    if (selectedCredIds.length === 0) return;
    const hasFolders = availableFoldersForSelected.length > 0;
    setBulkGroupMode(defaultFolder !== undefined ? "existing" : hasFolders ? "existing" : "new");
    setBulkTargetGroupName(defaultFolder ?? (hasFolders ? availableFoldersForSelected[0] : ""));
    setBulkNewGroupName("");
    setIsBulkGroupModalOpen(true);
  };

  const handleApplyBulkGroup = async (targetGroup: string, isNew: boolean) => {
    if (selectedCredIds.length === 0) return;
    const finalGroupName = targetGroup.trim();

    if (isNew) {
      if (!finalGroupName) {
        alert("Please enter a name for the new folder");
        return;
      }
      if (finalGroupName.toLowerCase() === "no group") {
        alert("Folder name cannot be \"No Group\"");
        return;
      }
    }

    setIsBulkGroupSubmitting(true);
    try {
      const updatedCreds = await apiRequest<Credential[]>("/api/admin/credentials/bulk-assign-group", {
        method: "POST",
        body: JSON.stringify({
          credential_ids: selectedCredIds,
          group_name: finalGroupName,
        }),
      });

      const updatedMap = new Map(updatedCreds.map((c) => [c.id, c]));
      setCredentials((prev) => prev.map((c) => updatedMap.get(c.id) || c));

      // If a folder name was provided, ensure it exists in customFolders and providers config
      if (finalGroupName) {
        setCustomFolders((prev) => {
          const next = { ...prev };
          selectedProviderIds.forEach((pid) => {
            const list = next[pid] || [];
            if (!list.includes(finalGroupName)) {
              next[pid] = [...list, finalGroupName];
            }
          });
          return next;
        });

        setProviders((prev) =>
          prev.map((p) => {
            if (selectedProviderIds.includes(p.id)) {
              const currentFolders: string[] = Array.isArray(p.configuration?.folders)
                ? p.configuration.folders
                : [];
              if (!currentFolders.includes(finalGroupName)) {
                return {
                  ...p,
                  configuration: {
                    ...(p.configuration || {}),
                    folders: [...currentFolders, finalGroupName],
                  },
                };
              }
            }
            return p;
          })
        );
      }

      const label = finalGroupName ? `folder "${finalGroupName}"` : '"No Group"';
      setActionMessage({
        id: -1,
        text: `Successfully moved ${selectedCredIds.length} keys to ${label}!`, 
        ok: true,
      });

      setSelectedCredIds([]);
      setIsBulkGroupModalOpen(false);
    } catch (err: any) {
      alert(`Error moving keys: ${err.message || String(err)}`);
    } finally {
      setIsBulkGroupSubmitting(false);
    }
  };

  const handleQuickMoveSelectedToGroup = async (
    targetGroup: string,
    providerId: number
  ) => {
    const credIdsInProv = selectedCredIds.filter((id) => {
      const c = credentials.find((item) => item.id === id);
      return c && c.provider_id === providerId;
    });

    if (credIdsInProv.length === 0) return;

    try {
      const updatedCreds = await apiRequest<Credential[]>("/api/admin/credentials/bulk-assign-group", {
        method: "POST",
        body: JSON.stringify({
          credential_ids: credIdsInProv,
          group_name: targetGroup,
        }),
      });

      const updatedMap = new Map(updatedCreds.map((c) => [c.id, c]));
      setCredentials((prev) => prev.map((c) => updatedMap.get(c.id) || c));

      const label = targetGroup ? `folder "${targetGroup}"` : '"No Group"';
      const prov = providers.find((p) => p.id === providerId);
      setActionMessage({
        id: providerId,
        name: prov?.name,
        text: `Moved ${credIdsInProv.length} keys to ${label}!`, 
        ok: true,
      });

      setSelectedCredIds((prev) => prev.filter((id) => !credIdsInProv.includes(id)));
    } catch (err: any) {
      alert(`Error moving keys: ${err.message || String(err)}`);
    }
  };

  useEffect(() => {
    try {
      localStorage.setItem("myairouter_custom_folders", JSON.stringify(customFolders));
    } catch {}
  }, [customFolders]);

  // Search & Filtering & Accordion states
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProviderFilter, setSelectedProviderFilter] = useState<number | "all">("all");
  const [collapsedProviders, setCollapsedProviders] = useState<Record<number, boolean>>({});

  const loadData = async () => {
    setLoading(true);
    try {
      const [c, p, px] = await Promise.all([
        apiRequest<Credential[]>("/api/admin/credentials"),
        apiRequest<Provider[]>("/api/admin/providers"),
        apiRequest<Proxy[]>("/api/admin/proxies"),
      ]);
      setCredentials(c);
      setProviders(p);
      setProxies(px);

      // Merge provider.configuration.folders into customFolders
      setCustomFolders((prev) => {
        const merged = { ...prev };
        p.forEach((prov) => {
          const configFolders = Array.isArray(prov.configuration?.folders)
            ? (prov.configuration.folders as string[])
            : [];
          const existing = merged[prov.id] || [];
          const set = new Set([...existing, ...configFolders]);
          merged[prov.id] = Array.from(set);
        });
        return merged;
      });

      if (p.length > 0 && !formProviderId) {
        setFormProviderId(p[0].id);
        setIsKeyless(p[0].auth_type === "none");
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

  const openCreateModal = (defaultProviderId?: number, defaultGroupName?: string) => {
    setEditingCred(null);
    const pid = defaultProviderId ?? (providers.length > 0 ? providers[0].id : 1);
    setFormProviderId(pid);
    const prov = providers.find((p) => p.id === pid);
    setIsKeyless(prov?.auth_type === "none");
    setFormName("");
    setFormGroupName(defaultGroupName ?? "");
    setFormApiKey("");
    setFormProxyId(undefined);
    setFormPriority(1);
    setFormWeight(1);
    setFormRpm("");
    setIsModalOpen(true);
  };

  const openEditModal = (c: Credential) => {
    setEditingCred(c);
    setFormProviderId(c.provider_id);
    setFormName(c.name);
    setFormGroupName(c.group_name ?? "");
    setFormApiKey("");
    setFormProxyId(c.proxy_id);
    setFormPriority(c.priority);
    setFormWeight(c.weight);
    setFormRpm(c.rpm_limit ? c.rpm_limit.toString() : "");
    setIsKeyless(c.masked_key?.includes("Keyless") || false);
    setIsModalOpen(true);
  };

  const handleProviderChange = (pid: number) => {
    setFormProviderId(pid);
    const p = providers.find((item) => item.id === pid);
    setIsKeyless(p?.auth_type === "none");
  };

  const existingGroupsForSelectedProvider = useMemo(() => {
    const set = new Set<string>();
    credentials
      .filter((c) => c.provider_id === formProviderId && c.group_name && c.group_name.trim())
      .forEach((c) => set.add(c.group_name!.trim()));
    const customList = customFolders[formProviderId] || [];
    customList.forEach((f) => {
      if (f && f.trim()) set.add(f.trim());
    });
    return Array.from(set).sort();
  }, [credentials, formProviderId, customFolders]);

  // Check if a proxy is already used by any key of the current provider
  const getProxyProviderUsage = (proxyId: number) => {
    const otherCreds = credentials.filter(
      (c) => c.provider_id === formProviderId && c.proxy_id === proxyId && c.id !== editingCred?.id
    );
    const isCurrent = editingCred?.proxy_id === proxyId;
    return {
      isUsed: otherCreds.length > 0,
      usedBy: otherCreds.map((c) => c.name),
      isCurrent,
    };
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const finalApiKey = isKeyless ? "no-key" : (formApiKey ? formApiKey.trim() : undefined);
      const finalGroupName = formGroupName.trim() || null;
      if (editingCred) {
        await apiRequest(`/api/admin/credentials/${editingCred.id}`, {
          method: "PUT",
          body: JSON.stringify({
            name: formName,
            group_name: finalGroupName,
            api_key: finalApiKey,
            proxy_id: formProxyId || null,
            priority: formPriority,
            weight: formWeight,
            rpm_limit: formRpm ? parseInt(formRpm) : null,
          }),
        });
      } else {
        await apiRequest("/api/admin/credentials", {
          method: "POST",
          body: JSON.stringify({
            provider_id: formProviderId,
            name: formName,
            group_name: finalGroupName,
            api_key: isKeyless ? "no-key" : formApiKey.trim(),
            proxy_id: formProxyId || null,
            priority: formPriority,
            weight: formWeight,
            rpm_limit: formRpm ? parseInt(formRpm) : null,
          }),
        });
      }
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleTest = async (id: number) => {
    const target = credentials.find((c) => c.id === id);
    const credName = target ? target.name : `Key #${id}`;
    setTestingId(id);
    setActionMessage(null);
    try {
      const res = await apiRequest<CredentialTestResult>(`/api/admin/credentials/${id}/test`, {
        method: "POST",
      });
      const newStatus = res.success
        ? "HEALTHY"
        : (res.error_category?.toUpperCase() as any) || "INVALID";

      // Update key status and models directly in local state without reloading whole catalog
      setCredentials((prev) =>
        prev.map((c) =>
          c.id === id
            ? {
                ...c,
                status: newStatus,
                last_error: res.success ? undefined : res.message,
                last_checked_at: new Date().toISOString(),
                discovered_models_count: res.models_found || c.discovered_models_count,
              }
            : c
        )
      );

      setActionMessage({
        id,
        name: credName,
        text: res.message,
        ok: res.success,
        status: newStatus,
        latency: res.latency_ms,
        modelsFound: res.models_found,
      });
    } catch (err: any) {
      setCredentials((prev) =>
        prev.map((c) =>
          c.id === id
            ? {
                ...c,
                status: "DEGRADED",
                last_error: err.message || "Connection error",
                last_checked_at: new Date().toISOString(),
              }
            : c
        )
      );
      setActionMessage({
        id,
        name: credName,
        text: err.message || "Connection error during test",
        ok: false,
        status: "DEGRADED",
      });
    } finally {
      setTestingId(null);
    }
  };

  const handleFetchModels = async (id: number) => {
    const target = credentials.find((c) => c.id === id);
    const credName = target ? target.name : `Key #${id}`;
    setFetchingId(id);
    setActionMessage(null);
    try {
      const models = await apiRequest<any[]>(`/api/admin/models/fetch/${id}`, { method: "POST" });
      setCredentials((prev) =>
        prev.map((c) =>
          c.id === id
            ? {
                ...c,
                discovered_models_count: models.length,
              }
            : c
        )
      );
      setActionMessage({
        id,
        name: credName,
        text: `Fetched ${models.length} available models!`, 
        ok: true,
        status: "HEALTHY",
        modelsFound: models.length,
      });
    } catch (err: any) {
      setActionMessage({
        id,
        name: credName,
        text: err.message || "Failed to fetch models",
        ok: false,
        status: "ERROR",
      });
    } finally {
      setFetchingId(null);
    }
  };

  const handleResetBreaker = async (id: number) => {
    const target = credentials.find((c) => c.id === id);
    const credName = target ? target.name : `Key #${id}`;
    try {
      await apiRequest(`/api/admin/credentials/${id}/reset-circuit-breaker`, { method: "POST" });
      setCredentials((prev) =>
        prev.map((c) =>
          c.id === id
            ? {
                ...c,
                status: "HEALTHY",
                last_error: undefined,
              }
            : c
        )
      );
      setActionMessage({
        id,
        name: credName,
        text: "Circuit breaker successfully reset to HEALTHY",
        ok: true,
        status: "HEALTHY",
      });
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete credential "${name}"?`)) return;
    try {
      await apiRequest(`/api/admin/credentials/${id}`, { method: "DELETE" });
      setCredentials((prev) => prev.filter((c) => c.id !== id));
      setActionMessage({
        id,
        name,
        text: `API key "${name}" successfully deleted`, 
        ok: true,
      });
    } catch (err: any) {
      alert(err.message);
    }
  };

  const openCreateFolderModal = (providerId: number) => {
    const prov = providers.find((p) => p.id === providerId) || null;
    setSelectedProviderForFolder(prov);
    setNewFolderName("");
    setMoveSelectedToNewFolder(true);
    setIsFolderModalOpen(true);
  };

  const handleCreateFolderSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProviderForFolder) return;
    const pid = selectedProviderForFolder.id;
    const trimmed = newFolderName.trim();
    if (!trimmed) return;
    if (trimmed.toLowerCase() === "no group") {
      alert("Folder name cannot be \"No Group\"");
      return;
    }

    const prov = selectedProviderForFolder;
    const existingCustom = customFolders[pid] || [];
    const existingFromCreds = credentials
      .filter((c) => c.provider_id === pid && c.group_name)
      .map((c) => c.group_name!.trim());

    if (existingCustom.includes(trimmed) || existingFromCreds.includes(trimmed)) {
      alert(`Folder "${trimmed}" already exists for this provider`);
      return;
    }

    const updatedFolders = [...existingCustom, trimmed];
    setCustomFolders((prev) => ({
      ...prev,
      [pid]: updatedFolders,
    }));

    let movedCount = 0;
    const credIdsToMove = selectedCredIds.filter((id) => {
      const c = credentials.find((item) => item.id === id);
      return c && c.provider_id === pid;
    });

    if (moveSelectedToNewFolder && credIdsToMove.length > 0) {
      try {
        const updatedCreds = await apiRequest<Credential[]>("/api/admin/credentials/bulk-assign-group", {
          method: "POST",
          body: JSON.stringify({
            credential_ids: credIdsToMove,
            group_name: trimmed,
          }),
        });
        const updatedMap = new Map(updatedCreds.map((c) => [c.id, c]));
        setCredentials((prev) => prev.map((c) => updatedMap.get(c.id) || c));
        movedCount = credIdsToMove.length;
        setSelectedCredIds((prev) => prev.filter((id) => !credIdsToMove.includes(id)));
      } catch (err) {
        console.error("Failed to move credentials to new folder:", err);
      }
    }

    try {
      const updatedConfig = { ...(prov.configuration || {}), folders: updatedFolders };
      await apiRequest(`/api/admin/providers/${pid}`, {
        method: "PUT",
        body: JSON.stringify({ configuration: updatedConfig }),
      });
      setProviders((prev) =>
        prev.map((p) => (p.id === pid ? { ...p, configuration: updatedConfig } : p))
      );
      setActionMessage({
        id: pid,
        name: prov.name,
        text:
          movedCount > 0
            ? `Folder "${trimmed}" created, and ${movedCount} keys moved into it!`
            : `Folder "${trimmed}" successfully created in ${prov.name}`, 
        ok: true,
      });
    } catch (err: any) {
      console.error("Failed to persist folder:", err);
    }

    setIsFolderModalOpen(false);
    setNewFolderName("");
  };

  const handleDeleteFolder = async (providerId: number, folderName: string) => {
    const prov = providers.find((p) => p.id === providerId);
    const credsInGroup = credentials.filter(
      (c) => c.provider_id === providerId && (c.group_name?.trim() || "") === folderName
    );

    if (credsInGroup.length > 0) {
      if (
        !confirm(
          `Folder "${folderName}" contains ${credsInGroup.length} keys. Move them to "No Group" and delete folder?`
        )
      ) {
        return;
      }
      for (const cred of credsInGroup) {
        try {
          await apiRequest(`/api/admin/credentials/${cred.id}`, {
            method: "PUT",
            body: JSON.stringify({ group_name: "" }),
          });
        } catch (err) {
          console.error("Failed to clear group on cred:", err);
        }
      }
      setCredentials((prev) =>
        prev.map((c) =>
          c.provider_id === providerId && (c.group_name?.trim() || "") === folderName
            ? { ...c, group_name: null }
            : c
        )
      );
    } else {
      if (!confirm(`Delete empty folder "${folderName}"?`)) return;
    }

    const existingCustom = customFolders[providerId] || [];
    const updatedFolders = existingCustom.filter((f) => f !== folderName);
    setCustomFolders((prev) => ({
      ...prev,
      [providerId]: updatedFolders,
    }));

    if (prov) {
      try {
        const updatedConfig = { ...(prov.configuration || {}), folders: updatedFolders };
        await apiRequest(`/api/admin/providers/${providerId}`, {
          method: "PUT",
          body: JSON.stringify({ configuration: updatedConfig }),
        });
        setProviders((prev) =>
          prev.map((p) => (p.id === providerId ? { ...p, configuration: updatedConfig } : p))
        );
      } catch (err) {
        console.error("Failed to update provider config:", err);
      }
    }

    setActionMessage({
      id: providerId,
      name: prov?.name,
      text: `Folder "${folderName}" successfully deleted`, 
      ok: true,
    });
  };

  const handleMoveCredToGroup = async (
    cred: Credential,
    targetGroupName: string,
    provider: Provider
  ) => {
    const credId = cred.id;
    const finalGroupName = targetGroupName.trim() || null;
    const fromLabel = cred.group_name || "No Group";
    const toLabel = finalGroupName || "No Group";

    if (fromLabel === toLabel) return;

    setIsMoving(credId);
    // Optimistic UI update
    setCredentials((prev) =>
      prev.map((c) => (c.id === credId ? { ...c, group_name: finalGroupName } : c))
    );

    try {
      await apiRequest<Credential>(`/api/admin/credentials/${credId}`, {
        method: "PUT",
        body: JSON.stringify({
          group_name: finalGroupName || "",
        }),
      });

      setActionMessage({
        id: credId,
        name: cred.name,
        text: `Key "${cred.name}" moved: ${fromLabel} → ${toLabel}`, 
        ok: true,
      });
    } catch (err: any) {
      // Revert optimistic update
      setCredentials((prev) =>
        prev.map((c) => (c.id === credId ? { ...c, group_name: cred.group_name } : c))
      );
      setActionMessage({
        id: credId,
        name: cred.name,
        text: `Error moving key: ${err.message}`, 
        ok: false,
      });
    } finally {
      setIsMoving(null);
      setDraggedCred(null);
      setDragOverGroupKey(null);
    }
  };

  const startEditingName = (c: Credential) => {
    setEditingNameId(c.id);
    setEditingNameValue(c.name);
  };

  const cancelEditingName = () => {
    setEditingNameId(null);
    setEditingNameValue("");
  };

  const handleSaveInlineName = async (id: number) => {
    const cred = credentials.find((c) => c.id === id);
    if (!cred) return;
    const trimmed = editingNameValue.trim();
    if (!trimmed) {
      alert("Key name cannot be empty");
      return;
    }
    if (trimmed === cred.name) {
      cancelEditingName();
      return;
    }

    const oldName = cred.name;
    setSavingNameId(id);

    // Optimistic UI update
    setCredentials((prev) =>
      prev.map((c) => (c.id === id ? { ...c, name: trimmed } : c))
    );
    setEditingNameId(null);

    try {
      await apiRequest<Credential>(`/api/admin/credentials/${id}`, {
        method: "PUT",
        body: JSON.stringify({ name: trimmed }),
      });

      setActionMessage({
        id,
        name: trimmed,
        text: `Key name updated: "${oldName}" → "${trimmed}"`, 
        ok: true,
      });
    } catch (err: any) {
      // Revert optimistic update
      setCredentials((prev) =>
        prev.map((c) => (c.id === id ? { ...c, name: oldName } : c))
      );
      setActionMessage({
        id,
        name: oldName,
        text: `Failed to update key name: ${err.message}`, 
        ok: false,
      });
    } finally {
      setSavingNameId(null);
    }
  };

  const toggleProviderCollapse = (providerId: number) => {
    setCollapsedProviders((prev) => ({
      ...prev,
      [providerId]: !prev[providerId],
    }));
  };

  const expandAll = () => {
    setCollapsedProviders({});
  };

  const collapseAll = () => {
    const allCollapsed: Record<number, boolean> = {};
    providers.forEach((p) => {
      allCollapsed[p.id] = true;
    });
    setCollapsedProviders(allCollapsed);
  };

  // Filter credentials
  const filteredCredentials = useMemo(() => {
    return credentials.filter((c) => {
      if (selectedProviderFilter !== "all" && c.provider_id !== selectedProviderFilter) {
        return false;
      }
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      return (
        c.name.toLowerCase().includes(q) ||
        (c.group_name && c.group_name.toLowerCase().includes(q)) ||
        c.provider_name.toLowerCase().includes(q) ||
        (c.proxy_name && c.proxy_name.toLowerCase().includes(q)) ||
        c.masked_key.toLowerCase().includes(q)
      );
    });
  }, [credentials, selectedProviderFilter, searchQuery]);

  // Group providers to display
  const providersToDisplay = useMemo(() => {
    let list = providers;
    if (selectedProviderFilter !== "all") {
      list = providers.filter((p) => p.id === selectedProviderFilter);
    }
    if (searchQuery.trim()) {
      const matchingProvIds = new Set(filteredCredentials.map((c) => c.provider_id));
      list = list.filter((p) => matchingProvIds.has(p.id));
    }
    // Sort: providers with credentials first (sorted by count descending), then 0-cred providers
    return [...list].sort((a, b) => {
      const aCount = credentials.filter((c) => c.provider_id === a.id).length;
      const bCount = credentials.filter((c) => c.provider_id === b.id).length;
      if (aCount > 0 && bCount === 0) return -1;
      if (aCount === 0 && bCount > 0) return 1;
      if (aCount !== bCount) return bCount - aCount;
      return a.name.localeCompare(b.name);
    });
  }, [providers, credentials, filteredCredentials, selectedProviderFilter, searchQuery]);

  // For a provider, group credentials into distinct groups (including empty folders)
  const getProviderGroups = (providerId: number) => {
    const provCreds = filteredCredentials.filter((c) => c.provider_id === providerId);
    const prov = providers.find((p) => p.id === providerId);

    const groupNamesSet = new Set<string>();

    // 1. Existing groups with credentials
    provCreds.forEach((c) => {
      const g = c.group_name?.trim();
      if (g) groupNamesSet.add(g);
    });

    // 2. Custom folders created by user (even if empty)
    const customList = customFolders[providerId] || (prov?.configuration?.folders as string[]) || [];
    customList.forEach((f) => {
      const g = f?.trim();
      if (g) groupNamesSet.add(g);
    });

    const groups: { name: string; isDefault: boolean; creds: Credential[] }[] = [];
    const sortedNames = Array.from(groupNamesSet).sort((a, b) => a.localeCompare(b));

    sortedNames.forEach((name) => {
      const credsInGroup = provCreds.filter((c) => (c.group_name?.trim() || "") === name);
      groups.push({
        name,
        isDefault: false,
        creds: credsInGroup,
      });
    });

    // Default "No Group" group
    const unassignedCreds = provCreds.filter((c) => !c.group_name || !c.group_name.trim());
    groups.push({
      name: "No Group",
      isDefault: true,
      creds: unassignedCreds,
    });

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      return groups.filter((g) => g.creds.length > 0 || g.name.toLowerCase().includes(q));
    }

    return groups;
  };

  const totalHealthy = credentials.filter((c) => c.status === "HEALTHY").length;
  const totalDistinctGroups = useMemo(() => {
    const s = new Set<string>();
    credentials.forEach((c) => {
      if (c.group_name && c.group_name.trim()) s.add(`${c.provider_id}::${c.group_name.trim()}`);
    });
    Object.entries(customFolders).forEach(([provId, folders]) => {
      folders.forEach((f) => {
        if (f && f.trim()) s.add(`${provId}::${f.trim()}`);
      });
    });
    return s.size;
  }, [credentials, customFolders]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <KeyRound size={20} className="text-indigo-400" />
            {t.credentials.title}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {t.credentials.subtitle}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setIsExportModalOpen(true)}
            className="btn-press flex items-center gap-1.5 px-3 py-2 bg-slate-900/80 hover:bg-slate-800 text-slate-200 text-xs font-medium rounded-xl transition-all cursor-pointer border border-white/[0.08] shadow-sm"
            title="Export credentials and providers to file"
          >
            <Download size={14} className="text-indigo-400" />
            <span>{t.common.export}</span>
          </button>
          <button
            onClick={() => setIsImportModalOpen(true)}
            className="btn-press flex items-center gap-1.5 px-3 py-2 bg-slate-900/80 hover:bg-slate-800 text-slate-200 text-xs font-medium rounded-xl transition-all cursor-pointer border border-white/[0.08] shadow-sm"
            title="Import credentials and providers from backup file"
          >
            <Upload size={14} className="text-emerald-400" />
            <span>{t.common.import}</span>
          </button>
          <button
            onClick={() => openCreateModal()}
            className="btn-press flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-400 hover:to-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-500/20 border border-white/10 transition-all cursor-pointer"
          >
            <Plus size={15} />
            <span>{t.credentials.addKey}</span>
          </button>
        </div>
      </div>

      {/* Overview Stats Bar & Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-3.5">
        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 flex items-center justify-between hover:border-white/[0.12] transition-all">
          <div>
            <div className="text-[11px] font-medium text-slate-400">Total API Keys</div>
            <div className="text-2xl font-bold font-mono text-slate-100 mt-0.5 tracking-tight">{credentials.length}</div>
          </div>
          <div className="text-right">
            <span className="text-xs font-mono font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2.5 py-0.5 rounded-full shadow-xs">
              {totalHealthy} Healthy
            </span>
            <div className="text-[10px] text-slate-500 mt-1">
              {credentials.length - totalHealthy > 0 ? `${credentials.length - totalHealthy} require attention` : "All healthy"}
            </div>
          </div>
        </div>

        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 flex items-center justify-between hover:border-white/[0.12] transition-all">
          <div>
            <div className="text-[11px] font-medium text-slate-400">{t.common.provider}s</div>
            <div className="text-2xl font-bold font-mono text-slate-100 mt-0.5 tracking-tight">
              {providers.filter((p) => credentials.some((c) => c.provider_id === p.id)).length}{" "}
              <span className="text-xs text-slate-500 font-normal font-sans">/ {providers.length}</span>
            </div>
          </div>
          <div className="w-8 h-8 rounded-xl bg-indigo-500/10 border border-indigo-500/25 flex items-center justify-center text-indigo-400 shadow-sm">
            <Layers size={16} />
          </div>
        </div>

        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 flex items-center justify-between hover:border-white/[0.12] transition-all">
          <div>
            <div className="text-[11px] font-medium text-slate-400">Custom Groups</div>
            <div className="text-2xl font-bold font-mono text-slate-100 mt-0.5 tracking-tight">{totalDistinctGroups}</div>
          </div>
          <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-center text-amber-400 shadow-sm">
            <Folder size={16} />
          </div>
        </div>

        {/* Quick controls: Collapse / Expand & Multi-Selection */}
        <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-4 flex flex-wrap items-center justify-between gap-2 hover:border-white/[0.12] transition-all">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400">Sections:</span>
            <button
              onClick={expandAll}
              className="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 transition-colors cursor-pointer"
            >
              Expand All
            </button>
            <button
              onClick={collapseAll}
              className="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 transition-colors cursor-pointer"
            >
              Collapse All
            </button>
          </div>

          <div className="flex items-center gap-2">
            {selectedCredIds.length > 0 && (
              <span className="text-[11px] font-medium text-indigo-300 bg-indigo-950/70 border border-indigo-800/70 px-2 py-0.5 rounded-full flex items-center gap-1">
                <CheckSquare size={12} />
                <span>Selected: {selectedCredIds.length}</span>
              </span>
            )}
            <button
              type="button"
              onClick={selectAllFiltered}
              className="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 transition-colors cursor-pointer"
              title="Select all visible keys"
            >
              Select All ({filteredCredentials.length})
            </button>
            {selectedCredIds.length > 0 && (
              <button
                type="button"
                onClick={clearSelection}
                className="px-2.5 py-1 text-[11px] bg-rose-950/40 hover:bg-rose-950/70 text-rose-300 rounded border border-rose-800/50 transition-colors cursor-pointer"
              >
                Clear Selection
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 glass-panel card-specular border border-white/[0.07] p-3.5 rounded-2xl shadow-sm">
        <div className="flex items-center gap-2.5 flex-1 flex-wrap sm:flex-nowrap">
          <div className="relative flex-1 min-w-[220px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by key name, group, provider, proxy..."
              className="w-full pl-9 pr-7 py-2 bg-slate-950/80 border border-white/[0.08] rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/30 focus:outline-none"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 cursor-pointer"
              >
                <X size={13} />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Filter size={13} className="text-slate-400" />
            <select
              value={selectedProviderFilter}
              onChange={(e) => setSelectedProviderFilter(e.target.value === "all" ? "all" : parseInt(e.target.value))}
              className="px-3 py-2 bg-slate-950/80 border border-white/[0.08] rounded-xl text-xs text-slate-200 focus:border-indigo-500 focus:outline-none cursor-pointer"
            >
              <option value="all">All Providers ({providers.length})</option>
              {providers.map((p) => {
                const count = credentials.filter((c) => c.provider_id === p.id).length;
                return (
                  <option key={p.id} value={p.id}>
                    {p.name} ({count} {count === 1 ? "key" : "keys"})
                  </option>
                );
              })}
            </select>
          </div>
        </div>

        {searchQuery && (
          <div className="text-[11px] font-mono text-slate-400 self-center px-1">
            Found: <strong className="text-indigo-300">{filteredCredentials.length}</strong> keys
          </div>
        )}
      </div>

      {/* Floating Status Notification Toast — Always visible on screen regardless of scroll position */}
      {actionMessage && (
        <div className="fixed top-16 right-4 left-4 sm:left-auto sm:right-6 sm:w-96 z-50 animate-in fade-in slide-in-from-top-2 duration-200">
          <div
            className={`p-3.5 rounded-xl border shadow-2xl backdrop-blur-md flex items-start gap-3 ${
              actionMessage.ok
                ? "bg-slate-900/95 border-emerald-500/60 text-slate-100 shadow-emerald-950/50"
                : "bg-slate-900/95 border-rose-500/60 text-slate-100 shadow-rose-950/50"
            }`}
          >
            <div className="shrink-0 mt-0.5">
              {actionMessage.ok ? (
                <CheckCircle2 size={18} className="text-emerald-400" />
              ) : (
                <ShieldAlert size={18} className="text-rose-400" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-xs text-slate-100 truncate">
                  {actionMessage.name ? actionMessage.name : `Key #${actionMessage.id}`}
                </span>
                {actionMessage.status && (
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                      actionMessage.ok
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        : "bg-rose-950 text-rose-300 border border-rose-800"
                    }`}
                  >
                    {actionMessage.status}
                  </span>
                )}
              </div>
              <div className="text-xs text-slate-300 mt-1 break-words">
                {actionMessage.text}
              </div>
              {actionMessage.latency !== undefined && actionMessage.latency > 0 && (
                <div className="text-[11px] text-slate-400 mt-1.5 flex items-center gap-2">
                  <span className="text-emerald-400 font-medium flex items-center gap-1">
                    <Zap size={12} />
                    <span>{actionMessage.latency} ms</span>
                  </span>
                  {actionMessage.modelsFound !== undefined && (
                    <span className="text-slate-400">
                      • Models: <strong className="text-slate-200">{actionMessage.modelsFound}</strong>
                    </span>
                  )}
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => setActionMessage(null)}
              className="shrink-0 text-slate-400 hover:text-slate-200 p-1 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
              aria-label="Close"
            >
              <X size={15} />
            </button>
          </div>
        </div>
      )}

      {/* Main Content: Grouped by Provider & by Groups within Provider */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400 bg-slate-900/60 border border-slate-800 rounded-xl">
            Loading credentials and providers...
          </div>
        ) : providersToDisplay.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400 bg-slate-900/60 border border-slate-800 rounded-xl space-y-2">
            <div>No credentials found matching your criteria.</div>
            {searchQuery && (
              <button
                onClick={() => {
                  setSearchQuery("");
                  setSelectedProviderFilter("all");
                }}
                className="text-indigo-400 hover:text-indigo-300 underline"
              >
                Reset filters
              </button>
            )}
          </div>
        ) : (
          providersToDisplay.map((provider) => {
            const provCreds = filteredCredentials.filter((c) => c.provider_id === provider.id);
            const totalProvCreds = credentials.filter((c) => c.provider_id === provider.id);
            const isCollapsed = !!collapsedProviders[provider.id];
            const groups = getProviderGroups(provider.id);
            const healthyInProv = provCreds.filter((c) => c.status === "HEALTHY").length;
            const provGroupsCount = new Set(
              totalProvCreds.map((c) => c.group_name?.trim()).filter(Boolean)
            ).size;

            return (
              <div
                key={provider.id}
                className="glass-card card-specular rounded-2xl border border-white/[0.07] overflow-hidden shadow-xl transition-all"
              >
                {/* Level 1: Provider Card Header */}
                <div className="p-4 bg-slate-950/60 border-b border-white/[0.07] flex items-center justify-between gap-3">
                  <div
                    onClick={() => toggleProviderCollapse(provider.id)}
                    className="flex items-center gap-2.5 cursor-pointer select-none flex-1 min-w-0"
                  >
                    <button
                      type="button"
                      className="p-1 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] transition-colors"
                      aria-label="Toggle section"
                    >
                      {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                    </button>

                    <div className="flex items-center gap-2 flex-wrap min-w-0">
                      <span className="font-bold text-slate-100 text-sm tracking-tight">{provider.name}</span>
                      <span className="font-mono text-[10px] text-slate-400 bg-white/[0.04] px-2 py-0.5 rounded-md border border-white/[0.08]">
                        {provider.slug}
                      </span>
                      <span className="text-[10px] text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded-md font-mono font-medium">
                        {provider.adapter_type}
                      </span>
                      {provider.auth_type === "none" && (
                        <span className="text-[10px] text-cyan-300 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded-md font-medium">
                          Keyless
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[11px] text-slate-300 bg-white/[0.05] border border-white/[0.08] px-2.5 py-0.5 rounded-full font-mono">
                      {totalProvCreds.length} {totalProvCreds.length === 1 ? "key" : "keys"}
                    </span>

                    {totalProvCreds.length > 0 && (
                      <span
                        className={`text-[10px] font-mono uppercase tracking-wider font-semibold px-2.5 py-0.5 rounded-full border ${
                          healthyInProv === provCreds.length
                            ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                            : "bg-amber-500/10 text-amber-300 border-amber-500/30"
                        }`}
                      >
                        {healthyInProv} / {provCreds.length} Healthy
                      </span>
                    )}

                    {provGroupsCount > 0 && (
                      <span className="text-[10px] text-amber-300 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full flex items-center gap-1 font-medium">
                        <Folder size={11} className="text-amber-400" />
                        {provGroupsCount} {provGroupsCount === 1 ? "group" : "groups"}
                      </span>
                    )}

                    {totalProvCreds.length > 0 && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          selectProviderCreds(provider.id);
                        }}
                        className={`btn-press flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-xl border transition-colors cursor-pointer ${
                          totalProvCreds.every((c) => selectedCredIds.includes(c.id))
                            ? "bg-indigo-600 text-white border-indigo-500 shadow-sm shadow-indigo-600/30"
                            : "bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 border-white/[0.08]"
                        }`}
                        title="Select all keys for this provider"
                      >
                        <CheckSquare size={13} />
                        <span>
                          {totalProvCreds.every((c) => selectedCredIds.includes(c.id))
                            ? "Deselect All"
                            : `Select All (${totalProvCreds.length})`}
                        </span>
                      </button>
                    )}

                    <button
                      onClick={() => openCreateFolderModal(provider.id)}
                      className="btn-press flex items-center gap-1.5 px-2.5 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/25 text-xs font-medium rounded-xl transition-colors cursor-pointer"
                      title={`Create new folder inside ${provider.name}`}
                    >
                      <FolderPlus size={13} />
                      <span>New Folder</span>
                    </button>

                    <button
                      onClick={() => openCreateModal(provider.id)}
                      className="btn-press flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-indigo-600/25 cursor-pointer ml-1"
                      title={`Add key for ${provider.name}`}
                    >
                      <Plus size={13} />
                      <span>{t.credentials.addKey}</span>
                    </button>
                  </div>
                </div>

                {/* Level 2: Body (Groups inside this Provider) */}
                {!isCollapsed && (
                  <div className="p-3.5 space-y-4 bg-slate-900/40">
                    {provCreds.length === 0 && (customFolders[provider.id] || []).length === 0 ? (
                      <div className="p-6 text-center text-slate-400 text-xs border border-dashed border-slate-800 rounded-lg space-y-2">
                        <div>No keys or folders added for <strong>{provider.name}</strong> yet.</div>
                        <div className="flex items-center justify-center gap-2 pt-1">
                          <button
                            onClick={() => openCreateFolderModal(provider.id)}
                            className="inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-500/30 rounded-lg transition-colors cursor-pointer"
                          >
                            <FolderPlus size={12} />
                            Create Folder
                          </button>
                          <button
                            onClick={() => openCreateModal(provider.id)}
                            className="inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-lg transition-colors cursor-pointer"
                          >
                            <Plus size={12} />
                            Add First Key
                          </button>
                        </div>
                      </div>
                    ) : (
                      groups.map((group) => {
                        const groupKey = `${provider.id}::${group.name}`;
                        const isDragOver = dragOverGroupKey === groupKey;
                        const canDrop =
                          draggedCred &&
                          draggedCred.provider_id === provider.id &&
                          (draggedCred.group_name?.trim() || "") !== (group.isDefault ? "" : group.name);

                        return (
                          <div
                            key={group.name}
                            onDragOver={(e) => {
                              if (draggedCred && draggedCred.provider_id === provider.id) {
                                e.preventDefault();
                                e.dataTransfer.dropEffect = "move";
                                if (dragOverGroupKey !== groupKey) {
                                  setDragOverGroupKey(groupKey);
                                }
                              }
                            }}
                            onDragLeave={(e) => {
                              if (e.currentTarget.contains(e.relatedTarget as Node)) return;
                              if (dragOverGroupKey === groupKey) {
                                setDragOverGroupKey(null);
                              }
                            }}
                            onDrop={async (e) => {
                              e.preventDefault();
                              setDragOverGroupKey(null);
                              if (!draggedCred) return;
                              if (draggedCred.provider_id !== provider.id) return;
                              const targetGroup = group.isDefault ? "" : group.name;

                              const selectedInProv = selectedCredIds.filter((id) => {
                                const c = credentials.find((item) => item.id === id);
                                return c && c.provider_id === provider.id;
                              });

                              if (selectedInProv.length > 1 && selectedInProv.includes(draggedCred.id)) {
                                try {
                                  setIsMoving(draggedCred.id);
                                  const updatedCreds = await apiRequest<Credential[]>("/api/admin/credentials/bulk-assign-group", {
                                    method: "POST",
                                    body: JSON.stringify({
                                      credential_ids: selectedInProv,
                                      group_name: targetGroup,
                                    }),
                                  });
                                  const updatedMap = new Map(updatedCreds.map((c) => [c.id, c]));
                                  setCredentials((prev) => prev.map((c) => updatedMap.get(c.id) || c));
                                  setActionMessage({
                                    id: provider.id,
                                    name: provider.name,
                                    text: `Moved ${selectedInProv.length} selected keys to ${targetGroup ? `folder "${targetGroup}"` : '"No Group"'}!`, 
                                    ok: true,
                                  });
                                  setSelectedCredIds((prev) => prev.filter((id) => !selectedInProv.includes(id)));
                                } catch (err: any) {
                                  alert(`Move error: ${err.message || String(err)}`);
                                } finally {
                                  setIsMoving(null);
                                  setDraggedCred(null);
                                }
                              } else {
                                await handleMoveCredToGroup(draggedCred, targetGroup, provider);
                              }
                            }}
                            className={`rounded-xl overflow-hidden transition-all duration-150 border ${
                              isDragOver && canDrop
                                ? "border-indigo-500 ring-2 ring-indigo-500/50 bg-indigo-950/50 shadow-lg shadow-indigo-950/50"
                                : isDragOver && !canDrop
                                ? "border-slate-700 bg-slate-900/50"
                                : "border-white/[0.06] bg-slate-950/50 backdrop-blur-xs"
                            }`}
                          >
                            {/* Drag and Drop Hover Banner */}
                            {isDragOver && canDrop && (
                              <div className="bg-indigo-600/30 border-b border-indigo-500/50 px-3 py-1.5 flex items-center justify-center gap-2 text-xs font-medium text-indigo-200 animate-pulse">
                                <FolderDown size={14} className="text-indigo-400" />
                                <span>
                                  {selectedCredIds.includes(draggedCred.id) &&
                                  selectedCredIds.filter((id) => {
                                    const c = credentials.find((item) => item.id === id);
                                    return c && c.provider_id === provider.id;
                                  }).length > 1 ? (
                                    <>
                                      Release mouse to move all{" "}
                                      <strong>
                                        {
                                          selectedCredIds.filter((id) => {
                                            const c = credentials.find((item) => item.id === id);
                                            return c && c.provider_id === provider.id;
                                          }).length
                                        }
                                      </strong>{" "}
                                      selected keys to {group.isDefault ? '"No Group"' : `folder "${group.name}"`}
                                    </>
                                  ) : (
                                    <>
                                      Release mouse to move <strong>"{draggedCred.name}"</strong> to{" "}
                                      {group.isDefault ? '"No Group"' : `folder "${group.name}"`}
                                    </>
                                  )}
                                </span>
                              </div>
                            )}

                            {/* Group Subheader */}
                            <div className="px-3.5 py-2.5 bg-slate-950/80 border-b border-white/[0.06] flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Folder
                                  size={14}
                                  className={group.isDefault ? "text-slate-400" : "text-amber-400"}
                                />
                                <span
                                  className={`text-xs font-semibold tracking-tight ${
                                    group.isDefault ? "text-slate-300" : "text-amber-200"
                                  }`}
                                >
                                  {group.name}
                                </span>
                                <span className="text-[10px] text-slate-400 font-mono bg-white/[0.04] px-2 py-0.5 rounded-md border border-white/[0.06]">
                                  {group.creds.length} {group.creds.length === 1 ? "key" : "keys"}
                                </span>
                                {group.creds.length === 0 && (
                                  <span className="text-[9px] text-amber-300/90 font-mono bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-md">
                                    Empty folder
                                  </span>
                                )}
                                {!group.isDefault && (
                                  <span className="text-[9px] text-blue-300 font-mono bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 rounded-md">
                                    Target Fallback Group
                                  </span>
                                )}
                              </div>

                              <div className="flex items-center gap-1.5">
                                {/* Quick move selected keys of this provider into this group */}
                                {selectedCredIds.some((id) => {
                                  const c = credentials.find((item) => item.id === id);
                                  return (
                                    c &&
                                    c.provider_id === provider.id &&
                                    (c.group_name?.trim() || "") !== (group.isDefault ? "" : group.name)
                                  );
                                }) && (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      handleQuickMoveSelectedToGroup(
                                        group.isDefault ? "" : group.name,
                                        provider.id
                                      )
                                    }
                                    className="btn-press text-[11px] text-amber-300 hover:text-amber-200 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 flex items-center gap-1 transition-colors px-2.5 py-1 rounded-lg cursor-pointer font-medium"
                                    title={`Move selected keys here (${
                                      selectedCredIds.filter((id) => {
                                        const c = credentials.find((item) => item.id === id);
                                        return (
                                          c &&
                                          c.provider_id === provider.id &&
                                          (c.group_name?.trim() || "") !== (group.isDefault ? "" : group.name)
                                        );
                                      }).length
                                    })`}
                                  >
                                    <FolderDown size={12} />
                                    <span>
                                      Here (
                                      {
                                        selectedCredIds.filter((id) => {
                                          const c = credentials.find((item) => item.id === id);
                                          return (
                                            c &&
                                            c.provider_id === provider.id &&
                                            (c.group_name?.trim() || "") !== (group.isDefault ? "" : group.name)
                                          );
                                        }).length
                                      }
                                      )
                                    </span>
                                  </button>
                                )}

                                {!group.isDefault && (
                                  <button
                                    onClick={() => handleDeleteFolder(provider.id, group.name)}
                                    className="btn-press text-[11px] text-slate-500 hover:text-rose-400 p-1.5 rounded-lg hover:bg-white/[0.06] transition-colors cursor-pointer"
                                    title={group.creds.length === 0 ? "Delete empty folder" : `Delete folder "${group.name}"`}
                                  >
                                    <Trash2 size={12} />
                                  </button>
                                )}
                                <button
                                  onClick={() => openCreateModal(provider.id, group.isDefault ? undefined : group.name)}
                                  className="btn-press text-[11px] text-indigo-300 hover:text-indigo-200 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 flex items-center gap-1 transition-colors px-2.5 py-1 rounded-lg cursor-pointer font-medium"
                                  title={`Add key to group "${group.name}"`}
                                >
                                  <Plus size={12} />
                                  <span>Add Key Here</span>
                                </button>
                              </div>
                            </div>

                            {/* Group Content: Table or Empty Folder Drop Zone */}
                            {group.creds.length === 0 ? (
                              <div
                                className={`p-5 text-center border border-dashed rounded-lg m-2.5 transition-colors ${
                                  isDragOver && canDrop
                                    ? "border-indigo-400 bg-indigo-950/50 text-indigo-200"
                                    : "border-slate-800/80 bg-slate-950/20 text-slate-500 hover:border-slate-700"
                                }`}
                              >
                                <div className="flex flex-col items-center gap-1.5">
                                  <FolderDown
                                    size={20}
                                    className={isDragOver && canDrop ? "text-indigo-400 animate-bounce" : "text-slate-600"}
                                  />
                                  <div className="text-xs font-medium text-slate-400">
                                    {isDragOver && canDrop
                                      ? "Release mouse to move key here"
                                      : group.isDefault
                                      ? "All keys are organized into folders"
                                      : "Folder is empty"}
                                  </div>
                                  <div className="text-[11px] text-slate-500">
                                    Drag any key here or click{" "}
                                    <button
                                      onClick={() => openCreateModal(provider.id, group.isDefault ? undefined : group.name)}
                                      className="text-indigo-400 hover:underline cursor-pointer"
                                    >
                                      "Add Key Here"
                                    </button>
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse text-xs">
                                  <thead>
                                    <tr className="border-b border-slate-800/60 bg-slate-950/30 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                                      <th className="py-2.5 px-3 w-8 text-center">
                                        <input
                                          type="checkbox"
                                          checked={
                                            group.creds.length > 0 &&
                                            group.creds.every((c) => selectedCredIds.includes(c.id))
                                          }
                                          ref={(el) => {
                                            if (el) {
                                              const some = group.creds.some((c) => selectedCredIds.includes(c.id));
                                              const all =
                                                group.creds.length > 0 &&
                                                group.creds.every((c) => selectedCredIds.includes(c.id));
                                              el.indeterminate = some && !all;
                                            }
                                          }}
                                          onChange={() => selectGroupCreds(group.creds)}
                                          className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 cursor-pointer w-3.5 h-3.5"
                                          title="Select all keys in this folder"
                                        />
                                      </th>
                                      <th className="py-2.5 px-3.5">Key</th>
                                      <th className="py-2.5 px-3.5">Masked Key</th>
                                      <th className="py-2.5 px-3.5">{t.credentials.proxy}</th>
                                      <th className="py-2.5 px-3.5">{t.common.status}</th>
                                      <th className="py-2.5 px-3.5">Models</th>
                                      <th className="py-2.5 px-3.5 text-right">{t.common.actions}</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-800/50 text-slate-300">
                                    {group.creds.map((c) => (
                                      <tr
                                        key={c.id}
                                        draggable={editingNameId !== c.id}
                                        onDragStart={(e) => {
                                          if (editingNameId === c.id) return;
                                          setDraggedCred(c);
                                          e.dataTransfer.setData(
                                            "application/json",
                                            JSON.stringify({ credId: c.id, providerId: c.provider_id })
                                          );
                                          e.dataTransfer.effectAllowed = "move";
                                        }}
                                        onDragEnd={() => {
                                          setDraggedCred(null);
                                          setDragOverGroupKey(null);
                                        }}
                                        className={`transition-colors select-none ${
                                          draggedCred?.id === c.id
                                            ? "opacity-30 bg-indigo-950/40"
                                            : isMoving === c.id
                                            ? "opacity-60 bg-amber-950/30 animate-pulse"
                                            : selectedCredIds.includes(c.id)
                                            ? "bg-indigo-950/30"
                                            : "hover:bg-slate-800/30"
                                        }`}
                                      >
                                        <td
                                          className="py-2.5 px-3 w-8 text-center"
                                          onClick={(e) => e.stopPropagation()}
                                        >
                                          <input
                                            type="checkbox"
                                            checked={selectedCredIds.includes(c.id)}
                                            onChange={() => toggleSelectCred(c.id)}
                                            className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 cursor-pointer w-3.5 h-3.5"
                                            title="Select key for batch actions"
                                          />
                                        </td>
                                        <td className="py-2.5 px-3.5 font-medium text-slate-100">
                                          <div className="flex items-center gap-2">
                                            <div
                                              className="cursor-grab active:cursor-grabbing text-slate-500 hover:text-indigo-400 p-0.5 rounded hover:bg-slate-800 transition-colors"
                                              title="Drag key to move to another folder"
                                            >
                                              <GripVertical size={14} />
                                            </div>
                                            <KeyRound size={13} className="text-indigo-400 shrink-0" />
                                            <div>
                                              {editingNameId === c.id ? (
                                                <div
                                                  className="flex items-center gap-1.5 my-0.5"
                                                  onClick={(e) => e.stopPropagation()}
                                                  onMouseDown={(e) => e.stopPropagation()}
                                                >
                                                  <input
                                                    type="text"
                                                    autoFocus
                                                    value={editingNameValue}
                                                    onChange={(e) => setEditingNameValue(e.target.value)}
                                                    onKeyDown={(e) => {
                                                      if (e.key === "Enter") {
                                                        e.preventDefault();
                                                        handleSaveInlineName(c.id);
                                                      } else if (e.key === "Escape") {
                                                        e.preventDefault();
                                                        cancelEditingName();
                                                      }
                                                    }}
                                                    className="px-2 py-0.5 bg-slate-950 border border-indigo-500 rounded text-xs text-slate-100 font-semibold focus:outline-none focus:ring-1 focus:ring-indigo-500 min-w-[140px] max-w-[220px]"
                                                    placeholder="Key name..."
                                                  />
                                                  <button
                                                    type="button"
                                                    disabled={savingNameId === c.id}
                                                    onClick={() => handleSaveInlineName(c.id)}
                                                    className="p-1 bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-300 border border-emerald-500/40 rounded transition-colors cursor-pointer disabled:opacity-50"
                                                    title="Save name (Enter)"
                                                  >
                                                    <Check size={12} />
                                                  </button>
                                                  <button
                                                    type="button"
                                                    onClick={cancelEditingName}
                                                    className="p-1 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700 rounded transition-colors cursor-pointer"
                                                    title="Cancel (Esc)"
                                                  >
                                                    <X size={12} />
                                                  </button>
                                                </div>
                                              ) : (
                                                <div className="font-semibold text-slate-100 flex items-center gap-1.5 group/name">
                                                  <span
                                                    onDoubleClick={() => startEditingName(c)}
                                                    className="cursor-pointer hover:text-indigo-300 transition-colors"
                                                    title="Double click to rename inline"
                                                  >
                                                    {c.name}
                                                  </span>
                                                  <button
                                                    type="button"
                                                    onClick={() => startEditingName(c)}
                                                    className="opacity-0 group-hover/name:opacity-100 text-slate-500 hover:text-indigo-300 p-0.5 rounded transition-all cursor-pointer"
                                                    title="Rename key inline"
                                                  >
                                                    <Edit2 size={11} />
                                                  </button>
                                                  {c.group_name && (
                                                    <span className="text-[10px] text-amber-300/90 font-normal">
                                                      [{c.group_name}]
                                                    </span>
                                                  )}
                                                </div>
                                              )}
                                              <div className="text-[10px] text-slate-400">
                                                Priority {c.priority} • Weight {c.weight}
                                                {c.rpm_limit ? ` • ${c.rpm_limit} RPM` : ""}
                                              </div>
                                            </div>
                                          </div>
                                        </td>

                                    <td className="py-2.5 px-3.5 font-mono text-[11px] text-slate-300">
                                      {c.masked_key}
                                    </td>

                                    <td className="py-2.5 px-3.5 font-mono text-[11px]">
                                      {c.proxy_name ? (
                                        <div className="flex items-center gap-1.5 flex-wrap">
                                          <span className="text-indigo-300 bg-indigo-950/60 border border-indigo-800/60 px-1.5 py-0.5 rounded text-[10px] flex items-center gap-1">
                                            {(() => {
                                              const px = proxies.find((p) => p.id === c.proxy_id);
                                              return px ? (
                                                <span role="img" aria-label={px.country || "flag"}>
                                                  {getCountryFlag(px.country_code)}
                                                </span>
                                              ) : null;
                                            })()}
                                            <span>{c.proxy_name}</span>
                                          </span>
                                          {c.proxy_id &&
                                            credentials.some(
                                              (other) =>
                                                other.id !== c.id &&
                                                other.provider_id === c.provider_id &&
                                                other.proxy_id === c.proxy_id
                                            ) && (
                                              <span
                                                className="text-[9px] text-rose-300 bg-rose-950/80 border border-rose-800/80 px-1.5 py-0.5 rounded font-sans"
                                                title="This proxy is shared with another key on this provider"
                                              >
                                                🔴 shared
                                              </span>
                                            )}
                                        </div>
                                      ) : (
                                        <span className="text-slate-500">DIRECT</span>
                                      )}
                                    </td>

                                    <td className="py-2.5 px-3.5">
                                      <div className="flex flex-col gap-0.5">
                                        <div className="flex items-center gap-1.5 flex-wrap">
                                          <StatusBadge status={c.status} />
                                          {actionMessage?.id === c.id && actionMessage.latency !== undefined && (
                                            <span className="text-[10px] text-emerald-400 font-mono font-medium flex items-center gap-0.5">
                                              <Zap size={10} />
                                              {actionMessage.latency}ms
                                            </span>
                                          )}
                                        </div>
                                        {c.last_error && (
                                          <span
                                            className="text-[10px] text-rose-400 truncate max-w-xs"
                                            title={c.last_error}
                                          >
                                            {c.last_error}
                                          </span>
                                        )}
                                      </div>
                                    </td>

                                    <td className="py-2.5 px-3.5 font-medium text-slate-200">
                                      <span className="bg-slate-800 px-2 py-0.5 rounded-full text-[11px]">
                                        {c.discovered_models_count}
                                      </span>
                                    </td>

                                     <td className="py-2.5 px-3.5 text-right space-x-1 whitespace-nowrap">
                                       <button
                                         onClick={() => handleTest(c.id)}
                                         disabled={testingId === c.id}
                                         className="btn-press px-2.5 py-1 bg-white/[0.05] hover:bg-white/[0.09] text-slate-200 text-[11px] font-medium rounded-lg border border-white/10 transition-colors inline-flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                                         title="Test connection & key"
                                       >
                                         <Play
                                           size={11}
                                           className={testingId === c.id ? "animate-spin text-indigo-400" : ""}
                                         />
                                         {testingId === c.id ? "Testing..." : t.common.test}
                                       </button>
                                       <button
                                         onClick={() => handleFetchModels(c.id)}
                                         disabled={fetchingId === c.id}
                                         className="btn-press px-2.5 py-1 bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 border border-indigo-500/30 text-[11px] font-medium rounded-lg transition-colors inline-flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                                         title="Fetch provider models using this key"
                                       >
                                         <RefreshCw
                                           size={11}
                                           className={fetchingId === c.id ? "animate-spin" : ""}
                                         />
                                         Models
                                       </button>
                                       {c.status !== "HEALTHY" && (
                                         <button
                                           onClick={() => handleResetBreaker(c.id)}
                                           className="btn-press p-1.5 text-amber-400 hover:text-amber-300 hover:bg-amber-500/10 rounded-lg transition-colors cursor-pointer"
                                           title="Reset circuit breaker to HEALTHY"
                                         >
                                           <RotateCcw size={13} />
                                         </button>
                                       )}
                                       <button
                                         onClick={() => openEditModal(c)}
                                         className="btn-press p-1.5 text-slate-400 hover:text-indigo-300 hover:bg-white/[0.06] rounded-lg transition-colors cursor-pointer"
                                         title="Edit key and folder"
                                       >
                                         <Edit2 size={13} />
                                       </button>
                                       <button
                                         onClick={() => handleDelete(c.id, c.name)}
                                         className="btn-press p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors cursor-pointer"
                                         title="Delete key"
                                       >
                                         <Trash2 size={13} />
                                       </button>
                                     </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Modal: Add / Edit Credential */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingCred ? t.credentials.editKey : t.credentials.addKey}
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">{t.common.provider}</label>
            <select
              value={formProviderId}
              onChange={(e) => handleProviderChange(parseInt(e.target.value))}
              disabled={!!editingCred}
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none disabled:opacity-60"
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.slug})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">{t.credentials.keyName}</label>
            <input
              type="text"
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g.: OpenAI Primary Key 1 or Gemini Team Account"
              className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
            />
          </div>

          {/* Group Field with Autocomplete & Suggestions */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-medium text-slate-300">
                Key Group (Folder inside Provider)
              </label>
              <span className="text-[10px] text-slate-400">Optional</span>
            </div>
            <div className="relative">
              <input
                type="text"
                value={formGroupName}
                onChange={(e) => setFormGroupName(e.target.value)}
                placeholder="e.g.: Primary, Fallback, Team A, Account 2..."
                list="group-name-suggestions"
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
              <datalist id="group-name-suggestions">
                {existingGroupsForSelectedProvider.map((g) => (
                  <option key={g} value={g} />
                ))}
              </datalist>
            </div>
            {existingGroupsForSelectedProvider.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap mt-1.5">
                <span className="text-[10px] text-slate-400">Existing Groups:</span>
                {existingGroupsForSelectedProvider.map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setFormGroupName(g)}
                    className={`text-[10px] px-2 py-0.5 rounded border transition-colors flex items-center gap-1 ${
                      formGroupName === g
                        ? "bg-indigo-600 text-white border-indigo-500 font-medium"
                        : "bg-slate-900 text-slate-300 border-slate-700 hover:border-slate-500 hover:text-white"
                    }`}
                  >
                    <Folder size={10} className={formGroupName === g ? "text-indigo-200" : "text-amber-400"} />
                    <span>{g}</span>
                  </button>
                ))}
                {formGroupName && (
                  <button
                    type="button"
                    onClick={() => setFormGroupName("")}
                    className="text-[10px] text-slate-400 hover:text-rose-300 underline ml-1 cursor-pointer"
                  >
                    Clear
                  </button>
                )}
              </div>
            )}
            <p className="text-[10px] text-slate-400 mt-1">
              Group keys under the same provider to route requests to a specific key pool in Fallback chains.
            </p>
          </div>

          {/* Keyless Toggle Checkbox */}
          <div className="flex items-center gap-2 py-0.5">
            <label className="flex items-center gap-2 text-xs text-indigo-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={isKeyless}
                onChange={(e) => setIsKeyless(e.target.checked)}
                className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-0 cursor-pointer"
              />
              <span>Keyless Access (Public Gateway, Kilo AI, Ollama, vLLM)</span>
            </label>
          </div>

          {!isKeyless ? (
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                {editingCred ? "API Key Secret (leave empty to keep current)" : t.credentials.apiKey}
              </label>
              <input
                type="password"
                required={!editingCred && !isKeyless}
                value={formApiKey}
                onChange={(e) => setFormApiKey(e.target.value)}
                placeholder="sk-... or AIzaSy..."
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none font-mono"
              />
              {formApiKey.trim().startsWith("http") && (
                <p className="text-[11px] text-amber-400 mt-1 font-sans">
                  ⚠️ Warning: this looks like a URL! Enter your secret token / API key here, not the Base URL.
                </p>
              )}
              <p className="text-[11px] text-slate-400 mt-1">
                API key is encrypted with AES/Fernet master key and securely stored.
              </p>
            </div>
          ) : (
            <div className="p-3 bg-indigo-950/40 border border-indigo-800/60 rounded-lg text-xs text-indigo-200">
              <div className="font-semibold flex items-center gap-1.5 text-indigo-300">
                <CheckCircle2 size={14} className="text-emerald-400" />
                No API Key Required
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                This service runs without authentication. Router sends upstream requests without an Authorization header.
              </p>
            </div>
          )}

          {/* Assigned Proxy Selector with Provider Usage Indicator */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-medium text-slate-300">
                Assigned Proxy
              </label>
              {formProxyId ? (
                (() => {
                  const usage = getProxyProviderUsage(formProxyId);
                  return (
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded border flex items-center gap-1 ${
                        usage.isUsed
                          ? "bg-rose-950/80 text-rose-300 border-rose-800/80"
                          : "bg-emerald-950/80 text-emerald-300 border-emerald-800/80"
                      }`}
                    >
                      {usage.isUsed ? "🔴 YES (In use on this provider)" : "🟢 NO (Free for provider)"}
                    </span>
                  );
                })()
              ) : null}
            </div>

            <select
              value={formProxyId ?? ""}
              onChange={(e) => setFormProxyId(e.target.value ? parseInt(e.target.value) : undefined)}
              className={`w-full px-3 py-2 bg-slate-950 border rounded-lg text-xs focus:outline-none transition-colors ${
                formProxyId && getProxyProviderUsage(formProxyId).isUsed
                  ? "border-rose-600/80 text-rose-200 focus:border-rose-500"
                  : formProxyId
                  ? "border-emerald-600/80 text-emerald-200 focus:border-emerald-500"
                  : "border-slate-800 text-slate-100 focus:border-indigo-500"
              }`}
            >
              <option value="" className="text-slate-400 bg-slate-950">
                Direct (No Proxy) — direct connection
              </option>
              {proxies.map((px) => {
                const usage = getProxyProviderUsage(px.id);
                return (
                  <option
                    key={px.id}
                    value={px.id}
                    style={{
                      color: usage.isUsed ? "#f87171" : "#4ade80",
                      backgroundColor: "#020617",
                    }}
                    className={usage.isUsed ? "text-rose-400 bg-slate-950 font-medium" : "text-emerald-400 bg-slate-950 font-medium"}
                  >
                    {usage.isUsed ? "🔴 YES" : "🟢 NO"} — {getCountryFlag(px.country_code)} {px.name} ({px.scheme.toUpperCase()}://{px.host}:{px.port}){px.country ? ` [${px.country}]` : ""}
                    {usage.isUsed
                      ? ` — In use (${usage.usedBy.join(", ")})`
                      : usage.isCurrent
                      ? " — Current key"
                      : " — Available"}
                  </option>
                );
              })}
            </select>

            {/* Status explanation badge under the select */}
            {formProxyId ? (
              (() => {
                const usage = getProxyProviderUsage(formProxyId);
                const currentProvName = providers.find((p) => p.id === formProviderId)?.name || "this provider";
                const selectedPx = proxies.find((p) => p.id === formProxyId);
                const otherProviders = (selectedPx?.assigned_providers || []).filter((prov) => prov !== currentProvName);
                return usage.isUsed ? (
                  <div className="mt-1.5 flex flex-col gap-1 text-[11px] text-rose-300 bg-rose-950/40 border border-rose-900/60 rounded-md px-2.5 py-1.5 leading-tight">
                    <div className="flex items-start gap-1.5">
                      <span className="shrink-0 mt-0.5">🔴</span>
                      <span>
                        <strong>Already assigned on {currentProvName}:</strong> proxy is in use on key <em>"{usage.usedBy.join('", "')}"</em>.
                      </span>
                    </div>
                    {otherProviders.length > 0 && (
                      <div className="text-[10px] text-slate-400 pl-5">
                        Also used on other providers: {otherProviders.join(", ")}.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="mt-1.5 flex flex-col gap-1 text-[11px] text-emerald-300 bg-emerald-950/30 border border-emerald-900/50 rounded-md px-2.5 py-1.5 leading-tight">
                    <div className="flex items-center gap-1.5">
                      <span className="shrink-0">🟢</span>
                      <span>
                        <strong>Available on provider:</strong> proxy is free for {currentProvName} keys.
                      </span>
                    </div>
                    {otherProviders.length > 0 && (
                      <div className="text-[10px] text-slate-400 pl-5">
                        Used on other providers: {otherProviders.join(", ")}.
                      </div>
                    )}
                  </div>
                );
              })()
            ) : (
              <p className="text-[10px] text-slate-500 mt-1">
                Direct connection to API without using a proxy server.
              </p>
            )}
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Priority Order</label>
              <input
                type="number"
                value={formPriority}
                onChange={(e) => setFormPriority(parseInt(e.target.value) || 1)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Weight</label>
              <input
                type="number"
                value={formWeight}
                onChange={(e) => setFormWeight(parseInt(e.target.value) || 1)}
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">RPM Limit</label>
              <input
                type="number"
                value={formRpm}
                onChange={(e) => setFormRpm(e.target.value)}
                placeholder="e.g.: 60"
                className="w-full px-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium cursor-pointer"
            >
              {t.common.cancel}
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
            >
              {editingCred ? t.common.save : t.credentials.addKey}
            </button>
          </div>
        </form>
      </Modal>

      {/* Modal: Create Folder */}
      <Modal
        isOpen={isFolderModalOpen}
        onClose={() => setIsFolderModalOpen(false)}
        title={`Create new folder for "${selectedProviderForFolder?.name || "provider"}"`}
        maxWidth="md"
      >
        <form onSubmit={handleCreateFolderSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Folder / Group Name
            </label>
            <input
              type="text"
              required
              autoFocus
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="e.g.: Production, Team-A, Fallback-Keys, Backup"
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-amber-500 focus:outline-none"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              You can drag & drop keys into this folder and target it in Fallback routing chains.
            </p>
          </div>

          <div>
            <label className="block text-[11px] text-slate-400 mb-1.5">Quick Templates:</label>
            <div className="flex flex-wrap gap-1.5">
              {["Production", "Staging", "Team-A", "Backup", "Fast-Tier", "Free-Tier"].map((tmpl) => (
                <button
                  key={tmpl}
                  type="button"
                  onClick={() => setNewFolderName(tmpl)}
                  className="text-[10px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors cursor-pointer"
                >
                  + {tmpl}
                </button>
              ))}
            </div>
          </div>

          {/* Option to immediately move selected keys of this provider into this new folder */}
          {selectedProviderForFolder &&
            selectedCredIds.filter((id) => {
              const c = credentials.find((item) => item.id === id);
              return c && c.provider_id === selectedProviderForFolder.id;
            }).length > 0 && (
              <div className="p-2.5 bg-indigo-950/40 border border-indigo-500/40 rounded-lg flex items-center gap-2">
                <input
                  type="checkbox"
                  id="moveSelectedCheckbox"
                  checked={moveSelectedToNewFolder}
                  onChange={(e) => setMoveSelectedToNewFolder(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 cursor-pointer w-4 h-4"
                />
                <label htmlFor="moveSelectedCheckbox" className="text-xs text-indigo-200 cursor-pointer">
                  Immediately move selected keys (
                  <strong className="text-indigo-300 font-bold">
                    {
                      selectedCredIds.filter((id) => {
                        const c = credentials.find((item) => item.id === id);
                        return c && c.provider_id === selectedProviderForFolder.id;
                      }).length
                    }
                  </strong>
                  ) into this new folder
                </label>
              </div>
            )}

          <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={() => setIsFolderModalOpen(false)}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium cursor-pointer"
            >
              {t.common.cancel}
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer flex items-center gap-1.5"
            >
              <FolderPlus size={14} />
              <span>Create Folder</span>
            </button>
          </div>
        </form>
      </Modal>

      {/* Floating Bulk Action Bar */}
      {selectedCredIds.length > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-slate-900/95 border border-indigo-500/60 shadow-2xl shadow-indigo-950/80 rounded-2xl px-4 py-3 backdrop-blur-md flex items-center gap-3 animate-in fade-in slide-in-from-bottom-5">
          <div className="flex items-center gap-2 pr-2 border-r border-slate-700/60">
            <div className="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300">
              <CheckSquare size={15} />
            </div>
            <div className="text-xs text-slate-200 whitespace-nowrap">
              Selected: <strong className="text-indigo-300 font-bold">{selectedCredIds.length}</strong>{" "}
              {selectedCredIds.length === 1 ? "key" : "keys"}
            </div>
          </div>

          <button
            type="button"
            onClick={() => openBulkGroupModal()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-amber-600/20 transition-all cursor-pointer whitespace-nowrap"
            title="Move selected keys to another folder or create new one"
          >
            <FolderInput size={14} />
            <span>Move to Folder</span>
          </button>

          <button
            type="button"
            onClick={() => openBulkProxyModal()}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer whitespace-nowrap"
            title="Assign proxy to all selected keys"
          >
            <Network size={14} />
            <span>Assign Proxy</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (
                confirm(
                  `Remove proxy from all ${selectedCredIds.length} selected keys (switch to DIRECT)?`
                )
              ) {
                handleApplyBulkProxy(null);
              }
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium border border-slate-700 transition-colors cursor-pointer whitespace-nowrap"
            title="Remove proxy from selected keys (direct connection)"
          >
            <Ban size={14} className="text-slate-400" />
            <span>Remove Proxy (DIRECT)</span>
          </button>

          <button
            type="button"
            onClick={clearSelection}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer ml-1"
            title="Clear selection"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {/* Modal: Bulk Assign Proxy */}
      <Modal
        isOpen={isBulkProxyModalOpen}
        onClose={() => !isBulkSubmitting && setIsBulkProxyModalOpen(false)}
        title={`Assign Proxy to Selected Keys (${selectedCredIds.length})`}
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Selected keys ({selectedCredIds.length}):
            </label>
            <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-2.5 max-h-32 overflow-y-auto flex flex-wrap gap-1.5">
              {selectedCredIds.map((id) => {
                const cred = credentials.find((c) => c.id === id);
                if (!cred) return null;
                return (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 text-[11px] bg-slate-900 border border-slate-700/80 px-2 py-0.5 rounded text-slate-200"
                  >
                    <span className="text-indigo-400 font-semibold">{cred.provider_name}:</span>
                    <span>{cred.name}</span>
                    {cred.group_name && (
                      <span className="text-[9px] text-amber-300">[{cred.group_name}]</span>
                    )}
                    <button
                      type="button"
                      onClick={() => toggleSelectCred(id)}
                      className="text-slate-500 hover:text-rose-400 transition-colors cursor-pointer ml-0.5"
                      title="Exclude from selection"
                    >
                      <X size={10} />
                    </button>
                  </span>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">
              Select proxy to assign:
            </label>
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {/* Option: DIRECT (No Proxy) */}
              <div
                onClick={() => setBulkTargetProxyId(null)}
                className={`p-3 rounded-lg border cursor-pointer transition-all flex items-center justify-between gap-3 ${
                  bulkTargetProxyId === null
                    ? "bg-indigo-950/40 border-indigo-500 ring-1 ring-indigo-500/30"
                    : "bg-slate-950/50 border-slate-800 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <input
                    type="radio"
                    name="bulkProxyChoice"
                    checked={bulkTargetProxyId === null}
                    onChange={() => setBulkTargetProxyId(null)}
                    className="text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                  />
                  <div>
                    <div className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                      <Zap size={13} className="text-amber-400" />
                      <span>Direct connection (DIRECT / no proxy)</span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Requests will connect directly to provider API without proxy tunneling
                    </div>
                  </div>
                </div>
              </div>

              {/* Proxies List */}
              {proxies.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400 border border-dashed border-slate-800 rounded-lg">
                  No proxies configured yet. You can add them on the Proxies page.
                </div>
              ) : (
                proxies.map((p) => {
                  const isSelected = bulkTargetProxyId === p.id;
                  const keysUsingThisProxy = credentials.filter((c) => c.proxy_id === p.id);
                  const selectedUsingThisProxy = credentials.filter(
                    (c) => selectedCredIds.includes(c.id) && c.proxy_id === p.id
                  );

                  return (
                    <div
                      key={p.id}
                      onClick={() => setBulkTargetProxyId(p.id)}
                      className={`p-3 rounded-lg border cursor-pointer transition-all flex items-center justify-between gap-3 ${
                        isSelected
                          ? "bg-indigo-950/40 border-indigo-500 ring-1 ring-indigo-500/30"
                          : "bg-slate-950/50 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 flex-1 min-w-0">
                        <input
                          type="radio"
                          name="bulkProxyChoice"
                          checked={isSelected}
                          onChange={() => setBulkTargetProxyId(p.id)}
                          className="text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-semibold text-slate-200 flex items-center gap-2 flex-wrap">
                            {p.country_code && (
                              <span role="img" aria-label={p.country || "flag"}>
                                {getCountryFlag(p.country_code)}
                              </span>
                            )}
                            <span className="truncate">{p.name}</span>
                            <span className="text-[10px] text-indigo-300 font-mono bg-indigo-950/70 border border-indigo-800/70 px-1.5 py-0.2 rounded uppercase">
                              {p.scheme}
                            </span>
                            <StatusBadge status={p.status} />
                          </div>
                          <div className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">
                            {p.host}:{p.port} {p.country ? `• ${p.country}` : ""}
                          </div>
                        </div>
                      </div>

                      <div className="text-right shrink-0 text-[10px] text-slate-400">
                        {selectedUsingThisProxy.length > 0 && (
                          <div className="text-amber-300 font-medium">
                            Already on {selectedUsingThisProxy.length} of selected
                          </div>
                        )}
                        <div>Total on {keysUsingThisProxy.length} keys</div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-800">
            <button
              type="button"
              disabled={isBulkSubmitting}
              onClick={() => setIsBulkProxyModalOpen(false)}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium cursor-pointer disabled:opacity-50"
            >
              {t.common.cancel}
            </button>
            <button
              type="button"
              disabled={isBulkSubmitting || selectedCredIds.length === 0}
              onClick={() => handleApplyBulkProxy(bulkTargetProxyId)}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
            >
              {isBulkSubmitting ? (
                <>
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Network size={14} />
                  <span>
                    {bulkTargetProxyId === null
                      ? `Remove proxy (${selectedCredIds.length} keys)`
                      : `Assign proxy (${selectedCredIds.length} keys)`}
                  </span>
                </>
              )}
            </button>
          </div>
        </div>
      </Modal>

      {/* Modal: Bulk Move to Folder */}
      <Modal
        isOpen={isBulkGroupModalOpen}
        onClose={() => !isBulkGroupSubmitting && setIsBulkGroupModalOpen(false)}
        title={`Move Selected Keys to Folder (${selectedCredIds.length})`}
        maxWidth="lg"
      >
        <div className="space-y-4">
          {/* Selected keys chips */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-slate-300">
                Selected keys ({selectedCredIds.length}):
              </label>
              {selectedProviders.length > 0 && (
                <div className="flex items-center gap-1 flex-wrap">
                  {selectedProviders.map((p) => (
                    <span
                      key={p.id}
                      className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-indigo-950/80 text-indigo-300 border border-indigo-800/60"
                    >
                      {p.name}: {selectedCredsList.filter((c) => c.provider_id === p.id).length}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-2.5 max-h-32 overflow-y-auto flex flex-wrap gap-1.5">
              {selectedCredsList.map((cred) => (
                <span
                  key={cred.id}
                  className="inline-flex items-center gap-1 text-[11px] bg-slate-900 border border-slate-700/80 px-2 py-0.5 rounded text-slate-200"
                >
                  <span className="text-indigo-400 font-semibold">{cred.provider_name}:</span>
                  <span>{cred.name}</span>
                  <span className="text-[9px] text-amber-300/90 font-mono">
                    [{cred.group_name || "No Group"}]
                  </span>
                  <button
                    type="button"
                    onClick={() => toggleSelectCred(cred.id)}
                    className="text-slate-500 hover:text-rose-400 transition-colors cursor-pointer ml-0.5"
                    title="Exclude from selection"
                  >
                    <X size={10} />
                  </button>
                </span>
              ))}
            </div>
            {selectedProviders.length > 1 && (
              <p className="text-[11px] text-amber-300/90 mt-1">
                ℹ️ Keys selected across {selectedProviders.length} providers. Target folder will be assigned within each provider.
              </p>
            )}
          </div>

          {/* Mode Switcher Tabs */}
          <div className="grid grid-cols-2 gap-2 p-1 bg-slate-950 rounded-xl border border-slate-800">
            <button
              type="button"
              onClick={() => setBulkGroupMode("existing")}
              className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                bulkGroupMode === "existing"
                  ? "bg-amber-600 text-white shadow-md shadow-amber-600/20"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60"
              }`}
            >
              <Folder size={14} />
              <span>Existing Folder</span>
              {availableFoldersForSelected.length > 0 && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-black/20 text-white font-mono">
                  {availableFoldersForSelected.length + 1}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setBulkGroupMode("new")}
              className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                bulkGroupMode === "new"
                  ? "bg-amber-600 text-white shadow-md shadow-amber-600/20"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60"
              }`}
            >
              <FolderPlus size={14} />
              <span>Create New Folder</span>
            </button>
          </div>

          {/* Mode 1: Existing folder list */}
          {bulkGroupMode === "existing" && (
            <div className="space-y-2">
              <label className="block text-xs font-medium text-slate-300">
                Select target folder to move into:
              </label>
              <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                {/* Option: No Group (Root Pool) */}
                <div
                  onClick={() => setBulkTargetGroupName("")}
                  className={`p-2.5 rounded-lg border cursor-pointer transition-all flex items-center justify-between gap-3 ${
                    bulkTargetGroupName === ""
                      ? "bg-amber-950/40 border-amber-500 ring-1 ring-amber-500/30"
                      : "bg-slate-950/50 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <input
                      type="radio"
                      name="bulkGroupExistingChoice"
                      checked={bulkTargetGroupName === ""}
                      onChange={() => setBulkTargetGroupName("")}
                      className="text-amber-500 focus:ring-amber-500 cursor-pointer"
                    />
                    <div>
                      <div className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                        <Folder size={13} className="text-slate-400" />
                        <span>No Group (Root Pool)</span>
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Clear group and move keys to default pool without folder
                      </div>
                    </div>
                  </div>
                  {selectedCredsList.filter((c) => !c.group_name).length > 0 && (
                    <span className="text-[10px] text-slate-400 shrink-0">
                      Already here: {selectedCredsList.filter((c) => !c.group_name).length}
                    </span>
                  )}
                </div>

                {/* List of existing folders */}
                {availableFoldersForSelected.map((fName) => {
                  const isSelected = bulkTargetGroupName === fName;
                  const keysInThisFolder = credentials.filter(
                    (c) =>
                      selectedProviderIds.includes(c.provider_id) &&
                      (c.group_name?.trim() || "") === fName
                  );
                  const selectedAlreadyInFolder = selectedCredsList.filter(
                    (c) => (c.group_name?.trim() || "") === fName
                  );

                  return (
                    <div
                      key={fName}
                      onClick={() => setBulkTargetGroupName(fName)}
                      className={`p-2.5 rounded-lg border cursor-pointer transition-all flex items-center justify-between gap-3 ${
                        isSelected
                          ? "bg-amber-950/40 border-amber-500 ring-1 ring-amber-500/30"
                          : "bg-slate-950/50 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <input
                          type="radio"
                          name="bulkGroupExistingChoice"
                          checked={isSelected}
                          onChange={() => setBulkTargetGroupName(fName)}
                          className="text-amber-500 focus:ring-amber-500 cursor-pointer"
                        />
                        <div>
                          <div className="text-xs font-semibold text-amber-200 flex items-center gap-1.5">
                            <Folder size={13} className="text-amber-400" />
                            <span>{fName}</span>
                          </div>
                          <div className="text-[11px] text-slate-400">
                            Total keys in folder: {keysInThisFolder.length}
                          </div>
                        </div>
                      </div>
                      {selectedAlreadyInFolder.length > 0 && (
                        <span className="text-[10px] text-amber-300/80 shrink-0">
                          Already here: {selectedAlreadyInFolder.length}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Mode 2: Create new folder */}
          {bulkGroupMode === "new" && (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  New Folder Name:
                </label>
                <input
                  type="text"
                  autoFocus
                  value={bulkNewGroupName}
                  onChange={(e) => setBulkNewGroupName(e.target.value)}
                  placeholder="e.g.: Production, Team-A, Fallback-Pool, Backup"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-xs focus:border-amber-500 focus:outline-none"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  A new folder will be created and all{" "}
                  <strong className="text-amber-300">{selectedCredIds.length}</strong> selected
                  keys will be moved into it.
                </p>
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1.5">Quick Templates:</label>
                <div className="flex flex-wrap gap-1.5">
                  {["Production", "Staging", "Team-A", "Backup", "Fast-Tier", "Free-Tier"].map(
                    (tmpl) => (
                      <button
                        key={tmpl}
                        type="button"
                        onClick={() => setBulkNewGroupName(tmpl)}
                        className="text-[10px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors cursor-pointer"
                      >
                        + {tmpl}
                      </button>
                    )
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Modal Footer */}
          <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-800">
            <button
              type="button"
              disabled={isBulkGroupSubmitting}
              onClick={() => setIsBulkGroupModalOpen(false)}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium cursor-pointer disabled:opacity-50"
            >
              {t.common.cancel}
            </button>
            <button
              type="button"
              disabled={
                isBulkGroupSubmitting ||
                selectedCredIds.length === 0 ||
                (bulkGroupMode === "new" && !bulkNewGroupName.trim())
              }
              onClick={() => {
                const target = bulkGroupMode === "new" ? bulkNewGroupName : bulkTargetGroupName;
                handleApplyBulkGroup(target, bulkGroupMode === "new");
              }}
              className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
            >
              {isBulkGroupSubmitting ? (
                <>
                  <RefreshCw size={14} className="animate-spin" />
                  <span>Moving...</span>
                </>
              ) : bulkGroupMode === "new" ? (
                <>
                  <FolderPlus size={14} />
                  <span>Create Folder & Move ({selectedCredIds.length})</span>
                </>
              ) : (
                <>
                  <FolderInput size={14} />
                  <span>
                    {bulkTargetGroupName === ""
                      ? `Move to Root Pool (${selectedCredIds.length})`
                      : `Move to "${bulkTargetGroupName}" (${selectedCredIds.length})`}
                  </span>
                </>
              )}
            </button>
          </div>
        </div>
      </Modal>

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
          loadData();
        }}
      />
    </div>
  );
};
