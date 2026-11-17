"use client";

import Link from "next/link";
import { LoadMoreBlock, useSentinel } from "@/lib/useInfinite";
import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import DailySummary from "@/components/DailySummary";
import WeeklyLetter from "@/components/WeeklyLetter";
import { api } from "@/lib/api";

type Item = { id: number; kind: string; symbol: string | null; severity: "bull" | "bear" | "info"; title: string; body: string; url: string | null; created_at: string };

const KINDS = [
  { id: "all", label: "All" },
  { id: "earnings", label: "Earnings" },
  { id: "mover", label: "Big movers" },
  { id: "breakout", label: "Breakouts" },
  { id: "high", label: "New highs" },
  { id: "idea", label: "Ideas" },
  { id: "news", label: "News" },
] as const;

const ICON: Record<string, string> = { earnings: "📊", mover: "⚡", breakout: "📈", high: "🏔️", idea: "💡", news: "📰" };
const ACCENT = { bull: "border-l-up", bear: "border-l-down", info: "border-l-accent" };

// headlines that usually move prices (same idea as the server's "critical news" rule)
const MOVING = /\b(FDA|SEC|antitrust|lawsuit|investigation|probe|recall|bankrupt\w*|acquir\w*|acquisition|merger|buyout|takeover|guidance|outlook|warns?|layoffs?|CEO|CFO|resign\w*|upgrade\w*|downgrade\w*|beats?|miss(es|ed)?|tariffs?|Fed|FOMC|rate (cut|hike)s?|CPI|inflation|jobs report|payrolls|recession|stock split|buyback)\b/i;
const SOURCES: Record<string, string> = {
  "cnbc.com": "CNBC", "marketwatch.com": "MarketWatch", "yahoo.com": "Yahoo Finance", "investing.com": "Investing.com", "nasdaq.com": "Nasdaq",
  "seekingalpha.com": "Seeking Alpha", "foxbusiness.com": "Fox Business", "reuters.com": "Reuters", "bloomberg.com": "Bloomberg", "wsj.com": "WSJ",
  "benzinga.com": "Benzinga", "fool.com": "Motley Fool", "barrons.com": "Barron's", "ft.com": "Financial Times", "finnhub.io": "Finnhub",
};
function sourceOf(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    const k = Object.keys(SOURCES).find((d) => host === d || host.endsWith(`.${d}`));
    return k ? SOURCES[k] : host;
  } catch {
    return "News";
  }
}

function ago(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Turns "$NVDA" mentions in a title into links to the chart. */
function Title({ text }: { text: string }) {
  const parts = text.split(/(\$[A-Z][A-Z.\-]{0,6})/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("$") ? (
          <Link key={i} href={`/chart?s=${encodeURIComponent(p.slice(1))}`} className="text-accent hover:underline">
            {p}
          </Link>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

function Feed() {
  const [kind, setKind] = useState<string>("all");
  const [items, setItems] = useState<Item[] | null>(null);
  const [more, setMore] = useState(true);

  const load = useCallback(() => {
    api<Item[]>(`/api/feed?kind=${kind}&limit=50`).then((r) => {
      setItems(r);
      setMore(r.length === 50);
    });
  }, [kind]);

  useEffect(() => {
    setItems(null);
    load();
    const id = setInterval(() => { if (!document.hidden) load(); }, 120_000);
    return () => clearInterval(id);
  }, [load]);

  const [loadingOlder, setLoadingOlder] = useState(false);
  const older = async () => {
    if (!items?.length || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const r = await api<Item[]>(`/api/feed?kind=${kind}&limit=50&before_id=${items[items.length - 1].id}`);
      setItems((cur) => {
        const have = new Set((cur ?? []).map((x) => x.id));
        return [...(cur ?? []), ...r.filter((x) => !have.has(x.id))];
      });
      setMore(r.length === 50);
    } finally {
      setLoadingOlder(false);
    }
  };
  const sentinel = useSentinel(older, more); // the next 50 load when the end of the feed scrolls into view

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl p-4 sm:p-6">
        <h1 className="text-xl font-semibold">Market feed</h1>
        <p className="mb-4 text-sm text-muted">Earnings beats and misses, big movers, breakouts, new highs, trade ideas and market-moving news, as they happen.</p>
        <DailySummary />
        <WeeklyLetter />
        <div className="sticky top-0 z-10 -mx-1 mb-4 flex gap-1 overflow-x-auto bg-bg/90 px-1 py-2 backdrop-blur">
          {KINDS.map((k) => (
            <button key={k.id} onClick={() => setKind(k.id)} className={`whitespace-nowrap rounded-full px-3 py-1 text-sm ${kind === k.id ? "bg-accent text-white" : "bg-panel text-muted hover:text-text"}`}>
              {k.label}
            </button>
          ))}
        </div>
        {items === null && <p className="text-sm text-muted">Loading…</p>}
        {items?.length === 0 && <p className="rounded-xl border border-line bg-panel p-6 text-center text-sm text-muted">Nothing here yet. The feed updates every few minutes.</p>}
        <ul className="space-y-3">
          {items?.map((it) => (
            <li key={it.id} className={`rounded-xl border border-l-4 border-line bg-panel p-4 ${ACCENT[it.severity]}`}>
              <div className="flex items-start gap-3">
                <span className="text-xl leading-none">{ICON[it.kind] ?? "🔔"}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline gap-2">
                    <p className="font-medium leading-snug">
                      <Title text={it.title} />
                    </p>
                    <span className="ml-auto shrink-0 text-xs text-muted">{ago(it.created_at)}</span>
                  </div>
                  {it.body && <p className={`mt-1 text-sm text-muted ${it.kind === "news" ? "line-clamp-2" : ""}`}>{it.body}</p>}
                  <div className="mt-2 flex items-center gap-3 text-xs">
                    {it.symbol && (
                      <Link href={`/chart?s=${encodeURIComponent(it.symbol)}`} className="rounded bg-panel-2 px-2 py-0.5 font-medium hover:text-accent">
                        {it.symbol}
                      </Link>
                    )}
                    {it.url && (
                      <a href={it.url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                        Read more ↗
                      </a>
                    )}
                    <span className="text-muted capitalize">{it.kind === "news" && it.url ? sourceOf(it.url) : KINDS.find((k) => k.id === it.kind)?.label ?? it.kind}</span>
                    {it.kind === "news" && MOVING.test(it.title) && <span className="rounded bg-amber-500/15 px-1.5 py-0.5 font-semibold text-amber-300">Market-moving</span>}
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
        {more && items && items.length > 0 && <LoadMoreBlock sentinel={sentinel} loading={loadingOlder} onClick={older} />}
        <p className="mt-6 text-center text-xs text-muted">For educational purposes only. Not financial advice.</p>
      </div>
    </div>
  );
}

export default function FeedPage() {
  return (
    <AppShell>
      <Feed />
    </AppShell>
  );
}
