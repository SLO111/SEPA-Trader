"""TradeGrader: grades the timing of every buy and sell, and the trade as a whole.

Entry (long; mirrored for shorts), judged with what the chart looked like around the entry:
  * Late    - bought extended: more than 5% above the pivot / breakout level, or over 2.5 ATR above
              the low of the previous 10 days (no hindsight: only what was known at the entry).
  * Early   - the stock then fell more than 1.5 ATR below the entry within 15 days (it wasn't ready yet).
  * Perfect - within 3% of the pivot or of the previous 10-day low, and it never fell more than 0.5 ATR below the entry.
  * Fair    - everything in between.
Exit:
  * Perfect - within 3% of the highest price from 10 days before to 10 days after the sale.
  * Early   - it rose another 10% (or 2R) within 20 days after the sale.
  * Late    - more than half of the best open gain during the trade was given back.
  * Fair    - everything in between.
The grade (A-F) combines entry, exit, result and risk discipline.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from .indicators import atr
from .vcp import detect_vcp

GRADES = [(85, "A"), (70, "B"), (55, "C"), (40, "D"), (0, "F")]
ENTRY_PTS = {"Perfect": 15, "Fair": 5, "Early": -10, "Late": -15}
EXIT_PTS = {"Perfect": 15, "Fair": 3, "Early": -8, "Late": -15}


def _letter(score: float) -> str:
    return next(g for cut, g in GRADES if score >= cut)


def _pos(df: pd.DataFrame, day) -> int | None:
    i = df.index.searchsorted(pd.Timestamp(day))
    return int(i) if i < len(df) else None


def grade_trade(t: dict, df: pd.DataFrame) -> dict:
    """t: symbol, side (long|short), entry_date, entry_price, exit_date, exit_price, optional stop."""
    long = t.get("side", "long") != "short"
    sign = 1 if long else -1
    ei = _pos(df, t["entry_date"])
    if ei is None or ei < 30:
        return {**t, "grade": None, "entry_class": None, "exit_class": None, "open": not t.get("exit_date"), "notes": ["Not enough price history around this trade."]}
    entry = float(t["entry_price"])
    a = float(atr(df, 14).iloc[ei]) or entry * 0.02
    hi, lo, cl = df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float)
    notes: list[str] = []

    # sanity: the price must be close to where the stock traded that day
    if not (lo[ei] * 0.95 <= entry <= hi[ei] * 1.05):
        return {**t, "grade": None, "entry_class": None, "exit_class": None, "open": not t.get("exit_date"),
                "notes": [f"The entry price {entry} is far from where {t['symbol']} traded on {str(t['entry_date'])[:10]}: check the price (currency?) or the date."]}

    # ---- entry
    before = df.iloc[: ei + 1]
    v = detect_vcp(before) if len(before) >= 60 else {}
    if long:
        pivot = float(v["pivot"]) if v.get("pivot") else float(np.max(hi[max(0, ei - 21): ei])) if ei > 1 else entry
        base = float(np.min(lo[max(0, ei - 10): ei + 1]))  # only what was known at the entry
        extended = entry > pivot * 1.05 and entry > base + 2.5 * a or entry > base + 3 * a
        near = abs(entry / pivot - 1) <= 0.03 or (entry - base) / entry <= 0.03
    else:
        pivot = float(np.min(lo[max(0, ei - 21): ei])) if ei > 1 else entry
        base = float(np.max(hi[max(0, ei - 10): ei + 1]))
        extended = entry < pivot * 0.95 and entry < base - 2.5 * a or entry < base - 3 * a
        near = abs(entry / pivot - 1) <= 0.03 or (base - entry) / entry <= 0.03
    xi = _pos(df, t["exit_date"]) if t.get("exit_date") else None
    look_end = min(len(df), ei + 16 if xi is None else min(xi + 1, ei + 16))
    if look_end > ei + 1:
        adverse = float(entry - np.min(lo[ei + 1: look_end])) if long else float(np.max(hi[ei + 1: look_end]) - entry)
    else:
        adverse = 0.0
    if xi is None and len(df) - 1 - ei < 5 and not extended:
        entry_class = None
        notes.append("Too soon to judge the entry: it needs at least 5 trading days after the buy.")
    elif extended:
        entry_class = "Late"
        notes.append(f"Bought extended: {abs(entry / pivot - 1) * 100:.1f}% from the breakout level ({pivot:.2f}). Waiting for a pullback or a tighter base lowers risk.")
    elif adverse > 1.5 * a:
        entry_class = "Early"
        notes.append(f"Bought early: it moved {adverse / entry * 100:.1f}% against you right after the entry (over 1.5 ATR). The setup wasn't ready yet.")
    elif near and adverse <= 0.5 * a:
        entry_class = "Perfect"
        notes.append("Bought perfect: near the breakout level / the low of the area, and it never moved meaningfully against you.")
    else:
        entry_class = "Fair"
        notes.append("Entry was fair: not extended, but not at the ideal point either.")

    out = {**t, "entry_class": entry_class, "exit_class": None, "open": xi is None}
    if xi is None:
        cur = float(cl[-1])
        hold_hi, hold_lo = float(np.max(hi[ei:])), float(np.min(lo[ei:]))
        out.update({
            "pnl_pct": round((cur / entry - 1) * 100 * sign, 2),
            "mfe_pct": round(((hold_hi / entry - 1) if long else (1 - hold_lo / entry)) * 100, 2),
            "mae_pct": round(((hold_lo / entry - 1) if long else (1 - hold_hi / entry)) * 100, 2),
            "score": None, "grade": None,
        })
        notes.append("Still open: the sale is graded once you close it.")
        out["notes"] = notes
        return out

    # ---- exit
    exitp = float(t["exit_price"])
    hold_hi, hold_lo = float(np.max(hi[ei: xi + 1])), float(np.min(lo[ei: xi + 1]))
    win_hi = float(np.max(hi[max(ei, xi - 10): min(len(df), xi + 11)]))
    win_lo = float(np.min(lo[max(ei, xi - 10): min(len(df), xi + 11)]))
    after = slice(xi + 1, min(len(df), xi + 21))
    risk = abs(entry - float(t["stop"])) if t.get("stop") else entry * 0.07
    if long:
        best_after = float(np.max(hi[after])) if after.start < after.stop else exitp
        perfect = exitp >= win_hi * 0.97
        early = best_after >= exitp * 1.10 or best_after - exitp >= 2 * risk
        gain, gave = hold_hi - entry, hold_hi - exitp
        left = (best_after / exitp - 1) * 100
    else:
        best_after = float(np.min(lo[after])) if after.start < after.stop else exitp
        perfect = exitp <= win_lo * 1.03
        early = best_after <= exitp * 0.90 or exitp - best_after >= 2 * risk
        gain, gave = entry - hold_lo, exitp - hold_lo
        left = (1 - best_after / exitp) * 100
    if perfect:
        exit_class = "Perfect"
        notes.append("Sold perfect: within 3% of the best price around the sale.")
    elif early:
        exit_class = "Early"
        notes.append(f"Sold early: it went another {max(left, 0):.1f}% your way within 20 days. A trailing stop or selling only half would have kept more.")
    elif gain > 0 and gave > 0.5 * gain:
        exit_class = "Late"
        notes.append(f"Sold late: gave back {gave / gain * 100:.0f}% of the best open gain. Selling into strength or raising the stop protects profits.")
    else:
        exit_class = "Fair"
        notes.append("Exit was fair.")

    pnl = (exitp / entry - 1) * 100 * sign
    loss_r = (entry - exitp) * sign / risk
    score = 70 + ENTRY_PTS[entry_class] + EXIT_PTS[exit_class] + (5 if pnl > 0 else -5)
    if loss_r > 1.25 and t.get("stop"):
        score -= 10
        notes.append(f"The loss was {loss_r:.1f}× the planned risk: the stop wasn't respected.")
    score = float(np.clip(score, 0, 100))
    out.update({
        "exit_class": exit_class, "pnl_pct": round(pnl, 2),
        "r_multiple": round((exitp - entry) * sign / risk, 2) if t.get("stop") else None,
        "mfe_pct": round(((hold_hi / entry - 1) if long else (1 - hold_lo / entry)) * 100, 2),
        "mae_pct": round(((hold_lo / entry - 1) if long else (1 - hold_hi / entry)) * 100, 2),
        "left_on_table_pct": round(max(left, 0.0), 2),
        "days": int(xi - ei), "score": round(score), "grade": _letter(score),
    })
    out["notes"] = notes
    return out


def aggregate(graded: list[dict]) -> dict:
    ok = [g for g in graded if g.get("entry_class")]
    closed = [g for g in ok if g.get("exit_class")]
    def dist(rows, key):
        c = Counter(r[key] for r in rows)
        n = len(rows) or 1
        return [{"label": k, "count": c.get(k, 0), "pct": round(c.get(k, 0) / n * 100)} for k in ("Perfect", "Early", "Late", "Fair")]
    mistakes = Counter([f"Bought {g['entry_class'].lower()}" for g in ok if g["entry_class"] in ("Early", "Late")]
                       + [f"Sold {g['exit_class'].lower()}" for g in closed if g["exit_class"] in ("Early", "Late")])
    scores = [g["score"] for g in closed if g.get("score") is not None]
    return {
        "trades": len(ok), "closed": len(closed),
        "total": len(graded), "total_open": sum(1 for g in graded if g.get("open")), "total_closed": sum(1 for g in graded if not g.get("open")),
        "bought": dist(ok, "entry_class"), "sold": dist(closed, "exit_class"),
        "avg_score": round(float(np.mean(scores))) if scores else None,
        "avg_grade": _letter(float(np.mean(scores))) if scores else None,
        "top_mistake": mistakes.most_common(1)[0][0] if mistakes else None,
        "grades": dict(Counter(g["grade"] for g in closed if g.get("grade"))),
    }


# ------------------------------------------------------------------ round trips from portfolio transactions

def round_trips(txns: list[dict]) -> list[dict]:
    """FIFO-match buys and sells per symbol into trades (long only, like a portfolio). Open lots stay open."""
    lots: dict[str, list[list]] = defaultdict(list)  # symbol -> [[date, price, shares]]
    out = []
    for x in sorted(txns, key=lambda r: (str(r["date"]), 0 if r["side"] == "buy" else 1)):
        sym = x["symbol"].upper()
        if x["side"] == "buy":
            lots[sym].append([x["date"], float(x["price"]), float(x["shares"])])
            continue
        left = float(x["shares"])
        while left > 1e-9 and lots[sym]:
            lot = lots[sym][0]
            take = min(left, lot[2])
            out.append({"symbol": sym, "side": "long", "entry_date": lot[0], "entry_price": lot[1], "exit_date": x["date"],
                        "exit_price": float(x["price"]), "shares": take})
            lot[2] -= take
            left -= take
            if lot[2] <= 1e-9:
                lots[sym].pop(0)
    for sym, ls in lots.items():
        for d, p, sh in ls:
            out.append({"symbol": sym, "side": "long", "entry_date": d, "entry_price": p, "exit_date": None, "exit_price": None, "shares": sh})
    return out


# ------------------------------------------------------------------ TradingLogger-style analytics

def analytics(trades: list[dict]) -> dict:
    """Statistics over closed trades: pnl_pct, exit_date, optional r_multiple / mfe_pct."""
    closed = sorted([t for t in trades if t.get("exit_date") and t.get("pnl_pct") is not None], key=lambda t: str(t["exit_date"]))
    if not closed:
        return {"trades": 0}
    pnl = np.array([t["pnl_pct"] for t in closed], dtype=float)
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    win_rate = len(wins) / len(pnl)
    capture = [t["pnl_pct"] / t["mfe_pct"] for t in closed if t["pnl_pct"] > 0 and (t.get("mfe_pct") or 0) > 0]
    monthly: dict[str, list[float]] = defaultdict(list)
    for t in closed:
        monthly[str(t["exit_date"])[:7]].append(t["pnl_pct"])
    months = [{"month": m, "trades": len(v), "pnl_pct": round(float(np.sum(v)), 2), "win_rate": round(float(np.mean([x > 0 for x in v])) * 100)} for m, v in sorted(monthly.items())]
    streak_w = streak_l = cur_w = cur_l = 0
    for x in pnl:
        cur_w, cur_l = (cur_w + 1, 0) if x > 0 else (0, cur_l + 1)
        streak_w, streak_l = max(streak_w, cur_w), max(streak_l, cur_l)
    edges = [-100, -15, -10, -7, -5, -3, -1, 0, 1, 3, 5, 7, 10, 15, 25, 1000]
    hist = np.histogram(pnl, bins=edges)[0]
    labels = ["<-15", "-15..-10", "-10..-7", "-7..-5", "-5..-3", "-3..-1", "-1..0", "0..1", "1..3", "3..5", "5..7", "7..10", "10..15", "15..25", ">25"]
    return {
        "trades": len(pnl),
        "win_rate": round(win_rate * 100, 1),
        "avg_win_pct": round(avg_win, 2), "avg_loss_pct": round(avg_loss, 2),
        "win_loss_ratio": round(avg_win / abs(avg_loss), 2) if avg_loss else None,
        "expectancy_pct": round(win_rate * avg_win + (1 - win_rate) * avg_loss, 2),
        "profit_factor": round(float(wins.sum() / abs(losses.sum())), 2) if losses.sum() else None,
        "capture_pct": round(float(np.mean(capture)) * 100, 1) if capture else None,
        "largest_win_pct": round(float(pnl.max()), 2), "largest_loss_pct": round(float(pnl.min()), 2),
        "max_win_streak": int(streak_w), "max_loss_streak": int(streak_l),
        "profitable_months_pct": round(float(np.mean([m["pnl_pct"] > 0 for m in months])) * 100) if months else None,
        "months": months,
        "equity": [{"date": str(t["exit_date"])[:10], "value": round(float(v), 2)} for t, v in zip(closed, np.cumsum(pnl))],
        "histogram": [{"key": k, "value": int(v)} for k, v in zip(labels, hist)],
    }
