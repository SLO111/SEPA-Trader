"""Trend Template (8 criteria) and Relative Strength."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import sma

TEMPLATE_LABELS = [
    "Price above the 150-day and 200-day SMA",
    "150-day SMA above the 200-day SMA",
    "200-day SMA trending up for at least 1 month",
    "50-day SMA above the 150-day and 200-day SMA",
    "Price above the 50-day SMA",
    "Price at least 30% above the 52-week low",
    "Price within 25% of the 52-week high",
    "RS Rating of at least 70",
]


def template_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Criteria 1–7 vectorized (a bool per bar). Criterion 8 (RS) is computed across the universe."""
    c = df["close"]
    s50, s150, s200 = sma(c, 50), sma(c, 150), sma(c, 200)
    low52 = df["low"].rolling(252, min_periods=200).min()
    high52 = df["high"].rolling(252, min_periods=200).max()
    out = pd.DataFrame(
        {
            "c1": (c > s150) & (c > s200),
            "c2": s150 > s200,
            "c3": s200 > s200.shift(21),
            "c4": (s50 > s150) & (s50 > s200),
            "c5": c > s50,
            "c6": c >= 1.30 * low52,
            "c7": c >= 0.75 * high52,
        },
        index=df.index,
    )
    valid = s200.notna() & s200.shift(21).notna() & low52.notna()
    return out.where(valid, False).astype(bool)


def rs_raw(close: pd.Series) -> pd.Series:
    """Weighted performance: 40% last 3 months + 20% each for 6, 9 and 12 months."""
    r = lambda n: close / close.shift(n) - 1
    return 0.4 * r(63) + 0.2 * r(126) + 0.2 * r(189) + 0.2 * r(252)


def rs_ratings(raw_by_symbol: dict[str, float]) -> dict[str, int]:
    """RS Rating 1–99 = rank of weighted performance within the analyzed universe (99 = strongest)."""
    ser = pd.Series({s: v for s, v in raw_by_symbol.items() if v is not None and np.isfinite(v)}, dtype=float)
    if ser.empty:
        return {}
    if len(ser) == 1:
        return {ser.index[0]: 50}
    rank = ser.rank(method="average")
    return {s: int(round(1 + 98 * (r - 1) / (len(ser) - 1))) for s, r in rank.items()}


def rs_line(close: pd.Series, bench_close: pd.Series) -> pd.Series:
    """RS line: stock price relative to the index (rising = outperforming the market)."""
    b = bench_close.reindex(close.index).ffill()
    return close / b


def trend_template(df: pd.DataFrame, rs_rating: int | None) -> dict:
    frame = template_frame(df)
    last = frame.iloc[-1].tolist()
    passed = [bool(x) for x in last] + [rs_rating is not None and rs_rating >= 70]
    return {
        "criteria": [{"label": lbl, "passed": p} for lbl, p in zip(TEMPLATE_LABELS, passed)],
        "passed_count": int(sum(passed)),
        "all_passed": all(passed),
    }
