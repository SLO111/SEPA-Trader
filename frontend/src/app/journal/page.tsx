"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/AppShell";
import ReviewPanel from "@/components/journal/ReviewPanel";
import TradeForm from "@/components/journal/TradeForm";
import type { JStats, JTrade } from "@/components/journal/types";
import { api, del } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmt, pct, signedUsd, tone, usd } from "@/lib/format";

const LineChart = dynamic(() => import("@/components/markets/LineChart"), { ssr: false });

function Stat({ label, value, sub, cls = "", hint }: { label: string; value: string; sub?: string; cls?: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-line bg-panel p-3" title={hint}>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className={`tabular text-xl font-semibold ${cls}`}>{value}</div>
      {sub && <div className="tabular text-xs text-muted">{sub}</div>}
    </div>
  );
}

function Bars({ data, label }: { data: { key: string; value: number }[]; label: (v: number) => string }) {
  const max = Math.max(...data.map((d) => Math.abs(d.value)), 1);
  return (
    <div className="flex h-40 items-stretch gap-1">
      {data.map((d) => (
        <div key={d.key} className="flex flex-1 flex-col items-center" title={`${d.key}: ${label(d.value)}`}>
          <div className="flex w-full flex-1 flex-col justify-end">
            <div className="flex h-1/2 w-full items-end">{d.value > 0 && <div className="w-full rounded-t bg-up/70" style={{ height: `${(d.value / max) * 100}%` }} />}</div>
            <div className="flex h-1/2 w-full items-start border-t border-line">{d.value < 0 && <div className="w-full rounded-b bg-down/70" style={{ height: `${(-d.value / max) * 100}%` }} />}</div>
          </div>
          <span className="mt-1 text-[10px] text-muted">{d.key}</span>
        </div>
      ))}
    </div>
  );
}

