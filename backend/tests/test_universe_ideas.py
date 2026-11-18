"""Wider universe (Russell 1000 + theme lists) and industry variety in the trade ideas."""

from types import SimpleNamespace

import pytest

from app import data_store as ds
from app.db import SessionLocal
from engine.data import universe
from engine.data.providers import SyntheticProvider
from engine.ideas import diversify

ISHARES = """﻿iShares Russell 1000 ETF
Fund Holdings as of,"Nov 14, 2026"
Inception Date,"May 15, 2000"
Shares Outstanding,"100,000,000.00"
\xa0
Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Quantity,Price,Location,Exchange,Currency,FX Rate,Market Currency,Accrual Date
"ZZMID","ZZ MIDCAP CORP","Information Technology","Equity","1,000.00","0.10","1,000.00","10.00","100.00","United States","NASDAQ","USD","1.00","USD","-"
"ZZBIG","ZZ BIG CORP","Communication","Equity","9,000.00","2.50","9,000.00","90.00","100.00","United States","New York Stock Exchange Inc.","USD","1.00","USD","-"
"BRKB","BERKSHIRE HATHAWAY INC CLASS B","Financials","Equity","5,000.00","1.50","5,000.00","10.00","500.00","United States","New York Stock Exchange Inc.","USD","1.00","USD","-"
"USD","USD CASH","Cash and/or Derivatives","Cash","500.00","0.05","500.00","500.00","1.00","United States","-","USD","1.00","USD","-"
"ZZSML","ZZ SMALL INC","Health Care","Equity","500.00","0.02","500.00","5.00","100.00","United States","NASDAQ","USD","1.00","USD","-"
\xa0
"The content contained herein is owned or licensed by BlackRock."
"""


def test_parse_ishares_holdings():
    out = universe.parse_ishares_holdings(ISHARES)
    assert list(out) == ["ZZBIG", "BRK-B", "ZZMID", "ZZSML"]  # equities only, largest weight first
    assert out["ZZMID"] == {"name": "Zz Midcap Corp", "sector": "Technology", "exchange": "NASDAQ"}
    assert out["ZZBIG"]["sector"] == "Communication Services" and out["ZZBIG"]["exchange"] == "NYSE"
    assert universe.parse_ishares_holdings("no table here") == {}


def test_theme_symbols_skip_etfs():
    themes = universe.theme_symbols()
    assert {"IONQ", "MU", "OKLO", "MARA"} <= set(themes)
    assert not {"SPY", "XLK", "IBIT", "SMH"} & set(themes)
    assert themes["IONQ"]["sector"] == "Technology"


def test_merge_universe_limits_extras_and_keeps_sp500_metadata():
    sp500 = {"AAPL": {"name": "Apple Inc.", "sector": "Technology", "exchange": ""}}
    r1000 = {"AAPL": {"name": "Apple", "sector": "X", "exchange": ""}, "ZZ1": {"name": "a", "sector": "Energy", "exchange": ""},
             "ZZ2": {"name": "b", "sector": "Energy", "exchange": ""}, "ZZ3": {"name": "c", "sector": "Energy", "exchange": ""}}
    e = universe.merge_universe(sp500, True, r1000, extra=2)
    assert e["AAPL"]["name"] == "Apple Inc."
    assert "ZZ1" in e and "ZZ2" in e and "ZZ3" not in e  # only the largest `extra` new names
    assert "ASML" in e and "IONQ" in e  # Nasdaq-100 extras and theme lists
    assert "MELI" not in universe.merge_universe(sp500, False)  # Nasdaq-100 extras only with "+"


@pytest.fixture
def saved_universe():
    saved = dict(universe.SYMBOLS)
    yield
    universe.SYMBOLS.clear()
    universe.SYMBOLS.update(saved)


def _nasdaq_json(n=1600):
    rows = [{"symbol": f"ZN{chr(65 + i // 676)}{chr(65 + i // 26 % 26)}{chr(65 + i % 26)}", "name": f"Fake {i} Common Stock",
             "lastsale": "$20.00", "marketCap": f"{(n - i) * 1_000_000:,}.00", "sector": "Finance", "industry": "Banks"} for i in range(n)]
    return {"data": {"rows": rows}}


