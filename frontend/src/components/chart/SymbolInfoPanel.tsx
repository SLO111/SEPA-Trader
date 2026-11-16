"use client";

import Link from "next/link";
import { scoreColor } from "@/components/ScoreBadge";
import { compactUsd, fmt, pct, tone } from "@/lib/format";
import type { SymbolInfo } from "@/lib/types";

function Range({ low, high, value, label }: { low: number; high: number; value: number; label: string }) {
  const pos = high > low ? Math.min(100, Math.max(0, ((value - low) / (high - low)) * 100)) : 50;
  return (
    <div>
      <div className="flex justify-between text-[11px] text-muted">
        <span className="tabular">{fmt(low)}</span>
        <span>{label}</span>
        <span className="tabular">{fmt(high)}</span>
      </div>
      <div className="relative mt-1 h-1 rounded-full bg-line">
        <div className="absolute -top-1 h-3 w-0.5 -translate-x-1/2 rounded bg-text" style={{ left: `${pos}%` }} />
      </div>
    </div>
  );
}

const Row = ({ k, v, cls = "" }: { k: string; v: React.ReactNode; cls?: string }) => (
  <div className="flex justify-between gap-3 py-1 text-sm">
    <span className="text-muted">{k}</span>
    <span className={`tabular ${cls}`}>{v}</span>
  </div>
);

