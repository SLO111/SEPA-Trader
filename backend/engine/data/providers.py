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

    def bulk_history(self, symbols: list[str], years: int = 3) -> dict[str, pd.DataFrame]:
        """Daily history for many symbols. Providers with a batch endpoint override this."""
        out = {}
        for s in symbols:
            try:
                out[s] = self.history(s, "1d", years)
            except Exception:
                continue
        return out

    def fundamentals(self, symbol: str) -> dict:
        """Market cap ($B), P/E, dividend yield (%), EPS growth (%), sector, name."""
        from .fundamentals import reference

        meta = SYMBOLS.get(symbol.upper(), {})
        return {"name": meta.get("name", symbol.upper()), "sector": meta.get("sector", "Other"), **reference(symbol)}

    def dividends(self, symbol: str) -> pd.Series:
        """Per-share cash dividends indexed by ex-dividend date."""
        return pd.Series(dtype=float)

    def quarterly_revenue(self, symbol: str) -> list[dict]:
        """Quarterly revenue, newest first: [{"date": quarter end, "revenue": $}]. Default: a demo series consistent with
        the reference growth rate (offline providers)."""
        from .fundamentals import reference

        ref = reference(symbol)
        cap = (ref.get("market_cap_b") or 50) * 1e9
        g = (ref.get("eps_growth") or 8) / 100
        q = pd.Timestamp.today().to_period("Q").start_time - pd.offsets.QuarterEnd(1)
        base = cap / 25 / 4
        out = []
        for i in range(9):
            d = (q - pd.offsets.QuarterEnd(i)).normalize()
            out.append({"date": d.strftime("%Y-%m-%d"), "revenue": round(base / ((1 + g) ** (i / 4)) * (1 + 0.03 * ((i * 7) % 3 - 1)))})
        return out

    def all_time_highs(self, symbols: list[str]) -> dict[str, dict]:
        """All-time high (split/dividend adjusted, like the prices) per symbol: {"ath": price, "date": "YYYY-MM"}.
        Default: the highest high in the available history."""
        out = {}
        for s in symbols:
            try:
                d = self.history(s, "1d", 3)
            except Exception:
                continue
            out[s] = {"ath": round(float(d["high"].max()), 4), "date": d["high"].idxmax().strftime("%Y-%m")}
        return out

    def company(self, symbol: str) -> dict:
        """Full company overview for the ticker page (see engine/data/company.py)."""
        from .company import synthetic_company

        return synthetic_company(symbol, self.history(symbol), self.dividends(symbol))

    def earnings(self, symbol: str) -> dict:
        """{"next_date", "next_eps_estimate", "history": [{date, eps_estimate, eps_actual, surprise_pct}]} (newest first)."""
        e = self.company(symbol)["earnings"]
        return {"next_date": e.get("next_date"), "next_eps_estimate": None, "history": e.get("history", [])}

    def extended_hours(self, symbols: list[str]) -> list[dict]:
        """Pre-market / after-hours quotes. Needs live intraday data; the base provider has none."""
        return []

    def live_bars(self, symbols: list[str]) -> dict[str, dict]:
        """Today's running daily bar per symbol ({date, open, high, low, close, volume}). None for offline providers."""
        return {}

    def intraday(self, symbol: str, interval: str) -> pd.DataFrame:
        """Intraday bars indexed by New York wall-clock time, with a "session" column: pre | regular | post."""
        raise NotImplementedError("Intraday charts need a live data provider")


INTRADAY_MINUTES = {"5m": 5, "15m": 15, "1h": 60}


def session_of(ts: pd.Timestamp) -> str:
    m = ts.hour * 60 + ts.minute
    return "pre" if m < 570 else "post" if m >= 960 else "regular"