def _fake_get(ishares_ok: bool, nasdaq_ok: bool = False):
    import httpx

    def get(url, *a, **k):
        if url == universe.R1000_CSV:
            if not ishares_ok:
                raise httpx.ConnectError("offline")
            rows = [f'"ZQ{chr(65 + i // 676)}{chr(65 + i // 26 % 26)}{chr(65 + i % 26)}","Fake {i}","Industrials","Equity","1.00","{900 - i}","1","1","1","US","NASDAQ","USD","1","USD","-"'
                    for i in range(900)]
            text = "iShares Russell 1000 ETF\nTicker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Quantity,Price,Location,Exchange,Currency,FX Rate,Market Currency,Accrual Date\n" + "\n".join(rows)
            return SimpleNamespace(text=text, raise_for_status=lambda: None)
        if url == universe.NASDAQ_SCREENER:
            if not nasdaq_ok:
                raise httpx.ReadTimeout("timed out")
            return SimpleNamespace(json=_nasdaq_json, raise_for_status=lambda: None)
        raise httpx.ConnectError("offline")  # S&P 500 list: falls back to the bundled copy

    return get


def _wide_row(delete=False):
    from sqlalchemy import select

    from app.models import MarketCache

    with SessionLocal() as db:
        row = db.scalar(select(MarketCache).where(MarketCache.key == "universe:wide2"))
        payload = ds._unpack(row.payload) if row else None
        if row and delete:
            db.delete(row)
            db.commit()
        return payload


def test_refresh_universe_ishares(monkeypatch, saved_universe):
    import httpx

    from app.config import settings

    monkeypatch.setattr(settings, "universe", "sp500+r1000")
    monkeypatch.setattr(settings, "universe_extra", 50)
    monkeypatch.setattr(httpx, "get", _fake_get(True))
    s = ds.DataStore(SyntheticProvider, SessionLocal)
    s.refresh_universe()
    fake = [x for x in universe.SYMBOLS if x.startswith("ZQ")]
    assert len(fake) == 50 and "ZQAAA" in fake  # the largest 50
    assert "IONQ" in universe.SYMBOLS and "MMM" in universe.SYMBOLS
    assert s.status["universe_source"].startswith("ishares")
    assert "ZQAAA" in _wide_row(delete=True)


def test_refresh_universe_falls_back_to_nasdaq(monkeypatch, saved_universe):
    import httpx

    from app.config import settings

    monkeypatch.setattr(settings, "universe", "sp500+r1000")
    monkeypatch.setattr(settings, "universe_extra", 40)
    monkeypatch.setattr(httpx, "get", _fake_get(False, True))
    s = ds.DataStore(SyntheticProvider, SessionLocal)
    s.refresh_universe()
    fake = [x for x in universe.SYMBOLS if x.startswith("ZN")]
    assert len(fake) == 40 and "ZNAAA" in fake
    assert universe.SYMBOLS["ZNAAA"] == {"name": "Fake 0", "sector": "Financials", "exchange": "", "industry": "Banks", "country": ""}
    assert s.status["universe_source"] == "nasdaq (40 mid caps)"
    _wide_row(delete=True)


def test_failed_midcaps_keep_universe_and_retry(monkeypatch, saved_universe):
    import httpx

    from app.config import settings

    monkeypatch.setattr(settings, "universe", "sp500+r1000")
    monkeypatch.setattr(httpx, "get", _fake_get(False, False))
    universe.SYMBOLS["ZKEEP"] = {"name": "Kept", "sector": "Energy", "exchange": ""}
    n = len(universe.stock_symbols())
    s = ds.DataStore(SyntheticProvider, SessionLocal)
    s.refresh_universe()
    assert "ZKEEP" in universe.SYMBOLS and len(universe.stock_symbols()) >= n
    assert "ishares ConnectError" in s.status["universe_source"] and "nasdaq ReadTimeout" in s.status["universe_source"]
    assert _wide_row() is None  # nothing saved ...
    assert s.stale("universe:wide2", ds.UNIVERSE_TTL)  # ... so the next pass tries again


def test_parse_nasdaq_screener_filters():
    payload = {"data": {"rows": [
        {"symbol": "SMALL", "name": "Small Co Common Stock", "lastsale": "$50", "marketCap": "1,000,000", "sector": "Technology", "industry": "x"},
        {"symbol": "BIG", "name": "Big Corp Class A Common Stock", "lastsale": "$100", "marketCap": "9,000,000,000", "sector": "Finance", "industry": "y"},
        {"symbol": "PENNY", "name": "Penny Inc Common Stock", "lastsale": "$1.20", "marketCap": "5,000,000,000", "sector": "Energy", "industry": "z"},
        {"symbol": "ABCW", "name": "ABC Corp Warrant", "lastsale": "$10", "marketCap": "8,000,000,000", "sector": "Energy", "industry": "z"},
        {"symbol": "XYZ^A", "name": "XYZ 6% Preferred", "lastsale": "$25", "marketCap": "8,000,000,000", "sector": "Energy", "industry": "z"},
        {"symbol": "BRK/B", "name": "Berkshire Hathaway Inc. Class B", "lastsale": "$480", "marketCap": "7,000,000,000", "sector": "Finance", "industry": "w"},
        {"symbol": "NOCAP", "name": "No Cap Common Stock", "lastsale": "$10", "marketCap": "", "sector": "Energy", "industry": "z"},
    ]}}
    out = universe.parse_nasdaq_screener(payload)
    assert list(out) == ["BIG", "BRK-B", "SMALL"]
    assert out["BIG"]["name"] == "Big Corp" and out["BIG"]["sector"] == "Financials"


