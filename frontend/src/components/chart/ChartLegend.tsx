"use client";

import { useState } from "react";
import type { ActiveStrategy, StrategyDef } from "@/lib/types";

type Props = {
  active: ActiveStrategy[];
  defs: StrategyDef[];
  onChange: (next: ActiveStrategy[]) => void;
  header?: React.ReactNode; // OHLC line shown above the indicators
  values?: Record<string, string>; // indicator values under the crosshair, by uid
};

function summary(a: ActiveStrategy, d?: StrategyDef) {
  if (!d) return "";
  return d.params
    .map((p) => (p.type === "select" ? p.options?.find(([v]) => v === (a.params[p.key] ?? p.default))?.[1] : String(a.params[p.key] ?? p.default)))
    .filter((x) => x && x !== "No")
    .join(" ");
}

/** Active indicators shown over the chart (like TradingView's legend): settings, hide and remove. */
export default function ChartLegend({ active, defs, onChange, header, values = {} }: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  if (!active.length && !header) return null;
  const update = (uid: string, patch: Partial<ActiveStrategy>) => onChange(active.map((a) => (a.uid === uid ? { ...a, ...patch } : a)));

  return (
    <div className="pointer-events-none absolute left-2 top-2 z-10 flex max-w-[70%] flex-col gap-1">
      {header}
      {active.map((a) => {
        const d = defs.find((x) => x.id === a.id);
        return (
          <div key={a.uid} className="pointer-events-auto">
            <div className={`group inline-flex items-center gap-2 rounded bg-bg/70 px-2 py-0.5 text-xs backdrop-blur ${a.hidden ? "opacity-50" : ""}`}>
              <span className="text-text">{d?.name ?? a.id}</span>
              <span className="tabular hidden text-muted sm:inline">{summary(a, d)}</span>
              {values[a.uid] && <span className="tabular hidden text-text/90 sm:inline">{values[a.uid]}</span>}
              <span className="flex gap-1 opacity-60 group-hover:opacity-100">
                <button title={a.hidden ? "Show" : "Hide"} onClick={() => update(a.uid, { hidden: !a.hidden })} className="px-0.5 hover:text-accent">
                  {a.hidden ? "◌" : "◉"}
                </button>
                {d && d.params.length > 0 && (
                  <button title="Settings" onClick={() => setEditing(editing === a.uid ? null : a.uid)} className="px-0.5 hover:text-accent">
                    ⚙
                  </button>
                )}
                <button title="Remove" onClick={() => onChange(active.filter((x) => x.uid !== a.uid))} className="px-0.5 hover:text-down">
                  ✕
                </button>
              </span>
            </div>
            {editing === a.uid && d && (
              <div className="mt-1 w-64 rounded-lg border border-line bg-panel p-3 shadow-xl">
                <div className="mb-2 text-xs font-medium">{d.name}: settings</div>
                <div className="grid grid-cols-2 gap-2">
                  {d.params.map((p) => (
                    <label key={p.key} className="text-[11px] text-muted">
                      {p.label}
                      {p.type === "select" ? (
                        <select
                          value={a.params[p.key] ?? p.default}
                          onChange={(e) => update(a.uid, { params: { ...a.params, [p.key]: Number(e.target.value) } })}
                          className="mt-0.5 w-full rounded border border-line bg-bg px-1.5 py-1 text-xs text-text"
                        >
                          {p.options?.map(([v, label]) => (
                            <option key={v} value={v}>
                              {label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="number"
                          min={p.min}
                          max={p.max}
                          step={p.step}
                          value={a.params[p.key] ?? p.default}
                          onChange={(e) => update(a.uid, { params: { ...a.params, [p.key]: Number(e.target.value) } })}
                          className="tabular mt-0.5 w-full rounded border border-line bg-bg px-1.5 py-1 text-xs text-text"
                        />
                      )}
                    </label>
                  ))}
                </div>
                <button onClick={() => setEditing(null)} className="mt-3 w-full rounded bg-panel-2 py-1 text-xs hover:bg-line">
                  Done
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
