"use client";

import EarningsBadge from "@/components/EarningsBadge";


import Link from "next/link";
import { Fragment, useEffect, useState } from "react";
import { LoadMoreRow, ShowingCount, useShowMore } from "@/lib/useInfinite";
import AppShell from "@/components/AppShell";
import VnicornAICard from "@/components/VnicornAICard";
import { ApiError, api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmt, pct, tone } from "@/lib/format";

const SORTABLE: Record<string, "ai" | "rr" | "status"> = { "R/R": "rr", vnicornAI: "ai", Status: "status" };

type Idea = {
  id: number; date: string; symbol: string; sector?: string; industry?: string; timeframe: "SWING" | "TRADE" | "INVEST" | "SHORT" | "AI"; side: "long" | "short";
  entry: number; stop: number; trim: number | null; target: number; rr: number; weight: number; score: number; reason: string; taken?: boolean; earnings_in?: number | null; rr_now?: number | null; gap?: { price: number; change_pct: number; session: string; text: string } | null; ai?: { prob: number; ev: number; stop: number; trim: number | null; target: number; rr: number; pick: boolean } | null; stage?: { stage: number; name: string; weeks: number } | null; structure?: { text: string; side: "bull" | "bear" | null; step: number; defence: number | null } | null;
  status: "WAIT" | "BUY" | "TRIM" | "TARGET" | "STOPPED" | "CANCEL"; current: number | null; pnl_pct: number | null; r_multiple: number | null; closed_at: string | null;
};
type MarketEvent = { kind: "earnings" | "fed" | "move" | "market"; symbol: string | null; when: string; text: string };
type Resp = {
  events?: MarketEvent[];
  updated: string | null; ideas: Idea[];
  summary: { open: number; active: number; unrealized_pct: number | null; closed: number; win_rate: number | null; avg_r: number | null; by_timeframe: Record<string, number>; ai_closed?: number; ai_avg_r?: number | null; rules_avg_r?: number | null };
};

type Filter = "ALL" | "AIPICKS" | "SWING" | "TRADE" | "INVEST" | "SHORT" | "AI";
const match = (i: Idea, f: Filter) => f === "ALL" || (f === "AIPICKS" ? !!i.ai?.pick : i.timeframe === f);

const TF_STYLE: Record<string, string> = {
  SWING: "bg-blue-600/80 text-white", TRADE: "bg-violet-600/80 text-white", INVEST: "bg-teal-500/80 text-white", SHORT: "bg-red-600/80 text-white",
  AI: "bg-gradient-to-r from-violet-500 to-cyan-500 text-white",
};
const STATUS: Record<string, [string, string]> = {
  WAIT: ["WAIT", "bg-slate-500/30 text-slate-200"], BUY: ["BUY", "bg-up/80 text-white"], TRIM: ["TRIM", "bg-amber-500/80 text-black"],
  TARGET: ["TARGET ✓", "bg-emerald-600 text-white"], STOPPED: ["STOPPED", "bg-down/80 text-white"], CANCEL: ["CNCL", "bg-red-900/70 text-red-200"],
};

function RangeBar({ i }: { i: Idea }) {
  // stop on one side, target on the other; entry tick and current price marker
  const lo = Math.min(i.stop, i.target), hi = Math.max(i.stop, i.target);
  const pos = (x: number) => `${Math.min(100, Math.max(0, ((x - lo) / (hi - lo)) * 100))}%`;
  const cur = i.current ?? i.entry;
  return (
    <div className="relative mx-1 h-1.5 w-20 rounded-full xl:w-28 bg-gradient-to-r from-red-500/50 via-slate-500/40 to-green-500/60" title={`Stop ${i.stop} · entry ${i.entry} · target ${i.target}`}>
      {i.side === "short" && <div className="absolute inset-0 rounded-full bg-gradient-to-r from-green-500/60 via-slate-500/40 to-red-500/50" />}
      <div className="absolute -top-1 h-3.5 w-px bg-white/60" style={{ left: pos(i.entry) }} />
      {i.trim && <div className="absolute -top-0.5 h-2.5 w-px bg-amber-300/80" style={{ left: pos(i.trim) }} />}
      <div className="absolute -top-1 h-3.5 w-3.5 -translate-x-1/2 rounded-full border-2 border-bg bg-white" style={{ left: pos(cur) }} />
    </div>
  );
}