def test_refresh_loop_continues_after_a_failing_step(monkeypatch):
    import threading

    s = ds.DataStore(SyntheticProvider, SessionLocal)
    calls = []
    monkeypatch.setattr(s, "load_all", lambda: 0)
    monkeypatch.setattr(s, "refresh_universe", lambda: calls.append("universe"))
    monkeypatch.setattr(s, "refresh_directory", lambda: calls.append("directory"))

    def boom(*a, **k):
        calls.append("prices")
        raise RuntimeError("database went away")

    monkeypatch.setattr(s, "refresh_prices", boom)
    monkeypatch.setattr(s, "refresh_slow", lambda *a, **k: calls.append("fundamentals"))
    done = threading.Event()
    monkeypatch.setattr(s, "refresh_ath", lambda *a, **k: (calls.append("ath"), done.set()))
    s.start(lambda: ["AAPL"], lambda: ["AAPL"], interval=3600)
    try:
        assert done.wait(5)
        for _ in range(50):
            if s.status["state"] == "error":
                break
            import time

            time.sleep(0.05)
        assert calls == ["universe", "directory", "prices", "fundamentals", "ath"]
        assert s.status["state"] == "error" and s.status["last_error"] == "prices: RuntimeError: database went away"
    finally:
        s._stop.set()


def test_diversify_moves_the_fourth_of_an_industry_down():
    items = [SimpleNamespace(symbol=f"S{i}") for i in range(8)] + [SimpleNamespace(symbol="B1"), SimpleNamespace(symbol="B2")]
    ind = {f"S{i}": "Semis" for i in range(8)} | {"B1": "Banks", "B2": "Banks"}
    top = diversify(items, ind)[:5]
    assert sum(1 for t in top if ind[t.symbol] == "Semis") == 3
    assert [t.symbol for t in top] == ["S0", "S1", "S2", "B1", "B2"]
    assert len(diversify(items, ind)) == 10  # nothing is dropped
    assert diversify(items, None) == items


def test_ideas_response_has_sector(client, register):
    from datetime import date

    from app.models import TradeIdea, User

    h, _ = register("sector-ideas@test.ro")
    with SessionLocal() as db:
        db.query(User).filter_by(email="sector-ideas@test.ro").one().plan = "premium"
        idea = TradeIdea(batch_date=date(2026, 11, 13), symbol="AAPL", timeframe="SWING", side="long", entry=100, stop=95, trim=107.5,
                         target=115, rr=3, weight=10, score=99, reason="test", status="WAIT", current=100)
        db.add(idea)
        db.commit()
        iid = idea.id
    try:
        r = client.get("/api/ideas", headers=h)
        assert r.status_code == 200
        row = next(i for i in r.json()["ideas"] if i["id"] == iid)
        assert row["sector"] == "Technology" and row["industry"]
    finally:
        with SessionLocal() as db:
            db.query(TradeIdea).filter_by(id=iid).delete()
            db.commit()


def test_save_survives_a_concurrent_insert(monkeypatch):
    """The insert loses a race with another thread: the row is updated instead of raising."""
    from app.models import MarketCache

    s = ds.DataStore(SyntheticProvider, SessionLocal)
    with SessionLocal() as db:
        db.add(MarketCache(key="prices:ZRACE", payload=ds._pack({"v": 1})))
        db.commit()
    calls = {"n": 0}
    from sqlalchemy.orm import Session

    orig = Session.get

    def first_miss(self, model, key, *a, **k):
        if model is MarketCache and key == "prices:ZRACE" and calls["n"] == 0:
            calls["n"] += 1
            return None  # this thread didn't see the other thread's row yet
        return orig(self, model, key, *a, **k)

    monkeypatch.setattr(Session, "get", first_miss)
    s._save("prices:ZRACE", {"v": 2})
    monkeypatch.setattr(Session, "get", orig)
    with SessionLocal() as db:
        row = db.get(MarketCache, "prices:ZRACE")
        assert ds._unpack(row.payload) == {"v": 2}
        db.delete(row)
        db.commit()


