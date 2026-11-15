from datetime import datetime

import pandas as pd

from engine.triggers import ET, evaluate, projected_volume

from .synthetic_patterns import flat_benchmark, vcp_stock


def _append(df: pd.DataFrame, bars: list[tuple[float, float, float]]) -> pd.DataFrame:
    """Append (open, close, volume) bars on the following business days."""
    rows, idx = [], []
    day = df.index[-1]
    for o, c, v in bars:
        day = day + pd.offsets.BDay()
        rows.append({"open": o, "high": max(o, c) * 1.003, "low": min(o, c) * 0.997, "close": c, "volume": v})
        idx.append(day)
    return pd.concat([df, pd.DataFrame(rows, index=pd.DatetimeIndex(idx, name="date"))])


def test_breakout_fires_exactly_on_breakout_bar():
    base = vcp_stock()
    df = _append(base, [(95.6, 99.5, 5e6)])
    bench = flat_benchmark(len(df))
    events = evaluate(df, bench, ["breakout"])
    assert [e.type for e in events] == ["breakout"]
    e = events[0]
    assert 96 <= e.data["pivot"] <= 98.5 and e.data["stop"] < e.data["pivot"] and e.data["rvol"] >= 1.4
    # never earlier: no breakout on any of the previous 30 bars
    for i in range(len(df) - 31, len(df) - 1):
        assert not evaluate(df, bench, ["breakout"], i=i), i


def test_breakout_requires_volume():
    df = _append(vcp_stock(), [(95.6, 99.5, 1.2e6)])  # below 1.4x average
    assert not evaluate(df, None, ["breakout"])


def test_failed_breakout():
    df = _append(vcp_stock(), [(95.6, 99.5, 5e6), (99.4, 98.0, 2e6), (98.0, 96.5, 2e6), (96.5, 94.0, 3e6)])
    types = [e.type for e in evaluate(df, None, ["failed_breakout"])]
    assert types == ["failed_breakout"]
    # fires once: the bar before is not a failed breakout yet
    assert not evaluate(df, None, ["failed_breakout"], i=len(df) - 2)


def test_gap_and_price_levels():
    df = _append(vcp_stock(), [(100.0, 100.5, 2e6)])  # opens ~4.7% above 95.5
    types = {e.type for e in evaluate(df, None, ["gap_up", "gap_down", "price_above", "price_below"], {"price_level": 98})}
    assert types == {"gap_up", "price_above"}


def test_projected_volume_intraday():
    df = vcp_stock().copy()
    today = datetime(2026, 11, 13, 12, 45, tzinfo=ET)  # 195 minutes after the open
    df.index = df.index[:-1].append(pd.DatetimeIndex([pd.Timestamp("2026-11-13")]))
    last = float(df["volume"].iloc[-1])
    assert abs(projected_volume(df, today) - last * 2) < 1
    after_close = datetime(2026, 11, 13, 17, 0, tzinfo=ET)
    assert projected_volume(df, after_close) == last
