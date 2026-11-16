"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { downloadExport } from "@/lib/csv";

/** "Export CSV" (Premium): downloads a server export, or shows a lock on other plans. */
export default function ExportButton({ path, filename, label = "Export CSV" }: { path: string; filename: string; label?: string }) {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!user?.limits.csv_export) {
    return (
      <Link href="/billing" title="CSV export is part of Premium" className="rounded-md border border-line px-2.5 py-1 text-xs text-muted/70 hover:text-amber-300">
        🔒 {label}
      </Link>
    );
  }
  return (
    <span className="inline-flex items-center gap-2">
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setErr("");
          try {
            await downloadExport(path, filename);
          } catch (e) {
            setErr(e instanceof Error ? e.message : "Export failed");
          } finally {
            setBusy(false);
          }
        }}
        className="rounded-md border border-line px-2.5 py-1 text-xs text-muted hover:text-text disabled:opacity-50"
      >
        {busy ? "Exporting…" : `⬇ ${label}`}
      </button>
      {err && <span className="text-xs text-down">{err}</span>}
    </span>
  );
}
