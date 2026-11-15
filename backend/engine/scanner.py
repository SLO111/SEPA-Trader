"""Scanner: runs through the whole universe computing Trend Template, RS Rating, VCP and Move Detector."""

from __future__ import annotations

from typing import Callable

import pandas as pd

from . import move_detector as md
from .data.universe import SYMBOLS
from .sepa import rs_raw, rs_ratings, trend_template
from .vcp import detect_vcp

BENCHMARK = "SPY"


def scan_universe(history: Callable[[str], pd.DataFrame], symbols: list[str] | None = None) -> list[dict]:
    symbols = symbols or [s for s, m in SYMBOLS.items() if m["sector"] != "ETF"]
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

    ratings = rs_ratings({s: float(rs_raw(df["close"]).iloc[-1]) for s, df in frames.items()})
    rows = []
    for s, df in frames.items():
        rs = ratings.get(s)
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
        rows.append(
            {
                "symbol": s,
                "name": meta["name"],
                "sector": meta["sector"],
                "price": round(float(c.iloc[-1]), 2),
                "change_pct": round(float(c.iloc[-1] / c.iloc[-2] - 1) * 100, 2),
                "rs_rating": rs,
                "template_passed": tt["passed_count"],
                "vcp": vcp["detected"],
                "pivot": vcp.get("pivot"),
                "pivot_distance_pct": vcp.get("distance_pct"),
                "bull_score": an["bull"]["score"],
                "bear_score": an["bear"]["score"],
                "signals": signals,
            }
        )
    return rows


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