def test_ideas_use_completed_sessions_only():
    from datetime import datetime, timezone

    import pandas as pd

    from app.ideas_service import _completed_sessions

    idx = pd.bdate_range("2026-11-10", "2026-11-17")
    df = pd.DataFrame({"close": range(len(idx))}, index=idx)
    during = datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc)  # 10:00 New York, market open
    after = datetime(2026, 11, 17, 21, 30, tzinfo=timezone.utc)  # 16:30 New York
    assert _completed_sessions({"X": df}, during)["X"].index[-1] == pd.Timestamp("2026-11-16")
    assert _completed_sessions({"X": df}, after)["X"].index[-1] == pd.Timestamp("2026-11-17")


def test_forced_regenerate_keeps_triggered_and_taken_ideas(monkeypatch, register):
    register("regen-keep@test.ro")  # a user to own the taken trade
    from datetime import date

    from app import ideas_service
    from app.models import PaperTrade, TradeIdea, User
    from engine.ideas import Idea

    p = SyntheticProvider()
    hist = {s: p.history(s) for s in ("AAPL", "MSFT")}
    day = max(df.index[-1] for df in hist.values()).date()
    monkeypatch.setattr(ideas_service, "_histories", lambda: hist)
    monkeypatch.setattr(ideas_service, "_completed_sessions", lambda h, now=None: h)
    monkeypatch.setattr(ideas_service, "_scan", lambda *a: {})
    monkeypatch.setattr(ideas_service, "_vnicorn", lambda *a, **k: [])
    monkeypatch.setattr(ideas_service, "publish_summary", lambda *a, **k: None)
    monkeypatch.setattr(ideas_service, "add_feed", lambda *a, **k: 0)
    new = [Idea("AAPL", "SWING", "long", 100, 95, 107.5, 115, 3, 10, 90, "new"),
           Idea("ZZNEW", "SWING", "long", 50, 47, 54.5, 59, 3, 10, 80, "new")]
    monkeypatch.setattr(ideas_service, "generate", lambda *a, **k: list(new))

    def idea(sym, status):
        return TradeIdea(batch_date=day, symbol=sym, timeframe="SWING", side="long", entry=100, stop=95, trim=107.5, target=115,
                         rr=3, weight=10, score=50, reason="old", status=status, current=100)

    with SessionLocal() as db:
        db.query(TradeIdea).filter(TradeIdea.batch_date == day).delete()
        a, b, c = idea("AAPL", "BUY"), idea("MSFT", "WAIT"), idea("KO", "WAIT")
        db.add_all([a, b, c])
        db.commit()
        uid = db.query(User).first().id
        db.add(PaperTrade(user_id=uid, idea_id=c.id, symbol="KO", side="long", entry_date=day, entry=100, stop=95, target=115))
        db.commit()
        ids = (a.id, b.id, c.id)
    try:
        with SessionLocal() as db:
            ideas_service.run_ideas(db, force=True)
            left = {(r.symbol, r.reason) for r in db.query(TradeIdea).filter(TradeIdea.batch_date == day)}
        assert ("AAPL", "old") in left and ("AAPL", "new") not in left  # triggered idea kept, no duplicate
        assert ("KO", "old") in left  # taken idea kept
        assert ("MSFT", "old") not in left  # waiting, untaken idea replaced
        assert ("ZZNEW", "new") in left
    finally:
        with SessionLocal() as db:
            db.query(PaperTrade).filter(PaperTrade.idea_id.in_(ids)).delete(synchronize_session=False)
            db.query(TradeIdea).filter(TradeIdea.batch_date == day).delete()
            db.commit()


def test_foreign_company_amounts_in_usd(monkeypatch):
    """Finnhub reports TSMC in Taiwan dollars: the market cap is converted and local per-share figures are skipped."""
    from engine.data import finnhub

    monkeypatch.setitem(finnhub._fx, "TWD", (1e18, 0.031))  # cached rate, no network
    fh = finnhub.Finnhub.__new__(finnhub.Finnhub)
    prof = {"name": "Taiwan Semiconductor", "currency": "TWD", "marketCapitalization": 57_440_000, "finnhubIndustry": "Semiconductors",
            "shareOutstanding": 25_930}
    met = {"peTTM": 22.5, "52WeekHigh": 2590, "52WeekLow": 1375, "epsTTM": 98.25, "grossMarginTTM": 65.9}
    monkeypatch.setattr(fh, "profile", lambda s: prof, raising=False)
    monkeypatch.setattr(fh, "metrics", lambda s: met, raising=False)
    monkeypatch.setattr(fh, "recommendations", lambda s: [], raising=False)
    f = fh.fundamentals("TSM")
    assert f["market_cap_b"] == round(57_440 * 0.031, 1) and f["ccy"] == "USD" and f["pe"] == 22.5
    co = fh.enrich_company({"symbol": "TSM", "analysts": {"total": 1}})
    assert co["stats"]["market_cap_b"] == round(57_440 * 0.031, 1)
    assert "week52_high" not in co["stats"] and "eps_ttm" not in co["stats"]
    assert co["profitability"]["gross_margin"] == 65.9
    monkeypatch.setitem(finnhub._fx, "XYZ", (1e18, None))
    assert finnhub.Finnhub.cap_usd_b({"currency": "XYZ", "marketCapitalization": 5}) is None
    assert finnhub.Finnhub.cap_usd_b({"currency": "USD", "marketCapitalization": 3_000_000}) == 3000.0


