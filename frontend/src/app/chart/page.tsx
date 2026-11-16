"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import ChartLegend from "@/components/chart/ChartLegend";
import IndicatorPicker from "@/components/chart/IndicatorPicker";
import SymbolInfoPanel from "@/components/chart/SymbolInfoPanel";
import SepaStrip from "@/components/SepaStrip";
import WatchlistPanel from "@/components/WatchlistPanel";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ActiveStrategy, CandlesResponse, StrategyDef, StrategyOutput, SymbolInfo } from "@/lib/types";

const PriceChart = dynamic(() => import("@/components/PriceChart"), { ssr: false });

const INTERVALS = [
  { id: "5m", label: "5m" },
  { id: "15m", label: "15m" },
  { id: "1h", label: "1h" },
  { id: "1d", label: "D" },
  { id: "1wk", label: "W" },
  { id: "1mo", label: "M" },
];
const STORE_KEY = "sepa_chart_indicators_v2";
const uid = () => Math.random().toString(36).slice(2, 10);

function loadActive(): ActiveStrategy[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return [{ uid: uid(), id: "ma_ribbon", params: {} }];
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
  const [picker, setPicker] = useState(false);
  const [panel, setPanel] = useState<"none" | "watch" | "info">("none");
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);
  const loaded = useRef(false); // don't overwrite saved indicators with the empty initial state
  const max = user?.limits.max_strategies_on_chart ?? 3;

  useEffect(() => {
    api<StrategyDef[]>("/api/strategies")
      .then((ds) => {
        setDefs(ds);
        const allowed = new Set(ds.filter((d) => !d.requires || user?.limits[d.requires as keyof typeof user.limits]).map((d) => d.id));
        setActive(loadActive().filter((a) => allowed.has(a.id)).slice(0, max));
        loaded.current = true;
      })
      .catch(() => {});
  }, [max, user]);

  // Live data: reload prices (and indicators) every minute.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  // Symbol details (side panel + extended-hours price in the header), refreshed every minute.
  const [info, setInfo] = useState<SymbolInfo | null>(null);
  const [infoError, setInfoError] = useState("");
  useEffect(() => {
    setInfoError("");
    api<SymbolInfo>(`/api/market/info/${encodeURIComponent(symbol)}`)
      .then(setInfo)
      .catch((e) => setInfoError(e.message));
  }, [symbol, tick]);

  useEffect(() => {
    if (tick === 0) setError("");
    api<CandlesResponse>(`/api/market/candles/${encodeURIComponent(symbol)}?interval=${interval}`)
      .then(setData)
      .catch((e) => tick === 0 && setError(e.message));
  }, [symbol, interval, tick]);

  useEffect(() => {
    if (loaded.current) {
      try {
        localStorage.setItem(STORE_KEY, JSON.stringify(active));
      } catch {
        /* ignore */
      }
    }
    clearTimeout(debounce.current);
    const visible = active.filter((a) => !a.hidden);
    if (!visible.length) return setOverlays([]);
    debounce.current = setTimeout(() => {
      post<{ results: StrategyOutput[] }>("/api/strategies/run", { symbol, interval, strategies: visible.map(({ id, params }) => ({ id, params })) })
        .then((r) => setOverlays(r.results))
        .catch((e) => setError(e.message));
    }, 250);
  }, [active, symbol, interval, tick]);

  const add = useCallback(
    (d: StrategyDef) => {
      setActive((a) => {
        const params = Object.fromEntries(d.params.map((p) => [p.key, p.default]));
        // each extra copy of an indicator gets the next color, so they are easy to tell apart
        const colorParam = d.params.find((p) => p.key === "color");
        if (colorParam) params.color = a.filter((x) => x.id === d.id).length % (colorParam.max + 1);
        return [...a, { uid: uid(), id: d.id, params }];
      });
      setPicker(false);
    },
    [],
  );

  // OHLC legend: the candle under the crosshair, or the last one.
  const [hover, setHover] = useState<string | number | null>(null);
  const candleIndex = useMemo(() => new Map((data?.candles ?? []).map((c, i) => [c.time, i])), [data]);
  const lineMaps = useMemo(
    () => overlays.map((o) => o.lines.map((l) => ({ color: l.color, points: new Map(l.data.map((d) => [d.time, d.value])) }))),
    [overlays],
  );
  const ohlc = useMemo(() => {
    const cs = data?.candles ?? [];
    if (!cs.length) return null;
    const i = hover !== null && candleIndex.has(hover) ? candleIndex.get(hover)! : cs.length - 1;
    const c = cs[i];
    const prev = i > 0 ? cs[i - 1].close : c.open;
    return { c, chg: c.close - prev, pct: prev ? (c.close / prev - 1) * 100 : 0 };
  }, [data, hover, candleIndex]);
  const values = useMemo(() => {
    const out: Record<string, string> = {};
    const visible = active.filter((a) => !a.hidden);
    const t = ohlc?.c.time;
    if (t === undefined) return out;
    visible.forEach((a, i) => {
      const vs = (lineMaps[i] ?? []).map((l) => l.points.get(t)).filter((v): v is number => v !== undefined);
      if (vs.length) out[a.uid] = vs.map((v) => (Math.abs(v) >= 1000 ? v.toFixed(0) : v.toFixed(2))).join("  ");
    });
    return out;
  }, [active, lineMaps, ohlc]);
  const vol = (v: number) => (v >= 1e9 ? `${(v / 1e9).toFixed(2)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(2)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(1)}K` : String(v));
  const ohlcHeader = ohlc && (
    <div className={`tabular pointer-events-none inline-flex flex-wrap items-baseline gap-x-2 rounded bg-bg/70 px-2 py-0.5 text-xs backdrop-blur ${ohlc.c.close >= ohlc.c.open ? "text-up" : "text-down"}`}>
      {(["open", "high", "low", "close"] as const).map((k) => (
        <span key={k}>
          <span className="text-muted">{k[0].toUpperCase()}</span>
          {ohlc.c[k].toFixed(2)}
        </span>
      ))}
      <span className={ohlc.chg >= 0 ? "text-up" : "text-down"}>
        {ohlc.chg >= 0 ? "+" : ""}
        {ohlc.chg.toFixed(2)} ({ohlc.chg >= 0 ? "+" : ""}
        {ohlc.pct.toFixed(2)}%)
      </span>
      <span className="text-muted">Vol {vol(ohlc.c.volume)}</span>
      {ohlc.c.session && ohlc.c.session !== "regular" && <span className="text-violet-300">{ohlc.c.session === "pre" ? "Pre-market" : "After hours"}</span>}
    </div>
  );

  const q = data?.quote;
  const up = (q?.change ?? 0) >= 0;
  const intraday = ["5m", "15m", "1h"].includes(interval);

  return (
    <div className="relative flex h-full">
      <aside className={`${panel === "watch" ? "absolute inset-y-0 left-0 z-30 flex" : "hidden"} w-64 shrink-0 flex-col border-r border-line bg-panel lg:static lg:flex`}>
        <WatchlistPanel
          selected={symbol}
          onSelect={(s) => {
            setSymbol(s);
            setPanel("none");
          }}
        />
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-3 py-1.5">
          <button onClick={() => setPanel(panel === "watch" ? "none" : "watch")} className="rounded border border-line px-2 py-1 text-xs text-muted lg:hidden">
            Lists
          </button>
          <Link href={`/stock?s=${encodeURIComponent(symbol)}`} className="flex items-baseline gap-2 hover:text-accent" title="Open the full company overview">
            <span className="text-lg font-semibold">{data?.symbol ?? symbol}</span>
            <span className="hidden max-w-[220px] truncate text-sm text-muted sm:inline">{data?.name}</span>
          </Link>
          {q?.price !== undefined && (
            <span className="tabular flex items-baseline gap-2">
              <span className="font-semibold">{q.price.toFixed(2)}</span>
              <span className={`text-sm ${up ? "text-up" : "text-down"}`}>
                {up ? "+" : ""}
                {q.change?.toFixed(2)} ({up ? "+" : ""}
                {q.change_pct?.toFixed(2)}%)
              </span>
            </span>
          )}
          {info?.symbol === symbol && info.extended && (
            <span className="tabular flex items-baseline gap-1.5 rounded bg-violet-500/10 px-2 py-0.5 text-sm" title={`Last trade ${info.extended.time}`}>
              <span className="text-[11px] font-medium text-violet-300">{info.extended.session === "pre_market" ? "Pre-market" : "Post-market"}</span>
              <span className="font-semibold">{info.extended.price.toFixed(2)}</span>
              <span className={info.extended.change >= 0 ? "text-up" : "text-down"}>
                {info.extended.change >= 0 ? "+" : ""}
                {info.extended.change.toFixed(2)} ({info.extended.change >= 0 ? "+" : ""}
                {info.extended.change_pct.toFixed(2)}%)
              </span>
            </span>
          )}
          <div className="mx-1 h-5 w-px bg-line" />
          <div className="flex items-center gap-0.5">
            {INTERVALS.map((i) => (
              <button
                key={i.id}
                onClick={() => setIntervalId(i.id)}
                className={`rounded px-2 py-1 text-xs ${interval === i.id ? "bg-panel-2 text-text" : "text-muted hover:bg-panel-2 hover:text-text"}`}
              >
                {i.label}
              </button>
            ))}
          </div>
          <div className="mx-1 h-5 w-px bg-line" />
          <button onClick={() => setPicker(true)} className="flex items-center gap-1.5 rounded px-2 py-1 text-sm text-muted hover:bg-panel-2 hover:text-text">
            <span className="text-base leading-none">ƒx</span> Indicators
          </button>
          <Link href={`/alerts?symbol=${encodeURIComponent(symbol)}`} className="rounded px-2 py-1 text-sm text-muted hover:bg-panel-2 hover:text-text">
            🔔 Alert
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <Link href={`/stock?s=${encodeURIComponent(symbol)}`} className="hidden rounded border border-line px-2 py-1 text-xs text-muted hover:border-accent hover:text-text md:inline">
              Overview ↗
            </Link>
            <button onClick={() => setPanel(panel === "info" ? "none" : "info")} className="rounded border border-line px-2 py-1 text-xs text-muted xl:hidden">
              Details
            </button>
          </div>
        </div>
        <SepaStrip symbol={symbol} />
        {error && <div className="bg-down/10 px-4 py-2 text-sm text-down">{error}</div>}
        <div className="relative min-h-0 flex-1">
          <ChartLegend active={active} defs={defs} onChange={setActive} header={ohlcHeader} values={values} />
          {data && <PriceChart candles={data.candles} overlays={overlays} fitKey={`${symbol}:${interval}`} onHover={setHover} />}
        </div>
        <div className="flex flex-wrap gap-x-3 border-t border-line px-3 py-1 text-[11px] text-muted">
          {data?.live_at && <span className="text-up">● Live · updated {data.live_at}</span>}
          {intraday && <span>Faded candles: pre-market (4:00–9:30) and after-hours (16:00–20:00), New York time</span>}
          {data && data.delay_minutes > 0 && <span>Data delayed by {data.delay_minutes} min</span>}
          <span>For educational purposes only. Not financial advice.</span>
        </div>
      </section>

      <aside className={`${panel === "info" ? "absolute inset-y-0 right-0 z-30 flex" : "hidden"} w-80 shrink-0 flex-col border-l border-line bg-panel xl:static xl:flex`}>
        <SymbolInfoPanel symbol={symbol} info={info} error={infoError} />
      </aside>

      {picker && <IndicatorPicker defs={defs} features={user?.limits ?? {}} activeCount={active.length} max={max} onAdd={add} onClose={() => setPicker(false)} />}
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
