from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..ideas_service import latest_batch, refresh_statuses, run_ideas
from ..models import DailyDigest, FeedItem, TradeIdea, User
from ..plans import limits_for
from ..security import admin_user, current_user

router = APIRouter(prefix="/api", tags=["ideas"])

OPEN = ("WAIT", "BUY", "TRIM")


def _live(symbol: str) -> dict:
    """Current Structure Count 4/4 and market cycle stage for the symbol (live, from daily prices)."""
    from engine import stages, structure

    from .. import market_data

    def build():
        try:
            df = market_data.history(symbol)
        except Exception:
            return {"structure": None, "stage": None}
        return {"structure": structure.label(structure.analyze(df.iloc[-300:]).state), "stage": stages.stage_now(df)}

    return market_data._fast(f"ideas-live:{symbol}", 600, build)


def idea_out(r: TradeIdea, with_structure: bool = False) -> dict:
    return {
        **(_live(r.symbol) if with_structure else {}),
        "id": r.id, "date": r.batch_date.isoformat(), "symbol": r.symbol, "timeframe": r.timeframe, "side": r.side,
        "entry": r.entry, "stop": r.stop, "trim": r.trim, "target": r.target, "rr": r.rr, "weight": r.weight,
        "score": r.score, "reason": r.reason, "status": r.status, "current": r.current, "pnl_pct": r.pnl_pct,
        "r_multiple": r.r_multiple, "closed_at": r.closed_at.isoformat() if r.closed_at else None,
    }


@router.get("/ideas")
def ideas(view: Literal["open", "closed", "all"] = "open", user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not limits_for(user)["move_detector"]:
        raise HTTPException(403, "Trade ideas are available on the Pro and Premium plans.")
    q = select(TradeIdea)
    if view == "open":
        q = q.where(TradeIdea.status.in_(OPEN))
    elif view == "closed":
        q = q.where(TradeIdea.status.notin_(OPEN))
    rows = db.scalars(q.order_by(TradeIdea.batch_date.desc(), TradeIdea.score.desc()).limit(200)).all()
    allrows = db.scalars(select(TradeIdea)).all()
    open_rows = [r for r in allrows if r.status in OPEN]
    done = [r for r in allrows if r.status in ("TARGET", "STOPPED") or (r.status not in OPEN and r.r_multiple is not None)]
    entered_open = [r for r in open_rows if r.pnl_pct is not None]
    wins = [r for r in done if (r.r_multiple or 0) > 0]
    return {
        "updated": latest_batch(db).isoformat() if latest_batch(db) else None,
        "ideas": [idea_out(r, with_structure=r.status in OPEN) for r in rows],
        "summary": {
            "open": len(open_rows),
            "active": len(entered_open),
            "unrealized_pct": round(sum(r.pnl_pct for r in entered_open) / len(entered_open), 2) if entered_open else None,
            "closed": len(done),
            "win_rate": round(len(wins) / len(done) * 100, 1) if done else None,
            "avg_r": round(sum(r.r_multiple or 0 for r in done) / len(done), 2) if done else None,
            "by_timeframe": {tf: sum(1 for r in open_rows if r.timeframe == tf) for tf in ("SWING", "TRADE", "INVEST", "SHORT")},
        },
    }


@router.post("/ideas/regenerate")
def regenerate(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = run_ideas(db, force=True)
    refresh_statuses(db)
    return {"generated": len(rows)}


@router.get("/feed")
def feed(
    kind: Literal["all", "earnings", "mover", "breakout", "high", "news", "idea", "summary"] = "all",
    symbol: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = select(FeedItem)
    if kind != "all":
        q = q.where(FeedItem.kind == kind)
    else:
        q = q.where(FeedItem.kind != "summary")  # the daily summary has its own card
    if symbol:
        q = q.where(FeedItem.symbol == symbol.upper())
    if before_id:
        q = q.where(FeedItem.id < before_id)
    rows = db.scalars(q.order_by(FeedItem.id.desc()).limit(limit)).all()
    return [
        {"id": r.id, "kind": r.kind, "symbol": r.symbol, "severity": r.severity, "title": r.title, "body": r.body, "url": r.url,
         "created_at": r.created_at.isoformat()}
        for r in rows
    ]


@router.get("/feed/summary")
def latest_summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The latest end-of-day summary (sections as JSON), or null before the first one."""
    import json

    r = db.scalars(select(FeedItem).where(FeedItem.kind == "summary").order_by(FeedItem.id.desc()).limit(1)).first()
    if not r:
        return None
    return {"id": r.id, "title": r.title, "created_at": r.created_at.isoformat(), **json.loads(r.body)}


class DigestIn(BaseModel):
    enabled: bool


@router.get("/feed/digest")
def get_digest(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..notify import email_configured

    d = db.get(DailyDigest, user.id)
    return {"enabled": bool(d and d.enabled), "email": user.email, "email_configured": email_configured()}


@router.put("/feed/digest")
def set_digest(body: DigestIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.get(DailyDigest, user.id)
    if d is None:
        d = DailyDigest(user_id=user.id, enabled=body.enabled)
        db.add(d)
    else:
        d.enabled = body.enabled
    db.commit()
    return get_digest(user, db)
