import Link from "next/link";

/** Paid-feature teaser: what the feature does and a link to the plans. */
export default function Locked({ feature, text, compact = false }: { feature: string; text?: string; compact?: boolean }) {
  if (compact) {
    return (
      <Link href="/billing" className="inline-flex items-center gap-1 rounded bg-amber-500/15 px-1.5 py-0.5 text-[11px] font-semibold text-amber-300 hover:bg-amber-500/25" title={`${feature}: Pro and Premium`}>
        🔒 Pro
      </Link>
    );
  }
  return (
    <div className="rounded-lg border border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-transparent p-3 text-sm">
      <div className="flex items-center gap-1.5 font-medium text-amber-200">🔒 {feature}</div>
      {text && <p className="mt-1 text-xs text-muted">{text}</p>}
      <Link href="/billing" className="mt-2 inline-block rounded-md bg-amber-500 px-3 py-1 text-xs font-semibold text-black hover:bg-amber-400">
        Unlock with Pro
      </Link>
    </div>
  );
}
