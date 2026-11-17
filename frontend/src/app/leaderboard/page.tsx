"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import PublicShell from "@/components/PublicShell";
import { api, del, post, put } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Row = { rank: number; user_id: number; display_name: string; allow_copy: boolean; followers: number; trades: number; win_rate: number; avg_r: number; total_r: number };
type Me = { profile: { display_name: string; public: boolean; allow_copy: boolean } | null; following: { user_id: number; display_name: string }[]; followers: number; max_follows: number };

/** Monthly ranking of members' trades, with copy trading. */
export default function LeaderboardPage() {
  const { user } = useAuth();
  const [period, setPeriod] = useState<"month" | "90d" | "all">("month");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    setRows(null);
    api<{ rows: Row[] }>(`/api/public/leaderboard?period=${period}`).then((r) => setRows(r.rows)).catch(() => setRows([]));
  }, [period]);
  const loadMe = useCallback(() => {
    if (user) api<Me>("/api/community/profile").then(setMe).catch(() => {});
  }, [user]);
  useEffect(loadMe, [loadMe]);

  const act = async (fn: () => Promise<Me>) => {
    setMsg("");
    try {
      setMe(await fn());
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Error");
    }
  };
  const following = new Set(me?.following.map((f) => f.user_id));
  const myId = user?.id;

  return (
    <PublicShell>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
          <div>
            <h1 className="text-2xl font-semibold">Leaderboard</h1>
            <p className="mt-1 max-w-3xl text-sm text-muted">
              Members ranked by the result of their trades (from charts, trade ideas and the Move Detector), in R: multiples of the risk taken. At least 5 closed trades.
              Press <b>Copy</b> to mirror a trader&apos;s new chart trades in your account: they open and close together.
            </p>
          </div>

          {user && me && (
            <section className="rounded-xl border border-line bg-panel p-4 text-sm">
              {me.profile ? (
                <div className="flex flex-wrap items-center gap-3">
                  <span>You appear as <b>{me.profile.display_name}</b>{me.profile.public ? "" : " (hidden)"} · {me.followers} follower{me.followers === 1 ? "" : "s"}</span>
                  <label className="flex items-center gap-1.5 text-muted">
                    <input type="checkbox" checked={me.profile.public} onChange={(e) => act(() => put<Me>("/api/community/profile", { ...me.profile, public: e.target.checked }))} />
                    Show me on the leaderboard
                  </label>
                  <label className="flex items-center gap-1.5 text-muted">
                    <input type="checkbox" checked={me.profile.allow_copy} onChange={(e) => act(() => put<Me>("/api/community/profile", { ...me.profile, allow_copy: e.target.checked }))} />
                    Allow others to copy me
                  </label>
                  <span className="ml-auto text-muted">Copying {me.following.length}/{me.max_follows >= 1e6 ? "∞" : me.max_follows}{me.following.length ? `: ${me.following.map((f) => f.display_name).join(", ")}` : ""}</span>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <span>Join the leaderboard with a public name (your email is never shown):</span>
                  <input value={name} onChange={(e) => setName(e.target.value)} maxLength={24} placeholder="e.g. BreakoutHunter" className="rounded-md border border-line bg-bg px-2 py-1" />
                  <button onClick={() => act(() => put<Me>("/api/community/profile", { display_name: name, public: true, allow_copy: true }))} className="rounded-md bg-accent px-3 py-1 font-medium text-white">Join</button>
                </div>
              )}
              {msg && <p className="mt-2 text-down">{msg}</p>}
            </section>
          )}

          <div className="flex gap-1">
            {(["month", "90d", "all"] as const).map((p) => (
              <button key={p} onClick={() => setPeriod(p)} className={`rounded-full px-3 py-1 text-sm ${period === p ? "bg-accent text-white" : "bg-panel text-muted hover:text-text"}`}>
                {p === "month" ? "This month" : p === "90d" ? "90 days" : "All time"}
              </button>
            ))}
          </div>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-panel text-left text-[11px] uppercase tracking-wide text-muted">
                <tr><th className="px-3 py-2.5">#</th><th className="px-3 py-2.5">Trader</th><th className="px-3 py-2.5 text-right">Trades</th><th className="px-3 py-2.5 text-right">Win rate</th>
                  <th className="px-3 py-2.5 text-right">Avg</th><th className="px-3 py-2.5 text-right">Total</th><th className="px-3 py-2.5 text-right">Copiers</th><th className="px-3 py-2.5" /></tr>
              </thead>
              <tbody>
                {rows === null && <tr><td colSpan={8} className="px-3 py-8 text-center text-muted">Loading…</td></tr>}
                {rows?.length === 0 && <tr><td colSpan={8} className="px-3 py-8 text-center text-muted">Nobody has 5 closed trades in this period yet. Be the first!</td></tr>}
                {rows?.map((r) => (
                  <tr key={r.user_id} className="border-t border-line">
                    <td className={`tabular px-3 py-2 font-semibold ${r.rank <= 3 ? "text-amber-300" : "text-muted"}`}>{r.rank <= 3 ? ["🥇", "🥈", "🥉"][r.rank - 1] : r.rank}</td>
                    <td className="px-3 py-2 font-medium">{r.display_name}{r.user_id === myId && <span className="ml-1 text-xs text-muted">(you)</span>}</td>
                    <td className="tabular px-3 py-2 text-right">{r.trades}</td>
                    <td className="tabular px-3 py-2 text-right">{r.win_rate}%</td>
                    <td className={`tabular px-3 py-2 text-right ${r.avg_r >= 0 ? "text-up" : "text-down"}`}>{r.avg_r > 0 ? "+" : ""}{r.avg_r}R</td>
                    <td className={`tabular px-3 py-2 text-right font-semibold ${r.total_r >= 0 ? "text-up" : "text-down"}`}>{r.total_r > 0 ? "+" : ""}{r.total_r}R</td>
                    <td className="tabular px-3 py-2 text-right text-muted">{r.followers}</td>
                    <td className="px-3 py-2 text-right">
                      {!user ? (
                        <Link href="/register" className="text-xs text-accent hover:underline">Sign up to copy</Link>
                      ) : r.user_id === myId || !r.allow_copy ? null : following.has(r.user_id) ? (
                        <button onClick={() => act(() => del<Me>(`/api/community/follow/${r.user_id}`))} className="rounded-md border border-line px-2.5 py-1 text-xs text-muted hover:text-down">Stop copying</button>
                      ) : (
                        <button onClick={() => act(() => post<Me>(`/api/community/follow/${r.user_id}`, {}))} className="rounded-md bg-violet-500/20 px-2.5 py-1 text-xs font-semibold text-violet-200 hover:bg-violet-500/30">Copy</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {user && <p className="text-xs text-muted">Copied trades are followed in <Link href="/backtest?tab=copy" className="text-accent hover:underline">Backtest → Copied trades</Link>.</p>}
        </div>
      </div>
    </PublicShell>
  );
}
