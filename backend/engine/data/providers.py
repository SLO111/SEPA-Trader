"""Market data providers. All return a DataFrame with a date index and the columns
open, high, low, close, volume (lowercase)."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from .universe import SYMBOLS

INTERVALS = {"1d", "1wk", "1mo"}


class DataProvider(ABC):
    name: str

    @abstractmethod
    def history(self, symbol: str, interval: str = "1d", years: int = 3) -> pd.DataFrame: ...


def _resample(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    if interval == "1d":
        return df
    rule = {"1wk": "W-FRI", "1mo": "ME"}[interval]
    out = df.resample(rule).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return out.dropna()


class SyntheticProvider(DataProvider):
    """Deterministic demo data (same symbol => same data) for offline development.
    These are NOT real prices."""

    name = "synthetic"

    def history(self, symbol: str, interval: str = "1d", years: int = 3) -> pd.DataFrame:
        return _resample(_synthetic_daily(symbol.upper(), years, date.today()), interval)


@lru_cache(maxsize=512)
def _synthetic_daily(symbol: str, years: int, end: date) -> pd.DataFrame:
    seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(end=end, periods=int(252 * years))
    n = len(days)

    # Market regimes: up/down/sideways periods with different volatility.
    base_vol = rng.uniform(0.011, 0.032)
    drift = np.empty(n)
    vol = np.empty(n)
    i = 0
    while i < n:
        length = int(rng.integers(30, 140))
        regime = rng.choice(["up", "down", "flat"], p=[0.45, 0.25, 0.30])
        d = {"up": rng.uniform(0.0008, 0.0025), "down": rng.uniform(-0.0022, -0.0006), "flat": 0.0}[regime]
        v = base_vol * (0.6 if regime == "flat" else rng.uniform(0.9, 1.3))
        drift[i : i + length] = d
        vol[i : i + length] = v
        i += length

    rets = drift + vol * rng.standard_t(df=4, size=n) / np.sqrt(2)
    close = rng.uniform(20, 400) * np.exp(np.cumsum(rets))
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, base_vol / 3, n))
    spread = np.abs(rng.normal(0, base_vol * 0.8, n)) * close
    high = np.maximum(open_, close) + spread * rng.uniform(0.2, 1.0, n)
    low = np.minimum(open_, close) - spread * rng.uniform(0.2, 1.0, n)
    base_volume = rng.uniform(2e6, 6e7)
    volume = base_volume * np.exp(rng.normal(0, 0.35, n)) * (1 + 8 * np.abs(rets))

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume.round()},
        index=pd.DatetimeIndex(days, name="date"),
    )


class YFinanceProvider(DataProvider):
    """Free real data from Yahoo Finance (delayed). Fine for personal use and development;
    paying users require a provider with a commercial license."""

    name = "yfinance"

    def history(self, symbol: str, interval: str = "1d", years: int = 3) -> pd.DataFrame:
        import yfinance as yf

        start = date.today() - timedelta(days=int(365.25 * years) + 5)
        df = yf.Ticker(symbol).history(start=start.isoformat(), interval="1d", auto_adjust=True)
        if df.empty:
            raise LookupError(f"No data available for {symbol}")
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        df.index = pd.DatetimeIndex(df.index.tz_localize(None).normalize(), name="date")
        return _resample(df, interval)


_PROVIDERS: dict[str, type[DataProvider]] = {"synthetic": SyntheticProvider, "yfinance": YFinanceProvider}


def get_provider(name: str) -> DataProvider:
    try:
        return _PROVIDERS[name]()
    except KeyError:
        raise ValueError(f"Unknown provider: {name}. Options: {', '.join(_PROVIDERS)}")


def known_symbol(symbol: str) -> bool:
    return symbol.upper() in SYMBOLS