def _synthetic_intraday(self, symbol: str, interval: str) -> pd.DataFrame:
        """Demo intraday bars for the last 5 sessions (4:00-20:00 ET), consistent with the daily closes."""
        daily = self.history(symbol).iloc[-6:]
        step = INTRADAY_MINUTES[interval]
        rng = np.random.default_rng(abs(hash((symbol.upper(), interval))) % 2**32)
        frames = []
        for (day, row), prev_close in zip(daily.iloc[1:].iterrows(), daily["close"].iloc[:-1]):
            times = pd.date_range(day + pd.Timedelta(hours=4), day + pd.Timedelta(hours=20) - pd.Timedelta(minutes=step), freq=f"{step}min")
            path = np.linspace(prev_close, row["close"], len(times)) * (1 + rng.normal(0, 0.002, len(times)).cumsum() / 10)
            path[-1] = row["close"]
            opens = np.r_[prev_close, path[:-1]]
            vol = np.where([session_of(t) == "regular" for t in times], row["volume"] / 78 * step / 5, row["volume"] / 2000)
            frames.append(pd.DataFrame({"open": opens, "high": np.maximum(opens, path) * 1.001, "low": np.minimum(opens, path) * 0.999,
                                        "close": path, "volume": vol.round()}, index=times))
        df = pd.concat(frames)
        df["session"] = [session_of(t) for t in df.index]
        return df


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
    intraday = _synthetic_intraday

    def history(self, symbol: str, interval: str = "1d", years: int = 3) -> pd.DataFrame:
        if not known_symbol(symbol):
            raise LookupError(f"No demo data for {symbol.upper()}")  # never invent prices for unknown tickers
        if symbol.upper() == "^VIX":
            return _resample(_synthetic_vix(years, date.today()), interval)
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


def _synthetic_vix(years: int, end: date) -> pd.DataFrame:
    """Demo VIX: the S&P 500 proxy's 20-day realized volatility, scaled like the real index (~12-40)."""
    spy = _synthetic_daily("SPY", years, end)
    rv = spy["close"].pct_change().rolling(20, min_periods=5).std() * np.sqrt(252) * 100
    vix = (rv * 0.9 + 4).bfill().clip(lower=9)
    return pd.DataFrame({"open": vix, "high": vix * 1.04, "low": vix * 0.96, "close": vix, "volume": 0.0}, index=spy.index)


