from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from engine.journal import Trade, statistics, trade_metrics
from engine.trade_review import review

from .. import market_data
from ..db import get_db
from ..models import JournalTrade, User
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api/journal", tags=["journal"])

SETUPS = ["VCP breakout", "Pivot breakout", "Pullback to MA", "Earnings gap", "Base breakout", "Reversal", "Other"]


def _trade(j: JournalTrade) -> Trade:
    return Trade(j.id, j.symbol, j.side, j.entry_date, j.entry_price, j.shares, j.stop_price, j.target_price, j.exit_date, j.exit_price, j.fees, j.setup)


def _last(symbol: str) -> float | None:
    try:
        return float(market_data.history(symbol)["close"].iloc[-1])
    except Exception:
        return None


def trade_out(j: JournalTrade) -> dict:
    t = _trade(j)
    return {
        "id": j.id, "symbol": j.symbol, "side": j.side, "entry_date": j.entry_date.isoformat(), "entry_price": j.entry_price,
        "shares": j.shares, "stop_price": j.stop_price, "target_price": j.target_price,
        "exit_date": j.exit_date.isoformat() if j.exit_date else None, "exit_price": j.exit_price, "fees": j.fees,
        "setup": j.setup, "notes": j.notes, "last_price": None if t.closed else _last(j.symbol),
        **trade_metrics(t, None if t.closed else _last(j.symbol)),
    }


class TradeIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9.\-^=]+$")
    side: Literal["long", "short"] = "long"
    entry_date: date
    entry_price: float = Field(gt=0, le=1e7)
    shares: float = Field(gt=0, le=1e9)
    stop_price: float | None = Field(default=None, gt=0, le=1e7)
    target_price: float | None = Field(default=None, gt=0, le=1e7)
    exit_date: date | None = None
    exit_price: float | None = Field(default=None, gt=0, le=1e7)
    fees: float = Field(default=0.0, ge=0, le=1e6)
    setup: str = Field(default="", max_length=40)
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def _check(self):
        today = date.today()
        if self.entry_date > today or (self.exit_date and self.exit_date > today):
            raise ValueError("Dates cannot be in the future")
        if (self.exit_date is None) != (self.exit_price is None):
            raise ValueError("Enter both the exit date and exit price, or neither for an open trade")
        if self.exit_date and self.exit_date < self.entry_date:
            raise ValueError("The exit date must be on or after the entry date")
        if self.stop_price:
            wrong = self.stop_price >= self.entry_price if self.side == "long" else self.stop_price <= self.entry_price
            if wrong:
                raise ValueError("The stop must be below the entry for a long trade (above it for a short)")
        return self


def _apply(j: JournalTrade, b: TradeIn) -> None:
    for k, v in b.model_dump().items():
        setattr(j, k, v.upper() if k == "symbol" else v)


def _owned(db: Session, user: User, tid: int) -> JournalTrade:
    j = db.get(JournalTrade, tid)
    if j is None or j.user_id != user.id:
        raise HTTPException(404, "Trade not found")
    return j


@router.get("/setups")
def setups(user: User = Depends(current_user)):
    return SETUPS


@router.get("/trades")
def list_trades(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(JournalTrade).where(JournalTrade.user_id == user.id).order_by(JournalTrade.entry_date.desc(), JournalTrade.id.desc())).all()
    return [trade_out(j) for j in rows]


@router.post("/trades")
def create_trade(body: TradeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit = limits_for(user)["max_journal_trades"]
    n = db.scalar(select(func.count()).select_from(JournalTrade).where(JournalTrade.user_id == user.id)) or 0
    if n >= limit:
        raise HTTPException(403, f"Your plan allows up to {limit} journal trades. Upgrade for an unlimited journal.")
    j = JournalTrade(user_id=user.id)
    _apply(j, body)
    db.add(j)
    db.commit()
    return trade_out(j)


@router.put("/trades/{tid}")
def update_trade(tid: int, body: TradeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = _owned(db, user, tid)
    _apply(j, body)
    db.commit()
    return trade_out(j)


@router.delete("/trades/{tid}", status_code=204)
def delete_trade(tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, user, tid))
    db.commit()


@router.get("/stats")
def stats(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(JournalTrade).where(JournalTrade.user_id == user.id)).all()
    return statistics([_trade(j) for j in rows])


@router.get("/trades/{tid}/review")
def trade_review(tid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not limits_for(user)["trade_review"]:
        raise HTTPException(403, "Trade Review is available on the Premium plan.")
    j = _owned(db, user, tid)
    try:
        df = market_data.history(j.symbol)
    except Exception:
        raise HTTPException(404, f"No price data for {j.symbol}")
    try:
        bench = market_data.history("SPY")
    except Exception:
        bench = None
    return review(_trade(j), df, bench)
