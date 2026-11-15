from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from datetime import datetime, timedelta, timezone

from ..models import Payment, Subscription, User
from ..plans import PLANS
from ..security import admin_user
from .auth import user_out

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserPatch(BaseModel):
    plan: Literal["free", "pro", "premium"] | None = None
    role: Literal["user", "admin"] | None = None
    is_active: bool | None = None


@router.get("/stats")
def stats(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    by_plan = dict(db.execute(select(User.plan, func.count()).group_by(User.plan)).all())
    since = datetime.now(timezone.utc) - timedelta(days=30)
    subs = db.scalars(select(Subscription).where(Subscription.status.in_(["active", "trialing", "past_due"]))).all()
    # MRR: yearly plans count as 1/12 of their price each month.
    mrr = sum(s.amount_cents / (12 if s.interval == "year" else 1) for s in subs) / 100
    paid_30 = db.scalar(select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(Payment.status == "paid", Payment.created_at >= since)) or 0
    failed_30 = db.scalar(select(func.count()).select_from(Payment).where(Payment.status == "failed", Payment.created_at >= since)) or 0
    churned_30 = db.scalar(select(func.count()).select_from(Subscription).where(Subscription.canceled_at >= since)) or 0
    new_users_30 = db.scalar(select(func.count()).select_from(User).where(User.created_at >= since)) or 0
    recent = db.execute(select(Payment, User.email).join(User, User.id == Payment.user_id, isouter=True).order_by(Payment.created_at.desc()).limit(10)).all()
    return {
        "total_users": sum(by_plan.values()),
        "by_plan": {p: by_plan.get(p, 0) for p in PLANS},
        "new_users_30d": new_users_30,
        "mrr": round(mrr, 2),
        "arr": round(mrr * 12, 2),
        "active_subscriptions": len(subs),
        "past_due": sum(s.status == "past_due" for s in subs),
        "canceling": sum(s.cancel_at_period_end for s in subs),
        "revenue_30d": round(paid_30 / 100, 2),
        "failed_payments_30d": failed_30,
        "churned_30d": churned_30,
        "recent_payments": [
            {"date": p.created_at.isoformat(), "email": email, "amount": p.amount_cents / 100, "currency": p.currency, "status": p.status}
            for p, email in recent
        ],
    }


@router.get("/users")
def users(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.created_at.desc())).all()
    subs = {s.user_id: s for s in db.scalars(select(Subscription)).all()}
    return [{**user_out(u), "is_active": u.is_active, "subscription_status": subs[u.id].status if u.id in subs else None} for u in rows]


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, me: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    if u.id == me.id and (body.role == "user" or body.is_active is False):
        raise HTTPException(400, "You cannot remove your own administrator rights")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(u, field, value)
    db.commit()
    return {**user_out(u), "is_active": u.is_active}
