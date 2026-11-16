"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import { scoreColor } from "@/components/ScoreBadge";
import { compactUsd, fmt, pct, tone } from "@/lib/format";
import type { Candle, StockData } from "@/lib/types";
import Gauge from "./Gauge";
import type { Range } from "./MiniChart";

const MiniChart = dynamic(() => import("./MiniChart"), { ssr: false });
const TradingViewWidget = dynamic(() => import("@/components/TradingViewWidget"), { ssr: false });

const TONE_DOT = { positive: "bg-up", negative: "bg-down", neutral: "bg-muted" } as const;

export function Card({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export function KV({ rows }: { rows: [string, string][] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-3 border-b border-line/60 pb-1.5">
          <dt className="text-muted">{k}</dt>
          <dd className="tabular font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function Overview({ d, candles }: { d: StockData; candles: Candle[] }) {
  const [range, setRange] = useState<Range>("1Y");
  const c = d.company;
  const s = c.stats, v = c.valuation, p = c.profitability, h = c.health;
  const tt = d.sepa.trend_template;
  const md = d.sepa.move_detector;

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
      <div className="space-y-5">
        <Card
          title="Price"
          right={
            <div className="flex gap-1">
              {(["1M", "6M", "1Y", "3Y"] as Range[]).map((r) => (
                <button key={r} onClick={() => setRange(r)} className={`rounded px-2 py-0.5 text-xs ${range === r ? "bg-accent text-white" : "text-muted hover:text-text"}`}>
                  {r}
                </button>
              ))}
            </div>
          }
        >
          <MiniChart candles={candles} range={range} />
          <div className="mt-3 grid grid-cols-4 gap-2 text-center sm:grid-cols-7">
            {["1W", "1M", "3M", "6M", "YTD", "1Y", "3Y"].map((k) => (
              <div key={k} className="rounded-lg bg-panel-2/60 px-2 py-1.5">
                <div className="text-[11px] text-muted">{k}</div>
                <div className={`tabular text-sm font-medium ${tone(d.returns[k])}`}>{pct(d.returns[k], 1)}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card title={`Summary: ${d.verdict}`}>
          <ul className="space-y-2 text-sm">
            {d.takeaways.map((t) => (
              <li key={t.text} className="flex gap-2.5">
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${TONE_DOT[t.tone]}`} />
                <span>{t.text}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] text-muted">Generated automatically from market data and technical rules.</p>
        </Card>

        <Card title="Key statistics">
          <KV
            rows={[
              ["Market cap", compactUsd(s.market_cap_b ? s.market_cap_b * 1e9 : null)],
              ["P/E (TTM)", fmt(v.pe, 1)],
              ["52-week range", s.week52_low && s.week52_high ? `${fmt(s.week52_low)} – ${fmt(s.week52_high)}` : "—"],
              ["Forward P/E", fmt(v.forward_pe, 1)],
              ["EPS (TTM)", fmt(s.eps_ttm)],
              ["PEG ratio", fmt(v.peg)],
              ["Beta", fmt(s.beta)],
              ["Price/Sales", fmt(v.ps, 1)],
              ["Avg. volume", s.avg_volume ? s.avg_volume.toLocaleString("en-US") : "—"],
              ["Price/Book", fmt(v.pb, 1)],
              ["Dividend yield", fmt(c.dividends.yield, 2, "%")],
              ["EV/EBITDA", fmt(v.ev_ebitda, 1)],
              ["Gross margin", fmt(p.gross_margin, 1, "%")],
              ["Revenue growth", fmt(p.revenue_growth, 1, "%")],
              ["Net margin", fmt(p.net_margin, 1, "%")],
              ["EPS growth", fmt(p.eps_growth, 1, "%")],
              ["ROE", fmt(p.roe, 1, "%")],
              ["Debt/Equity", fmt(h.debt_to_equity)],
              ["Cash", compactUsd(h.cash_b ? h.cash_b * 1e9 : null)],
              ["Total debt", compactUsd(h.debt_b ? h.debt_b * 1e9 : null)],
            ]}
          />
        </Card>

        {d.peers.length > 0 && (
          <Card title="Peers">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
                  <tr>
                    <th className="py-1.5">Symbol</th>
                    <th className="py-1.5 text-right">Price</th>
                    <th className="py-1.5 text-right">Today</th>
                    <th className="py-1.5 text-right">Market cap</th>
                    <th className="py-1.5 text-right">P/E</th>
                    <th className="py-1.5 text-right">Yield</th>
                    <th className="py-1.5 text-right">RS</th>
                  </tr>
                </thead>
                <tbody>
                  {d.peers.map((x) => (
                    <tr key={x.symbol} className="border-t border-line">
                      <td className="py-1.5">
                        <Link href={`/stock?s=${encodeURIComponent(x.symbol)}`} className="font-medium hover:text-accent">
                          {x.symbol}
                        </Link>
                        <span className="ml-2 text-xs text-muted">{x.name}</span>
                      </td>
                      <td className="tabular py-1.5 text-right">{fmt(x.price)}</td>
                      <td className={`tabular py-1.5 text-right ${tone(x.change_pct)}`}>{pct(x.change_pct)}</td>
                      <td className="tabular py-1.5 text-right">{compactUsd(x.market_cap_b ? x.market_cap_b * 1e9 : null)}</td>
                      <td className="tabular py-1.5 text-right">{fmt(x.pe, 1)}</td>
                      <td className="tabular py-1.5 text-right">{fmt(x.dividend_yield, 2, "%")}</td>
                      <td className="tabular py-1.5 text-right">{x.rs_rating ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>

      <div className="space-y-5">
        {d.key_facts && (d.key_facts.facts.length > 0 || d.key_facts.headline) && (
          <section className="rounded-xl border border-violet-500/30 bg-gradient-to-br from-violet-500/10 to-panel p-4">
            <h2 className="mb-2 flex items-center gap-1.5 font-semibold">
              <span className="text-violet-300">✦</span> Key facts
            </h2>
            <ul className="space-y-1.5 text-sm">
              {d.key_facts.facts.map((f) => (
                <li key={f} className="leading-snug">
                  {f}
                </li>
              ))}
            </ul>
            {d.key_facts.headline && (
              <div className="mt-3 border-t border-line pt-2 text-sm">
                <span className="text-[11px] uppercase tracking-wide text-muted">In the news</span>
                <p className="leading-snug">{d.key_facts.headline.title}</p>
                {d.key_facts.headline.url && (
                  <a href={d.key_facts.headline.url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent hover:underline">
                    Keep reading{d.key_facts.headline.publisher ? ` (${d.key_facts.headline.publisher})` : ""} ›
                  </a>
                )}
              </div>
            )}
          </section>
        )}

        <Card title="Technicals" right={<span className="text-[11px] text-muted">26 indicators · TradingView</span>}>
          <TradingViewWidget
            script="embed-widget-technical-analysis.js"
            height={420}
            config={{
              interval: "1D",
              width: "100%",
              height: "100%",
              isTransparent: true,
              symbol: c.symbol.replace("-", "."),
              showIntervalTabs: true,
              displayMode: "single",
              locale: "en",
              colorTheme: "dark",
            }}
          />
        </Card>

        {c.analysts && c.analysts.score !== null && (
          <Card title="Analyst rating" right={<span className="text-[11px] text-muted">{c.analysts.total} analysts</span>}>
            <Gauge value={(5 - c.analysts.score) / 4} label={c.analysts.rating ?? "—"} />
            {c.analysts.target_mean && (
              <div className="mt-3 flex justify-between text-sm">
                <span className="text-muted">1-year price target</span>
                <span className="tabular">
                  {fmt(c.analysts.target_mean)}{" "}
                  {c.analysts.upside_pct !== null && <span className={tone(c.analysts.upside_pct)}>({pct(c.analysts.upside_pct, 1)})</span>}
                </span>
              </div>
            )}
          </Card>
        )}

        <Card title="SEPA analysis" right={<Link href={`/chart?s=${encodeURIComponent(c.symbol)}`} className="text-xs text-accent hover:underline">Open chart</Link>}>
          <div className="grid grid-cols-2 gap-3 text-center">
            <div className="rounded-lg bg-panel-2/60 p-2">
              <div className="text-[11px] text-muted">Trend Template</div>
              <div className={`tabular text-xl font-semibold ${tt.all_passed ? "text-up" : tt.passed_count <= 3 ? "text-down" : "text-amber-300"}`}>{tt.passed_count}/8</div>
            </div>
            <div className="rounded-lg bg-panel-2/60 p-2">
              <div className="text-[11px] text-muted">RS Rating</div>
              <div className={`tabular text-xl font-semibold ${(d.sepa.rs_rating ?? 0) >= 80 ? "text-up" : ""}`}>{d.sepa.rs_rating ?? "—"}</div>
            </div>
            <div className="rounded-lg bg-panel-2/60 p-2">
              <div className="text-[11px] text-muted">Bull Score</div>
              <div className={`tabular text-xl font-semibold ${scoreColor(md?.bull.score, "bull")}`}>{md ? md.bull.score ?? "—" : "Pro"}</div>
            </div>
            <div className="rounded-lg bg-panel-2/60 p-2">
              <div className="text-[11px] text-muted">Bear Score</div>
              <div className={`tabular text-xl font-semibold ${scoreColor(md?.bear.score, "bear")}`}>{md ? md.bear.score ?? "—" : "Pro"}</div>
            </div>
          </div>
          <ul className="mt-3 space-y-1 text-xs">
            {tt.criteria.map((x) => (
              <li key={x.label} className="flex gap-2">
                <span className={x.passed ? "text-up" : "text-down"}>{x.passed ? "✓" : "✗"}</span>
                <span className={x.passed ? "" : "text-muted"}>{x.label}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-sm">
            VCP:{" "}
            {d.sepa.vcp.detected ? (
              <span className="text-up">
                detected · pivot {d.sepa.vcp.pivot} · stop {d.sepa.vcp.stop}
              </span>
            ) : (
              <span className="text-muted">not detected</span>
            )}
          </p>
        </Card>

        <Card title="About">
          {c.profile.description && <p className="text-sm leading-relaxed text-muted">{c.profile.description}</p>}
          <dl className="mt-3 space-y-1.5 text-sm">
            {[
              ["Sector", c.sector],
              ["Industry", c.industry],
              ["Employees", c.profile.employees?.toLocaleString("en-US")],
              ["Headquarters", c.profile.headquarters],
            ]
              .filter(([, val]) => val)
              .map(([k, val]) => (
                <div key={k} className="flex justify-between gap-3">
                  <dt className="text-muted">{k}</dt>
                  <dd className="text-right">{val}</dd>
                </div>
              ))}
            {c.profile.website && (
              <div className="flex justify-between gap-3">
                <dt className="text-muted">Website</dt>
                <dd>
                  <a href={c.profile.website} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                    {c.profile.website.replace(/^https?:\/\//, "")}
                  </a>
                </dd>
              </div>
            )}
          </dl>
        </Card>
      </div>
    </div>
  );
}
