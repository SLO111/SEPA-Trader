"""Move Detector – stratul 1: Setup Score.

Doua scoruri 0–100, calculate pe fiecare bara (vectorizat, fara look-ahead):
  * Bull Score: cat de "incarcata" e actiunea pentru o miscare majora in sus;
  * Bear Score: cat de mare e riscul unei miscari majore in jos.
Fiecare factor e normalizat la 0..1 si ponderat. Ponderile sunt initiale si vor fi
optimizate prin backtesting / ML (stratul 3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind
from .sepa import rs_line, template_frame

BULL_WEIGHTS = {
    "compression": 0.20,
    "volume": 0.15,
    "trend": 0.25,
    "rs": 0.20,
    "pivot": 0.10,
    "market": 0.10,
}
BEAR_WEIGHTS = {
    "breakdown": 0.30,
    "distribution": 0.20,
    "rs_weak": 0.20,
    "climax": 0.10,
    "failed_breakout": 0.10,
    "market": 0.10,
}
FACTOR_LABELS = {
    "compression": "Compresie de volatilitate",
    "volume": "Volum secat + acumulare",
    "trend": "Trend (Trend Template)",
    "rs": "Forță relativă vs. piață",
    "pivot": "Aproape de maxime / pivot",
    "market": "Regim de piață",
    "breakdown": "Trend deteriorat",
    "distribution": "Zile de distribuție",
    "rs_weak": "Slăbiciune relativă",
    "climax": "Extensie / climax",
    "failed_breakout": "Breakout eșuat",
}


def _clip(s: pd.Series) -> pd.Series:
    return s.clip(0.0, 1.0)


def _pct_rank(s: pd.Series, window: int) -> pd.Series:
    """Percentila valorii curente in fereastra ei trecuta (0 = cea mai mica)."""
    return s.rolling(window, min_periods=window // 2).rank(pct=True)


def _market_regime(bench: pd.DataFrame | None, index: pd.Index) -> pd.Series:
    if bench is None or bench.empty:
        return pd.Series(0.5, index=index)
    c = bench["close"]
    regime = ((c > ind.sma(c, 50)).astype(float) + (c > ind.sma(c, 200)).astype(float)) / 2
    return regime.reindex(index).ffill().fillna(0.5)


def compute_factors(df: pd.DataFrame, bench: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    c, v = df["close"], df["volume"]
    up_day = c > c.shift()
    vol50 = ind.sma(v, 50)
    s50, s150, s200 = ind.sma(c, 50), ind.sma(c, 150), ind.sma(c, 200)
    market = _market_regime(bench, df.index)

    # --- Bull ---
    bb = ind.bollinger(c, 20, 2.0)
    bbw = (bb["upper"] - bb["lower"]) / bb["mid"]
    atr_ratio = ind.atr(df, 10) / ind.atr(df, 50)
    compression = 0.5 * (1 - _pct_rank(bbw, 252)) + 0.5 * _clip((1.2 - atr_ratio) / 0.6)

    dryup = _clip(1 - ind.sma(v, 10) / vol50)
    upvol = (v.where(up_day, 0)).rolling(50).sum() / v.rolling(50).sum()
    accumulation = _clip((upvol - 0.4) / 0.3)
    volume = 0.5 * dryup + 0.5 * accumulation

    trend = template_frame(df).sum(axis=1) / 7.0

    if bench is not None and not bench.empty:
        rsl = rs_line(c, bench["close"])
        lo, hi = rsl.rolling(252, min_periods=120).min(), rsl.rolling(252, min_periods=120).max()
        rs_pos = _clip((rsl - lo) / (hi - lo))
    else:
        r = c / c.shift(126) - 1
        rs_pos = _clip((r + 0.1) / 0.6)

    high60 = df["high"].rolling(60, min_periods=40).max()
    pivot = _clip(1 - ((high60 - c) / high60) / 0.15)

    bull = pd.DataFrame(
        {"compression": compression, "volume": volume, "trend": trend, "rs": rs_pos, "pivot": pivot, "market": market}
    )

    # --- Bear ---
    breakdown = (
        (c < s50).astype(float) + (s50 < s50.shift(10)).astype(float) + (c < s200).astype(float) + (s50 < s150).astype(float)
    ) / 4
    dist_day = (~up_day) & (v > 1.25 * vol50) & (c / c.shift() - 1 < -0.01)
    distribution = _clip(dist_day.astype(float).rolling(25).sum() / 5)
    rs_weak = 1 - rs_pos
    climax = _clip((c / s200 - 1 - 0.4) / 0.6)
    recent_high = df["high"].rolling(15, min_periods=10).max()
    was_at_high = recent_high >= df["high"].rolling(120, min_periods=60).max().shift(15) * 0.999
    failed = _clip(((recent_high - c) / recent_high - 0.03) / 0.12) * was_at_high.astype(float)

    bear = pd.DataFrame(
        {
            "breakdown": breakdown,
            "distribution": distribution,
            "rs_weak": rs_weak,
            "climax": climax,
            "failed_breakout": failed,
            "market": 1 - market,
        }
    )
    valid = s200.notna() & vol50.notna()
    return bull.where(valid), bear.where(valid)


def _score(f: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    w = pd.Series(weights)
    return (f[w.index].fillna(0) * w).sum(axis=1).where(f.notna().any(axis=1)) * 100


def score_series(df: pd.DataFrame, bench: pd.DataFrame | None = None) -> pd.DataFrame:
    bull_f, bear_f = compute_factors(df, bench)
    return pd.DataFrame({"bull": _score(bull_f, BULL_WEIGHTS), "bear": _score(bear_f, BEAR_WEIGHTS)})


def label(score: float) -> str:
    if score >= 75:
        return "Foarte puternic"
    if score >= 60:
        return "Puternic"
    if score >= 45:
        return "Moderat"
    return "Slab"


def analyze(df: pd.DataFrame, bench: pd.DataFrame | None = None, rs_rating: int | None = None) -> dict:
    """Scorurile curente plus explicatia pe factori."""
    bull_f, bear_f = compute_factors(df, bench)
    if rs_rating is not None:
        # Pe univers avem RS Rating-ul real; il combinam cu pozitia liniei RS.
        bull_f.loc[bull_f.index[-1], "rs"] = 0.5 * bull_f["rs"].iloc[-1] + 0.5 * (rs_rating / 99)
        bear_f.loc[bear_f.index[-1], "rs_weak"] = 1 - bull_f["rs"].iloc[-1]

    def pack(f: pd.DataFrame, weights: dict[str, float]) -> dict:
        last = f.iloc[-1]
        if last.isna().all():
            return {"score": None, "label": "Date insuficiente", "factors": []}
        score = float(sum(float(np.nan_to_num(last[k])) * w for k, w in weights.items()) * 100)
        factors = [
            {
                "key": k,
                "label": FACTOR_LABELS[k],
                "value": round(float(np.nan_to_num(last[k])), 3),
                "weight": w,
                "contribution": round(float(np.nan_to_num(last[k])) * w * 100, 1),
            }
            for k, w in weights.items()
        ]
        factors.sort(key=lambda x: -x["contribution"])
        return {"score": round(score, 1), "label": label(score), "factors": factors}

    return {"bull": pack(bull_f, BULL_WEIGHTS), "bear": pack(bear_f, BEAR_WEIGHTS)}
