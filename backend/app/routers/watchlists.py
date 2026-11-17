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


def active_watchlist_ids(user: User) -> set[int]:
    """After a downgrade the oldest watchlists within the plan stay usable; the rest are kept but locked."""
    ws = sorted(user.watchlists, key=lambda w: (w.created_at or 0, w.id) if w.created_at else (0, w.id))
    return {w.id for w in ws[: limits_for(user)["max_watchlists"]]}


def _sections(w: Watchlist, visible: list[str]) -> list[dict]:
    """The list's sections, cleaned against its symbols (removed symbols drop out, each symbol in one section)."""
    import json

    from sqlalchemy.orm import object_session

    from ..models import WatchlistLayout

    db = object_session(w)
    row = db.get(WatchlistLayout, w.id) if db else None
    try:
        data = json.loads(row.data) if row else {}
    except ValueError:
        data = {}
    keep, seen, out = set(visible), set(), []
    for sec in data.get("sections", []):
        syms = [x for x in sec.get("symbols", []) if x in keep and x not in seen]
        seen.update(syms)
        out.append({"id": str(sec.get("id") or len(out)), "name": str(sec.get("name") or "Section")[:40], "symbols": syms,
                    "collapsed": bool(sec.get("collapsed"))})
    return out


def wl_out(w: Watchlist, user: User | None = None) -> dict:
    syms = [i.symbol for i in w.items]
    if user is None:
        return {"id": w.id, "name": w.name, "color": w.color, "symbols": syms, "sections": _sections(w, syms)}
    if w.id not in active_watchlist_ids(user):
        return {"id": w.id, "name": w.name, "color": w.color, "symbols": [], "locked": True, "hidden": len(syms), "sections": []}
    cap = limits_for(user)["max_symbols_per_watchlist"]
    return {"id": w.id, "name": w.name, "color": w.color, "symbols": syms[:cap], "hidden": max(0, len(syms) - cap),
            "sections": _sections(w, syms[:cap])}


def _get_owned(db: Session, user: User, wl_id: int, active: bool = True) -> Watchlist:
    w = db.get(Watchlist, wl_id)
    if w is None or w.user_id != user.id:
        raise HTTPException(404, "Watchlist not found")
    if active and wl_id not in active_watchlist_ids(user):
        n = limits_for(user)["max_watchlists"]
        raise HTTPException(403, f"Your plan includes {n} watchlist{'s' if n != 1 else ''}. Upgrade to use this one, or delete another.")
    return w


@router.get("")
def list_watchlists(user: User = Depends(current_user)):
    return [wl_out(w, user) for w in user.watchlists]


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
    return wl_out(w, user)


