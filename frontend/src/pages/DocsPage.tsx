import React, { useState, useMemo } from "react";
import {
  BookOpen,
  Search,
  ChevronRight,
  ChevronLeft,
  Terminal,
  GitFork,
  Merge,
  ShieldCheck,
  Network,
  Cpu,
  KeyRound,
  Boxes,
  Zap,
  AlertTriangle,
  Copy,
  Check,
  Brain,
  Gauge,
  Sparkles,
  BarChart3,
  Bot,
  Code2,
} from "lucide-react";
import { useI18n } from "../i18n";
import { docsTranslations, DocSectionContent } from "../i18n/docs";

const sectionIcons: Record<string, React.ReactNode> = {
  overview: <BookOpen size={15} />,
  quickstart: <Zap size={15} />,
  models: <Boxes size={15} />,
  ollama: <Bot size={15} />,
  "intelligence-ratings": <Brain size={15} />,
  "model-limits": <Gauge size={15} />,
  "thinking-cot": <Sparkles size={15} />,
  "direct-routing": <Terminal size={15} />,
  "priority-fallback": <GitFork size={15} />,
  fusion: <Merge size={15} />,
  providers: <Cpu size={15} />,
  credentials: <KeyRound size={15} />,
  "api-keys": <ShieldCheck size={15} />,
  proxies: <Network size={15} />,
  "backup-restore": <Code2 size={15} />,
  analytics: <BarChart3 size={15} />,
  "circuit-breaker": <AlertTriangle size={15} />,
  "api-reference": <Terminal size={15} />,
  errors: <AlertTriangle size={15} />,
  "env-config": <Zap size={15} />,
};

const GROUP_NAMES: Record<string, Record<string, string>> = {
  intro: {
    en: "Introduction",
    ru: "Введение",
    uk: "Вступ",
    be: "Уводзіны",
    zh: "入门与架构",
    es: "Introducción",
    fr: "Introduction",
    de: "Einführung",
    ja: "はじめに",
    pt: "Introdução",
    ar: "مقدمة",
    hi: "परिचय",
    bn: "ভূমিকা",
  },
  models: {
    en: "Models & Intelligence",
    ru: "Модели и ИИ-индексы",
    uk: "Моделі та ШІ-індекси",
    be: "Мадэлі і ШІ-індэксы",
    zh: "模型与智能评级",
    es: "Modelos e Inteligencia",
    fr: "Modèles et Intelligence",
    de: "Modelle & Intelligenz",
    ja: "モデルと性能指標",
    pt: "Modelos e Inteligência",
    ar: "النماذج والذكاء",
    hi: "मॉडल और बुद्धिमत्ता",
    bn: "মডেল এবং বুদ্ধিমত্তা",
  },
  routing: {
    en: "Routing Engines",
    ru: "Движки маршрутизации",
    uk: "Механізми маршрутизації",
    be: "Рухавікі маршрутызацыі",
    zh: "智能路由引擎",
    es: "Motores de Enrutamiento",
    fr: "Moteurs de Routage",
    de: "Routing-Engines",
    ja: "ルーティングエンジン",
    pt: "Motores de Roteamento",
    ar: "محركات التوجيه",
    hi: "रूटिंग इंजन",
    bn: "রাউটিং ইঞ্জিন",
  },
  management: {
    en: "Management & Security",
    ru: "Управление и безопасность",
    uk: "Керування та безпека",
    be: "Кіраванне і бяспека",
    zh: "配置管理与安全",
    es: "Gestión y Seguridad",
    fr: "Gestion et Sécurité",
    de: "Verwaltung & Sicherheit",
    ja: "管理とセキュリティ",
    pt: "Gerenciamento e Segurança",
    ar: "الإدارة والأمان",
    hi: "प्रबंधन और सुरक्षा",
    bn: "ব্যবস্থাপনা ও নিরাপত্তা",
  },
  system: {
    en: "System & Operations",
    ru: "Система и эксплуатация",
    uk: "Система та експлуатація",
    be: "Сістэма і эксплуатацыя",
    zh: "系统运维与参考",
    es: "Sistema y Operaciones",
    fr: "Système et Exploitation",
    de: "System & Betrieb",
    ja: "システムと運用",
    pt: "Sistema e Operações",
    ar: "النظام والتشغيل",
    hi: "सिस्टम और संचालन",
    bn: "সিস্টেম এবং পরিচালনা",
  },
};

