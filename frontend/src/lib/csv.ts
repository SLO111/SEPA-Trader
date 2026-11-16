/** Download rows as a CSV file (client-side export, e.g. backtest results). */
export function downloadCsv(rows: Record<string, unknown>[], filename: string) {
  if (!rows.length) return;
  const cols = Array.from(new Set(rows.flatMap((r) => Object.keys(r)))).filter((k) => rows.some((r) => typeof r[k] !== "object" || r[k] === null));
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const body = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([body], { type: "text/csv;charset=utf-8" }));
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/** Download a server CSV export (Premium) with the user's token. */
export async function downloadExport(path: string, filename: string) {
  const { BASE, getToken } = await import("./api");
  const r = await fetch(`${BASE}${path}`, { headers: { Authorization: `Bearer ${getToken() ?? ""}` } });
  if (!r.ok) {
    let msg = `Export failed (${r.status})`;
    try {
      msg = (await r.json()).detail ?? msg;
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob());
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
