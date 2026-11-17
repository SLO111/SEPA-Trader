"""Imported positions in TradeGrader, watchlist sections, leaderboard / copy fixes, vnicornAI real trades,
portfolio insights and order, branded exports, news aggregator, scorecard."""

from datetime import datetime, timedelta, timezone

import pandas as pd

from app.db import SessionLocal
from app.models import User


def _plan(email, plan):
    with SessionLocal() as db:
        db.query(User).filter_by(email=email).one().plan = plan
        db.commit()


def _uid(email):
    with SessionLocal() as db:
        return db.query(User).filter_by(email=email).one().id


# ------------------------------------------------------------------ 1. TradeGrader + statement imports

def test_grade_statement_position_is_followed_not_rejected():
    from app import market_data
    from engine.trade_grader import grade_trade

    df = market_data.history("NVDA")
    day = df.index[-20].strftime("%Y-%m-%d")
    avg_cost = float(df["close"].iloc[-20]) * 0.55  # bought long ago, far below that day's range
    g = grade_trade({"symbol": "NVDA", "side": "long", "entry_date": day, "entry_price": avg_cost, "exit_date": None, "exit_price": None,
                     "statement": True}, df)
    assert g["statement"] and g["entry_class"] is None and g["pnl_pct"] > 0
    assert "imported" in g["notes"][0].lower() and "check the price" not in " ".join(g["notes"])
    sold = grade_trade({"symbol": "NVDA", "side": "long", "entry_date": day, "entry_price": avg_cost,
                        "exit_date": df.index[-5].strftime("%Y-%m-%d"), "exit_price": float(df["close"].iloc[-5]), "statement": True}, df)
    assert sold["exit_class"] in ("Perfect", "Early", "Late", "Fair") and sold["grade"]
    # a hand-entered price 3x off is still flagged (wrong currency)
    bad = grade_trade({"symbol": "NVDA", "side": "long", "entry_date": day, "entry_price": float(df["close"].iloc[-20]) * 3,
                       "exit_date": None, "exit_price": None}, df)
    assert "check the price" in bad["notes"][0]


def test_round_trips_carry_statement_flag():
    from engine.trade_grader import round_trips

    t = round_trips([{"date": "2026-11-13", "symbol": "AAPL", "side": "buy", "shares": 10, "price": 100, "statement": True},
                     {"date": "2026-11-14", "symbol": "AAPL", "side": "buy", "shares": 5, "price": 120}])
    assert [x["statement"] for x in t] == [True, False]


# ------------------------------------------------------------------ 2. watchlist sections

def test_watchlist_sections_presets_and_sector_grouping(client, register):
    h, _ = register("sections@test.ro")
    _plan("sections@test.ro", "pro")
    wl = client.get("/api/watchlists", headers=h).json()[0]
    presets = client.get("/api/watchlists/presets", headers=h).json()
    assert any(p["id"] == "mag7" for p in presets) and any(p["id"] == "semis" for p in presets)
    w = client.post(f"/api/watchlists/{wl['id']}/sections", headers=h, json={"name": "Mag 7", "symbols": ["AAPL", "MSFT", "NVDA"]}).json()
    sec = w["sections"][-1]
    assert sec["name"] == "Mag 7" and set(sec["symbols"]) <= set(w["symbols"]) and "NVDA" in sec["symbols"]
    # move NVDA out, collapse, rename via layout
    w2 = client.put(f"/api/watchlists/{wl['id']}/layout", headers=h,
                    json={"sections": [{"id": sec["id"], "name": "Big tech", "symbols": ["AAPL", "MSFT"], "collapsed": True}]}).json()
    assert w2["sections"][0]["name"] == "Big tech" and w2["sections"][0]["collapsed"] and "NVDA" not in w2["sections"][0]["symbols"]
    # removing a symbol drops it from its section
    w3 = client.delete(f"/api/watchlists/{wl['id']}/items/AAPL", headers=h).json()
    assert "AAPL" not in w3["sections"][0]["symbols"]
    g = client.post(f"/api/watchlists/{wl['id']}/group-by-sector", headers=h).json()
    assert g["sections"] and sum(len(s["symbols"]) for s in g["sections"]) == len(g["symbols"])


def test_free_preset_respects_symbol_limit(client, register):
    h, _ = register("sections-free@test.ro")
    wl = client.get("/api/watchlists", headers=h).json()[0]
    w = client.post(f"/api/watchlists/{wl['id']}/sections", headers=h,
                    json={"name": "Semis", "symbols": ["NVDA", "AMD", "AVGO", "TSM", "ASML", "QCOM", "ARM", "MRVL", "INTC", "AMAT"]}).json()
    assert len(w["symbols"]) <= 10 and w["skipped"]


