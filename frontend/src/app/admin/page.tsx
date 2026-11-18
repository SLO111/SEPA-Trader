"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, clearApiCache, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { User } from "@/lib/types";

type Stats = {
  total_users: number; by_plan: Record<string, number>; new_users_30d: number; mrr: number; arr: number; active_subscriptions: number;
  past_due: number; canceling: number; revenue_30d: number; failed_payments_30d: number; churned_30d: number;
  recent_payments: { date: string; email: string | null; amount: number; currency: string; status: string }[];
};
type NewsLevel = { id: string; label: string; help: string; keep_days: number };

function NewsSetting() {
  const [s, setS] = useState<{ news_level: string; news_levels: NewsLevel[] } | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    api<{ news_level: string; news_levels: NewsLevel[] }>("/api/admin/settings").then(setS).catch(() => {});
  }, []);
  if (!s) return null;
  const choose = async (id: string) => {
    setS(await patch<typeof s>("/api/admin/settings", { news_level: id }));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };
  const cur = s.news_levels.find((l) => l.id === s.news_level);
  return (
    <div className="mb-8 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">News in the feed</h2>
          <p className="text-xs text-muted">Fewer headlines means less work for the server (fetching, tagging and storing).</p>
        </div>
        <div className="flex gap-1 rounded-lg bg-panel-2 p-1">
          {s.news_levels.map((l) => (
            <button key={l.id} onClick={() => choose(l.id)}
              className={`rounded-md px-3 py-1 text-sm ${l.id === s.news_level ? "bg-accent text-white" : "text-muted hover:text-text"}`}>
              {l.label}
            </button>
          ))}
        </div>
      </div>
      {cur && (
        <p className="mt-2 text-xs text-muted">
          {cur.help} Headlines older than {cur.keep_days} days are removed.{saved && <span className="ml-2 text-up">Saved.</span>}
        </p>
      )}
    </div>
  );
}

type Regen = { running: boolean; generated: number | null; scanned: number | null; error: string | null; finished_at: string | null };

/** Admin only: rebuild Move Detector and today's trade ideas (vnicornAI ratings included) from the last close.
 *  Everyone else gets them automatically after each market close. */
function RegenerateSignals() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => {
    api<Regen>("/api/ideas/regenerate").then((st) => st.running && setMsg("A regeneration is already running…")).catch(() => {});
  }, []);
  const run = async () => {
    setBusy(true);
    setMsg("Regenerating Move Detector and trade ideas from the last close… this takes a minute or two.");
    try {
      await post("/api/ideas/regenerate", {});
      for (let i = 0; i < 120; i++) {
        await new Promise((r) => setTimeout(r, 5000));
        clearApiCache();
        const st = await api<Regen>("/api/ideas/regenerate");
        if (!st.running) {
          setMsg(st.error ? `Failed: ${st.error}` : `Done: Move Detector rescanned ${st.scanned ?? 0} stocks, ${st.generated ?? 0} new trade ideas.`);
          break;
        }
      }
      clearApiCache();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mb-8 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">Regenerate signals</h2>
          <p className="text-xs text-muted">
            Rebuilds Move Detector and the trade ideas (with vnicornAI) from the last market close. Users get them automatically after each close.
          </p>
        </div>
        <button onClick={run} disabled={busy} className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
          {busy ? "Regenerating…" : "Regenerate now"}
        </button>
      </div>
      {msg && <p className="mt-2 text-xs text-muted">{msg}</p>}
    </div>
  );
}

const money = (v: number) => v.toLocaleString("en-US", { style: "currency", currency: "USD" });