def test_old_local_currency_caps_hidden_and_refetched_first(monkeypatch, saved_universe):
    from app import market_data

    universe.SYMBOLS["ZJPN"] = {"name": "Japan Co", "sector": "Health Care", "exchange": "", "country": "Japan"}
    universe.SYMBOLS["ZUSA"] = {"name": "US Co", "sector": "Health Care", "exchange": "", "country": "United States"}
    s = ds.DataStore(SyntheticProvider, SessionLocal)
    old = {"market_cap_b": 11070.0, "pe": 27.0, "source": "finnhub"}  # stored before the USD conversion
    s.slow["fundamentals"]["ZJPN"] = dict(old)
    s.slow["fundamentals"]["ZUSA"] = dict(old)
    monkeypatch.setattr(ds, "get_store", lambda: s)
    monkeypatch.setattr(market_data, "get_store", lambda: s)
    assert market_data.cached("fundamentals", "ZJPN")["market_cap_b"] is None  # hidden until refreshed
    assert market_data.cached("fundamentals", "ZJPN")["pe"] == 27.0  # ratios stay
    assert market_data.cached("fundamentals", "ZUSA")["market_cap_b"] == 11070.0
    assert universe.is_foreign("ZJPN") and not universe.is_foreign("ZUSA") and not universe.is_foreign("AAPL")

    # the refresh fetches the foreign one first
    order = []
    monkeypatch.setattr(SyntheticProvider, "fundamentals", lambda self, sym: order.append(sym) or {"market_cap_b": 70.0, "ccy": "USD"})
    monkeypatch.setattr(SyntheticProvider, "earnings", lambda self, sym: {"next_date": "2026-12-01", "history": []})
    monkeypatch.setattr(ds, "SLOW_PAUSE", 0)
    s.refresh_slow(["ZUSA", "ZJPN"])
    assert order[0] == "ZJPN"
    assert market_data.cached("fundamentals", "ZJPN")["market_cap_b"] == 70.0


def test_parse_nasdaq_keeps_country():
    out = universe.parse_nasdaq_screener({"data": {"rows": [
        {"symbol": "IBN", "name": "ICICI Bank Limited Common Stock", "lastsale": "$30", "marketCap": "100,000,000,000",
         "sector": "Finance", "industry": "Banks", "country": "India"}]}})
    assert out["IBN"]["country"] == "India"


def test_screens_rebuilt_after_startup_load(monkeypatch):
    """Screens computed while the store was half loaded are marked stale when loading ends (and short-lived meanwhile)."""
    import threading

    from app import market_data
    from app.config import settings

    s = ds.DataStore(SyntheticProvider, SessionLocal)
    key = f"{settings.data_provider}:screen-rows"
    market_data._fast_cache[key] = (__import__("time").monotonic(), ["partial"])
    monkeypatch.setattr(market_data, "get_store", lambda: s)
    s.status["state"] = "loading"
    assert market_data.screen_ttl(120) == 30 and market_data.loading()["total"] > 0
    calls = []
    s.on_prices_refreshed(lambda: calls.append("scan"))
    done = threading.Event()
    monkeypatch.setattr(s, "load_all", lambda: 0)
    for name in ("refresh_universe", "refresh_directory", "refresh_prices", "refresh_slow"):
        monkeypatch.setattr(s, name, lambda *a, **k: None)
    monkeypatch.setattr(s, "refresh_ath", lambda *a, **k: done.set())
    s.start(lambda: [], lambda: [], interval=3600)
    try:
        assert done.wait(5)
        assert calls and calls[0] == "scan"
        assert market_data._fast_cache[key][0] == float("-inf")  # rebuilt on the next request
        assert market_data.loading() is None and market_data.screen_ttl(120) == 120
    finally:
        s._stop.set()
        market_data._fast_cache.pop(key, None)


def _store_with_prices(last_day: str, n_symbols: int | None = None):
    import pandas as pd

    from engine.data.universe import stock_symbols

    s = ds.DataStore(SyntheticProvider, SessionLocal)
    idx = pd.bdate_range(end=last_day, periods=30)
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    syms = stock_symbols()
    for sym in syms[: n_symbols if n_symbols is not None else len(syms)]:
        s.prices[sym] = df
    s.status["state"] = "refreshing"
    return s


