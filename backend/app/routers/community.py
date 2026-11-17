"""Public track record, leaderboard, shared watchlists, copy trading and academy progress."""

from __future__ import annotations

import re
import secrets
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import market_data
from ..db import SessionLocal, get_db
from ..models import (AIPick, CommunityProfile, CopiedTrade, CopyFollow, LessonDone, PaperTrade, SharedWatchlist, TradeIdea, User,
                      Watchlist, WatchlistItem)
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api", tags=["community"])

DONE = ("TARGET", "STOPPED")


# ------------------------------------------------------------------ public track record

def _stats(rs: list[float]) -> dict:
    if not rs:
        return {"trades": 0}
    wins = [r for r in rs if r > 0]
    return {"trades": len(rs), "win_rate": round(100 * len(wins) / len(rs), 1), "avg_r": round(sum(rs) / len(rs), 2),
            "total_r": round(sum(rs), 1), "best_r": round(max(rs), 2), "worst_r": round(min(rs), 2)}


def track_record(db: Session) -> dict:
    """How the published daily ideas played out: closed ideas only, each counted as a 1R risk."""
    rows = db.scalars(select(TradeIdea).where(TradeIdea.r_multiple.is_not(None), TradeIdea.closed_at.is_not(None),
                                              TradeIdea.status.notin_(("WAIT", "BUY", "TRIM", "CANCEL")))).all()
    picks = set(db.scalars(select(AIPick.idea_id).where(AIPick.pick.is_(True))).all())
    rows = sorted(rows, key=lambda r: r.closed_at)
    months: dict[str, list[float]] = defaultdict(list)
    tfs: dict[str, list[float]] = defaultdict(list)
    eq, cum = [], 0.0
    for r in rows:
        months[r.closed_at.strftime("%Y-%m")].append(r.r_multiple)
        tfs[r.timeframe].append(r.r_multiple)
        cum += r.r_multiple
        eq.append({"time": r.closed_at.isoformat(), "value": round(cum, 2)})
    # one point per day on the curve
    by_day = {}
    for p in eq:
        by_day[p["time"]] = p
    open_n = db.scalar(select(func.count()).select_from(TradeIdea).where(TradeIdea.status.in_(("WAIT", "BUY", "TRIM")))) or 0
    first = db.scalar(select(func.min(TradeIdea.batch_date)))
    return {
        "since": first.isoformat() if first else None, "open": open_n,
        "all": _stats([r.r_multiple for r in rows]),
        "ai_picks": _stats([r.r_multiple for r in rows if r.id in picks]),
        "by_timeframe": [{"timeframe": k, **_stats(v)} for k, v in sorted(tfs.items())],
        "by_month": [{"month": k, **_stats(v)} for k, v in sorted(months.items())],
        "equity": list(by_day.values()),
        "recent": [{"symbol": r.symbol, "timeframe": r.timeframe, "side": r.side, "closed_at": r.closed_at.isoformat(), "status": r.status,
                    "r": round(r.r_multiple, 2), "ai_pick": r.id in picks} for r in reversed(rows[-15:])],
    }


@router.get("/public/track-record")
def public_track_record():
    def build():
        with SessionLocal() as db:
            return track_record(db)

    return market_data._fast("public:track-record", 3600, build)


# ------------------------------------------------------------------ community profile & leaderboard

class ProfileIn(BaseModel):
    display_name: str = Field(min_length=3, max_length=24)
    public: bool = True
    allow_copy: bool = True


def _profile(db: Session, uid: int) -> CommunityProfile | None:
    return db.get(CommunityProfile, uid)


@router.get("/community/profile")
def get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _profile(db, user.id)
    following = db.scalars(select(CopyFollow.leader_id).where(CopyFollow.follower_id == user.id)).all()
    names = {c.user_id: c.display_name for c in db.scalars(select(CommunityProfile).where(CommunityProfile.user_id.in_(following))).all()} if following else {}
    followers = db.scalar(select(func.count()).select_from(CopyFollow).where(CopyFollow.leader_id == user.id)) or 0
    return {"profile": {"display_name": p.display_name, "public": p.public, "allow_copy": p.allow_copy} if p else None,
            "following": [{"user_id": i, "display_name": names.get(i, "?")} for i in following], "followers": followers,
            "max_follows": limits_for(user)["max_copy_follows"]}


