"use client";

import { useEffect, useRef, useState } from "react";
import TradingViewWidget from "@/components/TradingViewWidget";

const SOURCES = [
  { id: "SPX500", label: "S&P 500" },
  { id: "NASDAQ100", label: "Nasdaq 100" },
  { id: "DJDJI", label: "Dow Jones" },
  { id: "AllUSA", label: "All US stocks" },
];

/** S&P 500 heatmap: block size = market cap, color = today's change, grouped by sector (TradingView, loaded in the browser). */
export default function Heatmap() {
  const [source, setSource] = useState("SPX500");
  // fill the screen: from the top of the heatmap to the bottom of the window (at least 520px)
  const box = useRef<HTMLDivElement>(null);
  const [h, setH] = useState(640);
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const fit = () => {
      clearTimeout(t);
      t = setTimeout(() => {
        const top = box.current?.getBoundingClientRect().top ?? 200;
        setH(Math.max(520, Math.round(window.innerHeight - top - 16)));
      }, 150);
    };
    fit();
    window.addEventListener("resize", fit);
    return () => {
      window.removeEventListener("resize", fit);
      clearTimeout(t);
    };
  }, []);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1">
        {SOURCES.map((s) => (
          <button
            key={s.id}
            onClick={() => setSource(s.id)}
            className={`rounded px-3 py-1 text-sm ${source === s.id ? "bg-accent text-white" : "text-muted hover:bg-panel-2 hover:text-text"}`}
          >
            {s.label}
          </button>
        ))}
        <span className="ml-auto hidden text-xs text-muted sm:inline">Size: market cap · Color: today&apos;s change · Click a sector to zoom</span>
      </div>
      <div ref={box}>
      <TradingViewWidget
        script="embed-widget-stock-heatmap.js"
        height={h}
        config={{
          dataSource: source,
          blockSize: "market_cap_basic",
          blockColor: "change",
          grouping: "sector",
          exchanges: [],
          locale: "en",
          symbolUrl: "",
          colorTheme: "dark",
          hasTopBar: false,
          isDataSetEnabled: false,
          isZoomEnabled: true,
          hasSymbolTooltip: true,
          isMonoSize: false,
          width: "100%",
          height: "100%",
        }}
      />
      </div>
    </div>
  );
}
