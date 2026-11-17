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
        row = db.scalar(select(MarketCache).where(MarketCache.key == "universe:wide"))
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
    assert universe.SYMBOLS["ZNAAA"] == {"name": "Fake 0", "sector": "Financials", "exchange": "", "industry": "Banks"}
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
    assert s.stale("universe:wide", ds.UNIVERSE_TTL)  # ... so the next pass tries again


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
