"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import NotificationsCard from "@/components/alerts/NotificationsCard";
import { api, patch, post, put } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { applyTheme, getThemePref, type ThemePref } from "@/lib/theme";

type Prefs = { theme: ThemePref; default_interval: string; start_page: string; compact_tables: boolean };
type Sub = { status: string; plan: string; interval?: string | null; amount?: number; current_period_end?: string | null; cancel_at_period_end?: boolean };
type Digest = { enabled: boolean; email: string; email_configured: boolean };

function Section({ id, title, desc, children }: { id: string; title: string; desc?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 rounded-xl border border-line bg-panel p-5">
      <h2 className="font-semibold">{title}</h2>
      {desc && <p className="mb-4 mt-0.5 text-sm text-muted">{desc}</p>}
      {!desc && <div className="mb-4" />}
      {children}
    </section>
  );
}

const input = "w-full rounded-md border border-line bg-bg px-3 py-2 text-sm outline-none focus:border-accent";
const btn = "rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40";

function Msg({ m }: { m: { ok: boolean; text: string } | null }) {
  if (!m) return null;
  return <p className={`mt-2 text-sm ${m.ok ? "text-up" : "text-down"}`}>{m.text}</p>;
}

function Settings() {
  const { user, refresh, logout } = useAuth();
  const router = useRouter();
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [emailPw, setEmailPw] = useState("");
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [sub, setSub] = useState<Sub | null>(null);
  const [digest, setDigest] = useState<Digest | null>(null);
  const [delPw, setDelPw] = useState("");
  const [msgs, setMsgs] = useState<Record<string, { ok: boolean; text: string } | null>>({});
  const say = (k: string, ok: boolean, text: string) => setMsgs((m) => ({ ...m, [k]: { ok, text } }));
  const err = (e: unknown) => (e instanceof Error ? e.message : String(e));

  useEffect(() => {
    api<Prefs>("/api/auth/prefs").then((p) => setPrefs({ ...p, theme: getThemePref() || p.theme })).catch(() => {});
    api<{ subscription: Sub }>("/api/billing/plans").then((r) => setSub(r.subscription)).catch(() => {});
    api<Digest>("/api/feed/digest").then(setDigest).catch(() => {});
  }, []);

  const savePrefs = async (patchP: Partial<Prefs>) => {
    if (!prefs) return;
    const next = { ...prefs, ...patchP };
    setPrefs(next);
    if (patchP.theme) applyTheme(patchP.theme);
    try {
      localStorage.setItem("vn_prefs", JSON.stringify(next));
    } catch {
      /* ignore */
    }
    try {
      await put("/api/auth/prefs", patchP);
      say("prefs", true, "Saved");
    } catch (e) {
      say("prefs", false, err(e));
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto grid max-w-5xl gap-6 p-3 sm:p-6 md:grid-cols-[180px_1fr]">
        <nav className="top-4 hidden h-fit space-y-0.5 text-sm md:sticky md:block">
          {[["profile", "Profile"], ["security", "Password"], ["appearance", "Appearance"], ["preferences", "Preferences"], ["notifications", "Notifications"], ["subscription", "Subscription"], ["danger", "Delete account"]].map(([id, label]) => (
            <a key={id} href={`#${id}`} className="block rounded px-3 py-1.5 text-muted hover:bg-panel-2 hover:text-text">{label}</a>
          ))}
        </nav>
        <div className="space-y-5">
          <h1 className="text-xl font-semibold">Settings</h1>

          <Section id="profile" title="Profile">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="text-xs text-muted">Name</label>
                <div className="mt-1 flex gap-2">
                  <input value={name} onChange={(e) => setName(e.target.value)} className={input} />
                  <button className={btn} disabled={!name.trim() || name === user?.name} onClick={async () => {
                    try { await patch("/api/auth/me", { name }); await refresh(); say("name", true, "Name updated"); } catch (e) { say("name", false, err(e)); }
                  }}>Save</button>
                </div>
                <Msg m={msgs.name ?? null} />
              </div>
              <div>
                <label className="text-xs text-muted">Email</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={`${input} mt-1`} />
                {email !== user?.email && (
                  <div className="mt-2 flex gap-2">
                    <input type="password" placeholder="Your password, to confirm" value={emailPw} onChange={(e) => setEmailPw(e.target.value)} className={input} />
                    <button className={btn} disabled={!emailPw} onClick={async () => {
                      try { await post("/api/auth/email", { password: emailPw, new_email: email }); setEmailPw(""); await refresh(); say("email", true, "Email updated"); } catch (e) { say("email", false, err(e)); }
                    }}>Change</button>
                  </div>
                )}
                <Msg m={msgs.email ?? null} />
              </div>
            </div>
          </Section>

          <Section id="security" title="Password" desc="At least 8 characters.">
            <div className="grid gap-3 sm:grid-cols-3">
              <input type="password" placeholder="Current password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} className={input} />
              <input type="password" placeholder="New password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} className={input} />
              <input type="password" placeholder="Repeat new password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} className={input} />
            </div>
            {pw.confirm && pw.next !== pw.confirm && <p className="mt-2 text-sm text-down">The new passwords don&apos;t match.</p>}
            <button className={`${btn} mt-3`} disabled={!pw.current || pw.next.length < 8 || pw.next !== pw.confirm} onClick={async () => {
              try { await post("/api/auth/password", { current_password: pw.current, new_password: pw.next }); setPw({ current: "", next: "", confirm: "" }); say("pw", true, "Password changed"); } catch (e) { say("pw", false, err(e)); }
            }}>Change password</button>
            <Msg m={msgs.pw ?? null} />
          </Section>

          <Section id="appearance" title="Appearance" desc="Choose a theme. System follows your device's light or dark setting.">
            <div className="grid grid-cols-3 gap-3 sm:max-w-md">
              {(["dark", "light", "system"] as ThemePref[]).map((t) => (
                <button key={t} onClick={() => savePrefs({ theme: t })}
                  className={`rounded-xl border p-3 text-sm capitalize ${prefs?.theme === t ? "border-accent ring-1 ring-accent" : "border-line hover:border-muted"}`}>
                  <span className={`mb-2 block h-10 rounded-md border border-line ${t === "dark" ? "bg-[#0b0e14]" : t === "light" ? "bg-[#f4f6fa]" : "bg-gradient-to-r from-[#0b0e14] to-[#f4f6fa]"}`} />
                  {t}
                </button>
              ))}
            </div>
          </Section>

          <Section id="preferences" title="Preferences">
            {prefs && (
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="text-xs text-muted">
                  Default chart timeframe
                  <select value={prefs.default_interval} onChange={(e) => savePrefs({ default_interval: e.target.value })} className={`${input} mt-1`}>
                    {[["5m", "5 minutes"], ["15m", "15 minutes"], ["1h", "1 hour"], ["1d", "1 day"], ["1wk", "1 week"], ["1mo", "1 month"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </label>
                <label className="text-xs text-muted">
                  Page to open after logging in
                  <select value={prefs.start_page} onChange={(e) => savePrefs({ start_page: e.target.value })} className={`${input} mt-1`}>
                    {[["/chart", "Charts"], ["/markets", "Markets"], ["/ideas", "Trade ideas"], ["/portfolios", "Portfolio"], ["/feed", "Alerts & feed"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </label>
              </div>
            )}
            <Msg m={msgs.prefs ?? null} />
          </Section>

          <Section id="notifications" title="Notifications" desc="Where alerts are sent, and the daily summary email.">
            {digest && (
              <label className="mb-4 flex items-center gap-2 text-sm">
                <input type="checkbox" checked={digest.enabled} className="accent-blue-500" onChange={async (e) => {
                  try { setDigest(await put<Digest>("/api/feed/digest", { enabled: e.target.checked })); } catch (x) { say("digest", false, err(x)); }
                }} />
                Email me the daily summary after each trading day
              </label>
            )}
            {user?.limits.alerts ? <NotificationsCard /> : <p className="text-sm text-muted">Alert notifications are part of the Pro and Premium plans.</p>}
          </Section>

          <Section id="subscription" title="Subscription">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span>Plan: <b>{user?.limits.label}</b></span>
              {sub && sub.status !== "none" && (
                <span className="text-muted">
                  {sub.amount ? `$${sub.amount}/${sub.interval}` : ""} ·{" "}
                  {sub.cancel_at_period_end
                    ? `cancelled: access until ${sub.current_period_end?.slice(0, 10)}, no further charges`
                    : `renews on ${sub.current_period_end?.slice(0, 10) ?? "—"}`}
                </span>
              )}
              <Link href="/billing" className="ml-auto rounded-md border border-line px-3 py-1.5 text-muted hover:text-text">Change plan</Link>
            </div>
            {sub && ["active", "trialing", "past_due"].includes(sub.status) && (
              <div className="mt-4 rounded-lg border border-line bg-panel-2/40 p-3">
                {sub.cancel_at_period_end ? (
                  <>
                    <p className="text-sm">Your subscription ends on <b>{sub.current_period_end?.slice(0, 10)}</b>. You won&apos;t be charged again.</p>
                    <button className={`${btn} mt-2`} onClick={async () => {
                      try { setSub(await post<Sub>("/api/billing/cancel", { resume: true })); say("sub", true, "Your subscription continues"); } catch (e) { say("sub", false, err(e)); }
                    }}>Keep my subscription</button>
                  </>
                ) : (
                  <>
                    <p className="text-sm text-muted">Cancel anytime: you keep full access until the end of the period you&apos;ve paid for, and you won&apos;t be charged again.</p>
                    <button className="mt-2 rounded-md border border-down/50 px-4 py-2 text-sm text-down hover:bg-down/10" onClick={async () => {
                      if (!confirm("Cancel your subscription? You keep access until the end of the current period and won't be charged again.")) return;
                      try { setSub(await post<Sub>("/api/billing/cancel", {})); say("sub", true, "Subscription cancelled: no charge next period"); } catch (e) { say("sub", false, err(e)); }
                    }}>Cancel subscription</button>
                  </>
                )}
              </div>
            )}
            <Msg m={msgs.sub ?? null} />
          </Section>

          <Section id="danger" title="Delete account" desc="Deletes your account, watchlists, portfolios, trades and alerts. This can't be undone. Cancel any paid subscription first.">
            <div className="flex flex-wrap gap-2">
              <input type="password" placeholder="Your password" value={delPw} onChange={(e) => setDelPw(e.target.value)} className={`${input} max-w-xs`} />
              <button disabled={!delPw} className="rounded-md bg-down px-4 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-40" onClick={async () => {
                if (!confirm("Delete your account permanently?")) return;
                try {
                  await api("/api/auth/me", { method: "DELETE", body: JSON.stringify({ password: delPw }) });
                  logout();
                  router.replace("/");
                } catch (e) { say("del", false, err(e)); }
              }}>Delete my account</button>
            </div>
            <Msg m={msgs.del ?? null} />
          </Section>
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <AppShell>
      <Settings />
    </AppShell>
  );
}
