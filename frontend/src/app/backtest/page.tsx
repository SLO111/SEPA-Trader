"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmt, pct, tone } from "@/lib/format";
import type { StrategyDef } from "@/lib/types";

const LineChart = dynamic(() => import("@/components/markets/LineChart"), { ssr: false });

type Bucket = { bucket: string; samples: number; hit_rate: number; avg_fwd_5: number; avg_fwd_10: number; avg_fwd_20: number };
type Side = { base_rate: number; top10_hit_rate: number | null; lift: number | null; buckets: Bucket[] };
type ML = {
  available: boolean; reason?: string; avg_auc_model?: number; avg_auc_rules?: number; base_rate?: number; top10_model?: number; top10_rules?: number;
  verdict?: string; note?: string; folds?: { train_until: string; test_from: string; test_to: string; test_samples: number; base_rate: number; auc_model: number; auc_rules: number; top10_model: number; top10_rules: number }[];
};
type MD = { demo: boolean; validation: { samples: number; stocks: number; start: string; end: string; definition: { up: string; down: string }; bull: Side; bear: Side }; ml_up: ML; ml_down: ML };
type StratResult = {
  symbol: string; strategy: string; reason?: string;
  stats: { trades: number; win_rate?: number; avg_return_pct?: number; total_return_pct?: number; buy_hold_return_pct?: number; cagr_pct?: number; buy_hold_cagr_pct?: number; max_drawdown_pct?: number; buy_hold_max_drawdown_pct?: number; time_in_market_pct?: number; avg_days?: number };
  trades: { entry_date: string; entry: number; exit_date: string; exit: number; return_pct: number; days: number; open: boolean }[];
  equity: { time: string; value: number }[]; buy_hold: { time: string; value: number }[];
};

