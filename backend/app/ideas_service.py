"""Daily trade ideas and the market feed.

* Ideas are generated once per trading day, after the close (16:15 New York time), from the universe's daily
  history and the Move Detector scan. Open ideas are re-checked every few minutes (WAIT -> BUY -> TRIM ->
  TARGET / STOPPED / CANCEL), which builds a public track record.
* The feed collects earnings beats/misses, upcoming reports, big movers, breakouts, new highs, new ideas and
  critical news (Finnhub) and stores each event once.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from engine import feed as feedmod
from engine import market_tools as mt
from engine.data.universe import SYMBOLS, stock_symbols
from engine.ideas import generate, update_status

from . import market_data
from .config import settings
from .models import DailyDigest, FeedItem, TradeIdea, User, Watchlist, WatchlistItem

log = logging.getLogger("sepa.ideas")
ET = ZoneInfo("America/New_York")


def _histories() -> dict[str, pd.DataFrame]:
    out = {}
    for s in stock_symbols():
        try:
            out[s] = market_data.stored_history(s)
        except Exception:
            continue
    return out


def _scan(symbols: list[str] | None = None) -> dict[str, dict]:
    """The Move Detector scan (RS, Trend Template, Bull / Bear scores) by symbol. With `symbols`, it must cover them:
    a scan built for a smaller universe (or served stale) is rebuilt now, or new stocks would get default scores
    and never pass the idea rules."""
    from . import market_data
    from .routers import sepa

    rows = sepa.cached_scan()
    if symbols:
        have = {r["symbol"] for r in rows}
        if len(have & set(symbols)) < 0.9 * len(symbols):
            prev = market_data.in_background()
            market_data._tls.rebuilding = True  # compute it here instead of returning the previous scan
            try:
                sepa.invalidate_scan()
                rows = sepa.cached_scan()
            finally:
                market_data._tls.rebuilding = prev
    return {r["symbol"]: r for r in rows}


def classify(symbol: str) -> tuple[str, str]:
    """(sector, industry) of a stock from the universe and the cached fundamentals; industry falls back to the sector."""
    f = market_data.cached("fundamentals", symbol) or {}
    sector = SYMBOLS.get(symbol, {}).get("sector") or f.get("sector") or ""
    return sector, f.get("industry") or SYMBOLS.get(symbol, {}).get("industry") or sector


def industry_map(symbols: list[str]) -> dict[str, str]:
    return {s: classify(s)[1] for s in symbols}


def latest_batch(db: Session) -> date | None:
    return db.scalar(select(func.max(TradeIdea.batch_date)))


def _completed_sessions(hist: dict[str, pd.DataFrame], now: datetime | None = None) -> dict[str, pd.DataFrame]:
    """Before 16:15 New York time, today's row is a running intraday bar: leave it out, so ideas are always built from
    a completed trading day (and the run after the close still happens)."""
    t = (now or datetime.now(timezone.utc)).astimezone(ET)
    if t.hour * 60 + t.minute >= 16 * 60 + 15:
        return hist
    today = pd.Timestamp(t.date())
    return {s: df[df.index < today] for s, df in hist.items() if len(df[df.index < today])}


def run_ideas(db: Session, force: bool = False) -> list[TradeIdea]:
    """Generate the idea list for the latest completed trading day (once per day unless forced).
    Forced: the day's ideas that are still waiting and that nobody took are replaced; triggered or taken ideas stay."""
    if not force:
        _final_close_bars()
    hist = _completed_sessions(_histories())
    if not hist:
        return []
    day = max(df.index[-1] for df in hist.values()).date()
    if not force and latest_batch(db) == day:
        return []
    kept: set[str] = set()
    if force:
        from .models import AIPick, PaperTrade

        taken = {i for (i,) in db.query(PaperTrade.idea_id).filter(PaperTrade.idea_id.isnot(None)).all()}
        day_rows = db.query(TradeIdea).filter(TradeIdea.batch_date == day).all()
        drop = [r.id for r in day_rows if r.status == "WAIT" and r.id not in taken]
        kept = {r.symbol for r in day_rows if r.id not in drop}
        if drop:
            db.query(AIPick).filter(AIPick.idea_id.in_(drop)).delete(synchronize_session=False)
            db.query(TradeIdea).filter(TradeIdea.id.in_(drop)).delete(synchronize_session="fetch")
        db.commit()
    scan = _scan([s for s, df in hist.items() if len(df) >= 260])  # the stocks long enough for the idea rules
    ideas = generate(hist, scan, max_long=None, max_short=None, industry_of=industry_map(list(hist)))  # every opportunity
    ideas = [i for i in ideas if i.symbol not in kept]
    rows = []
    for i in ideas:
        row = TradeIdea(batch_date=day, **i.to_dict(), status="WAIT", current=i.entry)
        db.add(row)
        rows.append(row)
    db.commit()
    try:
        rows += _vnicorn(db, day, hist, rows)
    except Exception as e:
        log.exception("vnicornAI failed")
        from . import vnicorn_service

        vnicorn_service.last_error = f"rating: {type(e).__name__}: {str(e)[:120]}"
        db.rollback()
    add_feed(db, feedmod.idea_items([i.to_dict() for i in ideas], day.isoformat()))
    log.info("Generated %d ideas for %s", len(rows), day)
    try:
        publish_summary(db, day, hist, [i.to_dict() for i in ideas])
    except Exception:
        log.exception("Daily summary failed")
    return rows


