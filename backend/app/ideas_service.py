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
            out[s] = market_data.history(s)
        except Exception:
            continue
    return out


def _scan() -> dict[str, dict]:
    from .routers.sepa import cached_scan

    return {r["symbol"]: r for r in cached_scan()}


def classify(symbol: str) -> tuple[str, str]:
    """(sector, industry) of a stock from the universe and the cached fundamentals; industry falls back to the sector."""
    f = market_data.cached("fundamentals", symbol) or {}
    sector = SYMBOLS.get(symbol, {}).get("sector") or f.get("sector") or ""
    return sector, f.get("industry") or sector


def industry_map(symbols: list[str]) -> dict[str, str]:
    return {s: classify(s)[1] for s in symbols}


def latest_batch(db: Session) -> date | None:
    return db.scalar(select(func.max(TradeIdea.batch_date)))


def run_ideas(db: Session, force: bool = False) -> list[TradeIdea]:
    """Generate the idea list for the latest completed trading day (once per day unless forced)."""
    hist = _histories()
    if not hist:
        return []
    day = max(df.index[-1] for df in hist.values()).date()
    if not force and latest_batch(db) == day:
        return []
    if force:
        from .models import AIPick

        ids = [i for (i,) in db.query(TradeIdea.id).filter(TradeIdea.batch_date == day).all()]
        if ids:
            db.query(AIPick).filter(AIPick.idea_id.in_(ids)).delete(synchronize_session=False)
        db.query(TradeIdea).filter(TradeIdea.batch_date == day).delete()
    ideas = generate(hist, _scan(), max_long=60, max_short=15, industry_of=industry_map(list(hist)))  # top 75 per day
    rows = []
    for i in ideas:
        row = TradeIdea(batch_date=day, **i.to_dict(), status="WAIT", current=i.entry)
        db.add(row)
        rows.append(row)
    db.commit()
    try:
        rows += _vnicorn(db, day, hist, rows)
    except Exception:
        log.exception("vnicornAI failed")
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

    rows = mt.mover_rows(hist, SYMBOLS)
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
    n = 0
    for it in items:
        try:
            with db.begin_nested():
                db.add(FeedItem(**{k: it.get(k) for k in ("key", "kind", "symbol", "severity", "title", "body", "url")}))
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
    rows = mt.mover_rows(hist, SYMBOLS)
    try:
        bench = market_data.history("SPY")
    except Exception:
        bench = None
    entries = {s: e for s in hist if (e := market_data.cached("earnings", s))}
    items = (feedmod.earnings_items(entries, hist, date.today()) + feedmod.mover_items(rows, scan, day.isoformat())
             + feedmod.breakout_items(hist, bench))
    from engine.data.providers import _finnhub

    n = add_feed(db, items)
    if settings.data_provider != "synthetic":
        try:
            n += refresh_news(db, _finnhub())
        except Exception:
            log.warning("News refresh failed", exc_info=True)
    return n


_news_cursor = 0


def refresh_news(db: Session, fh=None, fetch=None) -> int:
    """Headlines from publishers' RSS feeds and Finnhub (general, M&A, company news for a rotating set of stocks)."""
    global _news_cursor
    import httpx

    from engine import news

    def get(url: str) -> bytes:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; VnicornNews/1.0)"})
        r.raise_for_status()
        return r.content

    syms = stock_symbols()
    batch = syms[_news_cursor:_news_cursor + 20] if syms else []  # ~20 company-news calls per pass, within Finnhub's limit
    _news_cursor = (_news_cursor + 20) % max(len(syms), 1)
    raw = news.collect(fetch or get, fh, batch)
    names = news.name_index({s: SYMBOLS.get(s, {}) for s in syms})
    return add_feed(db, news.to_feed_items(raw, set(syms), names))


def due_for_ideas(db: Session, now: datetime | None = None) -> bool:
    """After 16:15 New York time on a weekday, if today's batch is missing; always when there are no ideas yet."""
    last = latest_batch(db)
    if last is None:
        return True
    t = (now or datetime.now(timezone.utc)).astimezone(ET)
    return t.weekday() < 5 and t.hour * 60 + t.minute >= 16 * 60 + 15 and last < t.date()


def tick(db: Session) -> None:
    """One pass of the background job (every 10 minutes)."""
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
