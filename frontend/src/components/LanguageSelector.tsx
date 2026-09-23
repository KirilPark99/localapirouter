import React, { useState, useRef, useEffect } from "react";
import { Globe, ChevronDown, Check } from "lucide-react";
import { useI18n } from "../i18n/context";
import { Language, SUPPORTED_LANGUAGES } from "../i18n/types";

interface LanguageSelectorProps {
  variant?: "compact" | "full";
  className?: string;
}

export const LanguageSelector: React.FC<LanguageSelectorProps> = ({
  variant = "compact",
  className = "",
}) => {
  const { language, setLanguage, currentLanguage, t } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  if (variant === "full") {
    return (
      <div className={`grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 ${className}`}>
        {SUPPORTED_LANGUAGES.map((lang) => {
          const isSelected = lang.code === language;
          return (
            <button
              key={lang.code}
              type="button"
              onClick={() => setLanguage(lang.code as Language)}
              className={`flex items-center justify-between p-3 rounded-xl border text-left transition-all btn-press ${
                isSelected
                  ? "bg-indigo-600/20 border-indigo-500/50 text-white shadow-md shadow-indigo-600/10 ring-1 ring-indigo-500/30"
                  : "bg-slate-900/40 border-white/[0.06] text-slate-300 hover:bg-white/[0.04] hover:border-white/10 hover:text-white"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-xl shrink-0" role="img" aria-label={lang.name}>
                  {lang.flag}
                </span>
                <div>
                  <div className="text-xs font-semibold leading-tight flex items-center gap-1.5">
                    <span>{lang.nativeName}</span>
                    {lang.code === "en" && (
                      <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                        Default
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">{lang.name}</div>
                </div>
              </div>
              {isSelected && (
                <div className="w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center text-white shrink-0 shadow-xs">
                  <Check size={12} strokeWidth={3} />
                </div>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  // Compact variant (used in Header bar and Login page)
  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`btn-press flex items-center gap-2 px-3 py-1.5 rounded-xl border transition-all shadow-md cursor-pointer ${
          isOpen
            ? "bg-indigo-600/20 border-indigo-500/60 text-white ring-1 ring-indigo-500/40"
            : "bg-slate-900/95 hover:bg-slate-800 border-slate-700/80 hover:border-slate-600 text-slate-100"
        }`}
        title={t.header.language}
      >
        <Globe size={14} className="text-indigo-400 shrink-0" />
        <span className="text-sm shrink-0" role="img" aria-label={currentLanguage.name}>
          {currentLanguage.flag}
        </span>
        <span className="font-semibold text-xs tracking-tight text-slate-100">
          {currentLanguage.nativeName}
        </span>
        <ChevronDown
          size={12}
          className={`text-slate-400 transition-transform duration-200 shrink-0 ${isOpen ? "rotate-180 text-indigo-300" : ""}`}
        />
      </button>

      {isOpen && (
        <div
          className="absolute right-0 mt-2 w-80 max-h-[480px] flex flex-col rounded-2xl bg-slate-950/98 border border-slate-700/90 shadow-2xl shadow-black/90 p-2 z-[100] animate-in fade-in zoom-in-95 duration-150 backdrop-blur-2xl"
          style={{ maxHeight: "calc(100vh - 80px)" }}
        >
          <div className="px-3 py-2 flex items-center justify-between border-b border-white/[0.08] mb-1.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
              <Globe size={14} className="text-indigo-400" />
              <span>{t.header.language}</span>
            </div>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-white/[0.06] text-slate-400 border border-white/[0.08]">
              {SUPPORTED_LANGUAGES.length} {t.common.total}
            </span>
          </div>
          <div className="overflow-y-auto space-y-1 pr-1 flex-1">
            {SUPPORTED_LANGUAGES.map((lang) => {
              const isSelected = lang.code === language;
              return (
                <button
                  key={lang.code}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setLanguage(lang.code as Language);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs transition-all text-left cursor-pointer ${
                    isSelected
                      ? "bg-indigo-600/30 text-white font-semibold border border-indigo-500/50 shadow-sm"
                      : "text-slate-300 hover:bg-white/[0.08] hover:text-white hover:border-white/10 border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate">
                    <span className="text-lg shrink-0" role="img" aria-label={lang.name}>
                      {lang.flag}
                    </span>
                    <div className="truncate">
                      <div className="leading-tight font-medium text-slate-100 flex items-center gap-1.5">
                        <span>{lang.nativeName}</span>
                        {lang.dir === "rtl" && (
                          <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            RTL
                          </span>
                        )}
                        {lang.code === "en" && (
                          <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                            Default
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-400 truncate mt-0.5">{lang.name}</div>
                    </div>
                  </div>
                  {isSelected && (
                    <div className="w-5 h-5 rounded-full bg-indigo-500 text-white flex items-center justify-center shrink-0 ml-2 shadow-xs">
                      <Check size={12} strokeWidth={3} />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
