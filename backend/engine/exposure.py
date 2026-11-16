"""Market exposure meter: how much of a portfolio the market environment supports being invested (0-100%).

Built from data already in the app: the trend and cycle stage of the S&P 500 / Nasdaq 100, breadth (share of stocks
above their 50-day average), distribution days (index down on higher volume), new highs vs. new lows and Fear & Greed.
"""

from __future__ import annotations

import pandas as pd

from .indicators import sma
from .stages import stage_now

LABELS = [(25, "Defensive"), (50, "Cautious"), (80, "Normal"), (101, "Aggressive")]
STAGE_POINTS = {1: 0, 2: 20, 3: -10, 4: -25}


def distribution_days(df: pd.DataFrame, lookback: int = 25, drop_pct: float = 0.2) -> int:
    """Sessions in the lookback where the index fell at least `drop_pct`% on higher volume than the day before."""
    d = df.iloc[-(lookback + 1):]
    chg = d["close"].pct_change() * 100
    return int(((chg <= -drop_pct) & (d["volume"] > d["volume"].shift())).sum())


def exposure(spy: pd.DataFrame, qqq: pd.DataFrame | None, rows: list[dict], fear_greed: float | None = None) -> dict:
    score, reasons = 40.0, []

    def trend(df: pd.DataFrame, name: str, weight: float) -> None:
        nonlocal score
        st = stage_now(df)
        if st:
            pts = STAGE_POINTS.get(st["stage"], 0) * weight
            score += pts
            reasons.append({"text": f"{name} in Stage {st['stage']} ({st['name']})", "points": round(pts)})
        c = df["close"]
        last, m50, m200 = float(c.iloc[-1]), float(sma(c, 50).iloc[-1]), float(sma(c, 200).iloc[-1])
        pts = (8 if last > m50 else -8) * weight + (7 if last > m200 else -7) * weight
        score += pts
        where = "above" if last > m50 else "below"
        reasons.append({"text": f"{name} {where} its 50-day average, {'above' if last > m200 else 'below'} the 200-day", "points": round(pts)})

    trend(spy, "S&P 500", 1.0)
    if qqq is not None and len(qqq) >= 200:
        trend(qqq, "Nasdaq 100", 0.5)

    if rows:
        above = 100 * sum(bool(r.get("above_ma50")) for r in rows) / len(rows)
        pts = (above - 50) / 2.5
        score += pts
        reasons.append({"text": f"{above:.0f}% of stocks above their 50-day average", "points": round(pts)})
        nh, nl = sum(bool(r.get("new_high")) for r in rows), sum(bool(r.get("new_low")) for r in rows)
        pts = 5 if nh > nl else -5 if nl > nh else 0
        score += pts
        reasons.append({"text": f"{nh} new 52-week highs vs {nl} new lows", "points": pts})

    dd = distribution_days(spy)
    pts = 10 if dd <= 2 else 0 if dd <= 4 else -10 if dd == 5 else -20
    score += pts
    reasons.append({"text": f"{dd} distribution day{'s' if dd != 1 else ''} in the last 25 sessions", "points": pts})

    if fear_greed is not None:
        pts = -5 if fear_greed >= 80 else 0
        if pts:
            score += pts
            reasons.append({"text": f"Extreme greed ({fear_greed:.0f}): rallies are crowded", "points": pts})

    pct = int(max(0, min(100, round(score / 10) * 10)))
    label = next(lbl for lim, lbl in LABELS if pct < lim)
    advice = {
        "Defensive": "Protect capital: mostly cash, no new longs except the very best setups.",
        "Cautious": "Small positions, tighter stops, take profits sooner.",
        "Normal": "Normal position sizes in leading stocks with proper setups.",
        "Aggressive": "A healthy uptrend: full exposure to leaders is supported, still with stops.",
    }[label]
    return {"exposure": pct, "label": label, "advice": advice, "distribution_days": dd,
            "reasons": sorted(reasons, key=lambda r: -abs(r["points"]))}
