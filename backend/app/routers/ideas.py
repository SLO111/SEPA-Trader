from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import market_data
from ..db import get_db
from ..ideas_service import classify, latest_batch, refresh_statuses, run_ideas
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


def _plan_cut(rows: list, lim: dict) -> list:
    """Per daily batch: the best `ideas_limit` ideas (by score, at most 3 per industry while others are available);
    shorts only on plans that include them."""
    from engine.ideas import diversify

    from ..ideas_service import industry_map

    days: dict = {}
    for r in rows:
        if not lim["ideas_shorts"] and (r.side == "short" or r.timeframe == "SHORT"):
            continue
        days.setdefault(r.batch_date, []).append(r)
    inds = industry_map(list({r.symbol for r in rows}))
    out = []
    for day_rows in days.values():  # rows arrive newest day first, best score first
        out += diversify(day_rows, inds)[: lim["ideas_limit"]]
    return out


@router.get("/ideas")
def ideas(view: Literal["open", "closed", "all"] = "open", user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not limits_for(user)["move_detector"]:
        raise HTTPException(403, "Trade ideas are available on the Pro and Premium plans.")
    q = select(TradeIdea)
    if view == "open":
        q = q.where(TradeIdea.status.in_(OPEN))
    elif view == "closed":
        q = q.where(TradeIdea.status.notin_(OPEN))
    rows = db.scalars(q.order_by(TradeIdea.batch_date.desc(), TradeIdea.score.desc()).limit(400)).all()
    lim = limits_for(user)
    rows = _plan_cut(rows, lim)[:200]
    from engine.ideas import MIN_RR_SIGNALS, rr_now

    def _rr(r):
        return rr_now({"side": r.side, "stop": r.stop, "target": r.target, "rr": r.rr}, r.current, r.status)

    if view == "open":
        # a running idea whose reward left is under 1.5× the risk is no longer a good entry: it leaves Signals
        # (it is still followed in the background for the track record, and in Backtest for those who took it)
        rows = [r for r in rows if r.status == "WAIT" or (_rr(r) or 0) >= MIN_RR_SIGNALS]
    allrows = db.scalars(select(TradeIdea)).all()
    from ..models import PaperTrade

    taken = set(db.scalars(select(PaperTrade.idea_id).where(PaperTrade.user_id == user.id)).all())
    from ..models import AIPick

    ai_of = {a.idea_id: {"prob": a.prob, "ev": a.ev, "stop": a.stop, "trim": a.trim, "target": a.target, "rr": a.rr, "pick": a.pick}
             for a in db.scalars(select(AIPick).where(AIPick.idea_id.in_([r.id for r in rows]))).all()} if rows and lim["ai_picks"] else {}
    open_rows = [r for r in allrows if r.status in OPEN and (r.status == "WAIT" or (_rr(r) or 0) >= MIN_RR_SIGNALS)]
    done = [r for r in allrows if r.status in ("TARGET", "STOPPED") or (r.status not in OPEN and r.r_multiple is not None)]
    entered_open = [r for r in open_rows if r.pnl_pct is not None]
    wins = [r for r in done if (r.r_multiple or 0) > 0]
    return {
        "updated": latest_batch(db).isoformat() if latest_batch(db) else None,
        "plan": {"ideas_limit": lim["ideas_limit"], "shorts": lim["ideas_shorts"], "ai_picks": lim["ai_picks"], "min_rr": MIN_RR_SIGNALS},
        "ideas": [{**idea_out(r, with_structure=r.status in OPEN), "taken": r.id in taken, "ai": ai_of.get(r.id),
                   **dict(zip(("sector", "industry"), classify(r.symbol))),
                   "rr_now": _rr(r) if r.status in OPEN else None,
                   "earnings_in": market_data.earnings_in_days(r.symbol) if r.status in OPEN else None} for r in rows],
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


def _regenerate_job() -> None:
    from .. import market_data, regen_status
    from ..db import SessionLocal
    from . import sepa

    try:
        # Move Detector first: a fresh scan from the last close (RS, Trend Template, Bull / Bear scores)
        regen_status.stage("Scanning Move Detector")
        market_data._tls.rebuilding = True
        try:
            sepa.invalidate_scan()
            scanned = len(sepa.cached_scan())
        finally:
            market_data._tls.rebuilding = False
        # then the ideas, with vnicornAI's ratings and its major-move probabilities (shown in Move Detector)
        regen_status.stage("Building trade ideas")
        with SessionLocal() as db:
            rows = run_ideas(db, force=True)
            regen_status.stage("Updating idea statuses")
            refresh_statuses(db)
        market_data.mark_stale()
        regen_status.finish(generated=len(rows), scanned=scanned)
    except Exception as e:
        import logging

        logging.getLogger("sepa.ideas").exception("Regenerate failed")
        regen_status.finish(error=f"{type(e).__name__}: {str(e)[:150]}")


@router.post("/ideas/regenerate")
def regenerate(_: User = Depends(admin_user)):
    """Admin: rebuild Move Detector and the latest ideas batch from the last completed close, in the background
    (a few minutes over the whole universe). Users otherwise get them automatically after each close."""
    import threading

    from .. import regen_status
    from ..ideas_service import _data_ready

    if not _data_ready():
        raise HTTPException(409, "Market data is still loading after a restart. Try again in a few minutes.")
    if not regen_status.running_here():
        regen_status.start()
        threading.Thread(target=_regenerate_job, name="ideas-regenerate", daemon=True).start()
    return {"started": True, **regen_status.status()}


@router.get("/ideas/regenerate")
def regenerate_status(_: User = Depends(admin_user)):
    from .. import regen_status

    return regen_status.status()


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
        q = q.where(FeedItem.kind.notin_(("summary", "letter")))  # the daily summary and the weekly letter have their own cards
    if symbol:
        q = q.where(FeedItem.symbol == symbol.upper())
    if before_id:
        q = q.where(FeedItem.id < before_id)
    rows = db.scalars(q.order_by(FeedItem.id.desc()).limit(limit)).all()
    import json

    from engine.feed import gate_summary

    lim = limits_for(user)
    def body(r):
        if r.kind == "summary" and r.body:
            return json.dumps(gate_summary(json.loads(r.body), lim))
        if r.kind == "letter" and r.body and not lim["weekly_letter"]:
            return json.dumps({"locked": True, "paragraphs": json.loads(r.body).get("paragraphs", [])[:1]})
        return r.body
    return [
        {"id": r.id, "kind": r.kind, "symbol": r.symbol, "severity": r.severity, "title": r.title, "body": body(r), "url": r.url,
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
    from engine.feed import gate_summary

    return {"id": r.id, "day": r.key.split(":", 1)[1], "title": r.title, "created_at": r.created_at.isoformat(),
            **gate_summary(json.loads(r.body), limits_for(user))}


@router.get("/feed/letter")
def latest_letter(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """The latest weekly letter (Premium; others get the first paragraph and a lock)."""
    import json

    r = db.scalars(select(FeedItem).where(FeedItem.kind == "letter").order_by(FeedItem.id.desc()).limit(1)).first()
    if not r:
        return None
    d = json.loads(r.body)
    if not limits_for(user)["weekly_letter"]:
        d = {"week": d.get("week"), "paragraphs": d["paragraphs"][:1], "locked": True}
    return {"id": r.id, "title": r.title, "created_at": r.created_at.isoformat(), **d}


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


def _paper_filter(q, source: str):
    from ..models import PaperTrade

    if source == "md":
        return q.where(PaperTrade.timeframe == "MD")
    if source == "chart":
        return q.where(PaperTrade.timeframe == "CH")
    if source == "copy":
        return q.where(PaperTrade.timeframe == "CP")
    if source == "ideas":
        return q.where(PaperTrade.timeframe.notin_(["MD", "CH", "CP"]))
    return q


class ChartTradeIn(BaseModel):
    symbol: str
    side: Literal["long", "short"]
    entry: float | None = None  # default: the latest price
    stop: float | None = None
    trim: float | None = None
    target: float | None = None
    weight: float | None = None  # % of the account (default: 1% risk at the stop, max 20%)


@router.post("/paper-trades/chart")
def take_chart(body: ChartTradeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """A manual Buy / Short from the chart, with your own levels; followed separately ("Chart trades")."""
    from engine.indicators import atr

    from .. import market_data
    from ..models import PaperTrade

    sym = body.symbol.upper().strip()
    try:
        df = market_data.history(sym)
    except Exception:
        raise HTTPException(404, f"No data found for {sym}")
    price = float(df["close"].iloc[-1])
    entry = body.entry or price
    long = body.side == "long"
    a = float(atr(df, 14).iloc[-1]) or entry * 0.02
    stop = body.stop or (entry - 2 * a if long else entry + 2 * a)
    if (long and stop >= entry) or (not long and stop <= entry):
        raise HTTPException(400, "The stop must be below the entry for a buy and above it for a short.")
    risk = abs(entry - stop)
    target = body.target or (entry + 3 * risk if long else entry - 3 * risk)
    if (long and target <= entry) or (not long and target >= entry):
        raise HTTPException(400, "The target must be above the entry for a buy and below it for a short.")
    trim = body.trim
    if trim is not None and not (min(entry, target) < trim < max(entry, target)):
        raise HTTPException(400, "The trim level must be between the entry and the target.")
    weight = body.weight or round(min(20.0, 1 / (risk / entry)), 1)
    t = PaperTrade(user_id=user.id, idea_id=None, symbol=sym, timeframe="CH", side=body.side, entry_date=df.index[-1].date(),
                   entry=round(entry, 4), stop=round(stop, 4), trim=round(trim, 4) if trim else None, target=round(target, 4), weight=weight)
    db.add(t)
    db.commit()
    from .community import copy_new_trade

    copy_new_trade(db, t)  # copy trading: followers get the same trade
    return _paper_out(t, df)


@router.post("/paper-trades/chart/sell")
def sell_chart(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Sell from the chart: close your open chart position(s) in the symbol at the latest price."""
    from .. import market_data
    from ..models import PaperTrade

    sym = str(body.get("symbol") or "").upper().strip()
    df = market_data.history(sym)
    closed = []
    for t in db.scalars(select(PaperTrade).where(PaperTrade.user_id == user.id, PaperTrade.symbol == sym, PaperTrade.timeframe == "CH",
                                                 PaperTrade.exit_date.is_(None))).all():
        if _paper_out(t, df)["open"]:
            t.exit_price, t.exit_date = round(float(df["close"].iloc[-1]), 4), df.index[-1].date()
            closed.append(t)
    if not closed:
        raise HTTPException(404, f"You have no open chart position in {sym}. Use Short to sell short.")
    db.commit()
    from .community import close_copies

    for t in closed:
        close_copies(db, t)
    return [_paper_out(t, df) for t in closed]


def scan_plan(symbol: str, side: str, db: Session) -> dict:
    """Plan for a Move Detector trade: vnicornAI's best plan when the model exists, otherwise rules
    (long: VCP stop or 2 ATR; short: 2 ATR above), trim 1.5R, target 3R."""
    from engine import vnicorn_ai
    from engine.indicators import atr
    from engine.vcp import detect_vcp

    from .. import market_data, vnicorn_service

    df = market_data.history(symbol)
    try:
        bench = market_data.history("SPY")
    except Exception:
        bench = None
    bundle = vnicorn_service.load(db)
    if bundle is not None:
        plan = vnicorn_ai.best_plan(bundle, df, bench, side)
        if plan:
            return {**plan, "source": "vnicornAI", "df": df}
    plan = vnicorn_ai.rules_plan(df, side)
    if plan is None:
        raise HTTPException(400, f"Not enough price history for {symbol} yet to build a plan.")
    return {**plan, "source": "rules", "df": df}


@router.post("/paper-trades/scan")
def take_scan(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Buy / Short a Move Detector stock now; followed separately from the idea trades (timeframe "MD")."""
    from ..models import PaperTrade

    if not limits_for(user)["move_detector"]:
        raise HTTPException(403, "Move Detector is available on the Pro and Premium plans.")
    sym = str(body.get("symbol") or "").upper().strip()
    side = body.get("side")
    if not sym or side not in ("long", "short"):
        raise HTTPException(400, "symbol and side (long/short) are required")
    mine = db.scalars(select(PaperTrade).where(PaperTrade.user_id == user.id, PaperTrade.symbol == sym, PaperTrade.timeframe == "MD")).all()
    if mine:
        from .. import market_data

        df_now = market_data.history(sym)
        if any(_paper_out(t, df_now)["open"] for t in mine):
            raise HTTPException(409, f"You already have an open Move Detector trade in {sym}")
    try:
        plan = scan_plan(sym, side, db)
    except Exception:
        raise HTTPException(404, f"No data found for {sym}")
    df = plan.pop("df")
    weight = round(min(20.0, 1 / (abs(plan["entry"] - plan["stop"]) / plan["entry"])), 1) if plan["entry"] != plan["stop"] else 0.0
    t = PaperTrade(user_id=user.id, idea_id=None, symbol=sym, timeframe="MD", side=side, entry_date=df.index[-1].date(),
                   entry=plan["entry"], stop=plan["stop"], trim=plan["trim"], target=plan["target"], weight=weight)
    db.add(t)
    db.commit()
    return {**_paper_out(t, df), "plan_source": plan["source"]}


@router.get("/paper-trades")
def paper_trades(source: Literal["all", "ideas", "md", "chart", "copy"] = "all", user: User = Depends(current_user), db: Session = Depends(get_db)):
    from engine.paper import summary

    from .. import market_data
    from ..models import PaperTrade

    rows = []
    q = _paper_filter(select(PaperTrade).where(PaperTrade.user_id == user.id), source)
    for t in db.scalars(q.order_by(PaperTrade.created_at.desc())).all():
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


# ---------------- TradeGrader & analytics ----------------

def _trades_for(user: User, db: Session, source: str, portfolio_id: int | None = None) -> list[dict]:
    """Trades to grade: paper trades (ideas / Move Detector) and/or portfolio round trips."""
    from engine.trade_grader import round_trips

    from .. import market_data
    from ..models import PaperTrade, Portfolio, PortfolioTxn

    out = []
    if source in ("all", "backtest", "ideas", "md", "chart", "copy"):
        q = _paper_filter(select(PaperTrade).where(PaperTrade.user_id == user.id), source if source != "backtest" else "all")
        for t in db.scalars(q).all():
            try:
                df = market_data.history(t.symbol)
            except Exception:
                continue
            f = _paper_out(t, df)
            out.append({"source": {"MD": "Move Detector", "CH": "Charts", "CP": "Copied"}.get(t.timeframe, "Trade ideas"), "symbol": t.symbol, "side": t.side,
                        "entry_date": t.entry_date.isoformat(), "entry_price": t.entry, "stop": t.stop,
                        "exit_date": f["closed_at"], "exit_price": f["exit_price"], "ref": f"paper:{t.id}"})
    if source in ("all", "portfolio"):
        from .portfolios import _active_ids

        q = select(Portfolio).where(Portfolio.user_id == user.id, Portfolio.id.in_(_active_ids(db, user)))  # locked portfolios are skipped
        if portfolio_id:
            q = q.where(Portfolio.id == portfolio_id)
        for p in db.scalars(q).all():
            from ..models import TxnOrigin

            rows_ = db.scalars(select(PortfolioTxn).where(PortfolioTxn.portfolio_id == p.id)).all()
            stmt = set(db.scalars(select(TxnOrigin.txn_id).where(TxnOrigin.txn_id.in_([x.id for x in rows_]), TxnOrigin.origin == "statement")).all()) if rows_ else set()
            # positions imported before the origin was recorded: a statement shows up as several buys on one day
            from collections import Counter

            buys_per_day = Counter(x.date for x in rows_ if x.side == "buy")
            txns = [{"date": x.date.isoformat(), "symbol": x.symbol, "side": x.side, "shares": x.shares, "price": x.price,
                     "statement": x.id in stmt or (x.side == "buy" and buys_per_day[x.date] >= 3 and not stmt)}
                    for x in rows_]
            for i, rt in enumerate(round_trips(txns)):
                out.append({**rt, "source": f"Portfolio: {p.name}", "ref": f"pf:{p.id}:{i}"})
    return out


def _graded(user: User, db: Session, source: str, portfolio_id: int | None) -> list[dict]:
    from engine.trade_grader import grade_trade

    from .. import market_data

    rows = []
    for t in _trades_for(user, db, source, portfolio_id):
        try:
            df = market_data.history(t["symbol"])
        except Exception:
            continue
        rows.append(grade_trade(t, df))
    rows.sort(key=lambda r: str(r.get("exit_date") or r.get("entry_date")), reverse=True)
    return rows


@router.get("/grader")
def grader(source: Literal["all", "backtest", "ideas", "md", "chart", "copy", "portfolio"] = "all", portfolio_id: int | None = None,
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    """TradeGrader: Bought / Sold Perfect, Early or Late, plus an A-F grade for every trade."""
    from engine.trade_grader import aggregate

    if not limits_for(user)["backtesting"] and source not in ("chart", "portfolio", "copy"):
        source = "chart"  # Free: your own trades (charts, portfolios); Trade ideas / Move Detector trades are Pro
    rows = _graded(user, db, source, portfolio_id)
    return {"trades": rows, "summary": aggregate(rows)}


@router.get("/grader/chart")
def grader_chart(symbol: str, start: str, end: str | None = None, user: User = Depends(current_user)):
    """Daily candles around a trade, for the TradeGrader chart."""
    import pandas as pd

    from engine.strategies.base import t as ts

    from .. import market_data

    df = market_data.history(symbol.upper())
    a = df.index.searchsorted(pd.Timestamp(start)) - 40
    b = df.index.searchsorted(pd.Timestamp(end or df.index[-1])) + 30
    d = df.iloc[max(0, a): b]
    return [{"time": ts(i), "open": round(float(r.open), 2), "high": round(float(r.high), 2), "low": round(float(r.low), 2),
             "close": round(float(r.close), 2), "volume": int(r.volume)} for i, r in d.iterrows()]


@router.get("/analytics")
def trade_analytics(source: Literal["all", "backtest", "ideas", "md", "chart", "copy", "portfolio"] = "all", portfolio_id: int | None = None,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    """TradingLogger-style statistics over your closed trades."""
    from engine.trade_grader import analytics

    if not limits_for(user)["backtesting"] and source not in ("chart", "portfolio", "copy"):
        source = "chart"
    from ..models import TradeNote

    graded = _graded(user, db, source, portfolio_id)
    out = analytics(graded)
    notes = {n.ref: n for n in db.scalars(select(TradeNote).where(TradeNote.user_id == user.id)).all()}
    for key in ("setup", "emotion"):
        groups: dict[str, list[float]] = {}
        for t in graded:
            n = notes.get(t.get("ref", ""))
            v = getattr(n, key, "") if n else ""
            if v and t.get("exit_date") and t.get("pnl_pct") is not None:
                groups.setdefault(v, []).append(t["pnl_pct"])
        out[f"by_{key}"] = sorted(({"name": k, "trades": len(v), "win_rate": round(100 * sum(x > 0 for x in v) / len(v)),
                                    "avg_pct": round(sum(v) / len(v), 2)} for k, v in groups.items()), key=lambda x: -x["avg_pct"])
    return out
