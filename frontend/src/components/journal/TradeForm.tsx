"use client";

import { useEffect, useState } from "react";
import { api, post, put } from "@/lib/api";
import type { JTrade } from "./types";

const today = () => new Date().toISOString().slice(0, 10);
const field = "w-full rounded border border-line bg-bg px-2 py-1.5 text-sm outline-none focus:border-accent";

type Draft = Record<string, string>;

// Defined outside the form so inputs keep focus while typing.
function L({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block text-xs text-muted">
      {label}
      <div className="mt-1">{children}</div>
      {hint && <div className="mt-0.5 text-[11px]">{hint}</div>}
    </label>
  );
}

const toDraft = (t?: JTrade): Draft => ({
  symbol: t?.symbol ?? "", side: t?.side ?? "long", setup: t?.setup ?? "", entry_date: t?.entry_date ?? today(),
  entry_price: t ? String(t.entry_price) : "", shares: t ? String(t.shares) : "", stop_price: t?.stop_price ? String(t.stop_price) : "",
  target_price: t?.target_price ? String(t.target_price) : "", exit_date: t?.exit_date ?? "", exit_price: t?.exit_price ? String(t.exit_price) : "",
  fees: t?.fees ? String(t.fees) : "", notes: t?.notes ?? "",
});

export default function TradeForm({ setups, initial, onSaved, onCancel }: { setups: string[]; initial?: JTrade; onSaved: (t: JTrade) => void; onCancel: () => void }) {
  const [d, setD] = useState<Draft>(toDraft(initial));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setD((x) => ({ ...x, [k]: v }));

  // Suggest the entry price from that day's close when logging a new trade.
  useEffect(() => {
    if (initial || !d.symbol.trim() || !d.entry_date || d.entry_price) return;
    const t = setTimeout(() => {
      api<{ price: number | null }>(`/api/market/price/${encodeURIComponent(d.symbol.trim())}?on=${d.entry_date}`)
        .then((r) => r.price && setD((x) => (x.entry_price ? x : { ...x, entry_price: String(r.price) })))
        .catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [d.symbol, d.entry_date, d.entry_price, initial]);

  const num = (v: string) => (v.trim() ? Number(v) : null);
  const risk = num(d.entry_price) && num(d.stop_price) ? (Math.abs(num(d.entry_price)! - num(d.stop_price)!) / num(d.entry_price)!) * 100 : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    const body = {
      symbol: d.symbol.trim(), side: d.side, setup: d.setup, entry_date: d.entry_date, entry_price: num(d.entry_price), shares: num(d.shares),
      stop_price: num(d.stop_price), target_price: num(d.target_price), exit_date: d.exit_date || null, exit_price: num(d.exit_price),
      fees: num(d.fees) ?? 0, notes: d.notes,
    };
    try {
      onSaved(initial ? await put<JTrade>(`/api/journal/trades/${initial.id}`, body) : await post<JTrade>("/api/journal/trades", body));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="rounded-xl border border-line bg-panel p-4">
      <h2 className="mb-3 font-semibold">{initial ? `Edit ${initial.symbol} trade` : "Log a trade"}</h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        <L label="Symbol"><input required value={d.symbol} onChange={(e) => set("symbol", e.target.value.toUpperCase())} className={field} placeholder="AAPL" /></L>
        <L label="Direction">
          <select value={d.side} onChange={(e) => set("side", e.target.value)} className={field}>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </L>
        <L label="Setup">
          <select value={d.setup} onChange={(e) => set("setup", e.target.value)} className={field}>
            <option value="">—</option>
            {setups.map((s) => <option key={s}>{s}</option>)}
          </select>
        </L>
        <L label="Entry date"><input required type="date" max={today()} value={d.entry_date} onChange={(e) => set("entry_date", e.target.value)} className={field} /></L>
        <L label="Entry price"><input required type="number" step="any" min="0" value={d.entry_price} onChange={(e) => set("entry_price", e.target.value)} className={field} /></L>
        <L label="Shares"><input required type="number" step="any" min="0" value={d.shares} onChange={(e) => set("shares", e.target.value)} className={field} /></L>
        <L label="Stop-loss" hint={risk !== null ? `Risk ${risk.toFixed(1)}%` : "Recommended"}><input type="number" step="any" min="0" value={d.stop_price} onChange={(e) => set("stop_price", e.target.value)} className={field} /></L>
        <L label="Target (optional)"><input type="number" step="any" min="0" value={d.target_price} onChange={(e) => set("target_price", e.target.value)} className={field} /></L>
        <L label="Exit date" hint="Leave empty if still open"><input type="date" max={today()} value={d.exit_date} onChange={(e) => set("exit_date", e.target.value)} className={field} /></L>
        <L label="Exit price"><input type="number" step="any" min="0" value={d.exit_price} onChange={(e) => set("exit_price", e.target.value)} className={field} /></L>
        <L label="Fees"><input type="number" step="any" min="0" value={d.fees} onChange={(e) => set("fees", e.target.value)} className={field} /></L>
      </div>
      <label className="mt-3 block text-xs text-muted">
        Notes (why you took it, how you felt, what you learned)
        <textarea value={d.notes} onChange={(e) => set("notes", e.target.value)} rows={2} className={`${field} mt-1`} />
      </label>
      {error && <p className="mt-3 rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button disabled={busy} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60">{busy ? "Saving…" : initial ? "Save changes" : "Add trade"}</button>
        <button type="button" onClick={onCancel} className="rounded-md px-4 py-2 text-sm text-muted hover:text-text">Cancel</button>
      </div>
    </form>
  );
}
