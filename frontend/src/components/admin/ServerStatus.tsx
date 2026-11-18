"use client";

import { useEffect, useState } from "react";
import { BASE } from "@/lib/api";

type Health = {
  summary: string[];
  status: string;
  data_provider: string;
  universe_size: number;
  config: {
    data_provider: string; database: string; admin_email_set: boolean; jwt_secret_set: boolean; email_configured: boolean;
    finnhub_configured: boolean; universe: string; universe_extra?: number;
  };
  market_data?: {
    state: string; message: string; symbols_with_prices: number; prices_refreshed_at: string | null; live_updated_at: string | null;
    fundamentals_loaded: string; fundamentals_paused_until: string | null; universe_source?: string | null;
    last_error?: string | null; last_error_at?: string | null; screens_error?: string | null;
  } | null;
  ideas?: {
    last_batch: string | null; due: boolean;
    vnicorn?: { trained?: boolean; stocks?: number | null; trained_at?: string | null; error?: string | null; rated?: number | null; rated_by_region?: Record<string, number> | null; samples?: number | null; years?: number | null; trusted?: Record<string, boolean> | null };
    regenerate?: { running?: boolean; stage?: string | null; started_at?: string | null; finished_at?: string | null; generated?: number | null; error?: string | null; interrupted?: boolean };
  } | null;
  memory?: { used_mb: number; limit_mb: number; breakdown_mb?: Record<string, number> };
};

