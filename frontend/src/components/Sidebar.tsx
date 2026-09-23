import React from "react";
import {
  LayoutDashboard,
  BarChart3,
  Cpu,
  KeyRound,
  Boxes,
  GitFork,
  Merge,
  ShieldCheck,
  Network,
  TerminalSquare,
  ScrollText,
  Settings,
  LogOut,
  Sparkles,
  BookOpen,
} from "lucide-react";
import { useI18n } from "../i18n/context";

export type PageId =
  | "dashboard"
  | "analytics"
  | "providers"
  | "credentials"
  | "models"
  | "routing"
  | "fusion"
  | "keys"
  | "proxies"
  | "playground"
  | "logs"
  | "settings"
  | "docs";

interface SidebarProps {
  activePage: PageId;
  onNavigate: (page: PageId) => void;
  onLogout: () => void;
  username: string;
}

interface NavGroup {
  title: string;
  items: { id: PageId; label: string; icon: React.ReactNode; badge?: string }[];
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onNavigate,
  onLogout,
  username,
}) => {
  const { t } = useI18n();

  const navGroups: NavGroup[] = [
    {
      title: t.nav.groups.overview,
      items: [
        { id: "dashboard", label: t.nav.dashboard, icon: <LayoutDashboard size={16} /> },
        { id: "analytics", label: t.nav.analytics, icon: <BarChart3 size={16} /> },
        { id: "logs", label: t.nav.logs, icon: <ScrollText size={16} /> },
      ],
    },
    {
      title: t.nav.groups.providersModels,
      items: [
        { id: "playground", label: t.nav.playground, icon: <TerminalSquare size={16} />, badge: "Live" },
        { id: "models", label: t.nav.models, icon: <Boxes size={16} /> },
        { id: "routing", label: t.nav.routing, icon: <GitFork size={16} /> },
        { id: "fusion", label: t.nav.fusion, icon: <Merge size={16} />, badge: "AI" },
      ],
    },
    {
      title: t.nav.groups.securityAccess,
      items: [
        { id: "providers", label: t.nav.providers, icon: <Cpu size={16} /> },
        { id: "credentials", label: t.nav.credentials, icon: <KeyRound size={16} /> },
        { id: "keys", label: t.nav.keys, icon: <ShieldCheck size={16} /> },
        { id: "proxies", label: t.nav.proxies, icon: <Network size={16} /> },
      ],
    },
    {
      title: t.nav.groups.admin,
      items: [
        { id: "settings", label: t.nav.settings, icon: <Settings size={16} /> },
        { id: "docs", label: t.nav.docs, icon: <BookOpen size={16} /> },
      ],
    },
  ];

  return (
    <aside className="w-64 bg-slate-950/70 backdrop-blur-xl border-r border-white/[0.06] flex flex-col h-screen select-none shrink-0 shadow-2xl relative z-20">
      {/* Brand Header */}
      <div className="h-14 flex items-center px-4 border-b border-white/[0.06] gap-3 bg-slate-950/40">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 via-violet-500 to-purple-600 flex items-center justify-center text-white shadow-md shadow-indigo-500/25 ring-1 ring-white/20">
          <Sparkles size={17} className="animate-pulse" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-bold text-slate-100 text-sm tracking-tight flex items-center justify-between">
            <span className="truncate bg-gradient-to-r from-slate-100 to-slate-300 bg-clip-text text-transparent">
              MyAIrouter
            </span>
            <span className="text-[9px] font-mono tracking-wider font-bold uppercase px-1.5 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
              Gateway
            </span>
          </div>
          <div className="text-[10px] text-slate-400 font-medium truncate">Universal LLM Orchestrator</div>
        </div>
      </div>

      {/* Nav Menu */}
      <nav className="flex-1 px-3 py-3 space-y-4 overflow-y-auto">
        {navGroups.map((group, gIdx) => (
          <div key={gIdx} className="space-y-1">
            <div className="px-2.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 font-mono">
              {group.title}
            </div>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const isActive = activePage === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onNavigate(item.id)}
                    className={`w-full flex items-center justify-between px-2.5 py-2 rounded-xl text-xs font-medium transition-all duration-150 btn-press ${
                      isActive
                        ? "bg-gradient-to-r from-indigo-600/25 via-indigo-600/15 to-transparent text-indigo-100 font-semibold border-l-2 border-indigo-400 pl-2 shadow-xs"
                        : "text-slate-400 hover:text-slate-100 hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <span className={isActive ? "text-indigo-400" : "text-slate-400 group-hover:text-slate-300"}>
                        {item.icon}
                      </span>
                      <span className="truncate">{item.label}</span>
                    </div>
                    {item.badge && (
                      <span
                        className={`text-[9px] font-mono font-bold uppercase px-1.5 py-0.5 rounded-md ${
                          item.badge === "Live"
                            ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                            : "bg-purple-500/15 text-purple-300 border border-purple-500/30"
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* User / Footer */}
      <div className="p-3 border-t border-white/[0.06] bg-slate-950/50 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="relative">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-slate-800 to-slate-700 border border-white/10 flex items-center justify-center text-xs font-mono font-bold text-indigo-300 shadow-inner">
              {username.slice(0, 1).toUpperCase()}
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-slate-950 shadow-xs shadow-emerald-400/50" />
          </div>
          <div className="truncate">
            <div className="text-xs font-semibold text-slate-200 truncate">{username}</div>
            <div className="text-[10px] text-emerald-400 flex items-center gap-1 font-mono">
              <span className="w-1 h-1 rounded-full bg-emerald-400 animate-ping" />
              Connected
            </div>
          </div>
        </div>
        <button
          onClick={onLogout}
          title={t.nav.logout}
          className="text-slate-400 hover:text-rose-400 p-1.5 rounded-lg hover:bg-rose-950/40 border border-transparent hover:border-rose-900/50 transition-all btn-press"
        >
          <LogOut size={15} />
        </button>
      </div>
    </aside>
  );
};
