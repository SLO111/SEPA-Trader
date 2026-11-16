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


# ---------------- account settings ----------------

class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class EmailIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    new_email: EmailStr


class DeleteIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


PREF_DEFAULTS = {"theme": "dark", "default_interval": "1d", "start_page": "/chart", "compact_tables": False}
PREF_CHOICES = {"theme": {"dark", "light", "system"}, "default_interval": {"5m", "15m", "1h", "1d", "1wk", "1mo"},
                "start_page": {"/chart", "/markets", "/ideas", "/portfolios", "/feed"}}


@router.patch("/me")
def update_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.name = body.name.strip()
    db.commit()
    return user_out(user)


@router.post("/password")
def change_password(body: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "The current password is not correct")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


@router.post("/email")
def change_email(body: EmailIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "The password is not correct")
    email = body.new_email.lower()
    if email != user.email and db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user.email = email
    db.commit()
    return user_out(user)


@router.get("/prefs")
def get_prefs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    import json

    from ..models import UserPrefs

    row = db.get(UserPrefs, user.id)
    return {**PREF_DEFAULTS, **(json.loads(row.data) if row else {})}


@router.put("/prefs")
def set_prefs(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    import json

    from ..models import UserPrefs

    clean = {}
    for k, v in body.items():
        if k not in PREF_DEFAULTS:
            continue
        if k in PREF_CHOICES and v not in PREF_CHOICES[k]:
            raise HTTPException(400, f"Invalid value for {k}")
        if k == "compact_tables":
            v = bool(v)
        clean[k] = v
    row = db.get(UserPrefs, user.id)
    current = json.loads(row.data) if row else {}
    current.update(clean)
    if row is None:
        db.add(UserPrefs(user_id=user.id, data=json.dumps(current)))
    else:
        row.data = json.dumps(current)
    db.commit()
    return {**PREF_DEFAULTS, **current}


@router.delete("/me", status_code=204)
def delete_account(body: DeleteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "The password is not correct")
    if user.role == "admin" and user.email == settings.admin_email.lower().strip():
        raise HTTPException(400, "The main administrator account can't be deleted")
    db.delete(user)
    db.commit()
