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

    def fundamentals(self, symbol: str) -> dict:
        """Market cap ($B), P/E, dividend yield (%), EPS growth (%), sector, name."""
        from .fundamentals import reference

        meta = SYMBOLS.get(symbol.upper(), {})
        return {"name": meta.get("name", symbol.upper()), "sector": meta.get("sector", "Other"), **reference(symbol)}

    def dividends(self, symbol: str) -> pd.Series:
        """Per-share cash dividends indexed by ex-dividend date."""
        return pd.Series(dtype=float)

    def company(self, symbol: str) -> dict:
        """Full company overview for the ticker page (see engine/data/company.py)."""
        from .company import synthetic_company

        return synthetic_company(symbol, self.history(symbol), self.dividends(symbol))


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
        if not known_symbol(symbol):
            raise LookupError(f"No demo data for {symbol.upper()}")  # never invent prices for unknown tickers
        return _resample(_synthetic_daily(symbol.upper(), years, date.today()), interval)

    def dividends(self, symbol: str) -> pd.Series:
        """Quarterly demo dividends consistent with the reference dividend yield."""
        y = (self.fundamentals(symbol).get("dividend_yield") or 0) / 100
        if y <= 0:
            return pd.Series(dtype=float)
        close = self.history(symbol)["close"]
        dates = close.index[30::63]
        return pd.Series([round(float(close.loc[d]) * y / 4, 4) for d in dates], index=dates, name="dividends")


@lru_cache(maxsize=512)
def _synthetic_daily(symbol: str, years: int, end: date) -> pd.DataFrame:
    seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(end=end, periods=int(252 * years))
    n = len(days)

    # Daily volatility consistent with the stock's reference beta (riskier stocks swing more).
    from .fundamentals import reference

    beta = reference(symbol).get("beta")
    base_vol = 0.004 + 0.010 * beta if beta else rng.uniform(0.011, 0.032)
    # Market regimes: up/down/sideways periods with different volatility.
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

    def fundamentals(self, symbol: str) -> dict:
        import yfinance as yf

        base = super().fundamentals(symbol)
        try:
            info = yf.Ticker(symbol).info or {}
        except Exception:
            return base
        cap = info.get("marketCap")
        div = info.get("trailingAnnualDividendYield")  # a fraction, e.g. 0.027
        growth = info.get("earningsGrowth")  # a fraction
        live = {
            "name": info.get("shortName") or base["name"],
            "sector": info.get("sector") or base["sector"],
            "market_cap_b": round(cap / 1e9, 1) if cap else base["market_cap_b"],
            "pe": round(info["trailingPE"], 1) if info.get("trailingPE") else base["pe"],
            "dividend_yield": round(div * 100, 2) if div is not None else base["dividend_yield"],
            "eps_growth": round(growth * 100, 1) if growth is not None else base["eps_growth"],
            "beta": round(info["beta"], 2) if info.get("beta") is not None else base["beta"],
        }
        if info.get("quoteType") == "ETF":
            live["etf"] = True
        return {**base, **live}

    def company(self, symbol: str) -> dict:
        from .company import yfinance_company

        return yfinance_company(symbol, self.history(symbol), self.dividends(symbol))

    def dividends(self, symbol: str) -> pd.Series:
        import yfinance as yf

        try:
            s = yf.Ticker(symbol).dividends
        except Exception:
            return pd.Series(dtype=float)
        if s is None or s.empty:
            return pd.Series(dtype=float)
        s.index = pd.DatetimeIndex(s.index.tz_localize(None).normalize())
        return s.astype(float)


_PROVIDERS: dict[str, type[DataProvider]] = {"synthetic": SyntheticProvider, "yfinance": YFinanceProvider}


def get_provider(name: str) -> DataProvider:
    try:
        return _PROVIDERS[name]()
    except KeyError:
        raise ValueError(f"Unknown provider: {name}. Options: {', '.join(_PROVIDERS)}")


def known_symbol(symbol: str) -> bool:
    return symbol.upper() in SYMBOLS
