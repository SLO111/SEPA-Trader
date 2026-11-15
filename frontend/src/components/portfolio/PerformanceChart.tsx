"use client";

import { ColorType, LineSeries, createChart, type IChartApi, type ISeriesApi, type Time } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { Performance } from "@/lib/types";

export default function PerformanceChart({ data }: { data: Performance }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const pf = useRef<ISeriesApi<"Line"> | null>(null);
  const bm = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!el.current) return;
    const c = createChart(el.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8b95a7", fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: "#1b2231" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      localization: { priceFormatter: (v: number) => `${v.toFixed(1)}%` },
    });
    bm.current = c.addSeries(LineSeries, { color: "#64748b", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: true, title: "S&P 500" });
    pf.current = c.addSeries(LineSeries, { color: "#3b82f6", lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: "Portfolio" });
    chart.current = c;
    return () => c.remove();
  }, []);

  useEffect(() => {
    pf.current?.setData(data.series.map((p) => ({ time: p.time as Time, value: p.portfolio })));
    bm.current?.setData(data.series.filter((p) => p.benchmark !== undefined).map((p) => ({ time: p.time as Time, value: p.benchmark! })));
    chart.current?.timeScale().fitContent();
  }, [data]);

  return <div ref={el} className="h-64 w-full" />;
}
