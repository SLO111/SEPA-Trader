"use client";

import { useEffect, useState } from "react";
import { api, del, post } from "@/lib/api";
import { num, usd } from "@/lib/format";
import type { PortfolioDetail, PortfolioTxn } from "@/lib/types";

const today = () => new Date().toISOString().slice(0, 10);
const field = "w-full rounded border border-line bg-bg px-2 py-1.5 text-sm outline-none focus:border-accent";

export default function Transactions({ portfolioId, txns, onChange }: { portfolioId: number; txns: PortfolioTxn[]; onChange: (p: PortfolioDetail) => void }) {
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [symbol, setSymbol] = useState("");
  const [shares, setShares] = useState("");
  const [date, setDate] = useState(today());
  const [price, setPrice] = useState("");
  const [fees, setFees] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Suggest the closing price for the chosen symbol and date.
  useEffect(() => {
    const s = symbol.trim();
    if (!s || !date) return;
    const t = setTimeout(() => {
      api<{ price: number | null }>(`/api/market/price/${encodeURIComponent(s)}?on=${date}`)
        .then((r) => r.price && setPrice(String(r.price)))
        .catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [symbol, date]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const p = await post<PortfolioDetail>(`/api/portfolios/${portfolioId}/transactions`, {
        symbol: symbol.trim(),
        side,
        shares: Number(shares),
        price: price ? Number(price) : null,
        date,
        fees: fees ? Number(fees) : 0,
      });
      onChange(p);
      setSymbol("");
      setShares("");
      setPrice("");
      setFees("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (t: PortfolioTxn) => {
    if (!confirm(`Delete this ${t.side} of ${t.shares} ${t.symbol}?`)) return;
    try {
      onChange(await del<PortfolioDetail>(`/api/portfolios/${portfolioId}/transactions/${t.id}`));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Error");
    }
  };

  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <h2 className="mb-3 font-semibold">Transactions</h2>
      <form onSubmit={submit} className="grid grid-cols-2 gap-2 sm:grid-cols-7">
        <div className="col-span-2 flex overflow-hidden rounded border border-line sm:col-span-1">
          {(["buy", "sell"] as const).map((s) => (
            <button
              type="button"
              key={s}
              onClick={() => setSide(s)}
              className={`flex-1 py-1.5 text-sm capitalize ${side === s ? (s === "buy" ? "bg-up/20 text-up" : "bg-down/20 text-down") : "text-muted"}`}
            >
              {s}
            </button>
          ))}
        </div>
        <input required value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} placeholder="Symbol" className={field} aria-label="Symbol" />
        <input required type="number" min="0" step="any" value={shares} onChange={(e) => setShares(e.target.value)} placeholder="Shares" className={field} aria-label="Shares" />
        <input required type="date" max={today()} value={date} onChange={(e) => setDate(e.target.value)} className={field} aria-label="Date" />
        <input type="number" min="0" step="any" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="Price" className={field} aria-label="Price per share" />
        <input type="number" min="0" step="any" value={fees} onChange={(e) => setFees(e.target.value)} placeholder="Fees" className={field} aria-label="Fees" />
        <button disabled={busy} className="col-span-2 rounded-md bg-accent py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60 sm:col-span-1">
          {busy ? "Adding…" : "Add"}
        </button>
      </form>
      <p className="mt-1 text-xs text-muted">The price is filled in with that day&apos;s close; change it to your actual fill price.</p>
      {error && <p className="mt-2 rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}

      {txns.length > 0 && (
        <div className="mt-4 max-h-72 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>
                <th className="py-1.5">Date</th>
                <th className="py-1.5">Type</th>
                <th className="py-1.5">Symbol</th>
                <th className="py-1.5 text-right">Shares</th>
                <th className="py-1.5 text-right">Price</th>
                <th className="py-1.5 text-right">Total</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {txns.map((t) => (
                <tr key={t.id} className="group border-t border-line">
                  <td className="tabular py-1.5 text-muted">{t.date}</td>
                  <td className={`py-1.5 capitalize ${t.side === "buy" ? "text-up" : "text-down"}`}>{t.side}</td>
                  <td className="py-1.5 font-medium">{t.symbol}</td>
                  <td className="tabular py-1.5 text-right">{num(t.shares)}</td>
                  <td className="tabular py-1.5 text-right">{usd(t.price)}</td>
                  <td className="tabular py-1.5 text-right">{usd(t.shares * t.price + (t.side === "buy" ? t.fees : -t.fees))}</td>
                  <td className="py-1.5 text-right">
                    <button onClick={() => remove(t)} className="invisible text-xs text-muted hover:text-down group-hover:visible">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