function ago(iso?: string | null) {
  if (!iso) return "—";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

function Bar({ value, max, tone = "bg-accent" }: { value: number; max: number; tone?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded bg-panel-2">
      <div className={`h-full rounded ${tone}`} style={{ width: `${Math.min(100, (value / Math.max(1, max)) * 100)}%` }} />
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-line py-1.5 text-sm first:border-t-0">
      <span className="text-muted">{label}</span>
      <span className="tabular text-right">{children}</span>
    </div>
  );
}

function Check({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs ${ok ? "bg-up/10 text-up" : "bg-amber-500/10 text-amber-300"}`}>
      {ok ? "✓" : "!"} {label}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-bg/40 p-3">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</div>
      {children}
    </div>
  );
}

const STATE: Record<string, { label: string; tone: string }> = {
  ready: { label: "Running", tone: "bg-up" },
  refreshing: { label: "Running · updating data", tone: "bg-up" },
  loading: { label: "Starting up · loading saved prices", tone: "bg-amber-400" },
  error: { label: "Running · last update had errors", tone: "bg-down" },
};

/** The server's health (/api/health) laid out in the app's style, refreshed every 15 seconds. */
export default function ServerStatus() {
  const [h, setH] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const load = () =>
      fetch(`${BASE}/api/health`)
        .then((r) => r.json())
        .then((j) => {
          setH(j);
          setFailed(false);
        })
        .catch(() => setFailed(true));
    load();
    const t = setInterval(() => { if (!document.hidden) load(); }, 15000);
    return () => clearInterval(t);
  }, []);

  if (!h) return failed ? <p className="mb-8 rounded-xl border border-down/40 bg-down/10 p-4 text-sm text-down">The server is not responding.</p> : null;

  const md = h.market_data;
  const st = STATE[md?.state ?? "ready"] ?? STATE.ready;
  const m = h.memory;
  const pct = m ? (m.used_mb / m.limit_mb) * 100 : 0;
  const [fd, ft] = (md?.fundamentals_loaded ?? "0/0").split("/").map(Number);
  const v = h.ideas?.vnicorn;
  const r = h.ideas?.regenerate;
  const errors = [md?.last_error && `Data: ${md.last_error}`, md?.screens_error && `Screens: ${md.screens_error}`, v?.error && `vnicornAI: ${v.error}`,
    r?.error && `Regeneration: ${r.error}`].filter(Boolean) as string[];
  const breakdown = Object.entries(m?.breakdown_mb ?? {});
  const bdMax = Math.max(1, ...breakdown.map(([, x]) => x));

  return (
    <div className="mb-8 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${st.tone} ${md?.state === "loading" ? "animate-pulse" : ""}`} />
          <h2 className="font-semibold">Server status</h2>
          <span className="text-sm text-muted">{md ? st.label : `Running on ${h.data_provider} data`}</span>
        </div>
        <a href={`${BASE}/api/health`} target="_blank" rel="noreferrer" className="text-xs text-muted hover:text-text">Raw data ↗</a>
      </div>

      {errors.length > 0 && (
        <div className="mt-3 space-y-1 rounded-lg border border-down/30 bg-down/10 p-3 text-xs text-down">
          {errors.map((e) => <p key={e}>⚠ {e}</p>)}
        </div>
      )}
      {r?.interrupted && (
        <p className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
          The last regeneration was interrupted at “{r.stage}” (the server restarted).
        </p>
      )}

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <Section title="Market data">
          <div className="mb-2 mt-1 space-y-2">
            <div>
              <div className="mb-1 flex justify-between text-xs text-muted"><span>Stocks with prices</span><span className="tabular text-text">{md?.symbols_with_prices ?? "—"} / {h.universe_size}</span></div>
              <Bar value={md?.symbols_with_prices ?? 0} max={h.universe_size} />
            </div>
            <div>
              <div className="mb-1 flex justify-between text-xs text-muted"><span>Fundamentals</span><span className="tabular text-text">{fd} / {ft}</span></div>
              <Bar value={fd} max={ft} />
            </div>
          </div>
          <Row label="Universe">{h.config.universe}{h.config.universe_extra ? ` (+${h.config.universe_extra})` : ""}</Row>
          <Row label="Mid caps from">{md?.universe_source ?? "—"}</Row>
          <Row label="Prices refreshed">{ago(md?.prices_refreshed_at)}</Row>
          <Row label="Live update">{ago(md?.live_updated_at)}</Row>
          {md?.fundamentals_paused_until && <Row label="Fundamentals paused until">{new Date(md.fundamentals_paused_until).toLocaleString("en-US")}</Row>}
        </Section>

        <Section title="Signals & vnicornAI">
          <Row label="Last trade ideas">{h.ideas?.last_batch ? `${h.ideas.last_batch} close` : "none yet"}</Row>
          <Row label="Next batch">{h.ideas?.due ? <span className="text-amber-300">due now</span> : "after the next close"}</Row>
          <Row label="vnicornAI learned from">
            {v?.trained
              ? `${(v.stocks ?? 0).toLocaleString("en-US")} US stocks${v.years ? ` · ${v.years} y` : ""}${v.samples ? ` · ${v.samples >= 1000 ? `${Math.round(v.samples / 1000)}k` : v.samples} samples` : ""}`
              : "not trained yet"}
          </Row>
          {v?.trained && (
            <Row label="vnicornAI picks">
              {v.trusted && Object.values(v.trusted).some(Boolean)
                ? <span className="text-up">on ({Object.entries(v.trusted).filter(([, t]) => t).map(([k]) => k).join(" + ")})</span>
                : <span className="text-amber-300">learning (not beating the baseline yet)</span>}
            </Row>
          )}
          {v?.trained && (
            <Row label="vnicornAI rates">
              <span title={Object.entries(v.rated_by_region ?? {}).map(([r, n]) => `${r} ${n}`).join(" · ")}>
                {(v.rated ?? 0).toLocaleString("en-US")} stocks
                {Object.keys(v.rated_by_region ?? {}).length > 1 && (
                  <span className="ml-1 text-xs text-muted">({Object.entries(v.rated_by_region ?? {}).map(([r, n]) => `${r === "ASIA" ? "Asia" : r} ${n}`).join(" · ")})</span>
                )}
              </span>
            </Row>
          )}
          <Row label="Trained">{ago(v?.trained_at)}</Row>
          <Row label="Last regeneration">
            {r?.running ? <span className="text-accent">running: {r.stage}</span> : r?.finished_at ? `${r.generated ?? 0} ideas · ${ago(r.finished_at)}` : "—"}
          </Row>
        </Section>

        <Section title="Memory">
          {m && (
            <div className="mb-2 mt-1">
              <div className="mb-1 flex justify-between text-xs text-muted">
                <span>Used</span>
                <span className="tabular text-text">{m.used_mb.toLocaleString("en-US")} / {m.limit_mb.toLocaleString("en-US")} MB · {Math.round(pct)}%</span>
              </div>
              <Bar value={m.used_mb} max={m.limit_mb} tone={pct < 75 ? "bg-up" : pct < 90 ? "bg-amber-400" : "bg-down"} />
            </div>
          )}
          <div className="space-y-1.5 pt-1">
            {breakdown.map(([k, x]) => (
              <div key={k}>
                <div className="flex justify-between text-[11px] text-muted"><span>{k}</span><span className="tabular">≈{x} MB</span></div>
                <Bar value={x} max={bdMax} tone="bg-violet-400/70" />
              </div>
            ))}
          </div>
        </Section>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Check ok={h.config.database.startsWith("postgres")} label={`Database: ${h.config.database}`} />
        <Check ok={h.config.data_provider !== "synthetic"} label={`Data: ${h.config.data_provider}`} />
        <Check ok={h.config.finnhub_configured} label="Finnhub key" />
        <Check ok={h.config.admin_email_set} label="Admin e-mail" />
        <Check ok={h.config.jwt_secret_set} label="Login secret" />
        <Check ok={h.config.email_configured} label="E-mail sending" />
      </div>
    </div>
  );
}
