import React, { useEffect, useState } from "react";
import { Sidebar, PageId } from "./components/Sidebar";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ProvidersPage } from "./pages/ProvidersPage";
import { CredentialsPage } from "./pages/CredentialsPage";
import { ModelsPage } from "./pages/ModelsPage";
import { RoutingPage } from "./pages/RoutingPage";
import { FusionPage } from "./pages/FusionPage";
import { ApiKeysPage } from "./pages/ApiKeysPage";
import { ProxiesPage } from "./pages/ProxiesPage";
import { PlaygroundPage } from "./pages/PlaygroundPage";
import { LogsPage } from "./pages/LogsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { DocsPage } from "./pages/DocsPage";
import { apiRequest } from "./api/client";
import { TerminalSquare } from "lucide-react";
import { useI18n } from "./i18n/context";
import { LanguageSelector } from "./components/LanguageSelector";

export const App: React.FC = () => {
  const { t } = useI18n();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [username, setUsername] = useState<string>("admin");
  const [activePage, setActivePage] = useState<PageId>("dashboard");
  const [checkingAuth, setCheckingAuth] = useState<boolean>(true);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem("myairouter_token");
      if (!token) {
        setIsAuthenticated(false);
        setCheckingAuth(false);
        return;
      }
      try {
        const data = await apiRequest<{ username: string }>("/api/admin/auth/me");
        setUsername(data.username);
        setIsAuthenticated(true);
      } catch {
        localStorage.removeItem("myairouter_token");
        setIsAuthenticated(false);
      } finally {
        setCheckingAuth(false);
      }
    };
    checkAuth();
  }, []);

  const handleLogout = async () => {
    try {
      await apiRequest("/api/admin/auth/logout", { method: "POST" });
    } catch {}
    localStorage.removeItem("myairouter_token");
    setIsAuthenticated(false);
  };

  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-xs text-slate-400">
        {t.header.connecting}
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <LoginPage
        onLoginSuccess={(user) => {
          setUsername(user);
          setIsAuthenticated(true);
        }}
      />
    );
  }

  // Get active page label from translation
  const activePageLabel = (t.nav as Record<string, any>)[activePage] || activePage.replace("-", " ");

  return (
    <div className="flex h-full w-full bg-[#080c14] text-slate-100 overflow-hidden relative">
      {/* Ambient background glow orbs */}
      <div className="fixed top-0 right-1/4 w-[500px] h-[350px] bg-indigo-600/[0.04] rounded-full blur-3xl pointer-events-none" />
      <div className="fixed bottom-0 right-1/3 w-[450px] h-[350px] bg-purple-600/[0.04] rounded-full blur-3xl pointer-events-none" />

      {/* Navigation Sidebar */}
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        onLogout={handleLogout}
        username={username}
      />

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10">
        {/* Top Header Bar */}
        <header className="relative z-50 h-14 px-6 border-b border-white/[0.06] bg-slate-950/80 backdrop-blur-xl flex items-center justify-between shrink-0 shadow-xs">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400 font-medium">{t.header.gateway}</span>
            <span className="text-slate-700">/</span>
            <span className="font-semibold text-slate-200 capitalize tracking-tight px-2 py-0.5 rounded-lg bg-white/[0.04] border border-white/[0.06]">
              {activePageLabel}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-[11px] font-mono font-medium text-emerald-300 shadow-xs shadow-emerald-950/30">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span>{t.header.gatewayOnline}</span>
            </div>
            {activePage !== "playground" && (
              <button
                onClick={() => setActivePage("playground")}
                className="btn-press flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-indigo-600/20 border border-indigo-400/20 transition-all"
              >
                <TerminalSquare size={14} />
                <span>{t.nav.playground}</span>
              </button>
            )}
            <LanguageSelector variant="compact" />
          </div>
        </header>

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-6 relative content-pane">
          {activePage === "dashboard" && <DashboardPage />}
          {activePage === "analytics" && <AnalyticsPage />}
          {activePage === "providers" && <ProvidersPage />}
          {activePage === "credentials" && <CredentialsPage />}
          {activePage === "models" && <ModelsPage />}
          {activePage === "routing" && <RoutingPage />}
          {activePage === "fusion" && <FusionPage />}
          {activePage === "keys" && <ApiKeysPage />}
          {activePage === "proxies" && <ProxiesPage />}
          {activePage === "playground" && <PlaygroundPage />}
          {activePage === "logs" && <LogsPage />}
          {activePage === "settings" && <SettingsPage />}
          {activePage === "docs" && <DocsPage />}
        </main>
      </div>
    </div>
  );
};

export default App;
