"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import PublicShell from "@/components/PublicShell";
import { api } from "@/lib/api";

const LineChart = dynamic(() => import("@/components/markets/LineChart"), { ssr: false });

type S = { trades: number; win_rate?: number; avg_r?: number; total_r?: number; best_r?: number; worst_r?: number };
type TR = {
  since: string | null; open: number; all: S; ai_picks: S; by_timeframe: ({ timeframe: string } & S)[]; by_month: ({ month: string } & S)[];
  equity: { time: string; value: number }[]; recent: { symbol: string; timeframe: string; side: string; closed_at: string; status: string; r: number; ai_pick: boolean }[];
};

const r = (x?: number) => (x === undefined ? "—" : `${x > 0 ? "+" : ""}${x}R`);
const tone = (x?: number) => (x === undefined ? "" : x > 0 ? "text-up" : x < 0 ? "text-down" : "");

function Card({ label, s }: { label: string; s: S }) {
  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      {s.trades ? (
        <>
          <div className={`tabular text-2xl font-bold ${tone(s.avg_r)}`}>{r(s.avg_r)} <span className="text-sm font-normal text-muted">per idea</span></div>
          <div className="mt-1 text-sm text-muted">{s.trades} closed · win rate {s.win_rate}% · total <span className={tone(s.total_r)}>{r(s.total_r)}</span></div>
        </>
      ) : (
        <div className="mt-1 text-sm text-muted">No closed ideas yet.</div>
      )}
    </div>
  );
}

/** Public track record of the daily (simulated) trade ideas: every closed idea, counted as a 1R risk. */
export default function TrackRecordPage() {
  const [d, setD] = useState<TR | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api<TR>("/api/public/track-record").then(setD).catch((e) => setErr(e.message));
  }, []);
  return (
    <PublicShell>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
          <div>
            <h1 className="text-2xl font-semibold">Track record</h1>
            <p className="mt-1 max-w-3xl text-sm text-muted">
              Every trade idea Vnicorn published after the close, followed to its stop or target automatically. Each idea counts as risking 1R (the distance to its stop), so
              +3R means three times the risk was won. <b>Simulated results</b>: no slippage, fees or taxes. Past results do not guarantee future results.
            </p>
          </div>
          {err && <p className="text-sm text-down">{err}</p>}
          {!d && !err && <p className="text-sm text-muted">Loading…</p>}
          {d && (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <Card label="All ideas" s={d.all} />
                <Card label="✦ vnicornAI picks" s={d.ai_picks} />
                <div className="rounded-xl border border-line bg-panel p-4 text-sm">
                  <div className="text-[11px] uppercase tracking-wide text-muted">Running</div>
                  <div className="text-2xl font-bold">{d.open}</div>
                  <div className="text-muted">open ideas{d.since ? ` · published since ${d.since}` : ""}</div>
                </div>
              </div>
              {d.equity.length > 1 && (
                <section className="rounded-xl border border-line bg-panel p-4">
                  <h2 className="mb-2 font-semibold">Cumulative result (R)</h2>
                  <LineChart series={[{ name: "Total R", color: "#8b5cf6", data: d.equity }]} height={260} suffix="R" />
                </section>
              )}
              <div className="grid gap-4 lg:grid-cols-2">
                <section className="rounded-xl border border-line bg-panel p-4">
                  <h2 className="mb-2 font-semibold">By month</h2>
                  <table className="w-full text-sm">
                    <thead className="text-left text-[11px] uppercase tracking-wide text-muted"><tr><th className="py-1">Month</th><th className="py-1 text-right">Ideas</th><th className="py-1 text-right">Win rate</th><th className="py-1 text-right">Total</th></tr></thead>
                    <tbody>
                      {[...d.by_month].reverse().map((m) => (
                        <tr key={m.month} className="border-t border-line">
                          <td className="tabular py-1">{m.month}</td><td className="tabular py-1 text-right">{m.trades}</td>
                          <td className="tabular py-1 text-right">{m.win_rate}%</td><td className={`tabular py-1 text-right font-medium ${tone(m.total_r)}`}>{r(m.total_r)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
                <section className="rounded-xl border border-line bg-panel p-4">
                  <h2 className="mb-2 font-semibold">By timeframe</h2>
                  <table className="w-full text-sm">
                    <thead className="text-left text-[11px] uppercase tracking-wide text-muted"><tr><th className="py-1">Type</th><th className="py-1 text-right">Ideas</th><th className="py-1 text-right">Win rate</th><th className="py-1 text-right">Avg</th></tr></thead>
                    <tbody>
                      {d.by_timeframe.map((m) => (
                        <tr key={m.timeframe} className="border-t border-line">
                          <td className="py-1">{m.timeframe}</td><td className="tabular py-1 text-right">{m.trades}</td>
                          <td className="tabular py-1 text-right">{m.win_rate}%</td><td className={`tabular py-1 text-right font-medium ${tone(m.avg_r)}`}>{r(m.avg_r)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <h3 className="mb-1 mt-4 text-sm font-semibold">Latest closed</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {d.recent.map((x) => (
                      <span key={x.symbol + x.closed_at} className="tabular rounded bg-panel-2 px-2 py-0.5 text-xs" title={`${x.status} on ${x.closed_at}`}>
                        {x.ai_pick && "✦ "}{x.symbol} <span className={tone(x.r)}>{r(x.r)}</span>
                      </span>
                    ))}
                  </div>
                </section>
              </div>
              <p className="text-sm">
                Want the ideas every evening? <Link href="/register" className="text-accent hover:underline">Create a free account</Link> (Premium free for 14 days).
              </p>
            </>
          )}
        </div>
      </div>
    </PublicShell>
  );
}