def _ticker_frame(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """One symbol's columns from yf.download output. Recent yfinance versions return (ticker, field) MultiIndex
    columns even for a single symbol, so always select by ticker when the columns are multi-level."""
    if isinstance(data.columns, pd.MultiIndex):
        if symbol in data.columns.get_level_values(0):
            return data[symbol]
        if symbol in data.columns.get_level_values(1):
            return data.xs(symbol, axis=1, level=1)
        raise KeyError(symbol)
    return data


def _finnhub():
    """Finnhub client when FINNHUB_API_KEY is set (fundamentals, earnings, profiles, news that Yahoo blocks)."""
    import os

    # Accept the common names people use (the Signalist tutorial uses NEXT_PUBLIC_FINNHUB_API_KEY).
    names = ("FINNHUB_API_KEY", "FINNHUB_KEY", "FINNHUB_TOKEN", "NEXT_PUBLIC_FINNHUB_API_KEY", "NEXT_PUBLIC_NEXT_PUBLIC_FINNHUB_API_KEY")
    key = next((os.environ[n].strip() for n in names if os.environ.get(n, "").strip()), "")
    if not key:
        return None
    from .finnhub import Finnhub

    return Finnhub(key)


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

    def all_time_highs(self, symbols: list[str]) -> dict[str, dict]:
        """Full monthly history in batches: the highest monthly high is the all-time high."""
        import yfinance as yf

        out = {}
        for i in range(0, len(symbols), 100):
            chunk = symbols[i:i + 100]
            try:
                data = yf.download(chunk, period="max", interval="1mo", auto_adjust=True, group_by="ticker", threads=True, progress=False)
            except Exception:
                continue
            for s in chunk:
                try:
                    h = _ticker_frame(data, s).rename(columns=str.lower)["high"].dropna()
                except KeyError:
                    continue
                if len(h):
                    out[s] = {"ath": round(float(h.max()), 4), "date": pd.Timestamp(h.idxmax()).strftime("%Y-%m")}
        return out

    def bulk_history(self, symbols: list[str], years: int = 3) -> dict[str, pd.DataFrame]:
        """One batched download for many symbols (far fewer requests than one per symbol)."""
        import yfinance as yf

        start = date.today() - timedelta(days=int(365.25 * years) + 5)
        data = yf.download(symbols, start=start.isoformat(), interval="1d", auto_adjust=True, group_by="ticker",
                           threads=True, progress=False)
        out = {}
        for s in symbols:
            try:
                d = _ticker_frame(data, s)
            except KeyError:
                continue
            d = d.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
            if len(d) < 30:
                continue
            idx = d.index.tz_localize(None) if getattr(d.index, "tz", None) else d.index
            d.index = pd.DatetimeIndex(idx.normalize(), name="date")
            out[s] = d
        return out

    def fundamentals(self, symbol: str) -> dict:
        fh = _finnhub()
        if fh is not None:
            meta = SYMBOLS.get(symbol.upper(), {})
            try:
                return fh.fundamentals(symbol.upper(), meta.get("name", ""), meta.get("sector", ""))
            except Exception:
                pass  # fall back to Yahoo below
        return self._yahoo_fundamentals(symbol)

    def _yahoo_fundamentals(self, symbol: str) -> dict:
        import yfinance as yf

        # Live mode never falls back to the approximate demo reference values: missing data stays missing.
        meta = SYMBOLS.get(symbol.upper(), {})
        base = {"name": meta.get("name", symbol.upper()), "sector": meta.get("sector", "Other"),
                "market_cap_b": None, "pe": None, "dividend_yield": None, "eps_growth": None, "beta": None}
        t = yf.Ticker(symbol)
        try:
            info = t.info or {}
        except Exception:
            info = {}
        if not info.get("marketCap") and not info.get("trailingPE"):
            # Yahoo often refuses its quoteSummary endpoint from cloud servers ("Invalid Crumb").
            # Fall back to data served by the chart endpoint, which keeps working.
            return {**base, **self._fallback_fundamentals(t, symbol)}
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

        hist = self.history(symbol)
        co = yfinance_company(symbol, hist, self.dividends(symbol))
        fh = _finnhub()
        if fh is not None:
            co = fh.enrich_company(co)
        # still missing (Yahoo's profile blocked, foreign company): from the US price history itself
        st = co.setdefault("stats", {})
        from .universe import usd_cap_check

        if st.get("market_cap_b") is not None or SYMBOLS.get(symbol.upper(), {}).get("cap_usd_b"):
            st["market_cap_b"] = usd_cap_check(symbol, st.get("market_cap_b"))
        if len(hist):
            last = hist.iloc[-252:]
            st["week52_high"] = st.get("week52_high") or round(float(last["high"].max()), 2)
            st["week52_low"] = st.get("week52_low") or round(float(last["low"].min()), 2)
            st["avg_volume"] = st.get("avg_volume") or int(hist["volume"].iloc[-50:].mean())
        return co

    def earnings(self, symbol: str) -> dict:
        fh = _finnhub()
        if fh is not None:
            try:
                return fh.earnings(symbol.upper())
            except Exception:
                pass
        return self._yahoo_earnings(symbol)

    def quarterly_revenue(self, symbol: str) -> list[dict]:
        import yfinance as yf

        try:
            st = yf.Ticker(symbol).quarterly_income_stmt
            row = st.loc["Total Revenue"].dropna()
        except Exception:
            return []
        return [{"date": pd.Timestamp(d).strftime("%Y-%m-%d"), "revenue": float(v)} for d, v in sorted(row.items(), reverse=True)]

    def _yahoo_earnings(self, symbol: str) -> dict:
        import yfinance as yf

        out = {"next_date": None, "next_eps_estimate": None, "history": []}
        try:
            ed = yf.Ticker(symbol).earnings_dates
        except Exception:
            return out
        if ed is None or ed.empty:
            return out
        ed = ed.copy()
        ed.index = ed.index.tz_localize(None) if ed.index.tz else ed.index
        now = pd.Timestamp.now()
        future = ed[ed.index > now].sort_index()
        if len(future):
            out["next_date"] = future.index[0].strftime("%Y-%m-%d")
            est = future["EPS Estimate"].iloc[0]
            out["next_eps_estimate"] = None if pd.isna(est) else float(est)
        past = ed[(ed.index <= now) & ed["Reported EPS"].notna()].sort_index(ascending=False).head(8)
        num = lambda v: None if pd.isna(v) else float(v)
        out["history"] = [{"date": i.strftime("%Y-%m-%d"), "eps_estimate": num(r.get("EPS Estimate")), "eps_actual": num(r.get("Reported EPS")),
                           "surprise_pct": num(r.get("Surprise(%)"))} for i, r in past.iterrows()]
        return out

    def intraday(self, symbol: str, interval: str) -> pd.DataFrame:
        """Intraday bars including pre-market (4:00) and after-hours (to 20:00), in New York time."""
        import yfinance as yf
        from zoneinfo import ZoneInfo

        period = {"5m": "5d", "15m": "1mo", "1h": "3mo"}[interval]
        df = yf.Ticker(symbol).history(period=period, interval=interval, prepost=True, auto_adjust=True)
        if df.empty:
            raise LookupError(f"No intraday data for {symbol}")
        idx = df.index.tz_convert(ZoneInfo("America/New_York")) if df.index.tz else df.index
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        df.index = pd.DatetimeIndex(idx.tz_localize(None) if getattr(idx, "tz", None) else idx, name="date")
        df["session"] = [session_of(t) for t in df.index]
        return df.dropna(subset=["close"])

    def live_bars(self, symbols: list[str]) -> dict[str, dict]:
        """Today's regular-session bar built from 1-minute data, for many symbols in one request."""
        import yfinance as yf
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        data = yf.download(symbols, period="1d", interval="1m", prepost=False, group_by="ticker", auto_adjust=True,
                           threads=True, progress=False)
        out = {}
        for s in symbols:
            try:
                d = _ticker_frame(data, s).dropna(subset=["Close"])
            except KeyError:
                continue
            if d.empty:
                continue
            idx = d.index.tz_convert(et) if d.index.tz else d.index.tz_localize("UTC").tz_convert(et)
            d = d.set_axis(idx)
            day = d[d.index.date == idx[-1].date()]
            out[s] = {"date": idx[-1].strftime("%Y-%m-%d"), "open": float(day["Open"].iloc[0]), "high": float(day["High"].max()),
                      "low": float(day["Low"].min()), "close": float(day["Close"].iloc[-1]), "volume": float(day["Volume"].sum()),
                      "time": idx[-1].strftime("%H:%M ET")}
        return out

    def extended_hours(self, symbols: list[str]) -> list[dict]:
        """Latest pre-market or after-hours price vs. the relevant regular-session close (one batched download)."""
        import yfinance as yf
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        data = yf.download(symbols, period="5d", interval="5m", prepost=True, group_by="ticker", progress=False, auto_adjust=False, threads=True)
        out = []
        for s in symbols:
            try:
                d = _ticker_frame(data, s).dropna(subset=["Close"])
            except KeyError:
                continue
            if d.empty:
                continue
            idx = d.index.tz_convert(et) if d.index.tz else d.index.tz_localize("UTC").tz_convert(et)
            d = d.set_axis(idx)
            minutes = idx.hour * 60 + idx.minute
            regular = d[(minutes >= 570) & (minutes < 960)]
            if regular.empty:
                continue
            last_ts = idx[-1]
            last_min = last_ts.hour * 60 + last_ts.minute
            if last_min >= 960:  # after hours: vs. today's regular close
                session, ref = "after_hours", float(regular[regular.index.date == last_ts.date()]["Close"].iloc[-1]) if (regular.index.date == last_ts.date()).any() else float(regular["Close"].iloc[-1])
            elif last_min < 570:  # pre-market: vs. the previous regular close
                session, ref = "pre_market", float(regular[regular.index.date < last_ts.date()]["Close"].iloc[-1])
            else:
                continue  # regular session: nothing extended to show
            price = float(d["Close"].iloc[-1])
            ext = d[d.index.date == last_ts.date()]
            ext = ext[(ext.index.hour * 60 + ext.index.minute) >= 960] if session == "after_hours" else ext[(ext.index.hour * 60 + ext.index.minute) < 570]
            out.append({"symbol": s, "session": session, "price": round(price, 2), "reference_close": round(ref, 2),
                        "change": round(price - ref, 2), "change_pct": round((price / ref - 1) * 100, 2),
                        "volume": int(ext["Volume"].sum()) if len(ext) else 0, "time": last_ts.strftime("%Y-%m-%d %H:%M ET")})
        return out

    def _fallback_fundamentals(self, t, symbol: str) -> dict:
        out: dict = {}
        try:
            fi = t.fast_info
            cap = fi.get("marketCap") if hasattr(fi, "get") else getattr(fi, "market_cap", None)
            if cap:
                out["market_cap_b"] = round(float(cap) / 1e9, 1)
        except Exception:
            pass
        try:
            close = float(self.history(symbol)["close"].iloc[-1])
            divs = self.dividends(symbol)
            last_year = divs[divs.index >= pd.Timestamp.now() - pd.Timedelta(days=365)]
            out["dividend_yield"] = round(float(last_year.sum()) / close * 100, 2) if close else None
        except Exception:
            pass
        out["partial"] = True  # P/E, growth and beta need the blocked endpoint
        return out

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
