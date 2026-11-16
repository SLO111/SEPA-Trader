"use client";

import { useEffect, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import type { Watchlist } from "@/lib/types";

// One shared copy of the user's watchlists for every star on the page.
let shared: Promise<Watchlist[]> | null = null;
const loadLists = (fresh = false) => {
  if (!shared || fresh) shared = api<Watchlist[]>("/api/watchlists").catch(() => []);
  return shared;
};

/** ☆ button: add a ticker to one of your watchlists (★ when it is already in one). */
export default function AddToWatchlist({ symbol }: { symbol: string }) {
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState("");
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadLists().then(setLists);
    const refresh = () => loadLists(true).then(setLists);
    window.addEventListener("watchlists-changed", refresh);
    return () => window.removeEventListener("watchlists-changed", refresh);
  }, []);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const inAny = lists.some((l) => l.symbols.includes(symbol));
  const add = async (l: Watchlist) => {
    try {
      await post(`/api/watchlists/${l.id}/items`, { symbol });
      setMsg(`Added to ${l.name}`);
      window.dispatchEvent(new Event("watchlists-changed"));
      setTimeout(() => {
        setOpen(false);
        setMsg("");
      }, 900);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Could not add");
    }
  };

  return (
    <div ref={box} className="relative inline-block" onClick={(e) => e.stopPropagation()}>
      <button
        onClick={() => (lists.length === 1 && !inAny ? add(lists[0]) : setOpen((o) => !o))}
        title={inAny ? "In your watchlist" : "Add to a watchlist"}
        aria-label={`Add ${symbol} to a watchlist`}
        className={`grid h-6 w-6 place-items-center rounded text-base leading-none hover:bg-panel-2 ${inAny ? "text-amber-300" : "text-muted hover:text-amber-300"}`}
      >
        {inAny ? "★" : "☆"}
      </button>
      {open && (
        <div className="absolute left-0 top-7 z-30 w-52 rounded-lg border border-line bg-panel-2 p-1 shadow-xl">
          <div className="px-2 py-1 text-[11px] uppercase tracking-wide text-muted">Add {symbol} to</div>
          {lists.map((l) => {
            const has = l.symbols.includes(symbol);
            return (
              <button key={l.id} disabled={has} onClick={() => add(l)} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-line disabled:opacity-60">
                <span className="h-2 w-2 rounded-full" style={{ background: l.color }} />
                <span className="flex-1 truncate">{l.name}</span>
                {has && <span className="text-xs text-up">✓</span>}
              </button>
            );
          })}
          {msg && <div className="px-2 py-1 text-xs text-up">{msg}</div>}
        </div>
      )}
    </div>
  );
}
