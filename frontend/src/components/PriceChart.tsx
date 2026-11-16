"use client";

import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  LineType,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useEffect, useMemo, useRef } from "react";
import { chartColors } from "@/lib/theme";
import type { Candle, StrategyOutput } from "@/lib/types";

// fitKey: the view is re-fitted only when it changes (new symbol/interval), not on live refreshes.
// onHover: the time of the candle under the crosshair (null when the mouse leaves the chart).
type Props = { candles: Candle[]; overlays: StrategyOutput[]; fitKey?: string; onHover?: (time: string | number | null) => void };

function theme() {
  const c = chartColors();
  return {
    layout: { background: { type: ColorType.Solid, color: c.bg }, textColor: c.text, fontSize: 11 },
    grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
    rightPriceScale: { borderColor: c.border },
    timeScale: { borderColor: c.border, rightOffset: 6 },
    crosshair: { mode: CrosshairMode.Normal },
  };
}

export default function PriceChart({ candles, overlays, fitKey = "", onHover }: Props) {
  const hoverRef = useRef(onHover);
  hoverRef.current = onHover;
  const fitted = useRef<string | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const overlayRefs = useRef<ISeriesApi<"Line" | "Histogram">[]>([]);
  const markersRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  // Indicators can colour the candles (e.g. green above a trailing stop, red below)
  const barColors = useMemo(() => {
    const m = new Map<string | number, string>();
    for (const o of overlays) for (const b of o.bar_colors ?? []) m.set(b.time, b.color);
    return m;
  }, [overlays]);

  // Create the chart once
  useEffect(() => {
    if (!container.current) return;
    const chart = createChart(container.current, { ...theme(), autoSize: true });
    const retheme = () => chart.applyOptions(theme());
    window.addEventListener("theme-changed", retheme);
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    const volume = chart.addSeries(HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    candle.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.2 } });

    chartRef.current = chart;
    candleRef.current = candle;
    volumeRef.current = volume;
    markersRef.current = createSeriesMarkers(candle, []);
    const onMove = (p: { time?: Time }) => hoverRef.current?.(p.time === undefined ? null : (p.time as string | number));
    chart.subscribeCrosshairMove(onMove);
    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      window.removeEventListener("theme-changed", retheme);
      chart.remove();
      chartRef.current = null;
      overlayRefs.current = [];
      priceLinesRef.current = [];
    };
  }, []);

  // Price data
  useEffect(() => {
    if (!candleRef.current || !volumeRef.current) return;
    // Pre-market and after-hours candles are drawn faded, like on TradingView.
    const color = (c: Candle) => {
      const ext = c.session === "pre" || c.session === "post";
      const painted = barColors.get(c.time);
      if (painted && !ext) return painted;
      const upBar = c.close >= c.open;
      return ext ? (upBar ? "#22c55e66" : "#ef444466") : upBar ? "#22c55e" : "#ef4444";
    };
    candleRef.current.setData(
      candles.map((c) => {
        const col = color(c);
        return { time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close, color: col, wickColor: col, borderColor: col };
      }),
    );
    volumeRef.current.setData(
      candles.map((c) => ({ time: c.time as Time, value: c.volume, color: c.close >= c.open ? "#22c55e40" : "#ef444440" })),
    );
    if (fitted.current !== fitKey) {
      chartRef.current?.timeScale().fitContent();
      fitted.current = fitKey;
    }
  }, [candles, fitKey, barColors]);

  // Strategy overlays
  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleRef.current;
    if (!chart || !candle) return;

    overlayRefs.current.forEach((s) => chart.removeSeries(s));
    overlayRefs.current = [];
    // remove leftover empty lower panes
    while (chart.panes().length > 1) chart.removePane(chart.panes().length - 1);

    // each indicator with a lower part gets its own pane (RSI and the RS line don't share a scale)
    let panes = 0;
    for (const o of overlays) {
      const lower = o.lines.some((l) => l.pane === "lower") || o.histograms.some((h) => h.pane === "lower");
      const idx = lower ? ++panes : 0;
      const paneOf = (p: string) => (p === "lower" ? idx : 0);
      for (const h of o.histograms) {
        const s = chart.addSeries(HistogramSeries, { lastValueVisible: false, priceLineVisible: false }, paneOf(h.pane));
        s.setData(h.data.map((d) => ({ time: d.time as Time, value: d.value ?? 0, color: d.color })));
        overlayRefs.current.push(s);
      }
      for (const l of o.lines) {
        const s = chart.addSeries(
          LineSeries,
          {
            color: l.color, lineWidth: l.width as 1 | 2 | 3 | 4, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false, title: "",
            lineType: l.step ? LineType.WithSteps : LineType.Simple, lineStyle: l.style === "dashed" ? LineStyle.Dashed : l.style === "dotted" ? LineStyle.Dotted : LineStyle.Solid,
          },
          paneOf(l.pane),
        );
        s.setData(l.data.map((d) => (d.value === null || d.value === undefined ? { time: d.time as Time } : d.color ? { time: d.time as Time, value: d.value, color: d.color } : { time: d.time as Time, value: d.value })));
        overlayRefs.current.push(s);
      }
    }
    // main chart keeps most of the room; each lower pane gets a fair share
    chart.panes()[0]?.setStretchFactor(panes ? Math.max(2, 4 - panes) : 1);
    for (let i = 1; i <= panes; i++) chart.panes()[i]?.setStretchFactor(1);

    const markers: SeriesMarker<Time>[] = overlays
      .flatMap((o) => o.markers)
      .map((m) => ({ time: m.time as Time, position: m.position, shape: m.shape, color: m.color, text: m.text }))
      .sort((a, b) => String(a.time).localeCompare(String(b.time)));
    markersRef.current?.setMarkers(markers);

    priceLinesRef.current.forEach((pl) => candle.removePriceLine(pl));
    priceLinesRef.current = overlays.flatMap((o) =>
      o.levels.map((lv) => candle.createPriceLine({ price: lv.price, color: lv.color, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: lv.title })),
    );
  }, [overlays]);

  return <div ref={container} className="h-full w-full" />;
}
