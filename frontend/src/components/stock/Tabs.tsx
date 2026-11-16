"use client";

import { useState } from "react";
import { compactUsd, fmt, pct, tone } from "@/lib/format";
import type { Company, FinRow } from "@/lib/types";
import { Card, KV } from "./Overview";

function LiveOnly({ what }: { what: string }) {
  return <p className="text-sm text-muted">{what}: not available for this stock from our data sources right now.</p>;
}

// ------------------------------------------------------------------ financials

const ANNUAL_ROWS: [string, string][] = [
  ["Revenue", "revenue"], ["Gross profit", "gross_profit"], ["Operating income", "operating_income"], ["Net income", "net_income"], ["EPS (diluted)", "eps"],
  ["Total assets", "total_assets"], ["Total liabilities", "total_liabilities"], ["Shareholders' equity", "equity"], ["Cash", "cash"], ["Total debt", "debt"],
  ["Operating cash flow", "operating_cash_flow"], ["Capital expenditure", "capex"], ["Free cash flow", "free_cash_flow"],
];
const QUARTER_ROWS = ANNUAL_ROWS.slice(0, 5);

function Bars({ rows, k, label }: { rows: FinRow[]; k: string; label: string }) {
  const vals = [...rows].reverse().map((r) => ({ p: r.period, v: (r[k] as number | null) ?? 0 }));
  const max = Math.max(...vals.map((x) => Math.abs(x.v)), 1);
  return (
    <div>
      <div className="mb-2 text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className="flex h-28 items-end gap-2">
        {vals.map((x) => (
          <div key={x.p} className="flex flex-1 flex-col items-center gap-1" title={`${x.p}: ${compactUsd(x.v)}`}>
            <div className="flex w-full flex-1 items-end">
              <div className={`w-full rounded-t ${x.v >= 0 ? "bg-accent/70" : "bg-down/70"}`} style={{ height: `${(Math.abs(x.v) / max) * 100}%` }} />
            </div>
            <span className="text-[10px] text-muted">{x.p.length > 4 ? x.p.slice(2, 7) : x.p}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Financials({ c }: { c: Company }) {
  const [mode, setMode] = useState<"annual" | "quarterly">("annual");
  const rows = c.financials[mode];
  const defs = mode === "annual" ? ANNUAL_ROWS : QUARTER_ROWS;
  if (!c.financials.annual.length && !c.financials.quarterly.length) return <Card title="Financials"><LiveOnly what="Financial statements" /></Card>;
  return (
    <Card
      title="Financials"
      right={
        <div className="flex gap-1">
          {(["annual", "quarterly"] as const).map((m) => (
            <button key={m} onClick={() => setMode(m)} className={`rounded px-2 py-0.5 text-xs capitalize ${mode === m ? "bg-accent text-white" : "text-muted hover:text-text"}`}>
              {m}
            </button>
          ))}
        </div>
      }
    >
      <div className="mb-5 grid gap-6 sm:grid-cols-2">
        <Bars rows={rows} k="revenue" label="Revenue" />
        <Bars rows={rows} k="net_income" label="Net income" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px] text-sm">
          <thead className="text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="py-1.5 text-left" />
              {rows.map((r) => (
                <th key={r.period} className="py-1.5 text-right">
                  {r.period}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {defs.map(([label, k]) => (
              <tr key={k} className="border-t border-line">
                <td className="py-1.5 text-muted">{label}</td>
                {rows.map((r) => (
                  <td key={r.period} className={`tabular py-1.5 text-right ${typeof r[k] === "number" && (r[k] as number) < 0 ? "text-down" : ""}`}>
                    {k === "eps" ? fmt(r[k] as number | null) : compactUsd(r[k] as number | null)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ earnings

export function Earnings({ c }: { c: Company }) {
  const e = c.earnings;
  return (
    <Card title="Earnings" right={e.next_date && <span className="text-sm text-muted">Next report: <b className="text-text">{e.next_date}</b></span>}>
      {e.history.length === 0 ? (
        <LiveOnly what="Earnings results" />
      ) : (
        <table className="w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="py-1.5">Quarter</th>
              <th className="py-1.5 text-right">EPS estimate</th>
              <th className="py-1.5 text-right">EPS actual</th>
              <th className="py-1.5 text-right">Surprise</th>
            </tr>
          </thead>
          <tbody>
            {e.history.map((x) => (
              <tr key={x.date} className="border-t border-line">
                <td className="tabular py-1.5">{x.date}</td>
                <td className="tabular py-1.5 text-right text-muted">{fmt(x.eps_estimate)}</td>
                <td className="tabular py-1.5 text-right">{fmt(x.eps_actual)}</td>
                <td className={`tabular py-1.5 text-right ${tone(x.surprise_pct)}`}>
                  {pct(x.surprise_pct, 1)} {x.surprise_pct !== null && (x.surprise_pct >= 0 ? "beat" : "miss")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ dividends

export function Dividends({ c }: { c: Company }) {
  const d = c.dividends;
  if (!d.yield && !d.history.length) return <Card title="Dividends"><p className="text-sm text-muted">{c.name} does not pay a dividend.</p></Card>;
  return (
    <Card title="Dividends">
      <KV rows={[["Dividend yield", fmt(d.yield, 2, "%")], ["Annual dividend", d.annual ? `$${fmt(d.annual)}` : "—"], ["Payout ratio", fmt(d.payout_ratio, 0, "%")], ["Last ex-dividend date", d.ex_date ?? "—"]]} />
      {d.history.length > 0 && (
        <table className="mt-4 w-full text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="py-1.5">Ex-dividend date</th>
              <th className="py-1.5 text-right">Amount per share</th>
            </tr>
          </thead>
          <tbody>
            {[...d.history].reverse().map((x) => (
              <tr key={x.date} className="border-t border-line">
                <td className="tabular py-1.5">{x.date}</td>
                <td className="tabular py-1.5 text-right">${fmt(x.amount, 4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ analysts

const RATING_KEYS: [string, string, string][] = [
  ["strong_buy", "Strong buy", "bg-emerald-500"], ["buy", "Buy", "bg-green-400"], ["hold", "Hold", "bg-slate-400"], ["sell", "Sell", "bg-orange-400"], ["strong_sell", "Strong sell", "bg-red-500"],
];

export function Analysts({ c, price }: { c: Company; price: number }) {
  const a = c.analysts;
  if (!a || (!a.total && !a.target_mean)) return <Card title="Analyst ratings"><LiveOnly what="Analyst ratings" /></Card>;
  const lo = a.target_low ?? price, hi = a.target_high ?? price;
  const span = Math.max(hi, price) - Math.min(lo, price) || 1;
  const pos = (x: number) => `${((x - Math.min(lo, price)) / span) * 100}%`;
  return (
    <Card title="Analyst ratings">
      <div className="flex flex-wrap items-baseline gap-3">
        <span className={`text-2xl font-semibold ${a.rating?.includes("Buy") ? "text-up" : a.rating?.includes("Sell") ? "text-down" : ""}`}>{a.rating ?? "—"}</span>
        <span className="text-sm text-muted">{a.total} analysts</span>
      </div>
      {a.total > 0 && (
        <>
          <div className="mt-3 flex h-3 overflow-hidden rounded-full">
            {RATING_KEYS.map(([k, , col]) => (a.counts[k] ? <div key={k} className={col} style={{ width: `${(a.counts[k] / a.total) * 100}%` }} /> : null))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
            {RATING_KEYS.map(([k, label, col]) => (
              <span key={k} className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${col}`} />
                {label}: <b className="text-text">{a.counts[k] ?? 0}</b>
              </span>
            ))}
          </div>
        </>
      )}
      {a.target_mean && (
        <div className="mt-6">
          <div className="mb-2 flex items-baseline justify-between text-sm">
            <span className="text-muted">12-month price target</span>
            <span>
              <b className="tabular">${fmt(a.target_mean)}</b> <span className={`tabular ${tone(a.upside_pct)}`}>({pct(a.upside_pct, 1)})</span>
            </span>
          </div>
          <div className="relative mx-6 mt-10 h-1.5 rounded-full bg-line">
            {[["Low", lo], ["Mean", a.target_mean], ["High", hi]].map(([l, x]) => (
              <div key={l as string} className="absolute -top-8 -translate-x-1/2 text-center text-[10px] leading-tight text-muted" style={{ left: pos(x as number) }}>
                {l}
                <div className="tabular">{fmt(x as number)}</div>
              </div>
            ))}
            <div className="absolute -top-1 h-3.5 w-1 -translate-x-1/2 rounded bg-accent" style={{ left: pos(price) }} title={`Current price ${fmt(price)}`} />
          </div>
          <p className="mt-8 text-xs text-muted">Blue marker: current price ({fmt(price)}).</p>
        </div>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ ownership

export function Ownership({ c }: { c: Company }) {
  const o = c.ownership;
  return (
    <div className="space-y-5">
      {o.insider_sentiment && (
        <Card title="Insider sentiment" right={<span className="text-[11px] text-muted">Net buying vs. selling by executives, −100 to +100</span>}>
          <div className="flex flex-wrap items-end gap-6">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-muted">Last 3 months</div>
              <div className={`tabular text-3xl font-semibold ${o.insider_sentiment.avg_3m > 5 ? "text-up" : o.insider_sentiment.avg_3m < -5 ? "text-down" : ""}`}>
                {o.insider_sentiment.avg_3m > 0 ? "+" : ""}
                {o.insider_sentiment.avg_3m}
              </div>
              <div className="text-xs text-muted">{o.insider_sentiment.avg_3m > 5 ? "Insiders are buying" : o.insider_sentiment.avg_3m < -5 ? "Insiders are selling" : "Neutral"}</div>
            </div>
            <div className="flex h-20 flex-1 items-center gap-1.5">
              {o.insider_sentiment.months.map((m) => (
                <div key={m.month} className="flex flex-1 flex-col items-center justify-center" title={`${m.month}: ${m.mspr}`}>
                  <div className="flex h-16 w-full flex-col justify-center">
                    <div className="flex h-1/2 items-end">{m.mspr > 0 && <div className="w-full rounded-t bg-up/70" style={{ height: `${Math.min(100, m.mspr)}%` }} />}</div>
                    <div className="flex h-1/2 items-start border-t border-line">{m.mspr < 0 && <div className="w-full rounded-b bg-down/70" style={{ height: `${Math.min(100, -m.mspr)}%` }} />}</div>
                  </div>
                  <span className="mt-0.5 text-[10px] text-muted">{m.month.slice(5)}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}
      {(o.institutional_pct !== null || o.insider_pct !== null) && (
        <Card title="Ownership">
          <KV rows={[["Institutions", fmt(o.institutional_pct, 1, "%")], ["Insiders", fmt(o.insider_pct, 2, "%")]]} />
        </Card>
      )}
      <Card title="Top institutional holders">
        {o.top_holders.length === 0 ? (
          <p className="text-sm text-muted">Fund holdings (13F filings) are only offered on paid data plans, so they aren&apos;t shown here yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>
                <th className="py-1.5">Holder</th>
                <th className="py-1.5 text-right">% held</th>
                <th className="py-1.5 text-right">Shares</th>
                <th className="py-1.5 text-right">Value</th>
              </tr>
            </thead>
            <tbody>
              {o.top_holders.map((x) => (
                <tr key={x.name} className="border-t border-line">
                  <td className="py-1.5">{x.name}</td>
                  <td className="tabular py-1.5 text-right">{fmt(x.pct, 2, "%")}</td>
                  <td className="tabular py-1.5 text-right">{x.shares ? x.shares.toLocaleString("en-US") : "—"}</td>
                  <td className="tabular py-1.5 text-right">{compactUsd(x.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card title="Insider transactions">
        {o.insider_transactions.length === 0 ? (
          <LiveOnly what="Insider transactions" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
                <tr>
                  <th className="py-1.5">Date</th>
                  <th className="py-1.5">Insider</th>
                  <th className="py-1.5">Transaction</th>
                  <th className="py-1.5 text-right">Shares</th>
                  <th className="py-1.5 text-right">Price</th>
                  <th className="py-1.5 text-right">Value</th>
                </tr>
              </thead>
              <tbody>
                {o.insider_transactions.map((x, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="tabular py-1.5 text-muted">{x.date ?? "—"}</td>
                    <td className="py-1.5">
                      {x.insider}
                      <div className="text-xs text-muted">{x.position}</div>
                    </td>
                    <td className={`py-1.5 ${x.transaction === "Purchase" ? "text-up" : x.transaction === "Sale" ? "text-down" : "text-muted"}`}>{x.transaction || "—"}</td>
                    <td className={`tabular py-1.5 text-right ${(x.shares ?? 0) > 0 ? "text-up" : (x.shares ?? 0) < 0 ? "text-down" : ""}`}>
                      {x.shares ? `${x.shares > 0 ? "+" : ""}${x.shares.toLocaleString("en-US")}` : "—"}
                    </td>
                    <td className="tabular py-1.5 text-right">{x.price ? fmt(x.price) : "—"}</td>
                    <td className="tabular py-1.5 text-right">{compactUsd(x.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ news

export function News({ c }: { c: Company }) {
  return (
    <Card title="News">
      {c.news.length === 0 ? (
        <LiveOnly what="News headlines" />
      ) : (
        <ul className="divide-y divide-line">
          {c.news.map((n) => (
            <li key={n.url} className="py-3">
              <a href={n.url} target="_blank" rel="noopener noreferrer" className="font-medium hover:text-accent">
                {n.title}
              </a>
              <div className="mt-0.5 text-xs text-muted">
                {[n.publisher, n.published ? new Date(n.published).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" }) : null].filter(Boolean).join(" · ")}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
