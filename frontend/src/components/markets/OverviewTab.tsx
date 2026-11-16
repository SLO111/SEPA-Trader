"use client";

import Link from "next/link";
import { useState } from "react";
import { ScoreBar } from "@/components/ScoreBadge";
import { fmt, pct, tone } from "@/lib/format";
import FearGreedGauge from "./FearGreedGauge";
import type { MoverRow, Overview } from "./types";

export function Panel({ title, right, children, className = "" }: { title: string; right?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-line bg-panel p-4 ${className}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export const StockLink = ({ s }: { s: string }) => (
  <Link href={`/stock?s=${encodeURIComponent(s)}`} className="font-medium hover:text-accent">
    {s}
  </Link>
);

function Spark({ values, up }: { values: number[]; up: boolean }) {
  if (values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${30 - ((v - min) / span) * 28}`).join(" ");
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className="h-8 w-full">
      <polyline points={pts} fill="none" stroke={up ? "#22c55e" : "#ef4444"} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function MoverTable({ rows }: { rows: MoverRow[] }) {
  if (!rows.length) return <p className="py-4 text-sm text-muted">Nothing to show right now.</p>;
  return (
    <table className="w-full text-sm">
      <tbody>
        {rows.map((r) => (
          <tr key={r.symbol} className="border-t border-line first:border-0">
            <td className="py-1.5">
              <StockLink s={r.symbol} />
              <div className="max-w-[160px] truncate text-xs text-muted">{r.name}</div>
            </td>
            <td className="tabular py-1.5 text-right">{fmt(r.price)}</td>
            <td className={`tabular py-1.5 text-right ${tone(r.change_pct)}`}>{pct(r.change_pct)}</td>
            <td className="tabular hidden py-1.5 text-right text-xs text-muted sm:table-cell">{r.rel_volume ? `${r.rel_volume.toFixed(1)}× vol` : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const STAGES = [
  { n: 1, name: "Accumulation", hint: "Base after a decline. Watch, build a watchlist.", cls: "bg-slate-500/30 text-slate-200" },
  { n: 2, name: "Markup", hint: "Uptrend. The stage to own stocks.", cls: "bg-up/30 text-up" },
  { n: 3, name: "Distribution", hint: "Topping. Take profits, tighten stops.", cls: "bg-amber-500/30 text-amber-300" },
  { n: 4, name: "Markdown", hint: "Downtrend. Cash or shorts, no new longs.", cls: "bg-down/30 text-down" },
];

function CyclePanel({ rows }: { rows: Overview["cycle"] }) {
  return (
    <Panel title="Market cycle" right={<span className="text-xs text-muted">Stage analysis on the 30-week average</span>}>
      <div className="grid gap-3 lg:grid-cols-3">
        {rows.map((r) => {
          const cur = STAGES[r.stage - 1];
          return (
            <Link key={r.symbol} href={`/chart?s=${r.symbol}`} className="rounded-lg bg-panel-2/50 p-3 hover:bg-panel-2">
              <div className="flex items-baseline justify-between">
                <span className="font-medium">{r.label}</span>
                <span className="text-[11px] text-muted">{r.weeks} wk · since {r.since}</span>
              </div>
              <div className="mt-2 grid grid-cols-4 gap-1">
                {STAGES.map((s) => (
                  <div key={s.n} className={`rounded py-1 text-center text-[10px] font-semibold ${s.n === r.stage ? s.cls : "bg-line/40 text-muted/60"}`}>
                    {s.n}. {s.name}
                  </div>
                ))}
              </div>
              <div className="mt-2 text-xs text-muted">
                {cur.hint} 30-wk MA {fmt(r.ma30w)} ({r.slope_pct >= 0 ? "+" : ""}
                {r.slope_pct}% / 4 wk)
              </div>
            </Link>
          );
        })}
      </div>
    </Panel>
  );
}

export default function OverviewTab({ o, onFearGreed }: { o: Overview; onFearGreed: () => void }) {
  const [moverTab, setMoverTab] = useState<"gainers" | "losers" | "active">("gainers");
  const b = o.breadth;
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {o.indices.map((i) => {
          const up = i.symbol === "^VIX" ? i.change <= 0 : i.change >= 0;
          return (
            <div key={i.symbol} className="rounded-xl border border-line bg-panel p-3">
              <div className="text-xs text-muted">{i.label}</div>
              <div className="tabular text-lg font-semibold">{fmt(i.price)}</div>
              <div className={`tabular text-xs ${i.change >= 0 ? (i.symbol === "^VIX" ? "text-down" : "text-up") : i.symbol === "^VIX" ? "text-up" : "text-down"}`}>
                {i.change >= 0 ? "+" : ""}
                {fmt(i.change)} ({pct(i.change_pct)})
              </div>
              <Spark values={i.spark} up={up} />
            </div>
          );
        })}
      </div>

      {o.cycle?.length > 0 && <CyclePanel rows={o.cycle} />}

      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        <Panel title="Fear & Greed" right={<button onClick={onFearGreed} className="text-xs text-accent hover:underline">Details</button>}>
          <div className="flex flex-col items-center">
            <FearGreedGauge score={o.fear_greed.score} label={o.fear_greed.label} size={240} />
            <div className="text-lg font-semibold">{o.fear_greed.label}</div>
            <div className="mt-2 grid w-full grid-cols-3 gap-2 text-center text-xs">
              {(["close", "week", "month"] as const).map((k) => (
                <div key={k} className="rounded bg-panel-2/60 py-1">
                  <div className="text-muted">{k === "close" ? "Yesterday" : k === "week" ? "1 week ago" : "1 month ago"}</div>
                  <div className="tabular font-medium">{o.fear_greed.previous[k] !== null ? Math.round(o.fear_greed.previous[k]!) : "—"}</div>
                </div>
              ))}
            </div>
          </div>
        </Panel>

        <Panel
          title="Movers"
          right={
            <div className="flex gap-1">
              {(["gainers", "losers", "active"] as const).map((t) => (
                <button key={t} onClick={() => setMoverTab(t)} className={`rounded px-2 py-0.5 text-xs ${moverTab === t ? "bg-accent text-white" : "text-muted hover:text-text"}`}>
                  {t === "gainers" ? "Top gainers" : t === "losers" ? "Top losers" : "Most active"}
                </button>
              ))}
            </div>
          }
        >
          <div className="grid gap-5 md:grid-cols-[1fr_200px]">
            <MoverTable rows={o[moverTab]} />
            <div className="space-y-3 text-sm">
              <div className="text-[11px] uppercase tracking-wide text-muted">Market breadth</div>
              <div>
                <div className="flex justify-between text-xs">
                  <span className="text-up">{b.advancing} advancing</span>
                  <span className="text-down">{b.declining} declining</span>
                </div>
                <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-line">
                  <div className="bg-up" style={{ width: `${(b.advancing / Math.max(b.advancing + b.declining, 1)) * 100}%` }} />
                  <div className="bg-down" style={{ width: `${(b.declining / Math.max(b.advancing + b.declining, 1)) * 100}%` }} />
                </div>
              </div>
              <div className="flex justify-between"><span className="text-muted">New 52-week highs</span><span className="tabular text-up">{b.new_highs}</span></div>
              <div className="flex justify-between"><span className="text-muted">New 52-week lows</span><span className="tabular text-down">{b.new_lows}</span></div>
              <div className="flex justify-between"><span className="text-muted">Above 50-day MA</span><span className="tabular">{b.pct_above_ma50 ?? "—"}%</span></div>
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Sector rotation & emerging themes">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
                <tr>
                  <th className="py-1.5">Sector</th>
                  <th className="px-2 py-1.5 text-right">1W</th>
                  <th className="px-2 py-1.5 text-right">1M</th>
                  <th className="px-2 py-1.5 text-right">3M</th>
                  <th className="px-2 py-1.5 text-right">Avg RS</th>
                  <th className="py-1.5 pl-3">Trend</th>
                  <th className="py-1.5">Leaders</th>
                </tr>
              </thead>
              <tbody>
                {o.sectors.map((s) => (
                  <tr key={s.sector} className="border-t border-line">
                    <td className="py-1.5">
                      {s.sector}
                      {s.emerging && <span className="ml-1.5 rounded bg-violet-500/20 px-1.5 py-0.5 text-[10px] font-medium text-violet-300">Emerging</span>}
                    </td>
                    <td className={`tabular px-2 py-1.5 text-right ${tone(s.return_1w)}`}>{pct(s.return_1w, 1)}</td>
                    <td className={`tabular px-2 py-1.5 text-right ${tone(s.return_1m)}`}>{pct(s.return_1m, 1)}</td>
                    <td className={`tabular px-2 py-1.5 text-right ${tone(s.return_3m)}`}>{pct(s.return_3m, 1)}</td>
                    <td className="tabular px-2 py-1.5 text-right">{s.avg_rs ?? "—"}</td>
                    <td className={`py-1.5 pl-3 text-xs ${s.trend === "Improving" ? "text-up" : s.trend === "Weakening" ? "text-down" : "text-muted"}`}>
                      {s.trend === "Improving" ? "▲ " : s.trend === "Weakening" ? "▼ " : ""}
                      {s.trend}
                    </td>
                    <td className="py-1.5 text-xs">
                      {s.leaders.map((l, i) => (
                        <span key={l}>
                          {i > 0 && " · "}
                          <StockLink s={l} />
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] text-muted">Emerging: a sector that climbed into the top ranks over the last month after lagging over 3 months.</p>
        </Panel>

        <Panel title="Market leaders" right={<Link href="/scanner" className="text-xs text-accent hover:underline">Open Move Detector</Link>}>
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>
                <th className="py-1.5">#</th>
                <th className="py-1.5">Symbol</th>
                <th className="py-1.5 text-right">RS</th>
                <th className="py-1.5 text-right">TT</th>
                <th className="py-1.5 pl-3">Bull</th>
                <th className="py-1.5 text-right">Today</th>
              </tr>
            </thead>
            <tbody>
              {o.leaders.map((l, i) => (
                <tr key={l.symbol} className="border-t border-line">
                  <td className="tabular py-1.5 text-muted">{i + 1}</td>
                  <td className="py-1.5">
                    <StockLink s={l.symbol} />
                    {l.vcp && <span className="ml-1.5 rounded bg-up/10 px-1 text-[10px] text-up">VCP</span>}
                  </td>
                  <td className="tabular py-1.5 text-right">{l.rs_rating}</td>
                  <td className={`tabular py-1.5 text-right ${l.template_passed === 8 ? "text-up" : "text-muted"}`}>{l.template_passed}/8</td>
                  <td className="py-1.5 pl-3"><ScoreBar score={l.bull_score} kind="bull" /></td>
                  <td className={`tabular py-1.5 text-right ${tone(l.change_pct)}`}>{pct(l.change_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[11px] text-muted">Ranked by relative strength (50%), Move Detector Bull Score (30%) and Trend Template quality (20%).</p>
        </Panel>
      </div>
    </div>
  );
}
