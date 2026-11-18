from datetime import date

import numpy as np
import pandas as pd
import pytest

from engine import market_tools as mt
from engine.data import fed


def _df(close: np.ndarray, start="2024-01-01", vol=1e6) -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(close))
    c = pd.Series(close, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.005, "low": c * 0.995, "close": c, "volume": vol}, index=idx)


def _market(final_trend: float, n=600):
    """A calm year, then a final stretch that either rallies (greed) or crashes (fear)."""
    rng = np.random.default_rng(1)
    base = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.008, n - 40)))
    tail = base[-1] * np.exp(np.cumsum(np.full(40, final_trend)))
    spy = _df(np.r_[base, tail])
    stocks = {f"S{i}": _df(spy["close"].to_numpy() * (1 + i / 50)) for i in range(10)}
    vix_level = np.r_[np.full(n - 40, 16.0), np.full(40, 12.0 if final_trend > 0 else 40.0)]
    vix = _df(vix_level)
    bonds = _df(np.full(n, 100.0))
    hyg = _df(np.r_[np.full(n - 40, 100.0), 100 * np.exp(np.cumsum(np.full(40, final_trend / 2)))])
    return spy, vix, stocks, bonds, hyg, bonds


def test_fear_greed_reads_rally_as_greed_and_crash_as_fear():
    greed = mt.fear_greed(*_market(+0.006))
    fear = mt.fear_greed(*_market(-0.012))
    assert greed["score"] > 70 and greed["label"] in ("Greed", "Extreme Greed")
    assert fear["score"] < 30 and fear["label"] in ("Fear", "Extreme Fear")
    assert {c["key"] for c in greed["components"]} == set(mt.FG_COMPONENTS)
    assert all(0 <= c["score"] <= 100 for c in greed["components"])
    assert len(greed["history"]) == 252 and greed["previous"]["week"] is not None


@pytest.mark.parametrize("score,label", [(10, "Extreme Fear"), (30, "Fear"), (50, "Neutral"), (65, "Greed"), (90, "Extreme Greed")])
def test_fear_greed_labels(score, label):
    assert mt.fg_label(score) == label


def _rows():
    rng = np.random.default_rng(3)
    hist = {s: _df(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 300))), vol=1e6 * (i + 1)) for i, s in enumerate("ABCDEF")}
    meta = {s: {"name": s, "sector": "Tech" if s in "ABC" else "Energy"} for s in "ABCDEF"}
    return mt.mover_rows(hist, meta)


def test_movers_ordering():
    rows = _rows()
    g = mt.movers(rows, "gainers", 3)
    assert all(r["change_pct"] > 0 for r in g) and g == sorted(g, key=lambda r: -r["change_pct"])
    lo = mt.movers(rows, "losers", 3)
    assert all(r["change_pct"] < 0 for r in lo)
    act = mt.movers(rows, "active", 6)
    assert [r["dollar_volume"] for r in act] == sorted([r["dollar_volume"] for r in act], reverse=True)


def test_sector_rotation_and_leaders():
    rows = _rows()
    scan = [{"symbol": s, "rs_rating": 90 - i * 10, "bull_score": 50, "template_passed": 8 - i} for i, s in enumerate("ABCDEF")]
    sec = mt.sector_rotation(rows, scan)
    assert {s["sector"] for s in sec} == {"Tech", "Energy"} and all(s["trend"] in ("Improving", "Weakening", "Steady") for s in sec)
    assert next(s for s in sec if s["sector"] == "Tech")["leaders"][0] == "A"
    lead = mt.leaders(scan, 3)
    assert [r["symbol"] for r in lead] == ["A", "B", "C"]


def test_screener_presets():
    rows = [
        {"symbol": "V1", "name": "", "sector": "X", "price": 10, "change_pct": 0, "from_high_pct": -2, "rsi14": 60, "above_ma50": True, "return_1m": 1, "return_3m": 2,
         "market_cap_b": 50, "pe": 12, "eps_growth": 6, "peg": 2, "dividend_yield": 4, "beta": 0.5, "rs_rating": 92, "template_passed": 8, "bull_score": 70, "bear_score": 10, "vcp": True,
         "sector_pe": 20, "pe_vs_sector_pct": -40},
        {"symbol": "G1", "name": "", "sector": "X", "price": 10, "change_pct": 0, "from_high_pct": -20, "rsi14": 30, "above_ma50": False, "return_1m": -5, "return_3m": -9,
         "market_cap_b": 5, "pe": 28, "eps_growth": 30, "peg": 0.9, "dividend_yield": 0, "beta": 1.5, "rs_rating": 40, "template_passed": 3, "bull_score": 30, "bear_score": 60, "vcp": False,
         "sector_pe": 20, "pe_vs_sector_pct": 40},
    ]
    ids = lambda **kw: [r["symbol"] for r in mt.screen(rows, **kw)]
    assert ids(preset="undervalued") == ["V1"]
    assert ids(preset="garp") == ["G1"]
    assert ids(preset="dividend") == ["V1"]
    assert ids(preset="sepa_leaders") == ["V1"]
    assert ids(preset="oversold") == ["G1"]
    assert ids(min_cap_b=10) == ["V1"] and ids(max_pe=20) == ["V1"] and ids(above_ma50=True) == ["V1"]


