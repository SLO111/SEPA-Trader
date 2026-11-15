export function scoreColor(score: number | null | undefined, kind: "bull" | "bear") {
  if (score === null || score === undefined) return "text-muted";
  if (score >= 60) return kind === "bull" ? "text-up" : "text-down";
  if (score >= 45) return "text-amber-300";
  return "text-muted";
}

export function ScoreBar({ score, kind }: { score: number | null | undefined; kind: "bull" | "bear" }) {
  const v = Math.max(0, Math.min(100, score ?? 0));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-line">
        <div className={`h-full rounded-full ${kind === "bull" ? "bg-up" : "bg-down"}`} style={{ width: `${v}%`, opacity: 0.35 + v / 150 }} />
      </div>
      <span className={`tabular w-8 text-right text-sm font-medium ${scoreColor(score, kind)}`}>{score === null || score === undefined ? "—" : Math.round(v)}</span>
    </div>
  );
}
