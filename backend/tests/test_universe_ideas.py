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


def _fake_get(r1000_ok: bool):
    import httpx

    def get(url, *a, **k):
        if url == universe.R1000_CSV:
            if not r1000_ok:
                raise httpx.ConnectError("offline")
            rows = [f'"ZQ{chr(65 + i // 676)}{chr(65 + i // 26 % 26)}{chr(65 + i % 26)}","Fake {i}","Industrials","Equity","1.00","{900 - i}","1","1","1","US","NASDAQ","USD","1","USD","-"'
                    for i in range(900)]
            text = "iShares Russell 1000 ETF\nTicker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Quantity,Price,Location,Exchange,Currency,FX Rate,Market Currency,Accrual Date\n" + "\n".join(rows)
            return SimpleNamespace(text=text, raise_for_status=lambda: None)
        raise httpx.ConnectError("offline")  # S&P 500 list: falls back to the bundled copy

    return get


def test_refresh_universe_r1000(monkeypatch, saved_universe):
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
    n = len(universe.stock_symbols())

    # a failed Russell 1000 download a week later never shrinks the universe
    monkeypatch.setattr(httpx, "get", _fake_get(False))
    s2 = ds.DataStore(SyntheticProvider, SessionLocal)
    s2.refresh_universe()
    assert len(universe.stock_symbols()) == n
    from sqlalchemy import select

    from app.models import MarketCache

    with SessionLocal() as db:
        row = db.scalar(select(MarketCache).where(MarketCache.key == "universe:r1000"))
        assert row is not None and "ZQAAA" in ds._unpack(row.payload)
        db.delete(row)
        db.commit()


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
