import { useId } from "react";

const STOPS = ["#ef4444", "#f97316", "#94a3b8", "#3b82f6", "#22c55e"];

/** Rating meter: a smooth red → green arc, lit up to the value, with a glowing marker. value: 0 (left) to 1 (right). */
export default function Gauge({ value, label, sub, labels = ["Strong sell", "Neutral", "Strong buy"], size = "md" }: {
  value: number | null; label: string; sub?: string; labels?: [string, string, string] | string[]; size?: "sm" | "md";
}) {
  const id = useId().replace(/:/g, "");
  const v = value === null ? null : Math.min(1, Math.max(0, value));
  const r = 80, cx = 100, cy = 96;
  const arc = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;
  const ang = Math.PI * (1 - (v ?? 0.5));
  const mx = cx + r * Math.cos(ang), my = cy - r * Math.sin(ang);
  const color = v === null ? "#94a3b8" : STOPS[Math.min(4, Math.floor(v * 5))];
  const ends = labels.length === 5 ? [labels[0], labels[2], labels[4]] : labels;
  return (
    <div className={`mx-auto flex w-full flex-col items-center ${size === "sm" ? "max-w-[190px]" : "max-w-[240px]"}`}>
      <div className="relative w-full">
        <svg viewBox="0 0 200 112" className="w-full overflow-visible" role="img" aria-label={`${label}`}>
          <defs>
            <linearGradient id={`g${id}`} x1="0" x2="1" y1="0" y2="0">
              {STOPS.map((c, i) => <stop key={c} offset={i / 4} stopColor={c} />)}
            </linearGradient>
            <filter id={`f${id}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" />
            </filter>
          </defs>
          {/* full track, dimmed */}
          <path d={arc} stroke={`url(#g${id})`} strokeOpacity="0.18" strokeWidth="12" strokeLinecap="round" fill="none" />
          {/* lit part, up to the value */}
          {v !== null && <path d={arc} pathLength={100} strokeDasharray={`${Math.max(0.5, v * 100)} 200`} stroke={`url(#g${id})`} strokeWidth="12" strokeLinecap="round" fill="none" />}
          {/* ticks */}
          {[0, 0.25, 0.5, 0.75, 1].map((t) => {
            const a = Math.PI * (1 - t);
            return <line key={t} x1={cx + (r - 14) * Math.cos(a)} y1={cy - (r - 14) * Math.sin(a)} x2={cx + (r - 19) * Math.cos(a)} y2={cy - (r - 19) * Math.sin(a)} stroke="#475569" strokeWidth="1.5" strokeLinecap="round" />;
          })}
          {v !== null && (
            <>
              <circle cx={mx} cy={my} r="9" fill={color} opacity="0.55" filter={`url(#f${id})`} />
              <circle cx={mx} cy={my} r="7.5" fill="var(--color-bg)" stroke="var(--color-text)" strokeWidth="3" />
            </>
          )}
        </svg>
        <div className="absolute inset-x-0 bottom-1 text-center">
          <div className={`font-semibold leading-tight ${size === "sm" ? "text-base" : "text-xl"}`} style={{ color }}>{label}</div>
        </div>
      </div>
      <div className="mt-1 flex w-full justify-between px-1 text-[10px] uppercase tracking-wide text-muted">
        <span>{ends[0]}</span>
        <span>{ends[2]}</span>
      </div>
      {sub && <div className="mt-1 text-center text-[11px] text-muted">{sub}</div>}
    </div>
  );
}
