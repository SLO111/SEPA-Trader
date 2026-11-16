"""vnicorn Pulse: daily confirmations and warnings, i.e. is the stock acting constructively or flashing warning signs?

Our own rule set over daily bars. Each day gets a list of signals; the 10-day tally (confirmations /
warnings, e.g. "7/1") is a quick read of the stock's behaviour.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import atr, ema, sma
from .sepa import rs_line


def signals(df: pd.DataFrame, bench: pd.DataFrame | None = None, pivot: float | None = None, last: int | None = None) -> pd.DataFrame:
    """One row per day: `conf` and `warn` (lists of short labels). `last` limits the work to the final N days."""
    o, h, lo, c, v = (df[k] for k in ("open", "high", "low", "close", "volume"))
    rng = (h - lo).replace(0, np.nan)
    pos = (c - lo) / rng  # where the close sits in the day's range
    up, down = c > c.shift(), c < c.shift()
    vol50 = sma(v, 50)
    rvol = v / vol50
    e21, s50 = ema(c, 21), sma(c, 50)
    a = atr(df, 14)
    good = pos >= 0.5
    good4 = good.astype(int).rolling(4).sum()
    up2 = up & up.shift(1, fill_value=False)
    up_streak = up.astype(int).groupby((~up).cumsum()).cumsum()
    rsl_new_high = None
    if bench is not None and not bench.empty:
        rsl = rs_line(c, bench["close"])
        rsl_new_high = rsl >= rsl.rolling(252, min_periods=60).max()
    outside = (h > h.shift()) & (lo < lo.shift())
    piv = pivot if pivot else h.rolling(50, min_periods=20).max().shift(1)

    conf, warn = [], []
    first = max(0, len(df) - last) if last else 0
    for i in range(first, len(df)):
        cs, ws = [], []
        if i < 2 or np.isnan(pos.iloc[i]):
            conf.append(cs)
            warn.append(ws)
            continue
        if up2.iloc[i]:
            cs.append(f"{int(up_streak.iloc[i])} days up" if up_streak.iloc[i] > 2 else "2 of 2 days up")
        if pos.iloc[i] >= 0.75:
            cs.append("Close near high")
        if h.iloc[i] > h.iloc[i - 1] and lo.iloc[i] > lo.iloc[i - 1]:
            cs.append("Higher high & higher low")
        if up.iloc[i] and rvol.iloc[i] >= 1.5:
            cs.append(f"Up on +{(rvol.iloc[i] - 1) * 100:.0f}% volume")
        if rsl_new_high is not None and bool(rsl_new_high.iloc[i]):
            cs.append("RS line new high")
        if good4.iloc[i] >= 3:
            cs.append(f"{int(good4.iloc[i])} of 4 good closes")
        if c.iloc[i] > e21.iloc[i] and c.iloc[i - 1] <= e21.iloc[i - 1]:
            cs.append("Reclaimed 21-day EMA")
        p = piv if isinstance(piv, float) else piv.iloc[i]
        if p and not np.isnan(p) and c.iloc[i] > p >= c.iloc[i - 1]:
            cs.append("Breakout above pivot")

        if down.iloc[i] and rvol.iloc[i] >= 1.5:
            ws.append(f"Down on +{(rvol.iloc[i] - 1) * 100:.0f}% volume")
        if pos.iloc[i] <= 0.25:
            ws.append("Close near low")
        if lo.iloc[i] < lo.iloc[i - 1] and h.iloc[i] < h.iloc[i - 1]:
            ws.append("Lower low")
        if c.iloc[i] < e21.iloc[i] <= c.iloc[i - 1] or (c.iloc[i - 1] >= e21.iloc[i - 1] and c.iloc[i] < e21.iloc[i]):
            ws.append("Closed below 21-day EMA")
        if not np.isnan(s50.iloc[i]) and c.iloc[i] < s50.iloc[i] and c.iloc[i - 1] >= s50.iloc[i - 1]:
            ws.append("Broke the 50-day MA")
        if outside.iloc[i] and c.iloc[i] < o.iloc[i] and pos.iloc[i] < 0.35:
            ws.append("Outside reversal down")
        if rng.iloc[i] > 1.5 * a.iloc[i] and c.iloc[i] > c.iloc[i - 1] and pos.iloc[i] < 0.4:
            ws.append("Squat: big range, weak close")
        if good4.iloc[i] <= 1:
            ws.append(f"{4 - int(good4.iloc[i])} of 4 bad closes")
        if down.iloc[i] and (c.iloc[i - 1] - c.iloc[i]) > 2 * a.iloc[i]:
            ws.append("Wide down day (>2 ATR)")
        conf.append(cs)
        warn.append(ws)
    return pd.DataFrame({"conf": conf, "warn": warn}, index=df.index[first:])


def summary(df: pd.DataFrame, bench: pd.DataFrame | None = None, days: int = 10) -> dict:
    s = signals(df.iloc[-300:], bench.iloc[-300:] if bench is not None else None, last=days)
    last = s.iloc[-days:]
    c = sum(len(x) for x in last["conf"])
    w = sum(len(x) for x in last["warn"])
    tone = "constructive" if c >= 2 * max(w, 1) else "warning" if w >= 2 * max(c, 1) else "mixed"
    return {
        "today": {"date": s.index[-1].strftime("%Y-%m-%d"), "conf": s["conf"].iloc[-1], "warn": s["warn"].iloc[-1]},
        "conf": c, "warn": w, "days": days, "tone": tone,
        "recent": [{"date": ts.strftime("%Y-%m-%d"), "conf": r.conf, "warn": r.warn} for ts, r in last.iloc[::-1].iterrows() if r.conf or r.warn][:6],
    }
