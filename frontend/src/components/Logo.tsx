import Link from "next/link";

/**
 * Vnicorn mark: a stylized unicorn head whose horn is a rising price line with an arrow tip,
 * on a violet → cyan gradient tile. Pure SVG, so it is sharp at any size.
 */
export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} role="img" aria-label="Vnicorn Investments">
      <defs>
        <linearGradient id="vn-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8b5cf6" />
          <stop offset="0.55" stopColor="#6366f1" />
          <stop offset="1" stopColor="#06b6d4" />
        </linearGradient>
        <linearGradient id="vn-horn" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#fde68a" />
          <stop offset="1" stopColor="#ffffff" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#vn-bg)" />
      {/* head */}
      <path
        d="M19 57c1-7 2-12 5-17-2-5-1-11 3-15l5-4c3 0 6 2 8 5l8 8c2 2 1 5-2 5l-5-1c-2 3-3 6-3 10l1 9z"
        fill="#ffffff"
      />
      {/* mane */}
      <path d="M27 25c-5 2-8 7-8 13M25 30c-3 3-4 7-4 11M24 37c-2 3-2 6-2 9" stroke="#ffffff" strokeOpacity="0.55" strokeWidth="2.4" strokeLinecap="round" fill="none" />
      {/* ear */}
      <path d="M30 22l1-7 4 6z" fill="#ffffff" />
      {/* eye */}
      <circle cx="37" cy="28" r="1.8" fill="#4f46e5" />
      {/* horn = rising chart line */}
      <path d="M35 21l4-6 3 2 6-10" stroke="url(#vn-horn)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <path d="M44 5l6 0-1 6z" fill="#ffffff" />
    </svg>
  );
}

export default function Logo({ href = "/", compact = false }: { href?: string; compact?: boolean }) {
  return (
    <Link href={href} className="flex shrink-0 items-center gap-2" aria-label="Vnicorn Investments home">
      <LogoMark size={28} />
      {!compact && (
        <span className="flex flex-col leading-none">
          <span className="vn-logo-text bg-gradient-to-r from-violet-300 via-indigo-200 to-cyan-300 bg-clip-text text-[15px] font-bold tracking-tight text-transparent">Vnicorn</span>
          <span className="text-[8.5px] font-medium tracking-[0.28em] text-muted">INVESTMENTS</span>
        </span>
      )}
    </Link>
  );
}
