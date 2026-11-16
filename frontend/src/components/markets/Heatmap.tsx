"use client";

import { useState } from "react";
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
        <span className="ml-auto text-xs text-muted">Size: market cap · Color: today&apos;s change · Click a sector to zoom</span>
      </div>
      <TradingViewWidget
        script="embed-widget-stock-heatmap.js"
        height={640}
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
  );
}