def test_ideas_due_from_data_after_sleep(monkeypatch):
    from datetime import date, datetime, timezone

    from app import data_store, ideas_service

    batch = {"last": date(2026, 11, 13)}  # Friday's batch exists
    monkeypatch.setattr(ideas_service, "latest_batch", lambda db: batch["last"])
    s = _store_with_prices("2026-11-16")  # prices through Monday
    monkeypatch.setattr(data_store, "get_store", lambda: s)
    tue_morning = datetime(2026, 11, 17, 15, 0, tzinfo=timezone.utc)  # 10:00 New York
    assert ideas_service.last_completed_session(tue_morning) == date(2026, 11, 16)
    assert ideas_service.due_for_ideas(None, tue_morning)  # Monday's batch was missed while asleep: catch up
    batch["last"] = date(2026, 11, 16)
    assert not ideas_service.due_for_ideas(None, tue_morning)

    # weekend: prices through Friday, Friday's batch exists -> nothing to do
    s2 = _store_with_prices("2026-11-20")
    monkeypatch.setattr(data_store, "get_store", lambda: s2)
    batch["last"] = date(2026, 11, 20)
    assert not ideas_service.due_for_ideas(None, datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc))

    # a running bar for today doesn't count before 16:15 New York, it does after
    s3 = _store_with_prices("2026-11-17")
    monkeypatch.setattr(data_store, "get_store", lambda: s3)
    batch["last"] = date(2026, 11, 16)
    assert not ideas_service.due_for_ideas(None, tue_morning)
    assert ideas_service.due_for_ideas(None, datetime(2026, 11, 17, 21, 30, tzinfo=timezone.utc))


