"""Market-moving events and price gaps outside the regular session.

Ideas are built from the 4:00 PM close. A big report after the close (NVIDIA, Apple…) or a Fed decision can move a stock,
or the whole market, before the next open, and make an idea's entry or stop meaningless. This module:
* flags ideas whose pre-market / after-hours price has gapped too far from the close ("wait for the open");
* flags a market-wide gap (SPY / QQQ);
* lists high-impact events due today / tomorrow (mega-cap earnings, Fed decisions) or moving the market now.
"""

from __future__ import annotations

from datetime import date, timedelta

MEGA_CAPS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AVGO"]
INDEXES = ["SPY", "QQQ"]
GAP_PCT = 4.0  # a stock moving this much outside the session invalidates a plan made at the close
ENTRY_SLIP_PCT = 2.0  # a waiting idea whose price already jumped this far past the entry would fill at a worse price
MARKET_GAP_PCT = 1.0  # SPY / QQQ moving this much outside the session: the whole market is repricing
MEGA_MOVE_PCT = 5.0  # a mega-cap moving this much after a report moves the indexes with it
SESSION_NAME = {"after_hours": "after hours", "pre_market": "pre-market"}


def idea_gap(idea: dict, ext: dict | None) -> dict | None:
    """Flag for one idea {side, entry, stop, status} from its extended-hours quote {price, change_pct, session}."""
    if not ext or ext.get("price") is None:
        return None
    price, pct = float(ext["price"]), float(ext.get("change_pct") or 0.0)
    long = idea.get("side") != "short"
    where = SESSION_NAME.get(ext.get("session"), "outside the session")
    reasons = []
    if (long and price <= idea["stop"]) or (not long and price >= idea["stop"]):
        reasons.append(f"already through the stop ({idea['stop']:.2f})")
    elif abs(pct) >= GAP_PCT:
        reasons.append(f"{pct:+.1f}% {where}")
    elif idea.get("status") == "WAIT":
        slip = (price / idea["entry"] - 1) * 100 * (1 if long else -1)
        if slip >= ENTRY_SLIP_PCT:
            reasons.append(f"{slip:.1f}% past the entry {where}")
    if not reasons:
        return None
    return {"price": round(price, 2), "change_pct": round(pct, 2), "session": ext.get("session"),
            "text": f"Gap after the close: {reasons[0]}. Wait for the open before acting on this plan."}


def market_gap(ext_by_symbol: dict[str, dict]) -> dict | None:
    """The whole market moving outside the session (the bigger of SPY / QQQ)."""
    moves = [(s, float(ext_by_symbol[s]["change_pct"])) for s in INDEXES if ext_by_symbol.get(s) and ext_by_symbol[s].get("change_pct") is not None]
    if not moves:
        return None
    sym, pct = max(moves, key=lambda m: abs(m[1]))
    if abs(pct) < MARKET_GAP_PCT:
        return None
    where = SESSION_NAME.get(ext_by_symbol[sym].get("session"), "outside the session")
    return {"symbol": sym, "change_pct": round(pct, 2),
            "text": f"The market is moving {where}: {sym} {pct:+.1f}%. Plans made at the close may not hold at the open."}


def _when(d: date, today: date) -> str | None:
    if d == today:
        return "today"
    nxt = today + timedelta(days=3 if today.weekday() == 4 else 1)  # Friday -> Monday
    if d == nxt:
        return "next trading day" if today.weekday() == 4 else "tomorrow"
    return None


def high_impact(today: date, earnings_dates: dict[str, date | None], fomc_dates: list[str],
                ext_by_symbol: dict[str, dict] | None = None) -> list[dict]:
    """High-impact events for the banner: mega-cap reports and Fed decisions due today / next session, and mega-caps or
    the indexes moving hard outside the session right now."""
    out = []
    for sym in MEGA_CAPS:
        d = earnings_dates.get(sym)
        w = _when(d, today) if d else None
        if w:
            out.append({"kind": "earnings", "symbol": sym, "when": w,
                        "text": f"{sym} reports earnings {w}: expect big moves across the market. Consider smaller positions."})
    for m in fomc_dates:
        try:
            w = _when(date.fromisoformat(m), today)
        except ValueError:
            continue
        if w:
            out.append({"kind": "fed", "symbol": None, "when": w,
                        "text": f"Fed rate decision {w} (2:00 PM ET): volatility usually jumps around it."})
    for sym in MEGA_CAPS:
        e = (ext_by_symbol or {}).get(sym)
        if e and e.get("change_pct") is not None and abs(float(e["change_pct"])) >= MEGA_MOVE_PCT:
            where = SESSION_NAME.get(e.get("session"), "outside the session")
            out.append({"kind": "move", "symbol": sym, "when": "now",
                        "text": f"{sym} is moving {float(e['change_pct']):+.1f}% {where}: it can move the whole market at the open."})
    mg = market_gap(ext_by_symbol or {})
    if mg:
        out.append({"kind": "market", "symbol": mg["symbol"], "when": "now", "text": mg["text"]})
    return out


def reports_today(today: date, earnings_dates: dict[str, date | None]) -> list[str]:
    """Mega-caps reporting today (most report after the close)."""
    return [s for s in MEGA_CAPS if earnings_dates.get(s) == today]
