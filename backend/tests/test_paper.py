import pandas as pd

from engine.paper import follow, summary


def frame(bars):
    idx = pd.bdate_range("2026-01-01", periods=len(bars))
    return pd.DataFrame([dict(open=c, high=h, low=l, close=c, volume=1) for h, l, c in bars], index=idx)


T = {"side": "long", "entry": 100.0, "stop": 95.0, "trim": 105.0, "target": 115.0, "entry_date": "2026-01-01"}


def test_trim_then_target():
    df = frame([(100, 100, 100), (106, 101, 105), (116, 104, 115)])
    r = follow(T, df)
    assert r["status"] == "TARGET" and not r["open"]
    assert r["r_multiple"] == 2.0  # half at +1R, half at +3R


def test_trim_then_breakeven_stop():
    df = frame([(100, 100, 100), (106, 101, 105), (104, 99, 99.5)])
    r = follow(T, df)
    assert r["status"] == "BREAKEVEN" and r["r_multiple"] == 0.5


def test_stopped_and_open_and_manual_close():
    assert follow(T, frame([(100, 100, 100), (101, 94, 95)]))["r_multiple"] == -1.0
    o = follow(T, frame([(100, 100, 100), (103, 99, 102.5)]))
    assert o["open"] and o["r_multiple"] == 0.5 and o["pnl_pct"] == 2.5
    m = follow({**T, "exit_date": "2026-01-02", "exit_price": 102.0}, frame([(100, 100, 100), (103, 99, 102.5), (120, 101, 119)]))
    assert m["status"] == "CLOSED" and m["r_multiple"] == 0.4


def test_short_and_summary():
    s = {**T, "side": "short", "entry": 100, "stop": 105, "trim": 95, "target": 85}
    r = follow(s, frame([(100, 100, 100), (99, 84, 85)]))
    assert r["status"] == "TARGET" and r["r_multiple"] == 2.0
    sm = summary([{**r, "weight": 10}, {"open": False, "r_multiple": -1.0, "pnl_pct": -5.0, "weight": 10}])
    assert sm["win_rate"] == 50.0 and sm["avg_r"] == 0.5 and sm["account_pct"] == 0.5


def test_paper_trade_api(client, register):
    from app.db import SessionLocal
    from app.ideas_service import run_ideas
    from app.models import User

    h, _ = register("paper@test.ro")
    with SessionLocal() as db:
        db.query(User).filter_by(email="paper@test.ro").one().plan = "pro"
        db.commit()
        run_ideas(db, force=True)
    ideas = client.get("/api/ideas", headers=h).json()["ideas"]
    assert ideas and ideas[0]["taken"] is False
    idea = ideas[0]
    r = client.post("/api/paper-trades", headers=h, json={"idea_id": idea["id"]})
    assert r.status_code in (200, 400), r.text  # 400 only if price already beyond the stop
    if r.status_code == 200:
        assert client.post("/api/paper-trades", headers=h, json={"idea_id": idea["id"]}).status_code == 409
        lst = client.get("/api/paper-trades", headers=h).json()
        assert lst["summary"]["trades"] == 1 and lst["trades"][0]["symbol"] == idea["symbol"]
        assert any(i["taken"] for i in client.get("/api/ideas", headers=h).json()["ideas"])
        tid = lst["trades"][0]["id"]
        assert client.post(f"/api/paper-trades/{tid}/close", headers=h).json()["status"] == "CLOSED"
        assert client.delete(f"/api/paper-trades/{tid}", headers=h).status_code == 204