@router.put("/community/profile")
def set_profile(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    name = body.display_name.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.\- ]{3,24}", name):
        raise HTTPException(400, "Use 3-24 letters, digits, spaces, dots, dashes or underscores.")
    taken = db.scalar(select(CommunityProfile).where(func.lower(CommunityProfile.display_name) == name.lower(), CommunityProfile.user_id != user.id))
    if taken:
        raise HTTPException(409, "That name is taken.")
    p = _profile(db, user.id) or CommunityProfile(user_id=user.id, display_name=name)
    p.display_name, p.public, p.allow_copy = name, body.public, body.allow_copy
    db.add(p)
    if not body.allow_copy:  # stop being copied
        db.query(CopyFollow).filter(CopyFollow.leader_id == user.id).delete()
    db.commit()
    return get_profile(user, db)


def _closed_r(db: Session, since: date | None) -> dict[int, list[tuple[float, date]]]:
    """Closed paper trades (chart + ideas + Move Detector, not copies) in R per user."""
    from .ideas import _paper_out

    q = select(PaperTrade).where(PaperTrade.timeframe != "CP")
    out: dict[int, list] = defaultdict(list)
    hist: dict[str, object] = {}
    for t in db.scalars(q).all():
        if t.symbol not in hist:
            try:
                hist[t.symbol] = market_data.history(t.symbol)
            except Exception:
                hist[t.symbol] = None
        df = hist[t.symbol]
        if df is None:
            continue
        f = _paper_out(t, df)
        if f["open"] or not f["closed_at"]:
            continue
        d = date.fromisoformat(f["closed_at"])
        if since and d < since:
            continue
        out[t.user_id].append((f["r_multiple"], d))
    return out


