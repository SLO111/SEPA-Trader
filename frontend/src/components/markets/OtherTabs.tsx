"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ScoreBar } from "@/components/ScoreBadge";
import { ApiError, api } from "@/lib/api";
import { compactUsd, fmt, pct, tone } from "@/lib/format";
import FearGreedGauge, { fgColor } from "./FearGreedGauge";
import { Panel, StockLink } from "./OverviewTab";
import type { EarningsCal, Extended, ExtRow, FearGreed, Fed, ScreenRow } from "./types";

const LineChart = dynamic(() => import("./LineChart"), { ssr: false });

function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<{ status: number; message: string } | null>(null);
  useEffect(() => {
    setData(null);
    setError(null);
    api<T>(path).then(setData).catch((e) => setError({ status: e instanceof ApiError ? e.status : 0, message: e.message }));
  }, [path]);
  return { data, error };
}

const Loading = () => <p className="text-sm text-muted">Loading…</p>;
const Failed = ({ msg }: { msg: string }) => <p className="rounded-md bg-down/10 px-3 py-2 text-sm text-down">{msg}</p>;

// ------------------------------------------------------------------ Fear & Greed

export function FearGreedTab() {
  const { data: fg, error } = useLoad<FearGreed>("/api/markets/fear-greed");
  const series = useMemo(() => (fg?.history ? [{ name: "Fear & Greed", color: "#3b82f6", data: fg.history }] : []), [fg]);
  if (error) return <Failed msg={error.message} />;
  if (!fg) return <Loading />;
  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
        <Panel title="Fear & Greed index">
          <div className="flex flex-col items-center">
            <FearGreedGauge score={fg.score} label={fg.label} size={300} />
            <div className="text-xl font-semibold" style={{ color: fgColor(fg.score) }}>
              {fg.label}
            </div>
            <div className="mt-1 text-xs text-muted">As of {fg.as_of} close</div>
          </div>
          <dl className="mt-4 space-y-1.5 text-sm">
            {(["close", "week", "month", "year"] as const).map((k) => {
              const v = fg.previous[k];
              return (
                <div key={k} className="flex items-center justify-between">
                  <dt className="text-muted">{{ close: "Previous close", week: "1 week ago", month: "1 month ago", year: "1 year ago" }[k]}</dt>
                  <dd className="flex items-center gap-2">
                    <span className="text-xs" style={{ color: fgColor(v) }}>
                      {v !== null ? (v < 25 ? "Extreme Fear" : v < 45 ? "Fear" : v <= 55 ? "Neutral" : v <= 75 ? "Greed" : "Extreme Greed") : ""}
                    </span>
                    <span className="tabular w-8 rounded py-0.5 text-center font-semibold" style={{ background: `${fgColor(v)}33` }}>
                      {v !== null ? Math.round(v) : "—"}
                    </span>
                  </dd>
                </div>
              );
            })}
          </dl>
        </Panel>
        <Panel title="Last 12 months">
          <LineChart series={series} height={300} range={[0, 100]} />
          <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-muted">
            <span>0–24 Extreme Fear</span>
            <span>25–44 Fear</span>
            <span>45–55 Neutral</span>
            <span>56–75 Greed</span>
            <span>76–100 Extreme Greed</span>
          </div>
        </Panel>
      </div>
      <Panel title="What drives the index">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {fg.components?.map((c) => (
            <div key={c.key} className="rounded-lg border border-line p-3">
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="font-medium">{c.label}</h3>
                <span className="tabular text-sm font-semibold" style={{ color: fgColor(c.score) }}>
                  {Math.round(c.score)}
                </span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
                <div className="h-full rounded-full" style={{ width: `${c.score}%`, background: fgColor(c.score) }} />
              </div>
              <div className="mt-1 text-xs" style={{ color: fgColor(c.score) }}>
                {c.rating}
              </div>
              <p className="mt-2 text-xs text-muted">{c.description}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-muted">
          SEPA Trader&apos;s own sentiment index. Each component is scored 0–100 by where today&apos;s reading sits within its own last 12 months; the index is the average. Inspired by
          classic fear &amp; greed measures, computed from the stocks and ETFs we track.
        </p>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------ Earnings

export function EarningsTab() {
  const { data, error } = useLoad<EarningsCal>("/api/markets/earnings");
  if (error) return <Failed msg={error.message} />;
  if (!data) return <Loading />;
  const groups = data.upcoming.reduce<Record<string, EarningsCal["upcoming"]>>((acc, r) => ((acc[r.date] ||= []).push(r), acc), {});
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Panel title="Upcoming earnings (next 90 days)">
        {data.upcoming.length === 0 ? (
          <p className="text-sm text-muted">No scheduled reports in the next 90 days.</p>
        ) : (
          <div className="space-y-4">
            {Object.entries(groups).map(([day, rows]) => (
              <div key={day}>
                <div className="mb-1 text-xs font-medium text-muted">
                  {new Date(day + "T12:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" })}
                  <span className="ml-2 text-[11px]">in {rows[0].days_until} day{rows[0].days_until === 1 ? "" : "s"}</span>
                </div>
                <ul className="divide-y divide-line rounded-lg border border-line">
                  {rows.map((r) => (
                    <li key={r.symbol} className="flex items-center gap-3 px-3 py-2 text-sm">
                      <StockLink s={r.symbol} />
                      <span className="truncate text-xs text-muted">{r.name}</span>
                      <span className="ml-auto text-xs text-muted">
                        {r.eps_estimate !== null && <>Est. EPS <b className="text-text">{fmt(r.eps_estimate)}</b> · </>}
                        Last surprise <span className={tone(r.last_surprise_pct)}>{pct(r.last_surprise_pct, 1)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Panel>
      <Panel title="Recent reports (last 30 days)">
        {data.recent.length === 0 ? (
          <p className="text-sm text-muted">No reports in the last 30 days.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>
                <th className="py-1.5">Date</th>
                <th className="py-1.5">Symbol</th>
                <th className="py-1.5 text-right">Est.</th>
                <th className="py-1.5 text-right">Actual</th>
                <th className="py-1.5 text-right">Surprise</th>
                <th className="py-1.5 text-right" title="Close before the report to the first close after it">Reaction</th>
              </tr>
            </thead>
            <tbody>
              {data.recent.map((r) => (
                <tr key={r.symbol + r.date} className="border-t border-line">
                  <td className="tabular py-1.5 text-muted">{r.date.slice(5)}</td>
                  <td className="py-1.5"><StockLink s={r.symbol} /></td>
                  <td className="tabular py-1.5 text-right text-muted">{fmt(r.eps_estimate)}</td>
                  <td className="tabular py-1.5 text-right">{fmt(r.eps_actual)}</td>
                  <td className={`tabular py-1.5 text-right ${tone(r.surprise_pct)}`}>{pct(r.surprise_pct, 1)}</td>
                  <td className={`tabular py-1.5 text-right font-medium ${tone(r.reaction_pct)}`}>{pct(r.reaction_pct, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mt-2 text-[11px] text-muted">Reaction: price change from the close before the report to the first close after it.</p>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------ Pre-market & after-hours

function ExtTable({ rows }: { rows: ExtRow[] }) {
  if (!rows.length) return <p className="text-sm text-muted">No trades in this session yet.</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
        <tr>
          <th className="py-1.5">Symbol</th>
          <th className="py-1.5 text-right">Price</th>
          <th className="py-1.5 text-right">Change</th>
          <th className="py-1.5 text-right">Volume</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.symbol} className="border-t border-line">
            <td className="py-1.5">
              <StockLink s={r.symbol} />
              <div className="max-w-[180px] truncate text-xs text-muted">{r.name}</div>
            </td>
            <td className="tabular py-1.5 text-right">{fmt(r.price)}</td>
            <td className={`tabular py-1.5 text-right ${tone(r.change_pct)}`}>
              {pct(r.change_pct)}
              <div className="text-[11px] text-muted">vs {fmt(r.reference_close)}</div>
            </td>
            <td className="tabular py-1.5 text-right text-muted">{r.volume.toLocaleString("en-US")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ExtendedTab() {
  const { data, error } = useLoad<Extended>("/api/markets/extended-hours");
  if (error) return <Failed msg={error.message} />;
  if (!data) return <Loading />;
  if (!data.available) return <Panel title="Pre-market & after-hours"><p className="text-sm text-muted">{data.reason}</p></Panel>;
  return (
    <div className="space-y-3">
      {data.reason && <p className="text-sm text-muted">{data.reason}</p>}
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Pre-market movers" right={<span className="text-xs text-muted">4:00–9:30 AM ET, vs. previous close</span>}>
          <ExtTable rows={data.pre_market} />
        </Panel>
        <Panel title="After-hours movers" right={<span className="text-xs text-muted">4:00–8:00 PM ET, vs. today&apos;s close</span>}>
          <ExtTable rows={data.after_hours} />
        </Panel>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Fed monitor

export function FedTab() {
  const { data: f, error } = useLoad<Fed>("/api/markets/fed");
  const series = useMemo(
    () =>
      f
        ? [
            { name: "Fed funds (upper)", color: "#3b82f6", data: f.history.upper },
            { name: "2-year Treasury", color: "#f59e0b", data: f.history.note_2y, width: 1 as const },
          ].filter((s) => s.data.length)
        : [],
    [f],
  );
  if (error) return <Failed msg={error.message} />;
  if (!f) return <Loading />;
  const days = f.next_meeting ? Math.ceil((new Date(f.next_meeting + "T18:00:00Z").getTime() - Date.now()) / 86400000) : null;
  const o = f.outlook;
  return (
    <div className="space-y-5">
      {f.demo && <p className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm text-amber-200">Demo data: connect a live data provider to load real Federal Reserve data from FRED.</p>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl border border-line bg-panel p-4">
          <div className="text-xs text-muted">Fed funds target range</div>
          <div className="tabular text-2xl font-semibold">
            {f.target_range.lower.toFixed(2)}–{f.target_range.upper.toFixed(2)}%
          </div>
          <div className="text-xs text-muted">Effective rate {f.effective_rate.toFixed(2)}%</div>
        </div>
        <div className="rounded-xl border border-line bg-panel p-4">
          <div className="text-xs text-muted">Next FOMC decision</div>
          <div className="text-2xl font-semibold">{f.next_meeting ? new Date(f.next_meeting + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "TBA"}</div>
          <div className="text-xs text-muted">{days !== null ? `in ${days} day${days === 1 ? "" : "s"}` : "Schedule not yet published"}</div>
        </div>
        <div className="rounded-xl border border-line bg-panel p-4">
          <div className="text-xs text-muted">Treasury yields</div>
          <div className="tabular mt-1 space-y-0.5 text-sm">
            <div className="flex justify-between"><span className="text-muted">3-month</span><span>{fmt(f.treasury.bill_3m, 2, "%")}</span></div>
            <div className="flex justify-between"><span className="text-muted">2-year</span><span>{fmt(f.treasury.note_2y, 2, "%")}</span></div>
            <div className="flex justify-between"><span className="text-muted">10-year</span><span>{fmt(f.treasury.note_10y, 2, "%")}</span></div>
          </div>
        </div>
        <div className="rounded-xl border border-line bg-panel p-4">
          <div className="text-xs text-muted">Yield curve (10y − 2y)</div>
          <div className={`tabular text-2xl font-semibold ${(f.curve_2s10s_bp ?? 0) < 0 ? "text-down" : "text-up"}`}>
            {f.curve_2s10s_bp !== null ? `${f.curve_2s10s_bp > 0 ? "+" : ""}${f.curve_2s10s_bp} bp` : "—"}
          </div>
          <div className="text-xs text-muted">{(f.curve_2s10s_bp ?? 0) < 0 ? "Inverted: historically a recession warning" : "Normal (upward sloping)"}</div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        <Panel title="Market-implied outlook">
          {o ? (
            <>
              {(["cut", "hold", "hike"] as const).map((k) => (
                <div key={k} className="mb-3">
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="capitalize">{k === "cut" ? "Rate cut" : k === "hike" ? "Rate hike" : "No change"}</span>
                    <span className="tabular font-semibold">{o.probabilities[k]}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-line">
                    <div className={`h-full rounded-full ${k === "cut" ? "bg-up" : k === "hike" ? "bg-down" : "bg-slate-400"}`} style={{ width: `${o.probabilities[k]}%` }} />
                  </div>
                </div>
              ))}
              <p className="text-xs text-muted">
                Implied move over ~3 months: <b className="text-text">{o.implied_change_bp > 0 ? "+" : ""}{o.implied_change_bp} bp</b>. {o.method}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted">Not enough data for an estimate.</p>
          )}
          <h3 className="mb-2 mt-5 text-[11px] uppercase tracking-wide text-muted">FOMC meetings</h3>
          <div className="flex flex-wrap gap-1.5">
            {f.meetings.map((m) => (
              <span key={m.date} className={`rounded px-2 py-0.5 text-xs ${m.date === f.next_meeting ? "bg-accent text-white" : m.past ? "bg-line/50 text-muted" : "bg-panel-2"}`}>
                {new Date(m.date + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}
              </span>
            ))}
          </div>
        </Panel>
        <Panel title="Rates over 5 years">
          <LineChart series={series} height={280} suffix="%" />
        </Panel>
      </div>

      <Panel title="Rate decision history">
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="py-1.5">Date</th>
              <th className="py-1.5">Decision</th>
              <th className="py-1.5 text-right">Change</th>
              <th className="py-1.5 text-right">New target range</th>
            </tr>
          </thead>
          <tbody>
            {f.decisions.map((d) => (
              <tr key={d.date} className="border-t border-line">
                <td className="tabular py-1.5">{d.date}</td>
                <td className={`py-1.5 ${d.action === "Cut" ? "text-up" : "text-down"}`}>{d.action}</td>
                <td className="tabular py-1.5 text-right">{d.change_bp > 0 ? "+" : ""}{d.change_bp} bp</td>
                <td className="tabular py-1.5 text-right">{d.lower.toFixed(2)}–{d.upper.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-[11px] text-muted">Source: Federal Reserve Bank of St. Louis (FRED){f.demo ? " · demo values" : ""}. Data as of {f.as_of}.</p>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------ Screener

type Presets = { presets: { id: string; label: string; description: string }[]; sectors: string[] };

export function ScreenerTab({ allowed }: { allowed: boolean }) {
  const [presets, setPresets] = useState<Presets | null>(null);
  const [preset, setPreset] = useState("undervalued");
  const [filters, setFilters] = useState({ sector: "", min_cap_b: "", max_pe: "", min_yield: "", min_rs: "", template_only: false, above_ma50: false });
  const [rows, setRows] = useState<ScreenRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Presets>("/api/markets/screener/presets").then(setPresets).catch(() => {});
  }, []);

  useEffect(() => {
    if (!allowed) return;
    const qs = new URLSearchParams();
    if (preset) qs.set("preset", preset);
    Object.entries(filters).forEach(([k, v]) => {
      if (v === true) qs.set(k, "true");
      else if (v) qs.set(k, String(v));
    });
    setRows(null);
    setError("");
    const t = setTimeout(() => {
      api<{ results: ScreenRow[] }>(`/api/markets/screener?${qs}`).then((r) => setRows(r.results)).catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [preset, filters, allowed]);

  if (!allowed) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-6">
        <h2 className="font-semibold">Stock screener</h2>
        <p className="mt-1 text-sm text-muted">Find undervalued stocks, growth at a reasonable price, high dividends, SEPA leaders and more. Available on the Pro and Premium plans.</p>
        <Link href="/#pricing" className="mt-3 inline-block text-sm text-accent hover:underline">See plans</Link>
      </div>
    );
  }
  const set = (k: keyof typeof filters, v: string | boolean) => setFilters((f) => ({ ...f, [k]: v }));
  const input = "w-20 rounded border border-line bg-bg px-2 py-1 text-sm outline-none focus:border-accent";
  const current = presets?.presets.find((p) => p.id === preset);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        <button onClick={() => setPreset("")} className={`rounded-md px-3 py-1.5 text-sm ${!preset ? "bg-accent text-white" : "bg-panel text-muted hover:text-text"}`}>
          All stocks
        </button>
        {presets?.presets.map((p) => (
          <button key={p.id} onClick={() => setPreset(p.id)} className={`rounded-md px-3 py-1.5 text-sm ${preset === p.id ? "bg-accent text-white" : "bg-panel text-muted hover:text-text"}`}>
            {p.label}
          </button>
        ))}
      </div>
      {current && <p className="text-sm text-muted">{current.description}</p>}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-panel p-3 text-sm text-muted">
        <select value={filters.sector} onChange={(e) => set("sector", e.target.value)} className="rounded border border-line bg-bg px-2 py-1 text-text">
          <option value="">All sectors</option>
          {presets?.sectors.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <label className="flex items-center gap-1.5">Market cap ≥ $<input type="number" min="0" value={filters.min_cap_b} onChange={(e) => set("min_cap_b", e.target.value)} className={input} />B</label>
        <label className="flex items-center gap-1.5">P/E ≤ <input type="number" min="1" value={filters.max_pe} onChange={(e) => set("max_pe", e.target.value)} className={input} /></label>
        <label className="flex items-center gap-1.5">Yield ≥ <input type="number" min="0" step="0.1" value={filters.min_yield} onChange={(e) => set("min_yield", e.target.value)} className={input} />%</label>
        <label className="flex items-center gap-1.5">RS ≥ <input type="number" min="1" max="99" value={filters.min_rs} onChange={(e) => set("min_rs", e.target.value)} className={input} /></label>
        <label className="flex items-center gap-1.5"><input type="checkbox" checked={filters.template_only} onChange={(e) => set("template_only", e.target.checked)} className="accent-blue-500" />Trend Template 8/8</label>
        <label className="flex items-center gap-1.5"><input type="checkbox" checked={filters.above_ma50} onChange={(e) => set("above_ma50", e.target.checked)} className="accent-blue-500" />Above 50-day MA</label>
      </div>
      {error && <Failed msg={error} />}
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[1000px] text-sm">
          <thead className="bg-panel text-left text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2.5">Symbol</th>
              <th className="px-3 py-2.5 text-right">Price</th>
              <th className="px-3 py-2.5 text-right">Today</th>
              <th className="px-3 py-2.5 text-right">Mkt cap</th>
              <th className="px-3 py-2.5 text-right">P/E</th>
              <th className="px-3 py-2.5 text-right" title="P/E vs. sector median">vs sector</th>
              <th className="px-3 py-2.5 text-right">EPS gr.</th>
              <th className="px-3 py-2.5 text-right">Yield</th>
              <th className="px-3 py-2.5 text-right">RSI</th>
              <th className="px-3 py-2.5 text-right">RS</th>
              <th className="px-3 py-2.5 text-right">TT</th>
              <th className="px-3 py-2.5">Bull</th>
            </tr>
          </thead>
          <tbody>
            {rows === null && !error && (
              <tr><td colSpan={12} className="px-3 py-8 text-center text-muted">Screening…</td></tr>
            )}
            {rows?.length === 0 && (
              <tr><td colSpan={12} className="px-3 py-8 text-center text-muted">No stocks match these criteria.</td></tr>
            )}
            {rows?.map((r) => (
              <tr key={r.symbol} className="border-t border-line hover:bg-panel/60">
                <td className="px-3 py-2">
                  <StockLink s={r.symbol} />
                  <div className="max-w-[170px] truncate text-xs text-muted">{r.sector}</div>
                </td>
                <td className="tabular px-3 py-2 text-right">{fmt(r.price)}</td>
                <td className={`tabular px-3 py-2 text-right ${tone(r.change_pct)}`}>{pct(r.change_pct)}</td>
                <td className="tabular px-3 py-2 text-right">{compactUsd(r.market_cap_b ? r.market_cap_b * 1e9 : null)}</td>
                <td className="tabular px-3 py-2 text-right">{fmt(r.pe, 1)}</td>
                <td className={`tabular px-3 py-2 text-right ${r.pe_vs_sector_pct === null ? "text-muted" : r.pe_vs_sector_pct < 0 ? "text-up" : "text-down"}`}>{pct(r.pe_vs_sector_pct, 0)}</td>
                <td className={`tabular px-3 py-2 text-right ${tone(r.eps_growth)}`}>{fmt(r.eps_growth, 0, "%")}</td>
                <td className="tabular px-3 py-2 text-right">{fmt(r.dividend_yield, 2, "%")}</td>
                <td className={`tabular px-3 py-2 text-right ${r.rsi14 <= 30 ? "text-up" : r.rsi14 >= 70 ? "text-down" : ""}`}>{r.rsi14.toFixed(0)}</td>
                <td className="tabular px-3 py-2 text-right">{r.rs_rating ?? "—"}</td>
                <td className={`tabular px-3 py-2 text-right ${r.template_passed === 8 ? "text-up" : "text-muted"}`}>{r.template_passed ?? "—"}/8</td>
                <td className="px-3 py-2"><ScoreBar score={r.bull_score} kind="bull" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
