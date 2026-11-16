"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { StrategyDef } from "@/lib/types";

type Props = {
  defs: StrategyDef[];
  features: Record<string, unknown>;
  activeCount: number;
  max: number;
  onAdd: (d: StrategyDef) => void;
  onClose: () => void;
};

/** TradingView-style indicator dialog: search, categories on the left, click to add. */
export default function IndicatorPicker({ defs, features, activeCount, max, onAdd, onClose }: Props) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("All");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    input.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  const cats = useMemo(() => ["All", ...Array.from(new Set(defs.map((d) => d.category)))], [defs]);
  const list = defs.filter((d) => (cat === "All" || d.category === cat) && `${d.name} ${d.description} ${d.category}`.toLowerCase().includes(q.toLowerCase()));
  const atLimit = activeCount >= max;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onMouseDown={onClose}>
      <div className="flex h-[min(560px,90vh)] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-line bg-panel shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-line p-3">
          <h2 className="font-semibold">Indicators</h2>
          <input
            ref={input}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search indicators and strategies…"
            className="flex-1 rounded-md border border-line bg-bg px-3 py-1.5 text-sm outline-none focus:border-accent"
          />
          <button onClick={onClose} className="rounded px-2 py-1 text-muted hover:bg-panel-2 hover:text-text" aria-label="Close">
            ✕
          </button>
        </div>
        <div className="flex min-h-0 flex-1">
          <nav className="hidden w-44 shrink-0 border-r border-line p-2 sm:block">
            {cats.map((c) => (
              <button key={c} onClick={() => setCat(c)} className={`block w-full rounded px-3 py-1.5 text-left text-sm ${cat === c ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}>
                {c}
              </button>
            ))}
          </nav>
          <ul className="min-h-0 flex-1 overflow-y-auto p-2">
            {atLimit && max < 1e6 && <li className="mb-2 rounded bg-amber-500/10 px-3 py-2 text-xs text-amber-300">Your plan allows {max} indicators at once. Remove one or upgrade.</li>}
            {list.map((d) => {
              const locked = !!d.requires && !features[d.requires];
              return (
                <li key={d.id}>
                  <button
                    disabled={locked || atLimit}
                    onClick={() => onAdd(d)}
                    className="flex w-full items-start gap-3 rounded-md px-3 py-2 text-left hover:bg-panel-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded bg-accent/15 text-xs text-blue-300">+</span>
                    <span className="min-w-0">
                      <span className="text-sm">{d.name}</span>
                      {locked && <span className="ml-2 rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-300">PRO</span>}
                      <span className="ml-2 text-[11px] text-muted">{d.category}</span>
                      {d.description && <span className="block text-xs text-muted">{d.description}</span>}
                    </span>
                  </button>
                </li>
              );
            })}
            {list.length === 0 && <li className="p-6 text-center text-sm text-muted">No indicators found.</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}
