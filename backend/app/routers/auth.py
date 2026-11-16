from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User, Watchlist, WatchlistItem
from ..plans import effective_plan, limits_for, trial_until
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

DEFAULT_SYMBOLS = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)
    ref: str | None = Field(default=None, max_length=16)  # referral code
    accept_terms: bool = True


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def ensure_admin(user: User, db: Session) -> None:
    """Promote the account matching ADMIN_EMAIL, even if it was created before ADMIN_EMAIL was set."""
    if user.email == settings.admin_email.lower().strip() and user.role != "admin":
        user.role = "admin"
        user.plan = "premium"
        db.commit()
    if user.role == "admin":
        # once: admins created before plans applied to them start on Premium (later changes are kept)
        import json

        from ..models import UserPrefs

        row = db.get(UserPrefs, user.id)
        data = json.loads(row.data) if row else {}
        if not data.get("admin_plan_init"):
            if user.plan == "free":
                user.plan = "premium"
            data["admin_plan_init"] = True
            if row is None:
                db.add(UserPrefs(user_id=user.id, data=json.dumps(data)))
            else:
                row.data = json.dumps(data)
            db.commit()


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "plan": u.plan,
        "limits": limits_for(u),
        "effective_plan": effective_plan(u),
        "trial_until": t.isoformat() if (t := trial_until(u)) else None,
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
    if user.role == "admin":
        user.plan = "premium"
    wl = Watchlist(name="Favorites", position=0)
    wl.items = [WatchlistItem(symbol=s, position=i) for i, s in enumerate(DEFAULT_SYMBOLS)]
    user.watchlists = [wl]
    db.add(user)
    db.commit()
    from ..growth_service import on_signup

    on_signup(db, user, body.ref, body.accept_terms)
    db.refresh(user)
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
    from ..growth_service import accepted_terms

    return {**user_out(user), "terms_accepted": accepted_terms(db, user)}


@router.post("/accept-terms")
def accept_terms_now(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..growth_service import accept_terms

    accept_terms(db, user)
    return {"ok": True}


@router.get("/referral")
def referral(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..growth_service import referral_stats

    return referral_stats(db, user)


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
    saved = json.loads(row.data) if row else {}
    return {k: saved.get(k, v) for k, v in PREF_DEFAULTS.items()}


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
    return {k: current.get(k, v) for k, v in PREF_DEFAULTS.items()}


@router.delete("/me", status_code=204)
def delete_account(body: DeleteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "The password is not correct")
    if user.role == "admin" and user.email == settings.admin_email.lower().strip():
        raise HTTPException(400, "The main administrator account can't be deleted")
    from ..growth_service import purge

    purge(db, user.id)
    db.delete(user)
    db.commit()
