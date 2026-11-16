"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import PublicShell from "@/components/PublicShell";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type WL = { slug: string; name: string; owner: string; symbols: { symbol: string; name: string; price: number | null; change_pct: number | null }[] };

function Shared() {
  const slug = useSearchParams().get("s") ?? "";
  const { user } = useAuth();
  const [w, setW] = useState<WL | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => {
    if (slug) api<WL>(`/api/public/watchlists/${encodeURIComponent(slug)}`).then(setW).catch((e) => setErr(e.message));
  }, [slug]);
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
      {err && <p className="text-sm text-down">{err}</p>}
      {w && (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <h1 className="text-2xl font-semibold">{w.name}</h1>
              <p className="text-sm text-muted">A watchlist shared by {w.owner} · {w.symbols.length} stocks</p>
            </div>
            <div className="ml-auto">
              {user ? (
                <button
                  onClick={async () => {
                    try {
                      const r = await post<{ name: string }>(`/api/public/watchlists/${slug}/copy`, {});
                      setMsg(`Added to your watchlists as “${r.name}”.`);
                    } catch (e) {
                      setMsg(e instanceof Error ? e.message : "Error");
                    }
                  }}
                  className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white"
                >
                  Copy to my watchlists
                </button>
              ) : (
                <Link href={`/register`} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white">Sign up to copy it</Link>
              )}
            </div>
          </div>
          {msg && <p className="text-sm text-muted">{msg}</p>}
          <div className="overflow-hidden rounded-xl border border-line">
            <table className="w-full text-sm">
              <tbody>
                {w.symbols.map((s) => (
                  <tr key={s.symbol} className="border-t border-line first:border-0">
                    <td className="px-3 py-2"><Link href={`/chart?s=${s.symbol}`} className="font-semibold hover:text-accent">{s.symbol}</Link><div className="text-xs text-muted">{s.name}</div></td>
                    <td className="tabular px-3 py-2 text-right">{s.price?.toFixed(2) ?? "—"}</td>
                    <td className={`tabular px-3 py-2 text-right ${(s.change_pct ?? 0) >= 0 ? "text-up" : "text-down"}`}>{s.change_pct === null ? "—" : `${s.change_pct >= 0 ? "+" : ""}${s.change_pct.toFixed(2)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default function SharedWatchlistPage() {
  return (
    <PublicShell>
      <Suspense><Shared /></Suspense>
    </PublicShell>
  );
}
