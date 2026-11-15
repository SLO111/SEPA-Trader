"use client";

import Link from "next/link";
import type { AlertItem, Severity } from "@/lib/types";

const DOT: Record<Severity, string> = { bull: "bg-up", bear: "bg-down", info: "bg-accent" };
const FILTERS = [
  { id: "all", label: "All" },
  { id: "unread", label: "Unread" },
  { id: "bull", label: "Bullish" },
  { id: "bear", label: "Bearish" },
  { id: "info", label: "Info" },
] as const;
export type FeedFilter = (typeof FILTERS)[number]["id"];

function ago(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

type Props = {
  alerts: AlertItem[];
  filter: FeedFilter;
  onFilter: (f: FeedFilter) => void;
  onRead: (a: AlertItem) => void;
  onDelete: (a: AlertItem) => void;
  loading: boolean;
};

export default function AlertFeed({ alerts, filter, onFilter, onRead, onDelete, loading }: Props) {
  return (
    <section className="flex min-h-0 flex-col rounded-xl border border-line bg-panel">
      <div className="flex flex-wrap gap-1 border-b border-line p-2">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => onFilter(f.id)}
            className={`rounded px-3 py-1 text-sm ${filter === f.id ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}
          >
            {f.label}
          </button>
        ))}
      </div>
      <ul className="divide-y divide-line">
        {loading && <li className="p-8 text-center text-sm text-muted">Loading alerts…</li>}
        {!loading && alerts.length === 0 && (
          <li className="p-8 text-center text-sm text-muted">No alerts yet. Create a rule and alerts will show up here when it triggers.</li>
        )}
        {alerts.map((a) => (
          <li
            key={a.id}
            onClick={() => !a.read && onRead(a)}
            className={`group flex gap-3 px-4 py-3 ${a.read ? "" : "cursor-pointer bg-panel-2/50"}`}
          >
            <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${DOT[a.severity]} ${a.read ? "opacity-40" : ""}`} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <Link href={`/chart?s=${encodeURIComponent(a.symbol)}`} onClick={(e) => e.stopPropagation()} className="font-semibold hover:text-accent">
                  {a.symbol}
                </Link>
                <span className={a.read ? "text-muted" : "font-medium"}>{a.title}</span>
                <span className="ml-auto whitespace-nowrap text-xs text-muted" title={new Date(a.created_at).toLocaleString("en-US")}>
                  {ago(a.created_at)}
                </span>
              </div>
              <p className="mt-0.5 text-sm text-muted">{a.message}</p>
              <div className="mt-1 flex items-center gap-3 text-[11px] text-muted">
                <span className="rounded bg-line/60 px-1.5 py-0.5">{a.type_label}</span>
                <span>Bar {a.bar_date}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(a);
                  }}
                  className="invisible ml-auto hover:text-down group-hover:visible"
                >
                  Delete
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
