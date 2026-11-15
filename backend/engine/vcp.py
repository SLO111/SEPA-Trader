"""Detectarea pattern-ului VCP (Volatility Contraction Pattern): corectii succesive tot mai mici,
cu volum in scadere, care se termina aproape de un pivot (punctul de cumparare la breakout)."""

from __future__ import annotations

import pandas as pd

from .swings import zigzag


def detect_vcp(df: pd.DataFrame, lookback: int = 130, swing_pct: float = 0.04) -> dict:
    d = df.iloc[-lookback:]
    if len(d) < 40:
        return {"detected": False, "reason": "Istoric insuficient", "contractions": []}
    high, low, vol = d["high"].to_numpy(), d["low"].to_numpy(), d["volume"].to_numpy()
    swings, trend, pending = zigzag(high, low, swing_pct)
    pts = swings + ([pending] if pending is not None else [])

    # Baza incepe la cel mai inalt varf din fereastra.
    highs = [s for s in pts if s.kind == "H"]
    if not highs:
        return {"detected": False, "reason": "Nicio bază identificată", "contractions": []}
    top = max(highs, key=lambda s: s.price)
    pts = [s for s in pts if s.idx >= top.idx]

    contractions = []
    for a, b in zip(pts, pts[1:]):
        if a.kind == "H" and b.kind == "L":
            depth = (a.price - b.price) / a.price
            contractions.append(
                {
                    "start": d.index[a.idx].strftime("%Y-%m-%d"),
                    "end": d.index[b.idx].strftime("%Y-%m-%d"),
                    "high": round(a.price, 2),
                    "low": round(b.price, 2),
                    "depth_pct": round(depth * 100, 1),
                    "avg_volume": float(vol[a.idx : b.idx + 1].mean()),
                }
            )

    result = {"detected": False, "contractions": contractions}
    if len(contractions) < 2:
        result["reason"] = "Mai puțin de 2 contracții"
        return result

    depths = [c["depth_pct"] for c in contractions]
    decreasing = all(b <= a * 1.1 for a, b in zip(depths, depths[1:]))
    first_ok = 8 <= depths[0] <= 45
    last_tight = depths[-1] <= 12
    vol_dry = contractions[-1]["avg_volume"] < contractions[0]["avg_volume"]
    pivot = contractions[-1]["high"]
    stop = contractions[-1]["low"]
    close = float(d["close"].iloc[-1])
    dist = (pivot - close) / pivot * 100

    result.update(
        {
            "pivot": pivot,
            "stop": round(stop, 2),
            "risk_pct": round((pivot - stop) / pivot * 100, 1),
            "distance_pct": round(dist, 1),
            "volume_dryup": bool(vol_dry),
            "checks": {
                "Contracții descrescătoare": decreasing,
                "Prima corecție între 8% și 45%": first_ok,
                "Ultima contracție sub 12%": last_tight,
                "Volum în scădere": vol_dry,
                "Prețul aproape de pivot (≤ 5% sub, ≤ 3% peste)": -3 <= dist <= 5,
            },
        }
    )
    result["detected"] = bool(decreasing and first_ok and last_tight and dist >= -3 and dist <= 15)
    if not result["detected"]:
        result["reason"] = "Contracțiile nu respectă tiparul VCP"
    for c in contractions:
        c.pop("avg_volume")
    return result