def test_earnings_calendar_reaction():
    h = _df(np.r_[np.full(10, 100.0), np.full(10, 110.0)], start="2026-10-01")
    report_day = h.index[9].strftime("%Y-%m-%d")  # close before = 100, first close after = 110
    entries = {"AAA": {"next_date": "2026-12-01", "history": [{"date": report_day, "eps_estimate": 1, "eps_actual": 1.2, "surprise_pct": 20}]}}
    cal = mt.earnings_calendar(entries, {"AAA": h}, {"AAA": {"name": "Triple A"}}, pd.Timestamp("2026-10-20"))
    assert cal["upcoming"][0]["days_until"] == 42
    assert cal["recent"][0]["reaction_pct"] == pytest.approx(10.0)


def test_earnings_calendar_range():
    h = _df(np.full(30, 100.0), start="2026-10-01")
    entries = {"AAA": {"next_date": "2026-11-20", "history": [{"date": "2026-11-05", "eps_estimate": 1, "eps_actual": 1.1, "surprise_pct": 10}]},
               "BBB": {"next_date": "2026-12-20", "history": [{"date": "2026-10-02", "eps_estimate": 1, "eps_actual": 1.1, "surprise_pct": 10}]}}
    meta = {"AAA": {"name": "A"}, "BBB": {"name": "B"}}
    cal = mt.earnings_calendar(entries, {"AAA": h, "BBB": h}, meta, pd.Timestamp("2026-11-18"),
                               start=pd.Timestamp("2026-11-02"), end=pd.Timestamp("2026-11-29"))
    assert [r["symbol"] for r in cal["upcoming"]] == ["AAA"] and [r["symbol"] for r in cal["recent"]] == ["AAA"]


def test_fed_summary_and_decisions():
    d = fed.demo(date(2026, 11, 15))
    assert d["demo"] and d["target_range"]["upper"] - d["target_range"]["lower"] == pytest.approx(0.25)
    assert d["next_meeting"] == "2026-12-09"
    assert d["decisions"] and d["decisions"][0]["action"] in ("Cut", "Hike")
    p = d["outlook"]["probabilities"]
    assert sum(p.values()) == 100


def test_fred_csv_parsing(monkeypatch):
    class R:
        text = "observation_date,DFEDTARU\n2024-09-17,5.50\n2024-09-18,5.00\n2024-09-19,.\n2024-09-20,5.00\n"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(fed.httpx, "get", lambda *a, **k: R())
    s = fed.fred_series("DFEDTARU")
    assert list(s.values) == [5.5, 5.0, 5.0] and s.index[1] == pd.Timestamp("2024-09-18")


def test_markets_api(client, register):
    h, _ = register("markets-free@test.ro")
    o = client.get("/api/markets/overview", headers=h).json()
    assert [i["symbol"] for i in o["indices"]] == ["SPY", "QQQ", "DIA", "IWM", "^VIX"]
    assert 0 <= o["fear_greed"]["score"] <= 100 and o["fear_greed"]["label"]
    assert o["gainers"] and o["sectors"] and o["leaders"]
    assert all(r["symbol"] not in ("SPY", "^VIX", "TLT") for r in o["gainers"] + o["losers"])  # stocks only
    fg = client.get("/api/markets/fear-greed", headers=h).json()
    assert len(fg["components"]) == 6
    assert client.get("/api/markets/extended-hours", headers=h).json()["available"] is False
    e = client.get("/api/markets/earnings", headers=h).json()  # default: this week and next week
    monday = date.today() - pd.Timedelta(days=date.today().weekday())
    assert e["start"] == str(monday) and e["end"] == str(monday + pd.Timedelta(days=13))
    assert all(e["start"] <= r["date"] <= e["end"] for r in e["upcoming"] + e["recent"])
    day = lambda n: (date.today() + pd.Timedelta(days=n)).isoformat()
    assert client.get(f"/api/markets/earnings?start={day(-30)}&end={day(0)}", headers=h).json()["recent"]
    assert client.get(f"/api/markets/earnings?start={day(0)}&end={day(90)}", headers=h).json()["upcoming"]
    assert client.get(f"/api/markets/earnings?start={day(-60)}&end={day(60)}", headers=h).status_code == 400
    assert client.get("/api/markets/fed", headers=h).json()["next_meeting"]
    assert client.get("/api/markets/screener?preset=dividend", headers=h).status_code == 403  # free plan: screens are Pro
    assert client.get("/api/markets/screener", headers=h).status_code == 200  # the plain list is free
