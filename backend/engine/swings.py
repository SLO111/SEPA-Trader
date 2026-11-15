"""Swing detection (peaks and troughs) using the ZigZag algorithm."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Swing:
    idx: int
    price: float
    kind: str  # "H" (peak) | "L" (trough)


def zigzag(high: np.ndarray, low: np.ndarray, pct: float) -> tuple[list[Swing], str | None, Swing | None]:
    """Return (confirmed swings, current direction, unconfirmed extreme of the current leg).

    A peak is confirmed once price drops `pct` below it; a trough once price rises `pct` above it.
    Uses only data up to the current bar, so confirmations have no look-ahead.
    """
    n = len(high)
    swings: list[Swing] = []
    if n == 0:
        return swings, None, None
    trend: str | None = None
    hi_i, hi = 0, float(high[0])
    lo_i, lo = 0, float(low[0])
    for i in range(1, n):
        h, l = float(high[i]), float(low[i])
        if trend is None:
            if h > hi:
                hi_i, hi = i, h
            if l < lo:
                lo_i, lo = i, l
            if l <= hi * (1 - pct) and hi_i < i:
                swings.append(Swing(hi_i, hi, "H"))
                trend, lo_i, lo = "down", i, l
            elif h >= lo * (1 + pct) and lo_i < i:
                swings.append(Swing(lo_i, lo, "L"))
                trend, hi_i, hi = "up", i, h
        elif trend == "up":
            if h >= hi:
                hi_i, hi = i, h
            elif l <= hi * (1 - pct):
                swings.append(Swing(hi_i, hi, "H"))
                trend, lo_i, lo = "down", i, l
        else:
            if l <= lo:
                lo_i, lo = i, l
            elif h >= lo * (1 + pct):
                swings.append(Swing(lo_i, lo, "L"))
                trend, hi_i, hi = "up", i, h
    pending = Swing(hi_i, hi, "H") if trend == "up" else Swing(lo_i, lo, "L") if trend == "down" else None
    return swings, trend, pending
