"use client";

import { api, put } from "@/lib/api";
import { getLang, setLang, useT } from "@/lib/i18n";
import { LangSwitch } from "@/components/legal/LegalPage";
import { applyTheme, type ThemePref } from "@/lib/theme";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/AppShell";
import { useAuth } from "@/lib/auth";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const t = useT();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [terms, setTerms] = useState(false);
  const [ref, setRef] = useState("");
  useEffect(() => {
    // a referral link (?ref=CODE) is remembered on this device until the account is created
    const q = new URLSearchParams(window.location.search).get("ref");
    try {
      if (q) localStorage.setItem("vn_ref", q);
      setRef((q || localStorage.getItem("vn_ref") || "").toUpperCase());
    } catch {
      setRef((q || "").toUpperCase());
    }
  }, []);
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (isLogin) await login(email, password);
      else {
        if (!terms) throw new Error("Please accept the Terms and the Risk disclaimer.");
        await register(email, password, name, ref.trim());
      }
      // the account's preferences: theme on this device, and the page to open first
      let start = "/chart";
      try {
        const prefs = await api<{ theme: ThemePref; start_page: string; default_interval: string; lang?: "en" | "ro" }>("/api/auth/prefs");
        localStorage.setItem("vn_prefs", JSON.stringify(prefs));
        applyTheme(prefs.theme);
        if (!isLogin) put("/api/auth/prefs", { lang: getLang() }).catch(() => {}); // keep the language chosen before signing up
        else if (prefs.lang) setLang(prefs.lang);
        start = prefs.start_page || "/chart";
      } catch {
        /* defaults */
      }
      router.replace(start);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  };

  const field = "w-full rounded-md border border-line bg-bg px-3 py-2 text-sm outline-none focus:border-accent";

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center justify-center gap-4">
          <Logo />
          <span className="text-xs text-muted"><LangSwitch /></span>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-xl border border-line bg-panel p-6">
          <h1 className="text-lg font-semibold">{t(isLogin ? "Log in to your account" : "Create a free account")}</h1>
          {!isLogin && (
            <label className="block text-sm">
              <span className="mb-1 block text-muted">{t("Name")}</span>
              <input value={name} onChange={(e) => setName(e.target.value)} className={field} autoComplete="name" />
            </label>
          )}
          <label className="block text-sm">
            <span className="mb-1 block text-muted">{t("Email")}</span>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={field} autoComplete="email" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-muted">{t(isLogin ? "Password" : "Password (at least 8 characters)")}</span>
            <input
              type="password"
              required
              minLength={isLogin ? 1 : 8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={field}
              autoComplete={isLogin ? "current-password" : "new-password"}
            />
          </label>
          {!isLogin && (
            <>
              <label className="block text-sm">
                <span className="mb-1 block text-muted">{t("Referral code (optional)")}</span>
                <input value={ref} onChange={(e) => setRef(e.target.value.toUpperCase())} className={field} maxLength={16} />
              </label>
              <p className="rounded-md bg-violet-500/10 px-3 py-2 text-xs text-violet-200">✦ {t("New accounts get Premium free for 14 days")}{ref ? ` ${t("(+7 days with a referral code)")}` : ""}.</p>
              <label className="flex items-start gap-2 text-xs text-muted">
                <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-0.5" required />
                <span>
                  {t("I accept the")} <Link href="/terms" target="_blank" className="text-accent hover:underline">{t("Terms")}</Link>,{" "}
                  <Link href="/privacy" target="_blank" className="text-accent hover:underline">{t("Privacy")}</Link> {t("and the")}{" "}
                  <Link href="/disclaimer" target="_blank" className="text-accent hover:underline">{t("Risk disclaimer")}</Link>. {t("Vnicorn is an educational simulation, not investment advice.")}
                </span>
              </label>
            </>
          )}
          {error && <p className="rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
          <button disabled={busy} className="w-full rounded-md bg-accent py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60">
            {t(busy ? "Please wait…" : isLogin ? "Log in" : "Create account")}
          </button>
          <p className="text-center text-sm text-muted">
            {t(isLogin ? "Don't have an account? " : "Already have an account? ")}
            <Link href={isLogin ? "/register" : "/login"} className="text-accent hover:underline">
              {t(isLogin ? "Sign up" : "Log in")}
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
