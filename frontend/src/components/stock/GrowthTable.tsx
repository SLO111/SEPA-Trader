"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { compactUsd, pct, tone } from "@/lib/format";

type Q = { date: string; eps: number; eps_yoy: number | null; eps_surprise_pct: number | null; revenue: number | null; revenue_yoy: number | null };
type T = { quarters: Q[]; eps_accelerating: boolean | null; revenue_accelerating: boolean | null; canslim_c: boolean; locked?: boolean;
  group?: { group: string; rank: number; of: number } | null };

/** Quarterly EPS & sales growth with acceleration (Pro). Free sees the latest quarter. */
export default function GrowthTable({ symbol }: { symbol: string }) {
  const [t, setT] = useState<T | null>(null);
  useEffect(() => {
    setT(null);
    api<T>(`/api/stock/${encodeURIComponent(symbol)}/quarterly`).then(setT).catch(() => {});
  }, [symbol]);
  if (!t) return <p className="text-sm text-muted">Loading earnings…</p>;
  if (!t.quarters.length) return <p className="text-sm text-muted">No quarterly earnings data available.</p>;
  const Flag = ({ on, label }: { on: boolean | null; label: string }) =>
    on === null ? null : <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${on ? "bg-up/15 text-up" : "bg-panel-2 text-muted"}`}>{on ? "▲ " : ""}{label}{on ? " accelerating" : " not accelerating"}</span>;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Flag on={t.eps_accelerating} label="EPS" />
        <Flag on={t.revenue_accelerating} label="Sales" />
        {t.canslim_c && <span className="rounded bg-violet-500/15 px-1.5 py-0.5 text-[11px] font-semibold text-violet-200">EPS +25% YoY</span>}
        {t.group && <span className="rounded bg-sky-500/15 px-1.5 py-0.5 text-[11px] font-semibold text-sky-300">Group #{t.group.rank}/{t.group.of} · {t.group.group}</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
            <tr><th className="py-1.5">Reported</th><th className="py-1.5 text-right">EPS</th><th className="py-1.5 text-right">EPS YoY</th><th className="py-1.5 text-right">Surprise</th><th className="py-1.5 text-right">Sales</th><th className="py-1.5 text-right">Sales YoY</th></tr>
          </thead>
          <tbody>
            {t.quarters.map((q) => (
              <tr key={q.date} className="border-t border-line">
                <td className="tabular py-1.5">{q.date}</td>
                <td className="tabular py-1.5 text-right">{q.eps.toFixed(2)}</td>
                <td className={`tabular py-1.5 text-right font-medium ${tone(q.eps_yoy)}`}>{pct(q.eps_yoy, 0)}</td>
                <td className={`tabular py-1.5 text-right ${tone(q.eps_surprise_pct)}`}>{pct(q.eps_surprise_pct, 1)}</td>
                <td className="tabular py-1.5 text-right">{compactUsd(q.revenue)}</td>
                <td className={`tabular py-1.5 text-right ${tone(q.revenue_yoy)}`}>{pct(q.revenue_yoy, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {t.locked && <p className="text-xs text-amber-300">🔒 8 quarters of EPS and sales growth, with acceleration flags: <Link href="/billing" className="underline">Pro</Link>.</p>}
    </div>
  );
}
