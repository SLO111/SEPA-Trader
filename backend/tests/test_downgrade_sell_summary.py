"""Plan limits after a downgrade, sell / buy at market, Free daily summary, Free Trend Template, new indicators."""

import json

from app.db import SessionLocal
from app.models import User


def _plan(email, plan):
    with SessionLocal() as db:
        db.query(User).filter_by(email=email).one().plan = plan
        db.commit()


def test_extra_portfolios_lock_after_downgrade(client, register):
    h, _ = register("down-pf@test.ro")
    _plan("down-pf@test.ro", "premium")
    a = client.post("/api/portfolios", headers=h, json={"name": "First"}).json()
    b = client.post("/api/portfolios", headers=h, json={"name": "Second"}).json()
    _plan("down-pf@test.ro", "free")
    lst = {p["id"]: p for p in client.get("/api/portfolios", headers=h).json()}
    assert not lst[a["id"]].get("locked") and lst[b["id"]]["locked"]
    assert client.get(f"/api/portfolios/{a['id']}", headers=h).status_code == 200
    assert client.get(f"/api/portfolios/{b['id']}", headers=h).status_code == 403
    tx = {"symbol": "AAPL", "side": "buy", "shares": 1, "date": "2025-06-02"}
    assert client.post(f"/api/portfolios/{b['id']}/transactions", headers=h, json=tx).status_code == 403
    assert client.post(f"/api/portfolios/{b['id']}/import/preview", headers=h, json={"filename": "x.csv", "content_base64": ""}).status_code == 403
    assert client.delete(f"/api/portfolios/{b['id']}", headers=h).status_code == 204  # deleting is still allowed
    _plan("down-pf@test.ro", "premium")
    assert all(not p.get("locked") for p in client.get("/api/portfolios", headers=h).json())


def test_extra_watchlists_and_symbols_lock_after_downgrade(client, register):
    h, _ = register("down-wl@test.ro")
    _plan("down-wl@test.ro", "premium")
    first = client.get("/api/watchlists", headers=h).json()[0]
    second = client.post("/api/watchlists", headers=h, json={"name": "Second"}).json()
    for s in ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AMD", "NFLX", "AVGO", "COST", "JPM"]:
        client.post(f"/api/watchlists/{first['id']}/items", headers=h, json={"symbol": s})
    _plan("down-wl@test.ro", "free")
    got = {w["id"]: w for w in client.get("/api/watchlists", headers=h).json()}
    assert got[second["id"]]["locked"] and got[second["id"]]["symbols"] == []
    n = len(got[first["id"]]["symbols"]) + got[first["id"]]["hidden"]
    assert len(got[first["id"]]["symbols"]) == 10 and got[first["id"]]["hidden"] == n - 10
    assert client.post(f"/api/watchlists/{second['id']}/items", headers=h, json={"symbol": "AAPL"}).status_code == 403
    assert client.delete(f"/api/watchlists/{second['id']}", headers=h).status_code == 204


def test_free_grader_shows_portfolio_trades(client, register):
    h, _ = register("free-grade@test.ro")
    pf = client.post("/api/portfolios", headers=h, json={"name": "Mine"}).json()
    client.post(f"/api/portfolios/{pf['id']}/transactions", headers=h, json={"symbol": "AAPL", "side": "buy", "shares": 5, "date": "2025-06-02"})
    client.post(f"/api/portfolios/{pf['id']}/transactions", headers=h, json={"symbol": "AAPL", "side": "sell", "shares": 5, "date": "2025-08-01"})
    r = client.get(f"/api/grader?source=portfolio&portfolio_id={pf['id']}", headers=h).json()
    assert len(r["trades"]) >= 1 and r["trades"][0]["source"].startswith("Portfolio")
    a = client.get(f"/api/analytics?source=portfolio&portfolio_id={pf['id']}", headers=h).json()
    assert a["trades"] >= 1
    # Trade ideas / Move Detector trades stay Pro: Free falls back to chart trades
    assert all(t["source"] == "Charts" for t in client.get("/api/grader?source=ideas", headers=h).json()["trades"])


