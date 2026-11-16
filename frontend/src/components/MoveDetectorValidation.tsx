"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmt, pct, tone } from "@/lib/format";

type Bucket = { bucket: string; samples: number; hit_rate: number; avg_fwd_5: number; avg_fwd_10: number; avg_fwd_20: number };
type Side = { base_rate: number; top10_hit_rate: number | null; lift: number | null; buckets: Bucket[] };
type ML = {
  available: boolean; reason?: string; avg_auc_model?: number; avg_auc_rules?: number; base_rate?: number; top10_model?: number; top10_rules?: number;
  verdict?: string; note?: string; folds?: { train_until: string; test_from: string; test_to: string; test_samples: number; base_rate: number; auc_model: number; auc_rules: number; top10_model: number; top10_rules: number }[];
};
type MD = { demo: boolean; validation: { samples: number; stocks: number; start: string; end: string; definition: { up: string; down: string }; bull: Side; bear: Side }; ml_up: ML; ml_down: ML };

function SideCard({ title, side, kind, def }: { title: string; side: Side; kind: "bull" | "bear"; def: string }) {
  const max = Math.max(...side.buckets.map((b) => b.hit_rate), side.base_rate, 1);
  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <h2 className="font-semibold">{title}</h2>
      <p className="text-xs text-muted">Hit = {def}</p>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-panel-2/60 p-2"><div className="text-[11px] text-muted">All stocks (base rate)</div><div className="tabular text-lg font-semibold">{side.base_rate}%</div></div>
        <div className="rounded-lg bg-panel-2/60 p-2"><div className="text-[11px] text-muted">Top 10 by score</div><div className={`tabular text-lg font-semibold ${kind === "bull" ? "text-up" : "text-down"}`}>{side.top10_hit_rate ?? "—"}%</div></div>
        <div className="rounded-lg bg-panel-2/60 p-2"><div className="text-[11px] text-muted">Lift</div><div className={`tabular text-lg font-semibold ${(side.lift ?? 0) > 1.1 ? "text-up" : "text-muted"}`}>{side.lift ? `${side.lift}×` : "—"}</div></div>
      </div>
      <table className="mt-4 w-full text-sm">
        <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
          <tr><th className="py-1.5">Score</th><th className="py-1.5">Hit rate</th><th className="py-1.5 text-right">Samples</th><th className="py-1.5 text-right">Avg move 5d</th><th className="py-1.5 text-right">20d</th></tr>
        </thead>
        <tbody>
          {side.buckets.map((b) => (
            <tr key={b.bucket} className="border-t border-line">
              <td className="tabular py-1.5">{b.bucket}</td>
              <td className="py-1.5">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-24 overflow-hidden rounded-full bg-line"><div className={`h-full ${kind === "bull" ? "bg-up" : "bg-down"}`} style={{ width: `${(b.hit_rate / max) * 100}%` }} /></div>
                  <span className="tabular text-xs">{b.hit_rate}%</span>
                </div>
              </td>
              <td className="tabular py-1.5 text-right text-muted">{b.samples}</td>
              <td className={`tabular py-1.5 text-right ${tone(b.avg_fwd_5)}`}>{pct(b.avg_fwd_5)}</td>
              <td className={`tabular py-1.5 text-right ${tone(b.avg_fwd_20)}`}>{pct(b.avg_fwd_20)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-muted">{kind === "bull" ? "Average moves are price changes." : "Average moves are shown as declines (positive = the stock fell)."}</p>
    </section>
  );
}

function MLCard({ title, ml }: { title: string; ml: ML }) {
  if (!ml.available) return <section className="rounded-xl border border-line bg-panel p-4"><h2 className="font-semibold">{title}</h2><p className="mt-2 text-sm text-muted">{ml.reason}</p></section>;
  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-sm">{ml.verdict}</p>
      <div className="mt-3 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
        {[["AUC model", fmt(ml.avg_auc_model, 3)], ["AUC rules", fmt(ml.avg_auc_rules, 3)], ["Top-10 hit, model", `${ml.top10_model}%`], ["Top-10 hit, rules", `${ml.top10_rules}%`]].map(([k, v]) => (
          <div key={k} className="rounded-lg bg-panel-2/60 p-2"><div className="text-[11px] text-muted">{k}</div><div className="tabular font-semibold">{v}</div></div>
        ))}
      </div>
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-muted">Walk-forward folds</summary>
        <table className="mt-2 w-full text-xs">
          <thead className="text-left text-muted"><tr><th className="py-1">Trained until</th><th>Tested</th><th className="text-right">Samples</th><th className="text-right">AUC model</th><th className="text-right">AUC rules</th></tr></thead>
          <tbody>
            {ml.folds?.map((f) => (
              <tr key={f.test_from} className="border-t border-line">
                <td className="tabular py-1">{f.train_until}</td><td className="tabular">{f.test_from} → {f.test_to}</td><td className="tabular text-right">{f.test_samples}</td>
                <td className="tabular text-right">{f.auc_model}</td><td className="tabular text-right">{f.auc_rules}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      <p className="mt-2 text-[11px] text-muted">Base rate in test periods: {ml.base_rate}%. {ml.note}</p>
    </section>
  );
}

export default function MoveDetectorValidation() {
  const [d, setD] = useState<MD | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<MD>("/api/backtest/move-detector").then(setD).catch((e) => setError(e.message));
  }, []);
  if (error) return <p className="text-sm text-down">{error}</p>;
  if (!d) return <p className="text-sm text-muted">Running the backtest across all stocks (this takes a few seconds the first time)…</p>;
  const v = d.validation;
  return (
    <div className="space-y-5">
      {d.demo && <p className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm text-amber-200">Demo data: these results come from generated prices and say nothing about real markets. Run with live data to validate the algorithm.</p>}
      <p className="text-sm text-muted">
        Tested on {v.samples.toLocaleString("en-US")} stock-days ({v.stocks} stocks, {v.start} → {v.end}). Each score only uses data available on that day; the outcome is what happened over the following 20 trading days.
      </p>
      <div className="grid gap-5 xl:grid-cols-2">
        <SideCard title="Bull Score → major move up" side={v.bull} kind="bull" def={v.definition.up} />
        <SideCard title="Bear Score → major move down" side={v.bear} kind="bear" def={v.definition.down} />
      </div>
      <h2 className="pt-2 text-lg font-semibold">Machine-learning layer (walk-forward)</h2>
      <div className="grid gap-5 xl:grid-cols-2">
        <MLCard title="Predicting major up moves" ml={d.ml_up} />
        <MLCard title="Predicting major down moves" ml={d.ml_down} />
      </div>
    </div>
  );
}

