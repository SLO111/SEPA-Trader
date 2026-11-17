"""Market data access with an in-memory TTL cache, so the provider isn't hit on every request."""

import logging
import threading
import time
from threading import Lock

import pandas as pd

from engine.data.providers import INTERVALS, _resample, get_provider

from .config import settings
from .data_store import get_store

log = logging.getLogger("sepa.cache")

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


def stored_history(symbol: str) -> pd.DataFrame:
    """Daily history for universe-wide screens (scan, screener, movers, ideas): only prices already downloaded by the
    background refresh. A missing symbol is skipped (LookupError) instead of being fetched on the spot, so a screen over
    hundreds of stocks never waits for hundreds of one-by-one downloads (e.g. right after a deploy or a wider universe)."""
    store = get_store()
    if store is None:
        return history(symbol)
    df = store.get_prices(symbol.upper().strip())
    if df is None:
        raise LookupError(f"No stored prices yet for {symbol}")
    return df


INTRADAY = {"5m", "15m", "1h"}


def chart_data(symbol: str, interval: str = "1d", years: int = 3) -> pd.DataFrame:
    """Daily/weekly/monthly history, or intraday bars (with pre-market and after-hours) refreshed every minute."""
    if interval in INTRADAY:
        sym = symbol.upper().strip()
        return _fast(f"{settings.data_provider}:intraday:{sym}:{interval}", 60,
                     lambda: get_provider(settings.data_provider).intraday(sym, interval))
    return history(symbol, interval, years)


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
    if kind == "ath":
        if store is not None and (v := store.get_slow("ath", symbol.upper())):
            return v
        try:
            d = history(symbol)
        except Exception:
            return None
        return {"ath": float(d["high"].max()), "date": d["high"].idxmax().strftime("%Y-%m"), "partial": True}
    if store is None:
        return fundamentals(symbol) if kind == "fundamentals" else earnings(symbol)
    v = store.get_slow(kind, symbol.upper())
    return _usd_guard(symbol, v) if kind == "fundamentals" else v


def _usd_guard(symbol: str, f: dict | None) -> dict | None:
    """Fundamentals stored before amounts were converted to US dollars: a foreign company's market cap may be in its
    own currency (yen, rupees...), so it is hidden until the background refresh replaces it."""
    if not f or f.get("ccy") == "USD" or f.get("market_cap_b") is None:
        return f
    from engine.data.universe import is_foreign

    return {**f, "market_cap_b": None} if is_foreign(symbol) else f


def fundamentals_fresh(symbol: str) -> dict:
    """For a single symbol on screen: use stored fundamentals unless they are missing or incomplete,
    then fetch them now (Finnhub when configured) and store them."""
    store = get_store()
    if store is None:
        return fundamentals(symbol)
    sym = symbol.upper()
    f = store.get_slow("fundamentals", sym)
    if f and f.get("market_cap_b") is not None and not f.get("partial") and (f.get("ccy") == "USD" or f.get("source") != "finnhub"):
        return f
    try:
        fresh = get_provider(settings.data_provider).fundamentals(sym)
        if fresh.get("market_cap_b") is not None or not f:
            store.put_slow("fundamentals", sym, fresh)
            return fresh
    except Exception:
        pass
    return _usd_guard(sym, f) or {}


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
    """Company overview (profile, financials, analysts, ...); cached for 2 hours."""
    return _fast(f"{settings.data_provider}:company:{symbol.upper()}", 2 * 3600, lambda: get_provider(settings.data_provider).company(symbol.upper()))


def earnings(symbol: str) -> dict:
    return _stored("earnings", symbol, lambda: get_provider(settings.data_provider).earnings(symbol.upper()))


_fast_cache: dict[str, tuple[float, object]] = {}


_key_locks: dict[str, threading.Lock] = {}
cache_error: str | None = None  # last failed background refresh (shown in /api/health)
_refreshing: set[str] = set()


def _fast(key: str, ttl: float, loader, stale_ok: bool = False):
    """In-memory cache shared by all users.
    * Single flight: when many requests miss the same key at once, one computes it and the others wait for that result
      (instead of all computing the same heavy screen in parallel on a small server).
    * stale_ok: after the TTL, the previous value is served at once and refreshed in the background, so nobody waits
      for universe-wide screens (movers, Fear & Greed, groups...) once they were computed."""
    now = time.monotonic()
    with _lock:
        hit = _fast_cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
        if hit and stale_ok:
            if key not in _refreshing:
                _refreshing.add(key)
                threading.Thread(target=_refresh, args=(key, loader), name=f"refresh:{key[:40]}", daemon=True).start()
            return hit[1]
        klock = _key_locks.setdefault(key, threading.Lock())
    with klock:
        with _lock:
            hit = _fast_cache.get(key)
            if hit and time.monotonic() - hit[0] < ttl:  # computed by another request while this one waited
                return hit[1]
        value = loader()
        with _lock:
            _fast_cache[key] = (time.monotonic(), value)
        return value


UNIVERSE_KEYS = ("movers", "screen-rows", "fg", "groups", "exposure", "pulse-map", "earnings", "bt-dataset", "bt-md")


def mark_stale() -> None:
    """New prices or a different universe: the market-wide screens are rebuilt in the background on the next request
    (the previous result is served meanwhile)."""
    keys = {f"{settings.data_provider}:{k}" for k in UNIVERSE_KEYS}
    with _lock:
        for k in list(_fast_cache):
            if k in keys:
                _fast_cache[k] = (float("-inf"), _fast_cache[k][1])


def loading() -> dict | None:
    """While the store is still reading saved prices at startup: {"ready": stocks with prices, "total": universe}."""
    store = get_store()
    if store is None or store.status.get("state") != "loading":
        return None
    from engine.data.universe import stock_symbols

    syms = stock_symbols()
    return {"ready": sum(1 for s in syms if s in store.prices), "total": len(syms)}


def screen_ttl(normal: float) -> float:
    """Short cache while prices are still loading, so a partial list doesn't stick."""
    return 30 if loading() else normal


def _refresh(key: str, loader) -> None:
    try:
        value = loader()
        with _lock:
            _fast_cache[key] = (time.monotonic(), value)
    except Exception as e:
        global cache_error
        cache_error = f"{key}: {type(e).__name__}: {str(e)[:120]}"
        log.warning("Background refresh of %s failed; serving the previous value", key, exc_info=True)
    finally:
        with _lock:
            _refreshing.discard(key)


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


def quarterly_revenue(symbol: str) -> list[dict]:
    """Quarterly revenue (stored for a day in the market cache when it's active)."""
    from datetime import timedelta

    sym = symbol.upper().strip()
    store = get_store()
    if store is not None and not store.stale(f"revenue:{sym}", timedelta(days=1)):
        v = store.get_slow("revenue", sym)
        if v is not None:
            return v.get("quarters", [])

    def load():
        try:
            return get_provider(settings.data_provider).quarterly_revenue(sym)
        except Exception:
            return []

    q = _slow("revenue", sym, load)
    if store is not None and q:
        store.put_slow("revenue", sym, {"quarters": q})
    return q


def earnings_in_days(symbol: str, within: int = 5) -> int | None:
    """Trading days until the next earnings report, when it's within `within` trading days (else None)."""
    import numpy as np

    e = cached("earnings", symbol) or {}
    nd = e.get("next_date")
    if not nd:
        return None
    try:
        today = pd.Timestamp.today().normalize()
        d = pd.Timestamp(nd).normalize()
    except Exception:
        return None
    if d < today:
        return None
    n = int(np.busday_count(today.date(), d.date()))
    return n if n <= within else None
