import numpy as np
import pandas as pd

from engine.stages import stage_now, weekly_stages
from engine.strategies import run_strategy


def series(path):
    idx = pd.bdate_range("2022-01-03", periods=len(path))
    c = pd.Series(path, index=idx)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6})


def test_cycle_goes_through_all_four_stages():
    flat1 = np.full(250, 50.0)
    up = np.linspace(50, 120, 250)
    top = 120 + 3 * np.sin(np.linspace(0, 12, 200))
    down = np.linspace(120, 60, 250)
    df = series(np.concatenate([np.linspace(80, 50, 200), flat1, up, top, down]))
    st = weekly_stages(df)["stage"]
    seq = [int(x) for x in st[st != st.shift()] if x]
    assert seq == [4, 1, 2, 3, 4]
    assert stage_now(df)["stage"] == 4


def test_uptrend_is_stage_2_and_strategy_runs():
    df = series(np.linspace(50, 150, 400))
    assert stage_now(df)["name"] == "Markup"
    out = run_strategy("market_stage", df, {})
    assert out["histograms"][0]["data"] and any("Markup" in m["text"] for m in out["markers"])