def leaderboard(db: Session, period: str = "month", min_trades: int = 5) -> list[dict]:
    today = date.today()
    since = {"month": today.replace(day=1), "90d": today - timedelta(days=90), "all": None}[period]
    profiles = {p.user_id: p for p in db.scalars(select(CommunityProfile).where(CommunityProfile.public.is_(True))).all()}
    if not profiles:
        return []
    rs = _closed_r(db, since)
    followers = dict(db.execute(select(CopyFollow.leader_id, func.count()).group_by(CopyFollow.leader_id)).all())
    rows = []
    for uid, p in profiles.items():
        v = [r for r, _ in rs.get(uid, [])]
        if len(v) < min_trades:
            continue
        st = _stats(v)
        rows.append({"user_id": uid, "display_name": p.display_name, "allow_copy": p.allow_copy, "followers": followers.get(uid, 0), **st})
    rows.sort(key=lambda r: (-r["total_r"], -r["win_rate"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows[:100]


@router.get("/public/leaderboard")
def public_leaderboard(period: str = Query("month", pattern="^(month|90d|all)$")):
    def build():
        with SessionLocal() as db:
            return {"period": period, "min_trades": 5, "rows": leaderboard(db, period)}

    return market_data._fast(f"public:leaderboard:{period}", 600, build)


# ------------------------------------------------------------------ copy trading

@router.post("/community/follow/{leader_id}")
def follow(leader_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if leader_id == user.id:
        raise HTTPException(400, "You can't copy yourself.")
    p = _profile(db, leader_id)
    if p is None or not p.public or not p.allow_copy:
        raise HTTPException(404, "This trader can't be copied.")
    if db.scalar(select(CopyFollow).where(CopyFollow.follower_id == user.id, CopyFollow.leader_id == leader_id)):
        return get_profile(user, db)
    n = db.scalar(select(func.count()).select_from(CopyFollow).where(CopyFollow.follower_id == user.id)) or 0
    lim = limits_for(user)["max_copy_follows"]
    if n >= lim:
        raise HTTPException(403, f"Your plan lets you copy {lim} trader{'s' if lim != 1 else ''}. Upgrade to copy more.")
    db.add(CopyFollow(follower_id=user.id, leader_id=leader_id))
    db.commit()
    return get_profile(user, db)


@router.delete("/community/follow/{leader_id}")
def unfollow(leader_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(CopyFollow).filter(CopyFollow.follower_id == user.id, CopyFollow.leader_id == leader_id).delete()
    db.commit()
    return get_profile(user, db)


def copy_new_trade(db: Session, leader_trade: PaperTrade) -> int:
    """Mirror a leader's new chart trade into every follower's account (source "Copied")."""
    n = 0
    for f in db.scalars(select(CopyFollow).where(CopyFollow.leader_id == leader_trade.user_id)).all():
        c = PaperTrade(user_id=f.follower_id, idea_id=None, symbol=leader_trade.symbol, timeframe="CP", side=leader_trade.side,
                       entry_date=leader_trade.entry_date, entry=leader_trade.entry, stop=leader_trade.stop, trim=leader_trade.trim,
                       target=leader_trade.target, weight=leader_trade.weight)
        db.add(c)
        db.flush()
        db.add(CopiedTrade(paper_id=c.id, leader_paper_id=leader_trade.id, leader_id=leader_trade.user_id))
        n += 1
    db.commit()
    return n


def close_copies(db: Session, leader_trade: PaperTrade) -> int:
    """When the leader sells, the copies close at the same price and date."""
    ids = db.scalars(select(CopiedTrade.paper_id).where(CopiedTrade.leader_paper_id == leader_trade.id)).all()
    n = 0
    for t in db.scalars(select(PaperTrade).where(PaperTrade.id.in_(ids), PaperTrade.exit_date.is_(None))).all() if ids else []:
        t.exit_date, t.exit_price = leader_trade.exit_date, leader_trade.exit_price
        n += 1
    db.commit()
    return n


# ------------------------------------------------------------------ shared watchlists

@router.post("/watchlists/{wl_id}/share")
def share_watchlist(wl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = db.get(Watchlist, wl_id)
    if w is None or w.user_id != user.id:
        raise HTTPException(404, "Watchlist not found")
    s = db.scalar(select(SharedWatchlist).where(SharedWatchlist.watchlist_id == wl_id))
    if s is None:
        s = SharedWatchlist(slug=secrets.token_urlsafe(6).replace("-", "x").replace("_", "y")[:8], watchlist_id=wl_id, user_id=user.id)
        db.add(s)
        db.commit()
    return {"slug": s.slug}


@router.delete("/watchlists/{wl_id}/share", status_code=204)
def unshare_watchlist(wl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(SharedWatchlist).filter(SharedWatchlist.watchlist_id == wl_id, SharedWatchlist.user_id == user.id).delete()
    db.commit()


@router.get("/public/watchlists/{slug}")
def public_watchlist(slug: str, db: Session = Depends(get_db)):
    s = db.get(SharedWatchlist, slug)
    w = db.get(Watchlist, s.watchlist_id) if s else None
    if w is None:
        raise HTTPException(404, "This shared watchlist doesn't exist (anymore).")
    p = _profile(db, w.user_id)
    rows = []
    for it in w.items[:200]:
        try:
            q = market_data.quote(it.symbol)
            rows.append({"symbol": it.symbol, "name": market_data.symbol_meta(it.symbol).get("name", it.symbol), "price": q["price"], "change_pct": q["change_pct"]})
        except Exception:
            rows.append({"symbol": it.symbol, "name": it.symbol, "price": None, "change_pct": None})
    return {"slug": slug, "name": w.name, "owner": p.display_name if p else "A Vnicorn member", "symbols": rows}


@router.post("/public/watchlists/{slug}/copy")
def copy_watchlist(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(SharedWatchlist, slug)
    src = db.get(Watchlist, s.watchlist_id) if s else None
    if src is None:
        raise HTTPException(404, "This shared watchlist doesn't exist (anymore).")
    lim = limits_for(user)
    if len(user.watchlists) >= lim["max_watchlists"]:
        raise HTTPException(403, f"Your plan allows {lim['max_watchlists']} watchlist(s). Upgrade or delete one first.")
    w = Watchlist(user_id=user.id, name=f"{src.name} (copy)"[:80], color=src.color, position=len(user.watchlists))
    w.items = [WatchlistItem(symbol=i.symbol, position=k) for k, i in enumerate(src.items[: lim["max_symbols_per_watchlist"]])]
    db.add(w)
    db.commit()
    return {"id": w.id, "name": w.name}


# ------------------------------------------------------------------ academy progress

LESSONS = {"stages", "trend-template", "relative-strength", "vcp", "entries-risk", "selling", "exposure", "review"}


@router.get("/academy/progress")
def academy_progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"done": sorted(db.scalars(select(LessonDone.lesson).where(LessonDone.user_id == user.id)).all())}


@router.post("/academy/progress/{lesson}")
def lesson_done(lesson: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if lesson not in LESSONS:
        raise HTTPException(404, "Unknown lesson")
    if not db.scalar(select(LessonDone).where(LessonDone.user_id == user.id, LessonDone.lesson == lesson)):
        db.add(LessonDone(user_id=user.id, lesson=lesson))
        db.commit()
    return academy_progress(user, db)
