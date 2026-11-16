from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import market_data
from ..db import get_db
from ..models import User, Watchlist, WatchlistItem
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


class WatchlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")


class WatchlistPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class ItemIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9.\-^=]+$")


def wl_out(w: Watchlist) -> dict:
    return {"id": w.id, "name": w.name, "color": w.color, "symbols": [i.symbol for i in w.items]}


def _get_owned(db: Session, user: User, wl_id: int) -> Watchlist:
    w = db.get(Watchlist, wl_id)
    if w is None or w.user_id != user.id:
        raise HTTPException(404, "Watchlist not found")
    return w


@router.get("")
def list_watchlists(user: User = Depends(current_user)):
    return [wl_out(w) for w in user.watchlists]


@router.post("")
def create_watchlist(body: WatchlistIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit = limits_for(user)["max_watchlists"]
    if len(user.watchlists) >= limit:
        raise HTTPException(403, f"Your plan allows up to {limit} watchlist(s). Upgrade to create more.")
    w = Watchlist(user_id=user.id, name=body.name.strip(), color=body.color, position=len(user.watchlists))
    db.add(w)
    db.commit()
    from ..alerts_service import ensure_watchlist_rules

    ensure_watchlist_rules(db, user)  # alerts for the new list's symbols, automatically
    return wl_out(w)


@router.patch("/{wl_id}")
def update_watchlist(wl_id: int, body: WatchlistPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = _get_owned(db, user, wl_id)
    if body.name is not None:
        w.name = body.name.strip()
    if body.color is not None:
        w.color = body.color
    db.commit()
    return wl_out(w)


@router.delete("/{wl_id}", status_code=204)
def delete_watchlist(wl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_get_owned(db, user, wl_id))
    db.commit()


@router.post("/{wl_id}/items")
def add_item(wl_id: int, body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = _get_owned(db, user, wl_id)
    symbol = body.symbol.upper()
    if any(i.symbol == symbol for i in w.items):
        return wl_out(w)
    limit = limits_for(user)["max_symbols_per_watchlist"]
    if len(w.items) >= limit:
        raise HTTPException(403, f"Your plan allows up to {limit} symbols per watchlist.")
    try:
        market_data.history(symbol)
    except Exception:
        raise HTTPException(404, f"No data found for {symbol}")
    w.items.append(WatchlistItem(symbol=symbol, position=len(w.items)))
    db.commit()
    return wl_out(w)


@router.delete("/{wl_id}/items/{symbol}")
def remove_item(wl_id: int, symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = _get_owned(db, user, wl_id)
    w.items = [i for i in w.items if i.symbol != symbol.upper()]
    for pos, i in enumerate(w.items):
        i.position = pos
    db.commit()
    return wl_out(w)
