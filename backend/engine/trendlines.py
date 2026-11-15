"""Automatic trend lines: resistance through the last two peaks, support through the last two troughs."""

from __future__ import annotations

import pandas as pd

from .swings import zigzag


def auto_trendlines(df: pd.DataFrame, lookback: int = 250, swing_pct: float = 0.06) -> list[dict]:
    d = df.iloc[-lookback:]
    swings, _, _ = zigzag(d["high"].to_numpy(), d["low"].to_numpy(), swing_pct)
    lines = []
    for kind, name, color in (("H", "Resistance", "#f87171"), ("L", "Support", "#4ade80")):
        pts = [s for s in swings if s.kind == kind][-2:]
        if len(pts) < 2:
            continue
        a, b = pts
        slope = (b.price - a.price) / (b.idx - a.idx)
        last = len(d) - 1
        end_price = b.price + slope * (last - b.idx)
        data = [
            {"time": d.index[a.idx].strftime("%Y-%m-%d"), "value": round(a.price, 2)},
            {"time": d.index[b.idx].strftime("%Y-%m-%d"), "value": round(b.price, 2)},
        ]
        if last > b.idx:
            data.append({"time": d.index[last].strftime("%Y-%m-%d"), "value": round(end_price, 2)})
        lines.append({"name": name, "color": color, "data": data, "slope_per_bar": slope})
    return lines
