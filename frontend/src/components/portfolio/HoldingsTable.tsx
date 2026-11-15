import Link from "next/link";
import { num, pct, tone, usd } from "@/lib/format";
import type { Holding } from "@/lib/types";

export default function HoldingsTable({ rows }: { rows: Holding[] }) {
  return (
    <section className="rounded-xl border border-line bg-panel">
      <h2 className="px-4 pt-4 font-semibold">Holdings</h2>
      {rows.length === 0 ? (
        <p className="p-4 text-sm text-muted">No open positions. Add a buy transaction below.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="mt-2 w-full min-w-[760px] text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-2">Symbol</th>
                <th className="px-4 py-2 text-right">Shares</th>
                <th className="px-4 py-2 text-right">Avg cost</th>
                <th className="px-4 py-2 text-right">Price</th>
                <th className="px-4 py-2 text-right">Value</th>
                <th className="px-4 py-2 text-right">Weight</th>
                <th className="px-4 py-2 text-right">Today</th>
                <th className="px-4 py-2 text-right">Total P/L</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.symbol} className="border-t border-line">
                  <td className="px-4 py-2">
                    <Link href={`/stock?s=${encodeURIComponent(r.symbol)}`} className="font-medium hover:text-accent">
                      {r.symbol}
                    </Link>
                    <div className="max-w-[180px] truncate text-xs text-muted">{r.sector}</div>
                  </td>
                  <td className="tabular px-4 py-2 text-right">{num(r.shares)}</td>
                  <td className="tabular px-4 py-2 text-right">{usd(r.avg_cost)}</td>
                  <td className="tabular px-4 py-2 text-right">{usd(r.price)}</td>
                  <td className="tabular px-4 py-2 text-right">{usd(r.value)}</td>
                  <td className="tabular px-4 py-2 text-right text-muted">{r.weight.toFixed(1)}%</td>
                  <td className={`tabular px-4 py-2 text-right ${tone(r.day_change_pct)}`}>{pct(r.day_change_pct)}</td>
                  <td className={`tabular px-4 py-2 text-right ${tone(r.pnl)}`}>
                    {usd(r.pnl)}
                    <div className="text-xs">{pct(r.pnl_pct)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
