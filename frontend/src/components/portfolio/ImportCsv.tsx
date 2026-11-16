"use client";

import { useMemo, useState } from "react";
import { post } from "@/lib/api";
import { fmt } from "@/lib/format";

type Row = {
  id: number; symbol: string | null; found_by: string; name: string; isin: string; raw_symbol: string; shares: number; price: number; fees: number;
  current: number | null; date: string; side: "buy" | "sell"; status: "ok" | "unresolved" | "duplicate" | "check"; note: string; include: boolean;
};
type Change = { symbol: string; side: "buy" | "sell"; shares: number; price: number; date: string; note: string };
type Preview = {
  kind: "trades" | "positions" | null; as_of: string; format: string; rows: Row[]; skipped: { row: number; reason: string }[];
  tables: { index: number; rows: string[][] }[]; plan?: Change[]; error?: string;
};
const FIELDS = [
  ["date", "Date"], ["symbol", "Ticker / symbol"], ["name", "Company name"], ["isin", "ISIN"], ["side", "Buy / sell"],
  ["shares", "Quantity"], ["price", "Price"], ["fees", "Fees"],
] as const;
const STATUS: Record<Row["status"], [string, string]> = {
  ok: ["✓", "text-up"], unresolved: ["Ticker?", "text-down"], duplicate: ["Already imported", "text-muted"], check: ["Check price", "text-amber-300"],
};

