import type { Classification } from "@/lib/types";
import { PROFILE_STYLE, RiskMeter } from "./profile";

export default function ClassificationCard({ c }: { c: Classification }) {
  if (!c.primary) {
    return (
      <section className="rounded-xl border border-line bg-panel p-4">
        <h2 className="font-semibold">Portfolio profile</h2>
        <p className="mt-2 text-sm text-muted">Add positions and the portfolio type is detected automatically from your tickers.</p>
      </section>
    );
  }
  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">Portfolio profile</h2>
        <RiskMeter level={c.risk_level} />
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {[c.primary, ...c.secondary].map((k, i) => {
          const s = c.scores.find((x) => x.key === k)!;
          const label = k === "concentrated" ? `${c.sectors[0]?.sector}-heavy` : s.label;
          return (
            <span key={k} className={`rounded-md px-2 py-1 text-sm font-medium ${PROFILE_STYLE[k]} ${i ? "opacity-80" : ""}`} title={s.description}>
              {label}
            </span>
          );
        })}
      </div>
      <ul className="mt-3 space-y-1 text-sm text-muted">
        {c.insights.map((t) => (
          <li key={t}>• {t}</li>
        ))}
      </ul>

      <div className="mt-4 grid gap-5 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-[11px] uppercase tracking-wide text-muted">Style scores</h3>
          <ul className="space-y-1.5">
            {c.scores.slice(0, 7).map((s) => (
              <li key={s.key} className="grid grid-cols-[110px_1fr_32px] items-center gap-2 text-xs" title={s.description}>
                <span className="truncate text-muted">{s.label}</span>
                <span className="h-1.5 overflow-hidden rounded-full bg-line">
                  <span className="block h-full rounded-full bg-accent" style={{ width: `${s.score}%` }} />
                </span>
                <span className="tabular text-right">{s.score}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-[11px] uppercase tracking-wide text-muted">Sector allocation</h3>
          <ul className="space-y-1.5">
            {c.sectors.map((s) => (
              <li key={s.sector} className="grid grid-cols-[110px_1fr_40px] items-center gap-2 text-xs">
                <span className="truncate text-muted">{s.sector}</span>
                <span className="h-1.5 overflow-hidden rounded-full bg-line">
                  <span className="block h-full rounded-full bg-teal-400" style={{ width: `${s.weight}%` }} />
                </span>
                <span className="tabular text-right">{s.weight.toFixed(0)}%</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