def test_sell_now_buy_now_and_positions(client, register):
    from app import market_data

    h, _ = register("sellnow@test.ro")
    pf = client.post("/api/portfolios", headers=h, json={"name": "Quick"}).json()
    r = client.post(f"/api/portfolios/{pf['id']}/buy-now", headers=h, json={"symbol": "msft", "shares": 10})
    assert r.status_code == 200, r.text
    last = round(float(market_data.history("MSFT")["close"].iloc[-1]), 2)
    txn = r.json()["transactions"][-1]
    assert txn["side"] == "buy" and abs(txn["price"] - last) < 0.02
    pos = client.get("/api/portfolios/positions?symbol=MSFT", headers=h).json()
    assert pos[0]["portfolio_id"] == pf["id"] and pos[0]["shares"] == 10
    assert client.post(f"/api/portfolios/{pf['id']}/sell-now", headers=h, json={"symbol": "MSFT", "shares": 11}).status_code == 400
    part = client.post(f"/api/portfolios/{pf['id']}/sell-now", headers=h, json={"symbol": "MSFT", "shares": 4}).json()
    assert {p["symbol"]: p["shares"] for p in part["positions"]}["MSFT"] == 6
    rest = client.post(f"/api/portfolios/{pf['id']}/sell-now", headers=h, json={"symbol": "MSFT"}).json()
    assert "MSFT" not in {p["symbol"] for p in rest["positions"]}
    assert client.get("/api/portfolios/positions?symbol=MSFT", headers=h).json() == []
    assert client.post(f"/api/portfolios/{pf['id']}/sell-now", headers=h, json={"symbol": "MSFT"}).status_code == 400


def test_summary_sections_locked_on_free():
    from app.plans import PLANS
    from engine import feed

    scan = [{"symbol": "AAA", "bull_score": 80, "bear_score": 10, "price": 1, "change_pct": 1},
            {"symbol": "BBB", "bull_score": 20, "bear_score": 75, "price": 1, "change_pct": -1}]
    pulse = {"AAA": {"conf": 5, "warn": 0}, "BBB": {"conf": 0, "warn": 4}}
    item = feed.daily_summary("2026-11-13", [], [], {}, [], [], [], scan, pulse)
    d = json.loads(item["body"])
    assert d["move_detector"]["bull"][0]["symbol"] == "AAA" and d["move_detector"]["bear"][0]["symbol"] == "BBB"
    assert d["pulse"]["best"][0]["symbol"] == "AAA" and d["pulse"]["warning"][0]["symbol"] == "BBB"
    free = feed.gate_summary(d, PLANS["free"])
    assert free["ideas"]["locked"] and free["move_detector"] == {"locked": True} and free["pulse"] == {"locked": True}
    pro = feed.gate_summary(d, PLANS["pro"])
    assert pro["move_detector"]["bull"] and pro["pulse"]["best"]
    txt = feed.summary_text(item, None, PLANS["free"])
    assert "Upgrade to Pro" in txt and "MOVE DETECTOR" not in txt


def test_free_trend_template_only_chart_readable(client, register):
    h, _ = register("free-tt@test.ro")
    tt = client.get("/api/sepa/AAPL", headers=h).json()["trend_template"]
    assert tt["total"] == 3 and len(tt["criteria"]) == 3 and tt["passed_count"] <= 3
    assert all("52-week" not in c["label"] and "RS Rating" not in c["label"] for c in tt["criteria"])
    _plan("free-tt@test.ro", "pro")
    tt2 = client.get("/api/sepa/AAPL", headers=h).json()["trend_template"]
    assert tt2["total"] == 8 and len(tt2["criteria"]) == 8


def test_new_indicators_listed_with_ratings(client, register):
    from app import market_data
    from engine.strategies import list_strategies, run_strategy
    from engine.strategies.pro_indicators import ut_bot
    from engine import indicators as ind

    defs = {d["id"]: d for d in list_strategies()}
    for sid in ("ut_bot", "supertrend", "adaptive_ranges", "squeeze", "adx", "rs_line", "pocket_pivot", "donchian", "avwap"):
        assert 1 <= defs[sid]["rating"] <= 5 and defs[sid]["level"] in ("Beginner", "Intermediate", "Advanced")
    assert all(d.get("rating") for d in defs.values())
    df = market_data.history("AAPL")
    st, pos, buy, sell = ut_bot(df["close"], ind.atr(df, 10), 1.0)
    # signals alternate and always sit on the correct side of the trailing stop
    sig = sorted([(i, 1) for i in buy[buy].index] + [(i, -1) for i in sell[sell].index])
    assert sig and all(a[1] != b[1] for a, b in zip(sig, sig[1:]))
    assert all(df["close"][i] > st[i] for i in buy[buy].index) and all(df["close"][i] < st[i] for i in sell[sell].index)
    out = run_strategy("rs_line", df, {}, market_data.history("SPY"))
    assert out["lines"] and out["lines"][0]["pane"] == "lower"
    h, _ = register("ind@test.ro")
    r = client.post("/api/strategies/run", headers=h, json={"symbol": "AAPL", "interval": "1d", "strategies": [{"id": "ut_bot", "params": {}}]})
    assert r.status_code == 200 and r.json()["results"][0]["bar_colors"]


