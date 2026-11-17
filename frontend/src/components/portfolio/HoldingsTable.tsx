"use client";

import { useBackClose } from "@/lib/useBackClose";

import EarningsBadge from "@/components/EarningsBadge";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { post, put } from "@/lib/api";
import { num, pct, tone, usd } from "@/lib/format";
import type { Holding, PortfolioDetail } from "@/lib/types";

/** Sell at the market: pick a quantity (½ / All), see the estimated value and the P/L on this sale. */
export function SellNowDialog({ portfolioId, portfolioName, symbol, shares, avgCost, price, onClose, onSold }: {
  portfolioId: number; portfolioName?: string; symbol: string; shares: number; avgCost: number; price: number | null;
  onClose: () => void; onSold: (p: PortfolioDetail) => void;
}) {
  useBackClose(true, onClose);
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

/** Small editing panel under a table cell, so editing never widens the table. Closes on outside click / Escape. */
function Popover({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const down = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && onClose();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    setTimeout(() => window.addEventListener("mousedown", down), 0);
    window.addEventListener("keydown", esc);
    return () => {
      window.removeEventListener("mousedown", down);
      window.removeEventListener("keydown", esc);
    };
  }, [onClose]);
  return (
    <div ref={ref} className="absolute right-0 top-full z-30 mt-1 w-52 whitespace-normal rounded-lg border border-line bg-panel-2 p-2.5 text-left shadow-2xl">
      {children}
    </div>
  );
}

function StopCell({ portfolioId, symbol, stop, price, onSaved, autoEdit = false }: { portfolioId: number; symbol: string; stop: number | null; price: number; onSaved: (p: PortfolioDetail) => void; autoEdit?: boolean }) {
  const [edit, setEdit] = useState(false);
  useEffect(() => {
    if (autoEdit) setEdit(true);
  }, [autoEdit]);
  const [v, setV] = useState(stop ? String(stop) : (price * 0.93).toFixed(2));
  const save = async (val: number | null) => {
    onSaved(await put<PortfolioDetail>(`/api/portfolios/${portfolioId}/stops`, { symbol, stop: val }));
    setEdit(false);
  };
  const pct = Number(v) > 0 ? ((Number(v) / price - 1) * 100).toFixed(1) : null;
  return (
    <span className="relative inline-block">
      {stop !== null ? (
        <button onClick={() => setEdit((x) => !x)} className="tabular whitespace-nowrap text-down hover:underline" title={`${(((stop / price) - 1) * 100).toFixed(1)}% away`}>{usd(stop)}</button>
      ) : (
        <button onClick={() => setEdit((x) => !x)} className="whitespace-nowrap rounded border border-dashed border-amber-500/50 px-1.5 py-0.5 text-[11px] text-amber-300">+ Stop</button>
      )}
      {edit && (
        <Popover onClose={() => setEdit(false)}>
          <label className="block text-[11px] text-muted">
            Stop price {pct && <span className="text-down">({pct}%)</span>}
            <input autoFocus value={v} onChange={(e) => setV(e.target.value)} onKeyDown={(e) => e.key === "Enter" && Number(v) > 0 && save(Number(v))}
              className="tabular mt-1 block w-full rounded border border-line bg-bg px-2 py-1 text-right text-sm" inputMode="decimal" />
          </label>
          <div className="mt-2 flex gap-1.5">
            <button onClick={() => Number(v) > 0 && save(Number(v))} className="flex-1 rounded bg-accent px-2 py-1 text-xs font-medium text-white">Save</button>
            {stop !== null && <button onClick={() => save(null)} className="rounded border border-line px-2 py-1 text-xs text-muted hover:text-down">Remove</button>}
          </div>
        </Popover>
      )}
    </span>
  );
}

function TargetCell({ portfolioId, symbol, trim, target, price, onSaved, autoEdit = false }: {
  portfolioId: number; symbol: string; trim: number | null; target: number | null; price: number; onSaved: (p: PortfolioDetail) => void; autoEdit?: boolean;
}) {
  const [edit, setEdit] = useState(false);
  const [t1, setT1] = useState(trim ? String(trim) : (price * 1.1).toFixed(2));
  const [t2, setT2] = useState(target ? String(target) : (price * 1.2).toFixed(2));
  useEffect(() => {
    if (autoEdit) setEdit(true);
  }, [autoEdit]);
  const save = async (a: number | null, b: number | null) => {
    onSaved(await put<PortfolioDetail>(`/api/portfolios/${portfolioId}/targets`, { symbol, trim: a, target: b }));
    setEdit(false);
  };
  const inp = "tabular mt-1 block w-full rounded border border-line bg-bg px-2 py-1 text-right text-sm";
  const pctOf = (x: string) => (Number(x) > 0 ? `${((Number(x) / price - 1) * 100).toFixed(1)}%` : "");
  return (
    <span className="relative inline-block">
      {trim || target ? (
        <button onClick={() => setEdit((x) => !x)} className="tabular whitespace-nowrap text-up hover:underline" title="Trim (sell part) / target">
          {trim ? usd(trim) : "—"} / {target ? usd(target) : "—"}
        </button>
      ) : (
        <button onClick={() => setEdit((x) => !x)} className="whitespace-nowrap rounded border border-dashed border-line px-1.5 py-0.5 text-[11px] text-muted hover:text-text">+ Set</button>
      )}
      {edit && (
        <Popover onClose={() => setEdit(false)}>
          <label className="block text-[11px] text-muted">
            Trim: sell part at <span className="text-up">{pctOf(t1)}</span>
            <input autoFocus value={t1} onChange={(e) => setT1(e.target.value)} className={inp} inputMode="decimal" />
          </label>
          <label className="mt-2 block text-[11px] text-muted">
            Target <span className="text-up">{pctOf(t2)}</span>
            <input value={t2} onChange={(e) => setT2(e.target.value)} onKeyDown={(e) => e.key === "Enter" && save(Number(t1) || null, Number(t2) || null)} className={inp} inputMode="decimal" />
          </label>
          <div className="mt-2 flex gap-1.5">
            <button onClick={() => save(Number(t1) || null, Number(t2) || null)} className="flex-1 rounded bg-accent px-2 py-1 text-xs font-medium text-white">Save</button>
            {(trim || target) && <button onClick={() => save(null, null)} className="rounded border border-line px-2 py-1 text-xs text-muted hover:text-down">Remove</button>}
          </div>
        </Popover>
      )}
    </span>
  );
}

