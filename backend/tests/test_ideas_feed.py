from datetime import date

import numpy as np
import pandas as pd

from app.db import SessionLocal
from app.models import User
from engine import feed
from engine.data.providers import SyntheticProvider
from engine.data.universe import stock_symbols
from engine.ideas import generate, update_status
from engine.scanner import scan_universe


def _plan(email, plan):
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).one()
        u.plan = plan
        db.commit()


def test_generated_ideas_are_consistent():
    p = SyntheticProvider()
    ideas = generate({s: p.history(s) for s in stock_symbols()}, {r["symbol"]: r for r in scan_universe(p.history)})
    assert ideas
    for i in ideas:
        assert i.rr >= 2 and 0 < i.weight <= 20 and i.timeframe in ("SWING", "TRADE", "INVEST", "SHORT")
        if i.side == "long":
            assert i.stop < i.entry < i.trim < i.target
        else:
            assert i.target < i.trim < i.entry < i.stop
        assert abs(i.entry - i.stop) / i.entry <= 0.09


def _bars(closes, start="2026-10-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.array(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.005, "low": c * 0.995, "close": c, "volume": 1e6}, index=idx)


IDEA = {"entry": 100, "stop": 95, "trim": 107, "target": 115, "side": "long"}


def test_idea_lifecycle_target():
    df = _bars([99, 99, 101, 104, 108, 112, 116, 117])
    st = update_status(IDEA, df, df.index[0])
    assert st["status"] == "TARGET" and st["trimmed"] and st["r_multiple"] == 3.0 and not st["open"]


def test_idea_lifecycle_stopped_and_cancel():
    stopped = update_status(IDEA, _bars([99, 101, 98, 94, 93]), pd.Timestamp("2026-10-01"))
    assert stopped["status"] == "STOPPED" and stopped["r_multiple"] == -1.0
    cancel = update_status(IDEA, _bars([99, 97, 94, 92]), pd.Timestamp("2026-10-01"))
    assert cancel["status"] == "CANCEL" and cancel["pnl_pct"] is None  # never triggered
    waiting = update_status(IDEA, _bars([99, 98.5, 99.2]), pd.Timestamp("2026-10-01"))
    assert waiting["status"] == "WAIT" and waiting["open"]


def test_feed_builders():
    today = date(2026, 11, 16)
    e = {"NVDA": {"next_date": "2026-11-17", "next_eps_estimate": 1.4, "history": [{"date": "2026-11-14", "eps_estimate": 1.2, "eps_actual": 1.3, "surprise_pct": 8.3}]}}
    items = feed.earnings_items(e, {}, today)
    assert {i["title"] for i in items} == {"$NVDA beats EPS estimates by 8.3%", "$NVDA reports earnings tomorrow"}
    rows = [{"symbol": "AMD", "name": "AMD", "change_pct": -8.8, "rel_volume": 3.2, "price": 150.0, "new_high": False},
            {"symbol": "AVGO", "name": "Broadcom", "change_pct": 1.0, "rel_volume": 1.0, "price": 300.0, "new_high": True}]
    m = feed.mover_items(rows, {"AVGO": {"rs_rating": 95}}, "2026-11-16")
    assert [x["kind"] for x in m] == ["mover", "high"] and m[0]["severity"] == "bear" and "drops 8.8%" in m[0]["title"]
    news = feed.news_items([
        {"id": 1, "headline": "FDA approves Lilly's new obesity drug", "related": "LLY", "url": "https://x"},
        {"id": 2, "headline": "Five stocks to watch this week", "related": ""},
    ])
    assert len(news) == 1 and news[0]["symbol"] == "LLY"


def test_ideas_and_feed_api(client, register):
    from app.ideas_service import build_feed, run_ideas

    h, _ = register("ideas-user@test.ro")
    assert client.get("/api/ideas", headers=h).status_code == 403  # free plan
    with SessionLocal() as db:
        assert run_ideas(db)  # generated
        assert run_ideas(db) == []  # once per trading day
        first = build_feed(db)
        assert build_feed(db) == 0 or build_feed(db) < first  # events are stored once
    _plan("ideas-user@test.ro", "pro")
    r = client.get("/api/ideas", headers=h).json()
    assert r["ideas"] and r["summary"]["open"] == len(r["ideas"]) and r["updated"]
    f = client.get("/api/feed", headers=h).json()
    assert f and any(x["kind"] == "idea" for x in f)
    assert all(x["kind"] == "idea" for x in client.get("/api/feed?kind=idea", headers=h).json())
