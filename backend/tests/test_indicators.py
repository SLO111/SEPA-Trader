import numpy as np
import pandas as pd

from engine import indicators as ind
from engine.data.providers import SyntheticProvider


def test_synthetic_is_deterministic_and_valid():
    a = SyntheticProvider().history("AAPL")
    b = SyntheticProvider().history("AAPL")
    pd.testing.assert_frame_equal(a, b)
    assert (a["high"] >= a[["open", "close"]].max(axis=1)).all()
    assert (a["low"] <= a[["open", "close"]].min(axis=1)).all()
    assert (a["close"] > 0).all()


def test_sma_and_rsi_bounds():
    s = pd.Series(np.arange(1, 101, dtype=float))
    assert ind.sma(s, 10).iloc[-1] == np.mean(np.arange(91, 101))
    r = ind.rsi(SyntheticProvider().history("MSFT")["close"]).dropna()
    assert r.between(0, 100).all()


def test_no_lookahead():
    df = SyntheticProvider().history("NVDA")
    full = ind.sma(df["close"], 50)
    cut = ind.sma(df["close"].iloc[:400], 50)
    pd.testing.assert_series_equal(full.iloc[:400], cut)


def test_crossovers():
    fast = pd.Series([1, 2, 3, 2, 1], dtype=float)
    slow = pd.Series([2, 2, 2, 2, 2], dtype=float)
    up, down = ind.crossovers(fast, slow)
    assert up.tolist() == [False, False, True, False, False]
    assert down.tolist() == [False, False, False, True, False]


def test_weekly_resample():
    w = SyntheticProvider().history("AAPL", "1wk")
    assert (w.index.dayofweek == 4).all()