function SideCard({ title, side, kind, def }: { title: string; side: Side; kind: "bull" | "bear"; def: string }) {
  const max = Math.max(...side.buckets.map((b) => b.hit_rate), side.base_rate, 1);
  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <h2 className="font-semibold">{title}</h2>
      <p className="text-xs text-muted">Hit = {def}</p>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-panel-2/60 p-2"><div className="text-[11px] text-muted">All stocks (base rate)</div><div className="tabular text-lg font-semibold">{side.base_rate}%</div></div>
        <div className="rounded-lg bg-panel-2/60 p-2"><div className="text-[11px] text-muted">Top 10 by score</div><div className={`tabular text-lg font-semibold ${kind === "bull" ? "text-up" : "text-down"}`}>{side.top10_hit_rate ?? "—"}%</div></div>
        <div className="rounded-lg bg-panel-2/60 p-2"><div className="text-[11px] text-muted">Lift</div><div className={`tabular text-lg font-semibold ${(side.lift ?? 0) > 1.1 ? "text-up" : "text-muted"}`}>{side.lift ? `${side.lift}×` : "—"}</div></div>
      </div>
      <table className="mt-4 w-full text-sm">
        <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
          <tr><th className="py-1.5">Score</th><th className="py-1.5">Hit rate</th><th className="py-1.5 text-right">Samples</th><th className="py-1.5 text-right">Avg move 5d</th><th className="py-1.5 text-right">20d</th></tr>
        </thead>
        <tbody>
          {side.buckets.map((b) => (
            <tr key={b.bucket} className="border-t border-line">
              <td className="tabular py-1.5">{b.bucket}</td>
              <td className="py-1.5">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-24 overflow-hidden rounded-full bg-line"><div className={`h-full ${kind === "bull" ? "bg-up" : "bg-down"}`} style={{ width: `${(b.hit_rate / max) * 100}%` }} /></div>
                  <span className="tabular text-xs">{b.hit_rate}%</span>
                </div>
              </td>
              <td className="tabular py-1.5 text-right text-muted">{b.samples}</td>
              <td className={`tabular py-1.5 text-right ${tone(b.avg_fwd_5)}`}>{pct(b.avg_fwd_5)}</td>
              <td className={`tabular py-1.5 text-right ${tone(b.avg_fwd_20)}`}>{pct(b.avg_fwd_20)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-muted">{kind === "bull" ? "Average moves are price changes." : "Average moves are shown as declines (positive = the stock fell)."}</p>
    </section>
  );
}

function MLCard({ title, ml }: { title: string; ml: ML }) {
  if (!ml.available) return <section className="rounded-xl border border-line bg-panel p-4"><h2 className="font-semibold">{title}</h2><p className="mt-2 text-sm text-muted">{ml.reason}</p></section>;
  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-sm">{ml.verdict}</p>
      <div className="mt-3 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
        {[["AUC model", fmt(ml.avg_auc_model, 3)], ["AUC rules", fmt(ml.avg_auc_rules, 3)], ["Top-10 hit, model", `${ml.top10_model}%`], ["Top-10 hit, rules", `${ml.top10_rules}%`]].map(([k, v]) => (
          <div key={k} className="rounded-lg bg-panel-2/60 p-2"><div className="text-[11px] text-muted">{k}</div><div className="tabular font-semibold">{v}</div></div>
        ))}
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-muted">Walk-forward folds</summary>
        <table className="mt-2 w-full text-xs">
          <thead className="text-left text-muted"><tr><th className="py-1">Trained until</th><th>Tested</th><th className="text-right">Samples</th><th className="text-right">AUC model</th><th className="text-right">AUC rules</th></tr></thead>
          <tbody>
            {ml.folds?.map((f) => (
              <tr key={f.test_from} className="border-t border-line">
                <td className="tabular py-1">{f.train_until}</td><td className="tabular">{f.test_from} → {f.test_to}</td><td className="tabular text-right">{f.test_samples}</td>
                <td className="tabular text-right">{f.auc_model}</td><td className="tabular text-right">{f.auc_rules}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      <p className="mt-2 text-[11px] text-muted">Base rate in test periods: {ml.base_rate}%. {ml.note}</p>
    </section>
  );
}

function MoveDetectorValidation() {
  const [d, setD] = useState<MD | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<MD>("/api/backtest/move-detector").then(setD).catch((e) => setError(e.message));
  }, []);
  if (error) return <p className="text-sm text-down">{error}</p>;
  if (!d) return <p className="text-sm text-muted">Running the backtest across all stocks (this takes a few seconds the first time)…</p>;
  const v = d.validation;
  return (
    <div className="space-y-5">
      {d.demo && <p className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm text-amber-200">Demo data: these results come from generated prices and say nothing about real markets. Run with live data to validate the algorithm.</p>}
      <p className="text-sm text-muted">
        Tested on {v.samples.toLocaleString("en-US")} stock-days ({v.stocks} stocks, {v.start} → {v.end}). Each score only uses data available on that day; the outcome is what happened over the following 20 trading days.
      </p>
      <div className="grid gap-5 xl:grid-cols-2">
        <SideCard title="Bull Score → major move up" side={v.bull} kind="bull" def={v.definition.up} />
        <SideCard title="Bear Score → major move down" side={v.bear} kind="bear" def={v.definition.down} />
      </div>
      <h2 className="pt-2 text-lg font-semibold">Machine-learning layer (walk-forward)</h2>
      <div className="grid gap-5 xl:grid-cols-2">
        <MLCard title="Predicting major up moves" ml={d.ml_up} />
        <MLCard title="Predicting major down moves" ml={d.ml_down} />
      </div>
    </div>
  );
}

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

function Backtest() {
  const { user } = useAuth();
  const [tab, setTab] = useState<"md" | "strategy">("md");
  if (!user?.limits.backtesting) {
    return (
      <div className="grid h-full place-items-center p-6">
        <div className="max-w-md rounded-xl border border-amber-500/30 bg-amber-500/5 p-6 text-center">
          <h1 className="text-lg font-semibold">Backtesting</h1>
          <p className="mt-2 text-sm text-muted">Validate the Move Detector on historical data and test chart strategies against buy &amp; hold. Available on the Premium plan.</p>
          <Link href="/billing" className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-white">See plans</Link>
        </div>
      </div>
    );
  }
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <h1 className="text-xl font-semibold">Backtesting</h1>
        <p className="mb-4 text-sm text-muted">Does it actually work? Test the algorithm and strategies on historical data before trusting them with money.</p>
        <nav className="mb-5 flex gap-1 border-b border-line">
          {([["md", "Move Detector validation"], ["strategy", "Strategy backtest"]] as const).map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)} className={`border-b-2 px-3 py-2 text-sm ${tab === id ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}>{label}</button>
          ))}
        </nav>
        {tab === "md" ? <MoveDetectorValidation /> : <StrategyBacktest />}
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
