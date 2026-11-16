"""Persistent market-data store for live providers (e.g. Yahoo Finance).

Why: fetching every chart, fundamental and earnings date from the provider on demand is slow and gets cloud servers
rate-limited. Instead:
  * prices for the whole universe are downloaded in batches and refreshed every few hours;
  * fundamentals and earnings are refreshed slowly in the background (one symbol at a time, with pauses);
  * everything is saved in the database, so a restart (Render free instances restart often) starts warm.
Request handlers read from memory; a symbol that is not in the store yet is fetched once and then stored.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

import pandas as pd

from .config import settings

log = logging.getLogger("sepa.store")

PRICE_TTL = timedelta(hours=24)  # full history re-download (splits/dividend adjustments); live bars update in between
HOT_INTERVAL = 60  # seconds: symbols people are looking at
FULL_INTERVAL = 15 * 60  # seconds: the whole universe
HOT_WINDOW = timedelta(minutes=30)
SLOW_TTL = timedelta(hours=24)
UNIVERSE_TTL = timedelta(days=7)
CHUNK = 100
SLOW_PAUSE = 1.2  # seconds between per-symbol requests, to stay polite with the provider
BREAKER_FAILURES = 5  # consecutive refusals before backing off
BREAKER_PAUSE = timedelta(hours=6)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pack(obj) -> bytes:
    return gzip.compress(json.dumps(obj, default=str).encode())


def _unpack(b: bytes):
    return json.loads(gzip.decompress(b).decode())


def df_to_obj(df: pd.DataFrame) -> dict:
    return json.loads(df.to_json(orient="split", date_format="iso"))


def obj_to_df(obj: dict) -> pd.DataFrame:
    df = pd.read_json(io.StringIO(json.dumps(obj)), orient="split")
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index).tz_localize(None).normalize(), name="date")
    return df[["open", "high", "low", "close", "volume"]].astype(float)


class DataStore:
    def __init__(self, provider_factory: Callable, session_factory: Callable):
        self._provider_factory = provider_factory
        self._session_factory = session_factory
        self._lock = threading.RLock()
        self.prices: dict[str, pd.DataFrame] = {}
        self.slow: dict[str, dict[str, dict]] = {"fundamentals": {}, "earnings": {}}
        self.updated: dict[str, datetime] = {}
        self.status = {"state": "idle", "message": "", "prices_refreshed_at": None, "slow_done": 0, "slow_total": 0}
        self._listeners: list[Callable[[], None]] = []
        self.hot: dict[str, datetime] = {}
        self.slow_paused_until: datetime | None = None
        self.directory: dict[str, dict] = {}
        self.live_at: dict[str, str] = {}
        self._thread: threading.Thread | None = None

    # ---------------------------------------------------------------- persistence
    def _save(self, key: str, obj) -> None:
        from .models import MarketCache

        with self._session_factory() as db:
            row = db.get(MarketCache, key)
            if row is None:
                row = MarketCache(key=key, payload=b"")
                db.add(row)
            row.payload = _pack(obj)
            row.updated_at = _now()
            db.commit()

    def load_all(self) -> int:
        """Load everything saved in the database into memory."""
        from sqlalchemy import select

        from .models import MarketCache

        n = 0
        with self._session_factory() as db:
            for row in db.scalars(select(MarketCache)):
                kind, _, sym = row.key.partition(":")
                try:
                    obj = _unpack(row.payload)
                except Exception:
                    continue
                ts = row.updated_at if row.updated_at.tzinfo else row.updated_at.replace(tzinfo=timezone.utc)
                with self._lock:
                    if kind == "prices":
                        self.prices[sym] = obj_to_df(obj)
                    elif kind in self.slow:
                        self.slow[kind][sym] = obj
                    elif kind == "directory":
                        self.directory = obj
                    elif kind == "universe":
                        from engine.data.universe import extend

                        extend(obj)
                    self.updated[row.key] = ts
                n += 1
        if self.prices:
            self.status["prices_refreshed_at"] = max((v for k, v in self.updated.items() if k.startswith("prices:")), default=None)
        return n

    # ---------------------------------------------------------------- reads / writes
    def get_prices(self, symbol: str) -> pd.DataFrame | None:
        with self._lock:
            return self.prices.get(symbol)

    def put_prices(self, symbol: str, df: pd.DataFrame, persist: bool = True) -> None:
        with self._lock:
            self.prices[symbol] = df
            self.updated[f"prices:{symbol}"] = _now()
        if persist:
            self._save(f"prices:{symbol}", df_to_obj(df))

    def get_slow(self, kind: str, symbol: str) -> dict | None:
        with self._lock:
            return self.slow[kind].get(symbol)

    def put_slow(self, kind: str, symbol: str, value: dict) -> None:
        with self._lock:
            self.slow[kind][symbol] = value
            self.updated[f"{kind}:{symbol}"] = _now()
        self._save(f"{kind}:{symbol}", value)

    def stale(self, key: str, ttl: timedelta) -> bool:
        ts = self.updated.get(key)
        return ts is None or _now() - ts > ttl

    def touch(self, symbol: str) -> None:
        """Mark a symbol as being viewed, so its price refreshes every minute."""
        self.hot[symbol] = _now()

    def hot_symbols(self) -> list[str]:
        cutoff = _now() - HOT_WINDOW
        return [s for s, t in list(self.hot.items()) if t >= cutoff]

    def merge_bar(self, symbol: str, bar: dict) -> None:
        """Replace (or append) today's row in the stored daily history with the running live bar."""
        with self._lock:
            df = self.prices.get(symbol)
            if df is None:
                return
            day = pd.Timestamp(bar["date"])
            if day < df.index[-1]:
                return
            row = pd.DataFrame([{k: bar[k] for k in ("open", "high", "low", "close", "volume")}], index=pd.DatetimeIndex([day], name="date"))
            self.prices[symbol] = pd.concat([df[df.index < day], row])
            self.live_at[symbol] = f"{bar['date']} {bar.get('time', '')}".strip()

    def refresh_quotes(self, symbols: list[str], limit: int = 25) -> int:
        """Real-time last price for the symbols people are looking at, from Finnhub quotes (Yahoo throttles cloud servers).
        Today's volume is kept from the last Yahoo update (quotes have no volume)."""
        from zoneinfo import ZoneInfo

        from engine.data.providers import _finnhub

        fh = _finnhub()
        if fh is None:
            return 0
        et = ZoneInfo("America/New_York")
        n = 0
        for s in symbols[:limit]:
            try:
                q = fh.quote(s)
            except Exception as e:
                self.status["live_error"] = f"Finnhub quote: {type(e).__name__}"
                continue
            if not q or not q.get("c") or not q.get("t"):
                continue
            ts = datetime.fromtimestamp(int(q["t"]), tz=timezone.utc).astimezone(et)
            df = self.get_prices(s)
            vol = float(df["volume"].iloc[-1]) if df is not None and len(df) and df.index[-1].date() == ts.date() else 0.0
            self.merge_bar(s, {"date": ts.strftime("%Y-%m-%d"), "open": float(q.get("o") or q["c"]), "high": float(q.get("h") or q["c"]),
                               "low": float(q.get("l") or q["c"]), "close": float(q["c"]), "volume": vol, "time": ts.strftime("%H:%M ET")})
            n += 1
        if n:
            self.status.update(live_source="finnhub", live_error=None)
        return n

    def refresh_live(self, symbols: list[str], persist: bool = False) -> int:
        provider = self._provider_factory()
        n = 0
        for i in range(0, len(symbols), CHUNK):
            chunk = symbols[i : i + CHUNK]
            try:
                bars = provider.live_bars(chunk)
            except Exception as e:
                log.warning("Live price update failed", exc_info=True)
                self.status["live_error"] = f"Yahoo: {type(e).__name__}"
                continue
            for s, bar in bars.items():
                self.merge_bar(s, bar)
                if persist:
                    df = self.get_prices(s)
                    if df is not None:
                        self._save(f"prices:{s}", df_to_obj(df))
                n += 1
        return n

    def on_prices_refreshed(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    # ---------------------------------------------------------------- refresh jobs
    def refresh_universe(self) -> int:
        """Load the S&P 500 list (weekly) and add it to the universe."""
        if settings.universe not in ("sp500", "sp500+") or not self.stale("universe:sp500", UNIVERSE_TTL):
            return 0
        import httpx

        from engine.data.universe import SP500_CSV, extend, parse_constituents

        try:
            r = httpx.get(SP500_CSV, timeout=20, follow_redirects=True)
            r.raise_for_status()
            entries = parse_constituents(r.text)
            if len(entries) < 400:
                raise ValueError("short list")
        except Exception:
            # Bundled copy, so the universe is complete even when GitHub can't be reached.
            from pathlib import Path

            log.warning("S&P 500 download failed; using the bundled list")
            entries = parse_constituents((Path(__file__).resolve().parent.parent / "engine" / "data" / "sp500_constituents.csv").read_text())
        if len(entries) < 400:  # sanity check: never shrink the universe because of a bad download
            raise ValueError(f"Unexpected constituents list ({len(entries)} rows)")
        if settings.universe == "sp500+":
            from engine.data.universe import NASDAQ100_EXTRA

            entries = {**NASDAQ100_EXTRA, **entries}
        added = extend(entries)
        self._save("universe:sp500", entries)
        self.updated["universe:sp500"] = _now()
        log.info("Universe: %d S&P 500 symbols (%d new)", len(entries), added)
        return added

    def refresh_directory(self) -> int:
        """All US-listed stocks and ETFs (Nasdaq Trader symbol files), refreshed weekly. Powers the search."""
        if self.directory and not self.stale("directory:us", UNIVERSE_TTL):
            return 0
        import httpx

        from engine.data.directory import NASDAQ_URL, OTHER_URL, parse

        texts = [httpx.get(u, timeout=30, follow_redirects=True) for u in (NASDAQ_URL, OTHER_URL)]
        for r in texts:
            r.raise_for_status()
        directory = parse(texts[0].text, texts[1].text)
        if len(directory) < 3000:  # sanity check against a truncated download
            raise ValueError(f"Unexpected symbol directory ({len(directory)} rows)")
        with self._lock:
            self.directory = directory
        self._save("directory:us", directory)
        self.updated["directory:us"] = _now()
        log.info("Symbol directory: %d US stocks and ETFs", len(directory))
        return len(directory)

    def refresh_prices(self, symbols: list[str], force: bool = False) -> int:
        todo = [s for s in symbols if force or self.stale(f"prices:{s}", PRICE_TTL)]
        provider = self._provider_factory()
        done = 0
        for i in range(0, len(todo), CHUNK):
            chunk = todo[i : i + CHUNK]
            self.status["message"] = f"Downloading prices {i + 1}–{i + len(chunk)} of {len(todo)}"
            try:
                got = provider.bulk_history(chunk)
            except Exception:
                log.exception("Bulk price download failed")
                continue
            for s, df in got.items():
                self.put_prices(s, df)
                done += 1
        if done:
            self.status["prices_refreshed_at"] = _now()
            for fn in self._listeners:
                try:
                    fn()
                except Exception:
                    log.exception("Price-refresh listener failed")
        return done

    def refresh_slow(self, symbols: list[str], stop: threading.Event | None = None) -> int:
        """Fundamentals and earnings, one symbol at a time, only where missing or older than a day."""
        if self.slow_paused_until and _now() < self.slow_paused_until:
            return 0
        provider = self._provider_factory()
        from engine.data.providers import _finnhub

        if _finnhub() is not None:
            # Partial Yahoo fallbacks are replaced as soon as Finnhub is available.
            for sym, v in list(self.slow["fundamentals"].items()):
                if v.get("partial") or v.get("market_cap_b") is None or v.get("source") != "finnhub":
                    self.updated.pop(f"fundamentals:{sym}", None)
        todo = [s for s in symbols if self.stale(f"fundamentals:{s}", SLOW_TTL) or self.stale(f"earnings:{s}", SLOW_TTL)]
        self.status.update(slow_total=len(symbols), slow_done=len(symbols) - len(todo))
        n = 0
        failures = 0
        for s in todo:
            if stop is not None and stop.is_set():
                break
            for kind, fn in (("fundamentals", provider.fundamentals), ("earnings", provider.earnings)):
                if self.stale(f"{kind}:{s}", SLOW_TTL):
                    try:
                        value = fn(s)
                        empty = not value or (kind == "earnings" and not value.get("history") and not value.get("next_date"))
                        failures = failures + 1 if empty else 0
                        self.put_slow(kind, s, value)
                    except Exception:
                        failures += 1
                        log.debug("%s failed for %s", kind, s, exc_info=True)
                    time.sleep(SLOW_PAUSE)
                    if failures >= BREAKER_FAILURES:
                        # The provider is refusing us: back off so the server doesn't get blocked for prices too.
                        self.slow_paused_until = _now() + BREAKER_PAUSE
                        self.status["message"] = "The data provider is refusing fundamentals requests; paused for 6 hours (prices keep updating)"
                        log.warning("Fundamentals/earnings refused %d times in a row; pausing until %s", failures, self.slow_paused_until)
                        return n
            n += 1
            self.status["slow_done"] += 1
        return n

    # ---------------------------------------------------------------- background loop
    def start(self, symbols_fn: Callable[[], list[str]], stocks_fn: Callable[[], list[str]], interval: float = 3 * 3600) -> None:
        if self._thread is not None:
            return
        stop = threading.Event()

        def loop():
            try:
                self.status["state"] = "loading"
                self.load_all()
            except Exception:
                log.exception("Loading the market cache failed")
            while not stop.is_set():
                try:
                    self.status["state"] = "refreshing"
                    try:
                        self.refresh_universe()
                    except Exception:
                        log.warning("Universe refresh failed; using the existing list", exc_info=True)
                    try:
                        self.refresh_directory()
                    except Exception:
                        log.warning("Symbol directory refresh failed; search uses the existing list", exc_info=True)
                    self.refresh_prices(symbols_fn())
                    self.status["message"] = "Updating fundamentals and earnings"
                    self.refresh_slow(stocks_fn(), stop)
                    self.status.update(state="ready", message="")
                except Exception:
                    log.exception("Market data refresh failed")
                    self.status.update(state="error", message="Last refresh failed; will retry")
                stop.wait(interval)

        def live_loop():
            last_full = 0.0
            while not stop.is_set():
                if market_session_open():
                    try:
                        hot = self.hot_symbols()
                        if hot:
                            # real-time quotes first (Finnhub); Yahoo 1-minute bars for whatever is left
                            done = self.refresh_quotes(hot)
                            rest = hot if done == 0 else hot[25:]
                            if rest:
                                self.refresh_live(rest)
                        if time.monotonic() - last_full >= FULL_INTERVAL:
                            self.refresh_live(symbols_fn(), persist=True)
                            last_full = time.monotonic()
                            for fn in self._listeners:
                                fn()
                        self.status["live_updated_at"] = _now()
                    except Exception:
                        log.exception("Live update failed")
                stop.wait(HOT_INTERVAL)

        self._thread = threading.Thread(target=loop, name="market-data-refresh", daemon=True)
        self._thread.start()
        self._live_thread = threading.Thread(target=live_loop, name="market-data-live", daemon=True)
        self._live_thread.start()
        self._stop = stop


def market_session_open(now: datetime | None = None) -> bool:
    """US trading day between 9:30 and 16:05 ET (a few minutes after the close to capture the final bar)."""
    from zoneinfo import ZoneInfo

    t = (now or _now()).astimezone(ZoneInfo("America/New_York"))
    minutes = t.hour * 60 + t.minute
    return t.weekday() < 5 and 570 <= minutes <= 965


_store: DataStore | None = None


def enabled() -> bool:
    return settings.data_provider != "synthetic" and settings.data_refresh


def get_store() -> DataStore | None:
    global _store
    if not enabled():
        return None
    if _store is None:
        from engine.data.providers import get_provider

        from .db import SessionLocal

        _store = DataStore(lambda: get_provider(settings.data_provider), SessionLocal)
    return _store
