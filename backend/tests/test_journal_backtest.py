from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.db import SessionLocal
from app.models import User
from engine import backtest as bt
from engine.data.providers import SyntheticProvider
from engine.journal import Trade, statistics, trade_metrics
from engine.trade_review import review

from .synthetic_patterns import flat_benchmark, vcp_stock
from .test_triggers import _append


def _plan(email, plan):
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).one()
        u.plan = plan
        db.commit()


# ------------------------------------------------------------------ journal math

def test_trade_metrics_long_and_short():
    t = Trade(1, "X", "long", date(2026, 1, 5), 100, 10, stop_price=92, target_price=124, exit_date=date(2026, 1, 25), exit_price=116, fees=2)
    m = trade_metrics(t)
    assert m["pnl"] == 158 and m["return_pct"] == 16 and m["r_multiple"] == 2.0
    assert m["risk_pct"] == 8 and m["reward_risk"] == 3 and m["hold_days"] == 20
    s = Trade(2, "Y", "short", date(2026, 1, 5), 50, 10, stop_price=55, exit_date=date(2026, 1, 10), exit_price=45)
    assert trade_metrics(s)["r_multiple"] == 1.0 and trade_metrics(s)["pnl"] == 50
    open_t = Trade(3, "Z", "long", date(2026, 1, 5), 10, 100, stop_price=9)
    assert trade_metrics(open_t, last_price=11)["status"] == "open" and trade_metrics(open_t, 11)["pnl"] == 100


def test_statistics():
    d = lambda m, dd: date(2026, m, dd)
    trades = [
        Trade(1, "A", "long", d(1, 2), 100, 10, 95, None, d(1, 10), 110, setup="VCP breakout"),   # +10%, +2R, +100
        Trade(2, "B", "long", d(1, 12), 100, 10, 95, None, d(1, 20), 95, setup="VCP breakout"),   # -5%, -1R, -50
        Trade(3, "C", "long", d(2, 2), 50, 20, 48, None, d(2, 12), 56, setup="Pullback to MA"),   # +12%, +3R, +120
        Trade(4, "D", "long", d(2, 14), 50, 20, 48, None, d(2, 20), 48, setup="Pullback to MA"),  # -4%, -1R, -40
        Trade(5, "E", "long", d(3, 1), 20, 10, 19),  # open
    ]
    s = statistics(trades)
    assert s["closed_trades"] == 4 and s["open_trades"] == 1 and s["win_rate"] == 50
    assert s["avg_win_pct"] == 11 and s["avg_loss_pct"] == -4.5 and s["win_loss_ratio"] == pytest.approx(2.44, abs=0.01)
    assert s["expectancy_pct"] == 3.25 and s["expectancy_r"] == 0.75 and s["expectancy_usd"] == 32.5
    assert s["profit_factor"] == pytest.approx(220 / 90, abs=0.01) and s["total_pnl"] == 130
    assert s["max_drawdown"] == -50 and s["max_win_streak"] == 1 and s["max_loss_streak"] == 1
    # an early loss counts as drawdown from the starting point (0)
    early = statistics([Trade(9, "L", "long", d(1, 2), 100, 10, 95, None, d(1, 5), 90), *trades[:1]])
    assert early["max_drawdown"] == -100
    assert [x["value"] for x in s["equity_curve"]] == [100, 50, 170, 130]
    assert {x["setup"]: x["trades"] for x in s["by_setup"]} == {"VCP breakout": 2, "Pullback to MA": 2}


# ------------------------------------------------------------------ trade review

def _breakout_then_rally():
    df = _append(vcp_stock(), [(95.6, 99.5, 5e6)] + [(99.5 + i, 100.5 + i, 3e6) for i in range(15)])
    return df, flat_benchmark(len(df))


def test_review_textbook_trade_scores_high():
    df, bench = _breakout_then_rally()
    entry_day = df.index[-16].date()  # the breakout bar
    t = Trade(1, "X", "long", entry_day, 99.5, 100, stop_price=93, exit_date=df.index[-1].date(), exit_price=114)
    r = review(t, df, bench)
    assert r["grade"] in ("A", "B"), r
    assert any("proper breakout entry" in c["text"] for c in r["checks"])


def _rally_then_drop():
    df, _ = _breakout_then_rally()
    df = _append(df, [(114.0, 108.0, 3e6), (108.0, 103.0, 4e6)])
    return df, flat_benchmark(len(df))


def test_review_poor_trade_scores_low():
    df, bench = _rally_then_drop()
    # chased ~12% above the base after the run-up, no stop, then sold at a loss
    t = Trade(2, "X", "long", df.index[-7].date(), 110.5, 100, stop_price=None, exit_date=df.index[-1].date(), exit_price=103)
    r = review(t, df, bench)
    assert r["grade"] in ("D", "F"), r
    assert any("No stop-loss" in m for m in r["mistakes"]) and any("extended" in m for m in r["mistakes"])


def test_review_rejects_prices_that_do_not_match_the_market():
    df, bench = _breakout_then_rally()
    t = Trade(4, "X", "long", df.index[-16].date(), 300, 10, stop_price=280, exit_date=df.index[-1].date(), exit_price=310)
    r = review(t, df, bench)
    assert r["grade"] is None and "far from where" in r["summary"]


