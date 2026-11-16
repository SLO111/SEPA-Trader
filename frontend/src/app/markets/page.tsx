"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { EarningsTab, ExtendedTab, FearGreedTab, FedTab, ScreenerTab } from "@/components/markets/OtherTabs";
import Heatmap from "@/components/markets/Heatmap";
import OverviewTab from "@/components/markets/OverviewTab";
import type { Overview } from "@/components/markets/types";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "heatmap", label: "Heatmap" },
  { id: "fear-greed", label: "Fear & Greed" },
  { id: "earnings", label: "Earnings calendar" },
  { id: "extended", label: "Pre & after hours" },
  { id: "fed", label: "Fed monitor" },
  { id: "screener", label: "Screener" },
] as const;
type TabId = (typeof TABS)[number]["id"];

function Markets() {
  const { user } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const initial = (params.get("tab") as TabId) || "overview";
  const [tab, setTabState] = useState<TabId>(TABS.some((t) => t.id === initial) ? initial : "overview");
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
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
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
          (error ? <p className="text-sm text-down">{error}</p> : overview ? <OverviewTab o={overview} onFearGreed={() => setTab("fear-greed")} /> : <p className="text-sm text-muted">Loading market data…</p>)}
        {tab === "heatmap" && <Heatmap />}
        {tab === "fear-greed" && <FearGreedTab />}
        {tab === "earnings" && <EarningsTab />}
        {tab === "extended" && <ExtendedTab />}
        {tab === "fed" && <FedTab />}
        {tab === "screener" && <ScreenerTab allowed={!!user?.limits.move_detector} />}
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
