"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, del, patch, post } from "@/lib/api";
import type { Quote, Watchlist } from "@/lib/types";

type SearchHit = { symbol: string; name: string; exchange: string };
const COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#14b8a6", "#ec4899"];

export default function WatchlistPanel({ selected, onSelect }: { selected: string; onSelect: (s: string) => void }) {
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const active = lists.find((l) => l.id === activeId) ?? lists[0];

  const replaceList = (w: Watchlist) => setLists((ls) => ls.map((l) => (l.id === w.id ? w : l)));
  const run = async (fn: () => Promise<void>) => {
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
  };

  useEffect(() => {
    run(async () => {
      const ls = await api<Watchlist[]>("/api/watchlists");
      setLists(ls);
      setActiveId(ls[0]?.id ?? null);
    });
  }, []);

  const loadQuotes = useCallback(async (symbols: string[]) => {
    if (!symbols.length) return;
    const qs = await api<Quote[]>(`/api/market/quotes?symbols=${encodeURIComponent(symbols.join(","))}`);
    setQuotes((prev) => ({ ...prev, ...Object.fromEntries(qs.map((q) => [q.symbol, q])) }));
  }, []);

  useEffect(() => {
    if (!active) return;
    loadQuotes(active.symbols).catch(() => {});
    const id = setInterval(() => loadQuotes(active.symbols).catch(() => {}), 60_000);
    return () => clearInterval(id);
  }, [active, loadQuotes]);

  const onQuery = (v: string) => {
    setQuery(v);
    clearTimeout(searchTimer.current);
    if (!v.trim()) return setHits([]);
    searchTimer.current = setTimeout(() => {
      api<SearchHit[]>(`/api/market/search?q=${encodeURIComponent(v)}`).then(setHits).catch(() => setHits([]));
    }, 200);
  };

  const addSymbol = (symbol: string) =>
    run(async () => {
      if (!active || !symbol.trim()) return;
      replaceList(await post<Watchlist>(`/api/watchlists/${active.id}/items`, { symbol: symbol.trim() }));
      setQuery("");
      setHits([]);
    });

  const removeSymbol = (symbol: string) =>
    run(async () => {
      if (active) replaceList(await del<Watchlist>(`/api/watchlists/${active.id}/items/${encodeURIComponent(symbol)}`));
    });

  const createList = () =>
    run(async () => {
      const name = prompt("New watchlist name:");
      if (!name?.trim()) return;
      const w = await post<Watchlist>("/api/watchlists", { name, color: COLORS[lists.length % COLORS.length] });
      setLists((ls) => [...ls, w]);
      setActiveId(w.id);
    });

  const renameList = () =>
    run(async () => {
      setMenuOpen(false);
      const name = active && prompt("New name:", active.name);
      if (active && name?.trim()) replaceList(await patch<Watchlist>(`/api/watchlists/${active.id}`, { name }));
    });

  const recolorList = (color: string) =>
    run(async () => {
      if (active) replaceList(await patch<Watchlist>(`/api/watchlists/${active.id}`, { color }));
    });

  const deleteList = () =>
    run(async () => {
      setMenuOpen(false);
      if (!active || !confirm(`Delete the watchlist "${active.name}"?`)) return;
      await del(`/api/watchlists/${active.id}`);
      const rest = lists.filter((l) => l.id !== active.id);
      setLists(rest);
      setActiveId(rest[0]?.id ?? null);
    });

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b border-line p-2">
        <div className="flex min-w-0 flex-1 gap-1 overflow-x-auto">
          {lists.map((l) => (
            <button
              key={l.id}
              onClick={() => setActiveId(l.id)}
              className={`flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-xs ${l.id === active?.id ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}
            >
              <span className="h-2 w-2 rounded-full" style={{ background: l.color }} />
              {l.name}
            </button>
          ))}
        </div>
        <button onClick={createList} title="New watchlist" className="rounded px-2 py-1 text-muted hover:bg-panel-2 hover:text-text">
          +
        </button>
        <div className="relative">
          <button onClick={() => setMenuOpen((o) => !o)} title="Watchlist options" className="rounded px-2 py-1 text-muted hover:bg-panel-2 hover:text-text">
            ⋯
          </button>
          {menuOpen && active && (
            <div className="absolute right-0 z-20 mt-1 w-44 rounded-md border border-line bg-panel-2 p-1 text-sm shadow-xl">
              <button onClick={renameList} className="block w-full rounded px-2 py-1.5 text-left hover:bg-line">Rename</button>
              <div className="flex gap-1 px-2 py-1.5">
                {COLORS.map((c) => (
                  <button key={c} onClick={() => recolorList(c)} className="h-4 w-4 rounded-full" style={{ background: c }} aria-label={`Color ${c}`} />
                ))}
              </div>
              <button onClick={deleteList} className="block w-full rounded px-2 py-1.5 text-left text-down hover:bg-line">Delete watchlist</button>
            </div>
          )}
        </div>
      </div>

      <div className="relative border-b border-line p-2">
        <input
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addSymbol(hits[0]?.symbol ?? query)}
          placeholder="Add symbol (e.g. AAPL)"
          className="w-full rounded border border-line bg-bg px-2 py-1.5 text-sm outline-none focus:border-accent"
        />
        {hits.length > 0 && (
          <div className="absolute left-2 right-2 z-20 mt-1 max-h-64 overflow-y-auto rounded-md border border-line bg-panel-2 shadow-xl">
            {hits.map((h) => (
              <button key={h.symbol} onClick={() => addSymbol(h.symbol)} className="flex w-full items-baseline gap-2 px-2 py-1.5 text-left text-sm hover:bg-line">
                <span className="w-14 font-medium">{h.symbol}</span>
                <span className="truncate text-xs text-muted">{h.name}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <div className="border-b border-line bg-down/10 px-3 py-2 text-xs text-down">{error}</div>}

      <div className="grid grid-cols-[1fr_auto_auto] gap-x-3 px-3 py-1.5 text-[11px] uppercase tracking-wide text-muted">
        <span>Symbol</span>
        <span className="text-right">Price</span>
        <span className="w-14 text-right">Chg.</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {active?.symbols.map((s) => {
          const q = quotes[s];
          const up = (q?.change_pct ?? 0) >= 0;
          return (
            <div
              key={s}
              onClick={() => onSelect(s)}
              className={`group grid cursor-pointer grid-cols-[1fr_auto_auto] items-center gap-x-3 px-3 py-1.5 text-sm ${s === selected ? "bg-panel-2" : "hover:bg-panel-2/60"}`}
            >
              <span className="flex items-center gap-1 font-medium">
                {s}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeSymbol(s);
                  }}
                  className="invisible text-xs text-muted hover:text-down group-hover:visible"
                  aria-label={`Remove ${s}`}
                >
                  ✕
                </button>
              </span>
              <span className="tabular text-right">{q?.price?.toFixed(2) ?? "—"}</span>
              <span className={`tabular w-14 text-right ${q?.change_pct === undefined ? "text-muted" : up ? "text-up" : "text-down"}`}>
                {q?.change_pct === undefined ? "—" : `${up ? "+" : ""}${q.change_pct.toFixed(2)}%`}
              </span>
            </div>
          );
        })}
        {active && active.symbols.length === 0 && <p className="px-3 py-6 text-center text-sm text-muted">This watchlist is empty. Add a symbol above.</p>}
      </div>
    </div>
  );
}
