/** "Earnings in N days": a report soon can gap the stock either way. */
export default function EarningsBadge({ days, className = "" }: { days: number | null | undefined; className?: string }) {
  if (days === null || days === undefined) return null;
  const txt = days === 0 ? "Earnings today" : days === 1 ? "Earnings tomorrow" : `Earnings in ${days}d`;
  return (
    <span title="An earnings report is coming: the price can gap past stops. Many traders reduce size or wait." 
      className={`whitespace-nowrap rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300 ${className}`}>
      ⚠ {txt}
    </span>
  );
}

/** Trading days until a date (YYYY-MM-DD), or null if it's past or beyond `within` days. */
export function tradingDaysUntil(date: string | null | undefined, within = 5): number | null {
  if (!date) return null;
  const d = new Date(`${date}T12:00:00`);
  const t = new Date();
  t.setHours(12, 0, 0, 0);
  if (d < t) return null;
  let n = 0;
  const cur = new Date(t);
  while (cur < d) {
    cur.setDate(cur.getDate() + 1);
    const wd = cur.getDay();
    if (wd !== 0 && wd !== 6) n++;
  }
  return n <= within ? n : null;
}
