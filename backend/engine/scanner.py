"""Scanner: runs through the whole universe computing Trend Template, RS Rating, VCP and Move Detector."""

from __future__ import annotations

from typing import Callable

import pandas as pd

from . import move_detector as md
from .data.universe import SYMBOLS, stock_symbols
from .sepa import rs_raw, rs_ratings, trend_template
from .vcp import detect_vcp

BENCHMARK = "SPY"


def scan_universe(history: Callable[[str], pd.DataFrame], symbols: list[str] | None = None) -> list[dict]:
    symbols = symbols or stock_symbols()
    try:
        bench = history(BENCHMARK)
    except Exception:
        bench = None

    frames: dict[str, pd.DataFrame] = {}
    for s in symbols:
        try:
            df = history(s)
            if len(df) >= 260:
                frames[s] = df
        except Exception:
            continue

    raws = {}
    for s, df in list(frames.items()):
        try:
            r = float(rs_raw(df["close"]).iloc[-1])
            if r != r or r in (float("inf"), float("-inf")):
                raise ValueError("bad RS")
            raws[s] = r
        except Exception:  # broken prices: leave the stock out instead of failing the whole scan
            frames.pop(s)
    ratings = rs_ratings(raws)
    rows = []
    for s, df in frames.items():
        try:
            rows.append(_scan_row(s, df, ratings.get(s), bench))
        except Exception:
            continue
    return rows


def _scan_row(s: str, df: pd.DataFrame, rs: int | None, bench: pd.DataFrame | None) -> dict:
    """One stock's line in the scan."""
    tt = trend_template(df, rs)
    vcp = detect_vcp(df)
    an = md.analyze(df, bench, rs)
    c = df["close"]
    meta = SYMBOLS.get(s, {"name": s, "sector": ""})
    signals = []
    if tt["all_passed"]:
        signals.append("Trend Template 8/8")
    if vcp["detected"]:
        signals.append("VCP")
    if vcp.get("pivot") and 0 <= vcp.get("distance_pct", 99) <= 5:
        signals.append("Near pivot")
    if rs is not None and rs >= 90:
        signals.append("RS leader")
    if an["bear"]["score"] and an["bear"]["score"] >= 60:
        signals.append("Downside risk")
    return (
        {
            "symbol": s,
            "name": meta["name"],
            "sector": meta["sector"],
            "price": round(float(c.iloc[-1]), 2),
            "change_pct": round(float(c.iloc[-1] / c.iloc[-2] - 1) * 100, 2),
            "rs_rating": rs,
            "template_passed": tt["passed_count"],
            "template_free": sum(bool(tt["criteria"][i]["passed"]) for i in (0, 3, 4)),  # the chart-readable ones (Free plan)
            "vcp": vcp["detected"],
            "pivot": vcp.get("pivot"),
            "pivot_distance_pct": vcp.get("distance_pct"),
            "bull_score": an["bull"]["score"],
            "bear_score": an["bear"]["score"],
            "signals": signals,
        }
    )


def sepa_report(history: Callable[[str], pd.DataFrame], symbol: str, rs_rating: int | None) -> dict:
    df = history(symbol)
    try:
        bench = history(BENCHMARK)
    except Exception:
        bench = None
    vcp = detect_vcp(df)
    return {
        "symbol": symbol.upper(),
        "rs_rating": rs_rating,
        "trend_template": trend_template(df, rs_rating),
        "vcp": vcp,
        "move_detector": md.analyze(df, bench, rs_rating),
    }
