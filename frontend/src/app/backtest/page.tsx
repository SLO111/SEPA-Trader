"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import PaperTrades from "@/components/PaperTrades";
import TradeAnalytics from "@/components/TradeAnalytics";
import TradeGrader from "@/components/TradeGrader";
import RulesBuilder from "@/components/backtest/RulesBuilder";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmt, pct, tone } from "@/lib/format";
import type { StrategyDef } from "@/lib/types";

const LineChart = dynamic(() => import("@/components/markets/LineChart"), { ssr: false });

type StratResult = {
  symbol: string; strategy: string; reason?: string;
  stats: { trades: number; win_rate?: number; avg_return_pct?: number; total_return_pct?: number; buy_hold_return_pct?: number; cagr_pct?: number; buy_hold_cagr_pct?: number; max_drawdown_pct?: number; buy_hold_max_drawdown_pct?: number; time_in_market_pct?: number; avg_days?: number };
  trades: { entry_date: string; entry: number; exit_date: string; exit: number; return_pct: number; days: number; open: boolean }[];
  equity: { time: string; value: number }[]; buy_hold: { time: string; value: number }[];
};

function StrategyBacktest() {
  const [strats, setStrats] = useState<StrategyDef[]>([]);
  const [symbol, setSymbol] = useState("AAPL");
  const [sid, setSid] = useState("");
  const [params, setParams] = useState<Record<string, number>>({});
  const [fees, setFees] = useState("0.05");
  const [res, setRes] = useState<StratResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<StrategyDef[]>("/api/backtest/strategies").then((s) => {
      setStrats(s);
      if (s[0]) {
        setSid(s[0].id);
        setParams(Object.fromEntries(s[0].params.map((p) => [p.key, p.default])));
      }
    });
  }, []);
  const def = strats.find((s) => s.id === sid);
  const series = useMemo(
    () => (res ? [{ name: "Strategy", color: "#3b82f6", data: res.equity }, { name: "Buy & hold", color: "#64748b", data: res.buy_hold, width: 1 as const }] : []),
    [res],
  );

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setRes(await post<StratResult>("/api/backtest/strategy", { symbol, strategy: sid, params, fees_pct: Number(fees) || 0 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  };
  const s = res?.stats;
  const input = "rounded border border-line bg-bg px-2 py-1.5 text-sm outline-none focus:border-accent";
  return (
    <div className="space-y-5">
      <form onSubmit={run} className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-panel p-4 text-sm">
        <label className="text-xs text-muted">Symbol<input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} className={`${input} mt-1 block w-24`} /></label>
        <label className="text-xs text-muted">
          Strategy
          <select value={sid} onChange={(e) => { setSid(e.target.value); const d = strats.find((x) => x.id === e.target.value); setParams(Object.fromEntries((d?.params ?? []).map((p) => [p.key, p.default]))); }} className={`${input} mt-1 block`}>
            {strats.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        {def?.params.map((p) => (
          <label key={p.key} className="text-xs text-muted">{p.label}<input type="number" min={p.min} max={p.max} step={p.step} value={params[p.key] ?? p.default} onChange={(e) => setParams({ ...params, [p.key]: Number(e.target.value) })} className={`${input} mt-1 block w-20`} /></label>
        ))}
        <label className="text-xs text-muted">Fees per side %<input type="number" min="0" step="0.01" value={fees} onChange={(e) => setFees(e.target.value)} className={`${input} mt-1 block w-20`} /></label>
        <button disabled={busy || !sid} className="rounded-md bg-accent px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:opacity-60">{busy ? "Running…" : "Run backtest"}</button>
      </form>
      {error && <p className="text-sm text-down">{error}</p>}
      {res && (
        res.reason ? <p className="text-sm text-muted">{res.reason}</p> : (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {[
                ["Total return", pct(s!.total_return_pct), `Buy & hold ${pct(s!.buy_hold_return_pct)}`, tone(s!.total_return_pct)],
                ["CAGR", pct(s!.cagr_pct), `Buy & hold ${pct(s!.buy_hold_cagr_pct)}`, tone(s!.cagr_pct)],
                ["Max drawdown", pct(s!.max_drawdown_pct), `Buy & hold ${pct(s!.buy_hold_max_drawdown_pct)}`, "text-down"],
                ["Trades", String(s!.trades), `Win rate ${s!.win_rate}% · in market ${s!.time_in_market_pct}%`, ""],
              ].map(([k, v, sub, cls]) => (
                <div key={k} className="rounded-xl border border-line bg-panel p-3">
                  <div className="text-[11px] uppercase tracking-wide text-muted">{k}</div>
                  <div className={`tabular text-xl font-semibold ${cls}`}>{v}</div>
                  <div className="text-xs text-muted">{sub}</div>
                </div>
              ))}
            </div>
            <section className="rounded-xl border border-line bg-panel p-4">
              <h2 className="mb-2 font-semibold">{res.strategy} on {res.symbol} vs. buy & hold</h2>
              <LineChart series={series} height={280} suffix="%" />
            </section>
            <section className="rounded-xl border border-line bg-panel p-4">
              <h2 className="mb-2 font-semibold">Trades</h2>
              <table className="w-full text-sm">
                <thead className="text-left text-[11px] uppercase tracking-wide text-muted"><tr><th className="py-1.5">Entry</th><th className="py-1.5">Exit</th><th className="py-1.5 text-right">Entry $</th><th className="py-1.5 text-right">Exit $</th><th className="py-1.5 text-right">Days</th><th className="py-1.5 text-right">Return</th></tr></thead>
                <tbody>
                  {res.trades.map((t) => (
                    <tr key={t.entry_date} className="border-t border-line">
                      <td className="tabular py-1.5">{t.entry_date}</td>
                      <td className="tabular py-1.5">{t.exit_date}{t.open && <span className="ml-1 text-[10px] text-blue-300">open</span>}</td>
                      <td className="tabular py-1.5 text-right">{fmt(t.entry)}</td><td className="tabular py-1.5 text-right">{fmt(t.exit)}</td>
                      <td className="tabular py-1.5 text-right text-muted">{t.days}</td>
                      <td className={`tabular py-1.5 text-right ${tone(t.return_pct)}`}>{pct(t.return_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-2 text-[11px] text-muted">Long only: buy at the close of a BUY signal, sell at the close of the next SELL signal. Past results do not guarantee future returns.</p>
            </section>
          </>
        )
      )}
    </div>
  );
}

function Locked({ what }: { what: string }) {
  return (
    <div className="max-w-md rounded-xl border border-amber-500/30 bg-amber-500/5 p-6">
      <h2 className="font-semibold">🔒 {what} is part of Pro</h2>
      <p className="mt-2 text-sm text-muted">On the Free plan you can backtest the trades you place from the charts (Chart trades, TradeGrader and Analytics). Pro and Premium add the trades from Trade ideas and the Move Detector, and strategy backtests.</p>
      <Link href="/billing" className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-white">See plans</Link>
    </div>
  );
}

function Backtest() {
  const { user } = useAuth();
  type Tab = "trades" | "mdtrades" | "chart" | "grader" | "analytics" | "md" | "strategy" | "builder";
  const [tab, setTab] = useState<Tab>(() => {
    if (typeof window === "undefined") return "chart";
    const t = new URLSearchParams(window.location.search).get("tab");
    return t === "md" ? "mdtrades" : (["trades", "mdtrades", "chart", "grader", "analytics", "validation", "strategy", "builder"].includes(t ?? "") ? (t === "validation" ? "md" : t) : "chart") as Tab;
  });
  const paid = !!user?.limits.backtesting;
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <h1 className="text-xl font-semibold">Backtesting</h1>
        <p className="mb-4 text-sm text-muted">Does it actually work? Follow the ideas you took, and test the algorithm and strategies on historical data before trusting them with money.</p>
        <nav className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
          {([["chart", "Chart trades"], ["trades", "Idea trades"], ["mdtrades", "Move Detector trades"], ["grader", "TradeGrader"], ["analytics", "Analytics"], ["strategy", "Strategy backtest"], ["builder", "Strategy builder"]] as const).map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)} className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${tab === id ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}>
              {label}
              {((!paid && ["trades", "mdtrades", "strategy"].includes(id)) || (id === "builder" && !user?.limits.custom_backtest)) && <span className="ml-1 text-[10px]">🔒</span>}
            </button>
          ))}
        </nav>
        {tab === "trades" ? (
          paid ? <PaperTrades source="ideas" /> : <Locked what="Idea trades" />
        ) : tab === "mdtrades" ? (
          paid ? <PaperTrades source="md" /> : <Locked what="Move Detector trades" />
        ) : tab === "chart" ? (
          <PaperTrades source="chart" />
        ) : tab === "grader" ? (
          <TradeGrader source={paid ? "all" : "chart"} chartOnly={!paid} />
        ) : tab === "analytics" ? (
          <TradeAnalytics chartOnly={!paid} />
        ) : tab === "builder" ? (
          <RulesBuilder allowed={!!user?.limits.custom_backtest} />
        ) : !paid ? (
          <Locked what="Strategy backtest" />
        ) : (
          <StrategyBacktest />
        )}
        <p className="mt-4 text-xs text-muted">
          Logging trades you made elsewhere?{" "}
          <Link href="/journal" className="text-accent hover:underline">Trade journal &amp; Trade Review</Link>
        </p>
        <p className="mt-6 text-xs text-muted">For educational purposes only. Not financial advice. Past performance does not guarantee future results.</p>
      </div>
    </div>
  );
}

export default function BacktestPage() {
  return (
    <AppShell>
      <Backtest />
    </AppShell>
  );
}