@router.patch("/{wl_id}")
def update_watchlist(wl_id: int, body: WatchlistPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = _get_owned(db, user, wl_id)
    if body.name is not None:
        w.name = body.name.strip()
    if body.color is not None:
        w.color = body.color
    db.commit()
    return wl_out(w, user)


@router.delete("/{wl_id}", status_code=204)
def delete_watchlist(wl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_get_owned(db, user, wl_id, active=False))  # locked lists can still be deleted
    db.commit()


@router.post("/{wl_id}/items")
def add_item(wl_id: int, body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = _get_owned(db, user, wl_id)
    symbol = body.symbol.upper()
    if any(i.symbol == symbol for i in w.items):
        return wl_out(w, user)
    limit = limits_for(user)["max_symbols_per_watchlist"]
    if len(w.items) >= limit:
        raise HTTPException(403, f"Your plan allows up to {limit} symbols per watchlist.")
    try:
        market_data.history(symbol)
    except Exception:
        raise HTTPException(404, f"No data found for {symbol}")
    w.items.append(WatchlistItem(symbol=symbol, position=len(w.items)))
    db.commit()
    return wl_out(w, user)


@router.delete("/{wl_id}/items/{symbol}")
def remove_item(wl_id: int, symbol: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    w = _get_owned(db, user, wl_id, active=False)
    w.items = [i for i in w.items if i.symbol != symbol.upper()]
    for pos, i in enumerate(w.items):
        i.position = pos
    db.commit()
    return wl_out(w, user)


class OrderIn(BaseModel):
    symbols: list[str] = Field(max_length=1000)


@router.put("/{wl_id}/order")
def reorder(wl_id: int, body: OrderIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Save the order of the symbols in a watchlist (drag & drop)."""
    w = _get_owned(db, user, wl_id)
    rank = {s.upper(): i for i, s in enumerate(body.symbols)}
    items = sorted(w.items, key=lambda i: (rank.get(i.symbol, len(rank) + i.position)))
    for pos, i in enumerate(items):
        i.position = pos
    w.items = items
    db.commit()
    db.refresh(w)
    return wl_out(w, user)



# ------------------------------------------------------------------ sections (groups inside a list)

class SectionIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=40)
    symbols: list[str] = Field(default_factory=list, max_length=1000)
    collapsed: bool = False


class LayoutIn(BaseModel):
    sections: list[SectionIn] = Field(max_length=50)


def _save_layout(db: Session, w: Watchlist, sections: list[dict]) -> None:
    import json

    from ..models import WatchlistLayout

    row = db.get(WatchlistLayout, w.id) or WatchlistLayout(watchlist_id=w.id)
    row.data = json.dumps({"sections": sections})
    db.add(row)
    db.commit()


@router.put("/{wl_id}/layout")
def set_layout(wl_id: int, body: LayoutIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Save the sections (names, order, which symbols, collapsed). Symbols not in any section are shown first, ungrouped."""
    w = _get_owned(db, user, wl_id)
    _save_layout(db, w, [{**s.model_dump(), "symbols": [x.upper() for x in s.symbols]} for s in body.sections])
    return wl_out(w, user)


@router.get("/presets")
def presets(user: User = Depends(current_user)):
    from engine.data.presets import PRESETS

    return PRESETS


class AddSectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    symbols: list[str] = Field(default_factory=list, max_length=100)


@router.post("/{wl_id}/sections")
def add_section(wl_id: int, body: AddSectionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """New section, optionally with symbols (e.g. a ready-made list). Symbols are added to the list within the plan's limit."""
    import secrets

    w = _get_owned(db, user, wl_id)
    limit = limits_for(user)["max_symbols_per_watchlist"]
    have = [i.symbol for i in w.items]
    added, skipped = [], []
    for raw in body.symbols:
        sym = raw.upper().strip()
        if not sym or sym in have or sym in added:
            if sym in have:
                added.append(sym)
            continue
        if len(have) + len([a for a in added if a not in have]) >= limit:
            skipped.append(sym)
            continue
        try:
            market_data.history(sym)
        except Exception:
            skipped.append(sym)
            continue
        w.items.append(WatchlistItem(symbol=sym, position=len(w.items)))
        added.append(sym)
    db.commit()
    sections = [s for s in _sections(w, [i.symbol for i in w.items])]
    # a symbol lives in one section: the new section takes the ones it lists
    for s in sections:
        s["symbols"] = [x for x in s["symbols"] if x not in added]
    sections.append({"id": secrets.token_hex(4), "name": body.name.strip(), "symbols": added, "collapsed": False})
    _save_layout(db, w, sections)
    out = wl_out(w, user)
    out["skipped"] = skipped
    return out


@router.post("/{wl_id}/group-by-sector")
def group_by_sector(wl_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Sections made automatically from each symbol's sector (ETFs together)."""
    from engine.data.universe import SYMBOLS

    w = _get_owned(db, user, wl_id)
    groups: dict[str, list[str]] = {}
    for i in w.items:
        meta = SYMBOLS.get(i.symbol, {})
        sector = meta.get("sector") or ""
        if not sector:
            f = market_data.cached("fundamentals", i.symbol) or {}
            sector = f.get("sector") or ""
        from engine.data.presets import PRESETS

        etfs = {x for p in PRESETS if p["id"] in ("index-etfs", "sector-etfs") for x in p["symbols"]} | {"TLT", "GLD", "IBIT", "HYG", "LQD"}
        if sector in ("ETF", "Index") or i.symbol in etfs:
            sector = "ETFs"
        groups.setdefault(sector or "Other", []).append(i.symbol)
    order = sorted(groups, key=lambda g: (g != "ETFs", g == "Other", g))
    _save_layout(db, w, [{"id": f"s{k}", "name": g, "symbols": groups[g], "collapsed": False} for k, g in enumerate(order)])
    return wl_out(w, user)
