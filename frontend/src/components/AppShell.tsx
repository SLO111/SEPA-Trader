"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Logo from "./Logo";
import SymbolSearch from "./SymbolSearch";
import { useAuth } from "@/lib/auth";

// Compact navigation: related pages share one top-level hub with sub-tabs.
const NAV: { label: string; tabs: { href: string; label: string; hidden?: boolean }[] }[] = [
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
  { label: "Portfolio", tabs: [{ href: "/portfolios", label: "Portfolios" }, { href: "/journal", label: "Journal", hidden: true }] },
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

export { Logo };

export default function AppShell({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);
  const [menu, setMenu] = useState(false);
  useEffect(() => setMenu(false), [pathname]);

  // After a new deploy an open tab may ask for files of the old version: reload once to get the new one.
  useEffect(() => {
    const stale = (msg: string) => /ChunkLoadError|Loading chunk|Failed to fetch dynamically imported module|importing a module script failed/i.test(msg);
    const reloadOnce = (msg: string) => {
      if (!stale(msg)) return;
      try {
        if (sessionStorage.getItem("vn_reloaded")) return;
        sessionStorage.setItem("vn_reloaded", "1");
      } catch {
        /* ignore */
      }
      window.location.reload();
    };
    const onError = (e: ErrorEvent) => reloadOnce(String(e.message || e.error));
    const onRejection = (e: PromiseRejectionEvent) => reloadOnce(String(e.reason?.message ?? e.reason));
    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    const t = setTimeout(() => {
      try {
        sessionStorage.removeItem("vn_reloaded");
      } catch {
        /* ignore */
      }
    }, 10_000);
    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
      clearTimeout(t);
    };
  }, []);

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
      <header className="relative flex h-12 shrink-0 items-center gap-3 border-b border-line bg-panel px-3 lg:gap-6 lg:px-4">
        <button
          onClick={() => setMenu((m) => !m)}
          className="grid h-8 w-8 place-items-center rounded text-muted hover:bg-panel-2 hover:text-text lg:hidden"
          aria-label="Menu"
          aria-expanded={menu}
        >
          {menu ? "✕" : "☰"}
          {!menu && unread > 0 && <span className="absolute left-8 top-2 h-2 w-2 rounded-full bg-down" />}
        </button>
        <span className="hidden sm:block">
          <Logo href="/chart" />
        </span>
        <span className="sm:hidden">
          <Logo href="/chart" compact />
        </span>
        <nav className="hidden min-w-0 items-center gap-1 overflow-x-auto text-sm lg:flex">
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
        <div className="ml-auto flex min-w-0 items-center gap-3 text-sm">
          <SymbolSearch />
          <Link href="/billing" title="Plans & billing" className={`hidden rounded px-2 py-0.5 text-xs font-medium hover:opacity-80 sm:inline ${PLAN_STYLE[user.plan]}`}>{user.limits.label}</Link>
          <span className="hidden max-w-[10rem] truncate text-muted xl:inline">{user.name || user.email}</span>
          <button
            onClick={() => {
              logout();
              router.replace("/");
            }}
            className="hidden whitespace-nowrap rounded px-2 py-1 text-muted hover:bg-panel-2 hover:text-text lg:block"
          >
            Log out
          </button>
        </div>
        {menu && (
          <div className="absolute inset-x-0 top-12 z-50 border-b border-line bg-panel p-3 shadow-2xl lg:hidden">
            <nav className="grid gap-1 text-base">
              {[...NAV.flatMap((n) => n.tabs.filter((t) => !t.hidden).map((t) => ({ ...t, group: n.label }))), ...(user.role === "admin" ? [{ href: "/admin", label: "Admin", group: "Admin" }] : [])].map((t) => (
                <Link
                  key={t.href}
                  href={t.href}
                  className={`flex items-center justify-between rounded-lg px-3 py-2.5 ${pathname.startsWith(t.href) ? "bg-panel-2 text-text" : "text-muted"}`}
                >
                  <span>{t.label}</span>
                  {t.href === "/alerts" && unread > 0 && <span className="rounded-full bg-down px-2 text-xs text-white">{unread}</span>}
                  {t.label !== t.group && <span className="text-xs text-muted/70">{t.group}</span>}
                </Link>
              ))}
            </nav>
            <div className="mt-3 flex items-center justify-between border-t border-line pt-3 text-sm">
              <span className="truncate text-muted">{user.name || user.email}</span>
              <span className="flex items-center gap-2">
                <Link href="/billing" className={`rounded px-2 py-0.5 text-xs font-medium ${PLAN_STYLE[user.plan]}`}>{user.limits.label}</Link>
                <button
                  onClick={() => {
                    logout();
                    router.replace("/");
                  }}
                  className="rounded border border-line px-3 py-1 text-muted"
                >
                  Log out
                </button>
              </span>
            </div>
          </div>
        )}
      </header>
      {hub && hub.tabs.filter((t) => !t.hidden).length > 1 && (
        <div className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-line bg-panel/60 px-2 text-sm md:px-4">
          {hub.tabs.filter((t) => !t.hidden).map((t) => (
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
