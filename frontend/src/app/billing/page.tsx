"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PlanLimits } from "@/lib/types";

type Sub = { status: string; plan: string; interval?: string | null; amount?: number; currency?: string; current_period_end?: string | null; cancel_at_period_end?: boolean };
type Plan = { id: "free" | "pro" | "premium"; label: string; prices: { monthly: number; yearly: number }; available: { monthly: boolean; yearly: boolean }; limits: PlanLimits };
type Plans = { enabled: boolean; current_plan: string; effective_plan: string; trial_until: string | null; currency: string; subscription: Sub; plans: Plan[] };

const lim = (n: number) => (n >= 1e6 ? "Unlimited" : String(n));

function features(l: PlanLimits): [string, boolean][] {
  return [
    ["Charts, indicators, free screener, market overview", true],
    [`${lim(l.max_watchlists)} watchlist${l.max_watchlists === 1 ? "" : "s"}, ${lim(l.max_symbols_per_watchlist)} symbols each`, true],
    [`${lim(l.max_strategies_on_chart)} indicators per chart`, true],
    [`${lim(l.max_portfolios)} portfolio${l.max_portfolios === 1 ? "" : "s"}`, true],
    ["Full Trend Template, VCP & vnicorn Pulse", !!l.sepa_details],
    ["Move Detector, screens & filters", l.move_detector],
    [l.ideas_limit ? (l.ideas_limit >= 1e6 ? `Trade ideas: every one found${l.ideas_shorts ? ", incl. shorts" : ""}` : `Trade ideas: top ${l.ideas_limit} a day${l.ideas_shorts ? ", incl. shorts" : ", longs"}`) : "Trade ideas", l.ideas_limit > 0],
    ["Backtesting, TradeGrader & analytics", l.backtesting],
    ["Quarterly EPS & sales acceleration", l.eps_history],
    [`Email alerts${l.alerts ? ` (${lim(l.max_alert_rules)} rules)` : ""}`, l.alerts],
    [l.ask_ai_monthly >= 1e6 ? "Ask vnicornAI: unlimited" : `Ask vnicornAI${l.ask_ai_monthly ? ` (${l.ask_ai_monthly}/month)` : ""}`, !!l.ask_ai],
    ["vnicornAI picks & move probabilities", l.ai_picks],
    ["Industry group rankings", l.industry_groups],
    ["Weekly market letter", l.weekly_letter],
    ["Custom strategy backtests", l.custom_backtest],
    ["Instant Telegram alerts", l.instant_alerts],
    ["CSV export", l.csv_export],
  ];
}

