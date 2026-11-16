"""Trials, referrals, monthly usage quotas and terms acceptance."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .models import PlanTrial, Referral, ReferralCode, TermsAcceptance, Usage, User

TERMS_VERSION = "2026-11"
REFERRAL_BONUS_DAYS = 7  # extra trial days for the invited user
REFERRAL_REWARD_DAYS = 30  # Premium days for the inviter when the invited user starts paying


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def grant_trial(db: Session, user: User, days: int, source: str) -> PlanTrial | None:
    """Start or extend a Premium trial (extends from its current end if it is still running)."""
    if days <= 0:
        return None
    t = db.get(PlanTrial, user.id)
    base = max(_now(), _aware(t.ends_at)) if t else _now()
    if t is None:
        t = PlanTrial(user_id=user.id, ends_at=base + timedelta(days=days), source=source)
        db.add(t)
    else:
        t.ends_at, t.source = base + timedelta(days=days), source
    db.flush()
    db.expire(user, ["trial"])
    return t


def referral_code(db: Session, user: User) -> str:
    row = db.get(ReferralCode, user.id)
    if row is None:
        while True:
            code = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()
            if len(code) >= 6 and not db.scalar(select(ReferralCode).where(ReferralCode.code == code)):
                break
        row = ReferralCode(user_id=user.id, code=code)
        db.add(row)
        db.commit()
    return row.code


def purge(db: Session, user_id: int) -> None:
    """Remove a user's trial / referral / usage rows (account deleted, or a reused id on SQLite)."""
    from sqlalchemy import delete, or_

    for model, cond in ((PlanTrial, PlanTrial.user_id == user_id), (ReferralCode, ReferralCode.user_id == user_id),
                        (Referral, or_(Referral.referred_id == user_id, Referral.owner_id == user_id)),
                        (Usage, Usage.user_id == user_id), (TermsAcceptance, TermsAcceptance.user_id == user_id)):
        db.execute(delete(model).where(cond))


def on_signup(db: Session, user: User, ref: str | None, accepted_terms: bool) -> None:
    purge(db, user.id)
    owner = None
    if ref:
        rc = db.scalar(select(ReferralCode).where(ReferralCode.code == ref.strip().upper()))
        if rc and rc.user_id != user.id:
            owner = rc.user_id
            db.add(Referral(referred_id=user.id, owner_id=owner))
    days = settings.trial_days + (REFERRAL_BONUS_DAYS if owner and settings.trial_days > 0 else 0)
    if user.role != "admin":
        grant_trial(db, user, days, "referral" if owner else "signup")
    if accepted_terms:
        db.add(TermsAcceptance(user_id=user.id, version=TERMS_VERSION))
    db.commit()


def on_paid(db: Session, user: User) -> None:
    """Called when a subscription becomes active: reward the inviter once."""
    r = db.get(Referral, user.id)
    if r and not r.rewarded:
        owner = db.get(User, r.owner_id)
        if owner is not None:
            grant_trial(db, owner, REFERRAL_REWARD_DAYS, "referral")
        r.rewarded = True


def referral_stats(db: Session, user: User) -> dict:
    invited = db.scalar(select(func.count()).select_from(Referral).where(Referral.owner_id == user.id)) or 0
    paid = db.scalar(select(func.count()).select_from(Referral).where(Referral.owner_id == user.id, Referral.rewarded.is_(True))) or 0
    return {"code": referral_code(db, user), "invited": invited, "rewarded": paid,
            "bonus_days": REFERRAL_BONUS_DAYS, "reward_days": REFERRAL_REWARD_DAYS}


def _month() -> str:
    return _now().strftime("%Y-%m")


def usage(db: Session, user: User, key: str) -> int:
    row = db.scalar(select(Usage).where(Usage.user_id == user.id, Usage.month == _month(), Usage.key == key))
    return row.count if row else 0


def consume(db: Session, user: User, key: str, limit: int, label: str) -> int:
    """Count one use against a monthly limit; 429 with a clear message when it's used up. Returns the uses left."""
    row = db.scalar(select(Usage).where(Usage.user_id == user.id, Usage.month == _month(), Usage.key == key))
    used = row.count if row else 0
    if used >= limit:
        nxt = (_now().replace(day=1) + timedelta(days=32)).replace(day=1)
        raise HTTPException(429, f"You've used {used}/{limit} {label} this month. It resets on {nxt:%b %d}; Premium is unlimited.")
    if row is None:
        row = Usage(user_id=user.id, month=_month(), key=key, count=0)
        db.add(row)
    row.count = used + 1
    db.commit()
    return max(0, limit - row.count)


def accepted_terms(db: Session, user: User) -> bool:
    return db.scalar(select(TermsAcceptance).where(TermsAcceptance.user_id == user.id, TermsAcceptance.version == TERMS_VERSION)) is not None


def accept_terms(db: Session, user: User) -> None:
    if not accepted_terms(db, user):
        db.add(TermsAcceptance(user_id=user.id, version=TERMS_VERSION))
        db.commit()
