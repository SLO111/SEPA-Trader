import Link from "next/link";

export type Exposure = {
  exposure?: number; label: string; advice: string; distribution_days?: number; locked?: boolean;
  reasons?: { text: string; points: number }[];
};

const TONE: Record<string, string> = {
  Defensive: "text-down", Cautious: "text-amber-300", Normal: "text-sky-300", Aggressive: "text-up",
};
const BAR: Record<string, string> = {
  Defensive: "bg-down", Cautious: "bg-amber-400", Normal: "bg-sky-400", Aggressive: "bg-up",
};

/** Market exposure meter: how invested the market environment supports being. */
export default function ExposureCard({ e, compact = false }: { e: Exposure | null | undefined; compact?: boolean }) {
  if (!e) return null;
  return (
    <section className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">Market exposure</h3>
        <span className="text-[11px] text-muted">Trend, breadth, distribution days, highs vs lows</span>
      </div>
      <div className="mt-2 flex items-end gap-3">
        <span className={`text-2xl font-bold ${TONE[e.label]}`}>{e.label}</span>
        {e.exposure !== undefined ? (
          <span className="tabular pb-0.5 text-lg font-semibold">{e.exposure}% invested</span>
        ) : (
          <Link href="/billing" className="pb-1 text-xs text-amber-300 hover:underline">🔒 % and reasons with Pro</Link>
        )}
      </div>
      {e.exposure !== undefined && (
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-panel-2">
          <div className={`h-full ${BAR[e.label]}`} style={{ width: `${e.exposure}%` }} />
        </div>
      )}
      <p className="mt-2 text-sm text-muted">{e.advice}</p>
      {!compact && e.reasons && (
        <ul className="mt-3 grid gap-1 text-xs sm:grid-cols-2">
          {e.reasons.map((r) => (
            <li key={r.text} className="flex items-baseline gap-2">
              <span className={`tabular w-8 shrink-0 text-right font-semibold ${r.points > 0 ? "text-up" : r.points < 0 ? "text-down" : "text-muted"}`}>
                {r.points > 0 ? "+" : ""}{r.points}
              </span>
              <span>{r.text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