function Billing() {
  const { user, refresh } = useAuth();
  const params = useSearchParams();
  const status = params.get("status");
  const [data, setData] = useState<Plans | null>(null);
  const [interval, setInterval] = useState<"monthly" | "yearly">("monthly");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () => api<Plans>("/api/billing/plans").then(setData).catch((e) => setError(e.message));
    load();
    if (status === "success") {
      // the webhook may land a moment after the redirect: refresh the plan a few times
      const ids = [1500, 4000, 8000].map((ms) => setTimeout(() => { load(); refresh(); }, ms));
      return () => ids.forEach(clearTimeout);
    }
  }, [status, refresh]);

  const go = async (key: string, path: string, body?: unknown) => {
    setBusy(key);
    setError("");
    try {
      const r = await post<{ url: string }>(path, body ?? {});
      window.location.href = r.url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
      setBusy(null);
    }
  };

  if (!data) return <div className="grid h-full place-items-center text-sm text-muted">{error || "Loading…"}</div>;
  const sub = data.subscription;
  const subscribed = ["active", "trialing", "past_due"].includes(sub.status);
  const isAdmin = user?.role === "admin";
  const cur = data.currency === "EUR" ? "€" : "$";
  const trialDays = data.trial_until ? Math.max(0, Math.ceil((new Date(data.trial_until).getTime() - Date.now()) / 86_400_000)) : 0;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl p-4 sm:p-6">
        <h1 className="text-xl font-semibold">{("Plans & billing")}</h1>
        <p className="mb-5 text-sm text-muted">Upgrade, switch or cancel at any time. Payments are processed securely by Stripe; card details never touch our servers.</p>

        {status === "success" && <p className="mb-4 rounded-lg border border-up/30 bg-up/10 px-3 py-2 text-sm text-up">Payment received. Your plan updates within a few seconds. Thank you!</p>}
        {status === "canceled" && <p className="mb-4 rounded-lg border border-line bg-panel px-3 py-2 text-sm text-muted">Checkout was canceled. You were not charged.</p>}
        {!data.enabled && (
          <p className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm text-amber-200">
            Online payments are not enabled yet. {isAdmin ? "Add your Stripe keys in the server environment (see README) to turn them on." : "Contact us to upgrade your account."}
          </p>
        )}
        {error && <p className="mb-4 rounded-md bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
        {data.trial_until && (
          <p className="mb-4 rounded-lg border border-violet-500/30 bg-violet-500/10 px-3 py-2 text-sm text-violet-200">
            ✦ Premium trial: {trialDays} day{trialDays === 1 ? "" : "s"} left (until {new Date(data.trial_until).toLocaleDateString("en-US")}). Pick a plan to keep the features; otherwise you return to Free automatically.
          </p>
        )}

        {subscribed && (
          <section className="mb-6 flex flex-wrap items-center gap-4 rounded-xl border border-line bg-panel p-4">
            <div>
              <div className="text-xs text-muted">Current subscription</div>
              <div className="text-lg font-semibold">
                {sub.plan.charAt(0).toUpperCase() + sub.plan.slice(1)} · {cur}{sub.amount}/{sub.interval === "year" ? "year" : "month"}
              </div>
              <div className={`text-sm ${sub.status === "past_due" ? "text-down" : "text-muted"}`}>
                {sub.status === "past_due"
                  ? "Your last payment failed. Update your card to keep access."
                  : sub.cancel_at_period_end
                    ? `Cancels on ${sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString("en-US") : "the end of the period"}`
                    : `Renews on ${sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString("en-US") : "—"}`}
              </div>
            </div>
            <button onClick={() => go("portal", "/api/billing/portal")} disabled={busy !== null} className="ml-auto rounded-md bg-panel-2 px-4 py-2 text-sm hover:bg-line disabled:opacity-60">
              {busy === "portal" ? "Opening…" : "Manage billing"}
            </button>
          </section>
        )}

        <div className="mb-5 flex justify-center">
          <div className="inline-flex rounded-lg border border-line bg-panel p-1 text-sm">
            {(["monthly", "yearly"] as const).map((iv) => (
              <button key={iv} onClick={() => setInterval(iv)} className={`rounded-md px-4 py-1.5 ${interval === iv ? "bg-accent text-white" : "text-muted hover:text-text"}`}>
                {(iv === "monthly" ? "Monthly" : "Yearly")}
                {iv === "yearly" && <span className={`ml-1.5 text-[11px] ${interval === iv ? "text-white/80" : "text-up"}`}>{("2 months free")}</span>}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {data.plans.map((p) => {
            const current = data.current_plan === p.id;
            const price = p.prices[interval];
            const highlight = p.id === "pro";
            return (
              <div key={p.id} className={`flex flex-col rounded-xl border p-5 ${highlight ? "border-accent bg-accent/5" : "border-line bg-panel"}`}>
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">{p.label}</h2>
                  {current && <span className="rounded bg-up/15 px-2 py-0.5 text-xs text-up">{("Current plan")}</span>}
                  {!current && data.trial_until && p.id === "premium" && <span className="rounded bg-violet-500/20 px-2 py-0.5 text-xs text-violet-200">{("On trial")}</span>}
                  {!current && highlight && <span className="rounded bg-accent/20 px-2 py-0.5 text-xs text-blue-300">{("Most popular")}</span>}
                </div>
                <p className="mt-2">
                  <span className="text-3xl font-bold">{cur}{price}</span>
                  <span className="text-muted">{p.id === "free" ? "" : interval === "monthly" ? "/month" : "/year"}</span>
                </p>
                {p.id !== "free" && interval === "yearly" && <p className="text-xs text-muted">{cur}{(price / 12).toFixed(2)}/month billed yearly</p>}
                <ul className="mt-4 flex-1 space-y-1.5 text-sm">
                  {features(p.limits).map(([f, ok]) => (
                    <li key={f} className={ok ? "" : "text-muted/60 line-through"}>
                      <span className={ok ? "text-up" : ""}>{ok ? "✓" : "–"}</span> {f}
                    </li>
                  ))}
                </ul>
                <div className="mt-5">
                  {p.id === "free" ? (
                    <p className="text-center text-xs text-muted">{subscribed ? "Cancel in Manage billing to return to Free." : ("Free forever")}</p>
                  ) : current && subscribed ? (
                    <button onClick={() => go("portal", "/api/billing/portal")} className="w-full rounded-md bg-panel-2 py-2 text-sm hover:bg-line">Manage billing</button>
                  ) : subscribed ? (
                    <button onClick={() => go("portal", "/api/billing/portal")} className="w-full rounded-md bg-accent py-2 text-sm font-medium text-white hover:bg-blue-500">Switch plan</button>
                  ) : (
                    <button
                      onClick={() => go(p.id, "/api/billing/checkout", { plan: p.id, interval })}
                      disabled={!data.enabled || !p.available[interval] || busy !== null}
                      className="w-full rounded-md bg-accent py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {busy === p.id ? "Redirecting to checkout…" : current ? "Current plan" : `Upgrade to ${p.label}`}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        {isAdmin && <p className="mt-4 text-center text-xs text-muted">You are an administrator: you have full access regardless of plan.</p>}
        <p className="mt-6 text-center text-xs text-muted">Prices in USD. Taxes may apply. Cancel anytime; you keep access until the end of the paid period.</p>
      </div>
    </div>
  );
}

export default function BillingPage() {
  return (
    <AppShell>
      <Suspense fallback={null}>
        <Billing />
      </Suspense>
    </AppShell>
  );
}
