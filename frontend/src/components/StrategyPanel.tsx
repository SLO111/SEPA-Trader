"use client";

import { useMemo, useState } from "react";
import type { ActiveStrategy, StrategyDef } from "@/lib/types";

type Props = {
  defs: StrategyDef[];
  active: ActiveStrategy[];
  onChange: (next: ActiveStrategy[]) => void;
  max: number;
  features: Record<string, unknown>;
};

export default function StrategyPanel({ defs, active, onChange, max, features }: Props) {
  const [q, setQ] = useState("");
  const activeMap = useMemo(() => new Map(active.map((a) => [a.id, a])), [active]);

  const grouped = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const groups = new Map<string, StrategyDef[]>();
    for (const d of defs) {
      if (needle && !`${d.name} ${d.category} ${d.description}`.toLowerCase().includes(needle)) continue;
      groups.set(d.category, [...(groups.get(d.category) ?? []), d]);
    }
    return [...groups.entries()];
  }, [defs, q]);

  const toggle = (d: StrategyDef) => {
    if (activeMap.has(d.id)) return onChange(active.filter((a) => a.id !== d.id));
    onChange([...active, { id: d.id, params: Object.fromEntries(d.params.map((p) => [p.key, p.default])) }]);
  };

  const setParam = (id: string, key: string, value: number) =>
    onChange(active.map((a) => (a.id === id ? { ...a, params: { ...a.params, [key]: value } } : a)));

  const atLimit = active.length >= max;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line p-3">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold">Strategii & indicatori</h2>
          <span className="tabular text-xs text-muted">
            {active.length}/{max >= 1e6 ? "∞" : max} active
          </span>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Caută strategie…"
          className="w-full rounded border border-line bg-bg px-2 py-1.5 text-sm outline-none focus:border-accent"
        />
        {atLimit && max < 1e6 && <p className="mt-2 text-xs text-amber-300">Ai atins limita planului. Fă upgrade pentru mai multe strategii simultan.</p>}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto pb-4">
        {grouped.map(([cat, items]) => (
          <section key={cat} className="pt-3">
            <h3 className="px-3 pb-1 text-[11px] uppercase tracking-wide text-muted">{cat}</h3>
            {items.map((d) => {
              const a = activeMap.get(d.id);
              const planLocked = !!d.requires && !features[d.requires];
              const disabled = (!a && atLimit) || planLocked;
              return (
                <div key={d.id} className={`px-3 py-1.5 ${a ? "bg-panel-2/70" : ""}`}>
                  <label className={`flex items-start gap-2 text-sm ${disabled ? "opacity-40" : "cursor-pointer"}`} title={d.description}>
                    <input type="checkbox" checked={!!a} disabled={disabled} onChange={() => toggle(d)} className="mt-0.5 accent-blue-500" />
                    <span>
                      {d.name}
                      {planLocked && <span className="ml-2 rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-medium text-amber-300">PRO</span>}
                      {d.description && <span className="block text-xs text-muted">{d.description}</span>}
                    </span>
                  </label>
                  {a && d.params.length > 0 && (
                    <div className="mt-2 grid grid-cols-3 gap-2 pl-6">
                      {d.params.map((p) => (
                        <label key={p.key} className="text-[11px] text-muted">
                          {p.label}
                          <input
                            type="number"
                            min={p.min}
                            max={p.max}
                            step={p.step}
                            value={a.params[p.key] ?? p.default}
                            onChange={(e) => setParam(d.id, p.key, Number(e.target.value))}
                            className="tabular mt-0.5 w-full rounded border border-line bg-bg px-1.5 py-1 text-xs text-text outline-none focus:border-accent"
                          />
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </section>
        ))}
        {grouped.length === 0 && <p className="px-3 py-6 text-center text-sm text-muted">Nicio strategie găsită.</p>}
      </div>
    </div>
  );
}
