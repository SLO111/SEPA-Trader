from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from engine.data.universe import NON_STOCK_SECTORS, SYMBOLS
from engine.report import build_pdf, period_returns, takeaways, verdict
from engine.scanner import sepa_report

from .. import market_data
from ..models import User
from ..plans import limits_for
from ..security import current_user
from .sepa import _rs_for, cached_scan

router = APIRouter(prefix="/api/stock", tags=["stock"])


def _peers(symbol: str, sector: str) -> list[dict]:
    rs = {r["symbol"]: r["rs_rating"] for r in cached_scan()}
    candidates = [s for s, m in SYMBOLS.items() if m["sector"] == sector and s != symbol and m["sector"] not in NON_STOCK_SECTORS]
    rows = []
    for s in candidates:
        try:
            q = market_data.quote(s)
            f = market_data.cached("fundamentals", s) or {"name": SYMBOLS[s]["name"]}
        except Exception:
            continue
        rows.append({"symbol": s, "name": f.get("name", s), "price": q["price"], "change_pct": q["change_pct"],
                     "market_cap_b": f.get("market_cap_b"), "pe": f.get("pe"), "dividend_yield": f.get("dividend_yield"), "rs_rating": rs.get(s)})
    rows.sort(key=lambda r: -(r["market_cap_b"] or 0))
    return rows[:6]


def _build(symbol: str, user: User) -> dict:
    symbol = symbol.upper().strip()
    market_data.watch(symbol)
    try:
        hist = market_data.history(symbol)
    except Exception:
        raise HTTPException(404, f"No data found for {symbol}")
    co = market_data.company(symbol)
    quote = market_data.quote(symbol)
    returns = period_returns(hist["close"])
    from ..plans import gate_sepa

    sepa_full = sepa_report(market_data.history, symbol, _rs_for(symbol))
    sepa = gate_sepa(sepa_full, limits_for(user))
    if not limits_for(user)["move_detector"]:
        sepa["move_detector"] = None
    peers = _peers(symbol, co.get("sector") or SYMBOLS.get(symbol, {}).get("sector", ""))
    items = takeaways(co, sepa, returns, [p["pe"] for p in peers] + [co.get("valuation", {}).get("pe")])
    from engine.key_facts import key_facts
    from engine.stages import stage_now

    facts = market_data._fast(f"keyfacts:{symbol}:{'pro' if limits_for(user)['sepa_details'] else 'free'}", 6 * 3600, lambda: key_facts(co, hist, stage_now(hist), sepa, peers))
    return {"company": co, "quote": quote, "returns": returns, "sepa": sepa, "peers": peers, "takeaways": items, "verdict": verdict(items),
            "key_facts": facts, "history": hist}


@router.get("/{symbol}")
def stock(symbol: str, user: User = Depends(current_user)):
    data = _build(symbol, user)
    data.pop("history")
    return data


@router.get("/{symbol}/report.pdf")
def report(symbol: str, user: User = Depends(current_user)):
    if not limits_for(user)["reports"]:
        raise HTTPException(403, "PDF reports are available on the Premium plan.")
    d = _build(symbol, user)
    pdf = build_pdf(d["company"], d["quote"], d["history"], d["sepa"], d["takeaways"], d["returns"], d["peers"])
    name = f"{d['company']['symbol']}-report-{d['quote']['date']}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{symbol}/quarterly")
def quarterly(symbol: str, user: User = Depends(current_user)):
    """Quarterly EPS and sales growth with acceleration. Free: the latest quarter only."""
    from engine.quarterly import growth_table

    sym = symbol.upper().strip()
    e = market_data.cached("earnings", sym) or {}
    t = growth_table(e.get("history") or [], market_data.quarterly_revenue(sym))
    if not limits_for(user)["eps_history"]:
        t = {"quarters": t["quarters"][:1], "eps_accelerating": None, "revenue_accelerating": None, "canslim_c": t["canslim_c"], "locked": True}
    if limits_for(user)["industry_groups"]:
        from engine.industry import symbol_ranks

        from .markets import groups_ranked

        t["group"] = symbol_ranks(groups_ranked()).get(sym)
    return {"symbol": sym, **t}