def _vnicorn(db: Session, day: date, hist: dict[str, pd.DataFrame], rows: list[TradeIdea]) -> list[TradeIdea]:
    """vnicornAI: rate the ideas, add its own, refresh major-move probabilities (trains weekly, on demand)."""
    from engine.stages import stage_now

    from . import vnicorn_service

    try:
        bench = market_data.history("SPY")
    except Exception:
        bench = None
    stage_of = {}
    for s, df in hist.items():
        try:
            st = stage_now(df)
            stage_of[s] = st["stage"] if st else 0
        except Exception:
            continue
    return vnicorn_service.rate_and_create(db, day, hist, bench, rows, stage_of)


def _next_trading_day(day: date) -> date:
    nxt = pd.Timestamp(day) + pd.offsets.BDay(1)
    return nxt.date()


def publish_summary(db: Session, day: date, hist: dict[str, pd.DataFrame], ideas: list[dict]) -> dict | None:
    """End-of-day recap in the feed (once per day), then emailed to users who opted in."""
    from engine.stages import stage_now

    from .routers.markets import _fear_greed, _indices

    from .routers.markets import _rows

    rows = _rows()  # the shared, cached movers table (not recomputed for every pass)
    cycle = []
    for sym, label in (("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("IWM", "Russell 2000")):
        try:
            st = stage_now(market_data.history(sym))
            if st:
                cycle.append({"label": label, **st})
        except Exception:
            continue
    nxt = _next_trading_day(day).isoformat()
    earn = [{"symbol": s} for s in hist if (e := market_data.cached("earnings", s)) and e.get("next_date") == nxt]
    try:
        fg = _fear_greed()
    except Exception:
        fg = {}
    try:
        from .routers.sepa import cached_scan, pulse_map

        scan, pm = cached_scan(), pulse_map()
    except Exception:
        scan, pm = [], {}
    try:
        from .routers.markets import _exposure

        ex = _exposure()
    except Exception:
        ex = None
    item = feedmod.daily_summary(day.isoformat(), _indices(), cycle, fg, rows, ideas, earn, scan, pm, ex)
    if not add_feed(db, [item]):
        return None  # already published today
    send_digests(db, day, item, {r["symbol"]: r for r in rows})
    return item


def send_digests(db: Session, day: date, item: dict, by_symbol: dict[str, dict]) -> int:
    from .notify import email_configured, send_email

    if not email_configured():
        return 0
    n = 0
    for sub, user in db.execute(select(DailyDigest, User).join(User, User.id == DailyDigest.user_id).where(DailyDigest.enabled.is_(True))).all():
        if sub.last_sent == day:
            continue
        syms = db.scalars(select(WatchlistItem.symbol).join(Watchlist, Watchlist.id == WatchlistItem.watchlist_id)
                          .where(Watchlist.user_id == user.id)).all()
        watch = [by_symbol[s] for s in dict.fromkeys(syms) if s in by_symbol][:15]
        from .plans import limits_for

        if send_email(user.email, f"[Vnicorn] {item['title']}", feedmod.summary_text(item, watch, limits_for(user))):
            sub.last_sent = day
            n += 1
    db.commit()
    return n


def refresh_statuses(db: Session) -> int:
    rows = db.scalars(select(TradeIdea).where(TradeIdea.status.in_(["WAIT", "BUY", "TRIM"]))).all()
    n = 0
    for r in rows:
        try:
            df = market_data.history(r.symbol)
        except Exception:
            continue
        st = update_status({"entry": r.entry, "stop": r.stop, "trim": r.trim, "target": r.target, "side": r.side}, df, pd.Timestamp(r.batch_date))
        r.status, r.current, r.pnl_pct, r.r_multiple = st["status"], st["current"], st["pnl_pct"], st["r_multiple"]
        r.closed_at = pd.Timestamp(st["closed_at"]).date() if st["closed_at"] else None
        n += 1
    db.commit()
    return n


def add_feed(db: Session, items: list[dict]) -> int:
    """Store new feed items: one query finds the keys already stored, the rest are inserted together."""
    if not items:
        return 0
    keys = list(dict.fromkeys(it["key"] for it in items))
    have: set[str] = set()
    for i in range(0, len(keys), 500):
        have |= set(db.scalars(select(FeedItem.key).where(FeedItem.key.in_(keys[i:i + 500]))).all())
    fresh, seen = [], set(have)
    for it in items:
        if it["key"] in seen:
            continue
        seen.add(it["key"])
        fresh.append(FeedItem(**{k: it.get(k) for k in ("key", "kind", "symbol", "severity", "title", "body", "url")}))
    if not fresh:
        return 0
    db.add_all(fresh)
    try:
        db.commit()
        return len(fresh)
    except IntegrityError:  # another writer stored some of them meanwhile: fall back to one by one
        db.rollback()
        n = 0
        for row in fresh:
            try:
                with db.begin_nested():
                    db.add(FeedItem(**{c: getattr(row, c) for c in ("key", "kind", "symbol", "severity", "title", "body", "url")}))
                n += 1
            except IntegrityError:
                continue
        db.commit()
        return n


def build_feed(db: Session) -> int:
    hist = _histories()
    if not hist:
        return 0
    day = max(df.index[-1] for df in hist.values()).date()
    scan = _scan()
    from .routers.markets import _rows

    rows = _rows()  # the shared, cached movers table (not recomputed for every pass)
    try:
        bench = market_data.history("SPY")
    except Exception:
        bench = None
    entries = {s: e for s in hist if (e := market_data.cached("earnings", s))}
    items = (feedmod.earnings_items(entries, hist, date.today()) + feedmod.mover_items(rows, scan, day.isoformat())
             + feedmod.breakout_items(hist, bench))
    from engine.data.providers import _finnhub

    n = add_feed(db, items)
    if settings.data_provider != "synthetic" and _news_due(db):
        try:
            n += refresh_news(db, _finnhub())
        except Exception:
            log.warning("News refresh failed", exc_info=True)
    return n


_news_cursor = 0
_news_last = 0.0  # monotonic time of the last news pass
_names_cache: tuple[int, list] | None = None


def _news_due(db: Session) -> bool:
    import time

    from .app_settings import news_config

    _, cfg = news_config(db)
    if not cfg["per_pass"]:
        purge_news(db, cfg["keep_days"])
        return False
    return time.monotonic() - _news_last >= cfg["every_min"] * 60 - 30


def purge_news(db: Session, keep_days: int) -> int:
    """Headlines older than `keep_days` are deleted (other feed items stay: they form the history)."""
    from datetime import timedelta

    cut = datetime.now(timezone.utc) - timedelta(days=keep_days)
    n = db.query(FeedItem).filter(FeedItem.kind == "news", FeedItem.created_at < cut).delete(synchronize_session=False)
    db.commit()
    return n


def _name_index(syms: list[str]) -> list:
    """Company-name patterns for tagging headlines, compiled once per universe (not on every pass)."""
    global _names_cache
    from engine import news

    key = hash(tuple(syms))
    if _names_cache is None or _names_cache[0] != key:
        _names_cache = (key, news.name_index({s: SYMBOLS.get(s, {}) for s in syms}))
    return _names_cache[1]


def refresh_news(db: Session, fh=None, fetch=None) -> int:
    """Headlines from publishers' RSS feeds and Finnhub, as much as the admin's News setting allows."""
    global _news_cursor, _news_last
    import time

    import httpx

    from engine import news

    from .app_settings import news_config

    _, cfg = news_config(db)
    _news_last = time.monotonic()
    purge_news(db, cfg["keep_days"])
    if not cfg["per_pass"]:
        return 0

    def get(url: str) -> bytes:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; VnicornNews/1.0)"})
        r.raise_for_status()
        return r.content

    syms = stock_symbols()
    k = cfg["company"]
    batch = syms[_news_cursor:_news_cursor + k] if syms and k else []  # company news for a rotating set of stocks
    if k:
        _news_cursor = (_news_cursor + k) % max(len(syms), 1)
    raw = news.collect(fetch or get, fh if cfg["finnhub"] or batch else None, batch, finnhub_general=cfg["finnhub"])
    keys = news.keys_of(raw)
    have: set[str] = set()
    for i in range(0, len(keys), 500):
        have |= set(db.scalars(select(FeedItem.key).where(FeedItem.key.in_(keys[i:i + 500]))).all())
    items = news.to_feed_items(raw, set(syms), _name_index(syms), skip_keys=have, limit=cfg["per_pass"])
    return add_feed(db, items)


def _data_ready() -> bool:
    """Ideas need the whole universe: not while saved prices are still loading, and only with prices for 90 % of it."""
    from .data_store import get_store

    store = get_store()
    if store is None:
        return True
    if store.status.get("state") == "loading":
        return False
    syms = stock_symbols()
    return not syms or sum(1 for s in syms if s in store.prices) >= 0.9 * len(syms)


def last_completed_session(now: datetime | None = None) -> date | None:
    """The latest trading day whose close is in the stored prices (today only after 16:15 New York). The median over
    the universe, so a few symbols with a running bar don't decide it."""
    from .data_store import get_store

    store = get_store()
    t = (now or datetime.now(timezone.utc)).astimezone(ET)
    today = t.date()
    after_close = t.hour * 60 + t.minute >= 16 * 60 + 15
    if store is not None:
        frames = [store.prices[s] for s in stock_symbols() if s in store.prices]
    else:
        frames = list(_histories().values())
    days = []
    for df in frames:
        idx = df.index
        if not len(idx):
            continue
        last = idx[-1].date()
        if last >= today and not after_close:
            last = idx[-2].date() if len(idx) > 1 else None
        if last:
            days.append(last)
    if not days:
        return None
    days.sort()
    return days[len(days) // 2]


def earnings_dates(symbols: list[str]) -> dict[str, date | None]:
    """Next earnings date per symbol, from the stored earnings calendar."""
    out: dict[str, date | None] = {}
    for s in symbols:
        nd = (market_data.cached("earnings", s) or {}).get("next_date")
        try:
            out[s] = date.fromisoformat(str(nd)[:10]) if nd else None
        except ValueError:
            out[s] = None
    return out


def extended_quotes(symbols: list[str]) -> dict[str, dict]:
    """Pre-market / after-hours quotes by symbol, outside the regular session only (cached 5 minutes)."""
    from .data_store import market_session_open

    if not symbols or market_session_open():
        return {}
    try:
        return {r["symbol"]: r for r in market_data.extended_hours(sorted(set(symbols)))}
    except Exception:
        log.debug("Extended-hours quotes failed", exc_info=True)
        return {}


def market_events(extra_symbols: list[str] | None = None, now: datetime | None = None) -> tuple[dict[str, dict], list[dict]]:
    """(extended quotes, high-impact events) for Signals: mega-cap reports and Fed decisions due, big moves after hours."""
    from engine import events as ev
    from engine.data.fed import FOMC_MEETINGS

    today = (now or datetime.now(timezone.utc)).astimezone(ET).date()
    ext = extended_quotes(list(extra_symbols or []) + ev.MEGA_CAPS + ev.INDEXES)
    return ext, ev.high_impact(today, earnings_dates(ev.MEGA_CAPS), FOMC_MEETINGS, ext)


EVENT_DELAY_MINUTES = 17 * 60  # on a mega-cap report day the batch waits until 5:00 PM New York, after the report


def due_for_ideas(db: Session, now: datetime | None = None) -> bool:
    """When the stored prices hold a completed trading day newer than the last batch. Driven by the data, not the clock,
    so a server that slept through the close (Render's free plan) catches up at the next wake-up, weekends included."""
    if not _data_ready():
        return False
    last = latest_batch(db)
    if last is None:
        return True
    sess = last_completed_session(now)
    if sess is None or sess <= last:
        return False
    # a mega-cap (NVIDIA, Apple…) reports after today's close: publish after the report, with the gap flags ready
    from engine.events import reports_today

    t = (now or datetime.now(timezone.utc)).astimezone(ET)
    if sess == t.date() and t.hour * 60 + t.minute < EVENT_DELAY_MINUTES and reports_today(t.date(), earnings_dates(["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AVGO"])):
        return False
    return True


def _final_close_bars() -> None:
    """Before a batch: refresh the latest daily bar of every stock once, so ideas use the real closing prices and not
    the last intraday update (every 15 minutes until the close)."""
    from .data_store import get_store

    store = get_store()
    if store is None:
        return
    try:
        store.refresh_live(stock_symbols(), persist=True)
    except Exception:
        log.warning("Final close-bar refresh failed; using the stored prices", exc_info=True)


def tick(db: Session) -> None:
    """One pass of the background job (every 10 minutes). Skipped while an admin regeneration runs (memory)."""
    from . import regen_status

    if regen_status.running_here():
        return
    if due_for_ideas(db):
        run_ideas(db)  # also publishes the daily summary
    refresh_statuses(db)
    build_feed(db)
    try:
        publish_weekly_letter(db)
    except Exception:
        log.exception("Weekly letter failed")


def publish_weekly_letter(db: Session, today: date | None = None, force: bool = False) -> dict | None:
    """Saturday / Sunday: the week's letter (once per ISO week), then emailed to Premium readers who opted in."""
    import pandas as pd

    from engine.letter import letter_text, weekly_letter

    today = today or date.today()
    if today.weekday() < 5 and not force:
        return None
    y, w, _ = today.isocalendar()
    week = f"{y}-W{w:02d}"
    if db.scalar(select(FeedItem).where(FeedItem.key == f"letter:{week}")):
        return None
    from .routers.markets import _exposure, groups_ranked
    from .routers.sepa import cached_scan, pulse_map

    indices = []
    for sym, label in (("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("IWM", "Russell 2000")):
        try:
            c = market_data.history(sym)["close"]
            indices.append({"symbol": sym, "label": label, "week_pct": round(float(c.iloc[-1] / c.iloc[-6] - 1) * 100, 2)})
        except Exception:
            continue
    try:
        ex = _exposure()
    except Exception:
        ex = None
    try:
        groups = groups_ranked()
    except Exception:
        groups = []
    scan = cached_scan()
    leaders = [{"symbol": r["symbol"], "rs": r["rs_rating"], "bull": r.get("bull_score")} for r in
               sorted([r for r in scan if (r.get("rs_rating") or 0) >= 90 and r.get("template_passed") == 8], key=lambda r: -r["rs_rating"])]
    try:
        pm = pulse_map()
    except Exception:
        pm = {}
    warnings = sorted([{"symbol": s, "warn": p["warn"]} for s, p in pm.items() if p.get("warn", 0) > p.get("conf", 0) + 2], key=lambda x: -x["warn"])
    end = (pd.Timestamp(today) + pd.offsets.BDay(5)).date()
    earnings = []
    for s in stock_symbols():
        e = market_data.cached("earnings", s) or {}
        nd = e.get("next_date")
        if nd and today.isoformat() < nd <= end.isoformat():
            earnings.append({"symbol": s, "date": nd})
    earnings.sort(key=lambda e: e["date"])
    week_start = today - pd.Timedelta(days=today.weekday())
    closed = db.scalars(select(TradeIdea).where(TradeIdea.closed_at >= week_start, TradeIdea.r_multiple.is_not(None),
                                                TradeIdea.status.in_(("TARGET", "STOPPED")))).all()
    rs = [r.r_multiple for r in closed]
    record = {"closed": len(rs), "win_rate": round(100 * sum(r > 0 for r in rs) / len(rs)) if rs else None, "total_r": round(sum(rs), 1)}
    item = weekly_letter(week, indices, ex, groups, leaders, warnings, earnings, record)
    if not add_feed(db, [item]):
        return None
    from .notify import email_configured, send_email
    from .plans import limits_for

    if email_configured():
        for sub, user in db.execute(select(DailyDigest, User).join(User, User.id == DailyDigest.user_id).where(DailyDigest.enabled.is_(True))).all():
            if limits_for(user)["weekly_letter"]:
                send_email(user.email, f"[Vnicorn] {item['title']}", letter_text(item))
    return item
