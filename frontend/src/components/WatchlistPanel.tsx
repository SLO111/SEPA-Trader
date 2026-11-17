"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, del, patch, post, put } from "@/lib/api";
import type { Quote, WatchSection, Watchlist } from "@/lib/types";
import PresetPicker from "./PresetPicker";

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
  const [presets, setPresets] = useState(false);
  const [dragSec, setDragSec] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const searchTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const active = lists.find((l) => l.id === activeId) ?? lists[0];

  // Drag & drop to reorder (mouse and touch): grab the ⋮⋮ handle and move the row. The drag is followed on the
  // window, because moving the row in the list would otherwise make the browser drop the pointer.
  const [dragging, setDragging] = useState<string | null>(null);
  const activeRef = useRef(active);
  activeRef.current = active;
  const startDrag = (e: React.PointerEvent, sym: string) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(sym);
  };
  useEffect(() => {
    if (!dragging) return;
    const move = (e: PointerEvent) => {
      const cur = activeRef.current;
      if (!cur) return;
      const hit = document.elementFromPoint(e.clientX, e.clientY);
      const header = hit?.closest("[data-section-header]") as HTMLElement | null;
      const el = hit?.closest("[data-symbol]") as HTMLElement | null;
      const over = el?.dataset.symbol;
      const target = header ? header.dataset.sectionHeader! : el ? el.dataset.section ?? "" : null; // "" = ungrouped
      if (target === null || over === dragging) return;
      const secs = (cur.sections ?? []).map((sc) => ({ ...sc, symbols: sc.symbols.filter((x) => x !== dragging) }));
      if (target) {
        const sc = secs.find((x) => x.id === target);
        if (!sc) return;
        const at = over ? sc.symbols.indexOf(over) : -1;
        sc.symbols.splice(at < 0 ? (header ? 0 : sc.symbols.length) : at + 1, 0, dragging);
      }
      let syms = cur.symbols;
      if (over && over !== dragging) {
        const from = cur.symbols.indexOf(dragging), to = cur.symbols.indexOf(over);
        syms = cur.symbols.filter((x) => x !== dragging);
        syms.splice(syms.indexOf(over) + (to > from ? 1 : 0), 0, dragging);
      }
      replaceList({ ...cur, symbols: syms, sections: secs });
    };
    const up = () => {
      const cur = activeRef.current;
      setDragging(null);
      if (cur)
        run(async () => {
          await put<Watchlist>(`/api/watchlists/${cur.id}/order`, { symbols: cur.symbols });
          replaceList(await put<Watchlist>(`/api/watchlists/${cur.id}/layout`, { sections: cur.sections ?? [] }));
        });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
    window.addEventListener("pointercancel", up, { once: true });
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
  }, [dragging]);


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
    const refresh = () => api<Watchlist[]>("/api/watchlists").then(setLists).catch(() => {});
    window.addEventListener("watchlists-changed", refresh);
    return () => window.removeEventListener("watchlists-changed", refresh);
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

  const saveSections = (sections: WatchSection[]) =>
    run(async () => {
      if (!active) return;
      replaceList({ ...active, sections });
      replaceList(await put<Watchlist>(`/api/watchlists/${active.id}/layout`, { sections }));
    });
  const addSection = (name: string, symbols: string[] = []) =>
    run(async () => {
      if (!active) return;
      const w = await post<Watchlist>(`/api/watchlists/${active.id}/sections`, { name, symbols });
      replaceList(w);
      setNotice(w.skipped?.length ? `Added ${name}. ${w.skipped.length} symbol${w.skipped.length === 1 ? "" : "s"} left out (${w.skipped.slice(0, 6).join(", ")}${w.skipped.length > 6 ? "…" : ""}): your plan's symbol limit or no data.` : "");
    });
  const newSection = () => {
    setMenuOpen(false);
    const name = prompt("Section name (e.g. Chips, ETFs, Long-term):");
    if (name?.trim()) addSection(name.trim());
  };
  const groupBySector = () =>
    run(async () => {
      setMenuOpen(false);
      if (!active) return;
      if ((active.sections?.length ?? 0) > 0 && !confirm("Replace the current sections with one section per sector?")) return;
      replaceList(await post<Watchlist>(`/api/watchlists/${active.id}/group-by-sector`, {}));
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
              {l.locked ? `🔒 ${l.name}` : l.name}
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
            <div className="absolute right-0 z-20 mt-1 w-52 rounded-md border border-line bg-panel-2 p-1 text-sm shadow-xl">
              <button onClick={newSection} className="block w-full rounded px-2 py-1.5 text-left hover:bg-line">+ Section</button>
              <button onClick={() => { setMenuOpen(false); setPresets(true); }} className="block w-full rounded px-2 py-1.5 text-left hover:bg-line">Add a ready-made list…</button>
              <button onClick={groupBySector} className="block w-full rounded px-2 py-1.5 text-left hover:bg-line">Group by sector</button>
              <div className="my-1 border-t border-line" />
              <button onClick={renameList} className="block w-full rounded px-2 py-1.5 text-left hover:bg-line">Rename list</button>
              <button
                onClick={async () => {
                  try {
                    const r = await post<{ slug: string }>(`/api/watchlists/${active.id}/share`, {});
                    const url = `${window.location.origin}/w?s=${r.slug}`;
                    await navigator.clipboard?.writeText(url).catch(() => {});
                    prompt("Public link copied. Anyone with it can view and copy this list:", url);
                  } catch (e) {
                    alert(e instanceof Error ? e.message : "Could not share");
                  }
                  setMenuOpen(false);
                }}
                className="block w-full rounded px-2 py-1.5 text-left hover:bg-line"
              >
                Share link…
              </button>
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
      {notice && <div className="border-b border-line bg-amber-500/10 px-3 py-2 text-xs text-amber-300" onClick={() => setNotice("")}>{notice}</div>}
      {presets && <PresetPicker onClose={() => setPresets(false)} onPick={(p) => { setPresets(false); addSection(p.name, p.symbols); }} />}

      <div className="grid grid-cols-[1fr_auto_auto] gap-x-3 px-3 py-1.5 text-[11px] uppercase tracking-wide text-muted">
        <span>Symbol</span>
        <span className="text-right">Price</span>
        <span className="w-14 text-right">Chg.</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {(() => {
          if (!active) return null;
          const secs = active.sections ?? [];
          const inSec = new Set(secs.flatMap((x) => x.symbols));
          const ungrouped = active.symbols.filter((x) => !inSec.has(x));
          const row = (s: string, section: string) => {
            const q = quotes[s];
            const up = (q?.change_pct ?? 0) >= 0;
            return (
              <div
                key={s}
                data-symbol={s}
                data-section={section}
                onClick={() => !dragging && onSelect(s)}
                className={`group grid cursor-pointer grid-cols-[1fr_auto_auto] items-center gap-x-3 py-1.5 pl-1 pr-3 text-sm transition-colors ${
                  dragging === s ? "bg-accent/20 ring-1 ring-accent/60" : s === selected ? "bg-panel-2" : "hover:bg-panel-2/60"
                }`}
              >
                <span className="flex items-center gap-1 font-medium">
                  <span
                    onPointerDown={(e) => startDrag(e, s)}
                    onClick={(e) => e.stopPropagation()}
                    className="cursor-grab touch-none select-none px-1 text-muted/40 hover:text-muted active:cursor-grabbing group-hover:text-muted"
                    title="Drag to reorder or move to another section"
                    aria-label={`Drag ${s}`}
                  >
                    ⋮⋮
                  </span>
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
          };
          return (
            <>
              {ungrouped.map((s) => row(s, ""))}
              {secs.map((sc) => {
                const day = sc.symbols.map((x) => quotes[x]?.change_pct).filter((x): x is number => x !== undefined);
                const avg = day.length ? day.reduce((a, b) => a + b, 0) / day.length : null;
                return (
                  <div key={sc.id}>
                    <div
                      data-section-header={sc.id}
                      draggable
                      onDragStart={(e) => {
                        setDragSec(sc.id);
                        e.dataTransfer.effectAllowed = "move";
                      }}
                      onDragOver={(e) => dragSec && e.preventDefault()}
                      onDrop={() => {
                        if (!dragSec || dragSec === sc.id) return setDragSec(null);
                        const moving = secs.find((x) => x.id === dragSec)!;
                        const rest = secs.filter((x) => x.id !== dragSec);
                        const from = secs.findIndex((x) => x.id === dragSec), to = secs.findIndex((x) => x.id === sc.id);
                        rest.splice(rest.findIndex((x) => x.id === sc.id) + (from < to ? 1 : 0), 0, moving);
                        setDragSec(null);
                        saveSections(rest);
                      }}
                      onDragEnd={() => setDragSec(null)}
                      className={`group flex items-center gap-1.5 border-t border-line bg-panel-2/40 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${
                        dragging || (dragSec && dragSec !== sc.id) ? "ring-1 ring-inset ring-accent/30" : ""
                      } ${dragSec === sc.id ? "opacity-50" : ""}`}
                    >
                      <span className="cursor-grab select-none text-muted/40 hover:text-muted active:cursor-grabbing" title="Drag to move this section">⋮⋮</span>
                      <button
                        onClick={() => saveSections(secs.map((x) => (x.id === sc.id ? { ...x, collapsed: !x.collapsed } : x)))}
                        className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-muted hover:text-text"
                      >
                        <span className="w-3">{sc.collapsed ? "▸" : "▾"}</span>
                        <span className="truncate">{sc.name}</span>
                        <span className="font-normal normal-case text-muted/70">{sc.symbols.length}</span>
                      </button>
                      {avg !== null && <span className={`tabular font-normal normal-case ${avg >= 0 ? "text-up" : "text-down"}`} title="Average change today">{avg >= 0 ? "+" : ""}{avg.toFixed(2)}%</span>}
                      {(() => {
                        const i = secs.findIndex((x) => x.id === sc.id);
                        const move = (d: number) => {
                          const next = [...secs];
                          [next[i], next[i + d]] = [next[i + d], next[i]];
                          saveSections(next);
                        };
                        return (
                          <>
                            <button onClick={() => move(-1)} disabled={i === 0} className="invisible px-0.5 font-normal text-muted hover:text-text disabled:opacity-30 group-hover:visible" title="Move up">↑</button>
                            <button onClick={() => move(1)} disabled={i === secs.length - 1} className="invisible px-0.5 font-normal text-muted hover:text-text disabled:opacity-30 group-hover:visible" title="Move down">↓</button>
                          </>
                        );
                      })()}
                      <button
                        onClick={() => {
                          const name = prompt("Rename section:", sc.name);
                          if (name?.trim()) saveSections(secs.map((x) => (x.id === sc.id ? { ...x, name: name.trim() } : x)));
                        }}
                        className="invisible px-1 font-normal text-muted hover:text-text group-hover:visible"
                        title="Rename section"
                      >
                        ✎
                      </button>
                      <button
                        onClick={() => confirm(`Remove the section "${sc.name}"? Its stocks stay in the list.`) && saveSections(secs.filter((x) => x.id !== sc.id))}
                        className="invisible px-1 font-normal text-muted hover:text-down group-hover:visible"
                        title="Remove section (keeps the stocks)"
                      >
                        ✕
                      </button>
                    </div>
                    {!sc.collapsed && sc.symbols.map((s) => row(s, sc.id))}
                    {!sc.collapsed && sc.symbols.length === 0 && <p className="px-3 py-1.5 text-[11px] text-muted">Drag stocks here.</p>}
                  </div>
                );
              })}
            </>
          );
        })()}
        {active?.locked && (
          <div className="m-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-muted">
            <div className="mb-1 font-medium text-amber-200">🔒 Locked on your current plan</div>
            This watchlist ({active.hidden ?? 0} symbols) is kept safe. Upgrade to use it again, or delete it from the ⋯ menu.
            <Link href="/billing" className="mt-2 block font-semibold text-amber-300 hover:underline">Unlock with Pro →</Link>
          </div>
        )}
        {active && !active.locked && (active.hidden ?? 0) > 0 && (
          <p className="px-3 py-2 text-[11px] text-amber-300">
            +{active.hidden} more symbol{active.hidden === 1 ? "" : "s"} hidden on your plan. <Link href="/billing" className="underline">Upgrade</Link>
          </p>
        )}
        {active && !active.locked && active.symbols.length === 0 && <p className="px-3 py-6 text-center text-sm text-muted">This watchlist is empty. Add a symbol above.</p>}
      </div>
    </div>
  );
}
