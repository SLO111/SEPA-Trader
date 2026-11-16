"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Report = { rows: number; symbols: number; auc?: number; test_from?: string; base_rate?: number; all_avg_r?: number; picks?: number; picks_win_rate?: number | null; picks_avg_r?: number | null; top10_hit_rate?: number };
type Status = { trained: boolean; trained_at?: string; symbols?: number; report?: Record<string, Report>; trusted?: Record<string, boolean>; retrain_days?: number; min_prob?: number; min_ev?: number; horizon_days?: number };

export function AIBadge() {
  return <span className="rounded bg-gradient-to-r from-violet-500 to-cyan-500 px-1.5 py-0.5 text-[10px] font-bold text-white">vnicornAI</span>;
}

/** The model behind vnicornAI, with its honest walk-forward results (tested on a period it never saw). */
export default function VnicornAICard({ aiAvgR, rulesAvgR, aiClosed }: { aiAvgR?: number | null; rulesAvgR?: number | null; aiClosed?: number }) {
  const [s, setS] = useState<Status | null>(null);
  useEffect(() => {
    api<Status>("/api/ai/status").then(setS).catch(() => {});
  }, []);
  if (!s) return null;
  const r = (x: number | null | undefined, suffix = "R") => (x === null || x === undefined ? "—" : `${x > 0 ? "+" : ""}${x}${suffix}`);
  return (
    <section className="rounded-xl border border-violet-500/30 bg-gradient-to-br from-violet-500/10 to-panel p-4">
      <h2 className="mb-2 flex items-center gap-2 font-semibold">
        <AIBadge /> model
      </h2>
      {!s.trained ? (
        <p className="text-sm text-muted">Training starts with the next batch of ideas, after the close.</p>
      ) : (
        <>
          <p className="text-xs text-muted">
            Learns from {s.symbols} liquid stocks which plans (stop, trim, target) reached the target before the stop within {s.horizon_days} trading days. Retrained every {s.retrain_days} days
            {s.trained_at ? `, last on ${s.trained_at.slice(0, 10)}` : ""}.
          </p>
          <div className="mt-3 space-y-2 text-sm">
            {(["long", "short"] as const).map((side) => {
              const x = s.report?.[side];
              if (!x) return null;
              return (
                <div key={side} className="rounded-lg bg-panel-2/60 p-2.5">
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium capitalize">{side} plans</span>
                    {s.trusted?.[side] ? (
                      <span className="rounded bg-up/20 px-1.5 py-0.5 text-[10px] font-semibold text-up">Beats baseline</span>
                    ) : (
                      <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300" title="No AI ideas are published for this side until it does">Learning</span>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-1 text-center text-[11px]">
                    <div><div className="text-muted">AI picks</div><div className={`tabular font-semibold ${(x.picks_avg_r ?? 0) > 0 ? "text-up" : ""}`}>{r(x.picks_avg_r)}</div></div>
                    <div><div className="text-muted">All setups</div><div className="tabular font-semibold">{r(x.all_avg_r)}</div></div>
                    <div><div className="text-muted">Win rate</div><div className="tabular font-semibold">{x.picks_win_rate ?? "—"}{x.picks_win_rate != null ? "%" : ""}</div></div>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-[11px] text-muted">
            Walk-forward test since {s.report?.long?.test_from ?? "—"}: average result per trade of the AI&apos;s picks vs. taking every setup. AI ideas are published only for a side that beats the baseline.
          </p>
          {(aiClosed ?? 0) > 0 && (
            <div className="mt-2 flex justify-between border-t border-line pt-2 text-xs">
              <span className="text-muted">Live: vnicornAI vs. rules</span>
              <span className="tabular">
                <span className={(aiAvgR ?? 0) >= 0 ? "text-up" : "text-down"}>{r(aiAvgR)}</span> vs {r(rulesAvgR)}
              </span>
            </div>
          )}
        </>
      )}
    </section>
  );
}
