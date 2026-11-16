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
from .models import FeedItem, TradeIdea

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
        db.query(TradeIdea).filter(TradeIdea.batch_date == day).delete()
    ideas = generate(hist, _scan())
    rows = []
    for i in ideas:
        row = TradeIdea(batch_date=day, **i.to_dict(), status="WAIT", current=i.entry)
        db.add(row)
        rows.append(row)
    db.commit()
    add_feed(db, feedmod.idea_items([i.to_dict() for i in ideas], day.isoformat()))
    log.info("Generated %d ideas for %s", len(rows), day)
    return rows


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

    fh = _finnhub() if settings.data_provider != "synthetic" else None
    if fh is not None:
        try:
            items += feedmod.news_items(fh.general_news())
        except Exception:
            log.warning("Finnhub news failed", exc_info=True)
    return add_feed(db, items)


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
        run_ideas(db)
    refresh_statuses(db)
    build_feed(db)
