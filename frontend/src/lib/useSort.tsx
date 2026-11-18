"use client";

import { useMemo, useState } from "react";

type Getter<T> = (row: T) => number | string | null | undefined;

/** Client-side column sorting. First click: largest first (A→Z for text); a second click reverses.
 *  Empty values always go last. */
export function useSort<T, G extends Record<string, Getter<T>>>(rows: T[] | null | undefined, getters: G, defaultKey: keyof G & string, defaultDir: 1 | -1 = -1) {
  type K = keyof G & string;
  const [sort, setSort] = useState<{ key: K; dir: 1 | -1 }>({ key: defaultKey, dir: defaultDir });
  const sorted = useMemo(() => {
    const get = getters[sort.key];
    return [...(rows ?? [])].sort((a, b) => {
      const x = get(a), y = get(b);
      if (x === null || x === undefined) return y === null || y === undefined ? 0 : 1;
      if (y === null || y === undefined) return -1;
      if (typeof x === "string" && typeof y === "string") return x.localeCompare(y) * sort.dir;
      return ((x as number) - (y as number)) * sort.dir;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, sort]);
  const click = (key: K, textKey = false) =>
    setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: textKey ? 1 : -1 }));
  return { sorted, sort, click, resetKey: `${sort.key}|${sort.dir}` };
}

/** A clickable column header showing ▲ / ▼ on the active column. */
export function SortTh<K extends string>({ k, label, sort, onClick, right = false, className = "", title, text = false }: {
  k: K; label: string; sort: { key: K; dir: 1 | -1 }; onClick: (k: K, text?: boolean) => void; right?: boolean; className?: string;
  title?: string; text?: boolean;
}) {
  return (
    <th className={`${right ? "text-right" : ""} ${className}`} title={title}>
      <button onClick={() => onClick(k, text)} className={`inline-flex items-center gap-1 uppercase tracking-wide hover:text-text ${sort.key === k ? "text-text" : ""}`}>
        {label}
        <span className="w-2 text-[9px]">{sort.key === k ? (sort.dir === 1 ? "▲" : "▼") : ""}</span>
      </button>
    </th>
  );
}
