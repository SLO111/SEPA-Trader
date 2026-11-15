const ZONES = [
  { to: 25, color: "#dc2626", label: "Extreme Fear" },
  { to: 45, color: "#f97316", label: "Fear" },
  { to: 55, color: "#a3a3a3", label: "Neutral" },
  { to: 75, color: "#84cc16", label: "Greed" },
  { to: 100, color: "#16a34a", label: "Extreme Greed" },
];

export function fgColor(score: number | null | undefined) {
  if (score === null || score === undefined) return "#64748b";
  return (ZONES.find((z) => score <= z.to) ?? ZONES[ZONES.length - 1]).color;
}

/** Semicircle gauge: 0 (Extreme Fear) on the left, 100 (Extreme Greed) on the right. */
export default function FearGreedGauge({ score, label, size = 260 }: { score: number | null; label: string; size?: number }) {
  const cx = 100, cy = 100, r = 80, w = 18;
  const pt = (v: number, rad = r) => {
    const a = Math.PI * (1 - v / 100);
    return [cx + rad * Math.cos(a), cy - rad * Math.sin(a)];
  };
  const arc = (from: number, to: number) => {
    const [x1, y1] = pt(from);
    const [x2, y2] = pt(to);
    return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
  };
  let prev = 0;
  const v = score ?? 50;
  const [nx, ny] = pt(v, r - 10);
  return (
    <svg viewBox="-14 0 228 125" width={size} height={(size * 125) / 228} role="img" aria-label={`Fear and Greed index ${score ?? "unavailable"}: ${label}`}>
      {ZONES.map((z) => {
        const d = arc(prev + 0.6, z.to - 0.6);
        prev = z.to;
        return <path key={z.label} d={d} stroke={z.color} strokeWidth={w} fill="none" opacity={0.85} />;
      })}
      {[0, 25, 50, 75, 100].map((t) => {
        const [x, y] = pt(t, r + 17);
        return (
          <text key={t} x={x} y={y} fontSize="7" fill="#8b95a7" textAnchor="middle" dominantBaseline="middle">
            {t}
          </text>
        );
      })}
      {score !== null && (
        <>
          <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="#e6e9ef" strokeWidth={3} strokeLinecap="round" />
          <circle cx={cx} cy={cy} r={6} fill="#e6e9ef" />
        </>
      )}
      <text x={cx} y={cy + 22} fontSize="20" fontWeight="700" fill={fgColor(score)} textAnchor="middle">
        {score === null ? "—" : Math.round(score)}
      </text>
    </svg>
  );
}
