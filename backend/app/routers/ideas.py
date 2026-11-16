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
    from ..models import PaperTrade

    taken = set(db.scalars(select(PaperTrade.idea_id).where(PaperTrade.user_id == user.id)).all())
    from ..models import AIPick

    ai_of = {a.idea_id: {"prob": a.prob, "ev": a.ev, "stop": a.stop, "trim": a.trim, "target": a.target, "rr": a.rr, "pick": a.pick}
             for a in db.scalars(select(AIPick).where(AIPick.idea_id.in_([r.id for r in rows]))).all()} if rows else {}
    open_rows = [r for r in allrows if r.status in OPEN]
    done = [r for r in allrows if r.status in ("TARGET", "STOPPED") or (r.status not in OPEN and r.r_multiple is not None)]
    entered_open = [r for r in open_rows if r.pnl_pct is not None]
    wins = [r for r in done if (r.r_multiple or 0) > 0]
    return {
        "updated": latest_batch(db).isoformat() if latest_batch(db) else None,
        "ideas": [{**idea_out(r, with_structure=r.status in OPEN), "taken": r.id in taken, "ai": ai_of.get(r.id)} for r in rows],
        "summary": {
            "open": len(open_rows),
            "active": len(entered_open),
            "unrealized_pct": round(sum(r.pnl_pct for r in entered_open) / len(entered_open), 2) if entered_open else None,
            "closed": len(done),
            "win_rate": round(len(wins) / len(done) * 100, 1) if done else None,
            "avg_r": round(sum(r.r_multiple or 0 for r in done) / len(done), 2) if done else None,
            "by_timeframe": {tf: sum(1 for r in open_rows if r.timeframe == tf) for tf in ("SWING", "TRADE", "INVEST", "SHORT", "AI")},
            # vnicornAI vs. the rules: closed results of each, so the comparison is public
            "ai_closed": len([r for r in done if r.timeframe == "AI"]),
            "ai_avg_r": round(sum(r.r_multiple or 0 for r in done if r.timeframe == "AI") / max(1, len([r for r in done if r.timeframe == "AI"])), 2) if any(r.timeframe == "AI" for r in done) else None,
            "rules_avg_r": round(sum(r.r_multiple or 0 for r in done if r.timeframe != "AI") / max(1, len([r for r in done if r.timeframe != "AI"])), 2) if any(r.timeframe != "AI" for r in done) else None,
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
    return {"id": r.id, "day": r.key.split(":", 1)[1], "title": r.title, "created_at": r.created_at.isoformat(), **json.loads(r.body)}


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


# ---------------- paper trades: take an idea and track it ----------------

def _paper_out(t, df) -> dict:
    from engine.paper import follow

    d = {"id": t.id, "idea_id": t.idea_id, "symbol": t.symbol, "timeframe": t.timeframe, "side": t.side,
         "entry_date": t.entry_date.isoformat(), "entry": t.entry, "stop": t.stop, "trim": t.trim, "target": t.target,
         "weight": t.weight}
    if df is None:
        return {**d, "status": "OPEN", "open": True, "current": None, "r_multiple": 0.0, "pnl_pct": 0.0, "closed_at": None, "exit_price": None}
    return {**d, **follow({**d, "exit_date": t.exit_date, "exit_price": t.exit_price}, df)}


@router.post("/paper-trades")
def take_idea(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Buy / Short an idea now: entry at the latest price, the idea's stop / trim / target."""
    from datetime import date as _date

    from .. import market_data
    from ..models import PaperTrade

    if not limits_for(user)["move_detector"]:
        raise HTTPException(403, "Trade ideas are available on the Pro and Premium plans.")
    idea = db.get(TradeIdea, int(body.get("idea_id") or 0))
    if idea is None:
        raise HTTPException(404, "Idea not found")
    existing = db.scalars(select(PaperTrade).where(PaperTrade.user_id == user.id, PaperTrade.idea_id == idea.id)).first()
    if existing:
        raise HTTPException(409, "You already took this idea")
    try:
        df = market_data.history(idea.symbol)
        price, day = float(df["close"].iloc[-1]), df.index[-1].date()
    except Exception:
        df, price, day = None, idea.entry, _date.today()
    long = idea.side == "long"
    if (long and price <= idea.stop) or (not long and price >= idea.stop):
        raise HTTPException(400, f"{idea.symbol} is already beyond the stop ({idea.stop}); this idea is no longer valid.")
    t = PaperTrade(user_id=user.id, idea_id=idea.id, symbol=idea.symbol, timeframe=idea.timeframe, side=idea.side,
                   entry_date=day, entry=round(price, 2), stop=idea.stop, trim=idea.trim, target=idea.target, weight=idea.weight)
    db.add(t)
    db.commit()
    return _paper_out(t, df)


@router.get("/paper-trades")
def paper_trades(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from engine.paper import summary

    from .. import market_data
    from ..models import PaperTrade

    rows = []
    for t in db.scalars(select(PaperTrade).where(PaperTrade.user_id == user.id).order_by(PaperTrade.created_at.desc())).all():
        try:
            df = market_data.history(t.symbol)
        except Exception:
            df = None
        rows.append(_paper_out(t, df))
    return {"trades": rows, "summary": summary(rows)}


@router.post("/paper-trades/{trade_id}/close")
def close_paper(trade_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from .. import market_data
    from ..models import PaperTrade

    t = db.get(PaperTrade, trade_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "Trade not found")
    df = market_data.history(t.symbol)
    t.exit_price, t.exit_date = round(float(df["close"].iloc[-1]), 2), df.index[-1].date()
    db.commit()
    return _paper_out(t, df)


@router.delete("/paper-trades/{trade_id}", status_code=204)
def delete_paper(trade_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..models import PaperTrade

    t = db.get(PaperTrade, trade_id)
    if t is None or t.user_id != user.id:
        raise HTTPException(404, "Trade not found")
    db.delete(t)
    db.commit()


@router.get("/ai/status")
def ai_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """vnicornAI: when it was trained, on how much data, and its walk-forward report."""
    from .. import vnicorn_service

    return vnicorn_service.status(db)
