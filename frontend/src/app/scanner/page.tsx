"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { ScoreBar } from "@/components/ScoreBadge";
import { ApiError, api } from "@/lib/api";
import type { ScanRow } from "@/lib/types";

type Tab = "bull" | "bear" | "rs";
const TABS: { id: Tab; label: string; hint: string }[] = [
  { id: "bull", label: "Upside candidates", hint: "Stocks set up for a major move up (Bull Score)." },
  { id: "bear", label: "Downside risk", hint: "Stocks showing signs of deterioration (Bear Score)." },
  { id: "rs", label: "RS leaders", hint: "The strongest stocks relative to the rest of the market." },
];

function Scanner() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("bull");
  const [minScore, setMinScore] = useState(0);
  const [templateOnly, setTemplateOnly] = useState(false);
  const [vcpOnly, setVcpOnly] = useState(false);
  const [rows, setRows] = useState<ScanRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    const qs = new URLSearchParams({ sort: tab, min_score: String(minScore), template_only: String(templateOnly), vcp_only: String(vcpOnly) });
    api<{ results: ScanRow[] }>(`/api/sepa/scan?${qs}`)
      .then((r) => setRows(r.results))
      .catch((e) => (e instanceof ApiError && e.status === 403 ? setLocked(e.message) : setError(e.message)))
      .finally(() => setLoading(false));
  }, [tab, minScore, templateOnly, vcpOnly]);

  if (locked) {
    return (
      <div className="grid h-full place-items-center p-6">
        <div className="max-w-md rounded-xl border border-amber-500/30 bg-amber-500/5 p-6 text-center">
          <h1 className="text-lg font-semibold">Move Detector</h1>
          <p className="mt-2 text-sm text-muted">{locked}</p>
          <Link href="/#preturi" className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-white">See plans</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-xl font-semibold">Move Detector</h1>
          <span className="text-xs text-muted">Scores refresh every 5 minutes</span>
        </div>
        <p className="mb-5 text-sm text-muted">{TABS.find((t) => t.id === tab)?.hint}</p>

        <div className="mb-4 flex flex-wrap items-center gap-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-md px-3 py-1.5 text-sm ${tab === t.id ? "bg-accent text-white" : "bg-panel text-muted hover:text-text"}`}
            >
              {t.label}
            </button>
          ))}
          <div className="ml-auto flex flex-wrap items-center gap-4 text-sm text-muted">
            {tab !== "rs" && (
              <label className="flex items-center gap-2">
                Min. score
                <select value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} className="rounded border border-line bg-bg px-2 py-1 text-text">
                  {[0, 45, 60, 75].map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </label>
            )}
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={templateOnly} onChange={(e) => setTemplateOnly(e.target.checked)} className="accent-blue-500" />
              Trend Template 8/8
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={vcpOnly} onChange={(e) => setVcpOnly(e.target.checked)} className="accent-blue-500" />
              VCP only
            </label>
          </div>
        </div>

        {error && <p className="mb-4 rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}

        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-panel text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3">Symbol</th>
                <th className="px-4 py-3 text-right">Price</th>
                <th className="px-4 py-3 text-right">Chg.</th>
                <th className="px-4 py-3">Bull</th>
                <th className="px-4 py-3">Bear</th>
                <th className="px-4 py-3 text-right">RS</th>
                <th className="px-4 py-3 text-right">TT</th>
                <th className="px-4 py-3 text-right">Pivot</th>
                <th className="px-4 py-3">Signals</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-muted">Scanning the market…</td>
                </tr>
              )}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-muted">No stocks match these filters.</td>
                </tr>
              )}
              {!loading &&
                rows.map((r) => (
                  <tr key={r.symbol} onClick={() => router.push(`/chart?s=${encodeURIComponent(r.symbol)}`)} className="cursor-pointer border-t border-line hover:bg-panel/70">
                    <td className="px-4 py-2.5">
                      <div className="font-medium">{r.symbol}</div>
                      <div className="max-w-[200px] truncate text-xs text-muted">{r.name}</div>
                    </td>
                    <td className="tabular px-4 py-2.5 text-right">{r.price.toFixed(2)}</td>
                    <td className={`tabular px-4 py-2.5 text-right ${r.change_pct >= 0 ? "text-up" : "text-down"}`}>
                      {r.change_pct >= 0 ? "+" : ""}
                      {r.change_pct.toFixed(2)}%
                    </td>
                    <td className="px-4 py-2.5"><ScoreBar score={r.bull_score} kind="bull" /></td>
                    <td className="px-4 py-2.5"><ScoreBar score={r.bear_score} kind="bear" /></td>
                    <td className={`tabular px-4 py-2.5 text-right ${(r.rs_rating ?? 0) >= 80 ? "text-up" : ""}`}>{r.rs_rating ?? "—"}</td>
                    <td className={`tabular px-4 py-2.5 text-right ${r.template_passed === 8 ? "text-up" : "text-muted"}`}>{r.template_passed}/8</td>
                    <td className="tabular px-4 py-2.5 text-right text-muted">
                      {r.pivot ? (
                        <>
                          {r.pivot.toFixed(2)}
                          <span className="block text-[11px]">{r.pivot_distance_pct! > 0 ? `${r.pivot_distance_pct}% below` : `${Math.abs(r.pivot_distance_pct!)}% above`}</span>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex flex-wrap gap-1">
                        {r.signals.map((s) => (
                          <span
                            key={s}
                            className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] ${s === "Downside risk" ? "bg-down/15 text-down" : "bg-up/10 text-up"}`}
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-xs text-muted">
          Scores are probability estimates based on technical patterns, not certainties. For educational purposes only. Not financial advice.
        </p>
      </div>
    </div>
  );
}

export default function ScannerPage() {
  return (
    <AppShell>
      <Scanner />
    </AppShell>
  );
}
