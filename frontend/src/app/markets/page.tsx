"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { EarningsTab, FearGreedTab, FedTab, ScreenerTab } from "@/components/markets/OtherTabs";
import LazySection from "@/components/LazySection";
import Heatmap from "@/components/markets/Heatmap";
import OverviewTab from "@/components/markets/OverviewTab";
import type { Overview } from "@/components/markets/types";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "heatmap", label: "Heatmap" },
  { id: "screener", label: "Screener" },
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

  return (
    <div className="h-full overflow-y-auto">
      <div className={`mx-auto p-3 sm:p-6 ${tab === "heatmap" ? "max-w-none" : "max-w-7xl"}`}>
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-xl font-semibold">Markets</h1>
          {overview?.demo && <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs text-amber-200">Demo data</span>}
        </div>
        <nav className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
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
        {tab === "overview" &&
          (error ? (
            <p className="text-sm text-down">{error}</p>
          ) : overview ? (
            <div className="space-y-8">
              <OverviewTab o={overview} onFearGreed={() => scrollToSection("fear-greed")} />
              <nav className="flex flex-wrap gap-2 text-sm">
                {[
                  ["fear-greed", "Fear & Greed"],
                  ["earnings", "Earnings calendar"],
                  ["fed", "Fed monitor"],
                ].map(([id, label]) => (
                  <button key={id} onClick={() => scrollToSection(id)} className="rounded-full border border-line px-3 py-1 text-muted hover:border-accent hover:text-text">
                    {label} ↓
                  </button>
                ))}
              </nav>
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
