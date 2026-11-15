"""Acces la date cu cache in memorie (TTL), ca sa nu interogam furnizorul la fiecare request."""

import time
from threading import Lock

import pandas as pd

from engine.data.providers import INTERVALS, get_provider

from .config import settings

_TTL_SECONDS = 300
_cache: dict[tuple, tuple[float, pd.DataFrame]] = {}
_lock = Lock()


def history(symbol: str, interval: str = "1d", years: int = 3) -> pd.DataFrame:
    symbol = symbol.upper().strip()
    if interval not in INTERVALS:
        raise ValueError(f"Interval invalid: {interval}")
    key = (settings.data_provider, symbol, interval, years)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _TTL_SECONDS:
            return hit[1]
    df = get_provider(settings.data_provider).history(symbol, interval, years)
    if df.empty:
        raise LookupError(f"Nu exista date pentru {symbol}")
    with _lock:
        _cache[key] = (now, df)
    return df


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
