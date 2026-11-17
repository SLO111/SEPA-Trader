import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from engine.triggers import DEFAULT_EVENTS, EVENT_TYPES

from .. import notify
from ..alerts_service import check_rules, format_text
from ..db import get_db
from ..models import Alert, AlertRule, NotificationSettings, User, Watchlist
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api", tags=["alerts"])

UPGRADE_MSG = "Alerts are available on the Pro and Premium plans."


def _require_alerts(user: User) -> None:
    if not limits_for(user)["alerts"]:
        raise HTTPException(403, UPGRADE_MSG)


def alert_out(a: Alert) -> dict:
    return {
        "id": a.id,
        "rule_id": a.rule_id,
        "symbol": a.symbol,
        "type": a.type,
        "type_label": EVENT_TYPES.get(a.type, {}).get("label", a.type),
        "severity": a.severity,
        "title": a.title,
        "message": a.message,
        "data": json.loads(a.data or "{}"),
        "bar_date": a.bar_date,
        "read": a.read,
        "created_at": a.created_at.isoformat(),
    }


def rule_out(r: AlertRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "scope": r.scope,
        "symbol": r.symbol,
        "watchlist_id": r.watchlist_id,
        "events": [e for e in r.events.split(",") if e],
        "price_level": r.price_level,
        "bull_threshold": r.bull_threshold,
        "bear_threshold": r.bear_threshold,
        "channels": [c for c in r.channels.split(",") if c],
        "active": r.active,
        "auto": r.name.startswith("Auto · "),
        "created_at": r.created_at.isoformat(),
    }


# ---------------- event catalog ----------------

@router.get("/alerts/event-types")
def event_types(user: User = Depends(current_user)):
    return {
        "events": [{"id": k, **v} for k, v in EVENT_TYPES.items()],
        "defaults": DEFAULT_EVENTS,
        "channels": {"app": True, "email": notify.email_configured(), "telegram": notify.telegram_configured()},
    }


# ---------------- alerts feed ----------------