function Ideas() {
  const { user } = useAuth();
  const [view, setView] = useState<"open" | "closed" | "all">("open");
  const [data, setData] = useState<Resp | null>(null);
  const [locked, setLocked] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const [tf, setTf] = useState<"ALL" | "AIPICKS" | "SWING" | "TRADE" | "INVEST" | "SHORT" | "AI">("ALL");
  const [sector, setSector] = useState("");
  // default: vnicornAI's expected value (best first); the R/R, vnicornAI and Status headers sort manually
  const [sort, setSort] = useState<{ key: "ai" | "rr" | "status"; dir: 1 | -1 }>({ key: "ai", dir: -1 });

  const load = () =>
    api<Resp>(`/api/ideas?view=${view}`)
      .then(setData)
      .catch((e) => (e instanceof ApiError && e.status === 403 ? setLocked(e.message) : null));
  const take = async (i: Idea) => {
    const verb = i.side === "short" ? "Short" : "Buy";
    if (i.gap && !confirm(`${i.gap.text}\n\nTake it anyway?`)) return;
    if (!confirm(`${verb} ${i.symbol} now at the current price?\nStop ${i.stop} · ${i.trim ? `trim ${i.trim} · ` : ""}target ${i.target}\n\nIt is followed in Backtest → My trades.`)) return;
    try {
      await post("/api/paper-trades", { idea_id: i.id });
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(() => { if (!document.hidden) load(); }, 120_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  const STATUS_ORDER: Record<string, number> = { BUY: 0, TRIM: 1, WAIT: 2, TARGET: 3, STOPPED: 4, CANCEL: 5 };
  const rrOf = (i: Idea) => (i.rr_now ?? i.rr ?? 0);
  const listed = (data?.ideas ?? [])
    .filter((i) => match(i, tf) && (!sector || i.sector === sector))
    .sort((a, b) => {
      let d = 0;
      if (sort.key === "ai") {
        const x = a.ai?.ev ?? null, y = b.ai?.ev ?? null;
        if (x === null && y !== null) return 1; // ideas vnicornAI didn't rate always last
        if (y === null && x !== null) return -1;
        d = ((x ?? 0) - (y ?? 0)) * sort.dir || (rrOf(a) - rrOf(b)) * -1;
      } else if (sort.key === "rr") d = (rrOf(a) - rrOf(b)) * sort.dir;
      else d = ((STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9)) * sort.dir || rrOf(b) - rrOf(a);
      return d;
    });
  const page = useShowMore(listed, `${tf}|${sector}|${view}|${sort.key}|${sort.dir}`);
  const clickSort = (key: "ai" | "rr" | "status") =>
    setSort((s0) => (s0.key === key ? { key, dir: (s0.dir * -1) as 1 | -1 } : { key, dir: key === "status" ? 1 : -1 }));

  if (locked) {
    return (
      <div className="grid h-full place-items-center p-6">
        <div className="max-w-md rounded-xl border border-amber-500/30 bg-amber-500/5 p-6 text-center">
          <h1 className="text-lg font-semibold">Trade ideas</h1>
          <p className="mt-2 text-sm text-muted">{locked}</p>
          <Link href="/billing" className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-white">See plans</Link>
        </div>
      </div>
    );
  }
  const s = data?.summary;
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1680px] p-3 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-semibold">Trade ideas</h1>
            <p className="text-sm text-muted">Generated every trading day after the close from daily, weekly and monthly trends and historical support/resistance. An idea leaves this list once the reward left is under 1.5× the risk.</p>
            {user && !user.limits.ai_picks && (
              <p className="mt-1 text-xs text-amber-300">
                Your plan shows the top {user.limits.ideas_limit} long ideas a day. <Link href="/billing" className="underline">Premium</Link> shows all 50, shorts and vnicornAI picks.
              </p>
            )}
          </div>
          <div className="ml-auto flex items-center gap-2">
            {data?.updated && <span className="text-xs text-muted">Updated for {data.updated} close</span>}
          </div>
        </div>

        {(data?.events?.length ?? 0) > 0 && (
          <div className="mb-4 space-y-1.5 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-amber-300">High-impact events</div>
            {data!.events!.map((e) => (
              <p key={`${e.kind}-${e.symbol}-${e.when}`} className="text-sm text-amber-100/90">
                {e.kind === "earnings" ? "📅" : e.kind === "fed" ? "🏛" : "⚡"} {e.text}
              </p>
            ))}
          </div>
        )}
        <div className="grid gap-5 2xl:grid-cols-[1fr_300px]">
          <section className="min-w-0 rounded-xl border border-line bg-panel">
            <div className="flex gap-1 border-b border-line p-2">
              {(["open", "closed", "all"] as const).map((v) => (
                <button key={v} onClick={() => setView(v)} className={`rounded px-3 py-1 text-sm ${view === v ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}>
                  {v === "open" ? "Open ideas" : v === "closed" ? "Closed (track record)" : "All"}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-1 border-b border-line px-2 py-1.5">
              {(["ALL", "AIPICKS", "SWING", "TRADE", "INVEST", "SHORT"] as const).map((t) => {
                const n = data?.ideas.filter((i) => match(i, t)).length;
                if (t === "AIPICKS" && user && !user.limits.ai_picks)
                  return <Link key={t} href="/billing" className="rounded-full px-3 py-0.5 text-xs text-muted/70 hover:text-amber-300">🔒 ✦ vnicornAI picks</Link>;
                if (t === "SHORT" && user && !user.limits.ideas_shorts)
                  return <Link key={t} href="/billing" className="rounded-full px-3 py-0.5 text-xs text-muted/70 hover:text-amber-300">🔒 SHORT</Link>;
                return (
                  <button key={t} onClick={() => setTf(t)} className={`rounded-full px-3 py-0.5 text-xs ${tf === t ? "bg-accent text-white" : "text-muted hover:bg-panel-2 hover:text-text"}`}>
                    {t === "ALL" ? "All" : t === "AIPICKS" ? "✦ vnicornAI picks" : t} <span className="tabular opacity-70">{n ?? 0}</span>
                  </button>
                );
              })}
              <select value={sector} onChange={(e) => setSector(e.target.value)} aria-label="Sector"
                className="ml-auto rounded-md border border-line bg-panel px-2 py-0.5 text-xs text-muted">
                <option value="">All sectors</option>
                {Object.entries((data?.ideas ?? []).filter((i) => match(i, tf)).reduce<Record<string, number>>((m, i) => {
                  if (i.sector) m[i.sector] = (m[i.sector] ?? 0) + 1;
                  return m;
                }, {})).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                  <option key={s} value={s}>{s} ({n})</option>
                ))}
              </select>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-sm">
                <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
                  <tr>
                    {[
                      ["Ticker", ""], ["Entry / now", "text-right"], ["Stop", "text-right"], ["Trim", "text-right"], ["Target", "text-right"],
                      ["R/R", "text-center"], ["vnicornAI", ""], ["Setup", ""], ["Range", ""], ["Status", ""], ["", "sticky right-0 z-[1] bg-panel"],
                    ].map(([h, cls]) => (
                      <th key={h || "action"} className={`whitespace-nowrap px-2 py-2.5 ${cls} ${h === "Ticker" ? "sticky left-0 z-[1] bg-panel pl-3" : ""}`}>
                        {SORTABLE[h] ? (
                          <button onClick={() => clickSort(SORTABLE[h])} className={`inline-flex items-center gap-1 uppercase tracking-wide hover:text-text ${sort.key === SORTABLE[h] ? "text-text" : ""}`}>
                            {h}
                            <span className="w-2 text-[9px]">{sort.key === SORTABLE[h] ? (sort.dir === 1 ? "▲" : "▼") : ""}</span>
                          </button>
                        ) : h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {!data && <tr><td colSpan={11} className="px-3 py-10 text-center text-muted">Loading ideas…</td></tr>}
                  {data?.ideas.length === 0 && <tr><td colSpan={11} className="px-3 py-10 text-center text-muted">No ideas here yet. New ideas are published after each trading day.</td></tr>}
                  {page.visible.map((i) => {
                    const move = i.current !== null ? ((i.current / i.entry - 1) * 100 * (i.side === "short" ? -1 : 1)) : null;
                    return (
                      <Fragment key={i.id}>
                        <tr onClick={() => setOpen(open === i.id ? null : i.id)} className="cursor-pointer border-t border-line hover:bg-panel-2/40">
                          <td className="sticky left-0 z-[1] bg-panel py-2 pl-3 pr-2">
                            <div className="flex items-center gap-1.5">
                              <Link href={`/chart?s=${encodeURIComponent(i.symbol)}`} onClick={(e) => e.stopPropagation()}
                                className={`inline-block min-w-[52px] rounded px-1.5 py-1 text-center text-xs font-bold ${i.side === "short" ? "bg-down/20 text-down" : "bg-up/20 text-up"}`}>
                                {i.symbol}
                              </Link>
                              <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${TF_STYLE[i.timeframe]}`}>{i.timeframe}</span>
                              <EarningsBadge days={i.earnings_in} />
                              {i.gap && (
                                <span title={i.gap.text} className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
                                  Gap {i.gap.change_pct > 0 ? "+" : ""}{i.gap.change_pct}%
                                </span>
                              )}
                            </div>
                            <div className="mt-0.5 text-[10px] text-muted" title={`Suggested weight ${i.weight}% of the account`}>{i.date.slice(5)} · {i.weight}%</div>
                            {i.industry && <div className="max-w-[150px] truncate text-[10px] text-muted/80" title={i.sector}>{i.industry}</div>}
                          </td>
                          <td className="tabular whitespace-nowrap px-2 py-2 text-right">
                            <div>${fmt(i.entry)}</div>
                            <div className="text-[11px] text-muted">
                              {i.current !== null ? `$${fmt(i.current)} ` : ""}
                              <span className={tone(i.pnl_pct ?? move)}>{pct(i.pnl_pct ?? move, 1)}</span>
                            </div>
                          </td>
                          <td className="tabular whitespace-nowrap px-2 py-2 text-right text-down/90">${fmt(i.stop)}</td>
                          <td className="tabular whitespace-nowrap px-2 py-2 text-right text-amber-300/90">{i.trim ? `$${fmt(i.trim)}` : "—"}</td>
                          <td className="tabular whitespace-nowrap px-2 py-2 text-right text-up/90">${fmt(i.target)}</td>
                          <td className="px-2 py-2 text-center">
                            <span title={i.rr_now !== null && i.rr_now !== undefined && i.rr_now !== i.rr ? `Planned R/R ${i.rr} · R/R from the current price ${i.rr_now}` : `R/R ${i.rr}`}
                              className={`tabular rounded px-1.5 py-1 text-xs font-semibold ${i.rr >= 3 ? "bg-up/80 text-white" : i.rr >= 2 ? "bg-up/40 text-white" : "bg-amber-500/60 text-black"}`}>{i.rr}</span>
                            {i.rr_now !== null && i.rr_now !== undefined && i.rr_now !== i.rr && <div className="tabular mt-0.5 text-[10px] text-muted">now {i.rr_now}</div>}
                          </td>
                          <td className="px-2 py-2">
                            {i.ai ? (
                              <span
                                title={`vnicornAI: ${Math.round(i.ai.prob * 100)}% chance to reach the target before the stop; expected value ${i.ai.ev > 0 ? "+" : ""}${i.ai.ev}R`}
                                className={`tabular whitespace-nowrap rounded px-1.5 py-1 text-[11px] font-semibold ${i.ai.pick ? "bg-gradient-to-r from-violet-500/30 to-cyan-500/30 text-cyan-100" : i.ai.ev > 0 ? "bg-panel-2 text-text" : "bg-panel-2 text-muted"}`}
                              >
                                {i.ai.pick && "✦ "}
                                {Math.round(i.ai.prob * 100)}% · {i.ai.ev > 0 ? "+" : ""}
                                {i.ai.ev}R
                              </span>
                            ) : user && !user.limits.ai_picks ? (
                              <Link href="/billing" className="text-[11px] text-amber-300/80 hover:text-amber-300" title="vnicornAI ratings are part of Premium">🔒 Premium</Link>
                            ) : (
                              <span className="text-xs text-muted">—</span>
                            )}
                          </td>
                          <td className="px-2 py-2">
                            <div className="flex flex-col items-start gap-1">
                              {i.stage && (
                                <span title={`Market cycle: ${i.stage.name} for ${i.stage.weeks} weeks`} className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-semibold ${STAGE_STYLE[i.stage.stage]}`}>
                                  S{i.stage.stage} {i.stage.name}
                                </span>
                              )}
                              <StructureBadge s={i.structure} />
                            </div>
                          </td>
                          <td className="px-2 py-2"><RangeBar i={i} /></td>
                          <td className="whitespace-nowrap px-2 py-2">
                            <span className={`rounded px-1.5 py-1 text-[11px] font-semibold ${STATUS[i.status][1]}`}>{STATUS[i.status][0]}</span>
                            {i.r_multiple !== null && i.status !== "WAIT" && <span className={`tabular ml-1.5 text-xs ${tone(i.r_multiple)}`}>{i.r_multiple > 0 ? "+" : ""}{i.r_multiple}R</span>}
                          </td>
                          <td className="sticky right-0 z-[1] bg-panel px-2 py-2 text-right" onClick={(e) => e.stopPropagation()}>
                            {["WAIT", "BUY", "TRIM"].includes(i.status) &&
                              (i.taken ? (
                                <Link href="/backtest" className="whitespace-nowrap rounded border border-line px-2 py-1 text-[11px] text-muted hover:text-text" title="Followed in Backtest → My trades">
                                  ✓ Taken
                                </Link>
                              ) : (
                                <button
                                  onClick={() => take(i)}
                                  className={`whitespace-nowrap rounded px-3 py-1 text-xs font-semibold text-white ${i.side === "short" ? "bg-down hover:bg-red-500" : "bg-up hover:bg-green-500"}`}
                                  title="Take this trade now at the current price and follow it in Backtest"
                                >
                                  {i.side === "short" ? "Short" : "Buy"}
                                </button>
                              ))}
                          </td>
                        </tr>
                        {open === i.id && (
                          <tr className="bg-panel-2/30">
                            <td colSpan={11} className="px-4 py-3 text-sm text-muted">
                              <b className="text-text">Why:</b> {i.reason} {i.side === "short" ? "Short" : "Buy"} near ${fmt(i.entry)}, stop ${fmt(i.stop)}
                              {i.trim ? `, trim part at $${fmt(i.trim)}` : ""}, target ${fmt(i.target)}. Suggested weight {i.weight}% risks about 1% of the account at the stop.
                              {i.closed_at && ` Closed ${i.closed_at}.`}
                              {i.ai && i.timeframe !== "AI" && (
                                <div className="mt-2">
                                  <b className="text-text">vnicornAI plan:</b> {Math.round(i.ai.prob * 100)}% estimated chance to reach the target first (EV {i.ai.ev > 0 ? "+" : ""}
                                  {i.ai.ev}R). Its best plan: stop ${fmt(i.ai.stop)}{i.ai.trim ? `, trim $${fmt(i.ai.trim)}` : ""}, target ${fmt(i.ai.target)} (R/R {i.ai.rr}).
                                  {i.ai.pick ? " ✦ A vnicornAI pick." : i.ai.ev <= 0 ? " The model sees a negative expected value here: consider skipping or a smaller size." : ""}
                                </div>
                              )}
                              <div className="mt-2">
                                <b className="text-text">Position plan:</b>{" "}
                                {i.side === "short"
                                  ? `Short half at $${fmt(i.entry)}; add the other half only after it closes below $${fmt(i.entry - (i.stop - i.entry))} (1R in your favor), never on a rally against you. `
                                  : `Buy half (${(i.weight / 2).toFixed(1)}%) at $${fmt(i.entry)}; add the other half only after it closes above $${fmt(i.entry + (i.entry - i.stop))} (1R in profit) — never add below the entry. `}
                                {i.trim ? `Sell half at $${fmt(i.trim)} and move the stop to break-even; ` : "Once up 2R, move the stop to break-even; "}
                                let the rest run to ${fmt(i.target)} or until the structure defence breaks. The stop at ${fmt(i.stop)} applies to the whole position.
                              </div>
                              {i.structure?.step === 4 && i.structure.defence && ` Structure ${i.structure.text}: defend at $${fmt(i.structure.defence)} (${i.structure.side === "bull" ? "higher lows" : "lower highs"}).`}
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                  {page.hasMore && <LoadMoreRow sentinel={page.sentinel} colSpan={11} onClick={page.more} />}
                </tbody>
              </table>
            </div>
            {page.total > 50 && <div className="px-3 pb-3"><ShowingCount shown={page.visible.length} total={page.total} /></div>}
          </section>

          <aside className="grid content-start gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-1">
            <section className="rounded-xl border border-line bg-panel p-4">
              <h2 className="mb-3 font-semibold">Summary</h2>
              <div className="rounded-lg bg-panel-2/60 p-3 text-center">
                <div className="text-[11px] uppercase tracking-wide text-muted">Unrealized P/L (active ideas)</div>
                <div className={`tabular text-3xl font-semibold ${tone(s?.unrealized_pct)}`}>{pct(s?.unrealized_pct, 1)}</div>
                <div className="text-xs text-muted">{s?.active ?? 0} active · {s?.open ?? 0} open</div>
              </div>
              <div className="mt-3 grid grid-cols-5 gap-1 text-center text-[11px]">
                {Object.entries(s?.by_timeframe ?? {}).map(([tf, n]) => (
                  <div key={tf} className="rounded bg-panel-2/60 py-1.5">
                    <div className="text-muted">{tf}</div>
                    <div className="tabular font-semibold">{n}</div>
                  </div>
                ))}
              </div>
            </section>
            <VnicornAICard aiAvgR={s?.ai_avg_r} rulesAvgR={s?.rules_avg_r} aiClosed={s?.ai_closed} />
            <section className="rounded-xl border border-line bg-panel p-4">
              <h2 className="mb-2 font-semibold">Track record</h2>
              <div className="flex justify-between py-1 text-sm"><span className="text-muted">Closed ideas</span><span className="tabular">{s?.closed ?? 0}</span></div>
              <div className="flex justify-between py-1 text-sm"><span className="text-muted">Win rate</span><span className="tabular">{s?.win_rate !== null && s?.win_rate !== undefined ? `${s.win_rate}%` : "—"}</span></div>
              <div className="flex justify-between py-1 text-sm"><span className="text-muted">Average result</span><span className={`tabular ${tone(s?.avg_r)}`}>{s?.avg_r !== null && s?.avg_r !== undefined ? `${s.avg_r > 0 ? "+" : ""}${s.avg_r}R` : "—"}</span></div>
              <p className="mt-2 text-[11px] text-muted">Every idea is tracked from its publication: WAIT until the entry triggers, then TRIM at the first target, TARGET or STOPPED. Ideas that never trigger are cancelled after 10 days.</p>
            </section>
            <p className="text-[11px] text-muted">Ideas are generated automatically by rules, not by a person. For educational purposes only. Not financial advice.</p>
          </aside>
        </div>
      </div>
    </div>
  );
}

const STAGE_STYLE: Record<number, string> = {
  1: "bg-slate-500/25 text-slate-200",
  2: "bg-up/25 text-up",
  3: "bg-amber-500/25 text-amber-300",
  4: "bg-down/25 text-down",
};

/** Structure Count 4/4: who is in control (4/4 = confirmed, 1–3 = count in progress). */
function StructureBadge({ s }: { s?: { text: string; side: "bull" | "bear" | null; step: number; defence: number | null } | null }) {
  if (!s || !s.side) return <span className="text-xs text-muted">—</span>;
  const bull = s.side === "bull";
  const done = s.step === 4;
  return (
    <span
      title={done && s.defence ? `Defence ${s.defence} (${bull ? "higher lows" : "lower highs"})` : "Count in progress"}
      className={`whitespace-nowrap rounded px-2 py-1 text-[11px] font-semibold ${done ? (bull ? "bg-up/25 text-up" : "bg-down/25 text-down") : "border border-line text-muted"}`}
    >
      {s.text}
    </span>
  );
}

export default function IdeasPage() {
  return (
    <AppShell>
      <Ideas />
    </AppShell>
  );
}