def test_ideas_wait_for_complete_data(monkeypatch):
    from datetime import date

    from app import data_store, ideas_service
    from engine.data.universe import stock_symbols

    monkeypatch.setattr(ideas_service, "latest_batch", lambda db: date(2026, 11, 13))
    s = _store_with_prices("2026-11-16")
    s.status["state"] = "loading"
    monkeypatch.setattr(data_store, "get_store", lambda: s)
    assert not ideas_service.due_for_ideas(None)  # still loading saved prices
    s2 = _store_with_prices("2026-11-16", n_symbols=len(stock_symbols()) // 2)
    monkeypatch.setattr(data_store, "get_store", lambda: s2)
    assert not ideas_service.due_for_ideas(None)  # only half the universe has prices


def test_final_close_bars_refreshed_before_a_batch(monkeypatch):
    from app import data_store, ideas_service

    calls = []
    s = _store_with_prices("2026-11-16")
    monkeypatch.setattr(s, "refresh_live", lambda syms, persist=False: calls.append((len(syms), persist)) or 0)
    monkeypatch.setattr(data_store, "get_store", lambda: s)
    monkeypatch.setattr(ideas_service, "_histories", lambda: {})
    ideas_service.run_ideas(None)
    assert calls and calls[0][1] is True
    calls.clear()
    ideas_service.run_ideas(None, force=True)  # the Regenerate button doesn't re-download
    assert not calls


def test_one_broken_stock_does_not_empty_the_screens():
    import numpy as np
    import pandas as pd

    from engine import market_tools as mt
    from engine.scanner import scan_universe

    p = SyntheticProvider()
    hist = {s: p.history(s) for s in ("AAPL", "MSFT", "NVDA")}
    bad = hist["AAPL"].copy()
    bad.iloc[-2:, bad.columns.get_loc("close")] = 0.0  # a zero close
    nan = hist["MSFT"].copy()
    nan["close"] = np.nan
    hist2 = {**hist, "ZBAD": bad, "ZNAN": nan}
    rows = mt.mover_rows(hist2, universe.SYMBOLS)
    assert {r["symbol"] for r in rows} == {"AAPL", "MSFT", "NVDA"}
    screen = mt.screen_rows(rows + [{"symbol": "ZODD", "name": "x", "sector": "y"}], [], {}, {})
    assert len(screen) == 3  # the malformed row is skipped
    scan = scan_universe(lambda s: hist2[s] if s in hist2 else p.history(s), list(hist2))
    assert {"AAPL", "MSFT", "NVDA"} <= {r["symbol"] for r in scan} and "ZNAN" not in {r["symbol"] for r in scan}


def test_saved_universe_restored_on_startup(monkeypatch, saved_universe):
    from app.config import settings

    monkeypatch.setattr(settings, "universe", "sp500+r1000")
    s = ds.DataStore(SyntheticProvider, SessionLocal)
    s._save("universe:wide2", {"ZREST": {"name": "Restored", "sector": "Energy", "exchange": ""}})
    s._save("universe:wide", {"ZOLD": {"name": "Old", "sector": "Energy", "exchange": ""}})  # an older key: ignored
    try:
        fresh = ds.DataStore(SyntheticProvider, SessionLocal)
        fresh.load_all()
        assert "ZREST" in universe.SYMBOLS and "ZOLD" not in universe.SYMBOLS
        assert not fresh.stale("universe:wide2", ds.UNIVERSE_TTL)
    finally:
        from app.models import MarketCache

        with SessionLocal() as db:
            db.query(MarketCache).filter(MarketCache.key.in_(["universe:wide2", "universe:wide"])).delete(synchronize_session=False)
            db.commit()


def test_background_rebuild_uses_fresh_inputs(monkeypatch):
    """A screen rebuilt in the background computes the screens it depends on fresh, not from their stale value."""
    from app import market_data

    calls = {"inner": 0}
    market_data._fast_cache.pop("t:inner", None)
    market_data._fast_cache.pop("t:outer", None)

    def inner():
        calls["inner"] += 1
        return calls["inner"]

    assert market_data._fast("t:inner", 999, inner, stale_ok=True) == 1
    market_data._fast_cache["t:inner"] = (float("-inf"), 1)  # stale
    market_data._tls.rebuilding = True
    try:
        assert market_data._fast("t:inner", 999, inner, stale_ok=True) == 2  # computed now, not the stale 1
    finally:
        market_data._tls.rebuilding = False
    market_data._fast_cache["t:inner"] = (float("-inf"), 2)
    assert market_data._fast("t:inner", 999, inner, stale_ok=True) == 2  # a request thread gets the old value at once
    market_data._fast_cache.pop("t:inner", None)


def test_ideas_scan_rebuilt_when_it_misses_stocks(monkeypatch):
    """A scan built for a smaller universe is rebuilt before generating, so new stocks get real scores."""
    from app import ideas_service
    from app.routers import sepa

    p = SyntheticProvider()
    syms = ["AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "AVGO", "AMD", "JPM", "KO"]
    calls = {"n": 0}

    def fake_scan(history, symbols=None):
        calls["n"] += 1
        return [{"symbol": s, "rs_rating": 80} for s in (syms[:2] if calls["n"] == 1 else syms)]

    monkeypatch.setattr(sepa, "scan_universe", fake_scan)
    sepa._scan_cache.clear()
    try:
        old = sepa.cached_scan()
        assert len(old) == 2  # built when only 2 stocks were known
        got = ideas_service._scan(syms)
        assert set(got) == set(syms) and calls["n"] == 2
        assert len(ideas_service._scan(syms)) == len(syms) and calls["n"] == 2  # covered now: no rebuild
    finally:
        sepa._scan_cache.clear()


def test_vnicorn_retrains_when_universe_grew(monkeypatch):
    from app import vnicorn_service as vs

    trained = []
    monkeypatch.setattr(vs, "load", lambda db: {"symbols": 36, "models": {"x": 1}})
    monkeypatch.setattr(vs, "_trained_at", __import__("datetime").datetime.now(__import__("datetime").timezone.utc))
    monkeypatch.setattr(vs, "_liquid", lambda hist, n: {f"S{i}": None for i in range(120)})
    monkeypatch.setattr(vs, "real_trades", lambda db, hist: [])
    monkeypatch.setattr(vs.ai, "train", lambda subset, bench, trades, trade_histories=None, **k: trained.append(len(subset)) or {"models": {"y": 1}})
    monkeypatch.setattr(vs, "_save", lambda db, b: None)
    vs.ensure_trained(None, {}, None)
    assert trained == [120]  # 36 << 120 available: retrained although trained this week
    trained.clear()
    monkeypatch.setattr(vs, "load", lambda db: {"symbols": 118, "models": {"x": 1}})
    vs.ensure_trained(None, {}, None)
    assert trained == []  # close enough: keeps the weekly schedule


def test_regenerate_runs_in_background(client, register, monkeypatch):
    import time

    from app import ideas_service
    from app.models import User
    from app.routers import ideas as ideas_router

    h, _ = register("regen-admin@test.ro")
    with SessionLocal() as db:
        db.query(User).filter_by(email="regen-admin@test.ro").one().role = "admin"
        db.commit()
    monkeypatch.setattr(ideas_service, "_data_ready", lambda: False)
    assert client.post("/api/ideas/regenerate", headers=h).status_code == 409
    monkeypatch.setattr(ideas_service, "_data_ready", lambda: True)
    monkeypatch.setattr(ideas_router, "run_ideas", lambda db, force=False: [1, 2, 3])
    r = client.post("/api/ideas/regenerate", headers=h)
    assert r.status_code == 200 and r.json()["started"]
    for _ in range(50):
        st = client.get("/api/ideas/regenerate", headers=h).json()
        if not st["running"]:
            break
        time.sleep(0.05)
    assert st["generated"] == 3 and st["error"] is None


def test_training_rows_stay_within_budget():
    """More stocks make the sampling sparser, so training memory stays about the same."""
    import numpy as np

    from engine import vnicorn_ai as ai

    p = SyntheticProvider()
    base = [p.history(s) for s in universe.stock_symbols()[:10]]
    few = {f"F{i}": base[i % 10] for i in range(10)}
    many = {f"M{i}": base[i % 10] for i in range(80)}
    bench = p.history("SPY")
    n_few = len(ai.build_dataset(few, bench, budget=800)["long"])
    n_many = len(ai.build_dataset(many, bench, budget=800)["long"])
    assert n_many < 2 * n_few  # 8x the stocks, not 8x the rows
    d = ai.build_dataset(few, bench, budget=800)
    assert set(ai.MARKET_FEATURES) <= set(d["long"].columns) and {"stop_atr", "target_r", "y", "symbol", "date"} <= set(d["long"].columns)
    assert d["long"]["y"].isin([0, 1]).all() and np.isfinite(d["long"]["stop_atr"]).all()


def test_setup_quotas_keep_trade_and_invest():
    from types import SimpleNamespace as N

    from engine.ideas import _with_quotas

    longs = [N(symbol=f"S{i}", timeframe="SWING") for i in range(80)] + [N(symbol=f"T{i}", timeframe="TRADE") for i in range(5)] \
        + [N(symbol=f"I{i}", timeframe="INVEST") for i in range(5)]
    out = _with_quotas(longs, 60)
    kinds = [i.timeframe for i in out]
    assert len(out) == 60 and kinds.count("TRADE") == 5 and kinds.count("INVEST") == 5 and kinds.count("SWING") == 50


def test_scan_and_alerts_pages(client, register):
    from app.models import Alert, User

    h, _ = register("pages-user@test.ro")
    with SessionLocal() as db:
        u = db.query(User).filter_by(email="pages-user@test.ro").one()
        u.plan = "premium"
        for i in range(60):
            db.add(Alert(user_id=u.id, symbol=f"Z{i:03d}", type="price_above", severity="info", title=f"A{i}", message="m", bar_date="2026-11-17"))
        db.commit()
    first = client.get("/api/sepa/scan?limit=10", headers=h).json()
    assert len(first["results"]) == min(10, first["count"]) and "has_more" in first
    if first["count"] > 10:
        second = client.get("/api/sepa/scan?limit=10&offset=10", headers=h).json()
        assert {r["symbol"] for r in first["results"]}.isdisjoint({r["symbol"] for r in second["results"]})
    a1 = client.get("/api/alerts?offset=0&limit=50", headers=h).json()
    assert a1["count"] == 60 and len(a1["results"]) == 50 and a1["has_more"]
    a2 = client.get("/api/alerts?offset=50&limit=50", headers=h).json()
    assert len(a2["results"]) == 10 and not a2["has_more"]
    assert isinstance(client.get("/api/alerts", headers=h).json(), list)  # without offset: the plain list, as before


def test_scan_order_ai_default_and_columns(client, register, monkeypatch):
    from app import vnicorn_service
    from app.models import User

    h, _ = register("scan-order@test.ro")
    with SessionLocal() as db:
        db.query(User).filter_by(email="scan-order@test.ro").one().plan = "premium"
        db.commit()
    syms = [r["symbol"] for r in client.get("/api/sepa/scan?limit=200", headers=h).json()["results"]]
    probs = {s: (i % 10) / 10 for i, s in enumerate(syms)}
    monkeypatch.setattr(vnicorn_service, "move_prob", lambda s: probs.get(s))
    r = client.get("/api/sepa/scan?limit=200", headers=h).json()
    assert r["order"] == "ai"
    ai = [x["ai_prob"] for x in r["results"]]
    assert ai == sorted(ai, reverse=True)
    rs = client.get("/api/sepa/scan?limit=200&order=rs&dir=asc", headers=h).json()["results"]
    vals = [x["rs_rating"] for x in rs if x["rs_rating"] is not None]
    assert vals == sorted(vals)
    # without vnicornAI ratings: the tab's score
    monkeypatch.setattr(vnicorn_service, "move_prob", lambda s: None)
    r2 = client.get("/api/sepa/scan?limit=200", headers=h).json()
    assert r2["order"] == "bull"
    b = [x["bull_score"] or 0 for x in r2["results"]]
    assert b == sorted(b, reverse=True)
