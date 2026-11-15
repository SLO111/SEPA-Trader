"""Trend Template (8 criterii) si Relative Strength."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import sma

TEMPLATE_LABELS = [
    "Prețul peste SMA 150 și SMA 200",
    "SMA 150 peste SMA 200",
    "SMA 200 în creștere de cel puțin o lună",
    "SMA 50 peste SMA 150 și SMA 200",
    "Prețul peste SMA 50",
    "Prețul cu cel puțin 30% peste minimul pe 52 de săptămâni",
    "Prețul la cel mult 25% sub maximul pe 52 de săptămâni",
    "RS Rating de cel puțin 70",
]


def template_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Criteriile 1–7 vectorizate (bool pe fiecare bara). Criteriul 8 (RS) se calculeaza pe univers."""
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
    """Performanta ponderata: 40% ultimele 3 luni + 20% fiecare pentru 6, 9 si 12 luni."""
    r = lambda n: close / close.shift(n) - 1
    return 0.4 * r(63) + 0.2 * r(126) + 0.2 * r(189) + 0.2 * r(252)


def rs_ratings(raw_by_symbol: dict[str, float]) -> dict[str, int]:
    """RS Rating 1–99 = pozitia performantei ponderate in universul analizat (99 = cea mai puternica)."""
    ser = pd.Series({s: v for s, v in raw_by_symbol.items() if v is not None and np.isfinite(v)}, dtype=float)
    if ser.empty:
        return {}
    if len(ser) == 1:
        return {ser.index[0]: 50}
    rank = ser.rank(method="average")
    return {s: int(round(1 + 98 * (r - 1) / (len(ser) - 1))) for s, r in rank.items()}


def rs_line(close: pd.Series, bench_close: pd.Series) -> pd.Series:
    """Linia RS: pretul actiunii raportat la indice (in sus = bate piata)."""
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