# ------------------------------------------------------------------ 3. leaderboard and copy trading

def test_hidden_profile_leaves_leaderboard_immediately_and_copy_pause(client, register):
    from app import market_data
    from app.models import PaperTrade

    lh, _ = register("hide-me@test.ro")
    fh, _ = register("hide-follower@test.ro")
    lid = _uid("hide-me@test.ro")
    client.put("/api/community/profile", headers=lh, json={"display_name": "Hider", "public": True, "allow_copy": True})
    with SessionLocal() as db:
        d = market_data.history("MSFT").index[-30].date()
        for _ in range(5):
            db.add(PaperTrade(user_id=lid, symbol="MSFT", timeframe="CH", side="long", entry_date=d, entry=100, stop=1, target=1e6,
                              weight=1, exit_date=d + timedelta(days=5), exit_price=105))
        db.commit()
    market_data._fast_cache.pop("public:leaderboard:all", None)
    assert any(r["display_name"] == "Hider" for r in client.get("/api/public/leaderboard?period=all").json()["rows"])
    client.post(f"/api/community/follow/{lid}", headers=fh)
    client.put("/api/community/profile", headers=lh, json={"display_name": "Hider", "public": False, "allow_copy": True})
    assert not any(r["display_name"] == "Hider" for r in client.get("/api/public/leaderboard?period=all").json()["rows"])  # no stale cache
    # copying switched off: the follower keeps the follow and its copies, sees "paused", gets no new trades
    client.post("/api/paper-trades/chart", headers=lh, json={"symbol": "AAPL", "side": "long"})
    assert len(client.get("/api/paper-trades?source=copy", headers=fh).json()["trades"]) == 1
    client.put("/api/community/profile", headers=lh, json={"display_name": "Hider", "public": False, "allow_copy": False})
    me = client.get("/api/community/profile", headers=fh).json()
    assert me["following"][0]["paused"] is True
    client.post("/api/paper-trades/chart", headers=lh, json={"symbol": "NVDA", "side": "long"})
    copies = client.get("/api/paper-trades?source=copy", headers=fh).json()["trades"]
    assert [c["symbol"] for c in copies] == ["AAPL"]


# ------------------------------------------------------------------ 4. vnicornAI learns from real trades

def test_trade_examples_weight_winners_more():
    from app import market_data
    from engine import vnicorn_ai as ai

    hist = {s: market_data.history(s) for s in ("NVDA", "AAPL")}
    d = hist["NVDA"].index[-60]
    trades = [{"symbol": "NVDA", "side": "long", "entry_date": d, "entry": 100, "stop": 93, "target": 121, "won": True, "r": 3},
              {"symbol": "AAPL", "side": "long", "entry_date": d, "entry": 100, "stop": 93, "target": 121, "won": False, "r": -1},
              {"symbol": "NVDA", "side": "short", "entry_date": d, "entry": 100, "stop": 107, "target": 79, "won": True, "r": 3}]
    ex = ai.trade_examples(trades, hist, market_data.history("SPY"))
    assert len(ex["long"]) == 2 and len(ex["short"]) == 1
    w = dict(zip(ex["long"]["y"], ex["long"]["w"]))
    assert w[1] == ai.REAL_WIN_WEIGHT > w[0] == ai.REAL_LOSS_WEIGHT
    assert abs(ex["long"]["target_r"].iloc[0] - 3.0) < 1e-6


# ------------------------------------------------------------------ 5. portfolio insights and order

def test_portfolio_insights_and_order(client, register):
    h, _ = register("insights@test.ro")
    a = client.post("/api/portfolios", headers=h, json={"name": "A"}).json()
    client.post(f"/api/portfolios/{a['id']}/buy-now", headers=h, json={"symbol": "NVDA", "shares": 50})
    client.post(f"/api/portfolios/{a['id']}/buy-now", headers=h, json={"symbol": "AAPL", "shares": 1})
    r = client.get(f"/api/portfolios/{a['id']}/insights", headers=h).json()
    titles = " | ".join(c["title"] for c in r["checks"])
    assert "No stop on NVDA" in titles and "% of the portfolio" in titles
    assert r["suggestions"] == {"locked": True}  # Free: risk checks only
    d = client.put(f"/api/portfolios/{a['id']}/targets", headers=h, json={"symbol": "NVDA", "trim": 2000, "target": 2500}).json()
    assert {p["symbol"]: (p["trim"], p["target"]) for p in d["positions"]}["NVDA"] == (2000, 2500)
    _plan("insights@test.ro", "pro")
    assert isinstance(client.get(f"/api/portfolios/{a['id']}/insights", headers=h).json()["suggestions"], list)
    b = client.post("/api/portfolios", headers=h, json={"name": "B"}).json()
    client.put("/api/portfolios/order", headers=h, json={"ids": [b["id"], a["id"]]})
    assert [p["name"] for p in client.get("/api/portfolios", headers=h).json()][:2] == ["B", "A"]


