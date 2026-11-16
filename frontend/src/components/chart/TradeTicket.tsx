"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { post } from "@/lib/api";

/** Manual order ticket from the chart: your own entry, stop, trim and target. Followed in Backtest → Chart trades. */
export default function TradeTicket({ symbol, price, side, onClose }: { symbol: string; price: number; side: "long" | "short"; onClose: () => void }) {
  const long = side === "long";
  const [entry, setEntry] = useState(price.toFixed(2));
  const [stop, setStop] = useState((long ? price * 0.93 : price * 1.07).toFixed(2));
  const [trim, setTrim] = useState("");
  const [target, setTarget] = useState((long ? price * 1.21 : price * 0.79).toFixed(2));
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const calc = useMemo(() => {
    const e = Number(entry), s = Number(stop), t = Number(target);
    const risk = Math.abs(e - s);
    const ok = e > 0 && s > 0 && t > 0 && (long ? s < e && t > e : s > e && t < e);
    return { ok, riskPct: e ? (risk / e) * 100 : 0, rr: risk ? Math.abs(t - e) / risk : 0, weight: risk ? Math.min(20, (1 / (risk / e)) * 1) : 0 };
  }, [entry, stop, target, long]);

  const submit = async () => {
    setError("");
    try {
      await post("/api/paper-trades/chart", {
        symbol, side, entry: Number(entry), stop: Number(stop), target: Number(target), ...(trim ? { trim: Number(trim) } : {}),
      });
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const field = "w-full rounded-md border border-line bg-bg px-3 py-2 text-sm tabular outline-none focus:border-accent";

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3" onMouseDown={onClose}>
      <div className="w-full max-w-sm rounded-xl border border-line bg-panel shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className={`flex items-center justify-between rounded-t-xl px-4 py-3 ${long ? "bg-up/15" : "bg-down/15"}`}>
          <h2 className="font-semibold">
            <span className={long ? "text-up" : "text-down"}>{long ? "Buy" : "Short"}</span> {symbol}
          </h2>
          <button onClick={onClose} className="rounded px-2 py-1 text-muted hover:bg-panel-2" aria-label="Close">✕</button>
        </div>
        {done ? (
          <div className="space-y-3 p-4 text-sm">
            <p className="text-up">Added. It closes by itself at the target or the stop (half is sold at the trim, if you set one).</p>
            <Link href="/backtest?tab=chart" className="inline-block rounded-md bg-accent px-4 py-2 font-medium text-white">Open Backtest → Chart trades</Link>
          </div>
        ) : (
          <div className="space-y-3 p-4">
            <div className="grid grid-cols-2 gap-3">
              <label className="text-xs text-muted">Entry<input value={entry} onChange={(e) => setEntry(e.target.value)} inputMode="decimal" className={`${field} mt-1`} /></label>
              <label className="text-xs text-muted">Stop<input value={stop} onChange={(e) => setStop(e.target.value)} inputMode="decimal" className={`${field} mt-1 text-down`} /></label>
              <label className="text-xs text-muted">Trim (optional)<input value={trim} onChange={(e) => setTrim(e.target.value)} inputMode="decimal" placeholder="sell half here" className={`${field} mt-1`} /></label>
              <label className="text-xs text-muted">Target<input value={target} onChange={(e) => setTarget(e.target.value)} inputMode="decimal" className={`${field} mt-1 text-up`} /></label>
            </div>
            <div className="grid grid-cols-3 gap-2 rounded-lg bg-panel-2/50 p-2 text-center text-xs">
              <div><div className="text-muted">Risk</div><div className="tabular font-semibold">{calc.riskPct.toFixed(1)}%</div></div>
              <div><div className="text-muted">Reward / risk</div><div className={`tabular font-semibold ${calc.rr >= 2 ? "text-up" : calc.rr >= 1 ? "" : "text-down"}`}>{calc.rr.toFixed(1)}</div></div>
              <div title="Position size so that hitting the stop costs about 1% of the account"><div className="text-muted">Size (1% risk)</div><div className="tabular font-semibold">{calc.weight.toFixed(1)}%</div></div>
            </div>
            {!calc.ok && <p className="text-xs text-down">{long ? "For a buy: stop below the entry, target above it." : "For a short: stop above the entry, target below it."}</p>}
            {error && <p className="text-xs text-down">{error}</p>}
            <button disabled={!calc.ok} onClick={submit} className={`w-full rounded-md py-2 text-sm font-semibold text-white disabled:opacity-40 ${long ? "bg-up hover:bg-green-500" : "bg-down hover:bg-red-500"}`}>
              {long ? "Buy" : "Short"} {symbol}
            </button>
            <p className="text-[11px] text-muted">A simulated trade, followed in Backtest → Chart trades and graded in TradeGrader. To record a real purchase, add it in Portfolio.</p>
          </div>
        )}
      </div>
    </div>
  );
}
