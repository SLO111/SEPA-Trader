"use client";

import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { Candle, StrategyOutput } from "@/lib/types";

// fitKey: the view is re-fitted only when it changes (new symbol/interval), not on live refreshes.
type Props = { candles: Candle[]; overlays: StrategyOutput[]; fitKey?: string };

const THEME = {
  layout: { background: { type: ColorType.Solid, color: "#0b0e14" }, textColor: "#8b95a7", fontSize: 11 },
  grid: { vertLines: { color: "#161c28" }, horzLines: { color: "#161c28" } },
  rightPriceScale: { borderColor: "#232c3d" },
  timeScale: { borderColor: "#232c3d", rightOffset: 6 },
  crosshair: { mode: CrosshairMode.Normal },
};

export default function PriceChart({ candles, overlays, fitKey = "" }: Props) {
  const fitted = useRef<string | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const overlayRefs = useRef<ISeriesApi<"Line" | "Histogram">[]>([]);
  const markersRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);

  // Create the chart once
  useEffect(() => {
    if (!container.current) return;
    const chart = createChart(container.current, { ...THEME, autoSize: true });
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
    return () => {
      chart.remove();
      chartRef.current = null;
      overlayRefs.current = [];
      priceLinesRef.current = [];
    };
  }, []);

  // Price data
  useEffect(() => {
    if (!candleRef.current || !volumeRef.current) return;
    candleRef.current.setData(candles.map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close })));
    volumeRef.current.setData(
      candles.map((c) => ({ time: c.time as Time, value: c.volume, color: c.close >= c.open ? "#22c55e40" : "#ef444440" })),
    );
    if (fitted.current !== fitKey) {
      chartRef.current?.timeScale().fitContent();
      fitted.current = fitKey;
    }
  }, [candles, fitKey]);

  // Strategy overlays
  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleRef.current;
    if (!chart || !candle) return;

    overlayRefs.current.forEach((s) => chart.removeSeries(s));
    overlayRefs.current = [];
    // remove leftover empty lower panes
    while (chart.panes().length > 1) chart.removePane(chart.panes().length - 1);

    const hasLower = overlays.some((o) => o.lines.some((l) => l.pane === "lower") || o.histograms.some((h) => h.pane === "lower"));
    const paneOf = (p: string) => (p === "lower" && hasLower ? 1 : 0);

    for (const o of overlays) {
      for (const h of o.histograms) {
        const s = chart.addSeries(HistogramSeries, { lastValueVisible: false, priceLineVisible: false }, paneOf(h.pane));
        s.setData(h.data.map((d) => ({ time: d.time as Time, value: d.value, color: d.color })));
        overlayRefs.current.push(s);
      }
      for (const l of o.lines) {
        const s = chart.addSeries(
          LineSeries,
          { color: l.color, lineWidth: l.width as 1 | 2 | 3 | 4, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false, title: "" },
          paneOf(l.pane),
        );
        s.setData(l.data.map((d) => ({ time: d.time as Time, value: d.value })));
        overlayRefs.current.push(s);
      }
    }
    if (hasLower) chart.panes()[1]?.setHeight(150);

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
