"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import Locked from "@/components/Locked";

type Mover = { symbol: string; name: string; price: number; change_pct: number };
export type Summary = {
  id: number;
  day: string;
  title: string;
  created_at: string;
  indices: { symbol: string; label: string; price: number; change_pct: number }[];
  vix: number | null;
  cycle: { label: string; stage: number; name: string }[];
  fear_greed: { score: number | null; label: string | null };
  breadth: { advancing: number; declining: number; new_highs: number; new_lows: number };
  gainers: Mover[];
  losers: Mover[];
  ideas: { locked?: boolean; count: number; top?: { symbol: string; timeframe: string; side: string; entry: number; stop: number; target: number; rr: number }[] };
  earnings_next: { symbol: string }[];
  move_detector?: { locked?: boolean; bull?: MdRow[]; bear?: MdRow[] };
  pulse?: { locked?: boolean; best?: PulseRow[]; warning?: PulseRow[] };
  exposure?: { exposure?: number; label: string; advice: string; locked?: boolean } | null;
};
type MdRow = { symbol: string; score: number; price: number; change_pct: number };
type PulseRow = { symbol: string; conf: number; warn: number };

function Chips({ items, cls }: { items: { symbol: string; label: string }[]; cls: string }) {
  if (!items.length) return <span className="text-xs text-muted">—</span>;
  return (
    <span className="flex flex-wrap gap-1.5">
      {items.map((x) => (
        <Link key={x.symbol} href={`/chart?s=${x.symbol}`} className="tabular rounded bg-panel-2 px-2 py-0.5 text-xs hover:text-accent">
          {x.symbol} <span className={cls}>{x.label}</span>
        </Link>
      ))}
    </span>
  );
}
type Digest = { enabled: boolean; email: string; email_configured: boolean };

const pct = (x: number) => `${x >= 0 ? "+" : ""}${x.toFixed(2)}%`;
const tone = (x: number) => (x >= 0 ? "text-up" : "text-down");
const STAGE = ["", "text-slate-300", "text-up", "text-amber-300", "text-down"];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const t = useT();
  title = t(title);
  return (
    <div>
      <div className="mb-1.5 text-[11px] uppercase tracking-wide text-muted">{title}</div>
      {children}
    </div>
  );
}

/** Which days the summary covers: a Friday summary stays pinned over the weekend ("Fri – Sun"). */
function coverage(day: string): string {
  const d = new Date(`${day}T12:00:00`);
  const long = d.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
  const now = new Date();
  const ageDays = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (d.getDay() === 5 && ageDays >= 1) return `${long} · covers Friday – Sunday`;
  return ageDays < 1 ? `Today · ${long}` : ageDays < 2 ? `Yesterday · ${long}` : long;
}