function AdminPanel() {
  const { user: me, refresh } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");

  const load = () => {
    api<Stats>("/api/admin/stats").then(setStats).catch((e) => setError(e.message));
    api<User[]>("/api/admin/users").then(setUsers).catch((e) => setError(e.message));
  };
  useEffect(load, []);

  const update = async (id: number, body: Partial<Pick<User, "plan" | "role" | "is_active">>) => {
    setError("");
    try {
      const u = await patch<User>(`/api/admin/users/${id}`, body);
      setUsers((us) => us.map((x) => (x.id === id ? u : x)));
      api<Stats>("/api/admin/stats").then(setStats);
      if (id === me?.id) await refresh(); // your own plan: the badge and the paywall update right away
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  const tiles = stats
    ? [
        { label: "MRR", value: money(stats.mrr), sub: `ARR ${money(stats.arr)}` },
        { label: "Revenue (30 days)", value: money(stats.revenue_30d), sub: `${stats.failed_payments_30d} failed payment${stats.failed_payments_30d === 1 ? "" : "s"}` },
        { label: "Active subscriptions", value: stats.active_subscriptions, sub: `${stats.past_due} past due · ${stats.canceling} canceling` },
        { label: "Churned (30 days)", value: stats.churned_30d, sub: "Subscriptions canceled" },
        { label: "Users", value: stats.total_users, sub: `+${stats.new_users_30d} in 30 days` },
        { label: "Free", value: stats.by_plan.free },
        { label: "Pro", value: stats.by_plan.pro },
        { label: "Premium", value: stats.by_plan.premium },
      ]
    : [];

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl p-4 sm:p-6">
        <h1 className="mb-6 text-xl font-semibold">Admin panel</h1>
        <RegenerateSignals />
        <NewsSetting />
        <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
          {tiles.map((t) => (
            <div key={t.label} className="rounded-xl border border-line bg-panel p-4">
              <div className="text-xs text-muted">{t.label}</div>
              <div className="tabular mt-1 text-2xl font-semibold">{t.value}</div>
              {"sub" in t && t.sub && <div className="text-xs text-muted">{t.sub}</div>}
            </div>
          ))}
        </div>
        {stats && stats.recent_payments.length > 0 && (
          <div className="mb-8 overflow-x-auto rounded-xl border border-line">
            <h2 className="px-4 pt-3 font-semibold">Recent payments</h2>
            <table className="mt-2 w-full text-sm">
              <tbody>
                {stats.recent_payments.map((p, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="tabular px-4 py-2 text-muted">{new Date(p.date).toLocaleDateString("en-US")}</td>
                    <td className="px-4 py-2">{p.email ?? "—"}</td>
                    <td className="tabular px-4 py-2 text-right">{money(p.amount)}</td>
                    <td className={`px-4 py-2 text-right ${p.status === "paid" ? "text-up" : "text-down"}`}>{p.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {error && <p className="mb-4 rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
        <p className="mb-2 text-xs text-muted">Change any user&apos;s plan here. Change your own plan to test what Free / Pro / Premium users see (you stay an administrator).</p>
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full text-sm">
            <thead className="bg-panel text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Plan</th>
                <th className="px-4 py-3">Subscription</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Active</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-line">
                  <td className="px-4 py-2.5">{u.email}</td>
                  <td className="px-4 py-2.5 text-muted">{u.name || "—"}</td>
                  <td className="px-4 py-2.5">
                    <select value={u.plan} onChange={(e) => update(u.id, { plan: e.target.value as User["plan"] })} className="rounded border border-line bg-bg px-2 py-1">
                      <option value="free">Free</option>
                      <option value="pro">Pro</option>
                      <option value="premium">Premium</option>
                    </select>
                  </td>
                  <td className="px-4 py-2.5 text-xs">
                    <span className={u.subscription_status === "active" ? "text-up" : u.subscription_status === "past_due" ? "text-down" : "text-muted"}>
                      {u.subscription_status && u.subscription_status !== "none" ? u.subscription_status : "—"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <select
                      value={u.role}
                      disabled={u.id === me?.id}
                      onChange={(e) => update(u.id, { role: e.target.value as User["role"] })}
                      className="rounded border border-line bg-bg px-2 py-1 disabled:opacity-50"
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  </td>
                  <td className="px-4 py-2.5">
                    <input
                      type="checkbox"
                      checked={u.is_active ?? true}
                      disabled={u.id === me?.id}
                      onChange={(e) => update(u.id, { is_active: e.target.checked })}
                      className="accent-blue-500"
                    />
                  </td>
                  <td className="tabular px-4 py-2.5 text-muted">{new Date(u.created_at).toLocaleDateString("en-US")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function AdminPage() {
  return (
    <AppShell adminOnly>
      <AdminPanel />
    </AppShell>
  );
}
