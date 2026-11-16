import numpy as np
import pandas as pd

from engine import vnicorn_ai as ai
from engine.data.providers import SyntheticProvider
from engine.data.universe import stock_symbols


def _hist():
    p = SyntheticProvider()
    return {s: p.history(s, "1d", 3) for s in stock_symbols()[:14]}, p.history("SPY", "1d", 3)


def test_plan_outcomes_label_target_before_stop():
    idx = pd.bdate_range("2026-01-01", periods=50)
    c = np.full(50, 100.0)
    df = pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c, "volume": 1.0}, index=idx)
    df.iloc[3, df.columns.get_loc("high")] = 104.5  # +2R for a 1 ATR (=2) stop: wins the 2R plan
    res = {(k, tr): (won[0], r[0]) for k, tr, won, r in ai.plan_outcomes(df, np.array([0]), np.array([2.0]), "long", horizon=40)}
    assert res[(1.0, 2.0)] == (1.0, 2.0)
    assert res[(1.0, 3.0)][0] == 0.0  # +6 never reached: a timeout, not a win


def test_train_and_best_plan():
    hist, bench = _hist()
    b = ai.train(hist, bench)
    assert set(b["models"]) == {"long", "short", "move"}
    assert {"auc", "picks", "all_avg_r"} <= set(b["report"]["long"]) and isinstance(b["trusted"]["long"], bool)
    plan = ai.best_plan(b, hist["NVDA"], bench, "long", extra=[(1.2, 2.5)])
    assert plan and plan["stop"] < plan["entry"] < plan["target"] and 0 <= plan["prob"] <= 1
    assert plan["trim"] > plan["entry"]
    short = ai.best_plan(b, hist["NVDA"], bench, "short")
    assert short["target"] < short["entry"] < short["stop"]
    assert 0 <= ai.move_probability(b, ai.features(hist["NVDA"], bench)) <= 1


def test_ideas_get_ai_ratings_and_status(client, register):
    from app.db import SessionLocal
    from app.ideas_service import run_ideas
    from app.models import User

    h, _ = register("ai-user@test.ro")
    with SessionLocal() as db:
        db.query(User).filter_by(email="ai-user@test.ro").one().plan = "pro"
        db.commit()
        run_ideas(db, force=True)
    st = client.get("/api/ai/status", headers=h).json()
    assert st["trained"] and "long" in st["report"]
    ideas = client.get("/api/ideas", headers=h).json()["ideas"]
    assert ideas and any(i["ai"] and 0 <= i["ai"]["prob"] <= 1 for i in ideas)
    scan = client.get("/api/sepa/scan?sort=ai", headers=h).json()["results"]
    assert any(r["ai_prob"] is not None for r in scan)
