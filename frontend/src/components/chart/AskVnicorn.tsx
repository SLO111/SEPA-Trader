"use client";

import { useBackClose } from "@/lib/useBackClose";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";

type Plan = {
  side: "long" | "short"; prob: number | null; ev: number | null; entry: number; stop: number; trim: number; target: number; rr: number; pick: boolean;
  source?: "vnicornAI" | "rules";
} | null;
type Analysis = {
  symbol: string; name: string; verdict: string; bias: number; as_of: string;
  sections: { title: string; text: string }[];
  pulse: { conf: number; warn: number; tone: string };
  plans: { long?: Plan; short?: Plan };
  plan_note?: string | null;
};

const VERDICT: Record<string, string> = {
  Constructive: "from-green-500/30 text-green-300", "Leaning positive": "from-green-500/15 text-green-200", Neutral: "from-slate-500/20 text-slate-200",
  "Leaning negative": "from-red-500/15 text-red-200", Weak: "from-red-500/30 text-red-300",
};

function PlanCard({ p, symbol, onTaken }: { p: Plan; symbol: string; onTaken: () => void }) {
  if (!p) return null;
  const long = p.side === "long";
  const take = async () => {
    if (!confirm(`${long ? "Buy" : "Short"} ${symbol} now with ${p.source === "rules" ? "the rule-based" : "vnicornAI's"} plan?\nStop ${p.stop} · trim ${p.trim} · target ${p.target}\n\nFollowed in Backtest → Move Detector trades.`)) return;
    try {
      await post("/api/paper-trades/scan", { symbol, side: p.side });
      onTaken();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  };
  return (
    <div className={`rounded-xl border p-3 ${p.pick ? "border-violet-400/50 bg-violet-500/10" : "border-line bg-panel-2/40"}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className={`text-sm font-semibold ${long ? "text-up" : "text-down"}`}>{long ? "▲ Long plan" : "▼ Short plan"}</span>
        {p.prob === null || p.ev === null ? (
          <span className="rounded bg-panel-2 px-1.5 py-0.5 text-[10px] font-semibold text-muted" title="Stop at 2 ATR (or under the VCP), trim at 1.5R, target at 3R">
            Rules-based · R/R {p.rr}
          </span>
        ) : (
          <span className="tabular text-xs text-muted">
            {Math.round(p.prob * 100)}% · <span className={p.ev > 0 ? "text-up" : "text-down"}>{p.ev > 0 ? "+" : ""}{p.ev}R</span>
            {p.pick && <span className="ml-1.5 rounded bg-gradient-to-r from-violet-500 to-cyan-500 px-1.5 py-0.5 text-[10px] font-bold text-white">PICK</span>}
          </span>
        )}
      </div>
      <div className="tabular grid grid-cols-4 gap-1 text-center text-xs">
        {[["Entry", p.entry, ""], ["Stop", p.stop, "text-down"], ["Trim", p.trim, "text-amber-300"], ["Target", p.target, "text-up"]].map(([k, v, c]) => (
          <div key={k as string} className="rounded bg-bg/60 py-1.5">
            <div className="text-[10px] text-muted">{k}</div>
            <div className={`font-medium ${c}`}>{(v as number).toFixed(2)}</div>
          </div>
        ))}
      </div>
      <button onClick={take} className={`mt-2 w-full rounded-md py-1.5 text-sm font-semibold text-white ${long ? "bg-up hover:bg-green-500" : "bg-down hover:bg-red-500"}`}>
        {long ? "Buy" : "Short"} with this plan
      </button>
    </div>
  );
}

/** "Ask vnicornAI": a plain-English read of the chart with vnicornAI's long and short plans. */
export default function AskVnicorn({ symbol, onClose, locked = false }: { symbol: string; onClose: () => void; locked?: boolean }) {
  useBackClose(true, onClose);
  const [a, setA] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [taken, setTaken] = useState(false);
  useEffect(() => {
    if (!locked) api<Analysis>(`/api/market/analysis/${encodeURIComponent(symbol)}`).then(setA).catch((e) => setError(e.message));
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [symbol, onClose, locked]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50" onMouseDown={onClose}>
      <aside className="flex h-full w-full max-w-md flex-col border-l border-violet-500/30 bg-panel shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-line bg-gradient-to-r from-violet-600/20 to-cyan-500/10 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="rounded bg-gradient-to-r from-violet-500 to-cyan-500 px-1.5 py-0.5 text-[11px] font-bold text-white">vnicornAI</span>
            <span className="font-semibold">{symbol}</span>
            {a && <span className="text-xs text-muted">as of {a.as_of}</span>}
            {a && typeof (a as { quota_left?: number | null }).quota_left === "number" && (
              <span className="rounded bg-panel-2 px-1.5 py-0.5 text-[10px] text-muted" title="Questions left this month on your plan">
                {(a as { quota_left?: number | null }).quota_left} left this month
              </span>
            )}
          </div>
          <button onClick={onClose} className="rounded px-2 py-1 text-muted hover:bg-panel-2" aria-label="Close">✕</button>
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          {locked && (
            <div className="space-y-4">
              <div className="space-y-2 opacity-60 blur-[2px]" aria-hidden>
                {["Trend & cycle", "Structure", "Setup", "Behaviour & volume", "vnicornAI plans"].map((t) => (
                  <div key={t}>
                    <div className="text-sm font-semibold text-violet-200">{t}</div>
                    <div className="mt-1 h-10 rounded bg-panel-2/70" />
                  </div>
                ))}
              </div>
              <div className="rounded-xl border border-violet-500/40 bg-violet-500/10 p-4">
                <p className="font-semibold">Ask vnicornAI is part of Pro</p>
                <p className="mt-1 text-sm text-muted">
                  A plain-English read of any chart in seconds: trend and cycle, structure, setup, volume behaviour, key levels and risk, plus vnicornAI&apos;s best
                  long and short plans with their odds, ready to take with one click.
                </p>
                <Link href="/billing" className="mt-3 inline-block rounded-md bg-gradient-to-r from-violet-500 to-cyan-500 px-4 py-2 text-sm font-semibold text-white">
                  Unlock with Pro
                </Link>
              </div>
            </div>
          )}
          {error && <p className="text-sm text-down">{error}</p>}
          {!locked && !a && !error && (
            <div className="space-y-3">
              {[0, 1, 2, 3].map((i) => <div key={i} className="h-16 animate-pulse rounded-lg bg-panel-2/50" />)}
            </div>
          )}
          {a && (
            <>
              <div className={`rounded-xl bg-gradient-to-r to-transparent p-4 ${VERDICT[a.verdict] ?? VERDICT.Neutral}`}>
                <div className="text-[11px] uppercase tracking-wide text-muted">Overall read</div>
                <div className="text-2xl font-semibold">{a.verdict}</div>
                <div className="text-xs text-muted">{a.name} · Pulse 10d: {a.pulse.conf} confirmations / {a.pulse.warn} warnings</div>
              </div>
              {a.sections.filter((s) => s.title !== "vnicornAI plan").map((s) => (
                <section key={s.title}>
                  <h3 className="mb-1 text-sm font-semibold text-violet-200">{s.title}</h3>
                  <p className="text-sm leading-relaxed text-slate-300">{s.text}</p>
                </section>
              ))}
              {(a.plans.long || a.plans.short) ? (
                <section className="space-y-2">
                  <h3 className="text-sm font-semibold text-violet-200">{a.plan_note ? "Plans" : "vnicornAI plans"}</h3>
                  {a.plan_note && <p className="rounded-lg border border-line bg-panel-2/50 px-3 py-2 text-xs text-muted">{a.plan_note}</p>}
                  {taken && (
                    <p className="rounded bg-up/10 px-3 py-2 text-xs text-up">
                      Added. Follow it in <Link href="/backtest?tab=md" className="underline">Backtest → Move Detector trades</Link>.
                    </p>
                  )}
                  <PlanCard p={a.plans.long ?? null} symbol={symbol} onTaken={() => setTaken(true)} />
                  <PlanCard p={a.plans.short ?? null} symbol={symbol} onTaken={() => setTaken(true)} />
                  {!a.plan_note && (
                    <p className="text-[11px] text-muted">Probability = estimated chance to reach the target before the stop; EV = expected result per trade in R (multiples of the risk).</p>
                  )}
                </section>
              ) : (
                <p className="text-xs text-muted">Not enough price history yet for a plan on {symbol}.</p>
              )}
              <p className="text-[11px] text-muted">Written automatically from the chart and the platform&apos;s analysis. For educational purposes only. Not financial advice.</p>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
