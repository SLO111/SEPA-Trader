"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SellNowDialog } from "@/components/portfolio/HoldingsTable";
import { api, post } from "@/lib/api";
import { num, tone, usd } from "@/lib/format";

type Pos = { portfolio_id: number; portfolio: string; shares: number; avg_cost: number; price: number | null; pnl: number | null };
type Paper = { id: number; symbol: string; side: string; entry: number; open: boolean };

/** Sell from the chart: every place you hold the symbol — your portfolios (real sale at market) and open simulated chart trades. */
export default function SellDialog({ symbol, onClose, onShort }: { symbol: string; onClose: () => void; onShort: () => void }) {
  const [pos, setPos] = useState<Pos[] | null>(null);
  const [paper, setPaper] = useState<Paper[] | null>(null);
  const [selling, setSelling] = useState<Pos | null>(null);
  const [msg, setMsg] = useState("");

  const load = () => {
    api<Pos[]>(`/api/portfolios/positions?symbol=${encodeURIComponent(symbol)}`).then(setPos).catch(() => setPos([]));
    api<{ trades: Paper[] }>("/api/paper-trades?source=chart")
      .then((r) => setPaper(r.trades.filter((t) => t.symbol === symbol && t.open)))
      .catch(() => setPaper([]));
  };
  useEffect(load, [symbol]);

  const closeSim = async () => {
    try {
      await post("/api/paper-trades/chart/sell", { symbol });
      setMsg(`Your simulated ${symbol} trade is closed at the market (Backtest → Chart trades).`);
      load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const loading = pos === null || paper === null;
  const nothing = !loading && pos!.length === 0 && paper!.length === 0;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3" onMouseDown={onClose}>
      {selling && (
        <SellNowDialog portfolioId={selling.portfolio_id} portfolioName={selling.portfolio} symbol={symbol} shares={selling.shares} avgCost={selling.avg_cost}
          price={selling.price} onClose={() => setSelling(null)}
          onSold={() => { setMsg(`Sold ${symbol} in “${selling.portfolio}” at the market.`); load(); }} />
      )}
      <div className="w-full max-w-md rounded-xl border border-line bg-panel shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between rounded-t-xl bg-panel-2 px-4 py-3">
          <h2 className="font-semibold">Sell {symbol}</h2>
          <button onClick={onClose} className="rounded px-2 py-1 text-muted hover:bg-line" aria-label="Close">✕</button>
        </div>
        <div className="space-y-3 p-4 text-sm">
          {msg && <p className="rounded-md bg-up/10 px-3 py-2 text-xs text-up">{msg}</p>}
          {loading && <p className="text-muted">Looking for your {symbol} positions…</p>}
          {!loading && pos!.length > 0 && (
            <div>
              <div className="mb-1.5 text-[11px] uppercase tracking-wide text-muted">In your portfolios</div>
              <ul className="divide-y divide-line rounded-lg border border-line">
                {pos!.map((p) => (
                  <li key={p.portfolio_id} className="flex items-center gap-3 px-3 py-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{p.portfolio}</div>
                      <div className="tabular text-xs text-muted">
                        {num(p.shares)} sh · avg {usd(p.avg_cost)}
                        {p.pnl !== null && <span className={`ml-1 ${tone(p.pnl)}`}>· {p.pnl >= 0 ? "+" : ""}{usd(p.pnl)}</span>}
                      </div>
                    </div>
                    <button onClick={() => setSelling(p)} className="rounded-md bg-down px-3 py-1 text-xs font-semibold text-white hover:opacity-90">Sell…</button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {!loading && paper!.length > 0 && (
            <div>
              <div className="mb-1.5 text-[11px] uppercase tracking-wide text-muted">Simulated (Backtest → Chart trades)</div>
              <div className="flex items-center gap-3 rounded-lg border border-line px-3 py-2">
                <div className="min-w-0 flex-1 text-xs text-muted">
                  {paper!.length} open {paper!.length === 1 ? "trade" : "trades"} · entry {paper!.map((t) => usd(t.entry)).join(", ")}
                </div>
                <button onClick={closeSim} className="rounded-md border border-line px-3 py-1 text-xs font-semibold hover:bg-panel-2">Close at market</button>
              </div>
            </div>
          )}
          {nothing && (
            <div className="rounded-lg border border-line bg-panel-2/40 p-3 text-xs text-muted">
              You don&apos;t hold {symbol} in a portfolio or in an open chart trade.
              <div className="mt-2 flex flex-wrap gap-2">
                <button onClick={onShort} className="rounded-md bg-down/15 px-3 py-1 font-semibold text-down hover:bg-down/25">Short it instead?</button>
                <Link href="/portfolios" className="rounded-md border border-line px-3 py-1 hover:text-text">Open Portfolio</Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
