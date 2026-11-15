from datetime import date

import pandas as pd
import pytest

from engine.portfolio import LedgerError, Txn, classify, dividends_received, holdings, period_start, twr_index, value_series


def _closes(values: dict[str, list[float]], start="2026-01-05"):
    idx = pd.bdate_range(start, periods=len(next(iter(values.values()))))
    return {s: pd.Series(v, index=idx, dtype=float) for s, v in values.items()}, idx


def test_average_cost_and_realized():
    t = [Txn(date(2026, 1, 5), "AAPL", "buy", 10, 100), Txn(date(2026, 1, 6), "AAPL", "buy", 10, 120), Txn(date(2026, 1, 7), "AAPL", "sell", 5, 150, 1)]
    h = holdings(t)["AAPL"]
    assert h["shares"] == 15 and h["avg_cost"] == pytest.approx(110) and h["realized"] == pytest.approx(199)
    with pytest.raises(LedgerError):
        holdings(t + [Txn(date(2026, 1, 8), "AAPL", "sell", 16, 150)])


def test_twr_ignores_deposits():
    closes, idx = _closes({"X": [100, 110, 110, 121]})
    txns = [Txn(idx[0].date(), "X", "buy", 10, 100), Txn(idx[2].date(), "X", "buy", 10, 110)]  # add money on day 3
    vs = value_series(txns, closes)
    assert vs["value"].tolist() == [1000, 1100, 2200, 2420]
    assert vs["flow"].tolist() == [1000, 0, 1100, 0]
    tw = twr_index(vs)
    assert tw.iloc[-1] == pytest.approx(1.21)  # +10% then +10%, the deposit does not count as gain


def test_dividends_received_only_for_shares_held_before_ex_date():
    t = [Txn(date(2026, 1, 5), "KO", "buy", 100, 60), Txn(date(2026, 3, 2), "KO", "buy", 50, 62)]
    divs = {"KO": pd.Series([0.5, 0.5], index=pd.DatetimeIndex(["2026-02-13", "2026-05-15"]))}
    got = dividends_received(t, divs)
    assert [(d["date"], d["amount"]) for d in got] == [("2026-02-13", 50.0), ("2026-05-15", 75.0)]


def test_period_start():
    idx = pd.bdate_range("2025-12-01", "2026-03-31")
    assert period_start(idx, "YTD") == pd.Timestamp("2025-12-31")
    assert period_start(idx, "1W") == idx[-6]
    assert period_start(idx, "ALL") == idx[0]


def _pos(symbol, sector, value=1.0, beta=1.0, vol=0.25, y=0.0, pe=20, cap=200, g=5, r6=0.05, r12=0.1):
    return {"symbol": symbol, "sector": sector, "value": value,
            "fundamentals": {"dividend_yield": y, "pe": pe, "market_cap_b": cap, "eps_growth": g},
            "metrics": {"beta": beta, "volatility": vol, "return_6m": r6, "return_12m": r12}}


def test_classify_dividend_portfolio():
    c = classify([_pos("VZ", "Communication Services", y=6.5, beta=0.4, vol=0.18, pe=10), _pos("MO", "Consumer Staples", y=7, beta=0.5, vol=0.2, pe=10),
                  _pos("O", "Real Estate", y=5.6, beta=0.8, vol=0.22, pe=50), _pos("CVX", "Energy", y=4.4, beta=0.9, vol=0.25, pe=17)])
    assert c["primary"] == "dividend" and c["risk_level"] <= 2
    assert "Dividend Income" in c["label"]


def test_classify_aggressive_tech_portfolio():
    c = classify([_pos(s, "Technology", beta=1.8, vol=0.6, y=0, pe=90, g=45, r6=0.3, r12=0.7) for s in ("NVDA", "AMD", "PLTR", "SMCI")])
    assert c["primary"] in ("aggressive", "concentrated", "growth")
    keys = [c["primary"], *c["secondary"]]
    assert "aggressive" in keys and c["risk_level"] >= 4
    assert c["sectors"][0] == {"sector": "Technology", "weight": 100.0}


def test_classify_balanced_portfolio():
    sectors = ["Technology", "Financials", "Health Care", "Energy", "Industrials", "Consumer Staples", "Utilities"]
    c = classify([_pos(f"S{i}", s) for i, s in enumerate(sectors)])
    assert c["primary"] == "balanced"


def test_classify_empty():
    assert classify([])["label"] == "Empty"