# ------------------------------------------------------------------ 6. branded exports

def test_branded_xlsx_and_pdf_exports(client, register):
    import io

    import openpyxl

    h, _ = register("branded@test.ro")
    _plan("branded@test.ro", "premium")
    pf = client.post("/api/portfolios", headers=h, json={"name": "Brand"}).json()
    client.post(f"/api/portfolios/{pf['id']}/buy-now", headers=h, json={"symbol": "AAPL", "shares": 3})
    x = client.get(f"/api/export/holdings?portfolio_id={pf['id']}&format=xlsx", headers=h)
    assert x.status_code == 200 and "spreadsheetml" in x.headers["content-type"]
    ws = openpyxl.load_workbook(io.BytesIO(x.content)).active
    assert "Vnicorn Investments" in str(ws["A1"].value) and "Holdings" in str(ws["A2"].value)
    p = client.get(f"/api/export/transactions?portfolio_id={pf['id']}&format=pdf", headers=h)
    assert p.status_code == 200 and p.content[:4] == b"%PDF"


# ------------------------------------------------------------------ 7. news aggregator

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Nvidia shares jump after record data-center sales</title><link>https://www.cnbc.com/a</link>
<description>&lt;p&gt;Chip giant beats estimates.&lt;/p&gt;</description><pubDate>%s</pubDate></item>
<item><title>Fed holds rates steady</title><link>https://www.cnbc.com/b</link><pubDate>%s</pubDate></item>
<item><title>Old story</title><link>https://www.cnbc.com/c</link><pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_news_aggregator_parses_dedupes_and_tags():
    from email.utils import format_datetime

    from engine import news
    from engine.data.universe import SYMBOLS, stock_symbols

    now = format_datetime(datetime.now(timezone.utc)).encode()
    xml = RSS % (now, now)
    other = xml.replace(b"cnbc.com/a", b"marketwatch.com/x")  # same headline from another publisher
    raw = news.collect(lambda url: other if "dowjones" in url else xml)
    syms = stock_symbols()
    items = news.to_feed_items(raw, set(syms), news.name_index({s: SYMBOLS.get(s, {}) for s in syms}))
    titles = [i["title"] for i in items]
    assert titles.count("Nvidia shares jump after record data-center sales") == 1 and "Old story" not in titles
    nv = next(i for i in items if i["title"].startswith("Nvidia"))
    assert nv["symbol"] == "NVDA" and nv["body"] == "Chip giant beats estimates." and nv["url"].startswith("https://")


def test_refresh_news_stores_many(client):
    from app.ideas_service import refresh_news
    from app.models import FeedItem
    from email.utils import format_datetime

    now = format_datetime(datetime.now(timezone.utc)).encode()
    feed = b"<rss><channel>" + b"".join(
        b"<item><title>Headline number %d about markets</title><link>https://example.com/%d</link><pubDate>%s</pubDate></item>" % (i, i, now)
        for i in range(30)) + b"</channel></rss>"
    with SessionLocal() as db:
        n = refresh_news(db, None, fetch=lambda url: feed)
        assert n == 30
        assert db.query(FeedItem).filter(FeedItem.kind == "news").count() >= 30
        assert refresh_news(db, None, fetch=lambda url: feed) == 0  # stored once


# ------------------------------------------------------------------ 8. scorecard

