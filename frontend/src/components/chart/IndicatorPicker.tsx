"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ActiveStrategy, StrategyDef } from "@/lib/types";

type Props = {
  defs: StrategyDef[];
  features: Record<string, unknown>;
  active: ActiveStrategy[];
  max: number;
  onAdd: (d: StrategyDef) => void;
  onRemove: (uid: string) => void;
  onClose: () => void;
};

/** TradingView-style indicator dialog: search, categories on the left, click to add. */
export default function IndicatorPicker({ defs, features, active, max, onAdd, onRemove, onClose }: Props) {
  const activeCount = active.length;
  const countOf = (id: string) => active.filter((a) => a.id === id).length;
  const nameOf = (id: string) => defs.find((d) => d.id === id)?.name ?? id;
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
            {active.length > 0 && !q && (
              <li className="mb-3 rounded-lg border border-accent/30 bg-accent/5 p-2">
                <div className="mb-1.5 px-1 text-[11px] uppercase tracking-wide text-muted">
                  On your chart ({activeCount}
                  {max < 1e6 ? `/${max}` : ""})
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {active.map((a) => (
                    <span key={a.uid} className={`inline-flex items-center gap-1.5 rounded-full bg-panel-2 px-2.5 py-1 text-xs ${a.hidden ? "opacity-50" : ""}`}>
                      <span className="text-up">✓</span>
                      {nameOf(a.id)}
                      <button onClick={() => onRemove(a.uid)} className="text-muted hover:text-down" aria-label={`Remove ${nameOf(a.id)}`}>
                        ✕
                      </button>
                    </span>
                  ))}
                </div>
              </li>
            )}
            {atLimit && max < 1e6 && <li className="mb-2 rounded bg-amber-500/10 px-3 py-2 text-xs text-amber-300">Your plan allows {max} indicators at once. Remove one or upgrade.</li>}
            {list.map((d) => {
              const locked = !!d.requires && !features[d.requires];
              const n = countOf(d.id);
              return (
                <li key={d.id} className="group relative">
                  <button
                    disabled={locked || atLimit}
                    onClick={() => onAdd(d)}
                    className="flex w-full items-start gap-3 rounded-md px-3 py-2 text-left hover:bg-panel-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded text-xs ${n ? "bg-up/20 text-up" : "bg-accent/15 text-blue-300"}`}>{n ? "✓" : "+"}</span>
                    <span className="min-w-0 pr-16">
                      <span className="text-sm">{d.name}</span>
                      {n > 0 && <span className="ml-2 rounded bg-up/15 px-1.5 py-0.5 text-[10px] font-semibold text-up">On chart{n > 1 ? ` ×${n}` : ""}</span>}
                      {locked && <span className="ml-2 rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] text-amber-300">PRO</span>}
                      <span className="ml-2 text-[11px] text-muted">{d.category}</span>
                      {d.description && <span className="block text-xs text-muted">{d.description}</span>}
                    </span>
                  </button>
                  {n > 0 && (
                    <button
                      onClick={() => {
                        const last = [...active].reverse().find((a) => a.id === d.id);
                        if (last) onRemove(last.uid);
                      }}
                      className="absolute right-2 top-2 rounded border border-line px-2 py-0.5 text-[11px] text-muted hover:border-down hover:text-down"
                    >
                      Remove
                    </button>
                  )}
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