function CodeBlock({
  children,
  lang,
  title,
  copyLabel,
  copiedLabel,
}: {
  children: string;
  lang?: string;
  title?: string;
  copyLabel?: string;
  copiedLabel?: string;
}) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(children.trim());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="relative group my-4 rounded-xl border border-white/[0.08] overflow-hidden shadow-lg bg-slate-950/90">
      {title && (
        <div className="text-[11px] tracking-wider text-slate-300 font-semibold px-4 py-2 bg-slate-900/90 border-b border-white/[0.08] font-mono flex items-center justify-between">
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-500 inline-block"></span>
            {title}
          </span>
          {lang && (
            <span className="text-indigo-400 font-mono text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-indigo-950/50 border border-indigo-500/20">
              {lang}
            </span>
          )}
        </div>
      )}
      <pre className="p-4 overflow-x-auto text-[12px] leading-relaxed font-mono text-slate-200 custom-scrollbar">
        <code>{children.trim()}</code>
      </pre>
      <button
        onClick={handleCopy}
        className="btn-press absolute top-2 right-2 px-2.5 py-1 rounded-lg bg-white/[0.08] hover:bg-white/[0.14] text-slate-300 hover:text-white transition-all border border-white/10 cursor-pointer flex items-center gap-1.5 text-[11px]"
        title={copyLabel || "Copy"}
      >
        {copied ? (
          <>
            <Check size={13} className="text-emerald-400" />
            <span className="text-emerald-400 font-medium text-[10px]">
              {copiedLabel || "Copied"}
            </span>
          </>
        ) : (
          <>
            <Copy size={13} />
            <span className="font-medium text-[10px]">{copyLabel || "Copy"}</span>
          </>
        )}
      </button>
    </div>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto my-4 rounded-xl border border-white/[0.08] shadow-lg bg-slate-950/40">
      <table className="w-full text-xs text-left">
        <thead className="bg-slate-900/80 text-slate-300 font-semibold text-[10px] uppercase tracking-wider font-mono border-b border-white/[0.08]">
          <tr>
            {headers.map((h, i) => (
              <th key={i} className="py-2.5 px-4 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="text-slate-300 divide-y divide-white/[0.05]">
          {rows.map((row, ri) => (
            <tr key={ri} className="hover:bg-white/[0.03] transition-colors">
              {row.map((cell, ci) => (
                <td key={ci} className="py-2.5 px-4 font-mono text-[11px] leading-relaxed">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Callout({
  type,
  title,
  text,
}: {
  type?: "info" | "warning" | "success";
  title?: string;
  text: string;
}) {
  const styles = {
    info: "bg-indigo-950/40 border-indigo-500/30 text-indigo-200",
    warning: "bg-amber-950/40 border-amber-500/30 text-amber-200",
    success: "bg-emerald-950/40 border-emerald-500/30 text-emerald-200",
  };
  const icon =
    type === "warning" ? (
      <AlertTriangle size={15} className="text-amber-400 shrink-0 mt-0.5" />
    ) : type === "success" ? (
      <Check size={15} className="text-emerald-400 shrink-0 mt-0.5" />
    ) : (
      <Sparkles size={15} className="text-indigo-400 shrink-0 mt-0.5" />
    );
  return (
    <div
      className={`p-4 rounded-xl border text-xs leading-relaxed my-4 flex items-start gap-3 shadow-md ${styles[type || "info"]}`}
    >
      {icon}
      <div className="space-y-1 flex-1">
        {title && <div className="font-semibold text-sm tracking-tight text-white">{title}</div>}
        <div className="text-slate-200">{text}</div>
      </div>
    </div>
  );
}

export const DocsPage: React.FC = () => {
  const { language } = useI18n();
  const docContent = docsTranslations[language] || docsTranslations.en;

  const [activeSectionId, setActiveSectionId] = useState<string>("overview");
  const [searchQuery, setSearchQuery] = useState("");

  const sectionsList: DocSectionContent[] = useMemo(() => {
    return docContent.sections || [];
  }, [docContent]);

  // Search filtering across title, description, badge, highlights, and subsections
  const filteredSections = useMemo(() => {
    if (!searchQuery.trim()) return sectionsList;
    const q = searchQuery.toLowerCase();
    return sectionsList.filter((s) => {
      if (s.title.toLowerCase().includes(q)) return true;
      if (s.description.toLowerCase().includes(q)) return true;
      if (s.badge && s.badge.toLowerCase().includes(q)) return true;
      if (s.highlights && s.highlights.some((h) => h.toLowerCase().includes(q))) return true;
      if (
        s.subsections &&
        s.subsections.some(
          (sub) =>
            sub.title.toLowerCase().includes(q) ||
            (sub.description && sub.description.toLowerCase().includes(q)) ||
            (sub.code && sub.code.content.toLowerCase().includes(q))
        )
      ) {
        return true;
      }
      return false;
    });
  }, [sectionsList, searchQuery]);

  // Group sections by their group identifier
  const groupedSections = useMemo(() => {
    const groups: Record<string, DocSectionContent[]> = {};
    for (const sec of filteredSections) {
      const g = sec.group || "intro";
      if (!groups[g]) groups[g] = [];
      groups[g].push(sec);
    }
    return groups;
  }, [filteredSections]);

  // Current active section
  const currentSection = useMemo(() => {
    const found = sectionsList.find((s) => s.id === activeSectionId);
    return found || sectionsList[0] || null;
  }, [sectionsList, activeSectionId]);

  // Index of current section for prev/next buttons
  const currentIndex = useMemo(() => {
    return sectionsList.findIndex((s) => s.id === (currentSection?.id || "overview"));
  }, [sectionsList, currentSection]);

  const prevSec = currentIndex > 0 ? sectionsList[currentIndex - 1] : null;
  const nextSec =
    currentIndex >= 0 && currentIndex < sectionsList.length - 1
      ? sectionsList[currentIndex + 1]
      : null;

  return (
    <div className="flex gap-6 max-w-7xl mx-auto h-[calc(100vh-5rem)]">
      {/* Sidebar Navigation */}
      <aside className="w-72 shrink-0 overflow-y-auto pr-3 border-r border-white/[0.08] py-2 space-y-5 custom-scrollbar">
        <div className="relative">
          <Search size={13} className="absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder={docContent.ui.searchPlaceholder}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-slate-900/90 border border-white/10 rounded-xl text-xs text-slate-200 placeholder-slate-400 focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 focus:outline-none transition-all shadow-inner"
          />
        </div>

        {Object.keys(groupedSections).length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-500">
            {docContent.ui.noSectionsFound}
          </div>
        ) : (
          Object.entries(groupedSections).map(([groupKey, items]) => {
            const groupTitle =
              (GROUP_NAMES[groupKey] && GROUP_NAMES[groupKey][language]) ||
              (GROUP_NAMES[groupKey] && GROUP_NAMES[groupKey].en) ||
              groupKey.toUpperCase();

            return (
              <div key={groupKey} className="space-y-1">
                <div className="px-2.5 pb-1 text-[10px] font-bold uppercase tracking-wider text-indigo-400/80 font-mono">
                  {groupTitle}
                </div>
                {items.map((item) => {
                  const isActive = currentSection?.id === item.id;
                  const icon = sectionIcons[item.id] || <BookOpen size={15} />;
                  return (
                    <button
                      key={item.id}
                      onClick={() => setActiveSectionId(item.id)}
                      className={`btn-press w-full flex items-center justify-between px-3 py-2 rounded-xl text-[12px] font-medium transition-all cursor-pointer ${
                        isActive
                          ? "bg-indigo-600/20 text-indigo-200 font-semibold border border-indigo-500/30 shadow-xs"
                          : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 truncate">
                        <span className={isActive ? "text-indigo-400" : "text-slate-500"}>
                          {icon}
                        </span>
                        <span className="truncate">{item.title}</span>
                      </div>
                      {item.badge && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.05] text-slate-400 shrink-0 ml-1.5">
                          {item.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })
        )}
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto py-2 pl-2 pr-4 custom-scrollbar">
        {currentSection ? (
          <div className="glass-card card-specular rounded-2xl border border-white/[0.07] p-8 shadow-xl">
            {/* Header */}
            <div className="border-b border-white/[0.08] pb-6">
              {currentSection.badge && (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-semibold uppercase tracking-wider bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 mb-3">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
                  {currentSection.badge}
                </div>
              )}
              <h1 className="text-2xl font-bold text-slate-100 tracking-tight flex items-center gap-3">
                <span className="text-indigo-400">
                  {sectionIcons[currentSection.id] || <BookOpen size={22} />}
                </span>
                {currentSection.title}
              </h1>
              <p className="text-sm text-slate-300 leading-relaxed mt-2.5 max-w-3xl">
                {currentSection.description}
              </p>
            </div>

            {/* Highlights Cards */}
            {currentSection.highlights && currentSection.highlights.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 my-6">
                {currentSection.highlights.map((highlight, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-3 p-3.5 rounded-xl bg-indigo-950/20 border border-indigo-500/15 text-slate-200 text-xs shadow-xs"
                  >
                    <Sparkles size={14} className="text-indigo-400 shrink-0 mt-0.5" />
                    <span className="leading-relaxed">{highlight}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Subsections */}
            {currentSection.subsections && currentSection.subsections.length > 0 && (
              <div className="space-y-8 mt-6">
                {currentSection.subsections.map((sub, idx) => (
                  <section
                    key={idx}
                    className="pt-6 border-t border-white/[0.06] first:border-0 first:pt-0"
                  >
                    <h2 className="text-base font-semibold text-slate-100 mb-2 flex items-center gap-2 tracking-tight">
                      <span className="w-1.5 h-4 rounded-full bg-indigo-500"></span>
                      {sub.title}
                    </h2>

                    {sub.description && (
                      <p className="text-xs text-slate-300 leading-relaxed mb-3">
                        {sub.description}
                      </p>
                    )}

                    {sub.bullets && sub.bullets.length > 0 && (
                      <ul className="space-y-1.5 my-3 text-xs text-slate-300 list-disc list-inside">
                        {sub.bullets.map((bullet, bi) => (
                          <li key={bi} className="leading-relaxed">
                            {bullet}
                          </li>
                        ))}
                      </ul>
                    )}

                    {sub.code && (
                      <CodeBlock
                        lang={sub.code.lang}
                        title={sub.code.title}
                        copyLabel={docContent.ui.copy}
                        copiedLabel={docContent.ui.copied}
                      >
                        {sub.code.content}
                      </CodeBlock>
                    )}

                    {sub.table && (
                      <Table headers={sub.table.headers} rows={sub.table.rows} />
                    )}

                    {sub.callout && (
                      <Callout
                        type={sub.callout.type}
                        title={sub.callout.title}
                        text={sub.callout.text}
                      />
                    )}
                  </section>
                ))}
              </div>
            )}

            {/* Footer Navigation (Prev / Next) */}
            <div className="flex items-center justify-between mt-12 pt-6 border-t border-white/[0.08]">
              {prevSec ? (
                <button
                  onClick={() => {
                    setActiveSectionId(prevSec.id);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                  className="btn-press flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-slate-900/90 border border-white/10 hover:border-indigo-500/40 text-xs text-slate-300 hover:text-white transition-all cursor-pointer"
                >
                  <ChevronLeft size={15} />
                  <div className="text-left">
                    <div className="text-[10px] text-slate-500 uppercase font-mono">
                      {docContent.ui.prevSection}
                    </div>
                    <div className="font-semibold text-slate-200">{prevSec.title}</div>
                  </div>
                </button>
              ) : (
                <div />
              )}

              {nextSec ? (
                <button
                  onClick={() => {
                    setActiveSectionId(nextSec.id);
                    window.scrollTo({ top: 0, behavior: "smooth" });
                  }}
                  className="btn-press flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-slate-900/90 border border-white/10 hover:border-indigo-500/40 text-xs text-slate-300 hover:text-white transition-all cursor-pointer text-right"
                >
                  <div className="text-right">
                    <div className="text-[10px] text-slate-500 uppercase font-mono">
                      {docContent.ui.nextSection}
                    </div>
                    <div className="font-semibold text-slate-200">{nextSec.title}</div>
                  </div>
                  <ChevronRight size={15} />
                </button>
              ) : (
                <div />
              )}
            </div>
          </div>
        ) : (
          <div className="text-center py-24 text-slate-500 text-sm">
            {docContent.ui.noSectionsFound}
          </div>
        )}
      </main>
    </div>
  );
};
