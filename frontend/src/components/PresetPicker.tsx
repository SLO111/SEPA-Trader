"use client";

import { useBackClose } from "@/lib/useBackClose";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Preset = { id: string; name: string; description: string; symbols: string[] };

/** Ready-made lists (ETFs, Mag 7, semiconductors, memory, AI…): one click adds a section with the tickers. */
export default function PresetPicker({ onPick, onClose }: { onPick: (p: Preset) => void; onClose: () => void }) {
  useBackClose(true, onClose);
  const [list, setList] = useState<Preset[]>([]);
  const [q, setQ] = useState("");
  useEffect(() => {
    api<Preset[]>("/api/watchlists/presets").then(setList).catch(() => {});
  }, []);
  const shown = list.filter((p) => `${p.name} ${p.description} ${p.symbols.join(" ")}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" onMouseDown={onClose}>
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-line bg-panel shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 border-b border-line p-3">
          <h2 className="font-semibold">Add a ready-made list</h2>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search (e.g. chips, NVDA, dividends)…" autoFocus
            className="flex-1 rounded-md border border-line bg-bg px-3 py-1.5 text-sm outline-none focus:border-accent" />
          <button onClick={onClose} className="rounded px-2 py-1 text-muted hover:bg-panel-2" aria-label="Close">✕</button>
        </div>
        <div className="grid min-h-0 gap-2 overflow-y-auto p-3 sm:grid-cols-2">
          {shown.map((p) => (
            <button key={p.id} onClick={() => onPick(p)} className="rounded-lg border border-line bg-bg/40 p-3 text-left hover:border-accent/60 hover:bg-panel-2">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium">{p.name}</span>
                <span className="text-[11px] text-muted">{p.symbols.length} stocks</span>
              </div>
              <p className="mt-0.5 text-xs text-muted">{p.description}</p>
              <p className="mt-1.5 truncate text-[11px] text-text/70">{p.symbols.join(" · ")}</p>
            </button>
          ))}
        </div>
        <p className="border-t border-line px-3 py-2 text-[11px] text-muted">The list is added as a section of the current watchlist. Drag stocks between sections; ✎ renames, ✕ removes a section (the stocks stay).</p>
      </div>
    </div>
  );
}
