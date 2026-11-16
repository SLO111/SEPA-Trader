"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import SymbolSearch from "./SymbolSearch";
import { useAuth } from "@/lib/auth";

// Compact navigation: related pages share one top-level hub with sub-tabs.
const NAV: { label: string; tabs: { href: string; label: string }[] }[] = [
  { label: "Charts", tabs: [{ href: "/chart", label: "Charts" }] },
  { label: "Markets", tabs: [{ href: "/markets", label: "Markets" }] },
  {
    label: "Signals",
    tabs: [
      { href: "/ideas", label: "Trade ideas" },
      { href: "/scanner", label: "Move Detector" },
      { href: "/backtest", label: "Backtest" },
    ],
  },
  {
    label: "Portfolio",
    tabs: [
      { href: "/portfolios", label: "Portfolios" },
      { href: "/journal", label: "Journal & Trade Review" },
    ],
  },
  {
    label: "Alerts",
    tabs: [
      { href: "/feed", label: "Feed" },
      { href: "/alerts", label: "My alerts" },
    ],
  },
];

const PLAN_STYLE: Record<string, string> = {
  free: "bg-slate-700/60 text-slate-200",
  pro: "bg-blue-600/30 text-blue-300",
  premium: "bg-amber-500/25 text-amber-300",
};

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <span className="grid h-7 w-7 place-items-center rounded-md bg-accent text-sm font-bold text-white">S</span>
      <span>SEPA Trader</span>
    </Link>
  );
}

export default function AppShell({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!user) return;
    const load = () => api<{ count: number }>("/api/alerts/unread-count").then((r) => setUnread(r.count)).catch(() => {});
    load();
    const id = setInterval(load, 60_000);
    window.addEventListener("alerts-changed", load);
    return () => {
      clearInterval(id);
      window.removeEventListener("alerts-changed", load);
    };
  }, [user]);

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (adminOnly && user.role !== "admin") router.replace("/chart");
  }, [user, loading, adminOnly, router]);

  const hub = NAV.find((n) => n.tabs.some((t) => pathname.startsWith(t.href)));

  if (loading || !user || (adminOnly && user.role !== "admin")) {
    return <div className="grid h-screen place-items-center text-muted">Loading…</div>;
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-12 shrink-0 items-center gap-6 border-b border-line bg-panel px-4">
        <Logo />
        <nav className="flex min-w-0 items-center gap-1 overflow-x-auto text-sm">
          {NAV.map((n) => {
            const on = n.tabs.some((t) => pathname.startsWith(t.href));
            return (
              <Link
                key={n.label}
                href={n.tabs[0].href}
                className={`whitespace-nowrap rounded px-3 py-1.5 ${on ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}
              >
                {n.label}
                {n.label === "Alerts" && unread > 0 && (
                  <span className="tabular ml-1.5 rounded-full bg-down px-1.5 py-0.5 text-[10px] font-semibold text-white">{unread > 99 ? "99+" : unread}</span>
                )}
              </Link>
            );
          })}
          {user.role === "admin" && (
            <Link
              href="/admin"
              className={`whitespace-nowrap rounded px-3 py-1.5 ${pathname.startsWith("/admin") ? "bg-panel-2 text-text" : "text-muted hover:text-text"}`}
            >
              Admin
            </Link>
          )}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <SymbolSearch />
          <Link href="/billing" title="Plans & billing" className={`rounded px-2 py-0.5 text-xs font-medium hover:opacity-80 ${PLAN_STYLE[user.plan]}`}>{user.limits.label}</Link>
          <span className="hidden text-muted sm:inline">{user.name || user.email}</span>
          <button
            onClick={() => {
              logout();
              router.replace("/");
            }}
            className="rounded px-2 py-1 text-muted hover:bg-panel-2 hover:text-text"
          >
            Log out
          </button>
        </div>
      </header>
      {hub && hub.tabs.length > 1 && (
        <div className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-line bg-panel/60 px-4 text-sm">
          {hub.tabs.map((t) => (
            <Link
              key={t.href}
              href={t.href}
              className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 ${pathname.startsWith(t.href) ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}
            >
              {t.label}
            </Link>
          ))}
        </div>
      )}
      <main className="min-h-0 flex-1">{children}</main>
    </div>
  );
}
