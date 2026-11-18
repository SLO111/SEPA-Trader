"use client";

import ExportButton from "@/components/ExportButton";
import { LoadMoreRow, ShowingCount, useShowMore } from "@/lib/useInfinite";
import { SortTh, useSort } from "@/lib/useSort";

import dynamic from "next/dynamic";
import Link from "next/link";
import { Fragment, useEffect, useState } from "react";
import { api } from "@/lib/api";
import TradeJournal from "./TradeJournal";
import { fmt, pct, tone } from "@/lib/format";
import type { Candle, StrategyOutput } from "@/lib/types";

const PriceChart = dynamic(() => import("@/components/PriceChart"), { ssr: false });

type Cls = "Perfect" | "Early" | "Late" | "Fair";
type Graded = {
  statement?: boolean;
  ref: string; source: string; symbol: string; side: "long" | "short"; entry_date: string; entry_price: number; exit_date: string | null; exit_price: number | null;
  stop?: number; entry_class?: Cls | null; exit_class?: Cls | null; grade?: string | null; score?: number | null; pnl_pct?: number; r_multiple?: number | null;
  mfe_pct?: number; mae_pct?: number; left_on_table_pct?: number; days?: number; open?: boolean; notes: string[];
};
type Dist = { label: Cls; count: number; pct: number }[];
type Resp = { trades: Graded[]; summary: { trades: number; closed: number; bought: Dist; sold: Dist; avg_score: number | null; avg_grade: string | null; top_mistake: string | null; grades: Record<string, number>; total?: number; total_open?: number; total_closed?: number } };

const CLS: Record<Cls, string> = { Perfect: "bg-up/20 text-up", Early: "bg-amber-500/20 text-amber-300", Late: "bg-down/20 text-down", Fair: "bg-slate-500/25 text-slate-200" };
const BAR: Record<Cls, string> = { Perfect: "bg-up", Early: "bg-amber-400", Late: "bg-down", Fair: "bg-slate-400" };
const GRADE: Record<string, string> = { A: "bg-up text-white", B: "bg-up/60 text-white", C: "bg-amber-500 text-black", D: "bg-orange-600 text-white", F: "bg-down text-white" };

