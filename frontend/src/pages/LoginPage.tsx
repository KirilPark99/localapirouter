import React, { useState } from "react";
import { Sparkles, AlertCircle, ArrowRight } from "lucide-react";
import { apiRequest } from "../api/client";
import { useI18n } from "../i18n/context";
import { LanguageSelector } from "../components/LanguageSelector";

interface LoginPageProps {
  onLoginSuccess: (username: string) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const data = await apiRequest<{ access_token: string; username: string }>(
        "/api/admin/auth/login",
        {
          method: "POST",
          body: JSON.stringify({ username, password }),
        }
      );
      localStorage.setItem("myairouter_token", data.access_token);
      onLoginSuccess(data.username);
    } catch (err: any) {
      setError(err.message || t.login.loginFailed);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#080c14] flex flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* Top right language selector */}
      <div className="absolute top-5 right-5 z-20">
        <LanguageSelector variant="compact" />
      </div>

      {/* Background ambient lighting */}
      <div className="absolute top-1/4 -left-20 w-96 h-96 bg-indigo-600/15 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-purple-600/15 rounded-full blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md glass-card card-specular rounded-3xl p-8 shadow-2xl shadow-black/80 relative z-10 border border-white/[0.08]">
        <div className="flex items-center gap-3.5 mb-6">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-indigo-500 via-violet-500 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 ring-1 ring-white/20">
            <Sparkles size={22} className="animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
                MyAIrouter
              </h1>
              <span className="text-[9px] font-mono tracking-wider font-bold uppercase px-1.5 py-0.5 rounded-full bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                Gateway
              </span>
            </div>
            <p className="text-xs text-slate-400 font-medium mt-0.5">{t.login.tagline}</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs rounded-xl flex items-center gap-2.5">
            <AlertCircle size={16} className="shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              {t.login.username}
            </label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-950/70 border border-white/[0.08] rounded-xl text-slate-100 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all font-mono placeholder:text-slate-600"
              placeholder="Configured admin username"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">
              {t.login.password}
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-950/70 border border-white/[0.08] rounded-xl text-slate-100 text-sm focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all font-mono placeholder:text-slate-600"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 text-white font-semibold text-sm rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/25 border border-indigo-400/20 btn-press mt-2"
          >
            {loading ? t.login.signingIn : t.login.loginBtn}
            <ArrowRight size={16} />
          </button>
        </form>

        <div className="mt-6 pt-4 border-t border-white/[0.06] text-center">
          <p className="text-[11px] text-slate-400">
            {t.login.defaultCredentialsNotice}
          </p>
        </div>
      </div>
    </div>
  );
};
