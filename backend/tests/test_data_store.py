from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app import data_store as ds
from app.db import SessionLocal
from engine.data.providers import SyntheticProvider
from engine.data.universe import SYMBOLS, extend, parse_constituents


class LiveFake(SyntheticProvider):
    """Synthetic history plus a controllable 'live' bar, standing in for Yahoo."""

    calls = {"bulk": 0, "live": 0, "fund": 0}

    def bulk_history(self, symbols, years=3):
        LiveFake.calls["bulk"] += 1
        return super().bulk_history(symbols, years)

    def live_bars(self, symbols):
        LiveFake.calls["live"] += 1
        out = {}
        for s in symbols:
            last = self.history(s).index[-1]
            out[s] = {"date": (last + pd.offsets.BDay()).strftime("%Y-%m-%d"), "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.5, "volume": 1e6, "time": "10:31 ET"}
        return out

    def fundamentals(self, symbol):
        LiveFake.calls["fund"] += 1
        return super().fundamentals(symbol)


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setattr(ds, "SLOW_PAUSE", 0)
    return ds.DataStore(LiveFake, SessionLocal)


def test_prices_persist_and_reload(store):
    assert store.refresh_prices(["AAPL", "MSFT"]) == 2
    assert store.refresh_prices(["AAPL", "MSFT"]) == 0  # fresh: nothing re-downloaded
    fresh = ds.DataStore(LiveFake, SessionLocal)
    fresh.load_all()
    a, b = store.get_prices("AAPL"), fresh.get_prices("AAPL")
    pd.testing.assert_frame_equal(a, b, check_freq=False)


def test_live_bar_updates_todays_row(store):
    store.refresh_prices(["NVDA"])
    before = store.get_prices("NVDA")
    store.touch("NVDA")
    assert store.hot_symbols() == ["NVDA"]
    assert store.refresh_live(store.hot_symbols()) == 1
    after = store.get_prices("NVDA")
    assert len(after) == len(before) + 1 and after["close"].iloc[-1] == 11.5
    assert store.live_at["NVDA"].endswith("10:31 ET")
    # a second update on the same day replaces the row instead of appending
    store.merge_bar("NVDA", {"date": after.index[-1].strftime("%Y-%m-%d"), "open": 10, "high": 13, "low": 9, "close": 12.25, "volume": 2e6})
    again = store.get_prices("NVDA")
    assert len(again) == len(after) and again["close"].iloc[-1] == 12.25


def test_hot_set_expires(store):
    store.touch("KO")
    store.hot["KO"] = datetime.now(timezone.utc) - timedelta(hours=1)
    assert store.hot_symbols() == []


def test_slow_refresh_is_incremental(store):
    assert store.refresh_slow(["KO", "PG"]) == 2
    assert store.get_slow("fundamentals", "KO")["sector"] == "Consumer Staples"
    calls = LiveFake.calls["fund"]
    assert store.refresh_slow(["KO", "PG"]) == 0  # already fresh: no provider calls at all
    assert LiveFake.calls["fund"] == calls


def test_market_session():
    et = timezone(timedelta(hours=-5))
    assert ds.market_session_open(datetime(2026, 11, 16, 10, 0, tzinfo=et))  # Monday 10:00 ET
    assert not ds.market_session_open(datetime(2026, 11, 16, 8, 0, tzinfo=et))
    assert not ds.market_session_open(datetime(2026, 11, 15, 12, 0, tzinfo=et))  # Sunday


def test_parse_constituents_and_extend():
    csv = "Symbol,Security,GICS Sector\nBRK.B,Berkshire Hathaway,Financials\nZZZT,Test Corp,Information Technology\n"
    entries = parse_constituents(csv)
    assert entries["BRK-B"]["sector"] == "Financials" and entries["ZZZT"]["sector"] == "Technology"
    try:
        assert extend(entries) == 1 and "ZZZT" in SYMBOLS
    finally:
        SYMBOLS.pop("ZZZT", None)


def test_market_data_reads_store_and_tracks_views(monkeypatch, store):
    from app import market_data

    store.refresh_prices(["AMD"])
    monkeypatch.setattr(market_data, "get_store", lambda: store)
    monkeypatch.setattr(ds, "get_store", lambda: store)
    df = market_data.history("AMD")
    assert df is store.get_prices("AMD") or df.equals(store.get_prices("AMD"))
    assert "AMD" not in store.hot_symbols()  # internal reads don't make a symbol "hot"
    market_data.watch("AMD")
    assert "AMD" in store.hot_symbols()
    assert market_data.history("AMD", "1wk").index.dayofweek.max() == 4  # weekly bars resampled from the store


def test_circuit_breaker_pauses_slow_refresh(store, monkeypatch):
    class Refusing(LiveFake):
        def fundamentals(self, symbol):
            raise RuntimeError("HTTP Error 401: Invalid Crumb")

        def earnings(self, symbol):
            raise RuntimeError("HTTP Error 401: Invalid Crumb")

    s = ds.DataStore(Refusing, SessionLocal)
    s.refresh_slow(["AAPL", "MSFT", "NVDA", "KO", "PG", "JPM"])
    assert s.slow_paused_until is not None and "paused" in s.status["message"]
    calls = []
    monkeypatch.setattr(Refusing, "fundamentals", lambda self, sym: calls.append(sym))
    assert s.refresh_slow(["AAPL"]) == 0 and calls == []  # no requests while paused


def test_universe_sp500_plus_uses_bundled_list_when_offline(monkeypatch):
    import httpx

    from app.config import settings
    from engine.data import universe

    saved = dict(universe.SYMBOLS)
    monkeypatch.setattr(settings, "universe", "sp500+")

    def offline(*a, **k):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", offline)
    try:
        s = ds.DataStore(LiveFake, SessionLocal)
        s.refresh_universe()
        assert "MMM" in universe.SYMBOLS and "ASML" in universe.SYMBOLS
        assert len(universe.stock_symbols()) > 500
    finally:
        universe.SYMBOLS.clear()
        universe.SYMBOLS.update(saved)


def test_realtime_quotes_from_finnhub(monkeypatch):
    import time as _t

    import engine.data.providers as prov

    s = ds.DataStore(LiveFake, SessionLocal)
    s.put_prices("AAPL", SyntheticProvider().history("AAPL", "1d", 1))
    last_day = s.get_prices("AAPL").index[-1]
    t = int(pd.Timestamp(last_day.date()).tz_localize("America/New_York").replace(hour=10, minute=31).timestamp())

    class Fake:
        def quote(self, sym):
            return {"c": 123.45, "o": 120, "h": 125, "l": 119, "pc": 118, "t": t}

    monkeypatch.setattr(prov, "_finnhub", lambda: Fake())
    assert s.refresh_quotes(["AAPL"]) == 1
    df = s.get_prices("AAPL")
    assert float(df["close"].iloc[-1]) == 123.45 and s.live_at["AAPL"].endswith("10:31 ET") and s.status["live_source"] == "finnhub"
