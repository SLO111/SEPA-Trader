"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import { EarningsTab, FearGreedTab, FedTab, ScreenerTab } from "@/components/markets/OtherTabs";
import LazySection from "@/components/LazySection";
import Heatmap from "@/components/markets/Heatmap";
import GroupsTab from "@/components/markets/GroupsTab";
import OverviewTab from "@/components/markets/OverviewTab";
import type { Overview } from "@/components/markets/types";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "heatmap", label: "Heatmap" },
  { id: "screener", label: "Screener" },
  { id: "groups", label: "Groups" },
] as const;
type TabId = (typeof TABS)[number]["id"];
// Old tab links now point to a section of the Overview, or to a Screener preset.
const LEGACY: Record<string, { tab: TabId; section?: string; preset?: string }> = {
  "fear-greed": { tab: "overview", section: "fear-greed" },
  earnings: { tab: "overview", section: "earnings" },
  fed: { tab: "overview", section: "fed" },
  extended: { tab: "screener", preset: "pre-market" },
};

function scrollToSection(id: string) {
  // sections above load as they come into view and grow, so settle the position again shortly after
  for (const ms of [50, 900, 1800]) setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: ms === 50 ? "smooth" : "auto", block: "start" }), ms);
}

function Markets() {
  const { user } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const raw = params.get("tab") || "overview";
  const legacy = LEGACY[raw];
  const initial: TabId = legacy?.tab ?? (TABS.some((t) => t.id === raw) ? (raw as TabId) : "overview");
  const [tab, setTabState] = useState<TabId>(initial);
  const [preset] = useState(legacy?.preset ?? params.get("preset") ?? "undervalued");

  useEffect(() => {
    if (legacy?.section) {
      window.location.hash = legacy.section;
      scrollToSection(legacy.section);
    }
  }, [legacy]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  const setTab = (t: TabId) => {
    setTabState(t);
    router.replace(`/markets?tab=${t}`, { scroll: false });
  };

  useEffect(() => {
    if (tab !== "overview") return;
    const load = () => api<Overview>("/api/markets/overview").then(setOverview).catch((e) => setError(e.message));
    if (!overview) load();
    const id = setInterval(load, 120_000);
    return () => clearInterval(id);
  }, [tab, overview]);

  // Overview sections menu (pinned under the tabs) that follows the scroll position.
  const scroller = useRef<HTMLDivElement>(null);
  const SECTIONS = [
    ["ov-overview", "Overview"],
    ["ov-cycle", "Market cycle"],
    ["fear-greed", "Fear & Greed"],
    ["earnings", "Earnings calendar"],
    ["fed", "Fed monitor"],
  ] as const;
  const [section, setSection] = useState<string>("ov-overview");
  useEffect(() => {
    const root = scroller.current;
    if (!root || tab !== "overview" || !overview) return;
    const io = new IntersectionObserver(
      (es) => {
        const vis = es.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (vis[0]) setSection(vis[0].target.id);
      },
      { root, rootMargin: "-140px 0px -60% 0px" },
    );
    SECTIONS.forEach(([id]) => {
      const el = document.getElementById(id);
      if (el) io.observe(el);
    });
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, overview]);

  return (
    <div ref={scroller} className="h-full overflow-y-auto">
      <div className={`mx-auto px-3 pb-6 pt-3 sm:px-6 sm:pt-6 ${tab === "heatmap" ? "max-w-none" : "max-w-7xl"}`}>
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-xl font-semibold">Markets</h1>
          {overview?.demo && <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs text-amber-200">Demo data</span>}
        </div>
        <div className="sticky top-0 z-20 -mx-3 mb-5 bg-bg/95 px-3 backdrop-blur sm:-mx-6 sm:px-6">
          <nav className="flex gap-1 overflow-x-auto border-b border-line">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${tab === t.id ? "border-accent text-text" : "border-transparent text-muted hover:text-text"}`}
              >
                {t.label}
              </button>
            ))}
          </nav>
          {tab === "overview" && overview && (
            <nav className="flex gap-1 overflow-x-auto border-b border-line py-1.5">
              {SECTIONS.map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => {
                    setSection(id);
                    scrollToSection(id);
                  }}
                  className={`whitespace-nowrap rounded-full px-3 py-1 text-xs ${section === id ? "bg-accent text-white" : "text-muted hover:bg-panel-2 hover:text-text"}`}
                >
                  {label}
                </button>
              ))}
            </nav>
          )}
        </div>
        {tab === "overview" &&
          (error ? (
            <p className="text-sm text-down">{error}</p>
          ) : overview ? (
            <div className="space-y-8">
              <div id="ov-overview" className="scroll-mt-28">
                <OverviewTab o={overview} onFearGreed={() => scrollToSection("fear-greed")} />
              </div>
              <section>
                <h2 className="mb-3 text-lg font-semibold">Fear &amp; Greed</h2>
                <LazySection id="fear-greed"><FearGreedTab /></LazySection>
              </section>
              <section>
                <h2 className="mb-3 text-lg font-semibold">Earnings calendar</h2>
                <LazySection id="earnings"><EarningsTab /></LazySection>
              </section>
              <section>
                <h2 className="mb-3 text-lg font-semibold">Fed monitor</h2>
                <LazySection id="fed"><FedTab /></LazySection>
              </section>
            </div>
          ) : (
            <p className="text-sm text-muted">Loading market data…</p>
          ))}
        {tab === "heatmap" && <Heatmap />}
        {tab === "screener" && <ScreenerTab allowed={!!user?.limits.move_detector} initialPreset={preset} />}
        {tab === "groups" && <GroupsTab allowed={!!user?.limits.industry_groups} />}
        <p className="mt-6 text-xs text-muted">For educational purposes only. Not financial advice.</p>
      </div>
    </div>
  );
}

export default function MarketsPage() {
  return (
    <AppShell>
      <Suspense fallback={null}>
        <Markets />
      </Suspense>
    </AppShell>
  );
}
