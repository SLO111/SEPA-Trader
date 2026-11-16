"use client";

import Link from "next/link";
import { Fragment, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { ApiError, api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmt, pct, tone } from "@/lib/format";

type Idea = {
  id: number; date: string; symbol: string; timeframe: "SWING" | "TRADE" | "INVEST" | "SHORT"; side: "long" | "short";
  entry: number; stop: number; trim: number | null; target: number; rr: number; weight: number; score: number; reason: string; structure?: { text: string; side: "bull" | "bear" | null; step: number; defence: number | null } | null;
  status: "WAIT" | "BUY" | "TRIM" | "TARGET" | "STOPPED" | "CANCEL"; current: number | null; pnl_pct: number | null; r_multiple: number | null; closed_at: string | null;
};
type Resp = {
  updated: string | null; ideas: Idea[];
  summary: { open: number; active: number; unrealized_pct: number | null; closed: number; win_rate: number | null; avg_r: number | null; by_timeframe: Record<string, number> };
};

const TF_STYLE: Record<string, string> = {
  SWING: "bg-blue-600/80 text-white", TRADE: "bg-violet-600/80 text-white", INVEST: "bg-teal-500/80 text-white", SHORT: "bg-red-600/80 text-white",
};
const STATUS: Record<string, [string, string]> = {
  WAIT: ["WAIT", "bg-slate-500/30 text-slate-200"], BUY: ["BUY", "bg-up/80 text-white"], TRIM: ["TRIM", "bg-amber-500/80 text-black"],
  TARGET: ["TARGET ✓", "bg-emerald-600 text-white"], STOPPED: ["STOPPED", "bg-down/80 text-white"], CANCEL: ["CNCL", "bg-red-900/70 text-red-200"],
};

function RangeBar({ i }: { i: Idea }) {
  // stop on one side, target on the other; entry tick and current price marker
  const lo = Math.min(i.stop, i.target), hi = Math.max(i.stop, i.target);
  const pos = (x: number) => `${Math.min(100, Math.max(0, ((x - lo) / (hi - lo)) * 100))}%`;
  const cur = i.current ?? i.entry;
  return (
    <div className="relative mx-1 h-1.5 w-32 rounded-full bg-gradient-to-r from-red-500/50 via-slate-500/40 to-green-500/60" title={`Stop ${i.stop} · entry ${i.entry} · target ${i.target}`}>
      {i.side === "short" && <div className="absolute inset-0 rounded-full bg-gradient-to-r from-green-500/60 via-slate-500/40 to-red-500/50" />}
      <div className="absolute -top-1 h-3.5 w-px bg-white/60" style={{ left: pos(i.entry) }} />
      {i.trim && <div className="absolute -top-0.5 h-2.5 w-px bg-amber-300/80" style={{ left: pos(i.trim) }} />}
      <div className="absolute -top-1 h-3.5 w-3.5 -translate-x-1/2 rounded-full border-2 border-bg bg-white" style={{ left: pos(cur) }} />
    </div>
  );
}

function Ideas() {
  const { user } = useAuth();
  const [view, setView] = useState<"open" | "closed" | "all">("open");
  const [data, setData] = useState<Resp | null>(null);
  const [locked, setLocked] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

  const load = () =>
    api<Resp>(`/api/ideas?view=${view}`)
      .then(setData)
      .catch((e) => (e instanceof ApiError && e.status === 403 ? setLocked(e.message) : null));
  useEffect(() => {
    load();
    const id = setInterval(load, 120_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  if (locked) {
    return (
      <div className="grid h-full place-items-center p-6">
        <div className="max-w-md rounded-xl border border-amber-500/30 bg-amber-500/5 p-6 text-center">
          <h1 className="text-lg font-semibold">Trade ideas</h1>
          <p className="mt-2 text-sm text-muted">{locked}</p>
          <Link href="/billing" className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-white">See plans</Link>
        </div>
      </div>
    );
  }
  const s = data?.summary;
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1400px] p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div>
            <h1 className="text-xl font-semibold">Trade ideas</h1>
            <p className="text-sm text-muted">Generated every trading day after the close from daily, weekly and monthly trends and historical support/resistance.</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {data?.updated && <span className="text-xs text-muted">Updated for {data.updated} close</span>}
            {user?.role === "admin" && (
              <button
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  await post("/api/ideas/regenerate", {}).catch(() => {});
                  await load();
                  setBusy(false);
                }}
                className="rounded-md border border-line px-3 py-1.5 text-xs text-muted hover:text-text disabled:opacity-50"
              >
                {busy ? "Regenerating…" : "Regenerate now"}
              </button>
            )}
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
          <section className="min-w-0 rounded-xl border border-line bg-panel">
            <div className="flex gap-1 border-b border-line p-2">
              {(["open", "closed", "all"] as const).map((v) => (
                <button key={v} onClick={() => setView(v)} className={`rounded px-3 py-1 text-sm ${view === v ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}>
                  {v === "open" ? "Open ideas" : v === "closed" ? "Closed (track record)" : "All"}
                </button>
              ))}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1100px] text-sm">
                <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
                  <tr>
                    {["Ticker", "TF", "Date", "Weight", "Entry", "Current", "%", "Stop", "Trim", "Target", "R/R", "Structure", "Range", "Status"].map((h) => (
                      <th key={h} className={`px-3 py-2.5 ${["Weight", "Entry", "Current", "%", "Stop", "Trim", "Target"].includes(h) ? "text-right" : ""}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {!data && <tr><td colSpan={14} className="px-3 py-10 text-center text-muted">Loading ideas…</td></tr>}
                  {data?.ideas.length === 0 && <tr><td colSpan={14} className="px-3 py-10 text-center text-muted">No ideas here yet. New ideas are published after each trading day.</td></tr>}
                  {data?.ideas.map((i) => {
                    const move = i.current !== null ? ((i.current / i.entry - 1) * 100 * (i.side === "short" ? -1 : 1)) : null;
                    return (
                      <Fragment key={i.id}>
                        <tr onClick={() => setOpen(open === i.id ? null : i.id)} className="cursor-pointer border-t border-line hover:bg-panel-2/40">
                          <td className="px-3 py-2">
                            <Link href={`/chart?s=${encodeURIComponent(i.symbol)}`} onClick={(e) => e.stopPropagation()}
                              className={`inline-block min-w-[56px] rounded px-2 py-1 text-center text-xs font-bold ${i.side === "short" ? "bg-down/20 text-down" : "bg-up/20 text-up"}`}>
                              {i.symbol}
                            </Link>
                          </td>
                          <td className="px-3 py-2"><span className={`rounded px-2 py-1 text-[11px] font-semibold ${TF_STYLE[i.timeframe]}`}>{i.timeframe}</span></td>
                          <td className="tabular whitespace-nowrap px-3 py-2 text-muted">{i.date.slice(5)}</td>
                          <td className="tabular px-3 py-2 text-right">{i.weight}%</td>
                          <td className="tabular px-3 py-2 text-right">${fmt(i.entry)}</td>
                          <td className="tabular px-3 py-2 text-right">{i.current !== null ? `$${fmt(i.current)}` : "—"}</td>
                          <td className={`tabular px-3 py-2 text-right text-xs ${tone(i.pnl_pct ?? move)}`}>{pct(i.pnl_pct ?? move, 1)}</td>
                          <td className="tabular px-3 py-2 text-right text-down/90">${fmt(i.stop)}</td>
                          <td className="tabular px-3 py-2 text-right text-amber-300/90">{i.trim ? `$${fmt(i.trim)}` : "N/A"}</td>
                          <td className="tabular px-3 py-2 text-right text-up/90">${fmt(i.target)}</td>
                          <td className="px-3 py-2">
                            <span className={`tabular rounded px-2 py-1 text-xs font-semibold ${i.rr >= 3 ? "bg-up/80 text-white" : i.rr >= 2 ? "bg-up/40 text-white" : "bg-amber-500/60 text-black"}`}>{i.rr}</span>
                          </td>
                          <td className="px-3 py-2"><StructureBadge s={i.structure} /></td>
                          <td className="px-3 py-2"><RangeBar i={i} /></td>
                          <td className="px-3 py-2">
                            <span className={`rounded px-2 py-1 text-[11px] font-semibold ${STATUS[i.status][1]}`}>{STATUS[i.status][0]}</span>
                            {i.r_multiple !== null && i.status !== "WAIT" && <span className={`tabular ml-2 text-xs ${tone(i.r_multiple)}`}>{i.r_multiple > 0 ? "+" : ""}{i.r_multiple}R</span>}
                          </td>
                        </tr>
                        {open === i.id && (
                          <tr className="bg-panel-2/30">
                            <td colSpan={14} className="px-4 py-3 text-sm text-muted">
                              <b className="text-text">Why:</b> {i.reason} {i.side === "short" ? "Short" : "Buy"} near ${fmt(i.entry)}, stop ${fmt(i.stop)}
                              {i.trim ? `, trim part at $${fmt(i.trim)}` : ""}, target ${fmt(i.target)}. Suggested weight {i.weight}% risks about 1% of the account at the stop.
                              {i.closed_at && ` Closed ${i.closed_at}.`}
                              {i.structure?.step === 4 && i.structure.defence && ` Structure ${i.structure.text}: defend at $${fmt(i.structure.defence)} (${i.structure.side === "bull" ? "higher lows" : "lower highs"}).`}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <aside className="space-y-4">
            <section className="rounded-xl border border-line bg-panel p-4">
              <h2 className="mb-3 font-semibold">Summary</h2>
              <div className="rounded-lg bg-panel-2/60 p-3 text-center">
                <div className="text-[11px] uppercase tracking-wide text-muted">Unrealized P/L (active ideas)</div>
                <div className={`tabular text-3xl font-semibold ${tone(s?.unrealized_pct)}`}>{pct(s?.unrealized_pct, 1)}</div>
                <div className="text-xs text-muted">{s?.active ?? 0} active · {s?.open ?? 0} open</div>
              </div>
              <div className="mt-3 grid grid-cols-4 gap-1 text-center text-[11px]">
                {Object.entries(s?.by_timeframe ?? {}).map(([tf, n]) => (
                  <div key={tf} className="rounded bg-panel-2/60 py-1.5">
                    <div className="text-muted">{tf}</div>
                    <div className="tabular font-semibold">{n}</div>
                  </div>
                ))}
              </div>
            </section>
            <section className="rounded-xl border border-line bg-panel p-4">
              <h2 className="mb-2 font-semibold">Track record</h2>
              <div className="flex justify-between py-1 text-sm"><span className="text-muted">Closed ideas</span><span className="tabular">{s?.closed ?? 0}</span></div>
              <div className="flex justify-between py-1 text-sm"><span className="text-muted">Win rate</span><span className="tabular">{s?.win_rate !== null && s?.win_rate !== undefined ? `${s.win_rate}%` : "—"}</span></div>
              <div className="flex justify-between py-1 text-sm"><span className="text-muted">Average result</span><span className={`tabular ${tone(s?.avg_r)}`}>{s?.avg_r !== null && s?.avg_r !== undefined ? `${s.avg_r > 0 ? "+" : ""}${s.avg_r}R` : "—"}</span></div>
              <p className="mt-2 text-[11px] text-muted">Every idea is tracked from its publication: WAIT until the entry triggers, then TRIM at the first target, TARGET or STOPPED. Ideas that never trigger are cancelled after 10 days.</p>
            </section>
            <p className="text-[11px] text-muted">Ideas are generated automatically by rules, not by a person. For educational purposes only. Not financial advice.</p>
          </aside>
        </div>
      </div>
    </div>
  );
}

/** Structure Count 4/4: who is in control (4/4 = confirmed, 1–3 = count in progress). */
function StructureBadge({ s }: { s?: { text: string; side: "bull" | "bear" | null; step: number; defence: number | null } | null }) {
  if (!s || !s.side) return <span className="text-xs text-muted">—</span>;
  const bull = s.side === "bull";
  const done = s.step === 4;
  return (
    <span
      title={done && s.defence ? `Defence ${s.defence} (${bull ? "higher lows" : "lower highs"})` : "Count in progress"}
      className={`whitespace-nowrap rounded px-2 py-1 text-[11px] font-semibold ${done ? (bull ? "bg-up/25 text-up" : "bg-down/25 text-down") : "border border-line text-muted"}`}
    >
      {s.text}
    </span>
  );
}

export default function IdeasPage() {
  return (
    <AppShell>
      <Ideas />
    </AppShell>
  );
}