@router.get("/alerts")
def list_alerts(
    filter: Literal["all", "unread", "bull", "bear", "info"] = "all",
    limit: int = Query(100, ge=1, le=500),
    offset: int | None = Query(None, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Your alerts, newest first. With `offset`: one page {count, has_more, results} for loading 50 at a time."""
    q = select(Alert).where(Alert.user_id == user.id)
    if filter == "unread":
        q = q.where(Alert.read.is_(False))
    elif filter in ("bull", "bear", "info"):
        q = q.where(Alert.severity == filter)
    if offset is None:
        rows = db.scalars(q.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)).all()
        return [alert_out(a) for a in rows]
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Alert.created_at.desc(), Alert.id.desc()).offset(offset).limit(limit)).all()
    return {"count": total, "has_more": offset + len(rows) < total, "results": [alert_out(a) for a in rows]}


@router.get("/alerts/unread-count")
def unread_count(user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.scalar(select(func.count()).select_from(Alert).where(Alert.user_id == user.id, Alert.read.is_(False)))
    return {"count": n or 0}


@router.post("/alerts/read-all")
def read_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(update(Alert).where(Alert.user_id == user.id, Alert.read.is_(False)).values(read=True))
    db.commit()
    return {"ok": True}


def _owned_alert(db: Session, user: User, alert_id: int) -> Alert:
    a = db.get(Alert, alert_id)
    if a is None or a.user_id != user.id:
        raise HTTPException(404, "Alert not found")
    return a


@router.post("/alerts/{alert_id}/read")
def mark_read(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = _owned_alert(db, user, alert_id)
    a.read = True
    db.commit()
    return alert_out(a)


@router.delete("/alerts/{alert_id}", status_code=204)
def delete_alert(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_owned_alert(db, user, alert_id))
    db.commit()


@router.post("/alerts/check-now")
def check_now(user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_alerts(user)
    created = check_rules(db, user_id=user.id)
    return {"created": len(created), "alerts": [alert_out(a) for a in created]}


# ---------------- rules ----------------

class RuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scope: Literal["symbol", "watchlist", "universe"]
    symbol: str | None = Field(default=None, max_length=16, pattern=r"^[A-Za-z0-9.\-^=]+$")
    watchlist_id: int | None = None
    events: list[str] = Field(min_length=1, max_length=len(EVENT_TYPES))
    price_level: float | None = Field(default=None, gt=0)
    bull_threshold: float = Field(default=70, ge=1, le=100)
    bear_threshold: float = Field(default=70, ge=1, le=100)
    channels: list[Literal["app", "email", "telegram"]] = Field(default_factory=lambda: ["app"])
    active: bool = True

    @model_validator(mode="after")
    def _check(self):
        unknown = [e for e in self.events if e not in EVENT_TYPES]
        if unknown:
            raise ValueError(f"Unknown event types: {', '.join(unknown)}")
        if self.scope == "symbol" and not self.symbol:
            raise ValueError("A symbol is required for a symbol alert")
        if self.scope == "watchlist" and not self.watchlist_id:
            raise ValueError("Choose a watchlist")
        if {"price_above", "price_below"} & set(self.events) and not self.price_level:
            raise ValueError("Price alerts need a price level")
        if "app" not in self.channels:
            self.channels = ["app", *self.channels]
        return self


def _validate_rule(db: Session, user: User, body: RuleIn) -> None:
    limits = limits_for(user)
    if body.scope == "watchlist":
        wl = db.get(Watchlist, body.watchlist_id)
        if wl is None or wl.user_id != user.id:
            raise HTTPException(404, "Watchlist not found")
    if (body.scope == "universe" or {"bull_score", "bear_score"} & set(body.events)) and not limits["move_detector"]:
        raise HTTPException(403, "Market-wide and Move Detector alerts require the Pro or Premium plan.")


def _apply(rule: AlertRule, body: RuleIn) -> None:
    rule.name = body.name.strip()
    rule.scope = body.scope
    rule.symbol = body.symbol.upper() if body.scope == "symbol" and body.symbol else None
    rule.watchlist_id = body.watchlist_id if body.scope == "watchlist" else None
    rule.events = ",".join(dict.fromkeys(body.events))
    rule.price_level = body.price_level
    rule.bull_threshold = body.bull_threshold
    rule.bear_threshold = body.bear_threshold
    rule.channels = ",".join(dict.fromkeys(body.channels))
    rule.active = body.active


def _owned_rule(db: Session, user: User, rule_id: int) -> AlertRule:
    r = db.get(AlertRule, rule_id)
    if r is None or r.user_id != user.id:
        raise HTTPException(404, "Alert rule not found")
    return r


@router.get("/alert-rules")
def list_rules(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..alerts_service import ensure_watchlist_rules

    ensure_watchlist_rules(db, user)
    rows = db.scalars(select(AlertRule).where(AlertRule.user_id == user.id).order_by(AlertRule.created_at)).all()
    return [rule_out(r) for r in rows]


@router.post("/alert-rules")
def create_rule(body: RuleIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_alerts(user)
    limit = limits_for(user)["max_alert_rules"]
    count = db.scalar(select(func.count()).select_from(AlertRule).where(AlertRule.user_id == user.id, AlertRule.name.notlike("Auto · %"))) or 0
    if count >= limit:
        raise HTTPException(403, f"Your plan allows up to {limit} alert rules.")
    _validate_rule(db, user, body)
    rule = AlertRule(user_id=user.id)
    _apply(rule, body)
    db.add(rule)
    db.commit()
    return rule_out(rule)


@router.put("/alert-rules/{rule_id}")
def update_rule(rule_id: int, body: RuleIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _require_alerts(user)
    rule = _owned_rule(db, user, rule_id)
    _validate_rule(db, user, body)
    _apply(rule, body)
    db.commit()
    return rule_out(rule)


@router.delete("/alert-rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_owned_rule(db, user, rule_id))
    db.commit()


# ---------------- notification settings ----------------

class NotifyIn(BaseModel):
    email_enabled: bool = False
    telegram_enabled: bool = False
    telegram_chat_id: str = Field(default="", max_length=40, pattern=r"^-?[0-9]*$")


def _prefs(db: Session, user: User) -> NotificationSettings:
    p = db.get(NotificationSettings, user.id)
    if p is None:
        p = NotificationSettings(user_id=user.id, email_enabled=False, telegram_enabled=False, telegram_chat_id="")
        db.add(p)
        db.commit()
    return p


def prefs_out(p: NotificationSettings, user: User) -> dict:
    return {
        "email": user.email,
        "email_enabled": p.email_enabled,
        "telegram_enabled": p.telegram_enabled,
        "telegram_chat_id": p.telegram_chat_id,
        "email_available": notify.email_configured(),
        "telegram_available": notify.telegram_configured(),
    }


@router.get("/notifications/settings")
def get_settings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return prefs_out(_prefs(db, user), user)


@router.put("/notifications/settings")
def put_settings(body: NotifyIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _prefs(db, user)
    p.email_enabled, p.telegram_enabled, p.telegram_chat_id = body.email_enabled, body.telegram_enabled, body.telegram_chat_id
    db.commit()
    return prefs_out(p, user)


@router.post("/notifications/test")
def test_notification(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _prefs(db, user)
    sample = Alert(symbol="TEST", type="breakout", severity="bull", title="Test notification", message="If you can read this, notifications are working.")
    result = {"email": None, "telegram": None}
    if p.email_enabled:
        result["email"] = notify.send_email(user.email, "[Vnicorn] Test notification", format_text(sample))
    if p.telegram_enabled:
        result["telegram"] = notify.send_telegram(p.telegram_chat_id, format_text(sample, html=True))
    return result