/** Portfolio heat: what you'd lose if every stop were hit. */
export function HeatCard({ heat, value }: { heat: NonNullable<PortfolioDetail["heat"]>; value: number }) {
  const pctRisk = heat.total_risk_pct ?? 0;
  const tone = pctRisk > 10 ? "text-down" : pctRisk > 6 ? "text-amber-300" : "text-up";
  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Portfolio heat (open risk)</h2>
        <span className="text-[11px] text-muted">If every stop were hit today</span>
      </div>
      <div className="mt-2 flex flex-wrap items-end gap-4">
        <span className={`tabular text-2xl font-bold ${tone}`}>{usd(heat.total_risk)}</span>
        <span className={`tabular pb-0.5 text-lg ${tone}`}>{heat.total_risk_pct !== null ? `${heat.total_risk_pct.toFixed(1)}% of ${usd(value)}` : ""}</span>
      </div>
      <p className="mt-1 text-xs text-muted">Many swing traders keep total open risk under 6-10% of the account and 0.5-2% per position.</p>
      {heat.positions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {heat.positions.map((x) => (
            <span key={x.symbol} className="tabular rounded bg-panel-2 px-2 py-0.5 text-xs">
              {x.symbol} <span className="text-down">{usd(x.risk)}</span> <span className="text-muted">({x.risk_pct?.toFixed(1)}%)</span>
            </span>
          ))}
        </div>
      )}
      {heat.missing.length > 0 && (
        <p className="mt-2 text-xs text-amber-300">⚠ No stop set for {heat.missing.join(", ")}: the risk on these positions is open-ended. Set one in the Stop column.</p>
      )}
    </section>
  );
}

export default function HoldingsTable({ rows, portfolioId, onSold }: { rows: Holding[]; portfolioId?: number; onSold?: (p: PortfolioDetail) => void }) {
  const [selling, setSelling] = useState<Holding | null>(null);
  const [editing, setEditing] = useState<{ kind: string; symbol: string } | null>(null);
  useEffect(() => {
    const on = (e: Event) => setEditing((e as CustomEvent).detail);
    window.addEventListener("holding-edit", on);
    return () => window.removeEventListener("holding-edit", on);
  }, []);
  return (
    <section id="holdings" className="scroll-mt-4 rounded-xl border border-line bg-panel">
      <h2 className="px-4 pt-4 font-semibold">Holdings</h2>
      {selling && portfolioId && onSold && (
        <SellNowDialog portfolioId={portfolioId} symbol={selling.symbol} shares={selling.shares} avgCost={selling.avg_cost} price={selling.price}
          onClose={() => setSelling(null)} onSold={onSold} />
      )}
      {rows.length === 0 ? (
        <p className="p-4 text-sm text-muted">No open positions. Add a buy transaction below.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="mt-2 w-full min-w-[960px] whitespace-nowrap text-sm [&_td]:px-3 [&_th]:px-3">
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
                {portfolioId && <th className="px-4 py-2 text-right" title="Your stop: used for the open-risk (heat) card">Stop</th>}
                {portfolioId && <th className="px-4 py-2 text-right" title="Where you sell part (trim) and take profits (target)">Trim / Target</th>}
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
                  {portfolioId && onSold && (
                    <td className="px-4 py-2 text-right">
                      <StopCell portfolioId={portfolioId} symbol={r.symbol} stop={r.stop ?? null} price={r.price} onSaved={onSold}
                        autoEdit={editing?.kind === "stop" && editing.symbol === r.symbol} />
                    </td>
                  )}
                  {portfolioId && onSold && (
                    <td className="px-4 py-2 text-right">
                      <TargetCell portfolioId={portfolioId} symbol={r.symbol} trim={r.trim ?? null} target={r.target ?? null} price={r.price} onSaved={onSold}
                        autoEdit={editing?.kind === "target" && editing.symbol === r.symbol} />
                    </td>
                  )}
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
