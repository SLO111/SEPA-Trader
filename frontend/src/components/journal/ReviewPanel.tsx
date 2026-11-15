"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Review } from "./types";

export const GRADE_STYLE: Record<string, string> = {
  A: "bg-emerald-500/20 text-emerald-300", B: "bg-green-500/15 text-green-300", C: "bg-amber-500/15 text-amber-300",
  D: "bg-orange-500/20 text-orange-300", F: "bg-red-500/20 text-red-300",
};
const ICON = { pass: ["✓", "text-up"], warn: ["!", "text-amber-300"], fail: ["✗", "text-down"] } as const;

export default function ReviewPanel({ tradeId }: { tradeId: number }) {
  const [r, setR] = useState<Review | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Review>(`/api/journal/trades/${tradeId}/review`).then(setR).catch((e) => setError(e.message));
  }, [tradeId]);
  if (error) return <p className="text-sm text-down">{error}</p>;
  if (!r) return <p className="text-sm text-muted">Reviewing the trade…</p>;
  if (!r.grade) return <p className="text-sm text-muted">{r.summary}</p>;
  const cats = [...new Set(r.checks.map((c) => c.category))];
  return (
    <div className="grid gap-4 md:grid-cols-[140px_1fr]">
      <div className="text-center">
        <div className={`mx-auto grid h-20 w-20 place-items-center rounded-2xl text-4xl font-bold ${GRADE_STYLE[r.grade]}`}>{r.grade}</div>
        <div className="tabular mt-1 text-sm text-muted">{r.score}/100</div>
      </div>
      <div>
        <p className="font-medium">{r.summary}</p>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          {cats.map((cat) => (
            <div key={cat}>
              <div className="mb-1 text-[11px] uppercase tracking-wide text-muted">{cat}</div>
              <ul className="space-y-1 text-sm">
                {r.checks.filter((c) => c.category === cat).map((c) => (
                  <li key={c.text} className="flex gap-2">
                    <span className={`w-3 shrink-0 font-bold ${ICON[c.status][1]}`}>{ICON[c.status][0]}</span>
                    <span>{c.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        {r.notes && r.notes.length > 0 && (
          <div className="mt-3 rounded-lg bg-panel-2/60 p-3 text-sm text-muted">
            <div className="mb-1 text-[11px] uppercase tracking-wide">In hindsight</div>
            {r.notes.map((n) => <p key={n}>{n}</p>)}
          </div>
        )}
      </div>
    </div>
  );
}