def test_review_detects_ignored_stop():
    df, bench = _breakout_then_rally()
    df = _append(df, [(114.0, 105.0, 3e6), (105.0, 98.6, 4e6), (98.6, 95.0, 5e6)])
    bench = flat_benchmark(len(df))
    entry = df.index[-19].date()  # the breakout bar
    # stop at 97 was hit a few days after entry, but the trade was held and closed at 95
    t = Trade(3, "X", "long", entry, 99.5, 100, stop_price=97, exit_date=df.index[-1].date(), exit_price=95)
    df.loc[df.index[-15], "low"] = 96
    r = review(t, df, bench)
    assert any(c["category"] == "Discipline" and c["status"] == "fail" for c in r["checks"])


# ------------------------------------------------------------------ backtesting

def test_triple_barrier_labels():
    idx = pd.bdate_range("2026-01-01", periods=30)
    up = pd.DataFrame({"close": np.r_[100, np.linspace(101, 125, 15), np.full(14, 125.0)]}, index=idx)  # +20% by day ~12
    up["high"], up["low"] = up["close"], up["close"]
    assert bt.triple_barrier(up).iloc[0] == 1.0
    stopped = up.copy()
    stopped.loc[idx[2], "low"] = 90  # stop hit before the target
    assert bt.triple_barrier(stopped).iloc[0] == 0.0
    assert bt.triple_barrier(up).iloc[-1] != bt.triple_barrier(up).iloc[-1]  # NaN: future unknown


def test_strategy_backtest_and_validation():
    p = SyntheticProvider()
    res = bt.strategy_backtest(p.history("NVDA"), "ma_cross_bot", {"fast": 20, "slow": 50})
    s = res["stats"]
    assert s["trades"] == len(res["trades"]) > 0 and 0 <= s["win_rate"] <= 100
    assert len(res["equity"]) == len(res["buy_hold"]) and res["equity"][0]["value"] == 0
    data = bt.build_dataset({k: p.history(k) for k in ("AAPL", "MSFT", "NVDA", "KO", "XOM", "JPM")}, p.history("SPY"))
    v = bt.validate_move_detector(data)
    assert v["samples"] == len(data) and v["bull"]["buckets"] and 0 <= v["bull"]["base_rate"] <= 100
    w = bt.walk_forward(data)
    if w["available"]:
        assert all(f["train_until"] < f["test_from"] for f in w["folds"])  # never trains on the test period
        assert 0 <= w["avg_auc_model"] <= 1


# ------------------------------------------------------------------ API

def test_journal_api(client, register):
    h, _ = register("journal@test.ro")
    close = SyntheticProvider().history("AAPL")["close"]
    days = close.index
    entry, exit_ = round(float(close.iloc[-60]), 2), round(float(close.iloc[-40]), 2)
    stop = round(entry * 0.93, 2)
    base = {"symbol": "aapl", "side": "long", "entry_date": days[-60].date().isoformat(), "entry_price": entry, "shares": 10, "stop_price": stop}
    r = client.post("/api/journal/trades", headers=h, json={**base, "exit_date": days[-40].date().isoformat(), "exit_price": exit_, "setup": "VCP breakout"})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["symbol"] == "AAPL" and t["status"] == "closed" and t["r_multiple"] == round((exit_ - entry) / (entry - stop), 2)
    o = client.post("/api/journal/trades", headers=h, json=base).json()
    assert o["status"] == "open" and o["last_price"] and o["pnl"] is not None
    assert client.post("/api/journal/trades", headers=h, json={**base, "stop_price": entry * 1.05}).status_code == 422  # stop above entry
    assert client.post("/api/journal/trades", headers=h, json={**base, "exit_price": 120}).status_code == 422  # exit price without date
    s = client.get("/api/journal/stats", headers=h).json()
    assert s["closed_trades"] == 1 and s["open_trades"] == 1 and s["win_rate"] == (100 if exit_ > entry else 0)
    assert client.get(f"/api/journal/trades/{t['id']}/review", headers=h).status_code == 403  # free plan
    assert client.post("/api/backtest/strategy", headers=h, json={"symbol": "AAPL", "strategy": "ma_cross_bot"}).status_code == 403

    _plan("journal@test.ro", "premium")
    rv = client.get(f"/api/journal/trades/{t['id']}/review", headers=h).json()
    assert rv["grade"] in list("ABCDF") and rv["checks"]
    bs = client.post("/api/backtest/strategy", headers=h, json={"symbol": "AAPL", "strategy": "rsi_bot"})
    assert bs.status_code == 200 and "stats" in bs.json()
    md = client.get("/api/backtest/move-detector", headers=h).json()
    assert md["validation"]["samples"] > 0 and "ml_up" in md


def test_free_journal_limit(client, register):
    h, _ = register("journal-limit@test.ro")
    d = SyntheticProvider().history("KO").index[-30].date().isoformat()
    for _ in range(20):
        assert client.post("/api/journal/trades", headers=h, json={"symbol": "KO", "entry_date": d, "entry_price": 60, "shares": 1}).status_code == 200
    assert client.post("/api/journal/trades", headers=h, json={"symbol": "KO", "entry_date": d, "entry_price": 60, "shares": 1}).status_code == 403
