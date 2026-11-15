"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import AlertFeed, { type FeedFilter } from "@/components/alerts/AlertFeed";
import NotificationsCard from "@/components/alerts/NotificationsCard";
import RuleForm, { emptyDraft, type RuleDraft } from "@/components/alerts/RuleForm";
import { api, del, post, put } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AlertItem, AlertRule, EventCatalog, Watchlist } from "@/lib/types";

function scopeText(r: AlertRule, wls: Watchlist[]) {
  if (r.scope === "symbol") return r.symbol;
  if (r.scope === "watchlist") return `Watchlist: ${wls.find((w) => w.id === r.watchlist_id)?.name ?? "—"}`;
  return "Entire market";
}

function AlertsWorkspace() {
  const { user } = useAuth();
  const params = useSearchParams();
  const prefill = (params.get("symbol") ?? "").toUpperCase();
  const canAlerts = !!user?.limits.alerts;
  const canMarketWide = !!user?.limits.move_detector;

  const [filter, setFilter] = useState<FeedFilter>("all");
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [catalog, setCatalog] = useState<EventCatalog | null>(null);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [editing, setEditing] = useState<AlertRule | "new" | null>(prefill ? "new" : null);
  const [status, setStatus] = useState("");

  const loadAlerts = useCallback(() => {
    api<AlertItem[]>(`/api/alerts?filter=${filter}`)
      .then(setAlerts)
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    loadAlerts();
    const id = setInterval(loadAlerts, 60_000);
    return () => clearInterval(id);
  }, [loadAlerts]);

  useEffect(() => {
    api<EventCatalog>("/api/alerts/event-types").then(setCatalog).catch(() => {});
    api<AlertRule[]>("/api/alert-rules").then(setRules).catch(() => {});
    api<Watchlist[]>("/api/watchlists").then(setWatchlists).catch(() => {});
  }, []);

  const notifyBadge = () => window.dispatchEvent(new Event("alerts-changed"));

  const checkNow = async () => {
    setStatus("Checking…");
    try {
      const r = await post<{ created: number }>("/api/alerts/check-now", {});
      setStatus(r.created ? `${r.created} new alert${r.created > 1 ? "s" : ""}.` : "No new alerts right now.");
      loadAlerts();
      notifyBadge();
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Error");
    }
  };

  const markAll = async () => {
    await post("/api/alerts/read-all", {});
    loadAlerts();
    notifyBadge();
  };

  const saveRule = async (d: RuleDraft) => {
    if (editing && editing !== "new") {
      const r = await put<AlertRule>(`/api/alert-rules/${editing.id}`, d);
      setRules((rs) => rs.map((x) => (x.id === r.id ? r : x)));
    } else {
      const r = await post<AlertRule>("/api/alert-rules", d);
      setRules((rs) => [...rs, r]);
    }
    setEditing(null);
  };

  const toggleRule = async (r: AlertRule) => {
    const { id, created_at, ...rest } = r;
    void created_at;
    const u = await put<AlertRule>(`/api/alert-rules/${id}`, { ...rest, active: !r.active });
    setRules((rs) => rs.map((x) => (x.id === u.id ? u : x)));
  };

  const deleteRule = async (r: AlertRule) => {
    if (!confirm(`Delete the rule "${r.name}"?`)) return;
    await del(`/api/alert-rules/${r.id}`);
    setRules((rs) => rs.filter((x) => x.id !== r.id));
  };

  const label = (id: string) => catalog?.events.find((e) => e.id === id)?.label ?? id;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl p-4 sm:p-6">
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <div>
            <h1 className="text-xl font-semibold">Alerts</h1>
            <p className="text-sm text-muted">Breakouts, unusual volume, gaps, warnings and Move Detector signals, checked every 5 minutes.</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {status && <span className="text-sm text-muted">{status}</span>}
            <button onClick={markAll} className="rounded-md px-3 py-1.5 text-sm text-muted hover:bg-panel-2 hover:text-text">
              Mark all read
            </button>
            {canAlerts && (
              <button onClick={checkNow} className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-500">
                Check now
              </button>
            )}
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[1fr_400px]">
          <AlertFeed
            alerts={alerts}
            filter={filter}
            loading={loading}
            onFilter={setFilter}
            onRead={async (a) => {
              await post(`/api/alerts/${a.id}/read`, {});
              setAlerts((xs) => xs.map((x) => (x.id === a.id ? { ...x, read: true } : x)));
              notifyBadge();
            }}
            onDelete={async (a) => {
              await del(`/api/alerts/${a.id}`);
              setAlerts((xs) => xs.filter((x) => x.id !== a.id));
              notifyBadge();
            }}
          />

          <div className="space-y-5">
            <section className="rounded-xl border border-line bg-panel p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-semibold">Alert rules</h2>
                {canAlerts && editing === null && (
                  <button onClick={() => setEditing("new")} className="rounded-md bg-panel-2 px-3 py-1 text-sm hover:bg-line">
                    + New rule
                  </button>
                )}
              </div>

              {!canAlerts ? (
                <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-sm">
                  <p className="font-medium text-amber-300">Alerts are available on the Pro and Premium plans.</p>
                  <p className="mt-1 text-muted">Get notified about breakouts, unusual volume, gaps and warning signs on your watchlists or the entire market.</p>
                  <Link href="/#pricing" className="mt-3 inline-block text-accent hover:underline">
                    See plans
                  </Link>
                </div>
              ) : editing !== null && catalog ? (
                <RuleForm
                  key={editing === "new" ? "new" : editing.id}
                  catalog={catalog}
                  watchlists={watchlists}
                  canMarketWide={canMarketWide}
                  initial={editing === "new" ? emptyDraft(catalog, prefill) : editing}
                  submitLabel={editing === "new" ? "Create rule" : "Save changes"}
                  onSubmit={saveRule}
                  onCancel={() => setEditing(null)}
                />
              ) : rules.length === 0 ? (
                <p className="text-sm text-muted">No rules yet. Create one to start receiving alerts.</p>
              ) : (
                <ul className="space-y-2">
                  {rules.map((r) => (
                    <li key={r.id} className={`rounded-lg border border-line p-3 ${r.active ? "" : "opacity-50"}`}>
                      <div className="flex items-start gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="font-medium">{r.name}</div>
                          <div className="text-xs text-muted">{scopeText(r, watchlists)}</div>
                        </div>
                        <label className="flex items-center gap-1 text-xs text-muted" title={r.active ? "Pause" : "Resume"}>
                          <input type="checkbox" checked={r.active} onChange={() => toggleRule(r)} className="accent-blue-500" />
                          On
                        </label>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {r.events.map((e) => (
                          <span key={e} className="rounded bg-line/60 px-1.5 py-0.5 text-[11px] text-muted">
                            {label(e)}
                            {(e === "price_above" || e === "price_below") && r.price_level ? ` ${r.price_level}` : ""}
                          </span>
                        ))}
                      </div>
                      <div className="mt-2 flex gap-3 text-xs">
                        <button onClick={() => setEditing(r)} className="text-muted hover:text-text">
                          Edit
                        </button>
                        <button onClick={() => deleteRule(r)} className="text-muted hover:text-down">
                          Delete
                        </button>
                        <span className="ml-auto text-muted">{r.channels.join(" · ")}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            {canAlerts && <NotificationsCard />}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AlertsPage() {
  return (
    <AppShell>
      <Suspense fallback={null}>
        <AlertsWorkspace />
      </Suspense>
    </AppShell>
  );
}