/** Import from any broker: CSV, Excel or PDF, a list of trades or a statement of positions. Keeps the portfolio in sync. */
export default function ImportCsv({ portfolioId, onClose, onSaved }: { portfolioId: number; onClose: () => void; onSaved: () => void }) {
  const [file, setFile] = useState<{ name: string; b64: string } | null>(null);
  const [p, setP] = useState<Preview | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [closeMissing, setCloseMissing] = useState(true);
  const [mapping, setMapping] = useState<Record<string, number>>({});
  const [headerRow, setHeaderRow] = useState(0);
  const [done, setDone] = useState<string>("");

  const run = async (f: { name: string; b64: string }, map?: Record<string, number>, hdr?: number) => {
    setBusy(true);
    setError("");
    try {
      const r = await post<Preview>(`/api/portfolios/${portfolioId}/import/preview`, {
        filename: f.name, content_base64: f.b64, ...(map ? { mapping: map, header_row: hdr ?? 0 } : {}),
      });
      setP(r);
      setRows(r.rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const onFile = async (f: File | undefined) => {
    if (!f) return;
    if (f.size > 10_000_000) return setError("The file is larger than 10 MB.");
    const b64 = await new Promise<string>((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result));
      r.onerror = () => rej(r.error);
      r.readAsDataURL(f);
    });
    const ff = { name: f.name, b64 };
    setFile(ff);
    setDone("");
    setMapping({});
    run(ff);
  };
  const edit = (id: number, patch: Partial<Row>) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  const plan = useMemo(() => (p?.plan ?? []).filter((c) => closeMissing || !c.note.includes("not on the statement")), [p, closeMissing]);
  const usable = rows.filter((r) => r.include && r.symbol);
  const save = async () => {
    if (!p?.kind) return;
    setBusy(true);
    setError("");
    try {
      const r = await post<{ added: number; skipped_duplicates: number }>(`/api/portfolios/${portfolioId}/import/apply`, {
        kind: p.kind, as_of: p.as_of, rows, close_missing: closeMissing,
      });
      onSaved();
      window.dispatchEvent(new Event("portfolio-changed"));
      setDone(r.added ? `Done: ${r.added} transaction${r.added === 1 ? "" : "s"} added${r.skipped_duplicates ? `, ${r.skipped_duplicates} already imported` : ""}.` : "Nothing new: the portfolio already matches this file.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const columns = p?.tables?.[0]?.rows?.[headerRow] ?? [];

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-2 sm:p-4" onMouseDown={onClose}>
      <div className="flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-line bg-panel shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line p-4">
          <h2 className="font-semibold">Import from your broker</h2>
          <button onClick={onClose} className="rounded px-2 py-1 text-muted hover:bg-panel-2" aria-label="Close">✕</button>
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          <p className="text-sm text-muted">
            Any broker, any format: <b>CSV, Excel (.xlsx / .xls) or PDF</b>. Upload a list of trades or a statement of your positions. Columns are
            recognised automatically in English, Romanian, German, French, Spanish, Italian, Dutch and Polish; tickers are found from the symbol, the ISIN or the
            company name. Importing again keeps the portfolio in sync: trades already imported are skipped, and a positions statement updates quantities.
          </p>
          <label className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-line p-5 text-center hover:border-accent">
            <span className="text-2xl">⬆</span>
            <span className="text-sm">{file?.name || "Choose a file (CSV, Excel or PDF)"}</span>
            <span className="text-xs text-muted">Nothing is saved until you confirm</span>
            <input type="file" accept=".csv,.txt,.tsv,.xlsx,.xlsm,.xls,.pdf" className="hidden" onChange={(e) => onFile(e.target.files?.[0])} />
          </label>
          {busy && <p className="text-sm text-muted">Reading…</p>}
          {error && <p className="rounded bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
          {done && <p className="rounded bg-up/10 px-3 py-2 text-sm text-up">{done}</p>}

          {p && !p.kind && p.tables.length > 0 && (
            <section className="space-y-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
              <p className="text-sm">The columns weren&apos;t recognised automatically. Tell us which column is which:</p>
              <label className="flex items-center gap-2 text-sm text-muted">
                Header row
                <select value={headerRow} onChange={(e) => setHeaderRow(Number(e.target.value))} className="rounded border border-line bg-bg px-2 py-1 text-text">
                  {p.tables[0].rows.map((r, i) => <option key={i} value={i}>{i + 1}: {r.slice(0, 4).join(" | ").slice(0, 60)}</option>)}
                </select>
              </label>
              <div className="grid gap-2 sm:grid-cols-4">
                {FIELDS.map(([k, label]) => (
                  <label key={k} className="text-xs text-muted">
                    {label}
                    <select value={mapping[k] ?? ""} onChange={(e) => setMapping((m) => { const n = { ...m }; if (e.target.value === "") delete n[k]; else n[k] = Number(e.target.value); return n; })}
                      className="mt-0.5 w-full rounded border border-line bg-bg px-2 py-1 text-sm text-text">
                      <option value="">—</option>
                      {columns.map((c, i) => <option key={i} value={i}>{c || `Column ${i + 1}`}</option>)}
                    </select>
                  </label>
                ))}
              </div>
              <button onClick={() => file && run(file, mapping, headerRow)} disabled={!("shares" in mapping && "price" in mapping)}
                className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40">Read with these columns</button>
            </section>
          )}

          {p?.kind && (
            <div className="space-y-3">
              <p className="text-sm">
                Detected: <b>{p.kind === "positions" ? `Positions statement as of ${p.as_of}` : "Trades"}</b> · {rows.length} rows · <span className="text-muted">{p.format}</span>
                {p.skipped.length > 0 && <span className="text-muted"> · {p.skipped.length} rows skipped</span>}
              </p>
              {p.error && <p className="rounded bg-down/10 px-3 py-2 text-sm text-down">{p.error}</p>}
              <div className="max-h-80 overflow-auto rounded-lg border border-line">
                <table className="w-full min-w-[760px] text-sm">
                  <thead className="sticky top-0 z-[1] bg-panel text-left text-[11px] uppercase tracking-wide text-muted">
                    <tr>
                      <th className="px-2 py-2" />
                      {p.kind === "trades" && <th className="px-2 py-2">Date</th>}
                      <th className="px-2 py-2">Ticker</th>
                      <th className="px-2 py-2">As in the file</th>
                      {p.kind === "trades" && <th className="px-2 py-2">Side</th>}
                      <th className="px-2 py-2 text-right">Shares</th>
                      <th className="px-2 py-2 text-right">{p.kind === "positions" ? "Avg price" : "Price"}</th>
                      <th className="px-2 py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id} className={`border-t border-line ${r.include ? "" : "opacity-50"}`}>
                        <td className="px-2 py-1.5"><input type="checkbox" checked={r.include} onChange={(e) => edit(r.id, { include: e.target.checked })} className="accent-blue-500" /></td>
                        {p.kind === "trades" && <td className="tabular px-2 py-1.5 text-xs">{r.date}</td>}
                        <td className="px-2 py-1.5">
                          <input value={r.symbol ?? ""} placeholder="e.g. NVDA" onChange={(e) => edit(r.id, { symbol: e.target.value.toUpperCase(), include: !!e.target.value, status: r.status === "unresolved" ? "ok" : r.status })}
                            className={`w-20 rounded border bg-bg px-1.5 py-0.5 font-semibold ${r.symbol ? "border-line" : "border-down"}`} />
                          {r.found_by && r.symbol && <div className="text-[10px] text-muted">via {r.found_by}</div>}
                        </td>
                        <td className="max-w-[220px] px-2 py-1.5 text-xs text-muted">
                          <div className="truncate" title={r.name || r.raw_symbol}>{r.name || r.raw_symbol}</div>
                          {r.isin && <div className="text-[10px]">{r.isin}</div>}
                        </td>
                        {p.kind === "trades" && <td className={`px-2 py-1.5 ${r.side === "buy" ? "text-up" : "text-down"}`}>{r.side}</td>}
                        <td className="px-2 py-1.5 text-right"><input type="number" step="any" value={r.shares} onChange={(e) => edit(r.id, { shares: Number(e.target.value) })} className="tabular w-20 rounded border border-line bg-bg px-1.5 py-0.5 text-right" /></td>
                        <td className="px-2 py-1.5 text-right"><input type="number" step="any" value={r.price} onChange={(e) => edit(r.id, { price: Number(e.target.value) })} className="tabular w-24 rounded border border-line bg-bg px-1.5 py-0.5 text-right" /></td>
                        <td className="px-2 py-1.5 text-xs">
                          <span className={STATUS[r.status][1]}>{STATUS[r.status][0]}</span>
                          {r.note && <div className="max-w-[220px] text-[10px] text-muted">{r.note}</div>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {p.kind === "positions" && (
                <section className="rounded-lg border border-line bg-panel-2/40 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold">What changes in the portfolio (dated {p.as_of})</h3>
                    <label className="flex items-center gap-2 text-xs text-muted">
                      <input type="checkbox" checked={closeMissing} onChange={(e) => setCloseMissing(e.target.checked)} className="accent-blue-500" />
                      Close positions that are not on the statement
                    </label>
                  </div>
                  {plan.length === 0 ? (
                    <p className="text-sm text-muted">Nothing changes: the portfolio already matches this statement.</p>
                  ) : (
                    <ul className="space-y-1 text-sm">
                      {plan.map((c, i) => (
                        <li key={i} className="flex flex-wrap gap-x-2">
                          <span className={c.side === "buy" ? "text-up" : "text-down"}>{c.side === "buy" ? "+ Buy" : "− Sell"}</span>
                          <b>{c.shares}</b> <b>{c.symbol}</b> <span className="tabular text-muted">@ {fmt(c.price)}</span>
                          <span className="text-xs text-muted">({c.note})</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-2 text-[11px] text-muted">If you edit tickers or quantities above, the changes are recalculated when you import.</p>
                </section>
              )}
              {p.skipped.length > 0 && (
                <details className="text-xs text-muted">
                  <summary className="cursor-pointer">Skipped rows</summary>
                  <ul className="mt-1 space-y-0.5">{p.skipped.slice(0, 50).map((s, i) => <li key={i}>Row {s.row}: {s.reason}</li>)}</ul>
                </details>
              )}
            </div>
          )}
          {p && !p.kind && p.tables.length === 0 && (
            <p className="rounded bg-down/10 px-3 py-2 text-sm text-down">{p.skipped[0]?.reason ?? "Nothing recognised in this file."}</p>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-line p-4">
          <button onClick={onClose} className="rounded-md px-4 py-2 text-sm text-muted hover:text-text">{done ? "Close" : "Cancel"}</button>
          <button onClick={save} disabled={!p?.kind || !usable.length || busy || !!done} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
            {p?.kind === "positions" ? "Update portfolio" : `Import ${usable.filter((r) => r.status !== "duplicate").length} trades`}
          </button>
        </div>
      </div>
    </div>
  );
}
