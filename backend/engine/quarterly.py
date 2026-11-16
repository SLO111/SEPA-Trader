"""Quarterly EPS and sales growth, with acceleration (the C and A of CANSLIM)."""

from __future__ import annotations


def _yoy(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev <= 0:
        return None
    return round((cur / prev - 1) * 100, 1)


def growth_table(eps_history: list[dict], revenue: list[dict] | None = None) -> dict:
    """eps_history: [{date, eps_actual}] newest first (from earnings); revenue: [{date, revenue}] newest first.
    Returns quarters newest first with YoY growth, plus whether growth is accelerating."""
    eps = [e for e in eps_history if e.get("eps_actual") is not None]
    rev = revenue or []
    quarters = []
    for i, e in enumerate(eps[:8]):
        prev = eps[i + 4]["eps_actual"] if i + 4 < len(eps) else None
        row = {"date": e["date"], "eps": e["eps_actual"], "eps_yoy": _yoy(e["eps_actual"], prev),
               "eps_surprise_pct": e.get("surprise_pct"), "revenue": None, "revenue_yoy": None}
        quarters.append(row)
    # revenue is matched to the nearest EPS report on or after the quarter's end (reports come weeks later)
    for j, r in enumerate(rev[:8]):
        prev = rev[j + 4]["revenue"] if j + 4 < len(rev) else None
        target = next((q for q in quarters if q["date"] >= r["date"] and q["revenue"] is None), None)
        if target is None and j < len(quarters):
            target = quarters[j]
        if target is not None:
            target["revenue"], target["revenue_yoy"] = r["revenue"], _yoy(r["revenue"], prev)

    def accelerating(key: str) -> bool | None:
        g = [q[key] for q in quarters[:3] if q[key] is not None]
        if len(g) < 3:
            return None
        return g[0] > g[1] > g[2]

    latest = quarters[0] if quarters else {}
    return {"quarters": quarters, "eps_accelerating": accelerating("eps_yoy"), "revenue_accelerating": accelerating("revenue_yoy"),
            "canslim_c": bool(latest.get("eps_yoy") is not None and latest["eps_yoy"] >= 25)}
