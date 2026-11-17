"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";

type Sent = { votes: number; bullish_pct: number | null; bearish_pct: number | null; mine: "bull" | "bear" | null };
type SC = {
  symbol: string;
  price: number | null;
  health: { score: number | null; label: string | null; categories?: { name: string; score: number | null }[]; categories_locked?: boolean };
  fair_value: { fair?: number | null; upside_pct?: number | null; label: string | null; models?: { name: string; value: number }[]; locked?: boolean };
  sentiment: Sent;
};

const HEALTH_COLOR: Record<string, string> = { Weak: "text-down", Fair: "text-amber-300", Good: "text-lime-300", Great: "text-up", Excellent: "text-up" };
const FV_COLOR: Record<string, string> = { Undervalued: "text-up", Overvalued: "text-down", "Fairly valued": "text-amber-300" };

function Segments({ score }: { score: number | null }) {
  const pos = score ? ((score - 1) / 4) * 100 : null;
  return (
    <div className="relative mt-2">
      <div className="flex gap-0.5">
        {["bg-down", "bg-orange-400", "bg-amber-300", "bg-lime-400", "bg-up"].map((c) => (
          <div key={c} className={`h-1.5 flex-1 rounded-sm ${c}`} />
        ))}
      </div>
      {pos !== null && <div className="absolute -top-1 h-3.5 w-1 -translate-x-1/2 rounded bg-text" style={{ left: `${pos}%` }} />}
    </div>
  );
}

/** Scorecard: Company's health, Fair value and Members' sentiment. */
export default function Scorecard({ symbol, compact = false }: { symbol: string; compact?: boolean }) {
  const [d, setD] = useState<SC | null>(null);
  useEffect(() => {
    setD(null);
    api<SC>(`/api/stock/${encodeURIComponent(symbol)}/scorecard`).then(setD).catch(() => {});
  }, [symbol]);
  if (!d) return <div className="text-xs text-muted">Loading scorecard…</div>;
  const vote = async (v: "bull" | "bear") => {
    const s = await post<Sent>(`/api/stock/${encodeURIComponent(symbol)}/sentiment`, { vote: v });
    setD({ ...d, sentiment: s });
  };
  const h = d.health;
  const fv = d.fair_value;
  const s = d.sentiment;
  return (
    <div className={`space-y-4 ${compact ? "text-xs" : "text-sm"}`}>
      <div>
        <div className="flex items-baseline justify-between">
          <span className="font-semibold">Company&apos;s health</span>
          <span className={`font-semibold ${HEALTH_COLOR[h.label ?? ""] ?? "text-muted"}`}>
            {h.label ?? "—"}
            {h.score ? ` · ${h.score.toFixed(1)}/5` : ""}
          </span>
        </div>
        <Segments score={h.score} />
        {!compact && h.categories && (
          <ul className="mt-2 space-y-1">
            {h.categories.map((c) => (
              <li key={c.name} className="flex items-center gap-2 text-xs">
                <span className="w-32 shrink-0 text-muted">{c.name}</span>
                <div className="h-1.5 flex-1 rounded bg-panel-2">
                  {c.score !== null && (
                    <div className={`h-full rounded ${c.score >= 3.5 ? "bg-up" : c.score >= 2.5 ? "bg-amber-300" : "bg-down"}`} style={{ width: `${((c.score - 1) / 4) * 100}%` }} />
                  )}
                </div>
                <span className="tabular w-8 text-right">{c.score?.toFixed(1) ?? "—"}</span>
              </li>
            ))}
          </ul>
        )}
        {!compact && h.categories_locked && (
          <p className="mt-1.5 text-[11px] text-amber-300">
            🔒 Profitability, growth, cash flow, strength and momentum scores: <Link href="/billing" className="underline">Pro</Link>
          </p>
        )}
      </div>

      <div className="border-t border-line pt-3">
        <div className="flex items-baseline justify-between">
          <span className="font-semibold">Fair value</span>
          <span className={`font-semibold ${FV_COLOR[fv.label ?? ""] ?? "text-muted"}`}>{fv.label ?? "—"}</span>
        </div>
        {fv.locked ? (
          <p className="mt-1 text-[11px] text-amber-300">
            🔒 Fair price and upside from 4 valuation models: <Link href="/billing" className="underline">Pro</Link>
          </p>
        ) : fv.fair ? (
          <>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-muted">Fair price</span>
              <span className="tabular font-semibold">${fv.fair.toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-muted">{(fv.upside_pct ?? 0) >= 0 ? "Upside" : "Downside"}</span>
              <span className={`tabular font-semibold ${(fv.upside_pct ?? 0) >= 0 ? "text-up" : "text-down"}`}>
                {(fv.upside_pct ?? 0) > 0 ? "+" : ""}
                {fv.upside_pct}%
              </span>
            </div>
            {!compact && fv.models && (
              <p className="mt-1 text-[11px] text-muted">
                Median of: {fv.models.map((m) => `${m.name} $${Math.round(m.value).toLocaleString("en-US")}`).join(" · ")}
              </p>
            )}
          </>
        ) : (
          <p className="mt-1 text-xs text-muted">Not enough data for a fair value.</p>
        )}
      </div>

      <div className="border-t border-line pt-3">
        <div className="flex items-baseline justify-between">
          <span className="font-semibold">Members&apos; sentiment</span>
          <span className="text-[11px] text-muted">
            {s.votes} vote{s.votes === 1 ? "" : "s"} · 30 days
          </span>
        </div>
        {s.votes > 0 && (
          <>
            <div className="mt-2 flex h-2 overflow-hidden rounded">
              <div className="bg-up" style={{ width: `${s.bullish_pct}%` }} />
              <div className="bg-down" style={{ width: `${s.bearish_pct}%` }} />
            </div>
            <div className="mt-1 flex justify-between text-[11px]">
              <span className="text-up">{s.bullish_pct}% bullish</span>
              <span className="text-down">{s.bearish_pct}% bearish</span>
            </div>
          </>
        )}
        <div className="mt-2 grid grid-cols-2 gap-2">
          <button
            onClick={() => vote("bear")}
            className={`rounded-md border px-2 py-1.5 font-medium ${s.mine === "bear" ? "border-down bg-down/15 text-down" : "border-line hover:border-down/60"}`}
          >
            Bearish
          </button>
          <button
            onClick={() => vote("bull")}
            className={`rounded-md border px-2 py-1.5 font-medium ${s.mine === "bull" ? "border-up bg-up/15 text-up" : "border-line hover:border-up/60"}`}
          >
            Bullish
          </button>
        </div>
      </div>
    </div>
  );
}
