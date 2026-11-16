"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { pct, tone } from "@/lib/format";

const LineChart = dynamic(() => import("@/components/markets/LineChart"), { ssr: false });

type A = {
  trades: number; win_rate?: number; avg_win_pct?: number; avg_loss_pct?: number; win_loss_ratio?: number | null; expectancy_pct?: number;
  profit_factor?: number | null; capture_pct?: number | null; largest_win_pct?: number; largest_loss_pct?: number; max_win_streak?: number; max_loss_streak?: number;
  profitable_months_pct?: number | null; months?: { month: string; trades: number; pnl_pct: number; win_rate: number }[];
  equity?: { date: string; value: number }[]; histogram?: { key: string; value: number }[];
};

function Stat({ label, value, cls = "", hint }: { label: string; value: string; cls?: string; hint: string }) {
  return (
    <div className="rounded-xl border border-line bg-panel p-3" title={hint}>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className={`tabular text-xl font-semibold ${cls}`}>{value}</div>
      <div className="mt-0.5 text-[11px] leading-tight text-muted">{hint}</div>
    </div>
  );
}

/** Trading statistics over your closed trades: expectancy, win/loss efficiency, consistency by month. */
export default function TradeAnalytics({ chartOnly = false }: { chartOnly?: boolean }) {
  const [source, setSource] = useState(chartOnly ? "chart" : "all");
  const [pf, setPf] = useState<number | "">("");
  const [portfolios, setPortfolios] = useState<{ id: number; name: string }[]>([]);
  useEffect(() => {
    api<{ id: number; name: string }[]>("/api/portfolios").then(setPortfolios).catch(() => {});
  }, []);
  const pid = source === "portfolio" && pf !== "" ? pf : undefined;
  const [a, setA] = useState<A | null>(null);
  useEffect(() => {
    setA(null);
    api<A>(`/api/analytics?source=${source}${pid ? `&portfolio_id=${pid}` : ""}`).then(setA).catch(() => setA({ trades: 0 }));
  }, [source, pid]);
  const max = Math.max(1, ...(a?.histogram ?? []).map((h) => h.value));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1">
        {(chartOnly ? [["chart", "Charts"], ["portfolio", "Portfolios"]] : [["all", "All trades"], ["ideas", "Trade ideas"], ["md", "Move Detector"], ["chart", "Charts"], ["portfolio", "Portfolios"]]).map(([id, label]) => (
          <button key={id} onClick={() => setSource(id)} className={`rounded-full px-3 py-1 text-sm ${source === id ? "bg-accent text-white" : "bg-panel text-muted hover:text-text"}`}>
            {label}
          </button>
        ))}
{source === "portfolio" && portfolios.length > 0 && (
          <select value={pf} onChange={(e) => setPf(e.target.value === "" ? "" : Number(e.target.value))}
            className="ml-1 rounded-full border border-line bg-panel px-3 py-1 text-sm text-text">
            <option value="">All portfolios</option>
            {portfolios.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        )}
      </div>
      {!a && <p className="text-sm text-muted">Calculating…</p>}
      {a && a.trades === 0 && <p className="rounded-xl border border-line bg-panel p-6 text-center text-sm text-muted">Statistics appear once you have closed trades.</p>}
      {a && a.trades > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <Stat label="Expectancy" value={pct(a.expectancy_pct)} cls={tone(a.expectancy_pct)} hint="Average result per trade" />
            <Stat label="Win rate" value={`${a.win_rate}%`} hint={`${a.trades} closed trades`} />
            <Stat label="Avg gain / loss" value={`${pct(a.avg_win_pct, 1)} / ${pct(a.avg_loss_pct, 1)}`} hint="Average winner vs. average loser" />
            <Stat label="Win/loss ratio" value={a.win_loss_ratio ? `${a.win_loss_ratio}×` : "—"} cls={(a.win_loss_ratio ?? 0) >= 2 ? "text-up" : ""} hint="Above 2× is a strong edge" />
            <Stat label="Profit factor" value={a.profit_factor ? `${a.profit_factor}` : "—"} cls={(a.profit_factor ?? 0) >= 1.5 ? "text-up" : ""} hint="Total gains ÷ total losses" />
            <Stat label="Gain captured" value={a.capture_pct ? `${a.capture_pct}%` : "—"} hint="Of the best open gain, on winners" />
            <Stat label="Largest win" value={pct(a.largest_win_pct)} cls="text-up" hint="Single best trade" />
            <Stat label="Largest loss" value={pct(a.largest_loss_pct)} cls="text-down" hint="Keep it small" />
            <Stat label="Win streak" value={`${a.max_win_streak}`} hint="Longest run of winners" />
            <Stat label="Loss streak" value={`${a.max_loss_streak}`} hint="Longest run of losers" />
            <Stat label="Profitable months" value={a.profitable_months_pct !== null && a.profitable_months_pct !== undefined ? `${a.profitable_months_pct}%` : "—"} hint="Consistency" />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="rounded-xl border border-line bg-panel p-4">
              <h3 className="mb-2 text-sm font-semibold">Cumulative result (% per trade, added up)</h3>
              <LineChart series={[{ name: "Cumulative %", color: "#8b5cf6", data: (a.equity ?? []).map((e) => ({ time: e.date, value: e.value })) }]} height={220} suffix="%" />
            </section>
            <section className="rounded-xl border border-line bg-panel p-4">
              <h3 className="mb-2 text-sm font-semibold">Distribution of results (%)</h3>
              <div className="flex h-[220px] items-end gap-1">
                {(a.histogram ?? []).map((h) => (
                  <div key={h.key} className="flex flex-1 flex-col items-center justify-end gap-1" title={`${h.key}%: ${h.value} trades`}>
                    <span className="tabular text-[10px] text-muted">{h.value || ""}</span>
                    <div className={`w-full rounded-t ${h.key.startsWith("-") || h.key.startsWith("<") ? "bg-down/70" : "bg-up/70"}`} style={{ height: `${(h.value / max) * 170}px` }} />
                    <span className="h-8 origin-top-left translate-x-2 rotate-45 whitespace-nowrap text-[9px] text-muted">{h.key}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
          <section className="overflow-x-auto rounded-xl border border-line bg-panel p-4">
            <h3 className="mb-2 text-sm font-semibold">By month</h3>
            <table className="w-full text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
                <tr><th className="py-1.5">Month</th><th className="py-1.5 text-right">Trades</th><th className="py-1.5 text-right">Win rate</th><th className="py-1.5 text-right">Result</th></tr>
              </thead>
              <tbody>
                {(a.months ?? []).slice().reverse().map((m) => (
                  <tr key={m.month} className="border-t border-line">
                    <td className="tabular py-1.5">{m.month}</td>
                    <td className="tabular py-1.5 text-right">{m.trades}</td>
                    <td className="tabular py-1.5 text-right">{m.win_rate}%</td>
                    <td className={`tabular py-1.5 text-right font-medium ${tone(m.pnl_pct)}`}>{pct(m.pnl_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