def test_ticket_levels(client, register):
    h, _ = register("levels@test.ro")
    free = client.get("/api/market/levels/AAPL", headers=h).json()
    assert free["atr"] > 0 and "vcp" not in free and "ai_plan" not in free
    _plan("levels@test.ro", "pro")
    pro = client.get("/api/market/levels/AAPL?side=long", headers=h).json()
    assert "vcp" in pro and "ai_plan" in pro


def test_screener_free_general_info_pro_full(client, register):
    h, _ = register("screen-free@test.ro")
    r = client.get("/api/markets/screener", headers=h)
    assert r.status_code == 200 and r.json()["locked"]
    rows = r.json()["results"]
    assert rows and all(k in rows[0] for k in ("symbol", "price", "market_cap_b", "pe", "dividend_yield"))
    assert not any(k in rows[0] for k in ("rsi14", "rs_rating", "template_passed", "bull_score", "from_ath_pct"))
    caps = [x["market_cap_b"] or 0 for x in rows]
    assert caps == sorted(caps, reverse=True)  # largest companies first
    for q in ("preset=dividend", "sector=Technology", "max_pe=20", "template_only=true"):
        assert client.get(f"/api/markets/screener?{q}", headers=h).status_code == 403, q
    _plan("screen-free@test.ro", "pro")
    full = client.get("/api/markets/screener", headers=h).json()
    assert not full["locked"]
    row = full["results"][0]
    assert row["from_ath_pct"] <= 0.01 and row["ath"] >= row["price"] and isinstance(row["at_ath"], bool)
    assert all(k in row for k in ("rsi14", "rs_rating", "template_passed", "bull_score"))
    assert client.get("/api/markets/screener?preset=dividend", headers=h).status_code == 200


def test_ath_distance():
    from engine.market_tools import _ath

    assert _ath({"price": 100, "week52_high": 100.5}, {"ath": 100.5})["at_ath"] is True
    far = _ath({"price": 80, "week52_high": 90}, {"ath": 120})
    assert far["ath"] == 120 and far["from_ath_pct"] == -33.33 and not far["at_ath"]
    assert _ath({"price": 130, "week52_high": 131}, {"ath": 120})["ath"] == 131  # a new high beats the stored value


def test_screener_pages_of_50_sorted_server_side(client, register):
    from engine.data import universe

    saved = dict(universe.SYMBOLS)
    for i in range(70):  # a universe bigger than one page (no prices: they still list with empty values)
        universe.SYMBOLS[f"ZP{i:03d}"] = {"name": f"Page {i}", "sector": "Industrials", "exchange": ""}
    from app import market_data

    market_data._fast_cache.clear()
    try:
        h, _ = register("screen-pages@test.ro")
        first = client.get("/api/markets/screener", headers=h).json()
        n = first["count"]
        assert len(first["results"]) == min(50, n) and first["offset"] == 0 and first["sort"] == "market_cap_b"
        if n > 50:
            assert first["has_more"]
            second = client.get("/api/markets/screener?offset=50", headers=h).json()
            assert {r["symbol"] for r in first["results"]}.isdisjoint({r["symbol"] for r in second["results"]})
        az = client.get("/api/markets/screener?sort=symbol&dir=asc&limit=10", headers=h).json()["results"]
        syms = [r["symbol"] for r in az]
        assert syms == sorted(syms)
        # Free users can't sort by paid columns: falls back to market cap
        assert client.get("/api/markets/screener?sort=rs_rating", headers=h).json()["sort"] == "market_cap_b"
    finally:
        universe.SYMBOLS.clear()
        universe.SYMBOLS.update(saved)
        market_data._fast_cache.clear()
