"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ScoreBlock, SepaReport } from "@/lib/types";
import { scoreColor } from "./ScoreBadge";

function Chip({ label, value, tone = "text-text" }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <span className="flex items-baseline gap-1.5 whitespace-nowrap">
      <span className="text-[11px] uppercase tracking-wide text-muted">{label}</span>
      <span className={`tabular text-sm font-medium ${tone}`}>{value}</span>
    </span>
  );
}

function Factors({ title, block, kind }: { title: string; block: ScoreBlock; kind: "bull" | "bear" }) {
  return (
    <div>
      <h4 className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 text-sm font-semibold">
        {title}
        <span className={`tabular whitespace-nowrap ${scoreColor(block.score, kind)}`}>
          {block.score ?? "—"} · {block.label}
        </span>
      </h4>
      <ul className="space-y-1.5">
        {block.factors.map((f) => (
          <li key={f.key} className="grid grid-cols-[1fr_80px_36px] items-center gap-2 text-xs">
            <span className="text-muted">{f.label}</span>
            <span className="h-1.5 overflow-hidden rounded-full bg-line">
              <span className={`block h-full ${kind === "bull" ? "bg-up" : "bg-down"}`} style={{ width: `${f.value * 100}%` }} />
            </span>
            <span className="tabular text-right">+{f.contribution}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function SepaStrip({ symbol }: { symbol: string }) {
  const [rep, setRep] = useState<SepaReport | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setRep(null);
    api<SepaReport>(`/api/sepa/${encodeURIComponent(symbol)}`).then(setRep).catch(() => setRep(null));
  }, [symbol]);

  if (!rep) return <div className="h-9 border-b border-line" />;
  const tt = rep.trend_template;
  const md = rep.move_detector;
  const v = rep.vcp;

  return (
    <div className="relative border-b border-line">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full flex-wrap items-center gap-x-5 gap-y-1 px-4 py-2 text-left hover:bg-panel/60">
        <Chip label="RS" value={rep.rs_rating ?? "—"} tone={(rep.rs_rating ?? 0) >= 80 ? "text-up" : "text-text"} />
        <Chip label="Trend Template" value={`${tt.passed_count}/8`} tone={tt.all_passed ? "text-up" : tt.passed_count <= 3 ? "text-down" : "text-amber-300"} />
        <Chip
          label="VCP"
          value={v.detected ? `da · pivot ${v.pivot} (${v.distance_pct! > 0 ? "-" : "+"}${Math.abs(v.distance_pct!)}%)` : "nu"}
          tone={v.detected ? "text-up" : "text-muted"}
        />
        {md ? (
          <>
            <Chip label="Bull" value={md.bull.score ?? "—"} tone={scoreColor(md.bull.score, "bull")} />
            <Chip label="Bear" value={md.bear.score ?? "—"} tone={scoreColor(md.bear.score, "bear")} />
          </>
        ) : (
          <Chip label="Move Detector" value="Pro" tone="text-amber-300" />
        )}
        <span className="ml-auto text-xs text-muted">{open ? "Ascunde ▲" : "Detalii ▼"}</span>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full z-20 grid max-h-[70vh] gap-6 overflow-y-auto border-b border-line bg-panel p-4 shadow-2xl md:grid-cols-3">
          <div>
            <h4 className="mb-2 text-sm font-semibold">Trend Template · {tt.passed_count}/8</h4>
            <ul className="space-y-1.5 text-xs">
              {tt.criteria.map((c) => (
                <li key={c.label} className="flex gap-2">
                  <span className={c.passed ? "text-up" : "text-down"}>{c.passed ? "✓" : "✗"}</span>
                  <span className={c.passed ? "" : "text-muted"}>{c.label}</span>
                </li>
              ))}
            </ul>
            <h4 className="mb-2 mt-5 text-sm font-semibold">VCP</h4>
            {v.contractions.length > 0 && (
              <p className="mb-2 text-xs text-muted">Contracții: {v.contractions.map((c) => `−${c.depth_pct}%`).join(" → ")}</p>
            )}
            {v.checks ? (
              <ul className="space-y-1.5 text-xs">
                {Object.entries(v.checks).map(([k, ok]) => (
                  <li key={k} className="flex gap-2">
                    <span className={ok ? "text-up" : "text-down"}>{ok ? "✓" : "✗"}</span>
                    <span className={ok ? "" : "text-muted"}>{k}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted">{v.reason}</p>
            )}
            {v.pivot && (
              <p className="tabular mt-2 text-xs">
                Pivot <b>{v.pivot}</b> · Stop <b>{v.stop}</b> · Risc {v.risk_pct}%
              </p>
            )}
          </div>
          {md ? (
            <>
              <Factors title="Bull Score: potențial de creștere" block={md.bull} kind="bull" />
              <Factors title="Bear Score: risc de scădere" block={md.bear} kind="bear" />
            </>
          ) : (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-sm md:col-span-2">
              <p className="font-medium text-amber-300">Move Detector este disponibil în planurile Pro și Premium.</p>
              <p className="mt-1 text-muted">Primești scorurile Bull/Bear cu explicația pe factori și scanner-ul care caută în toată piața acțiunile pregătite pentru o mișcare majoră.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
