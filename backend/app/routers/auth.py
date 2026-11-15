from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User, Watchlist, WatchlistItem
from ..plans import limits_for
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def ensure_admin(user: User, db: Session) -> None:
    """Promote the account matching ADMIN_EMAIL, even if it was created before ADMIN_EMAIL was set."""
    if user.email == settings.admin_email.lower().strip() and user.role != "admin":
        user.role = "admin"
        db.commit()


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "plan": u.plan,
        "limits": limits_for(u),
        "created_at": u.created_at.isoformat(),
    }


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(
        email=email,
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        role="admin" if email == settings.admin_email.lower().strip() else "user",
    )
    wl = Watchlist(name="Favorites", position=0)
    wl.items = [WatchlistItem(symbol=s, position=i) for i, s in enumerate(DEFAULT_SYMBOLS)]
    user.watchlists = [wl]
    db.add(user)
    db.commit()
    return {"token": create_token(user.id), "user": user_out(user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated")
    ensure_admin(user, db)
    return {"token": create_token(user.id), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ensure_admin(user, db)
    return user_out(user)
