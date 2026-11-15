"""Generators of artificial price series with known patterns, for tests."""

import numpy as np
import pandas as pd


def _frame(close: np.ndarray, volume: np.ndarray, noise: float = 0.004, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-11-13", periods=len(close))
    open_ = np.r_[close[0], close[:-1]]
    wig = np.abs(rng.normal(0, noise, len(close))) * close
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + wig,
            "low": np.minimum(open_, close) - wig,
            "close": close,
            "volume": volume,
        },
        index=pd.DatetimeIndex(idx, name="date"),
    )


def _leg(a: float, b: float, n: int) -> np.ndarray:
    return np.linspace(a, b, n + 1)[1:]


def vcp_stock() -> pd.DataFrame:
    """One-year uptrend, then a base with 25% -> 13% -> 6% contractions on declining volume, price just below the pivot."""
    up = np.geomspace(40, 100, 300)
    base = np.concatenate(
        [
            _leg(100, 75, 15), _leg(75, 98, 20),   # C1: -25%
            _leg(98, 85.3, 10), _leg(85.3, 97, 15),  # C2: ~-13%
            _leg(97, 91.2, 6), _leg(91.2, 95.5, 6),  # C3: ~-6%, near the pivot
        ]
    )
    close = np.concatenate([up, base])
    vol = np.concatenate([np.full(300, 3e6), np.full(35, 2.6e6), np.full(25, 1.8e6), np.full(12, 1.0e6)])
    return _frame(close, vol)


def downtrend_stock() -> pd.DataFrame:
    """One year of gains, then a sell-off with heavy volume on down days."""
    rng = np.random.default_rng(7)
    close = np.concatenate([np.geomspace(50, 120, 280), np.geomspace(120, 70, 90)])
    close = close * (1 + rng.normal(0, 0.006, len(close)))
    vol = np.full(len(close), 2e6)
    down = np.r_[False, close[1:] < close[:-1] * 0.99]
    vol[down & (np.arange(len(close)) > 280)] = 6e6
    return _frame(close, vol, seed=3)


def flat_benchmark(n: int, trend: float = 0.0003) -> pd.DataFrame:
    close = 400 * np.exp(np.arange(n) * trend)
    return _frame(close, np.full(n, 5e7), seed=9)