function Analytics({ s }: { s: JStats }) {
  const equity = useMemo(() => (s.equity_curve?.length ? [{ name: "Cumulative P/L", color: "#3b82f6", data: s.equity_curve }] : []), [s]);
  if (!s.closed_trades) return <p className="text-sm text-muted">Close a few trades to see your analytics.</p>;
  const rBuckets = [-3, -2, -1, 0, 1, 2, 3, 4].map((lo) => ({
    key: lo === -3 ? "≤−2R" : lo === 4 ? "≥4R" : `${lo}R`,
    value: (s.r_distribution ?? []).filter((r) => (lo === -3 ? r < -2 : lo === 4 ? r >= 4 : r >= lo && r < lo + 1)).length,
  }));
  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-2">
        <section className="rounded-xl border border-line bg-panel p-4">
          <h2 className="mb-2 font-semibold">Equity curve</h2>
          <LineChart series={equity} height={240} />
        </section>
        <section className="rounded-xl border border-line bg-panel p-4">
          <h2 className="mb-2 font-semibold">Monthly P/L</h2>
          <Bars data={(s.monthly ?? []).slice(-12).map((m) => ({ key: m.month.slice(2), value: m.pnl }))} label={(v) => signedUsd(v)} />
        </section>
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <section className="rounded-xl border border-line bg-panel p-4">
          <h2 className="mb-2 font-semibold">R-multiple distribution</h2>
          <div className="flex h-40 items-end gap-1">
            {rBuckets.map((b, i) => {
              const max = Math.max(...rBuckets.map((x) => x.value), 1);
              return (
                <div key={b.key} className="flex flex-1 flex-col items-center gap-1">
                  <span className="tabular text-[10px] text-muted">{b.value || ""}</span>
                  <div className={`w-full rounded-t ${i < 3 ? "bg-down/70" : "bg-up/70"}`} style={{ height: `${(b.value / max) * 100}%`, minHeight: b.value ? 2 : 0 }} />
                  <span className="text-[10px] text-muted">{b.key}</span>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-muted">Healthy systems cut losses near −1R and let a few winners run to 3R+.</p>
        </section>
        <section className="rounded-xl border border-line bg-panel p-4">
          <h2 className="mb-2 font-semibold">Consistency & efficiency</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {[
              ["Largest win", usd(s.largest_win ?? 0)], ["Largest loss", usd(s.largest_loss ?? 0)],
              ["Avg. hold (winners)", `${fmt(s.avg_hold_win, 1)} days`], ["Avg. hold (losers)", `${fmt(s.avg_hold_loss, 1)} days`],
              ["Longest win streak", String(s.max_win_streak)], ["Longest loss streak", String(s.max_loss_streak)],
              ["R std. deviation", fmt(s.r_std)], ["Profitable months", fmt(s.profitable_months_pct, 0, "%")],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-line/60 pb-1.5">
                <dt className="text-muted">{k}</dt>
                <dd className="tabular font-medium">{v}</dd>
              </div>
            ))}
          </dl>
          {(s.avg_hold_loss ?? 0) > (s.avg_hold_win ?? 0) && (
            <p className="mt-3 text-xs text-amber-300">You hold losers longer than winners. Most successful traders do the opposite.</p>
          )}
        </section>
      </div>
      {s.by_setup && s.by_setup.length > 0 && (
        <section className="rounded-xl border border-line bg-panel p-4">
          <h2 className="mb-2 font-semibold">Performance by setup</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
              <tr><th className="py-1.5">Setup</th><th className="py-1.5 text-right">Trades</th><th className="py-1.5 text-right">Win rate</th><th className="py-1.5 text-right">Avg R</th><th className="py-1.5 text-right">P/L</th></tr>
            </thead>
            <tbody>
              {s.by_setup.map((b) => (
                <tr key={b.setup} className="border-t border-line">
                  <td className="py-1.5">{b.setup}</td>
                  <td className="tabular py-1.5 text-right">{b.trades}</td>
                  <td className="tabular py-1.5 text-right">{b.win_rate}%</td>
                  <td className={`tabular py-1.5 text-right ${tone(b.avg_r)}`}>{fmt(b.avg_r)}</td>
                  <td className={`tabular py-1.5 text-right ${tone(b.pnl)}`}>{signedUsd(b.pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

function Journal() {
  const { user } = useAuth();
  const [tab, setTab] = useState<"trades" | "analytics">("trades");
  const [trades, setTrades] = useState<JTrade[] | null>(null);
  const [stats, setStats] = useState<JStats | null>(null);
  const [setups, setSetups] = useState<string[]>([]);
  const [form, setForm] = useState<JTrade | "new" | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [filter, setFilter] = useState<"all" | "open" | "closed">("all");
  const canReview = !!user?.limits.trade_review;

  const load = useCallback(() => {
    api<JTrade[]>("/api/journal/trades").then(setTrades).catch(() => setTrades([]));
    api<JStats>("/api/journal/stats").then(setStats).catch(() => {});
  }, []);
  useEffect(() => {
    load();
    api<string[]>("/api/journal/setups").then(setSetups).catch(() => {});
  }, [load]);

  const remove = async (t: JTrade) => {
    if (!confirm(`Delete the ${t.symbol} trade from ${t.entry_date}?`)) return;
    await del(`/api/journal/trades/${t.id}`);
    load();
  };

  const s = stats;
  const rows = (trades ?? []).filter((t) => filter === "all" || t.status === filter);
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div>
            <h1 className="text-xl font-semibold">Trading journal</h1>
            <p className="text-sm text-muted">Measure what matters: expectancy, win/loss efficiency and consistency, from your own trades.</p>
          </div>
          {form === null && (
            <button onClick={() => setForm("new")} className="ml-auto rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-500">+ Log trade</button>
          )}
        </div>

        {s && s.closed_trades > 0 && (
          <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Stat label="Total P/L" value={signedUsd(s.total_pnl ?? 0)} cls={tone(s.total_pnl)} sub={`${s.closed_trades} closed · ${s.open_trades} open`} />
            <Stat label="Win rate" value={`${s.win_rate}%`} sub={`${s.wins}W / ${s.losses}L`} />
            <Stat label="Expectancy" value={s.expectancy_r !== null && s.expectancy_r !== undefined ? `${s.expectancy_r > 0 ? "+" : ""}${s.expectancy_r}R` : pct(s.expectancy_pct)} cls={tone(s.expectancy_pct)} sub={`${pct(s.expectancy_pct)} · ${signedUsd(s.expectancy_usd ?? 0)} per trade`} hint="Average result per trade" />
            <Stat label="Avg win / avg loss" value={`${pct(s.avg_win_pct, 1)} / ${pct(s.avg_loss_pct, 1)}`} sub={`Ratio ${fmt(s.win_loss_ratio)}`} />
            <Stat label="Profit factor" value={fmt(s.profit_factor)} cls={(s.profit_factor ?? 0) >= 1.5 ? "text-up" : (s.profit_factor ?? 0) < 1 ? "text-down" : ""} sub="Gross profit ÷ gross loss" />
            <Stat label="Max drawdown" value={usd(s.max_drawdown ?? 0)} cls="text-down" sub="Peak-to-trough on closed P/L" />
          </div>
        )}

        {form !== null && (
          <div className="mb-5">
            <TradeForm
              key={form === "new" ? "new" : form.id}
              setups={setups}
              initial={form === "new" ? undefined : form}
              onCancel={() => setForm(null)}
              onSaved={() => {
                setForm(null);
                load();
              }}
            />
          </div>
        )}

        <nav className="mb-4 flex gap-1 border-b border-line">
          {(["trades", "analytics"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`border-b-2 px-3 py-2 text-sm capitalize ${tab === t ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}>
              {t}
            </button>
          ))}
        </nav>

        {tab === "analytics" ? (
          s ? <Analytics s={s} /> : <p className="text-sm text-muted">Loading…</p>
        ) : (
          <>
            <div className="mb-3 flex gap-1">
              {(["all", "open", "closed"] as const).map((f) => (
                <button key={f} onClick={() => setFilter(f)} className={`rounded px-3 py-1 text-sm capitalize ${filter === f ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}>{f}</button>
              ))}
            </div>
            <div className="overflow-x-auto rounded-xl border border-line">
              <table className="w-full min-w-[980px] text-sm">
                <thead className="bg-panel text-left text-[11px] uppercase tracking-wide text-muted">
                  <tr>
                    <th className="px-3 py-2.5">Entry</th>
                    <th className="px-3 py-2.5">Symbol</th>
                    <th className="px-3 py-2.5">Setup</th>
                    <th className="px-3 py-2.5 text-right">Entry $</th>
                    <th className="px-3 py-2.5 text-right">Stop</th>
                    <th className="px-3 py-2.5 text-right">Exit / last</th>
                    <th className="px-3 py-2.5 text-right">R</th>
                    <th className="px-3 py-2.5 text-right">P/L</th>
                    <th className="px-3 py-2.5 text-right">Days</th>
                    <th className="px-3 py-2.5" />
                  </tr>
                </thead>
                <tbody>
                  {trades === null && <tr><td colSpan={10} className="px-3 py-8 text-center text-muted">Loading…</td></tr>}
                  {trades?.length === 0 && <tr><td colSpan={10} className="px-3 py-8 text-center text-muted">No trades yet. Log your first trade to start measuring your edge.</td></tr>}
                  {rows.map((t) => (
                    <Fragment key={t.id}>
                      <tr className="border-t border-line">
                        <td className="tabular px-3 py-2 text-muted">{t.entry_date}</td>
                        <td className="px-3 py-2">
                          <Link href={`/stock?s=${encodeURIComponent(t.symbol)}`} className="font-medium hover:text-accent">{t.symbol}</Link>
                          <span className={`ml-2 rounded px-1.5 py-0.5 text-[10px] ${t.side === "long" ? "bg-up/10 text-up" : "bg-down/10 text-down"}`}>{t.side}</span>
                          {t.status === "open" && <span className="ml-1 rounded bg-accent/15 px-1.5 py-0.5 text-[10px] text-blue-300">open</span>}
                        </td>
                        <td className="px-3 py-2 text-muted">{t.setup || "—"}</td>
                        <td className="tabular px-3 py-2 text-right">{fmt(t.entry_price)}</td>
                        <td className="tabular px-3 py-2 text-right text-muted">{t.stop_price ? `${fmt(t.stop_price)} (${t.risk_pct}%)` : "—"}</td>
                        <td className="tabular px-3 py-2 text-right">{fmt(t.exit_price ?? t.last_price)}</td>
                        <td className={`tabular px-3 py-2 text-right font-medium ${tone(t.r_multiple)}`}>{t.r_multiple !== null ? `${t.r_multiple > 0 ? "+" : ""}${t.r_multiple}R` : "—"}</td>
                        <td className={`tabular px-3 py-2 text-right ${tone(t.pnl)}`}>
                          {t.pnl !== null ? signedUsd(t.pnl) : "—"}
                          <div className="text-xs">{pct(t.return_pct)}</div>
                        </td>
                        <td className="tabular px-3 py-2 text-right text-muted">{t.hold_days ?? "—"}</td>
                        <td className="whitespace-nowrap px-3 py-2 text-right text-xs">
                          {t.status === "closed" && (
                            <button
                              onClick={() => setOpen(open === t.id ? null : t.id)}
                              disabled={!canReview}
                              title={canReview ? "Grade this trade" : "Trade Review is available on the Premium plan"}
                              className="mr-2 rounded bg-panel-2 px-2 py-1 text-text hover:bg-line disabled:opacity-50"
                            >
                              {open === t.id ? "Hide review" : "Review"}
                              {!canReview && <span className="ml-1 text-[9px] text-amber-300">PREMIUM</span>}
                            </button>
                          )}
                          <button onClick={() => setForm(t)} className="mr-2 text-muted hover:text-text">{t.status === "open" ? "Close / edit" : "Edit"}</button>
                          <button onClick={() => remove(t)} className="text-muted hover:text-down">Delete</button>
                        </td>
                      </tr>
                      {open === t.id && (
                        <tr className="bg-panel/60">
                          <td colSpan={10} className="px-4 py-4">
                            <ReviewPanel tradeId={t.id} />
                            {t.notes && <p className="mt-3 border-t border-line pt-3 text-sm text-muted"><b className="text-text">Your notes:</b> {t.notes}</p>}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        <p className="mt-6 text-xs text-muted">For educational purposes only. Not financial advice.</p>
      </div>
    </div>
  );
}

export default function JournalPage() {
  return (
    <AppShell>
      <Journal />
    </AppShell>
  );
}
