import React, { useState, useEffect } from "react";
import { StickyNote, Save, Trash2, X, Check, FileText } from "lucide-react";
import { Modal } from "./Modal";

interface NotesModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  entityType?: "provider" | "module";
  initialNotes?: string | null;
  onSave: (notes: string) => Promise<void>;
  onClear?: () => Promise<void>;
}

export const NotesModal: React.FC<NotesModalProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  entityType = "provider",
  initialNotes = "",
  onSave,
  onClear,
}) => {
  const [notes, setNotes] = useState(initialNotes || "");
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setNotes(initialNotes || "");
      setSavedSuccess(false);
      setError(null);
    }
  }, [isOpen, initialNotes]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(notes);
      setSavedSuccess(true);
      setTimeout(() => {
        setSavedSuccess(false);
        onClose();
      }, 400);
    } catch (err: any) {
      setError(err.message || "Не удалось сохранить заметку");
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm("Удалить эту заметку?")) return;
    setSaving(true);
    setError(null);
    try {
      if (onClear) {
        await onClear();
      } else {
        await onSave("");
      }
      setNotes("");
      setSavedSuccess(true);
      setTimeout(() => {
        setSavedSuccess(false);
        onClose();
      }, 400);
    } catch (err: any) {
      setError(err.message || "Не удалось очистить заметку");
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSave();
    }
  };

  const wordCount = notes.trim() ? notes.trim().split(/\s+/).length : 0;
  const charCount = notes.length;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shadow-sm">
              <StickyNote size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-100 tracking-tight">{title}</h3>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/25">
                  {entityType === "provider" ? "Провайдер" : "Модуль"}
                </span>
              </div>
              {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-white/[0.06] transition-colors cursor-pointer"
          >
            <X size={16} />
          </button>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
            {error}
          </div>
        )}

        {/* Text Area */}
        <div className="space-y-1.5">
          <label className="block text-xs font-medium text-slate-300">
            Текст заметки
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={7}
            placeholder="Введите текст заметки (например, особенности провайдера, лимиты, специфика сессий, напоминания)..."
            className="w-full bg-slate-950/80 border border-white/10 rounded-xl p-3 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500/60 focus:ring-1 focus:ring-amber-500/30 font-sans leading-relaxed resize-y transition-all"
            autoFocus
          />
          <div className="flex items-center justify-between text-[11px] text-slate-400 px-1">
            <span>
              {charCount} симв. • {wordCount} слов
            </span>
            <span className="text-slate-400">
              <kbd className="px-1 py-0.5 bg-slate-900 border border-white/10 rounded text-[10px] font-mono">
                Ctrl+Enter
              </kbd>{" "}
              для сохранения
            </span>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-white/[0.08]">
          <div>
            {initialNotes && (
              <button
                type="button"
                onClick={handleClear}
                disabled={saving}
                className="btn-press flex items-center gap-1.5 px-3 py-1.5 text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 rounded-xl transition-colors cursor-pointer disabled:opacity-50"
              >
                <Trash2 size={13} />
                <span>Очистить</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] rounded-xl transition-colors cursor-pointer"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="btn-press flex items-center gap-1.5 px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold rounded-xl text-xs shadow-md shadow-amber-500/20 transition-all cursor-pointer disabled:opacity-50"
            >
              {savedSuccess ? (
                <>
                  <Check size={14} className="text-slate-950" />
                  <span>Сохранено!</span>
                </>
              ) : (
                <>
                  <Save size={14} />
                  <span>{saving ? "Сохранение..." : "Сохранить"}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
