"""Portfolio heat, trade journal notes, custom rule backtests, CSV export (Phase C)."""

from app.db import SessionLocal
from app.models import User


def _plan(email, plan):
    with SessionLocal() as db:
        db.query(User).filter_by(email=email).one().plan = plan
        db.commit()


def test_portfolio_heat(client, register):
    h, _ = register("heat@test.ro")
    pf = client.post("/api/portfolios", headers=h, json={"name": "Heat"}).json()
    client.post(f"/api/portfolios/{pf['id']}/buy-now", headers=h, json={"symbol": "AAPL", "shares": 10})
    d = client.post(f"/api/portfolios/{pf['id']}/buy-now", headers=h, json={"symbol": "MSFT", "shares": 5}).json()
    assert d["heat"]["missing"] == ["AAPL", "MSFT"] or set(d["heat"]["missing"]) == {"AAPL", "MSFT"}
    price = {p["symbol"]: p["price"] for p in d["positions"]}
    d = client.put(f"/api/portfolios/{pf['id']}/stops", headers=h, json={"symbol": "AAPL", "stop": round(price["AAPL"] * 0.9, 2)}).json()
    heat = d["heat"]
    assert heat["missing"] == ["MSFT"] and abs(heat["total_risk"] - 10 * price["AAPL"] * 0.1) < 1
    assert {p["symbol"]: p["stop"] for p in d["positions"]}["AAPL"] == round(price["AAPL"] * 0.9, 2)
    d = client.put(f"/api/portfolios/{pf['id']}/stops", headers=h, json={"symbol": "AAPL", "stop": None}).json()
    assert d["heat"]["total_risk"] == 0


def test_trade_notes_and_analytics_tags(client, register):
    h, _ = register("notes@test.ro")
    t = client.post("/api/paper-trades/chart", headers=h, json={"symbol": "AAPL", "side": "long"}).json()
    ref = f"paper:{t['id']}"
    img = "data:image/jpeg;base64," + "A" * 100
    r = client.put(f"/api/notes/{ref}", headers=h, json={"setup": "Breakout", "emotion": "FOMO", "notes": "Chased it", "image": img})
    assert r.status_code == 200 and r.json()["has_image"]
    assert client.get(f"/api/notes/{ref}", headers=h).json()["image"] == img
    assert [n["ref"] for n in client.get("/api/notes", headers=h).json()] == [ref]
    assert client.put("/api/notes/evil", headers=h, json={"notes": "x"}).status_code == 400
    assert client.put(f"/api/notes/{ref}", headers=h, json={"image": "data:image/png;base64," + "A" * 500_000}).status_code == 400
    client.post("/api/paper-trades/chart/sell", headers=h, json={"symbol": "AAPL"})
    a = client.get("/api/analytics?source=chart", headers=h).json()
    assert a["by_setup"][0]["name"] == "Breakout" and a["by_emotion"][0]["name"] == "FOMO"
    other, _ = register("notes2@test.ro")
    assert client.get(f"/api/notes/{ref}", headers=other).status_code == 404  # private to its owner


def test_rules_engine_conditions_and_exits():
    from app import market_data
    from engine.rules import CONDITIONS, run_rules

    df, bench = market_data.history("NVDA"), market_data.history("SPY")
    for t in CONDITIONS:
        r = run_rules(df, {"entry": [{"type": t}], "exit": {"stop_pct": 7, "target_r": 3}}, bench)
        assert "stats" in r, t
    r = run_rules(df, {"entry": [{"type": "price_above_sma", "n": 50}], "exit": {"stop_pct": 5, "target_r": 2}}, bench)
    assert r["stats"]["trades"] > 0 and set(r["stats"]["exits"]) <= {"stop", "target", "open"}
    for t in r["trades"]:
        if t["exit_reason"] == "stop":
            assert t["exit"] <= t["entry"] * 0.95 + 0.01
        if t["exit_reason"] == "target":
            assert t["exit"] >= t["entry"] * 1.10 - 0.01
    timed = run_rules(df, {"entry": [{"type": "price_above_sma", "n": 20}], "exit": {"stop_pct": 0, "max_days": 5}})
    assert all(t["days"] <= 9 for t in timed["trades"] if not t["open"])  # 5 trading days ≈ a week


def test_rules_api_gated_and_saved(client, register):
    h, _ = register("rules@test.ro")
    body = {"symbol": "AAPL", "rules": {"entry": [{"type": "breakout", "n": 20}], "exit": {"stop_pct": 7, "target_r": 3}}}
    _plan("rules@test.ro", "pro")
    assert client.post("/api/backtest/rules", headers=h, json=body).status_code == 403
    _plan("rules@test.ro", "premium")
    r = client.post("/api/backtest/rules", headers=h, json=body)
    assert r.status_code == 200 and "stats" in r.json()
    assert client.post("/api/backtest/rules", headers=h, json={"symbol": "AAPL", "rules": {"entry": []}}).status_code == 400
    s = client.post("/api/backtest/rules/saved", headers=h, json={"name": "Breakouts", "rules": body["rules"]}).json()
    assert [x["name"] for x in client.get("/api/backtest/rules/saved", headers=h).json()] == ["Breakouts"]
    assert client.delete(f"/api/backtest/rules/saved/{s['id']}", headers=h).status_code == 204


def test_csv_export(client, register):
    h, _ = register("csv@test.ro")
    pf = client.post("/api/portfolios", headers=h, json={"name": "CSV"}).json()
    client.post(f"/api/portfolios/{pf['id']}/buy-now", headers=h, json={"symbol": "AAPL", "shares": 3})
    assert client.get(f"/api/export/transactions?portfolio_id={pf['id']}", headers=h).status_code == 403
    _plan("csv@test.ro", "premium")
    r = client.get(f"/api/export/transactions?portfolio_id={pf['id']}", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("id,date,symbol") and "AAPL" in lines[1]
    assert "AAPL" in client.get(f"/api/export/holdings?portfolio_id={pf['id']}", headers=h).text
    assert client.get("/api/export/screener", headers=h).text.startswith("symbol")
    assert client.get("/api/export/grader?source=all", headers=h).status_code == 200
    assert client.get("/api/export/paper-trades", headers=h).status_code == 200
