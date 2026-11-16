"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, del, post } from "@/lib/api";
import { fmt, pct, tone } from "@/lib/format";

type Trade = {
  id: number; symbol: string; timeframe: string; side: "long" | "short"; entry_date: string; entry: number; stop: number;
  trim: number | null; target: number; weight: number; status: string; open: boolean; current: number | null;
  r_multiple: number; pnl_pct: number; closed_at: string | null; exit_price: number | null;
};
type Resp = {
  trades: Trade[];
  summary: { trades: number; open: number; closed: number; win_rate: number | null; avg_r: number | null; total_r: number; account_pct: number; avg_pnl_pct: number | null };
};

const STATUS: Record<string, string> = {
  OPEN: "bg-accent/20 text-blue-300", TRIMMED: "bg-amber-500/20 text-amber-300", TARGET: "bg-up/25 text-up",
  STOPPED: "bg-down/25 text-down", BREAKEVEN: "bg-slate-500/25 text-slate-200", CLOSED: "bg-slate-500/25 text-slate-200",
};

function Stat({ label, value, cls = "", hint }: { label: string; value: string; cls?: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-panel p-3" title={hint}>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className={`tabular text-xl font-semibold ${cls}`}>{value}</div>
    </div>
  );
}

function TradesTable({ rows, close, remove, closed = false }: { rows: Trade[]; close: (t: Trade) => void; remove: (t: Trade) => void; closed?: boolean }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="bg-panel text-left text-[11px] uppercase tracking-wide text-muted">
            <tr>
              {["Ticker", "TF", "Since", "Entry", closed ? "Exit" : "Current", "Stop", "Trim", "Target", "P/L", "R", closed ? "Result" : "Status", ""].map((h) => (
                <th key={h} className={`px-3 py-2.5 ${["Entry", "Current", "Exit", "Stop", "Trim", "Target", "P/L", "R"].includes(h) ? "text-right" : ""} ${h === "Ticker" ? "sticky left-0 bg-panel" : ""}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id} className="border-t border-line">
                <td className="sticky left-0 bg-bg px-3 py-2">
                  <Link href={`/chart?s=${t.symbol}`} className={`whitespace-nowrap rounded px-2 py-1 text-xs font-bold ${t.side === "short" ? "bg-down/20 text-down" : "bg-up/20 text-up"}`}>
                    {t.side === "short" ? "▼" : "▲"} {t.symbol}
                  </Link>
                </td>
                <td className="px-3 py-2 text-xs text-muted">{t.timeframe}</td>
                <td className="tabular whitespace-nowrap px-3 py-2 text-xs text-muted">{t.entry_date}</td>
                <td className="tabular px-3 py-2 text-right">{fmt(t.entry)}</td>
                <td className="tabular px-3 py-2 text-right">{t.exit_price !== null ? fmt(t.exit_price) : fmt(t.current)}</td>
                <td className="tabular px-3 py-2 text-right text-down/90">{fmt(t.stop)}</td>
                <td className="tabular px-3 py-2 text-right text-amber-300/90">{t.trim ? fmt(t.trim) : "—"}</td>
                <td className="tabular px-3 py-2 text-right text-up/90">{fmt(t.target)}</td>
                <td className={`tabular px-3 py-2 text-right ${tone(t.pnl_pct)}`}>{pct(t.pnl_pct)}</td>
                <td className={`tabular px-3 py-2 text-right font-medium ${tone(t.r_multiple)}`}>{t.r_multiple > 0 ? "+" : ""}{t.r_multiple}R</td>
                <td className="px-3 py-2">
                  {closed && (
                    <span className={`mr-1.5 rounded px-2 py-0.5 text-[11px] font-semibold ${t.r_multiple > 0 ? "bg-up/25 text-up" : t.r_multiple < 0 ? "bg-down/25 text-down" : "bg-slate-500/25 text-slate-200"}`}>
                      {t.r_multiple > 0 ? "Profit" : t.r_multiple < 0 ? "Loss" : "Flat"}
                    </span>
                  )}
                  <span className={`rounded px-2 py-0.5 text-[11px] font-semibold ${STATUS[t.status] ?? ""}`}>{t.status}</span>
                  {t.closed_at && <span className="ml-1 text-[11px] text-muted">{t.closed_at}</span>}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right text-xs">
                  {t.open && <button onClick={() => close(t)} className="mr-2 text-muted hover:text-text">Close</button>}
                  <button onClick={() => remove(t)} className="text-muted hover:text-down">Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
  );
}

/** The Trade Ideas the user took (Buy / Short), followed with the idea's stop / trim / target rules. */
export default function PaperTrades({ source = "ideas" }: { source?: "ideas" | "md" }) {
  const [data, setData] = useState<Resp | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => api<Resp>(`/api/paper-trades?source=${source}`).then(setData).catch((e) => setError(e.message)), [source]);
  useEffect(() => {
    load();
  }, [load]);

  const close = async (t: Trade) => {
    if (!confirm(`Close the rest of ${t.symbol} at the latest price?`)) return;
    await post(`/api/paper-trades/${t.id}/close`, {});
    load();
  };
  const remove = async (t: Trade) => {
    if (!confirm(`Remove ${t.symbol} from your trades?`)) return;
    await del(`/api/paper-trades/${t.id}`);
    load();
  };

  if (error) return <p className="text-sm text-down">{error}</p>;
  if (!data) return <p className="text-sm text-muted">Loading your trades…</p>;
  const s = data.summary;
  if (!data.trades.length) {
    return (
      <div className="rounded-xl border border-line bg-panel p-6 text-center">
        <p className="font-medium">No trades yet</p>
        <p className="mt-1 text-sm text-muted">
          {source === "md" ? (
            <>
              In the <Link href="/scanner" className="text-accent hover:underline">Move Detector</Link>, press <b>Buy</b> or <b>Short</b> next to a stock. vnicornAI (or the rules)
              sets the stop, trim and target, and the trade is followed here automatically.
            </>
          ) : (
            <>
              In <Link href="/ideas" className="text-accent hover:underline">Trade ideas</Link>, press <b>Buy</b> or <b>Short</b> on an idea. It is added here at the current
              price and followed automatically: half is sold at the trim, the stop moves to break-even, the rest runs to the target.
            </>
          )}
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Trades" value={`${s.trades}`} hint={`${s.open} open · ${s.closed} closed`} />
        <Stat label="Win rate" value={s.win_rate === null ? "—" : `${s.win_rate}%`} hint="Closed trades with a profit" />
        <Stat label="Avg. R (closed)" value={s.avg_r === null ? "—" : `${s.avg_r > 0 ? "+" : ""}${s.avg_r}R`} cls={tone(s.avg_r)} />
        <Stat label="Total R" value={`${s.total_r > 0 ? "+" : ""}${s.total_r}R`} cls={tone(s.total_r)} hint="Open and closed, in multiples of the risk" />
        <Stat label="Account impact" value={pct(s.account_pct)} cls={tone(s.account_pct)} hint="If each trade used the suggested weight (% of the account)" />
      </div>
      {(() => {
        const open = data.trades.filter((t) => t.open);
        const closed = data.trades.filter((t) => !t.open);
        const wins = closed.filter((t) => t.r_multiple > 0).length;
        return (
          <>
            <section className="space-y-2">
              <h3 className="text-sm font-semibold">Open trades <span className="text-muted">({open.length})</span></h3>
              {open.length ? <TradesTable rows={open} close={close} remove={remove} /> : <p className="text-sm text-muted">No open trades.</p>}
            </section>
            <section className="space-y-2">
              <h3 className="flex flex-wrap items-baseline gap-2 text-sm font-semibold">
                Closed trades <span className="text-muted">({closed.length})</span>
                {closed.length > 0 && (
                  <span className="text-xs font-normal text-muted">
                    {wins} profitable · {closed.length - wins} not profitable · closed automatically at the target or the stop. Study them in{" "}
                    <Link href="/backtest?tab=grader" className="text-accent hover:underline">TradeGrader</Link> and{" "}
                    <Link href="/backtest?tab=analytics" className="text-accent hover:underline">Analytics</Link>.
                  </span>
                )}
              </h3>
              {closed.length ? <TradesTable rows={closed} close={close} remove={remove} closed /> : <p className="text-sm text-muted">None yet: trades close by themselves when they reach the target or the stop.</p>}
            </section>
          </>
        );
      })()}
      <p className="text-xs text-muted">Simulated with the idea&apos;s plan, from daily prices: half at the trim with the stop moved to break-even, the rest at the target or the stop.</p>
    </div>
  );
}