/** TradingView-style details panel for the symbol on the chart. */
export default function SymbolInfoPanel({ symbol, info, error }: { symbol: string; info: SymbolInfo | null; error: string }) {
  if (error) return <p className="p-4 text-sm text-muted">{error}</p>;
  if (!info || info.symbol !== symbol) return <p className="p-4 text-sm text-muted">Loading {symbol}…</p>;
  const q = info.quote;
  const ext = info.extended;
  const s = info.stats;
  const sepa = info.sepa;

  return (
    <div className="h-full overflow-y-auto">
      <div className="border-b border-line p-4">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-lg font-semibold">{info.symbol}</span>
          <span className="text-xs text-muted">{info.exchange}</span>
        </div>
        <div className="truncate text-sm text-muted" title={info.name}>
          {info.name}
        </div>
        <div className="text-xs text-muted">{[info.sector, info.industry].filter(Boolean).join(" · ")}</div>

        <div className="mt-3 flex items-baseline gap-2">
          <span className="tabular text-2xl font-semibold">{fmt(q.price)}</span>
          <span className="text-xs text-muted">USD</span>
          <span className={`tabular text-sm ${tone(q.change)}`}>
            {q.change !== undefined && (q.change >= 0 ? "+" : "")}
            {fmt(q.change)} ({pct(q.change_pct)})
          </span>
        </div>
        <div className="text-[11px] text-muted">{info.live_at ? `● Live · ${info.live_at}` : `Close ${q.date}`}</div>

        {ext && (
          <div className="mt-2 rounded-lg bg-panel-2/60 px-3 py-2">
            <div className="flex items-baseline gap-2">
              <span className="text-[11px] uppercase tracking-wide text-violet-300">{ext.session === "pre_market" ? "Pre-market" : "After hours"}</span>
              <span className="tabular font-medium">{fmt(ext.price)}</span>
              <span className={`tabular text-xs ${tone(ext.change)}`}>
                {ext.change >= 0 ? "+" : ""}
                {fmt(ext.change)} ({pct(ext.change_pct)})
              </span>
            </div>
            <div className="text-[11px] text-muted">{ext.time}</div>
          </div>
        )}
        <div className="mt-2 text-[11px] text-muted" title="Overnight trading (8 PM–4 AM ET, e.g. Blue Ocean ATS) needs a paid real-time feed.">
          Overnight session: not available on free data
        </div>

        <div className="mt-4 flex gap-2">
          <Link href={`/stock?s=${encodeURIComponent(symbol)}`} className="flex-1 rounded-md bg-accent py-1.5 text-center text-sm font-medium text-white hover:bg-blue-500">
            Full overview
          </Link>
          <Link href={`/alerts?symbol=${encodeURIComponent(symbol)}`} className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-text">
            🔔
          </Link>
        </div>
      </div>

      <div className="space-y-3 border-b border-line p-4">
        <Range low={info.day.low} high={info.day.high} value={q.price ?? info.day.low} label="Day's range" />
        <Range low={info.week52.low} high={info.week52.high} value={q.price ?? info.week52.low} label="52-week range" />
      </div>

      <div className="border-b border-line p-4">
        <Row k="Volume" v={info.volume.today.toLocaleString("en-US")} />
        <Row k="Avg. volume (50d)" v={info.volume.avg_50d.toLocaleString("en-US")} />
        <Row k="Relative volume" v={info.volume.relative ? `${info.volume.relative}×` : "—"} cls={(info.volume.relative ?? 0) >= 1.5 ? "text-amber-300" : ""} />
        <Row k="Market cap" v={compactUsd(s.market_cap_b ? s.market_cap_b * 1e9 : null)} />
        <Row k="P/E" v={fmt(s.pe, 1)} />
        <Row k="Dividend yield" v={fmt(s.dividend_yield, 2, "%")} />
        <Row k="EPS growth" v={fmt(s.eps_growth, 1, "%")} cls={tone(s.eps_growth)} />
        <Row k="Beta" v={fmt(s.beta)} />
        <Row k="Next earnings" v={info.next_earnings ?? "—"} />
      </div>

      {info.pulse && (
        <div className="border-b border-line p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wide text-muted">vnicorn Pulse · 10 days</span>
            <span
              className={`tabular rounded px-2 py-0.5 text-xs font-semibold ${info.pulse.tone === "constructive" ? "bg-up/15 text-up" : info.pulse.tone === "warning" ? "bg-down/15 text-down" : "bg-panel-2 text-muted"}`}
              title="Confirmations / warnings"
            >
              {info.pulse.conf}/{info.pulse.warn}
            </span>
          </div>
          {info.pulse.today.conf.length + info.pulse.today.warn.length === 0 ? (
            <p className="text-xs text-muted">No signals today.</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {info.pulse.today.conf.map((x) => <span key={x} className="rounded bg-up/10 px-1.5 py-0.5 text-[11px] text-up">✓ {x}</span>)}
              {info.pulse.today.warn.map((x) => <span key={x} className="rounded bg-down/10 px-1.5 py-0.5 text-[11px] text-down">! {x}</span>)}
            </div>
          )}
          {info.pulse.recent.length > 1 && (
            <ul className="mt-2 space-y-0.5 text-[11px] text-muted">
              {info.pulse.recent.slice(1, 4).map((d) => (
                <li key={d.date} className="flex gap-2">
                  <span className="tabular w-10 shrink-0">{d.date.slice(5)}</span>
                  <span className="truncate">
                    {d.conf.length > 0 && <span className="text-up">+{d.conf.length} </span>}
                    {d.warn.length > 0 && <span className="text-down">−{d.warn.length} </span>}
                    {[...d.conf, ...d.warn].slice(0, 2).join(", ")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {sepa && (
        <div className="p-4">
          <div className="mb-2 text-[11px] uppercase tracking-wide text-muted">SEPA analysis</div>
          <Row k="RS Rating" v={sepa.rs_rating ?? "—"} cls={(sepa.rs_rating ?? 0) >= 80 ? "text-up" : ""} />
          <Row k="Trend Template" v={`${sepa.template_passed}/8`} cls={sepa.template_passed === 8 ? "text-up" : sepa.template_passed <= 3 ? "text-down" : "text-amber-300"} />
          <Row k="Bull Score" v={Math.round(sepa.bull_score)} cls={scoreColor(sepa.bull_score, "bull")} />
          <Row k="Bear Score" v={Math.round(sepa.bear_score)} cls={scoreColor(sepa.bear_score, "bear")} />
          <Row k="VCP" v={sepa.vcp ? `Yes · pivot ${sepa.pivot}` : "No"} cls={sepa.vcp ? "text-up" : "text-muted"} />
          {sepa.signals.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {sepa.signals.map((x) => (
                <span key={x} className={`rounded px-1.5 py-0.5 text-[11px] ${x === "Downside risk" ? "bg-down/15 text-down" : "bg-up/10 text-up"}`}>
                  {x}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