@router.get("/{symbol}/technicals")
def technicals(symbol: str, interval: str = "1d", user: User = Depends(current_user)):
    """Technical rating (15 moving averages + 11 oscillators) on 1 hour, 1 day or 1 week bars."""
    from engine.technicals import rating

    sym = symbol.upper().strip()
    if interval not in ("1h", "1d", "1wk"):
        raise HTTPException(400, "interval must be 1h, 1d or 1wk")

    def build():
        if interval == "1h":
            df = market_data.chart_data(sym, "1h")
            if "session" in df.columns:
                df = df[df["session"] == "regular"]
        elif interval == "1wk":
            df = market_data.history(sym, "1wk", 10)
        else:
            df = market_data.history(sym)
        return {"symbol": sym, "interval": interval, **rating(df)}

    try:
        return market_data._fast(f"tech:{sym}:{interval}", 300, build)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, f"No data for {sym} on {interval}")



# ------------------------------------------------------------------ scorecard: health, fair value, members' sentiment

def _sentiment(db, symbol: str, user_id: int | None = None) -> dict:
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from ..models import SentimentVote

    since = datetime.now(timezone.utc) - timedelta(days=30)
    votes = db.scalars(select(SentimentVote).where(SentimentVote.symbol == symbol, SentimentVote.voted_at >= since)).all()
    bull = sum(v.vote == "bull" for v in votes)
    mine = next((v.vote for v in votes if v.user_id == user_id), None) if user_id else None
    n = len(votes)
    return {"votes": n, "bullish_pct": round(bull / n * 100) if n else None, "bearish_pct": round((n - bull) / n * 100) if n else None, "mine": mine}


@router.get("/{symbol}/scorecard")
def scorecard(symbol: str, user: User = Depends(current_user)):
    """Company's health (everyone; categories on Pro), fair value (label on Free, price on Pro) and members' sentiment."""
    from engine.stages import stage_now
    from engine.valuation import fair_value, health

    from ..db import SessionLocal

    sym = symbol.upper().strip()
    lim = limits_for(user)

    def build():
        co = market_data.company(sym)
        try:
            df = market_data.history(sym)
            price = float(df["close"].iloc[-1])
            st = stage_now(df)
        except Exception:
            price, st = None, None
        try:
            sepa = sepa_report(market_data.history, sym, _rs_for(sym))
        except Exception:
            sepa = None
        sector_pe = None
        try:
            from engine import market_tools as mt

            from .markets import _rows
            from .sepa import cached_scan

            funds = {s: market_data.cached("fundamentals", s) or {} for s in [r["symbol"] for r in _rows()]}
            row = next((r for r in mt.screen_rows(_rows(), cached_scan(), funds) if r["symbol"] == sym), None)
            sector_pe = row.get("sector_pe") if row else None
        except Exception:
            pass
        return {"health": health(co, sepa, st["stage"] if st else None), "fair_value": fair_value(co, price, sector_pe), "price": price}

    data = market_data._fast(f"scorecard:{sym}", 6 * 3600, build)
    h, fv = dict(data["health"]), dict(data["fair_value"])
    if not lim["sepa_details"]:
        h = {"score": h["score"], "label": h["label"], "categories_locked": True}
        fv = {"label": fv["label"], "locked": True}
    with SessionLocal() as db:
        sent = _sentiment(db, sym, user.id)
    return {"symbol": sym, "price": data["price"], "health": h, "fair_value": fv, "sentiment": sent}


class VoteIn(BaseModel):
    vote: Literal["bull", "bear"]


@router.post("/{symbol}/sentiment")
def vote(symbol: str, body: VoteIn, user: User = Depends(current_user)):
    from datetime import datetime, timezone

    from sqlalchemy import select

    from ..db import SessionLocal
    from ..models import SentimentVote

    sym = symbol.upper().strip()
    with SessionLocal() as db:
        v = db.scalar(select(SentimentVote).where(SentimentVote.user_id == user.id, SentimentVote.symbol == sym))
        if v is None:
            v = SentimentVote(user_id=user.id, symbol=sym, vote=body.vote)
            db.add(v)
        else:
            v.vote, v.voted_at = body.vote, datetime.now(timezone.utc)
        db.commit()
        return _sentiment(db, sym, user.id)
