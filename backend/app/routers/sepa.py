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

_TTL = 1800  # live mode: also recomputed whenever the store finishes a full price update
_scan_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = Lock()


def invalidate_scan() -> None:
    with _lock:
        _scan_cache.clear()


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
    # Symbol outside the universe: rank it against the universe.
    raws = {}
    for r in rows:
        try:
            raws[r["symbol"]] = float(rs_raw(market_data.history(r["symbol"])["close"]).iloc[-1])
        except Exception:
            pass
    raws[symbol] = float(rs_raw(market_data.history(symbol)["close"]).iloc[-1])
    return rs_ratings(raws).get(symbol)


def pulse_map() -> dict[str, dict]:
    """Confirmations / warnings over the last 10 days for every stock (refreshed every 30 minutes)."""
    from engine import pulse
    from engine.data.universe import stock_symbols

    def build():
        try:
            bench = market_data.history("SPY")
        except Exception:
            bench = None
        out = {}
        for s in stock_symbols():
            try:
                p = pulse.summary(market_data.history(s), bench)
                out[s] = {"conf": p["conf"], "warn": p["warn"], "tone": p["tone"]}
            except Exception:
                continue
        return out

    return market_data._fast(f"{settings.data_provider}:pulse-map", 1800, build)


@router.get("/scan")
def scan(
    sort: Literal["bull", "bear", "rs", "ai"] = "bull",
    min_score: float = Query(0, ge=0, le=100),
    template_only: bool = False,
    vcp_only: bool = False,
    user: User = Depends(current_user),
):
    if not limits_for(user)["move_detector"]:
        raise HTTPException(403, "Move Detector and the scanner are available on Pro and Premium plans.")
    from .. import vnicorn_service
    from ..db import SessionLocal

    with SessionLocal() as db:
        vnicorn_service.load(db)  # makes the stored major-move probabilities available after a restart
    pm = pulse_map() if limits_for(user)["pulse"] else {}
    rows = [{**r, "ai_prob": vnicorn_service.move_prob(r["symbol"]), "pulse": pm.get(r["symbol"])} for r in cached_scan()]
    key = {"bull": "bull_score", "bear": "bear_score", "rs": "rs_rating", "ai": "ai_prob"}[sort]
    out = [
        r
        for r in rows
        if (r[key] or 0) >= (min_score if sort in ("bull", "bear") else 0)
        and (not template_only or r["template_passed"] == 8)
        and (not vcp_only or r["vcp"])
    ]
    out.sort(key=lambda r: -(r[key] or 0))
    return {"provider": settings.data_provider, "count": len(out), "results": out}


@router.get("/pulse/leaders")
def pulse_leaders(limit: int = Query(25, ge=5, le=100), user: User = Depends(current_user)):
    """vnicorn Pulse across the market: stocks acting best (most confirmations) and worst (most warnings) over 10 days."""
    from engine.data.universe import SYMBOLS

    if not limits_for(user)["pulse"]:
        raise HTTPException(403, "vnicorn Pulse is available on the Pro and Premium plans.")
    rows = [{"symbol": s, "name": SYMBOLS.get(s, {}).get("name", s), "sector": SYMBOLS.get(s, {}).get("sector", ""), **p,
             "net": p["conf"] - p["warn"]} for s, p in pulse_map().items()]
    for r in rows:
        try:
            q = market_data.quote(r["symbol"])
            r["price"], r["change_pct"] = q["price"], q["change_pct"]
        except Exception:
            r["price"] = r["change_pct"] = None
    best = sorted(rows, key=lambda r: (-r["net"], -r["conf"]))[:limit]
    worst = sorted(rows, key=lambda r: (r["net"], -r["warn"]))[:limit]
    return {"constructive": best, "warning": worst, "count": len(rows)}


@router.get("/{symbol}")
def report(symbol: str, user: User = Depends(current_user)):
    symbol = symbol.upper()
    try:
        market_data.history(symbol)
    except Exception:
        raise HTTPException(404, f"No data found for {symbol}")
    from ..plans import gate_sepa

    rep = gate_sepa(sepa_report(market_data.history, symbol, _rs_for(symbol)), limits_for(user))
    if not limits_for(user)["move_detector"]:
        # Free plan sees Trend Template and VCP, but not the Move Detector scores.
        rep["move_detector"] = None
    return rep