def test_scorecard_health_fair_value_and_sentiment(client, register):
    from app import market_data
    from engine.valuation import fair_value, health

    co = market_data.company("NVDA")
    hl = health(co)
    assert 1 <= hl["score"] <= 5 and hl["label"] and len(hl["categories"]) == 5
    fv = fair_value(co, float(market_data.history("NVDA")["close"].iloc[-1]), 30)
    assert fv["fair"] > 0 and fv["label"] in ("Undervalued", "Fairly valued", "Overvalued") and fv["models"]
    h, _ = register("scorecard@test.ro")
    free = client.get("/api/stock/NVDA/scorecard", headers=h).json()
    assert free["health"]["score"] and free["health"].get("categories_locked") and free["fair_value"]["locked"] and "fair" not in free["fair_value"]
    _plan("scorecard@test.ro", "pro")
    pro = client.get("/api/stock/NVDA/scorecard", headers=h).json()
    assert pro["fair_value"]["fair"] and pro["health"]["categories"]
    s = client.post("/api/stock/NVDA/sentiment", headers=h, json={"vote": "bull"}).json()
    assert s["votes"] == 1 and s["bullish_pct"] == 100 and s["mine"] == "bull"
    s2 = client.post("/api/stock/NVDA/sentiment", headers=h, json={"vote": "bear"}).json()
    assert s2["votes"] == 1 and s2["bearish_pct"] == 100  # changed, not added
    h2, _ = register("scorecard2@test.ro")
    s3 = client.post("/api/stock/NVDA/sentiment", headers=h2, json={"vote": "bull"}).json()
    assert s3["votes"] == 2 and s3["bullish_pct"] == 50


# ------------------------------------------------------------------ Ask vnicornAI on a recently listed stock

def test_ask_vnicorn_gives_rules_plans_for_a_new_stock(client, register, monkeypatch):
    from app import market_data
    from engine import vnicorn_ai

    real = market_data.history
    short = real("NVDA").iloc[-60:]  # like a stock listed 3 months ago

    def fake(symbol, interval="1d", years=3):
        return short if symbol.upper() == "NEWCO" else real(symbol, interval, years)

    monkeypatch.setattr(market_data, "history", fake)
    market_data._fast_cache.pop("analysis:NEWCO", None)
    h, _ = register("newco@test.ro")
    _plan("newco@test.ro", "premium")
    r = client.get("/api/market/analysis/NEWCO", headers=h)
    assert r.status_code == 200, r.text
    a = r.json()
    lg, sh = a["plans"]["long"], a["plans"]["short"]
    assert lg["source"] == sh["source"] == "rules" and lg["prob"] is None and lg["rr"] == 3.0
    assert lg["stop"] < lg["entry"] < lg["trim"] < lg["target"] and sh["target"] < sh["trim"] < sh["entry"] < sh["stop"]
    assert "60 trading days" in a["plan_note"]
    # the same levels are used when the plan is taken
    assert vnicorn_ai.rules_plan(short, "long")["stop"] == lg["stop"]
    t = client.post("/api/paper-trades/scan", headers=h, json={"symbol": "NEWCO", "side": "long"})
    assert t.status_code == 200, t.text
    assert abs(t.json()["stop"] - lg["stop"]) < 0.01


def test_old_statement_imports_detected_by_batch(client, register):
    """Positions imported before origins were recorded (several buys on one day, any price) are treated as a statement."""
    from app import market_data
    from app.models import PortfolioTxn

    h, _ = register("old-import@test.ro")
    pf = client.post("/api/portfolios", headers=h, json={"name": "Old broker"}).json()
    day = market_data.history("NVDA").index[-3].date()
    with SessionLocal() as db:
        for sym, px in (("NVDA", 50.0), ("AAPL", 3000.0), ("MSFT", 900.0)):  # average costs far from that day's prices
            db.add(PortfolioTxn(portfolio_id=pf["id"], date=day, symbol=sym, side="buy", shares=1, price=px, fees=0))
        db.commit()
    trades = client.get(f"/api/grader?source=portfolio&portfolio_id={pf['id']}", headers=h).json()["trades"]
    assert len(trades) == 3 and all(t["statement"] for t in trades)
    assert not any("check the price" in " ".join(t["notes"]) for t in trades)
    assert all(t.get("pnl_pct") is not None for t in trades)


def test_suggestions_follow_portfolio_profile(client, register):
    from app import market_data

    h, _ = register("profile-sugg@test.ro")
    _plan("profile-sugg@test.ro", "pro")
    pf = client.post("/api/portfolios", headers=h, json={"name": "Income"}).json()
    for s in ("KO", "PEP", "MO", "T", "VZ"):
        client.post(f"/api/portfolios/{pf['id']}/buy-now", headers=h, json={"symbol": s, "shares": 10})
    r = client.get(f"/api/portfolios/{pf['id']}/insights", headers=h).json()
    label = r["profile"]["label"]
    assert label in ("Dividend Income", "Conservative", "Value")  # an income / defensive portfolio
    assert r["suggestions"], "expected suggestions"
    held = {"KO", "PEP", "MO", "T", "VZ"}
    for s in r["suggestions"]:
        assert label in s["reason"] and s["symbol"] not in held
        assert (market_data.fundamentals(s["symbol"]).get("beta") or 1.0) <= 1.3  # defensive names, not high-flyers
