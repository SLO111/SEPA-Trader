"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import Overview from "@/components/stock/Overview";
import { Analysts, Dividends, Earnings, Financials, News, Ownership } from "@/components/stock/Tabs";
import { api, download } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmt, pct, tone } from "@/lib/format";
import type { CandlesResponse, StockData } from "@/lib/types";

const TABS = ["Overview", "Financials", "Earnings", "Dividends", "Analysts", "Ownership", "News"] as const;
type Tab = (typeof TABS)[number];
const sid = (t: Tab) => `sec-${t.toLowerCase()}`;

function StockPage() {
  const { user } = useAuth();
  const params = useSearchParams();
  const symbol = (params.get("s") ?? "AAPL").toUpperCase();
  const [tab, setTab] = useState<Tab>("Overview");
  const [data, setData] = useState<StockData | null>(null);
  const [candles, setCandles] = useState<CandlesResponse["candles"]>([]);
  const [error, setError] = useState("");
  const [pdfBusy, setPdfBusy] = useState(false);
  const canReport = !!user?.limits.reports;
  const scroller = useRef<HTMLDivElement>(null);

  // One page with every section; the sticky menu scrolls to a section and follows the scroll position.
  const go = (t: Tab) => {
    setTab(t);
    document.getElementById(sid(t))?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  useEffect(() => {
    const root = scroller.current;
    if (!root || !data) return;
    const io = new IntersectionObserver(
      (entries) => {
        const vis = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (vis[0]) setTab(TABS.find((t) => sid(t) === vis[0].target.id) ?? "Overview");
      },
      { root, rootMargin: "-120px 0px -60% 0px" },
    );
    TABS.forEach((t) => {
      const el = document.getElementById(sid(t));
      if (el) io.observe(el);
    });
    return () => io.disconnect();
  }, [data]);

  useEffect(() => {
    setData(null);
    setError("");
    setTab("Overview");
    api<StockData>(`/api/stock/${encodeURIComponent(symbol)}`).then(setData).catch((e) => setError(e.message));
    api<CandlesResponse>(`/api/market/candles/${encodeURIComponent(symbol)}?years=3`).then((r) => setCandles(r.candles)).catch(() => {});
  }, [symbol]);

  // Live quote in the header, refreshed every minute.
  useEffect(() => {
    const id = setInterval(() => {
      api<StockData["quote"][]>(`/api/market/quotes?symbols=${encodeURIComponent(symbol)}`)
        .then(([q]) => q && !q.error && setData((d) => (d ? { ...d, quote: q } : d)))
        .catch(() => {});
    }, 60_000);
    return () => clearInterval(id);
  }, [symbol]);

  const report = async () => {
    setPdfBusy(true);
    try {
      await download(`/api/stock/${encodeURIComponent(symbol)}/report.pdf`, `${symbol}-report.pdf`);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Download failed");
    } finally {
      setPdfBusy(false);
    }
  };

  if (error) {
    return (
      <div className="grid h-full place-items-center p-6 text-center">
        <div>
          <p className="text-lg font-semibold">{symbol}</p>
          <p className="mt-1 text-sm text-muted">{error}</p>
        </div>
      </div>
    );
  }
  if (!data) return <div className="grid h-full place-items-center text-sm text-muted">Loading {symbol}…</div>;

  const c = data.company;
  const q = data.quote;
  return (
    <div ref={scroller} className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl px-3 pb-6 pt-4 sm:px-6">
        {c.demo && (
          <div className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm text-amber-200">
            Demo data: prices and fundamentals are generated for demonstration and are not real.
          </div>
        )}
        <header className="flex flex-wrap items-end gap-x-6 gap-y-3">
          <div>
            <div className="flex items-baseline gap-2">
              <h1 className="text-2xl font-semibold">{c.name}</h1>
              <span className="text-lg text-muted">{c.symbol}</span>
            </div>
            <p className="text-sm text-muted">{[c.exchange, c.sector, c.industry !== c.sector ? c.industry : null].filter(Boolean).join(" · ")}</p>
          </div>
          <div className="tabular">
            <span className="text-2xl font-semibold">${fmt(q.price)}</span>
            <span className={`ml-2 ${tone(q.change)}`}>
              {q.change !== undefined && (q.change >= 0 ? "+" : "")}
              {fmt(q.change)} ({pct(q.change_pct)})
            </span>
            <div className="text-xs text-muted">As of {q.date} close</div>
          </div>
          <div className="ml-auto flex flex-wrap gap-2">
            <Link href={`/chart?s=${encodeURIComponent(symbol)}`} className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-text">
              Chart
            </Link>
            <Link href={`/alerts?symbol=${encodeURIComponent(symbol)}`} className="rounded-md border border-line px-3 py-1.5 text-sm text-muted hover:text-text">
              🔔 Alert
            </Link>
            <button
              onClick={report}
              disabled={!canReport || pdfBusy}
              title={canReport ? "Download a PDF report" : "PDF reports are available on the Premium plan"}
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {pdfBusy ? "Generating…" : "Download PDF report"}
              {!canReport && <span className="ml-1.5 rounded bg-amber-500/30 px-1 text-[10px] text-amber-200">PREMIUM</span>}
            </button>
          </div>
        </header>

        <nav className="sticky top-0 z-20 -mx-3 mt-4 flex gap-1 overflow-x-auto border-b border-line bg-bg/95 px-3 backdrop-blur sm:-mx-6 sm:px-6">
          <span className="hidden shrink-0 items-center pr-2 text-sm font-semibold md:flex">{c.symbol}</span>
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => go(t)}
              className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-sm ${tab === t ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}
            >
              {t}
            </button>
          ))}
          <span className={`tabular ml-auto hidden shrink-0 items-center text-sm md:flex ${tone(q.change)}`}>
            ${fmt(q.price)} ({pct(q.change_pct)})
          </span>
        </nav>

        <div className="mt-5 space-y-10">
          <section id={sid("Overview")} className="scroll-mt-14">
            <Overview d={data} candles={candles} />
          </section>
          {(
            [
              ["Financials", <Financials key="f" c={c} />],
              ["Earnings", <Earnings key="e" c={c} />],
              ["Dividends", <Dividends key="d" c={c} />],
              ["Analysts", <Analysts key="a" c={c} price={q.price ?? 0} />],
              ["Ownership", <Ownership key="o" c={c} />],
              ["News", <News key="n" c={c} />],
            ] as [Tab, React.ReactNode][]
          ).map(([t, node]) => (
            <section key={t} id={sid(t)} className="scroll-mt-14">
              <h2 className="mb-3 text-lg font-semibold">{t}</h2>
              {node}
            </section>
          ))}
        </div>
        <p className="mt-6 text-xs text-muted">For educational purposes only. Not financial advice.</p>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AppShell>
      <Suspense fallback={null}>
        <StockPage />
      </Suspense>
    </AppShell>
  );
}