/** End-of-day recap, pinned at the top of the Alerts pages until the next trading day's summary, with the email opt-in. */
export default function DailySummary({ compact = false }: { compact?: boolean }) {
  const [s, setS] = useState<Summary | null>(null);
  const [digest, setDigest] = useState<Digest | null>(null);
  const [open, setOpen] = useState(!compact);
  const t = useT();

  useEffect(() => {
    api<Summary | null>("/api/feed/summary").then(setS).catch(() => {});
    api<Digest>("/api/feed/digest").then(setDigest).catch(() => {});
  }, []);

  const toggle = async () => {
    if (!digest) return;
    const r = await api<Digest>("/api/feed/digest", { method: "PUT", body: JSON.stringify({ enabled: !digest.enabled }) });
    setDigest(r);
  };

  const optIn = digest && (
    <label className="flex cursor-pointer items-center gap-2 text-xs text-muted" title={digest.email_configured ? "" : "Email sending is not configured on the server yet"}>
      <input type="checkbox" checked={digest.enabled} onChange={toggle} className="accent-[var(--color-accent,#3b82f6)]" />
      {t("Email me the daily summary")}{digest.enabled ? ` (${digest.email})` : ""}
    </label>
  );

  if (!s) {
    return (
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line bg-panel p-4 text-sm text-muted">
        <span>📋 The daily summary is published after each trading day.</span>
        {optIn}
      </div>
    );
  }

  return (
    <section className="mb-4 rounded-xl border border-accent/40 bg-gradient-to-br from-accent/10 to-panel">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-start gap-3 p-4 text-left">
        <span className="text-xl leading-none">📋</span>
        <span className="min-w-0 flex-1">
          <span className="mb-0.5 flex flex-wrap items-center gap-2 text-[11px] text-muted">
            <span className="rounded bg-accent/25 px-1.5 py-0.5 font-semibold text-blue-200">📌 {t("PINNED")}</span>
            <span>{s.day ? coverage(s.day) : ""}</span>
          </span>
          <span className="block font-medium leading-snug">{s.title}</span>
        </span>
        <span className="text-xs text-muted">{t(open ? "Hide ▲" : "Show ▼")}</span>
      </button>
      {open && (
        <div className="space-y-4 border-t border-line px-4 pb-4 pt-3 text-sm">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {s.indices.map((i) => (
              <div key={i.symbol} className="rounded-lg bg-panel-2/60 px-3 py-2">
                <div className="text-[11px] text-muted">{i.label}</div>
                <div className="tabular font-medium">{i.price.toLocaleString("en-US", { maximumFractionDigits: 2 })}</div>
                <div className={`tabular text-xs ${tone(i.change_pct)}`}>{pct(i.change_pct)}</div>
              </div>
            ))}
            {s.vix !== null && (
              <div className="rounded-lg bg-panel-2/60 px-3 py-2">
                <div className="text-[11px] text-muted">VIX</div>
                <div className="tabular font-medium">{s.vix.toFixed(2)}</div>
              </div>
            )}
          </div>
          {s.exposure && (
            <p className="rounded-lg bg-panel-2/60 px-3 py-2 text-sm">
              <span className="text-muted">Market exposure: </span>
              <b>{s.exposure.label}</b>
              {s.exposure.exposure !== undefined ? <b className="tabular"> · {s.exposure.exposure}% invested</b> : <Link href="/billing" className="ml-1 text-xs text-amber-300">🔒 %</Link>}
              <span className="text-muted"> — {s.exposure.advice}</span>
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Section title="Market mood">
              <p>
                {s.fear_greed.score !== null && (
                  <>
                    Fear &amp; Greed <b className="tabular">{Math.round(s.fear_greed.score)}</b> ({s.fear_greed.label}) ·{" "}
                  </>
                )}
                <span className="text-up">{s.breadth.advancing} up</span> / <span className="text-down">{s.breadth.declining} down</span> ·{" "}
                {s.breadth.new_highs} new highs, {s.breadth.new_lows} new lows
              </p>
              {s.cycle.length > 0 && (
                <p className="mt-1 text-xs text-muted">
                  {s.cycle.map((c) => (
                    <span key={c.label} className="mr-3">
                      {c.label}: <span className={STAGE[c.stage]}>Stage {c.stage} {c.name}</span>
                    </span>
                  ))}
                </p>
              )}
            </Section>
            <Section title="Top movers">
              <div className="flex flex-wrap gap-1.5">
                {[...s.gainers, ...s.losers].map((m) => (
                  <Link key={m.symbol} href={`/chart?s=${m.symbol}`} className="tabular rounded bg-panel-2 px-2 py-0.5 text-xs hover:text-accent">
                    {m.symbol} <span className={tone(m.change_pct)}>{pct(m.change_pct)}</span>
                  </Link>
                ))}
              </div>
            </Section>
          </div>
          {(s.ideas.locked || s.move_detector?.locked || s.pulse?.locked) && (
            <div className="grid gap-3 sm:grid-cols-3">
              {s.ideas.locked && <Locked feature="Trade ideas" text={`${s.ideas.count ?? "New"} setups today with entry, stop, trim and target.`} />}
              {s.move_detector?.locked && <Locked feature="Move Detector" text="The day's strongest Bull and Bear scores across the market." />}
              {s.pulse?.locked && <Locked feature="vnicorn Pulse" text="Which stocks act best and which flash warnings, over the last 10 days." />}
            </div>
          )}
          {s.move_detector && !s.move_detector.locked && (s.move_detector.bull?.length || s.move_detector.bear?.length) ? (
            <Section title="Move Detector">
              <div className="space-y-1.5">
                <div className="flex items-start gap-2"><span className="w-12 shrink-0 text-xs text-up">Bull ↑</span>
                  <Chips items={(s.move_detector.bull ?? []).map((r) => ({ symbol: r.symbol, label: `${Math.round(r.score)}` }))} cls="text-up" /></div>
                <div className="flex items-start gap-2"><span className="w-12 shrink-0 text-xs text-down">Bear ↓</span>
                  <Chips items={(s.move_detector.bear ?? []).map((r) => ({ symbol: r.symbol, label: `${Math.round(r.score)}` }))} cls="text-down" /></div>
              </div>
              <Link href="/scanner" className="mt-1 inline-block text-xs text-accent hover:underline">Open Move Detector →</Link>
            </Section>
          ) : null}
          {s.pulse && !s.pulse.locked && (s.pulse.best?.length || s.pulse.warning?.length) ? (
            <Section title="vnicorn Pulse · 10 days">
              <div className="space-y-1.5">
                <div className="flex items-start gap-2"><span className="w-20 shrink-0 text-xs text-up">Acting best</span>
                  <Chips items={(s.pulse.best ?? []).map((r) => ({ symbol: r.symbol, label: `+${r.conf}/−${r.warn}` }))} cls="text-up" /></div>
                <div className="flex items-start gap-2"><span className="w-20 shrink-0 text-xs text-down">Warnings</span>
                  <Chips items={(s.pulse.warning ?? []).map((r) => ({ symbol: r.symbol, label: `+${r.conf}/−${r.warn}` }))} cls="text-down" /></div>
              </div>
              <Link href="/pulse" className="mt-1 inline-block text-xs text-accent hover:underline">Open vnicorn Pulse →</Link>
            </Section>
          ) : null}
          {!s.ideas.locked && (
          <Section title={`New trade ideas (${s.ideas.count})`}>
            {s.ideas.top?.length ? (
              <ul className="space-y-1">
                {s.ideas.top.map((i) => (
                  <li key={i.symbol} className="tabular text-xs">
                    <span className="mr-2 rounded bg-panel-2 px-1.5 py-0.5 text-[10px] font-semibold">{i.timeframe}</span>
                    <Link href={`/chart?s=${i.symbol}`} className={`font-semibold hover:underline ${i.side === "short" ? "text-down" : "text-up"}`}>
                      {i.symbol}
                    </Link>{" "}
                    {i.side === "short" ? "short" : "buy"} {i.entry} · stop {i.stop} · target {i.target} · R/R {i.rr}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted">No new ideas today.</p>
            )}
            <Link href="/ideas" className="mt-1 inline-block text-xs text-accent hover:underline">
              All ideas →
            </Link>
          </Section>
          )}
          {s.earnings_next.length > 0 && (
            <Section title="Earnings next trading day">
              <p className="text-xs">{s.earnings_next.map((e) => e.symbol).join(", ")}</p>
            </Section>
          )}
          <div className="border-t border-line pt-3">{optIn}</div>
        </div>
      )}
    </section>
  );
}
