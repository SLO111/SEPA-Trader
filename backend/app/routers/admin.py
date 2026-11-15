from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
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
    return {
        "total_users": sum(by_plan.values()),
        "by_plan": {p: by_plan.get(p, 0) for p in PLANS},
    }


@router.get("/users")
def users(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [{**user_out(u), "is_active": u.is_active} for u in rows]


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
