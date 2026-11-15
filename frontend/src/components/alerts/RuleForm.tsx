"use client";

import { useState } from "react";
import type { AlertRule, Channel, EventCatalog, Watchlist } from "@/lib/types";

export type RuleDraft = Omit<AlertRule, "id" | "created_at">;

const SEV_LABEL = { bull: "Bullish", bear: "Bearish / warnings", info: "Info & price levels" } as const;

export function emptyDraft(catalog: EventCatalog, symbol = ""): RuleDraft {
  return {
    name: symbol ? `${symbol} alerts` : "",
    scope: "symbol",
    symbol: symbol || null,
    watchlist_id: null,
    events: catalog.defaults,
    price_level: null,
    bull_threshold: 70,
    bear_threshold: 70,
    channels: ["app"],
    active: true,
  };
}

type Props = {
  catalog: EventCatalog;
  watchlists: Watchlist[];
  initial: RuleDraft;
  canMarketWide: boolean;
  submitLabel: string;
  onSubmit: (d: RuleDraft) => Promise<void>;
  onCancel?: () => void;
};

const field = "w-full rounded border border-line bg-bg px-2 py-1.5 text-sm outline-none focus:border-accent";

export default function RuleForm({ catalog, watchlists, initial, canMarketWide, submitLabel, onSubmit, onCancel }: Props) {
  const [d, setD] = useState<RuleDraft>(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof RuleDraft>(k: K, v: RuleDraft[K]) => setD((x) => ({ ...x, [k]: v }));

  const toggleEvent = (id: string) => set("events", d.events.includes(id) ? d.events.filter((e) => e !== id) : [...d.events, id]);
  const toggleChannel = (c: Channel) => set("channels", d.channels.includes(c) ? d.channels.filter((x) => x !== c) : [...d.channels, c]);
  const needsLevel = d.events.some((e) => e === "price_above" || e === "price_below");
  const needsScore = d.events.some((e) => e === "bull_score" || e === "bear_score");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!d.events.length) return setError("Pick at least one event.");
    setBusy(true);
    try {
      await onSubmit({ ...d, symbol: d.scope === "symbol" ? (d.symbol ?? "").trim().toUpperCase() : null });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <label className="block text-sm">
        <span className="mb-1 block text-muted">Rule name</span>
        <input required maxLength={80} value={d.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Breakouts in my watchlist" className={field} />
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block text-muted">Watch</span>
          <select value={d.scope} onChange={(e) => set("scope", e.target.value as RuleDraft["scope"])} className={field}>
            <option value="symbol">A single symbol</option>
            <option value="watchlist">A watchlist</option>
            <option value="universe" disabled={!canMarketWide}>
              Entire market{canMarketWide ? "" : " (Pro)"}
            </option>
          </select>
        </label>
        {d.scope === "symbol" && (
          <label className="block text-sm">
            <span className="mb-1 block text-muted">Symbol</span>
            <input required value={d.symbol ?? ""} onChange={(e) => set("symbol", e.target.value)} placeholder="AAPL" className={`${field} uppercase`} />
          </label>
        )}
        {d.scope === "watchlist" && (
          <label className="block text-sm">
            <span className="mb-1 block text-muted">Watchlist</span>
            <select required value={d.watchlist_id ?? ""} onChange={(e) => set("watchlist_id", Number(e.target.value) || null)} className={field}>
              <option value="">Choose…</option>
              {watchlists.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.symbols.length})
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <fieldset>
        <legend className="mb-2 text-sm text-muted">Alert me on</legend>
        <div className="space-y-3">
          {(["bull", "bear", "info"] as const).map((sev) => (
            <div key={sev}>
              <div className="mb-1 text-[11px] uppercase tracking-wide text-muted">{SEV_LABEL[sev]}</div>
              <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
                {catalog.events
                  .filter((ev) => ev.severity === sev)
                  .map((ev) => {
                    const locked = !canMarketWide && (ev.id === "bull_score" || ev.id === "bear_score");
                    return (
                      <label key={ev.id} title={ev.description} className={`flex items-center gap-2 text-sm ${locked ? "opacity-40" : "cursor-pointer"}`}>
                        <input type="checkbox" disabled={locked} checked={d.events.includes(ev.id) && !locked} onChange={() => toggleEvent(ev.id)} className="accent-blue-500" />
                        {ev.label}
                      </label>
                    );
                  })}
              </div>
            </div>
          ))}
        </div>
      </fieldset>

      {(needsLevel || needsScore) && (
        <div className="grid gap-3 sm:grid-cols-3">
          {needsLevel && (
            <label className="block text-sm">
              <span className="mb-1 block text-muted">Price level</span>
              <input type="number" step="0.01" min="0.01" required value={d.price_level ?? ""} onChange={(e) => set("price_level", e.target.value ? Number(e.target.value) : null)} className={field} />
            </label>
          )}
          {needsScore && (
            <>
              <label className="block text-sm">
                <span className="mb-1 block text-muted">Bull Score ≥</span>
                <input type="number" min={1} max={100} value={d.bull_threshold} onChange={(e) => set("bull_threshold", Number(e.target.value))} className={field} />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-muted">Bear Score ≥</span>
                <input type="number" min={1} max={100} value={d.bear_threshold} onChange={(e) => set("bear_threshold", Number(e.target.value))} className={field} />
              </label>
            </>
          )}
        </div>
      )}

      <fieldset>
        <legend className="mb-2 text-sm text-muted">Notify me via</legend>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2 opacity-70">
            <input type="checkbox" checked disabled className="accent-blue-500" /> In-app
          </label>
          {(["email", "telegram"] as const).map((c) => (
            <label key={c} className={`flex items-center gap-2 ${catalog.channels[c] ? "cursor-pointer" : "opacity-40"}`} title={catalog.channels[c] ? "" : "Not configured on the server yet"}>
              <input type="checkbox" disabled={!catalog.channels[c]} checked={d.channels.includes(c)} onChange={() => toggleChannel(c)} className="accent-blue-500" />
              {c === "email" ? "Email" : "Telegram"}
            </label>
          ))}
        </div>
      </fieldset>

      {error && <p className="rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
      <div className="flex gap-2">
        <button disabled={busy} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-60">
          {busy ? "Saving…" : submitLabel}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="rounded-md px-4 py-2 text-sm text-muted hover:text-text">
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
