import type { ProfileKey } from "@/lib/types";

export const PROFILE_STYLE: Record<ProfileKey, string> = {
  aggressive: "bg-red-500/15 text-red-300",
  growth: "bg-violet-500/15 text-violet-300",
  momentum: "bg-orange-500/15 text-orange-300",
  conservative: "bg-teal-500/15 text-teal-300",
  dividend: "bg-emerald-500/15 text-emerald-300",
  value: "bg-amber-500/15 text-amber-300",
  blue_chip: "bg-blue-500/15 text-blue-300",
  defensive: "bg-cyan-500/15 text-cyan-300",
  small_cap: "bg-pink-500/15 text-pink-300",
  speculative: "bg-rose-500/15 text-rose-300",
  balanced: "bg-slate-500/20 text-slate-200",
  concentrated: "bg-yellow-500/15 text-yellow-300",
};

export const RISK_LABEL = ["", "Very low", "Low", "Moderate", "High", "Very high"];

export function RiskMeter({ level, compact = false }: { level: number | null; compact?: boolean }) {
  if (!level) return null;
  return (
    <span className="inline-flex items-center gap-1.5" title={`Risk: ${RISK_LABEL[level]}`}>
      <span className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <span key={i} className={`h-2.5 w-1.5 rounded-sm ${i <= level ? (level >= 4 ? "bg-down" : level === 3 ? "bg-amber-400" : "bg-up") : "bg-line"}`} />
        ))}
      </span>
      {!compact && <span className="text-xs text-muted">{RISK_LABEL[level]} risk</span>}
    </span>
  );
}
