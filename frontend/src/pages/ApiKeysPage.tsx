import React, { useEffect, useState } from "react";
import { Plus, Copy, Check, Trash2, Key, ShieldCheck, AlertCircle, StickyNote } from "lucide-react";
import { apiRequest } from "../api/client";
import { RouterApiKey, RouterApiKeyCreated, PeriodQuotaRule, PeriodQuotaUsage } from "../types";
import { Modal } from "../components/Modal";
import { NotesModal } from "../components/NotesModal";
import { useI18n } from "../i18n/context";

export const ApiKeysPage: React.FC = () => {
  const { t } = useI18n();
  const [keys, setKeys] = useState<RouterApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [editingKey, setEditingKey] = useState<RouterApiKey | null>(null);
  const [formQuotas, setFormQuotas] = useState<PeriodQuotaRule[]>([]);
  const [quotaUsage, setQuotaUsage] = useState<PeriodQuotaUsage[]>([]);
  const [usageError, setUsageError] = useState("");
  const [saving, setSaving] = useState(false);
  const [formJudge, setFormJudge] = useState(true);
  const [formName, setFormName] = useState("");
  const [formDirect, setFormDirect] = useState(true);
  const [formRoutes, setFormRoutes] = useState(true);
  const [formFusion, setFormFusion] = useState(true);
  const [formRpm, setFormRpm] = useState("");
  const [formNotes, setFormNotes] = useState("");

  // Notes modal
  const [notesModalOpen, setNotesModalOpen] = useState(false);
  const [selectedKeyForNotes, setSelectedKeyForNotes] = useState<RouterApiKey | null>(null);

  const [createdKeyData, setCreatedKeyData] = useState<RouterApiKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);

  const loadKeys = async () => {
    setLoading(true);
    try {
      const data = await apiRequest<RouterApiKey[]>("/api/admin/keys");
      setKeys(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const openCreateModal = () => {
    setEditingKey(null);
    setFormQuotas([]);
    setQuotaUsage([]);
    setUsageError("");
    setFormJudge(true);
    setFormName("");
    setFormDirect(true);
    setFormRoutes(true);
    setFormFusion(true);
    setFormRpm("");
    setFormNotes("");
    setIsModalOpen(true);
  };

  const loadQuotaUsage = async (id: number) => {
    setUsageError("");
    try {
      setQuotaUsage(await apiRequest<PeriodQuotaUsage[]>(`/api/admin/keys/${id}/usage`));
    } catch (err: any) {
      setUsageError(err.message);
    }
  };

  const openEditModal = (key: RouterApiKey) => {
    setEditingKey(key);
    setFormName(key.name);
    setFormDirect(key.permissions.includes("direct"));
    setFormRoutes(key.permissions.includes("routes"));
    setFormFusion(key.permissions.includes("fusion"));
    setFormJudge(key.permissions.includes("judge"));
    setFormRpm(key.rate_limit_rpm == null ? "" : String(key.rate_limit_rpm));
    setFormNotes(key.notes || "");
    setFormQuotas((key.quota_rules || []).map(rule => ({ ...rule })));
    setQuotaUsage([]);
    setIsModalOpen(true);
    loadQuotaUsage(key.id);
  };

  const changeQuota = (index: number, patch: Partial<PeriodQuotaRule>) => {
    setFormQuotas(previous => previous.map((rule, i) => i === index ? { ...rule, ...patch } : rule));
  };

  const openNotesModal = (k: RouterApiKey) => {
    setSelectedKeyForNotes(k);
    setNotesModalOpen(true);
  };

  const handleSaveNotes = async (notes: string) => {
    if (!selectedKeyForNotes) return;
    const trimmed = notes.trim();
    await apiRequest(`/api/admin/keys/${selectedKeyForNotes.id}/notes`, {
      method: "PUT",
      body: JSON.stringify({ notes: trimmed }),
    });
    setKeys((prev) =>
      prev.map((k) =>
        k.id === selectedKeyForNotes.id ? { ...k, notes: trimmed || null } : k
      )
    );
    setSelectedKeyForNotes((prev) => (prev ? { ...prev, notes: trimmed || null } : null));
  };

  const handleClearNotes = async () => {
    if (!selectedKeyForNotes) return;
    await apiRequest(`/api/admin/keys/${selectedKeyForNotes.id}/notes`, {
      method: "PUT",
      body: JSON.stringify({ notes: "" }),
    });
    setKeys((prev) =>
      prev.map((k) =>
        k.id === selectedKeyForNotes.id ? { ...k, notes: null } : k
      )
    );
    setSelectedKeyForNotes((prev) => (prev ? { ...prev, notes: null } : null));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const permissions: string[] = editingKey ? editingKey.permissions.filter(permission => !["direct", "routes", "fusion", "judge"].includes(permission)) : [];
    if (formDirect) permissions.push("direct");
    if (formRoutes) permissions.push("routes");
    if (formFusion) permissions.push("fusion");
    if (formJudge) permissions.push("judge");

    setSaving(true);
    try {
      const body = {
        name: formName, permissions,
        ...(editingKey ? {} : { allowed_models: ["*"], allowed_routes: ["*"], allowed_fusions: ["*"], allowed_judges: ["*"] }),
        rate_limit_rpm: formRpm ? Number(formRpm) : null,
        notes: formNotes.trim() || null,
        quota_rules: formQuotas,
      };
      if (editingKey) {
        await apiRequest<RouterApiKey>(`/api/admin/keys/${editingKey.id}`, { method: "PUT", body: JSON.stringify(body) });
      } else {
        setCreatedKeyData(await apiRequest<RouterApiKeyCreated>("/api/admin/keys", { method: "POST", body: JSON.stringify(body) }));
      }
      setIsModalOpen(false);
      loadKeys();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = () => {
    if (!createdKeyData) return;
    navigator.clipboard.writeText(createdKeyData.raw_api_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleToggleEnabled = async (k: RouterApiKey) => {
    try {
      await apiRequest(`/api/admin/keys/${k.id}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: !k.enabled }),
      });
      loadKeys();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Revoke and delete API key "${name}"? Applications using this key will immediately lose access.`)) return;
    try {
      await apiRequest(`/api/admin/keys/${id}`, { method: "DELETE" });
      loadKeys();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-100">{t.keys.title}</h2>
          <p className="text-xs text-slate-400">
            {t.keys.subtitle}
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="btn-press flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-indigo-600/25 transition-all cursor-pointer"
        >
          <Plus size={15} />
          {t.keys.createKey}
        </button>
      </div>

      {/* Newly Created Key Alert Box */}
      {createdKeyData && (
        <div className="glass-card card-specular p-5 bg-emerald-950/30 border border-emerald-500/30 rounded-2xl space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-300 flex items-center gap-1.5">
              <Key size={15} />
              {t.keys.createKey}
            </span>
            <button
              onClick={() => setCreatedKeyData(null)}
              className="btn-press text-xs text-slate-400 hover:text-slate-200 p-1 hover:bg-white/[0.06] rounded-lg transition-colors cursor-pointer"
            >
              {t.common.close}
            </button>
          </div>
          <p className="text-xs text-slate-300">
            {t.keys.createdKeyWarning}
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={createdKeyData.raw_api_key}
              className="flex-1 px-3.5 py-2 bg-slate-950/80 border border-emerald-500/40 rounded-xl text-emerald-200 text-xs font-mono select-all focus:outline-none"
            />
            <button
              onClick={handleCopy}
              className="btn-press flex items-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-emerald-600/25 transition-all cursor-pointer"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? t.common.copied : t.common.copy}
            </button>
          </div>
        </div>
      )}

      {/* Keys Table */}
      <div className="glass-card card-specular rounded-2xl border border-white/[0.07] overflow-hidden shadow-xl">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-white/[0.06] bg-white/[0.02] text-slate-400 font-semibold uppercase tracking-wider text-[10px] font-mono">
              <th className="py-3.5 px-4">{t.keys.keyName}</th>
              <th className="py-3.5 px-4">{t.common.details}</th>
              <th className="py-3.5 px-4">{t.common.status}</th>
              <th className="py-3.5 px-4">{t.common.total}</th>
              <th className="py-3.5 px-4">{t.common.status}</th>
              <th className="py-3.5 px-4 text-right">{t.common.actions}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.05] text-slate-300">
            {keys.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-8 text-slate-400">
                  {t.keys.subtitle}
                </td>
              </tr>
            ) : (
              keys.map((k) => (
                <tr key={k.id} className="hover:bg-white/[0.03] transition-colors">
                  <td className="py-3.5 px-4 font-medium text-slate-100 flex items-center gap-2.5">
                    <ShieldCheck size={15} className="text-indigo-400 shrink-0 self-start mt-1" />
                    <div className="min-w-0">
                      <div className="font-semibold">{k.name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">{k.key_prefix}...</div>
                      {k.notes && (
                        <button
                          type="button"
                          onClick={() => openNotesModal(k)}
                          className="mt-1 flex items-center gap-1 text-[11px] text-amber-300/90 hover:text-amber-200 cursor-pointer max-w-xs text-left group/note"
                          title={k.notes}
                        >
                          <StickyNote size={11} className="shrink-0 text-amber-400 group-hover/note:scale-110 transition-transform" />
                          <span className="truncate">{k.notes}</span>
                        </button>
                      )}
                    </div>
                  </td>
                  <td className="py-3.5 px-4 font-mono text-[11px] text-slate-300">{k.masked_key}</td>
                  <td className="py-3.5 px-4">
                    <div className="flex flex-wrap gap-1">
                      {k.permissions.map((p) => (
                        <span
                          key={p}
                          className="px-2 py-0.5 rounded-md bg-white/[0.05] border border-white/[0.08] text-[10px] text-slate-300 font-mono"
                        >
                          {p}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3.5 px-4 font-mono text-[11px] text-slate-300">
                    {k.total_requests} reqs
                    <div className="text-slate-400">{(k.quota_rules || []).filter(r => r.enabled).length} period rules</div>
                  </td>
                  <td className="py-3.5 px-4">
                    <button
                      onClick={() => handleToggleEnabled(k)}
                      className={`btn-press px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold transition-colors cursor-pointer ${
                        k.enabled
                          ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30"
                          : "bg-white/[0.04] text-slate-500 border border-white/[0.08]"
                      }`}
                    >
                      {k.enabled ? t.common.active : t.common.disabled}
                    </button>
                  </td>
                  <td className="py-3.5 px-4 text-right space-x-1 whitespace-nowrap">
                    <button type="button" onClick={() => openEditModal(k)} className="btn-press px-2 py-1 text-indigo-300 hover:bg-white/[0.06] rounded-lg">Edit / quotas</button>
                    <button
                      type="button"
                      onClick={() => openNotesModal(k)}
                      className={`btn-press p-1.5 rounded-lg transition-colors cursor-pointer ${
                        k.notes
                          ? "text-amber-400 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/20"
                          : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.06]"
                      }`}
                      title={k.notes ? "Заметка" : "Добавить заметку"}
                    >
                      <StickyNote size={13} />
                    </button>
                    <button
                      onClick={() => handleDelete(k.id, k.name)}
                      className="btn-press p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors cursor-pointer"
                      title="Revoke and delete key"
                    >
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal: Create Key */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingKey ? `Edit key: ${editingKey.name}` : t.keys.createKey}
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">{t.keys.keyName}</label>
            <input
              type="text"
              required
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. VS Code Extension, Production Server"
              className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none transition-all"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">{t.keys.allowedModels}</label>
            <div className="space-y-2 bg-slate-950/60 p-3.5 rounded-xl border border-white/[0.07]">
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formDirect}
                  onChange={(e) => setFormDirect(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-0 cursor-pointer"
                />
                Direct Model Access (e.g. google/gemini-3.8-flash, openai/gpt-4o)
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formRoutes}
                  onChange={(e) => setFormRoutes(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-0 cursor-pointer"
                />
                Routing Profiles (e.g. route/coding, route/fast)
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formFusion}
                  onChange={(e) => setFormFusion(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-0 cursor-pointer"
                />
                Fusion Ensembles (e.g. fusion/powerful-coding)
              </label>
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input type="checkbox" checked={formJudge} onChange={e => setFormJudge(e.target.checked)} /> Judge Profiles
              </label>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              {t.keys.rateLimitRpm}
            </label>
            <input
              type="number"
              value={formRpm}
              onChange={(e) => setFormRpm(e.target.value)}
              placeholder="e.g. 60 requests / min"
              className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none transition-all"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Заметки
            </label>
            <textarea
              value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
              placeholder="Личные заметки к этому ключу роутера..."
              rows={3}
              className="w-full px-3 py-2 bg-slate-950/70 border border-white/10 rounded-xl text-slate-100 text-xs focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none transition-all resize-y"
            />
          </div>

          <section className="space-y-3 border-t border-white/10 pt-3" aria-label="Period quotas">
            <h3 className="text-sm font-semibold text-slate-100">Period quotas</h3>
            <p className="text-xs text-slate-400">Key-wide requests count admitted client calls, including local cache hits. Direct canonical-model rules also count admission (including cache hits); their first upstream dispatch is not counted twice, but extra retries consume requests. Behind route/fusion/judge profiles, model rules count every actual canonical upstream dispatch, including retries and fallback. Requested profile rules count one client request and all its upstream calls. Tokens and USD count upstream calls only.</p>
            <p className="text-xs text-slate-400">All windows use UTC; weeks start Monday, months are calendar months. Custom periods repeat from their anchor. Outside an explicit interval access is denied, not unlimited. Unknown usage retains a conservative reservation; actual measured usage can exceed the estimate. USD rules require known prices (zero is valid).</p>
            {formQuotas.map((rule, index) => {
              const current = quotaUsage.find(item => item.rule_id === rule.id);
              const locked = Boolean(rule.id);
              return <fieldset key={rule.id || index} className="space-y-2 p-3 rounded-xl border border-white/10 bg-slate-950/50">
                <legend className="text-xs text-slate-300">Rule {index + 1}</legend>
                <div className="flex items-center justify-between gap-2">
                  <label className="text-xs text-slate-300"><input type="checkbox" checked={rule.enabled} onChange={e => changeQuota(index, { enabled: e.target.checked })} /> Enabled</label>
                  <button type="button" onClick={() => setFormQuotas(previous => previous.filter((_, i) => i !== index))} className="text-xs text-rose-300">Remove</button>
                </div>
                <label className="block text-xs text-slate-300">Scope
                  <select aria-label={`Quota ${index + 1} scope`} value={rule.scope} disabled={locked} onChange={e => changeQuota(index, {scope: e.target.value as PeriodQuotaRule["scope"], model: null})} className="w-full p-2 rounded bg-slate-900">
                    <option value="key">Entire API key</option><option value="model">Actual canonical upstream model</option><option value="profile">Requested virtual profile</option>
                  </select>
                </label>
                {rule.scope !== "key" && <label className="block text-xs text-slate-300">{rule.scope === "model" ? "Canonical model (provider/model)" : "Requested profile (route/, fusion/, judge/)"}
                  <input required disabled={locked} pattern="[^\s*\/]+/[^\s*]+" value={rule.model || ""} onChange={e => changeQuota(index, {model: e.target.value})} className="w-full p-2 rounded bg-slate-900" />
                </label>}
                <label className="block text-xs text-slate-300">UTC window
                  <select value={rule.period} disabled={locked} onChange={e => changeQuota(index, {period: e.target.value as PeriodQuotaRule["period"], duration_seconds: null, anchor: null, start: null, end: null})} className="w-full p-2 rounded bg-slate-900">
                    {["minute", "hour", "day", "week", "month", "custom", "interval"].map(period => <option key={period}>{period}</option>)}
                  </select>
                </label>
                {rule.period === "custom" && <>
                  <label className="block text-xs text-slate-300">Duration in seconds<input required type="number" min="1" max="315360000" step="1" disabled={locked} value={rule.duration_seconds ?? ""} onChange={e => changeQuota(index, {duration_seconds: e.target.value ? Number(e.target.value) : null})} className="w-full p-2 rounded bg-slate-900" /></label>
                  <label className="block text-xs text-slate-300">Stable anchor (UTC)<input required type="datetime-local" step="1" disabled={locked} value={rule.anchor ? rule.anchor.slice(0,19) : ""} onChange={e => changeQuota(index, {anchor: e.target.value ? new Date(e.target.value + "Z").toISOString() : null})} className="w-full p-2 rounded bg-slate-900" /></label>
                </>}
                {rule.period === "interval" && (["start", "end"] as const).map(field => <label key={field} className="block text-xs text-slate-300">{field} (UTC)<input required type="datetime-local" step="1" disabled={locked} value={rule[field] ? rule[field]!.slice(0,19) : ""} onChange={e => changeQuota(index, {[field]: e.target.value ? new Date(e.target.value + "Z").toISOString() : null})} className="w-full p-2 rounded bg-slate-900" /></label>)}
                <div className="grid grid-cols-3 gap-2">
                  {(["requests", "tokens", "usd"] as const).map(field => <label key={field} className="text-xs text-slate-300">{field === "usd" ? "USD" : field === "tokens" ? "Total tokens" : "Requests"}
                    <input aria-label={`Quota ${index + 1} ${field}`} type="number" min={field === "usd" ? "5e-324" : "1"} max={field === "usd" ? "1000000000000" : field === "requests" ? "2147483647" : "9007199254740991"} step={field === "usd" ? "any" : "1"} value={rule[field] ?? ""} onChange={e => changeQuota(index, {[field]: e.target.value ? Number(e.target.value) : null})} placeholder="Unlimited" className="w-full p-2 rounded bg-slate-900" />
                  </label>)}
                </div>
                {locked && <p className="text-xs text-slate-500">Scope/window identity is fixed; limits and enabled status are editable without resetting usage. Remove and add to change scope/window. Re-adding the same window keeps its spending.</p>}
                {current && <div className="text-xs text-slate-400 space-y-1">
                  <div>{current.active ? "Current window" : "Inactive"}: {current.start} → {current.end}</div>
                  <div>Used: {current.used.requests} requests · {current.used.tokens} tokens · ${current.used.usd.toFixed(8)}</div>
                  <div>Remaining: {current.remaining.requests ?? "∞"} requests · {current.remaining.tokens ?? "∞"} tokens · {current.remaining.usd == null ? "∞ USD" : `$${current.remaining.usd.toFixed(8)}`}</div>
                </div>}
              </fieldset>;
            })}
            <div className="flex gap-3 text-xs">
              <button type="button" disabled={formQuotas.length >= 64} onClick={() => setFormQuotas(previous => [...previous, { enabled: true, scope: "key", period: "day", requests: null, tokens: null, usd: null }])} className="text-indigo-300 disabled:opacity-40">Add quota rule</button>
              <button type="button" onClick={() => setFormQuotas([])} className="text-rose-300">Clear all rules</button>
              {editingKey && <button type="button" onClick={() => loadQuotaUsage(editingKey.id)} className="text-indigo-300">Refresh usage</button>}
            </div>
            {usageError && <p role="alert" className="text-xs text-rose-300">{usageError}</p>}
            {!formQuotas.length && <p className="text-xs text-slate-400">No period quotas: unlimited (existing lifetime/RPM/TPM limits still apply).</p>}
          </section>

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
              disabled={saving}
              className="btn-press px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/25 transition-all cursor-pointer"
            >
              {saving ? "Saving…" : editingKey ? "Save changes" : t.common.create}
            </button>
          </div>
        </form>
      </Modal>

      {/* Notes Modal */}
      <NotesModal
        isOpen={notesModalOpen}
        onClose={() => setNotesModalOpen(false)}
        title={`Заметка: ${selectedKeyForNotes?.name || ""}`}
        initialNotes={selectedKeyForNotes?.notes || ""}
        onSave={handleSaveNotes}
        onClear={handleClearNotes}
      />
    </div>
  );
};

