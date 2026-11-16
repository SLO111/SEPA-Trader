"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Gauge from "./Gauge";

type Item = { name: string; value: number | null; action: "Buy" | "Sell" | "Neutral" };
type Block = { label: string; score: number; buy: number; sell: number; neutral: number; items?: Item[] };
type Tech = { summary: Block; oscillators: Block & { items: Item[] }; moving_averages: Block & { items: Item[] }; as_of: string };

const INTERVALS = [
  ["1h", "1 hour"],
  ["1d", "1 day"],
  ["1wk", "1 week"],
] as const;
const ACTION = { Buy: "text-blue-400", Sell: "text-red-400", Neutral: "text-muted" };

function Counts({ b }: { b: Block }) {
  return (
    <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
      <div><div className="text-muted">Sell</div><div className="tabular text-base font-semibold text-red-400">{b.sell}</div></div>
      <div><div className="text-muted">Neutral</div><div className="tabular text-base font-semibold">{b.neutral}</div></div>
      <div><div className="text-muted">Buy</div><div className="tabular text-base font-semibold text-blue-400">{b.buy}</div></div>
    </div>
  );
}

function Table({ title, items }: { title: string; items: Item[] }) {
  return (
    <div>
      <div className="mb-1 text-[11px] uppercase tracking-wide text-muted">{title}</div>
      <table className="w-full text-sm">
        <tbody>
          {items.map((i) => (
            <tr key={i.name} className="border-t border-line">
              <td className="py-1.5 pr-2 text-muted">{i.name}</td>
              <td className="tabular py-1.5 text-right">{i.value === null ? "—" : i.value.toLocaleString("en-US", { maximumFractionDigits: 2 })}</td>
              <td className={`w-16 py-1.5 text-right text-xs font-medium ${ACTION[i.action]}`}>{i.value === null ? "" : i.action}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Technical rating: oscillators, summary and moving averages as three gauges, with every indicator on demand. */
export default function Technicals({ symbol }: { symbol: string }) {
  const [iv, setIv] = useState<string>("1d");
  const [data, setData] = useState<Tech | null>(null);
  const [error, setError] = useState("");
  const [details, setDetails] = useState(false);

  useEffect(() => {
    setError("");
    setData(null);
    api<Tech>(`/api/stock/${encodeURIComponent(symbol)}/technicals?interval=${iv}`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [symbol, iv]);

  const val = (b: Block) => (b.score + 1) / 2;
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-center gap-1">
        {INTERVALS.map(([id, label]) => (
          <button key={id} onClick={() => setIv(id)} className={`rounded-md px-3 py-1 text-sm ${iv === id ? "bg-panel-2 font-medium text-text" : "text-muted hover:text-text"}`}>
            {label}
          </button>
        ))}
      </div>
      {error && <p className="text-center text-sm text-muted">{error}</p>}
      {!data && !error && <div className="h-64 animate-pulse rounded-lg bg-panel-2/40" />}
      {data && (
        <>
          <div className="grid items-end gap-6 sm:grid-cols-3">
            <div className="order-2 sm:order-1">
              <div className="mb-1 text-center text-sm text-muted">Oscillators</div>
              <Gauge size="sm" value={val(data.oscillators)} label={data.oscillators.label} />
              <Counts b={data.oscillators} />
            </div>
            <div className="order-1 sm:order-2">
              <div className="mb-1 text-center text-sm font-medium">Summary</div>
              <Gauge value={val(data.summary)} label={data.summary.label} />
              <Counts b={data.summary} />
            </div>
            <div className="order-3">
              <div className="mb-1 text-center text-sm text-muted">Moving averages</div>
              <Gauge size="sm" value={val(data.moving_averages)} label={data.moving_averages.label} />
              <Counts b={data.moving_averages} />
            </div>
          </div>
          <div className="mt-4 text-center">
            <button onClick={() => setDetails((d) => !d)} className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:text-text">
              {details ? "Hide indicators ▲" : "Show all 26 indicators ▼"}
            </button>
          </div>
          {details && (
            <div className="mt-4 grid gap-6 md:grid-cols-2">
              <Table title="Oscillators" items={data.oscillators.items} />
              <Table title="Moving averages" items={data.moving_averages.items} />
            </div>
          )}
          <p className="mt-3 text-center text-[11px] text-muted">Computed from {iv === "1h" ? "hourly" : iv === "1d" ? "daily" : "weekly"} bars · as of {data.as_of}</p>
        </>
      )}
    </div>
  );
}
