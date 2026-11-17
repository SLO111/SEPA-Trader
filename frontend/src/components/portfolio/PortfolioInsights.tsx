"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AddToWatchlist from "@/components/AddToWatchlist";
import { api } from "@/lib/api";

type Check = { level: "high" | "medium" | "low"; symbol: string | null; title: string; detail: string; action: "stop" | "target" | "sell" | null };
type Sugg = { symbol: string; name: string; sector: string; reason: string; source: string };
type Resp = { checks: Check[]; suggestions: Sugg[] | { locked: true }; profile?: { key: string | null; label: string } };

const DOT: Record<string, string> = { high: "bg-down", medium: "bg-amber-400", low: "bg-sky-400" };

/** vnicornAI insights: what to fix in the portfolio, and stocks worth a look (Pro). */
export default function PortfolioInsights({ portfolioId, version, onAction }: { portfolioId: number; version: number; onAction: (a: "stop" | "target", symbol: string) => void }) {
  const [d, setD] = useState<Resp | null>(null);
  const [all, setAll] = useState(false);
  useEffect(() => {
    setD(null);
    api<Resp>(`/api/portfolios/${portfolioId}/insights`).then(setD).catch(() => setD({ checks: [], suggestions: [] }));
  }, [portfolioId, version]);
  if (!d) return <section className="rounded-xl border border-violet-500/30 bg-panel p-4 text-sm text-muted">✦ vnicornAI is reviewing your portfolio…</section>;
  const checks = all ? d.checks : d.checks.slice(0, 5);
  const locked = !Array.isArray(d.suggestions);
  return (
    <section className="rounded-xl border border-violet-500/30 bg-gradient-to-br from-violet-500/10 to-panel p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="rounded bg-gradient-to-r from-violet-500 to-cyan-500 px-1.5 py-0.5 text-[11px] font-bold text-white">vnicornAI</span>
        <h2 className="font-semibold">Portfolio insights</h2>
        <span className="ml-auto text-xs text-muted">{d.checks.length ? `${d.checks.length} thing${d.checks.length === 1 ? "" : "s"} to review` : "All good"}</span>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div>
          {d.checks.length === 0 ? (
            <p className="text-sm text-up">✓ Every position has a stop and a plan, and nothing needs attention right now.</p>
          ) : (
            <ul className="space-y-2">
              {checks.map((c, i) => (
                <li key={i} className="flex gap-2.5 rounded-lg bg-panel/70 p-2.5 text-sm">
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${DOT[c.level]}`} />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{c.title}</div>
                    <div className="text-xs text-muted">{c.detail}</div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    {c.symbol && (c.action === "stop" || c.action === "target") && (
                      <button onClick={() => onAction(c.action as "stop" | "target", c.symbol!)} className="rounded-md bg-violet-500/20 px-2 py-0.5 text-xs text-violet-100 hover:bg-violet-500/30">
                        {c.action === "stop" ? "Set stop" : "Set target"}
                      </button>
                    )}
                    {c.symbol && <Link href={`/chart?s=${c.symbol}`} className="text-[11px] text-accent hover:underline">Chart</Link>}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {d.checks.length > 5 && (
            <button onClick={() => setAll((x) => !x)} className="mt-2 text-xs text-accent hover:underline">{all ? "Show less" : `Show all ${d.checks.length}`}</button>
          )}
        </div>
        <div>
          <div className="mb-1.5 text-[11px] uppercase tracking-wide text-muted">
            Stocks to consider{d.profile?.label ? <> · <span className="normal-case text-violet-200">fit your {d.profile.label} profile</span></> : null}
          </div>
          {locked ? (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-muted">
              🔒 vnicornAI suggests leaders that fit your portfolio (Trend Template 8/8, strong RS, sectors you own little of) and open trade ideas.
              <Link href="/billing" className="mt-1 block font-semibold text-amber-300 hover:underline">Unlock with Pro</Link>
            </div>
          ) : (d.suggestions as Sugg[]).length === 0 ? (
            <p className="text-xs text-muted">No stocks that fit your {d.profile?.label ?? "portfolio's"} profile are acting well enough right now.</p>
          ) : (
            <ul className="space-y-1.5">
              {(d.suggestions as Sugg[]).map((s) => (
                <li key={s.symbol} className="rounded-lg bg-panel/70 p-2 text-sm">
                  <div className="flex items-center gap-1.5">
                    <AddToWatchlist symbol={s.symbol} />
                    <Link href={`/chart?s=${s.symbol}`} className="font-semibold hover:text-accent">{s.symbol}</Link>
                    <span className="truncate text-xs text-muted">{s.name}</span>
                    <span className="ml-auto rounded bg-panel-2 px-1.5 py-0.5 text-[10px] text-muted">{s.source}</span>
                  </div>
                  <div className="mt-0.5 text-xs text-muted">{s.reason}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
