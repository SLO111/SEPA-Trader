"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type FeedPop = { id: number; kind: string; symbol: string | null; severity: string; title: string; url: string | null };
type AlertPop = { id: number; symbol: string | null; severity: string; title: string };
type Popups = { feed_last: number; alert_last: number; feed: FeedPop[]; alerts: AlertPop[] };
type Toast = { key: string; label: string; title: string; href: string; tone: string };

const KEY = "vn_popups_seen";
const KIND: Record<string, string> = {
  earnings: "Earnings", mover: "Big mover", breakout: "Breakout", high: "New high", news: "News", idea: "Trade idea",
  summary: "Daily summary", letter: "Weekly letter",
};
const TONE: Record<string, string> = { bull: "border-l-up", bear: "border-l-down" };

function readSeen(): { feed?: number; alert?: number } {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}");
  } catch {
    return {};
  }
}

/** Pop-ups for new feed items and alerts while you are anywhere in the app except the Feed (where you see them anyway).
 *  Checked every minute; what pops up follows Settings → Notifications. */
export default function NotificationToasts() {
  const pathname = usePathname();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const onFeed = useRef(false);
  onFeed.current = pathname.startsWith("/feed");

  useEffect(() => {
    let stop = false;
    const check = async () => {
      if (document.hidden) return;
      const seen = readSeen();
      const q = new URLSearchParams();
      if (seen.feed !== undefined) q.set("feed_after", String(seen.feed));
      if (seen.alert !== undefined) q.set("alert_after", String(seen.alert));
      let r: Popups;
      try {
        r = await api<Popups>(`/api/notifications/popups?${q}`);
      } catch {
        return;
      }
      if (stop) return;
      try {
        localStorage.setItem(KEY, JSON.stringify({ feed: r.feed_last, alert: r.alert_last }));
      } catch {
        /* storage unavailable */
      }
      const fresh: Toast[] = [
        ...r.alerts.map((a) => ({ key: `a${a.id}`, label: `Alert${a.symbol ? ` · ${a.symbol}` : ""}`, title: a.title, href: "/alerts", tone: TONE[a.severity] ?? "border-l-accent" })),
        ...(onFeed.current ? [] : r.feed).map((f) => ({
          key: `f${f.id}`, label: `${KIND[f.kind] ?? "Feed"}${f.symbol ? ` · ${f.symbol}` : ""}`, title: f.title,
          href: f.symbol && f.kind !== "news" ? `/chart?s=${encodeURIComponent(f.symbol)}` : "/feed", tone: TONE[f.severity] ?? "border-l-accent",
        })),
      ];
      if (fresh.length) setToasts((t) => [...fresh, ...t].slice(0, 30));
    };
    check();
    const id = setInterval(check, 60_000);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, []);

  // every pop-up closes by itself 6 seconds after it appears on screen (unless the mouse is over it)
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const [hover, setHover] = useState(false);
  useEffect(() => {
    if (!toasts.length && hover) setHover(false); // the last one was clicked away while the mouse was on it
    const visible = new Set(toasts.slice(0, 3).map((t) => t.key));
    timers.current.forEach((id, key) => {
      if (!visible.has(key) || hover) {
        clearTimeout(id);
        timers.current.delete(key);
      }
    });
    if (hover) return;
    visible.forEach((key) => {
      if (!timers.current.has(key)) {
        timers.current.set(key, setTimeout(() => {
          timers.current.delete(key);
          setToasts((x) => x.filter((t) => t.key !== key));
        }, 6000));
      }
    });
  }, [toasts, hover]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  if (!toasts.length) return null;
  const shown = toasts.slice(0, 3);
  const close = (key: string) => setToasts((t) => t.filter((x) => x.key !== key));
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2" aria-live="polite"
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      {shown.map((t) => (
        <div key={t.key} className={`pointer-events-auto flex items-start gap-2 rounded-lg border border-line border-l-4 ${t.tone} bg-panel p-3 shadow-xl`}>
          <Link href={t.href} onClick={() => close(t.key)} className="min-w-0 flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">{t.label}</div>
            <div className="mt-0.5 line-clamp-2 text-sm text-text">{t.title}</div>
          </Link>
          <button onClick={() => close(t.key)} className="text-muted hover:text-text" aria-label="Dismiss">✕</button>
        </div>
      ))}
      {toasts.length > 3 && (
        <button onClick={() => setToasts([])} className="pointer-events-auto self-end rounded-full bg-panel-2 px-3 py-1 text-xs text-muted hover:text-text">
          +{toasts.length - 3} more · dismiss all
        </button>
      )}
    </div>
  );
}
