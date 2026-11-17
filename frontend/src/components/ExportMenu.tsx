"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { downloadExport } from "@/lib/csv";

/** Export in Excel, PDF (Vnicorn Investments branded) or CSV. Premium. */
export default function ExportMenu({ path, filename, label }: { path: string; filename: string; label: string }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!user?.limits.csv_export) {
    return (
      <Link href="/billing" title="Exports are part of Premium" className="rounded-md border border-line px-2.5 py-1 text-xs text-muted/70 hover:text-amber-300">
        🔒 {label}
      </Link>
    );
  }
  const go = async (fmt: "xlsx" | "pdf" | "csv") => {
    setOpen(false);
    setBusy(true);
    setErr("");
    try {
      await downloadExport(`${path}${path.includes("?") ? "&" : "?"}format=${fmt}`, `${filename}.${fmt}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(false);
    }
  };
  return (
    <span className="relative inline-flex items-center gap-2">
      <button onClick={() => setOpen((o) => !o)} disabled={busy} className="rounded-md border border-line px-2.5 py-1 text-xs text-muted hover:text-text disabled:opacity-50">
        {busy ? "Exporting…" : `⬇ ${label}`}
      </button>
      {open && (
        <span className="absolute right-0 top-full z-30 mt-1 w-40 rounded-md border border-line bg-panel-2 p-1 text-xs shadow-xl">
          <button onClick={() => go("xlsx")} className="block w-full rounded px-2 py-1.5 text-left hover:bg-line">Excel (branded)</button>
          <button onClick={() => go("pdf")} className="block w-full rounded px-2 py-1.5 text-left hover:bg-line">PDF report</button>
          <button onClick={() => go("csv")} className="block w-full rounded px-2 py-1.5 text-left hover:bg-line">CSV (raw data)</button>
        </span>
      )}
      {err && <span className="text-xs text-down">{err}</span>}
    </span>
  );
}
