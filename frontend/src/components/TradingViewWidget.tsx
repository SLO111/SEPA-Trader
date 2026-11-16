"use client";

import { memo, useEffect, useRef } from "react";

/**
 * Embeds a free TradingView widget. The script and its data load in the visitor's browser, straight
 * from TradingView, only when this component is on screen: no load on our server or data provider.
 */
function TradingViewWidget({ script, config, height }: { script: string; config: Record<string, unknown>; height: number | string }) {
  const box = useRef<HTMLDivElement>(null);
  const key = JSON.stringify(config);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    el.innerHTML = '<div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>';
    const s = document.createElement("script");
    s.src = `https://s3.tradingview.com/external-embedding/${script}`;
    s.async = true;
    s.type = "text/javascript";
    s.innerHTML = key;
    el.appendChild(s);
    return () => {
      el.innerHTML = "";
    };
  }, [script, key]);

  return <div ref={box} className="tradingview-widget-container w-full overflow-hidden rounded-lg" style={{ height }} />;
}

export default memo(TradingViewWidget);
