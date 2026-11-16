"""Exposure meter, earnings warnings, industry groups, quarterly growth (Phase B)."""

import numpy as np
import pandas as pd

from app.db import SessionLocal
from app.models import User


def _plan(email, plan):
    with SessionLocal() as db:
        db.query(User).filter_by(email=email).one().plan = plan
        db.commit()


def _index(trend: float, n: int = 400, dist_days: int = 0) -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-11-13", periods=n)
    close = 100 * np.exp(np.cumsum(np.full(n, trend)))
    vol = np.full(n, 1e6)
    df = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": vol}, index=idx)
    for k in range(dist_days):  # down days on higher volume inside the last 25 sessions
        i = n - 2 - 3 * k
        df.iloc[i, df.columns.get_loc("close")] = df["close"].iloc[i - 1] * 0.99
        df.iloc[i, df.columns.get_loc("volume")] = 2e6
    return df


def test_exposure_up_vs_down_market():
    from engine.exposure import distribution_days, exposure

    up_rows = [{"above_ma50": True, "new_high": True, "new_low": False}] * 80 + [{"above_ma50": False, "new_high": False, "new_low": False}] * 20
    dn_rows = [{"above_ma50": False, "new_high": False, "new_low": True}] * 85 + [{"above_ma50": True, "new_high": False, "new_low": False}] * 15
    bull = exposure(_index(0.002), _index(0.002), up_rows, 55)
    bear = exposure(_index(-0.002, dist_days=6), None, dn_rows, 20)
    assert bull["exposure"] >= 80 and bull["label"] == "Aggressive"
    assert bear["exposure"] <= 20 and bear["label"] == "Defensive" and bear["distribution_days"] >= 6
    assert distribution_days(_index(0.001)) == 0 and bull["reasons"]


def test_exposure_api_gated(client, register):
    h, _ = register("expo@test.ro")
    free = client.get("/api/markets/exposure", headers=h).json()
    assert free["locked"] and free["label"] and "exposure" not in free
    _plan("expo@test.ro", "pro")
    pro = client.get("/api/markets/exposure", headers=h).json()
    assert 0 <= pro["exposure"] <= 100 and pro["reasons"]
    assert client.get("/api/markets/overview", headers=h).json()["exposure"]["exposure"] == pro["exposure"]


def test_earnings_in_days(monkeypatch):
    from app import market_data

    soon = (pd.Timestamp.today().normalize() + pd.offsets.BDay(2)).strftime("%Y-%m-%d")
    far = (pd.Timestamp.today().normalize() + pd.offsets.BDay(30)).strftime("%Y-%m-%d")
    monkeypatch.setattr(market_data, "cached", lambda kind, s: {"next_date": soon if s == "A" else far})
    assert market_data.earnings_in_days("A") == 2 and market_data.earnings_in_days("B") is None


def test_groups_ranking_and_gating(client, register):
    from engine.industry import group_of, rank_groups, symbol_ranks

    assert group_of("AAPL") and group_of("ZZZZ", "Tech") == "Tech"
    rows = [{"symbol": s, "sector": "X", "return_3m": r, "return_1m": 1, "change_pct": 0} for s, r in (("ZZA", 10), ("ZZB", 5), ("ZZC", -5))]
    scan = [{"symbol": "ZZA", "rs_rating": 95}, {"symbol": "ZZB", "rs_rating": 90}, {"symbol": "ZZC", "rs_rating": 20}]
    g = rank_groups(rows, scan, {"ZZA": "Chips", "ZZB": "Chips", "ZZC": "Banks"})
    assert g[0]["group"] == "Chips" and g[0]["rank"] == 1 and g[0]["leaders_pct"] == 100
    assert symbol_ranks(g)["ZZC"]["rank"] == 2
    h, _ = register("groups@test.ro")
    _plan("groups@test.ro", "pro")
    assert client.get("/api/markets/groups", headers=h).status_code == 403
    _plan("groups@test.ro", "premium")
    r = client.get("/api/markets/groups", headers=h).json()
    assert r["count"] > 3 and r["groups"][0]["rank"] == 1
    assert "group_rank" in client.get("/api/markets/screener", headers=h).json()["results"][0]


def test_quarterly_growth_table(client, register):
    from engine.quarterly import growth_table

    eps = [{"date": f"2026-{m:02d}-28", "eps_actual": v} for m, v in ((10, 2.0), (7, 1.6), (4, 1.3), (1, 1.2))] + \
          [{"date": f"2025-{m:02d}-28", "eps_actual": v} for m, v in ((10, 1.0), (7, 1.0), (4, 1.0), (1, 1.0))]
    t = growth_table(eps)
    assert [q["eps_yoy"] for q in t["quarters"][:4]] == [100.0, 60.0, 30.0, 20.0]
    assert t["eps_accelerating"] is True and t["canslim_c"] is True
    h, _ = register("quarterly@test.ro")
    free = client.get("/api/stock/AAPL/quarterly", headers=h).json()
    assert free["locked"] and len(free["quarters"]) == 1
    _plan("quarterly@test.ro", "pro")
    pro = client.get("/api/stock/AAPL/quarterly", headers=h).json()
    assert len(pro["quarters"]) >= 4 and pro["quarters"][0]["revenue"]


def test_summary_exposure_gate():
    from app.plans import PLANS
    from engine.feed import gate_summary

    d = {"ideas": {"count": 1, "top": []}, "move_detector": {}, "pulse": {}, "exposure": {"exposure": 60, "label": "Normal", "advice": "x"}}
    assert "exposure" not in gate_summary(d, PLANS["free"])["exposure"]
    assert gate_summary(d, PLANS["pro"])["exposure"]["exposure"] == 60
