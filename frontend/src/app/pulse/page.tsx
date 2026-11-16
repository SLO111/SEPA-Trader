"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import AddToWatchlist from "@/components/AddToWatchlist";
import AppShell from "@/components/AppShell";
import Locked from "@/components/Locked";
import { ApiError, api } from "@/lib/api";
import { pct, tone } from "@/lib/format";

type Row = { symbol: string; name: string; sector: string; conf: number; warn: number; net: number; tone: string; price: number | null; change_pct: number | null };
type Resp = { constructive: Row[]; warning: Row[]; count: number };

function Table({ rows, kind }: { rows: Row[]; kind: "constructive" | "warning" }) {
  const max = Math.max(1, ...rows.map((r) => Math.max(r.conf, r.warn)));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
          <tr>
            <th className="py-2 pl-1">Stock</th>
            <th className="py-2 text-right">Price</th>
            <th className="py-2 text-right">Today</th>
            <th className="w-44 py-2 pl-4">Confirmations / warnings</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol} className="border-t border-line">
              <td className="py-2 pl-1">
                <span className="flex items-center gap-1">
                  <AddToWatchlist symbol={r.symbol} />
                  <Link href={`/chart?s=${r.symbol}`} className="font-semibold hover:text-accent">{r.symbol}</Link>
                </span>
                <div className="max-w-[200px] truncate pl-7 text-xs text-muted">{r.name}</div>
              </td>
              <td className="tabular py-2 text-right">{r.price?.toFixed(2) ?? "—"}</td>
              <td className={`tabular py-2 text-right ${tone(r.change_pct)}`}>{pct(r.change_pct)}</td>
              <td className="py-2 pl-4">
                <div className="flex items-center gap-2">
                  <span className={`tabular w-12 rounded px-1.5 py-0.5 text-center text-xs font-semibold ${kind === "constructive" ? "bg-up/15 text-up" : "bg-down/15 text-down"}`}>
                    {r.conf}/{r.warn}
                  </span>
                  <span className="flex h-1.5 flex-1 overflow-hidden rounded-full bg-line">
                    <span className="bg-up" style={{ width: `${(r.conf / (max * 2)) * 100}%` }} />
                    <span className="bg-down" style={{ width: `${(r.warn / (max * 2)) * 100}%` }} />
                  </span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pulse() {
  const [data, setData] = useState<Resp | null>(null);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Resp>("/api/sepa/pulse/leaders?limit=25")
      .then(setData)
      .catch((e) => (e instanceof ApiError && e.status === 403 ? setLocked(true) : setError(e.message)));
  }, []);
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl p-3 sm:p-6">
        <h1 className="text-xl font-semibold">vnicorn Pulse</h1>
        <p className="mb-5 text-sm text-muted">
          Is a stock acting constructively or flashing warning signs? Daily confirmations (up on volume, closes near the high, higher highs, RS line new highs,
          breakouts…) vs. warnings (down on volume, closes near the low, lower lows, moving-average breaks, outside reversals…), over the last 10 trading days.
        </p>
        {locked && (
          <div className="max-w-xl">
            <Locked feature="vnicorn Pulse" text="The stocks acting best and worst across the market, every day, plus Pulse on every chart and in the Move Detector." />
          </div>
        )}
        {error && <p className="text-sm text-down">{error}</p>}
        {!data && !locked && !error && <p className="text-sm text-muted">Reading the market…</p>}
        {data && (
          <div className="grid gap-5 lg:grid-cols-2">
            <section className="rounded-xl border border-line bg-panel p-4">
              <h2 className="mb-1 font-semibold text-up">Acting best</h2>
              <p className="mb-2 text-xs text-muted">Most confirmations, fewest warnings: leadership behaviour.</p>
              <Table rows={data.constructive} kind="constructive" />
            </section>
            <section className="rounded-xl border border-line bg-panel p-4">
              <h2 className="mb-1 font-semibold text-down">Warning signs</h2>
              <p className="mb-2 text-xs text-muted">Most warnings: protect profits or avoid new buys.</p>
              <Table rows={data.warning} kind="warning" />
            </section>
          </div>
        )}
        {data && <p className="mt-4 text-xs text-muted">{data.count} stocks scanned · refreshed every 30 minutes. For educational purposes only. Not financial advice.</p>}
      </div>
    </div>
  );
}

export default function PulsePage() {
  return (
    <AppShell>
      <Pulse />
    </AppShell>
  );
}
