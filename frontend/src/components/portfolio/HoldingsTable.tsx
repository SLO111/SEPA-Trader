"use client";

import EarningsBadge from "@/components/EarningsBadge";

import Link from "next/link";
import { useState } from "react";
import { post } from "@/lib/api";
import { num, pct, tone, usd } from "@/lib/format";
import type { Holding, PortfolioDetail } from "@/lib/types";

/** Sell at the market: pick a quantity (½ / All), see the estimated value and the P/L on this sale. */
export function SellNowDialog({ portfolioId, portfolioName, symbol, shares, avgCost, price, onClose, onSold }: {
  portfolioId: number; portfolioName?: string; symbol: string; shares: number; avgCost: number; price: number | null;
  onClose: () => void; onSold: (p: PortfolioDetail) => void;
}) {
  const [qty, setQty] = useState(shares);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const valid = qty > 0 && qty <= shares + 1e-9;
  const value = price ? qty * price : null;
  const pnl = price ? (price - avgCost) * qty : null;
  const sell = async () => {
    setBusy(true);
    setErr("");
    try {
      const p = await post<PortfolioDetail>(`/api/portfolios/${portfolioId}/sell-now`, { symbol, shares: Math.abs(qty - shares) < 1e-9 ? null : qty });
      onSold(p);
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not sell");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3" onMouseDown={onClose}>
      <div className="w-full max-w-sm rounded-xl border border-line bg-bg p-4 shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-semibold">Sell {symbol} at market{portfolioName ? <span className="font-normal text-muted"> · {portfolioName}</span> : null}</h3>
          <button onClick={onClose} className="rounded px-2 text-muted hover:bg-panel-2" aria-label="Close">✕</button>
        </div>
        <label className="text-xs text-muted">Shares to sell (you hold {num(shares)})</label>
        <div className="mt-1 flex gap-2">
          <input type="number" min={0} step="any" value={qty} onChange={(e) => setQty(Number(e.target.value))}
            className="tabular min-w-0 flex-1 rounded-md border border-line bg-panel px-2 py-1.5 text-sm" />
          <button onClick={() => setQty(+(shares / 2).toFixed(6))} className="rounded-md bg-panel-2 px-2 text-sm hover:bg-line">½</button>
          <button onClick={() => setQty(shares)} className="rounded-md bg-panel-2 px-2 text-sm hover:bg-line">All</button>
        </div>
        <dl className="tabular mt-3 grid grid-cols-2 gap-y-1 text-sm">
          <dt className="text-muted">Market price</dt><dd className="text-right">{price ? usd(price) : "—"}</dd>
          <dt className="text-muted">Estimated value</dt><dd className="text-right">{value !== null ? usd(value) : "—"}</dd>
          <dt className="text-muted">P/L on this sale</dt>
          <dd className={`text-right ${tone(pnl ?? 0)}`}>{pnl !== null ? `${usd(pnl)} (${pct(((price! / avgCost) - 1) * 100)})` : "—"}</dd>
        </dl>
        <p className="mt-2 text-[11px] text-muted">Recorded at the latest price, dated the latest trading day. No price or date to type.</p>
        {err && <p className="mt-2 rounded bg-down/10 px-2 py-1 text-xs text-down">{err}</p>}
        <button onClick={sell} disabled={!valid || busy} className="mt-3 w-full rounded-md bg-down py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-40">
          {busy ? "Selling…" : `Sell ${num(qty)} ${symbol} now`}
        </button>
      </div>
    </div>
  );
}

export default function HoldingsTable({ rows, portfolioId, onSold }: { rows: Holding[]; portfolioId?: number; onSold?: (p: PortfolioDetail) => void }) {
  const [selling, setSelling] = useState<Holding | null>(null);
  return (
    <section className="rounded-xl border border-line bg-panel">
      <h2 className="px-4 pt-4 font-semibold">Holdings</h2>
      {selling && portfolioId && onSold && (
        <SellNowDialog portfolioId={portfolioId} symbol={selling.symbol} shares={selling.shares} avgCost={selling.avg_cost} price={selling.price}
          onClose={() => setSelling(null)} onSold={onSold} />
      )}
      {rows.length === 0 ? (
        <p className="p-4 text-sm text-muted">No open positions. Add a buy transaction below.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="mt-2 w-full min-w-[820px] text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-2">Symbol</th>
                <th className="px-4 py-2 text-right">Shares</th>
                <th className="px-4 py-2 text-right">Avg cost</th>
                <th className="px-4 py-2 text-right">Price</th>
                <th className="px-4 py-2 text-right">Value</th>
                <th className="px-4 py-2 text-right">Weight</th>
                <th className="px-4 py-2 text-right">Today</th>
                <th className="px-4 py-2 text-right">Total P/L</th>
                {portfolioId && <th className="px-2 py-2" />}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.symbol} className="border-t border-line">
                  <td className="px-4 py-2">
                    <Link href={`/stock?s=${encodeURIComponent(r.symbol)}`} className="font-medium hover:text-accent">
                      {r.symbol}
                    </Link>
                    <div className="max-w-[180px] truncate text-xs text-muted">{r.sector}</div>
                    <EarningsBadge days={r.earnings_in} />
                  </td>
                  <td className="tabular px-4 py-2 text-right">{num(r.shares)}</td>
                  <td className="tabular px-4 py-2 text-right">{usd(r.avg_cost)}</td>
                  <td className="tabular px-4 py-2 text-right">{usd(r.price)}</td>
                  <td className="tabular px-4 py-2 text-right">{usd(r.value)}</td>
                  <td className="tabular px-4 py-2 text-right text-muted">{r.weight.toFixed(1)}%</td>
                  <td className={`tabular px-4 py-2 text-right ${tone(r.day_change_pct)}`}>{pct(r.day_change_pct)}</td>
                  <td className={`tabular px-4 py-2 text-right ${tone(r.pnl)}`}>
                    {usd(r.pnl)}
                    <div className="text-xs">{pct(r.pnl_pct)}</div>
                  </td>
                  {portfolioId && (
                    <td className="px-2 py-2 text-right">
                      <button onClick={() => setSelling(r)} className="rounded-md border border-down/40 px-2.5 py-1 text-xs font-medium text-down hover:bg-down/10">
                        Sell
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
