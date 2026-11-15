from datetime import date, timedelta

from app.db import SessionLocal
from app.models import User
from engine.data.providers import SyntheticProvider


def _plan(email, plan):
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).one()
        u.plan = plan
        db.commit()


def _trading_day(n_back: int) -> date:
    return SyntheticProvider().history("AAPL").index[-1 - n_back].date()


def test_portfolio_lifecycle(client, register):
    h, _ = register("pf-user@test.ro")
    p = client.post("/api/portfolios", headers=h, json={"name": "Main"}).json()
    pid = p["id"]
    assert p["value"] == 0 and p["classification"]["label"] == "Empty"

    d1 = _trading_day(200)
    r = client.post(f"/api/portfolios/{pid}/transactions", headers=h, json={"symbol": "ko", "side": "buy", "shares": 10, "date": d1.isoformat()})
    assert r.status_code == 200, r.text
    expected_px = float(SyntheticProvider().history("KO")["close"].loc[str(d1)])
    assert abs(r.json()["transactions"][0]["price"] - expected_px) < 0.01  # price defaults to that day's close

    client.post(f"/api/portfolios/{pid}/transactions", headers=h, json={"symbol": "JNJ", "side": "buy", "shares": 5, "price": 150, "date": d1.isoformat()})
    over = client.post(f"/api/portfolios/{pid}/transactions", headers=h, json={"symbol": "KO", "side": "sell", "shares": 11, "price": 70, "date": _trading_day(5).isoformat()})
    assert over.status_code == 400 and "only 10" in over.json()["detail"]
    future = client.post(f"/api/portfolios/{pid}/transactions", headers=h, json={"symbol": "KO", "side": "buy", "shares": 1, "date": (date.today() + timedelta(days=3)).isoformat()})
    assert future.status_code == 400

    d = client.get(f"/api/portfolios/{pid}", headers=h).json()
    assert d["positions_count"] == 2 and {x["symbol"] for x in d["positions"]} == {"KO", "JNJ"}
    assert abs(sum(x["weight"] for x in d["positions"]) - 100) < 0.05
    assert abs(d["value"] - sum(x["value"] for x in d["positions"])) < 0.05
    assert d["dividends_total"] > 0  # KO and JNJ pay dividends in the demo data
    assert d["classification"]["scores"] and d["classification"]["label"] != "Empty"

    perf = client.get(f"/api/portfolios/{pid}/performance?period=ALL", headers=h).json()
    assert perf["series"][0]["portfolio"] == 0 and "benchmark" in perf["series"][-1]
    assert client.get(f"/api/portfolios/{pid}/performance?period=1M", headers=h).json()["series"]
    custom = client.get(f"/api/portfolios/{pid}/performance?period=CUSTOM&start={_trading_day(60)}&end={_trading_day(10)}", headers=h).json()
    assert custom["start"] <= custom["end"] and len(custom["series"]) > 30

    # deleting the KO buy is fine (no later KO sells)
    ko_buy = next(t for t in d["transactions"] if t["symbol"] == "KO")
    assert client.delete(f"/api/portfolios/{pid}/transactions/{ko_buy['id']}", headers=h).json()["positions_count"] == 1


def test_delete_buy_guard_and_isolation(client, register):
    h, _ = register("pf-guard@test.ro")
    h2, _ = register("pf-other@test.ro")
    pid = client.post("/api/portfolios", headers=h, json={"name": "G"}).json()["id"]
    buy = client.post(f"/api/portfolios/{pid}/transactions", headers=h, json={"symbol": "AAPL", "side": "buy", "shares": 5, "price": 100, "date": _trading_day(50).isoformat()}).json()
    client.post(f"/api/portfolios/{pid}/transactions", headers=h, json={"symbol": "AAPL", "side": "sell", "shares": 5, "price": 120, "date": _trading_day(10).isoformat()})
    buy_id = next(t["id"] for t in buy["transactions"] if t["side"] == "buy")
    assert client.delete(f"/api/portfolios/{pid}/transactions/{buy_id}", headers=h).status_code == 400
    summary = client.get(f"/api/portfolios/{pid}", headers=h).json()
    assert summary["realized_pnl"] == 100 and summary["positions_count"] == 0
    assert client.get(f"/api/portfolios/{pid}", headers=h2).status_code == 404


def test_free_plan_limit_and_templates(client, register):
    h, _ = register("pf-free@test.ro")
    assert client.post("/api/portfolios", headers=h, json={"name": "One"}).status_code == 200
    assert client.post("/api/portfolios", headers=h, json={"name": "Two"}).status_code == 403

    _plan("pf-free@test.ro", "pro")
    tpls = client.get("/api/portfolio-templates", headers=h).json()
    ids = {t["id"] for t in tpls}
    assert {"aggressive_growth", "dividend_income", "conservative", "momentum_leaders", "balanced"} <= ids
    momentum = next(t for t in tpls if t["id"] == "momentum_leaders")
    assert len(momentum["symbols"]) == 8

    r = client.post("/api/portfolios/from-template", headers=h, json={"template_id": "dividend_income", "amount": 10000})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["positions_count"] == 8 and abs(p["value"] - 10000) < 5
    assert p["classification"]["primary"] == "dividend"
    lst = client.get("/api/portfolios", headers=h).json()
    assert [x["name"] for x in lst] == ["One", "Dividend Income"]
    assert lst[1]["classification"]["label"].startswith("Dividend Income")
