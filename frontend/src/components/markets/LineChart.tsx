"use client";

import { ColorType, LineSeries, createChart, type Time } from "lightweight-charts";
import { useEffect, useRef } from "react";

type Series = { name: string; color: string; data: { time: string; value: number }[]; width?: 1 | 2 | 3 };

/** Small multi-line chart used for the Fear & Greed history and Fed rate history. */
export default function LineChart({ series, height = 220, suffix = "", range }: { series: Series[]; height?: number; suffix?: string; range?: [number, number] }) {
  const el = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!el.current) return;
    const c = createChart(el.current, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8b95a7", fontSize: 11 },
      grid: { vertLines: { visible: false }, horzLines: { color: "#1b2231" } },
      rightPriceScale: { borderVisible: false, scaleMargins: range ? { top: 0.04, bottom: 0.04 } : { top: 0.1, bottom: 0.1 } },
      timeScale: { borderVisible: false },
      localization: { priceFormatter: (v: number) => `${v.toFixed(suffix === "%" ? 2 : 0)}${suffix}` },
    });
    for (const s of series) {
      const line = c.addSeries(LineSeries, {
        color: s.color,
        lineWidth: s.width ?? 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: s.name,
        autoscaleInfoProvider: range ? () => ({ priceRange: { minValue: range[0], maxValue: range[1] } }) : undefined,
      });
      line.setData(s.data.map((p) => ({ time: p.time as Time, value: p.value })));
    }
    c.timeScale().fitContent();
    return () => c.remove();
  }, [series, suffix, range]);

  return <div ref={el} style={{ height }} className="w-full" />;
}
