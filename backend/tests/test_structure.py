import pandas as pd

from engine.structure import analyze
from engine.strategies import run_strategy


def frame(bars):
    idx = pd.bdate_range("2025-01-01", periods=len(bars))
    return pd.DataFrame([dict(open=c, high=h, low=l, close=c, volume=1000) for h, l, c in bars], index=idx)


def test_bear_count_completes_in_order():
    bars = [
        (110, 100, 105),
        (109, 99, 104),   # 1 lower low
        (105, 97, 98),    # 2 close below prev low (99); also a lower low
        (100, 96, 97),    # step 3: LL #1
        (99, 95, 96),     # step 3: LL #2 -> 3
        (97, 90, 91),     # 4 close below 95
        (95, 89, 90),
    ]
    r = analyze(frame(bars))
    steps = [(e.side, e.step) for e in r.events if e.side == "bear"]
    assert steps == [("bear", 1), ("bear", 2), ("bear", 3), ("bear", 4)]
    assert r.state["regime"] == "bear"
    # defence trails lower highs: after bar 6 the level is the prior high 97
    assert r.state["defence_level"] == 97


def test_opposite_close_resets_count_and_ends_defence():
    bars = [(110, 100, 105), (109, 99, 104), (105, 97, 98), (120, 104, 119)]  # close above prev high
    r = analyze(frame(bars))
    assert r.state["bear_step"] == 0


def test_strategy_runs():
    bars = [(200 - 3 * i, 190 - 3 * i, 191 - 3 * i) for i in range(30)] + [(110 + 3 * i, 100 + 3 * i, 109 + 3 * i) for i in range(30)]
    out = run_strategy("structure_count", frame(bars), {"steps": 1})
    texts = [m["text"] for m in out["markers"]]
    assert "Bear 4/4" in texts and "Bull 4/4" in texts
