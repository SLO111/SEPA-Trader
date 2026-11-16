"use client";

import { useState } from "react";
import { post } from "@/lib/api";
import { fmt } from "@/lib/format";

type Txn = { date: string; symbol: string; side: "buy" | "sell"; shares: number; price: number; fees: number };
type Res = { format: string; txns: Txn[]; skipped: { row: number; reason: string }[]; error: string | null; saved: number };

/** Import a broker's trade export (CSV) into a portfolio: preview first, then save. */
export default function ImportCsv({ portfolioId, onClose, onSaved }: { portfolioId: number; onClose: () => void; onSaved: () => void }) {
  const [text, setText] = useState("");
  const [pdf, setPdf] = useState("");
  const [name, setName] = useState("");
  const [res, setRes] = useState<Res | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const preview = async (csv: string, pdfB64 = "") => {
    setBusy(true);
    setError("");
    try {
      setRes(await post<Res>(`/api/portfolios/${portfolioId}/import`, { csv, pdf_base64: pdfB64, dry_run: true }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const onFile = async (f: File | undefined) => {
    if (!f) return;
    if (f.size > 5_000_000) return setError("The file is larger than 5 MB.");
    setName(f.name);
    if (f.name.toLowerCase().endsWith(".pdf") || f.type === "application/pdf") {
      const b64 = await new Promise<string>((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result));
        r.onerror = () => reject(r.error);
        r.readAsDataURL(f);
      });
      setText("");
      setPdf(b64);
      preview("", b64);
    } else {
      const t = await f.text();
      setPdf("");
      setText(t);
      preview(t);
    }
  };
  const save = async () => {
    setBusy(true);
    try {
      const r = await post<Res>(`/api/portfolios/${portfolioId}/import`, { csv: text, pdf_base64: pdf, dry_run: false });
      if (r.error) setError(r.error);
      else {
        onSaved();
        onClose();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-3" onMouseDown={onClose}>
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-line bg-panel shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line p-4">
          <h2 className="font-semibold">Import trades from your broker (CSV or PDF)</h2>
          <button onClick={onClose} className="rounded px-2 py-1 text-muted hover:bg-panel-2" aria-label="Close">✕</button>
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          <p className="text-sm text-muted">
            Export your trade history from your broker as CSV (Interactive Brokers, Trading 212, XTB, Revolut, or any file with date, symbol, side, quantity
            and price columns) or upload a PDF statement: trade lines (date, buy/sell, ticker, quantity, price) are recognised automatically. Check the preview
            before importing, especially for PDFs.
          </p>
          <label className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-line p-6 text-center hover:border-accent">
            <span className="text-2xl">⬆</span>
            <span className="text-sm">{name || "Choose a CSV or PDF file"}</span>
            <span className="text-xs text-muted">Nothing is saved until you confirm</span>
            <input type="file" accept=".csv,.pdf,text/csv,text/plain,application/pdf" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
          </label>
          {busy && <p className="text-sm text-muted">Reading…</p>}
          {error && <p className="rounded bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
          {res && (
            <div className="space-y-3">
              <p className="text-sm">
                Detected format: <b>{res.format}</b> · <b>{res.txns.length}</b> transactions
                {res.skipped.length > 0 && <span className="text-muted"> · {res.skipped.length} rows skipped</span>}
              </p>
              {res.error && <p className="rounded bg-down/10 px-3 py-2 text-sm text-down">{res.error}</p>}
              <div className="max-h-72 overflow-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-panel text-left text-[11px] uppercase tracking-wide text-muted">
                    <tr><th className="px-3 py-2">Date</th><th className="px-3 py-2">Symbol</th><th className="px-3 py-2">Side</th><th className="px-3 py-2 text-right">Shares</th><th className="px-3 py-2 text-right">Price</th><th className="px-3 py-2 text-right">Fees</th></tr>
                  </thead>
                  <tbody>
                    {res.txns.slice(0, 300).map((t, i) => (
                      <tr key={i} className="border-t border-line">
                        <td className="tabular px-3 py-1.5">{t.date}</td>
                        <td className="px-3 py-1.5 font-medium">{t.symbol}</td>
                        <td className={`px-3 py-1.5 ${t.side === "buy" ? "text-up" : "text-down"}`}>{t.side}</td>
                        <td className="tabular px-3 py-1.5 text-right">{t.shares}</td>
                        <td className="tabular px-3 py-1.5 text-right">{fmt(t.price)}</td>
                        <td className="tabular px-3 py-1.5 text-right text-muted">{t.fees ? fmt(t.fees) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {res.skipped.length > 0 && (
                <details className="text-xs text-muted">
                  <summary className="cursor-pointer">Skipped rows</summary>
                  <ul className="mt-1 space-y-0.5">{res.skipped.slice(0, 50).map((s) => <li key={s.row}>Row {s.row}: {s.reason}</li>)}</ul>
                </details>
              )}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-line p-4">
          <button onClick={onClose} className="rounded-md px-4 py-2 text-sm text-muted hover:text-text">Cancel</button>
          <button onClick={save} disabled={!res || !res.txns.length || !!res.error || busy} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            Import {res?.txns.length ?? 0} transactions
          </button>
        </div>
      </div>
    </div>
  );
}
