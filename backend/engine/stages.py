"""Market cycle stages (Wyckoff phases, measured the way Stan Weinstein does with the 30-week average).

  Stage 1 - Accumulation: after a decline, the 30-week MA flattens and price moves sideways around it.
  Stage 2 - Markup:       price above a rising 30-week MA. The only stage to own stocks (Weinstein, Minervini).
  Stage 3 - Distribution: after an advance, the MA flattens and price chops around it. Take profits / tighten stops.
  Stage 4 - Markdown:     price below a falling 30-week MA. Avoid longs; the stage for shorts.

The real cycle is not a sine wave: stages last from weeks to years and a Stage 1/3 can fail and resume
the prior trend. So a stage only changes after it holds for `confirm` weeks.
"""

import numpy as np
import pandas as pd

from .indicators import sma

NAMES = {1: "Accumulation", 2: "Markup", 3: "Distribution", 4: "Markdown"}
COLORS = {1: "#64748b", 2: "#22c55e", 3: "#f59e0b", 4: "#ef4444"}


def weekly_stages(df: pd.DataFrame, ma_weeks: int = 30, slope_weeks: int = 4, flat_pct: float = 1.0, confirm: int = 2) -> pd.DataFrame:
    """Stage per week. Returns columns: close, ma, slope_pct, stage (0 until there is enough history)."""
    w = df["close"].resample("W-FRI").last().dropna()
    ma = sma(w, ma_weeks)
    slope = (ma / ma.shift(slope_weeks) - 1) * 100
    raw = []
    prev_trend = 0  # last clear trend: 2 (up) or 4 (down)
    for c, m, s in zip(w.to_numpy(), ma.to_numpy(), slope.to_numpy()):
        if np.isnan(m) or np.isnan(s):
            raw.append(0)
            continue
        if c > m and s > flat_pct:
            st = prev_trend = 2
        elif c < m and s < -flat_pct:
            st = prev_trend = 4
        else:  # flat MA or price fighting the trend: a base after a decline, a top after an advance
            st = 1 if prev_trend in (0, 4) else 3
        raw.append(st)
    # confirmation: switch only after `confirm` consecutive weeks of the new stage
    out, cur, run, cand = [], 0, 0, 0
    for st in raw:
        if st == cur:
            run, cand = 0, 0
        elif st == cand:
            run += 1
        else:
            cand, run = st, 1
        if cur == 0 or (cand and run >= confirm):
            cur, cand, run = st, 0, 0
        out.append(cur)
    return pd.DataFrame({"close": w, "ma": ma, "slope_pct": slope, "stage": out}, index=w.index)


def stage_now(df: pd.DataFrame) -> dict | None:
    if len(df) < 200:
        return None
    w = weekly_stages(df)
    st = int(w["stage"].iloc[-1])
    if not st:
        return None
    since = w.index[-1]
    for ts, s in zip(w.index[::-1], w["stage"].to_numpy()[::-1]):
        if s != st:
            break
        since = ts
    start = since - pd.Timedelta(days=4)  # weeks are labelled by their Friday; show the Monday the stage began
    return {"stage": st, "name": NAMES[st], "since": start.strftime("%Y-%m-%d"), "weeks": int((w["stage"].loc[since:] == st).sum()),
            "ma30w": round(float(w["ma"].iloc[-1]), 2), "slope_pct": round(float(w["slope_pct"].iloc[-1]), 2)}


def daily_stages(df: pd.DataFrame) -> pd.Series:
    """Weekly stage mapped onto each bar of `df` (known at the end of the previous week, no look-ahead)."""
    w = weekly_stages(df)["stage"].shift(1)
    return w.reindex(df.index, method="ffill").fillna(0).astype(int)
