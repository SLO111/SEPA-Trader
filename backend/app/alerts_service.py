"""Alert engine: evaluates every active rule against the latest market data, stores new alerts
(deduplicated) and dispatches notifications."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from engine.data.universe import stock_symbols
from engine.triggers import evaluate

from . import market_data, notify
from .models import Alert, AlertRule, NotificationSettings, User, Watchlist
from .plans import limits_for

log = logging.getLogger("sepa.alerts")

SEVERITY_ICON = {"bull": "🟢", "bear": "🔴", "info": "🔵"}


def rule_symbols(db: Session, rule: AlertRule) -> list[str]:
    if rule.scope == "symbol":
        return [rule.symbol] if rule.symbol else []
    if rule.scope == "watchlist":
        wl = db.get(Watchlist, rule.watchlist_id) if rule.watchlist_id else None
        return [i.symbol for i in wl.items] if wl and wl.user_id == rule.user_id else []
    return stock_symbols()


def _params(rule: AlertRule) -> dict:
    return {"price_level": rule.price_level, "bull_threshold": rule.bull_threshold, "bear_threshold": rule.bear_threshold}


def check_rules(db: Session, user_id: int | None = None, now: datetime | None = None) -> list[Alert]:
    """Run all active rules (optionally for one user). Returns the newly created alerts."""
    q = select(AlertRule).where(AlertRule.active.is_(True))
    if user_id is not None:
        q = q.where(AlertRule.user_id == user_id)
    rules = db.scalars(q).all()

    try:
        bench = market_data.history("SPY")
    except Exception:
        bench = None

    created: list[Alert] = []
    users: dict[int, User] = {}
    for rule in rules:
        user = users.get(rule.user_id) or db.get(User, rule.user_id)
        if user is None or not user.is_active or not limits_for(user)["alerts"]:
            continue
        users[user.id] = user
        events = [e for e in rule.events.split(",") if e]
        for symbol in rule_symbols(db, rule):
            try:
                df = market_data.history(symbol)
                found = evaluate(df, bench, events, _params(rule), now=now)
            except Exception:
                log.warning("Alert check failed for %s", symbol, exc_info=True)
                continue
            for ev in found:
                alert = Alert(
                    user_id=user.id,
                    rule_id=rule.id,
                    symbol=symbol,
                    type=ev.type,
                    severity=ev.severity,
                    title=ev.title,
                    message=ev.message,
                    data=json.dumps(ev.data),
                    bar_date=ev.bar_date,
                )
                try:
                    with db.begin_nested():
                        db.add(alert)
                except IntegrityError:
                    continue  # already alerted for this symbol/event/bar
                created.append(alert)
                dispatch(db, user, rule, alert)
    db.commit()
    return created


def format_text(alert: Alert, html: bool = False) -> str:
    icon = SEVERITY_ICON.get(alert.severity, "🔔")
    head = f"{icon} {alert.symbol}: {alert.title}"
    if html:
        head = f"{icon} <b>{alert.symbol}</b>: {alert.title}"
    return f"{head}\n{alert.message}\n\nSEPA Trader · Not financial advice."


def dispatch(db: Session, user: User, rule: AlertRule, alert: Alert) -> None:
    channels = set(rule.channels.split(","))
    prefs = db.get(NotificationSettings, user.id)
    if prefs is None:
        return
    if "email" in channels and prefs.email_enabled:
        notify.send_email(user.email, f"[SEPA Trader] {alert.symbol}: {alert.title}", format_text(alert))
    if "telegram" in channels and prefs.telegram_enabled and prefs.telegram_chat_id:
        notify.send_telegram(prefs.telegram_chat_id, format_text(alert, html=True))
