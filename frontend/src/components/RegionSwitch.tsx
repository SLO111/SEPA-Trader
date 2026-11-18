"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export type Region = "US" | "EU" | "ASIA";
type RegionInfo = { id: Region; name: string; stocks: number };

const LABEL: Record<Region, string> = { US: "🇺🇸 US", EU: "🇪🇺 Europe", ASIA: "🌏 Asia" };
const KEY = "vn_region";

/** The region the user is looking at (US by default), shared by Screener, Move Detector, Signals and Pulse. */
export function useRegion(): [Region, (r: Region) => void, RegionInfo[]] {
  const [regions, setRegions] = useState<RegionInfo[]>([]);
  const [region, setRegionState] = useState<Region>("US");
  useEffect(() => {
    api<{ regions: RegionInfo[] }>("/api/markets/regions")
      .then((r) => {
        setRegions(r.regions);
        try {
          const saved = localStorage.getItem(KEY) as Region | null;
          if (saved && r.regions.some((x) => x.id === saved)) setRegionState(saved);
        } catch {
          /* storage unavailable */
        }
      })
      .catch(() => {});
  }, []);
  const setRegion = (r: Region) => {
    setRegionState(r);
    try {
      localStorage.setItem(KEY, r);
    } catch {
      /* storage unavailable */
    }
  };
  return [region, setRegion, regions];
}

/** US / Europe / Asia pills; hidden when the server scans only the US. */
export default function RegionSwitch({ region, onChange, regions }: { region: Region; onChange: (r: Region) => void; regions: RegionInfo[] }) {
  if (regions.length < 2) return null;
  return (
    <div className="inline-flex gap-1 rounded-lg bg-panel p-1" role="tablist" aria-label="Region">
      {regions.map((r) => (
        <button
          key={r.id}
          role="tab"
          aria-selected={region === r.id}
          onClick={() => onChange(r.id)}
          title={`${r.name}: ${r.stocks} stocks`}
          className={`rounded-md px-3 py-1 text-sm ${region === r.id ? "bg-accent text-white" : "text-muted hover:text-text"}`}
        >
          {LABEL[r.id]}
        </button>
      ))}
    </div>
  );
}

/** "€" style suffix for prices in a currency other than the US dollar. */
export function CurrencyTag({ currency }: { currency?: string | null }) {
  if (!currency || currency === "USD") return null;
  return <span className="ml-1 text-[10px] text-muted">{currency === "GBp" ? "GBX" : currency}</span>;
}