function DistCard({ title, rows, verb }: { title: string; rows: Dist; verb: string }) {
  return (
    <div className="rounded-xl border border-line bg-panel p-4">
      <div className="mb-2 text-sm font-semibold">{title}</div>
      <div className="space-y-2">
        {rows.filter((r) => r.label !== "Fair" || r.count).map((r) => (
          <div key={r.label} className="grid grid-cols-[110px_24px_1fr_40px] items-center gap-2 text-sm">
            <span className="text-muted">{verb} {r.label}</span>
            <span className="tabular text-right text-muted">{r.count}</span>
            <span className="h-1.5 overflow-hidden rounded-full bg-line"><span className={`block h-full ${BAR[r.label]}`} style={{ width: `${r.pct}%` }} /></span>
            <span className="tabular text-right">{r.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TradeChart({ t }: { t: Graded }) {
  const [candles, setCandles] = useState<Candle[] | null>(null);
  useEffect(() => {
    api<Candle[]>(`/api/grader/chart?symbol=${t.symbol}&start=${t.entry_date}${t.exit_date ? `&end=${t.exit_date}` : ""}`).then(setCandles).catch(() => setCandles([]));
  }, [t]);
  if (!candles) return <div className="h-72 animate-pulse rounded-lg bg-panel-2/40" />;
  const long = t.side === "long";
  const near = (d: string) => candles.find((c) => String(c.time) >= d)?.time ?? d;
  const overlay: StrategyOutput = {
    lines: [], histograms: [],
    markers: [
      { time: near(t.entry_date), position: long ? "belowBar" : "aboveBar", shape: long ? "arrowUp" : "arrowDown", color: "#3b82f6", text: `${long ? "Buy" : "Short"} ${t.entry_price}` },
      ...(t.exit_date ? [{ time: near(t.exit_date), position: (long ? "aboveBar" : "belowBar") as "aboveBar" | "belowBar", shape: (long ? "arrowDown" : "arrowUp") as "arrowDown" | "arrowUp", color: "#f59e0b", text: `${long ? "Sell" : "Cover"} ${t.exit_price}` }] : []),
    ],
    levels: [{ price: t.entry_price, color: "#3b82f6", title: "Entry" }, ...(t.stop ? [{ price: t.stop, color: "#ef4444", title: "Stop" }] : [])],
  };
  return (
    <div className="h-72 overflow-hidden rounded-lg border border-line">
      <PriceChart candles={candles} overlays={[overlay]} fitKey={t.ref} />
    </div>
  );
}

function GradeTable({ rows, open, setOpen, noted, onNote, stickyTop }: {
  rows: Graded[]; open: string | null; setOpen: (v: string | null) => void; noted?: Set<string>; onNote?: () => void; stickyTop: string;
}) {
  // default: newest trades first; Grade, Ticker, Entry, Exit, Result and Left on table sort on click
  const GRADE: Record<string, number> = { "A+": 6, A: 5, B: 4, C: 3, D: 2, F: 1 };
  const srt = useSort(rows, {
    grade: (t: Graded) => (t.grade ? GRADE[t.grade] ?? 0 : null), ticker: (t: Graded) => t.symbol,
    entry: (t: Graded) => t.entry_date, exit: (t: Graded) => t.exit_date ?? "9999", result: (t: Graded) => t.r_multiple ?? t.pnl_pct ?? null,
    left: (t: Graded) => t.left_on_table_pct ?? null, recent: (t: Graded) => t.exit_date ?? t.entry_date,
  }, "recent");
  const page = useShowMore(srt.sorted, `${rows.length}|${srt.resetKey}`); // 50 trades at a time
  return (
          <div className="overflow-x-auto rounded-xl border border-line lg:overflow-visible">
            <table className="w-full min-w-[820px] text-sm">
              <thead className={`sticky z-[5] bg-panel text-left text-[11px] uppercase tracking-wide text-muted shadow-[0_1px_0_var(--color-line)] ${stickyTop}`}>
                <tr>
                  {["Grade", "Ticker", "Source", "Entry", "Exit", "Result", "Buy timing", "Sell timing", "Left on table"].map((h) => {
                    const k = ({ Grade: "grade", Ticker: "ticker", Entry: "entry", Exit: "exit", Result: "result", "Left on table": "left" } as Record<string, "grade" | "ticker" | "entry" | "exit" | "result" | "left">)[h];
                    const right = ["Result", "Left on table"].includes(h);
                    return k ? (
                      <SortTh key={h} k={k} label={h} sort={srt.sort} onClick={srt.click} right={right} text={k === "ticker"} className="px-3 py-2.5" />
                    ) : (
                      <th key={h} className="px-3 py-2.5">{h}</th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {page.visible.map((t) => (
                  <Fragment key={t.ref}>
                    <tr onClick={() => setOpen(open === t.ref ? null : t.ref)} className="cursor-pointer border-t border-line hover:bg-panel-2/40">
                      <td className="px-3 py-2">
                        <span className={`inline-grid h-7 w-7 place-items-center rounded-md text-sm font-bold ${t.grade ? GRADE[t.grade] : "bg-panel-2 text-muted"}`}>{t.grade ?? "·"}</span>
                      </td>
                      <td className="px-3 py-2 font-semibold">
                        <span className={t.side === "short" ? "text-down" : "text-up"}>{t.side === "short" ? "▼" : "▲"}</span> {t.symbol}
                        {noted?.has(t.ref) && <span className="ml-1 text-xs" title="Has a journal note">📝</span>}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted">
                        {t.source}
                        {t.statement ? (
                          <div className="max-w-[220px] text-[10px] text-muted">Imported from a statement · buy date unknown</div>
                        ) : !t.grade && !t.entry_class && t.notes?.[0] && <div className="max-w-[220px] text-[10px] text-amber-300">{t.notes[0]}</div>}
                      </td>
                      <td className="tabular whitespace-nowrap px-3 py-2 text-xs">{t.entry_date}<div className="text-muted">${fmt(t.entry_price)}</div></td>
                      <td className="tabular whitespace-nowrap px-3 py-2 text-xs">{t.exit_date ?? "open"}<div className="text-muted">{t.exit_price ? `$${fmt(t.exit_price)}` : ""}</div></td>
                      <td className={`tabular px-3 py-2 text-right ${tone(t.pnl_pct)}`}>{pct(t.pnl_pct)}</td>
                      <td className="px-3 py-2">{t.entry_class ? <span className={`rounded px-2 py-0.5 text-[11px] font-semibold ${CLS[t.entry_class]}`}>{t.entry_class}</span> : <span className="text-xs text-muted">—</span>}</td>
                      <td className="px-3 py-2">{t.exit_class ? <span className={`rounded px-2 py-0.5 text-[11px] font-semibold ${CLS[t.exit_class]}`}>{t.exit_class}</span> : <span className="text-xs text-muted">—</span>}</td>
                      <td className="tabular px-3 py-2 text-right text-xs text-muted">{t.left_on_table_pct ? `${t.left_on_table_pct}%` : "—"}</td>
                    </tr>
                    {open === t.ref && (
                      <tr className="bg-panel-2/30">
                        <td colSpan={9} className="space-y-3 px-4 py-4">
                          <TradeChart t={t} />
                          <div className="flex flex-wrap gap-4 text-xs text-muted">
                            {t.mfe_pct !== undefined && <span>Best open gain (MFE): <b className="text-up">{pct(t.mfe_pct)}</b></span>}
                            {t.mae_pct !== undefined && <span>Worst drawdown (MAE): <b className="text-down">{pct(t.mae_pct)}</b></span>}
                            {t.days !== undefined && <span>Held {t.days} days</span>}
                            {t.r_multiple !== null && t.r_multiple !== undefined && <span>Result: {t.r_multiple > 0 ? "+" : ""}{t.r_multiple}R</span>}
                          </div>
                          <ul className="space-y-1 text-sm">
                            {t.notes.map((n) => (
                              <li key={n} className="flex gap-2"><span className="text-accent">›</span>{n}</li>
                            ))}
                          </ul>
                          <TradeJournal tradeRef={t.ref} onSaved={onNote} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {page.hasMore && <LoadMoreRow sentinel={page.sentinel} colSpan={9} onClick={page.more} />}
              </tbody>
            </table>
            {page.total > 50 && <div className="px-3 pb-2"><ShowingCount shown={page.visible.length} total={page.total} /></div>}
          </div>
  );
}

/** TradeGrader: how well each buy and sell was timed, plus an A-F grade, for trades from Backtest and Portfolios. */
export default function TradeGrader({ source: initial = "all", portfolioId, chartOnly = false }: { source?: string; portfolioId?: number; chartOnly?: boolean }) {
  const [source, setSource] = useState(initial);
  const [pf, setPf] = useState<number | "">("");
  const [portfolios, setPortfolios] = useState<{ id: number; name: string }[]>([]);
  useEffect(() => {
    api<{ id: number; name: string }[]>("/api/portfolios").then(setPortfolios).catch(() => {});
  }, []);
  const pid = portfolioId ?? (source === "portfolio" && pf !== "" ? pf : undefined);
  const [data, setData] = useState<Resp | null>(null);
  const [open_, setOpen] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [noted, setNoted] = useState<Set<string>>(new Set());
  const loadNotes = () => api<{ ref: string }[]>("/api/notes").then((l) => setNoted(new Set(l.map((x) => x.ref)))).catch(() => {});
  useEffect(() => {
    loadNotes();
  }, []);

  useEffect(() => {
    setData(null);
    setError("");
    api<Resp>(`/api/grader?source=${source}${pid ? `&portfolio_id=${pid}` : ""}`).then(setData).catch((e) => setError(e.message));
  }, [source, pid]);

  const s = data?.summary;
  return (
    <div className="space-y-4">
      {!portfolioId && (
        <div className="sticky top-10 z-10 -mx-1 flex min-h-12 flex-wrap items-center gap-1 bg-bg px-1 py-2">
          {(chartOnly ? [["chart", "Charts"], ["copy", "Copied"], ["portfolio", "Portfolios"]] : [["all", "All trades"], ["ideas", "Trade ideas"], ["md", "Move Detector"], ["chart", "Charts"], ["copy", "Copied"], ["portfolio", "Portfolios"]]).map(([id, label]) => (
            <button key={id} onClick={() => setSource(id)} className={`rounded-full px-3 py-1 text-sm ${source === id ? "bg-accent text-white" : "bg-panel text-muted hover:text-text"}`}>
              {label}
            </button>
          ))}
{source === "portfolio" && portfolios.length > 0 && (
          <select value={pf} onChange={(e) => setPf(e.target.value === "" ? "" : Number(e.target.value))}
            className="ml-1 rounded-full border border-line bg-panel px-3 py-1 text-sm text-text">
            <option value="">All portfolios</option>
            {portfolios.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </select>
        )}
        </div>
      )}
      {error && <p className="text-sm text-down">{error}</p>}
      {!data && !error && <p className="text-sm text-muted">Grading your trades…</p>}
      {data && data.trades.length === 0 && portfolioId && (
        <div className="rounded-xl border border-line bg-panel p-6 text-center text-sm text-muted">
          No trades in this portfolio yet. Add a buy (or import your broker file) and it shows up here: open positions are graded on the entry,
          sales on the exit.
        </div>
      )}
      {data && data.trades.length === 0 && !portfolioId && (
        <div className="rounded-xl border border-line bg-panel p-6 text-center text-sm text-muted">
          No trades to grade yet. Take trades from <Link href="/ideas" className="text-accent hover:underline">Trade ideas</Link> or the{" "}
          <Link href="/scanner" className="text-accent hover:underline">Move Detector</Link>, or add / import trades in{" "}
          <Link href="/portfolios" className="text-accent hover:underline">Portfolios</Link>.
        </div>
      )}
      {s && data!.trades.length > 0 && (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="flex items-center gap-4 rounded-xl border border-line bg-panel p-4">
              <span className={`grid h-16 w-16 place-items-center rounded-xl text-3xl font-bold ${s.avg_grade ? GRADE[s.avg_grade] : "bg-panel-2 text-muted"}`}>{s.avg_grade ?? "—"}</span>
              <div className="text-sm">
                <div className="text-muted">Average grade</div>
                <div className="tabular">{s.total_closed ?? s.closed} closed · {s.total_open ?? s.trades - s.closed} open</div>
                {s.closed === 0 && <div className="mt-1 text-xs text-muted">Grades appear when trades close; buys are graded after 5 trading days.</div>}
                {s.top_mistake && <div className="mt-1 text-xs text-amber-300">Most common: {s.top_mistake.toLowerCase()}</div>}
              </div>
            </div>
            <DistCard title="Entries" rows={s.bought} verb="Bought" />
            <DistCard title="Exits" rows={s.sold} verb="Sold" />
          </div>
          {(() => {
            const open = data!.trades.filter((t) => t.open);
            const closed = data!.trades.filter((t) => !t.open);
            return (
              <>
                <section className="space-y-2">
                  <h3 className="flex items-center gap-2 text-sm font-semibold">Closed trades <span className="text-muted">({closed.length})</span>
                    <span className="ml-auto"><ExportButton path={`/api/export/grader?source=${source}${pid ? `&portfolio_id=${pid}` : ""}`} filename="tradegrader.csv" /></span>
                  </h3>
                  {closed.length ? <GradeTable rows={closed} open={open_} setOpen={setOpen} noted={noted} onNote={loadNotes} stickyTop={portfolioId ? "top-0" : "top-[88px]"} /> : <p className="text-sm text-muted">No closed trades yet.</p>}
                </section>
                <section className="space-y-2">
                  <h3 className="text-sm font-semibold">Open trades <span className="text-muted">({open.length})</span> <span className="text-xs font-normal text-muted">· the buy is graded after 5 trading days, the sale when the trade closes</span></h3>
                  {open.length ? <GradeTable rows={open} open={open_} setOpen={setOpen} noted={noted} onNote={loadNotes} stickyTop={portfolioId ? "top-0" : "top-[88px]"} /> : <p className="text-sm text-muted">No open trades.</p>}
                </section>
              </>
            );
          })()}
          <p className="text-[11px] text-muted">
            Buy timing: Perfect = near the breakout / the low and it never went against you; Early = it dropped more than 1.5 ATR after you bought; Late = bought
            extended. Sell timing: Perfect = within 3% of the best price around the sale; Early = it rose another 10% after; Late = gave back more than half of the gain.
          </p>
        </>
      )}
    </div>
  );
}
