"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, del, post } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import { fmt, pct, tone } from "@/lib/format";

const LineChart = dynamic(() => import("@/components/markets/LineChart"), { ssr: false });

type Cond = { type: string; label: string; params: Record<string, number> };
type Rule = { type: string; [k: string]: number | string };
type Exit = { stop_pct: number; target_r: number; atr_trail: number; below_sma: number; max_days: number; ut_sell: boolean };
type Rules = { entry: Rule[]; exit: Exit };
type Result = {
  symbol: string; reason?: string;
  stats: {
    trades: number; win_rate?: number; avg_return_pct?: number; total_return_pct?: number; buy_hold_return_pct?: number; cagr_pct?: number; buy_hold_cagr_pct?: number;
    max_drawdown_pct?: number; buy_hold_max_drawdown_pct?: number; time_in_market_pct?: number; avg_days?: number; profit_factor?: number | null; exits?: Record<string, number>;
  };
  trades: { entry_date: string; entry: number; exit_date: string; exit: number; return_pct: number; days: number; open: boolean; exit_reason?: string }[];
  equity: { time: string; value: number }[];
  buy_hold: { time: string; value: number }[];
};
type Saved = { id: number; name: string; rules: Rules };

const PRESETS: { name: string; rules: Rules }[] = [
  { name: "Trend Template breakout", rules: { entry: [{ type: "trend_template" }, { type: "breakout", n: 20 }, { type: "volume_surge", value: 1.4 }], exit: { stop_pct: 7, target_r: 3, atr_trail: 0, below_sma: 50, max_days: 0, ut_sell: false } } },
  { name: "Pullback in an uptrend", rules: { entry: [{ type: "sma_stack" }, { type: "rsi_below", n: 14, value: 40 }], exit: { stop_pct: 6, target_r: 2, atr_trail: 0, below_sma: 0, max_days: 30, ut_sell: false } } },
  { name: "UT Bot trend follower", rules: { entry: [{ type: "price_above_sma", n: 200 }, { type: "ut_bot_buy", key: 1, atr: 10 }], exit: { stop_pct: 8, target_r: 0, atr_trail: 3, below_sma: 0, max_days: 0, ut_sell: true } } },
];

