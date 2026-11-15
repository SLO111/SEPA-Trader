import time
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from engine.scanner import scan_universe, sepa_report
from engine.sepa import rs_raw, rs_ratings

from .. import market_data
from ..config import settings
from ..models import User
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api/sepa", tags=["sepa"])

_TTL = 300
_scan_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = Lock()


def cached_scan() -> list[dict]:
    key = settings.data_provider
    with _lock:
        hit = _scan_cache.get(key)
        if hit and time.monotonic() - hit[0] < _TTL:
            return hit[1]
        rows = scan_universe(market_data.history)
        _scan_cache[key] = (time.monotonic(), rows)
        return rows


def _rs_for(symbol: str) -> int | None:
    rows = cached_scan()
    by_symbol = {r["symbol"]: r["rs_rating"] for r in rows}
    if symbol in by_symbol:
        return by_symbol[symbol]
    # Simbol din afara universului: il clasam fata de univers.
    raws = {}
    for r in rows:
        try:
            raws[r["symbol"]] = float(rs_raw(market_data.history(r["symbol"])["close"]).iloc[-1])
        except Exception:
            pass
    raws[symbol] = float(rs_raw(market_data.history(symbol)["close"]).iloc[-1])
    return rs_ratings(raws).get(symbol)


@router.get("/scan")
def scan(
    sort: Literal["bull", "bear", "rs"] = "bull",
    min_score: float = Query(0, ge=0, le=100),
    template_only: bool = False,
    vcp_only: bool = False,
    user: User = Depends(current_user),
):
    if not limits_for(user)["move_detector"]:
        raise HTTPException(403, "Move Detector și scanner-ul sunt disponibile în planurile Pro și Premium.")
    rows = cached_scan()
    key = {"bull": "bull_score", "bear": "bear_score", "rs": "rs_rating"}[sort]
    out = [
        r
        for r in rows
        if (r[key] or 0) >= (min_score if sort != "rs" else 0)
        and (not template_only or r["template_passed"] == 8)
        and (not vcp_only or r["vcp"])
    ]
    out.sort(key=lambda r: -(r[key] or 0))
    return {"provider": settings.data_provider, "count": len(out), "results": out}


@router.get("/{symbol}")
def report(symbol: str, user: User = Depends(current_user)):
    symbol = symbol.upper()
    try:
        market_data.history(symbol)
    except Exception:
        raise HTTPException(404, f"Nu am găsit date pentru {symbol}")
    rep = sepa_report(market_data.history, symbol, _rs_for(symbol))
    if not limits_for(user)["move_detector"]:
        # Planul Free vede Trend Template si VCP, dar nu si scorurile Move Detector.
        rep["move_detector"] = None
    return rep
