"use client";

import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import SepaStrip from "@/components/SepaStrip";
import StrategyPanel from "@/components/StrategyPanel";
import WatchlistPanel from "@/components/WatchlistPanel";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ActiveStrategy, CandlesResponse, StrategyDef, StrategyOutput } from "@/lib/types";

const PriceChart = dynamic(() => import("@/components/PriceChart"), { ssr: false });

const INTERVALS = [
  { id: "1d", label: "1Z" },
  { id: "1wk", label: "1S" },
  { id: "1mo", label: "1L" },
];
const STORE_KEY = "sepa_active_strategies";

function loadActive(): ActiveStrategy[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return [{ id: "sepa_mas", params: {} }];
}

function ChartWorkspace() {
  const { user } = useAuth();
  const params = useSearchParams();
  const [symbol, setSymbol] = useState((params.get("s") ?? "AAPL").toUpperCase());
  const [interval, setIntervalId] = useState("1d");
  const [data, setData] = useState<CandlesResponse | null>(null);
  const [defs, setDefs] = useState<StrategyDef[]>([]);
  const [active, setActive] = useState<ActiveStrategy[]>([]);
  const [overlays, setOverlays] = useState<StrategyOutput[]>([]);
  const [error, setError] = useState("");
  const [panel, setPanel] = useState<"none" | "watch" | "strat">("none");
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);
  const max = user?.limits.max_strategies_on_chart ?? 3;

  useEffect(() => {
    api<StrategyDef[]>("/api/strategies")
      .then((ds) => {
        setDefs(ds);
        const allowed = new Set(ds.filter((d) => !d.requires || user?.limits[d.requires as keyof typeof user.limits]).map((d) => d.id));
        setActive(loadActive().filter((a) => allowed.has(a.id)).slice(0, max));
      })
      .catch(() => {});
  }, [max, user]);

  useEffect(() => {
    setError("");
    api<CandlesResponse>(`/api/market/candles/${encodeURIComponent(symbol)}?interval=${interval}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [symbol, interval]);

  useEffect(() => {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(active));
    } catch {
      /* ignore */
    }
    clearTimeout(debounce.current);
    if (!active.length) return setOverlays([]);
    debounce.current = setTimeout(() => {
      post<Record<string, StrategyOutput>>("/api/strategies/run", { symbol, interval, strategies: active })
        .then((r) => setOverlays(active.map((a) => r[a.id]).filter(Boolean)))
        .catch((e) => setError(e.message));
    }, 250);
  }, [active, symbol, interval]);

  const q = data?.quote;
  const up = (q?.change ?? 0) >= 0;

  return (
    <div className="relative flex h-full">
      <aside className={`${panel === "watch" ? "absolute inset-y-0 left-0 z-30 flex" : "hidden"} w-72 shrink-0 flex-col border-r border-line bg-panel lg:static lg:flex`}>
        <WatchlistPanel
          selected={symbol}
          onSelect={(s) => {
            setSymbol(s);
            setPanel("none");
          }}
        />
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-4 py-2">
          <button onClick={() => setPanel(panel === "watch" ? "none" : "watch")} className="rounded border border-line px-2 py-1 text-xs text-muted lg:hidden">
            Liste
          </button>
          <div className="flex items-baseline gap-2">
            <h1 className="text-lg font-semibold">{data?.symbol ?? symbol}</h1>
            <span className="hidden text-sm text-muted sm:inline">{data?.name}</span>
            <span className="text-xs text-muted">{data?.exchange}</span>
          </div>
          {q?.price !== undefined && (
            <div className="tabular flex items-baseline gap-2">
              <span className="text-lg font-semibold">{q.price.toFixed(2)}</span>
              <span className={up ? "text-up" : "text-down"}>
                {up ? "+" : ""}
                {q.change?.toFixed(2)} ({up ? "+" : ""}
                {q.change_pct?.toFixed(2)}%)
              </span>
            </div>
          )}
          <div className="ml-auto flex items-center gap-1">
            {INTERVALS.map((i) => (
              <button
                key={i.id}
                onClick={() => setIntervalId(i.id)}
                className={`rounded px-2.5 py-1 text-xs ${interval === i.id ? "bg-accent text-white" : "text-muted hover:bg-panel-2 hover:text-text"}`}
              >
                {i.label}
              </button>
            ))}
            <button onClick={() => setPanel(panel === "strat" ? "none" : "strat")} className="ml-2 rounded border border-line px-2 py-1 text-xs text-muted xl:hidden">
              Strategii
            </button>
          </div>
        </div>
        <SepaStrip symbol={symbol} />
        {error && <div className="bg-down/10 px-4 py-2 text-sm text-down">{error}</div>}
        <div className="min-h-0 flex-1">{data && <PriceChart candles={data.candles} overlays={overlays} />}</div>
        <div className="border-t border-line px-4 py-1.5 text-[11px] text-muted">
          {data && data.delay_minutes > 0 ? `Date cu întârziere de ${data.delay_minutes} min · ` : ""}
          Informațiile au scop educațional și nu reprezintă sfat financiar.
        </div>
      </section>

      <aside className={`${panel === "strat" ? "absolute inset-y-0 right-0 z-30 flex" : "hidden"} w-80 shrink-0 flex-col border-l border-line bg-panel xl:static xl:flex`}>
        <StrategyPanel defs={defs} active={active} onChange={setActive} max={max} features={user?.limits ?? {}} />
      </aside>
    </div>
  );
}

export default function ChartPage() {
  return (
    <AppShell>
      <Suspense fallback={null}>
        <ChartWorkspace />
      </Suspense>
    </AppShell>
  );
}