/** Strategy builder (Premium): entry conditions (all must hold) + exit rules, backtested on daily bars. */
export default function RulesBuilder({ allowed }: { allowed: boolean }) {
  const [conds, setConds] = useState<Cond[]>([]);
  const [rules, setRules] = useState<Rules>(PRESETS[0].rules);
  const [symbol, setSymbol] = useState("NVDA");
  const [res, setRes] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<Saved[]>([]);

  useEffect(() => {
    api<{ conditions: Cond[] }>("/api/backtest/rules/conditions").then((r) => setConds(r.conditions)).catch(() => {});
    if (allowed) api<Saved[]>("/api/backtest/rules/saved").then(setSaved).catch(() => {});
  }, [allowed]);
  const series = useMemo(
    () => (res && !res.reason ? [{ name: "Strategy", color: "#8b5cf6", data: res.equity }, { name: "Buy & hold", color: "#64748b", data: res.buy_hold, width: 1 as const }] : []),
    [res],
  );

  if (!allowed) {
    return (
      <div className="max-w-xl rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-transparent p-6">
        <h2 className="font-semibold">🔒 Strategy builder is part of Premium</h2>
        <p className="mt-2 text-sm text-muted">
          Combine conditions (Trend Template, Stage 2, breakouts, volume surges, RSI pullbacks, UT Bot, Supertrend, RS vs the S&amp;P 500…) with your exit rules (stop, R target,
          ATR trailing stop, moving average, time limit) and see how the strategy would have done, trade by trade.
        </p>
        <Link href="/billing" className="mt-4 inline-block rounded-md bg-amber-500 px-4 py-2 text-sm font-semibold text-black">Unlock with Premium</Link>
      </div>
    );
  }

  const run = async () => {
    setBusy(true);
    setError("");
    try {
      setRes(await post<Result>("/api/backtest/rules", { symbol, rules }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  };
  const save = async () => {
    const name = prompt("Name this strategy:", "My strategy");
    if (!name?.trim()) return;
    try {
      const s = await post<Saved>("/api/backtest/rules/saved", { name, rules });
      setSaved([s, ...saved]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };
  const setCond = (i: number, patch: Partial<Rule>) => setRules({ ...rules, entry: rules.entry.map((c, k) => (k === i ? ({ ...c, ...patch } as Rule) : c)) });
  const setExit = (patch: Partial<Exit>) => setRules({ ...rules, exit: { ...rules.exit, ...patch } });
  const input = "w-16 rounded border border-line bg-bg px-1.5 py-1 text-xs tabular outline-none focus:border-accent";
  const s = res?.stats;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted">Start from:</span>
        {PRESETS.map((p) => (
          <button key={p.name} onClick={() => setRules(p.rules)} className="rounded-full bg-panel px-3 py-1 hover:bg-panel-2">{p.name}</button>
        ))}
        {saved.map((p) => (
          <span key={p.id} className="inline-flex items-center gap-1 rounded-full bg-violet-500/15 px-3 py-1 text-violet-200">
            <button onClick={() => setRules(p.rules)}>★ {p.name}</button>
            <button
              onClick={async () => {
                await del(`/api/backtest/rules/saved/${p.id}`);
                setSaved(saved.filter((x) => x.id !== p.id));
              }}
              className="text-muted hover:text-down"
              aria-label={`Delete ${p.name}`}
            >
              ✕
            </button>
          </span>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-line bg-panel p-4">
          <h3 className="mb-2 text-sm font-semibold">Buy when ALL of these are true</h3>
          <ul className="space-y-2">
            {rules.entry.map((c, i) => {
              const def = conds.find((d) => d.type === c.type);
              return (
                <li key={i} className="flex flex-wrap items-center gap-2 rounded-lg bg-panel-2/50 px-2 py-1.5 text-xs">
                  <select
                    value={c.type}
                    onChange={(e) => setCond(i, { type: e.target.value, ...(conds.find((d) => d.type === e.target.value)?.params ?? {}) })}
                    className="max-w-[260px] rounded border border-line bg-bg px-1.5 py-1"
                  >
                    {conds.map((d) => <option key={d.type} value={d.type}>{d.label}</option>)}
                  </select>
                  {Object.entries(def?.params ?? {}).map(([k, dv]) => (
                    <label key={k} className="flex items-center gap-1 text-muted">
                      {k === "n" ? "N" : k === "value" ? "X" : k}
                      <input type="number" step="any" value={Number(c[k] ?? dv)} onChange={(e) => setCond(i, { [k]: Number(e.target.value) })} className={input} />
                    </label>
                  ))}
                  <button onClick={() => setRules({ ...rules, entry: rules.entry.filter((_, k) => k !== i) })} className="ml-auto text-muted hover:text-down" aria-label="Remove condition">✕</button>
                </li>
              );
            })}
          </ul>
          <button onClick={() => setRules({ ...rules, entry: [...rules.entry, { type: "price_above_sma", n: 50 }] })} className="mt-2 rounded-md bg-panel-2 px-3 py-1 text-xs hover:bg-line">
            + Add condition
          </button>
        </section>
        <section className="rounded-xl border border-line bg-panel p-4">
          <h3 className="mb-2 text-sm font-semibold">Sell when ANY of these happens</h3>
          <div className="grid grid-cols-2 gap-2 text-xs text-muted">
            <label className="flex items-center justify-between gap-2">Stop loss (% below entry)<input type="number" step="any" value={rules.exit.stop_pct} onChange={(e) => setExit({ stop_pct: Number(e.target.value) })} className={input} /></label>
            <label className="flex items-center justify-between gap-2">Target (× risk, R)<input type="number" step="any" value={rules.exit.target_r} onChange={(e) => setExit({ target_r: Number(e.target.value) })} className={input} /></label>
            <label className="flex items-center justify-between gap-2">ATR trailing stop (×)<input type="number" step="any" value={rules.exit.atr_trail} onChange={(e) => setExit({ atr_trail: Number(e.target.value) })} className={input} /></label>
            <label className="flex items-center justify-between gap-2">Close below N-day avg.<input type="number" value={rules.exit.below_sma} onChange={(e) => setExit({ below_sma: Number(e.target.value) })} className={input} /></label>
            <label className="flex items-center justify-between gap-2">Max days in the trade<input type="number" value={rules.exit.max_days} onChange={(e) => setExit({ max_days: Number(e.target.value) })} className={input} /></label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={rules.exit.ut_sell} onChange={(e) => setExit({ ut_sell: e.target.checked })} />UT Bot sell signal</label>
          </div>
          <p className="mt-2 text-[11px] text-muted">0 turns a rule off. Entries fill at the close of the signal day; stops and targets fill at their price (or the open if it gaps past).</p>
        </section>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-muted">Symbol<input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} className="mt-1 block w-24 rounded border border-line bg-bg px-2 py-1.5 text-sm" /></label>
        <button onClick={run} disabled={busy} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60">{busy ? "Running…" : "Run backtest"}</button>
        <button onClick={save} className="rounded-md border border-line px-3 py-2 text-sm text-muted hover:text-text">★ Save strategy</button>
        {res && !res.reason && (
          <button onClick={() => downloadCsv(res.trades, `${res.symbol}-strategy-trades.csv`)} className="rounded-md border border-line px-3 py-2 text-sm text-muted hover:text-text">⬇ Export trades CSV</button>
        )}
      </div>
      {error && <p className="text-sm text-down">{error}</p>}
      {res && (res.reason ? <p className="text-sm text-muted">{res.reason}</p> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {[
              ["Total return", pct(s!.total_return_pct), `Buy & hold ${pct(s!.buy_hold_return_pct)}`, tone(s!.total_return_pct)],
              ["CAGR", pct(s!.cagr_pct), `Buy & hold ${pct(s!.buy_hold_cagr_pct)}`, tone(s!.cagr_pct)],
              ["Max drawdown", pct(s!.max_drawdown_pct), `Buy & hold ${pct(s!.buy_hold_max_drawdown_pct)}`, "text-down"],
              ["Trades", String(s!.trades), `Win rate ${s!.win_rate}% · avg ${pct(s!.avg_return_pct)}`, ""],
              ["Profit factor", s!.profit_factor ? String(s!.profit_factor) : "—", Object.entries(s!.exits ?? {}).map(([k, v]) => `${k} ${v}`).join(" · "), (s!.profit_factor ?? 0) >= 1.5 ? "text-up" : ""],
            ].map(([k, v, sub, cls]) => (
              <div key={k} className="rounded-xl border border-line bg-panel p-3">
                <div className="text-[11px] uppercase tracking-wide text-muted">{k}</div>
                <div className={`tabular text-xl font-semibold ${cls}`}>{v}</div>
                <div className="text-xs text-muted">{sub}</div>
              </div>
            ))}
          </div>
          <section className="rounded-xl border border-line bg-panel p-4">
            <h3 className="mb-2 text-sm font-semibold">Equity vs buy &amp; hold ({res.symbol})</h3>
            <LineChart series={series} height={260} suffix="%" />
          </section>
          <section className="overflow-x-auto rounded-xl border border-line bg-panel p-4">
            <table className="w-full text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
                <tr><th className="py-1.5">Entry</th><th className="py-1.5">Exit</th><th className="py-1.5 text-right">Entry $</th><th className="py-1.5 text-right">Exit $</th><th className="py-1.5">Why</th><th className="py-1.5 text-right">Days</th><th className="py-1.5 text-right">Return</th></tr>
              </thead>
              <tbody>
                {res.trades.map((t) => (
                  <tr key={t.entry_date} className="border-t border-line">
                    <td className="tabular py-1.5">{t.entry_date}</td>
                    <td className="tabular py-1.5">{t.exit_date}{t.open && <span className="ml-1 text-[10px] text-blue-300">open</span>}</td>
                    <td className="tabular py-1.5 text-right">{fmt(t.entry)}</td>
                    <td className="tabular py-1.5 text-right">{fmt(t.exit)}</td>
                    <td className="py-1.5 text-xs text-muted">{t.exit_reason}</td>
                    <td className="tabular py-1.5 text-right text-muted">{t.days}</td>
                    <td className={`tabular py-1.5 text-right ${tone(t.return_pct)}`}>{pct(t.return_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[11px] text-muted">Simulated, long only, fees 0.05% per side. Past results do not guarantee future returns.</p>
          </section>
        </>
      ))}
    </div>
  );
}
