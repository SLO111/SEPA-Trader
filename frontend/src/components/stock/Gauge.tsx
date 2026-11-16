/** Semicircle gauge (Strong sell … Strong buy) with a needle; value is 0 (left) to 1 (right). */
export default function Gauge({ value, label, labels = ["Strong sell", "Sell", "Neutral", "Buy", "Strong buy"] }: { value: number | null; label: string; labels?: string[] }) {
  const colors = ["#ef4444", "#f97316", "#94a3b8", "#3b82f6", "#22c55e"];
  const r = 70, cx = 90, cy = 85;
  const arc = (a0: number, a1: number) => {
    const p = (a: number) => [cx - r * Math.cos(a), cy - r * Math.sin(a)];
    const [x0, y0] = p(a0), [x1, y1] = p(a1);
    return `M ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1}`;
  };
  const seg = Math.PI / 5;
  const v = value === null ? null : Math.min(1, Math.max(0, value));
  const angle = v === null ? null : v * Math.PI;
  const color = v === null ? "#94a3b8" : colors[Math.min(4, Math.floor(v * 5))];
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 180 100" className="w-full max-w-[220px]" role="img" aria-label={`${label}`}>
        {colors.map((c, i) => (
          <path key={c} d={arc(i * seg + 0.04, (i + 1) * seg - 0.04)} stroke={c} strokeWidth="9" fill="none" strokeLinecap="round" opacity={0.85} />
        ))}
        {angle !== null && (
          <>
            <line x1={cx} y1={cy} x2={cx - (r - 16) * Math.cos(angle)} y2={cy - (r - 16) * Math.sin(angle)} stroke="#e2e8f0" strokeWidth="3" strokeLinecap="round" />
            <circle cx={cx} cy={cy} r="5" fill="#e2e8f0" />
          </>
        )}
      </svg>
      <div className="-mt-1 text-lg font-semibold" style={{ color }}>
        {label}
      </div>
      <div className="mt-1 flex w-full max-w-[240px] justify-between text-[10px] text-muted">
        <span>{labels[0]}</span>
        <span>{labels[2]}</span>
        <span>{labels[4]}</span>
      </div>
    </div>
  );
}
