"use client";

import Link from "next/link";
import { Fragment, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { pct, tone } from "@/lib/format";

type Group = {
  rank: number; group: string; sector: string; size: number; avg_rs: number | null; return_3m: number | null; return_1m: number | null; leaders_pct: number;
  members: { symbol: string; rs: number | null; return_3m: number | null }[];
};

/** Industry group rankings (Premium): leaders tend to come from the strongest groups. */
export default function GroupsTab({ allowed }: { allowed: boolean }) {
  const [data, setData] = useState<{ groups: Group[] } | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    if (allowed) api<{ groups: Group[] }>("/api/markets/groups").then(setData).catch((e) => setError(e.message));
  }, [allowed]);

  if (!allowed) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-transparent p-6">
        <h2 className="font-semibold">🔒 Industry group rankings</h2>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          About half of a stock&apos;s move comes from its industry. See which of the ~120 groups lead the market right now, ranked by the relative strength of their
          stocks, and the leaders inside each group. Part of Premium.
        </p>
        <Link href="/billing" className="mt-3 inline-block rounded-md bg-amber-500 px-4 py-1.5 text-sm font-semibold text-black hover:bg-amber-400">Unlock with Premium</Link>
      </div>
    );
  }
  if (error) return <p className="text-sm text-down">{error}</p>;
  if (!data) return <p className="text-sm text-muted">Ranking groups…</p>;
  const list = data.groups.filter((g) => `${g.group} ${g.sector} ${g.members.map((m) => m.symbol).join(" ")}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-sm text-muted">Ranked by the average RS Rating of each group&apos;s stocks. Click a group to see its members.</p>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search a group or ticker…"
          className="ml-auto w-56 rounded-md border border-line bg-bg px-3 py-1.5 text-sm outline-none focus:border-accent" />
      </div>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-panel text-left text-[11px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2.5">#</th><th className="px-3 py-2.5">Group</th><th className="px-3 py-2.5 text-right">Stocks</th>
              <th className="px-3 py-2.5 text-right">Avg RS</th><th className="px-3 py-2.5 text-right">1M</th><th className="px-3 py-2.5 text-right">3M</th>
              <th className="px-3 py-2.5 text-right">RS 80+</th><th className="px-3 py-2.5">Top stocks</th>
            </tr>
          </thead>
          <tbody>
            {list.map((g) => (
              <Fragment key={g.group}>
                <tr onClick={() => setOpen(open === g.group ? null : g.group)} className="cursor-pointer border-t border-line hover:bg-panel/60">
                  <td className={`tabular px-3 py-2 font-semibold ${g.rank <= 20 ? "text-up" : g.rank > data.groups.length - 20 ? "text-down" : "text-muted"}`}>{g.rank}</td>
                  <td className="px-3 py-2"><div className="font-medium">{g.group}</div><div className="text-xs text-muted">{g.sector}</div></td>
                  <td className="tabular px-3 py-2 text-right">{g.size}</td>
                  <td className="tabular px-3 py-2 text-right font-semibold">{g.avg_rs ?? "—"}</td>
                  <td className={`tabular px-3 py-2 text-right ${tone(g.return_1m)}`}>{pct(g.return_1m, 1)}</td>
                  <td className={`tabular px-3 py-2 text-right ${tone(g.return_3m)}`}>{pct(g.return_3m, 1)}</td>
                  <td className="tabular px-3 py-2 text-right">{g.leaders_pct}%</td>
                  <td className="px-3 py-2 text-xs text-muted">{g.members.slice(0, 4).map((m) => m.symbol).join(" · ")}</td>
                </tr>
                {open === g.group && (
                  <tr className="bg-panel/40">
                    <td colSpan={8} className="px-3 py-2">
                      <div className="flex flex-wrap gap-1.5">
                        {g.members.map((m) => (
                          <Link key={m.symbol} href={`/chart?s=${m.symbol}`} className="tabular rounded bg-panel-2 px-2 py-0.5 text-xs hover:text-accent">
                            {m.symbol} <span className="text-muted">RS {m.rs ?? "—"}</span> <span className={tone(m.return_3m)}>{pct(m.return_3m, 0)}</span>
                          </Link>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
