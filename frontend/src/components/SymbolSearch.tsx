"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type Hit = { symbol: string; name: string; exchange: string };

/** Header search: type a ticker or company name and open its overview page. */
export default function SymbolSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!q.trim()) return setHits([]);
    const t = setTimeout(() => {
      api<Hit[]>(`/api/market/search?q=${encodeURIComponent(q)}`)
        .then((h) => {
          setHits(h);
          setActive(0);
        })
        .catch(() => setHits([]));
    }, 150);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const go = (symbol: string) => {
    setQ("");
    setHits([]);
    setOpen(false);
    router.push(`/stock?s=${encodeURIComponent(symbol.toUpperCase())}`);
  };

  return (
    <div ref={box} className="relative hidden w-56 lg:block">
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setActive((a) => Math.min(a + 1, hits.length - 1));
          if (e.key === "ArrowUp") setActive((a) => Math.max(a - 1, 0));
          if (e.key === "Enter" && (hits[active] || q.trim())) go(hits[active]?.symbol ?? q.trim());
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder="Search stocks…"
        aria-label="Search stocks"
        className="w-full rounded-md border border-line bg-bg px-3 py-1.5 text-sm outline-none focus:border-accent"
      />
      {open && hits.length > 0 && (
        <ul className="absolute left-0 right-0 z-40 mt-1 overflow-hidden rounded-md border border-line bg-panel-2 shadow-xl">
          {hits.map((h, i) => (
            <li key={h.symbol}>
              <button
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => go(h.symbol)}
                className={`flex w-full items-baseline gap-2 px-3 py-1.5 text-left text-sm ${i === active ? "bg-line" : "hover:bg-line"}`}
              >
                <span className="w-14 font-medium">{h.symbol}</span>
                <span className="truncate text-xs text-muted">{h.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
