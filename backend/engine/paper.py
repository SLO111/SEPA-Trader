"""Paper trades taken from Trade Ideas: follow a position bar by bar with the plan's rules.

Rules (the same "position plan" shown in Trade Ideas):
  * entered at `entry` on `entry_date` (the price when the user clicked Buy / Short);
  * stop hit -> the whole position (or what is left) closes at the stop;
  * trim hit -> half is sold at the trim and the stop on the rest moves to break-even;
  * target hit -> the rest closes at the target;
  * the user can close the rest manually at any time (exit_price / exit_date).
Results are in % of the position and in R (multiples of the initial risk).
"""

from __future__ import annotations

import pandas as pd


def follow(trade: dict, df: pd.DataFrame) -> dict:
    long = trade["side"] == "long"
    sign = 1 if long else -1
    entry, stop0 = float(trade["entry"]), float(trade["stop"])
    trim, target = trade.get("trim"), float(trade["target"])
    risk = abs(entry - stop0) or entry * 0.01
    stop = stop0
    realized = 0.0  # in R, weighted by the closed fraction
    left = 1.0
    status, closed_at, exit_price = "OPEN", None, None
    bars = df[df.index > pd.Timestamp(trade["entry_date"])]
    manual = trade.get("exit_date")
    for ts, bar in bars.iterrows():
        if manual and ts > pd.Timestamp(manual):
            break
        hi, lo = float(bar["high"]), float(bar["low"])
        if (lo <= stop) if long else (hi >= stop):
            realized += left * (stop - entry) * sign / risk
            left, status, closed_at, exit_price = 0.0, ("BREAKEVEN" if stop != stop0 else "STOPPED"), ts, stop
            break
        if trim and left == 1.0 and ((hi >= trim) if long else (lo <= trim)):
            realized += 0.5 * (trim - entry) * sign / risk
            left, stop, status = 0.5, entry, "TRIMMED"
        if (hi >= target) if long else (lo <= target):
            realized += left * (target - entry) * sign / risk
            left, status, closed_at, exit_price = 0.0, "TARGET", ts, target
            break
    current = float(df["close"].iloc[-1])
    if left > 0 and manual and trade.get("exit_price") is not None:
        realized += left * (float(trade["exit_price"]) - entry) * sign / risk
        left, status, closed_at, exit_price = 0.0, "CLOSED", pd.Timestamp(manual), float(trade["exit_price"])
    open_r = left * (current - entry) * sign / risk
    r = realized + open_r
    return {
        "status": status,
        "open": left > 0,
        "current": round(current, 2),
        "r_multiple": round(r, 2),
        "pnl_pct": round(r * risk / entry * 100, 2),
        "closed_at": closed_at.strftime("%Y-%m-%d") if closed_at is not None else None,
        "exit_price": round(exit_price, 2) if exit_price is not None else None,
    }


def summary(rows: list[dict]) -> dict:
    closed = [r for r in rows if not r["open"]]
    wins = [r for r in closed if r["r_multiple"] > 0]
    weight = lambda r: (r.get("weight") or 1.0)
    total_w = sum(weight(r) for r in rows) or 1.0
    return {
        "trades": len(rows),
        "open": len(rows) - len(closed),
        "closed": len(closed),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "avg_r": round(sum(r["r_multiple"] for r in closed) / len(closed), 2) if closed else None,
        "total_r": round(sum(r["r_multiple"] for r in rows), 2),
        # account impact if every trade used the idea's suggested weight (% of the account)
        "account_pct": round(sum(r["pnl_pct"] * weight(r) / 100 for r in rows), 2),
        "avg_pnl_pct": round(sum(r["pnl_pct"] * weight(r) for r in rows) / total_w, 2) if rows else None,
    }
