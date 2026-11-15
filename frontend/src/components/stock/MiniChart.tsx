"use client";

import { AreaSeries, ColorType, createChart, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { Candle } from "@/lib/types";

const RANGES = { "1M": 21, "6M": 126, "1Y": 252, "3Y": 756 } as const;
export type Range = keyof typeof RANGES;

export default function MiniChart({ candles, range }: { candles: Candle[]; range: Range }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!el.current) return;
    const c = createChart(el.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8b95a7", fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: "#1b2231" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      handleScroll: false,
      handleScale: false,
    });
    series.current = c.addSeries(AreaSeries, { lineWidth: 2, priceLineVisible: false });
    chart.current = c;
    return () => c.remove();
  }, []);

  useEffect(() => {
    const data = candles.slice(-RANGES[range]);
    if (!data.length || !series.current) return;
    const up = data[data.length - 1].close >= data[0].close;
    series.current.applyOptions({
      lineColor: up ? "#22c55e" : "#ef4444",
      topColor: up ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)",
      bottomColor: "rgba(0,0,0,0)",
    });
    series.current.setData(data.map((c) => ({ time: c.time as Time, value: c.close })));
    chart.current?.timeScale().fitContent();
  }, [candles, range]);

  return <div ref={el} className="h-56 w-full" />;
}
