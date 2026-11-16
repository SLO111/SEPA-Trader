"""Market data access with an in-memory TTL cache, so the provider isn't hit on every request."""

import time
from threading import Lock

import pandas as pd

from engine.data.providers import INTERVALS, _resample, get_provider

from .config import settings
from .data_store import get_store

_TTL_SECONDS = 300
_cache: dict[tuple, tuple[float, pd.DataFrame]] = {}
_lock = Lock()


def history(symbol: str, interval: str = "1d", years: int = 3) -> pd.DataFrame:
    symbol = symbol.upper().strip()
    if interval not in INTERVALS:
        raise ValueError(f"Invalid interval: {interval}")
    store = get_store()
    if store is not None and years <= 3:
        df = store.get_prices(symbol)
        if df is None:
            df = get_provider(settings.data_provider).history(symbol, "1d", 3)
            if df.empty:
                raise LookupError(f"No data available for {symbol}")
            store.put_prices(symbol, df)
        return _resample(df, interval)
    key = (settings.data_provider, symbol, interval, years)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _TTL_SECONDS:
            return hit[1]
    df = get_provider(settings.data_provider).history(symbol, interval, years)
    if df.empty:
        raise LookupError(f"No data available for {symbol}")
    with _lock:
        _cache[key] = (now, df)
    return df


def watch(*symbols: str) -> None:
    """Symbols a person is looking at (chart, watchlist, portfolio, alerts) get minute-by-minute price updates."""
    store = get_store()
    if store is not None:
        for s in symbols:
            store.touch(s.upper().strip())


def quote(symbol: str) -> dict:
    df = history(symbol)
    last, prev = float(df["close"].iloc[-1]), float(df["close"].iloc[-2])
    return {
        "symbol": symbol.upper(),
        "price": round(last, 2),
        "change": round(last - prev, 2),
        "change_pct": round((last / prev - 1) * 100, 2),
        "volume": int(df["volume"].iloc[-1]),
        "date": df.index[-1].strftime("%Y-%m-%d"),
    }


_slow_cache: dict[tuple, tuple[float, object]] = {}
_SLOW_TTL = 12 * 3600


def _slow(kind: str, symbol: str, loader):
    key = (settings.data_provider, kind, symbol.upper())
    now = time.monotonic()
    with _lock:
        hit = _slow_cache.get(key)
        if hit and now - hit[0] < _SLOW_TTL:
            return hit[1]
    value = loader()
    with _lock:
        _slow_cache[key] = (now, value)
    return value


def _stored(kind: str, symbol: str, loader):
    store = get_store()
    if store is None:
        return _slow(kind, symbol, loader)
    value = store.get_slow(kind, symbol.upper())
    if value is None:
        value = loader()
        store.put_slow(kind, symbol.upper(), value)
    return value


def fundamentals(symbol: str) -> dict:
    """Fundamentals change slowly; refreshed daily in the background (live) or cached for 12 hours."""
    return _stored("fundamentals", symbol, lambda: get_provider(settings.data_provider).fundamentals(symbol.upper()))


def cached(kind: str, symbol: str) -> dict | None:
    """Stored fundamentals/earnings without calling the provider: for screens over the whole universe."""
    store = get_store()
    if store is None:
        return fundamentals(symbol) if kind == "fundamentals" else earnings(symbol)
    return store.get_slow(kind, symbol.upper())


def symbol_meta(symbol: str) -> dict:
    """Name / sector / exchange for any symbol: the universe first, then the US symbol directory."""
    from engine.data.universe import SYMBOLS

    s = symbol.upper()
    if s in SYMBOLS:
        return SYMBOLS[s]
    store = get_store()
    d = store.directory.get(s) if store else None
    if d:
        return {"name": d["name"], "sector": "ETF" if d["etf"] else "", "exchange": d["exchange"]}
    return {"name": s, "sector": "", "exchange": ""}


def search_symbols(query: str, limit: int = 10) -> list[dict]:
    """Universe matches first (they have full analysis), then every other US stock and ETF."""
    from engine.data.directory import search as dir_search
    from engine.data.universe import search as uni_search

    hits = uni_search(query, limit)
    store = get_store()
    if store is not None and store.directory:
        seen = {h["symbol"] for h in hits}
        q = query.strip().upper()
        extra = [h for h in dir_search(store.directory, query, limit) if h["symbol"] not in seen]
        # an exact ticker match always comes first
        hits = sorted(hits + extra, key=lambda h: h["symbol"] != q)[:limit]
    return hits


def live_status(symbol: str) -> str | None:
    store = get_store()
    return store.live_at.get(symbol.upper()) if store else None


def dividends(symbol: str) -> pd.Series:
    return _slow("dividends", symbol, lambda: get_provider(settings.data_provider).dividends(symbol.upper()))


def close_on(symbol: str, day) -> float | None:
    """Closing price on `day`, or the last close before it."""
    c = history(symbol)["close"]
    c = c[c.index <= pd.Timestamp(day)]
    return float(c.iloc[-1]) if len(c) else None


def company(symbol: str) -> dict:
    """Company overview (profile, financials, analysts, ...); cached for 12 hours."""
    return _slow("company", symbol, lambda: get_provider(settings.data_provider).company(symbol.upper()))


def earnings(symbol: str) -> dict:
    return _stored("earnings", symbol, lambda: get_provider(settings.data_provider).earnings(symbol.upper()))


_fast_cache: dict[str, tuple[float, object]] = {}


def _fast(key: str, ttl: float, loader):
    now = time.monotonic()
    with _lock:
        hit = _fast_cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = loader()
    with _lock:
        _fast_cache[key] = (now, value)
    return value


def extended_hours(symbols: list[str]) -> list[dict]:
    """Pre-market / after-hours quotes, refreshed every 5 minutes."""
    key = f"{settings.data_provider}:ext:{','.join(sorted(symbols))}"
    return _fast(key, 300, lambda: get_provider(settings.data_provider).extended_hours(symbols))


def fed() -> dict:
    """Fed rate monitor data (FRED), refreshed every 6 hours. Demo data in synthetic mode."""
    from engine.data import fed as fedmod

    if settings.data_provider == "synthetic":
        return _fast("fed:demo", 6 * 3600, fedmod.demo)
    return _fast("fed:live", 6 * 3600, fedmod.live)
