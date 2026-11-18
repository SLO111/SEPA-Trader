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


_build_lock = Lock()  # one scan build at a time
_rebuilding: set[str] = set()


def invalidate_scan() -> None:
    """New prices: mark every region's scan stale. Requests keep getting the previous scan while a new one is built."""
    with _lock:
        for k, (_, rows) in list(_scan_cache.items()):
            _scan_cache[k] = (float("-inf"), rows)  # stale whatever the clock (monotonic time can be small after boot)


def _scan_key(region: str) -> str:
    return settings.data_provider if region == "US" else f"{settings.data_provider}:{region}"


def _build_scan(key: str, region: str = "US") -> list[dict]:
    from engine.data.intl import BENCHMARKS
    from engine.data.universe import stock_symbols

    with _build_lock:
        syms = stock_symbols(region)
        rows = scan_universe(market_data.stored_history, syms, BENCHMARKS.get(region, "SPY")) if syms else []
        with _lock:
            _scan_cache[key] = (time.monotonic(), rows)
        return rows


def _rebuild_in_background(key: str, region: str) -> None:
    try:
        _build_scan(key, region)
    except Exception:
        import logging

        logging.getLogger("sepa.scan").warning("Scan rebuild failed; serving the previous scan", exc_info=True)
    finally:
        _rebuilding.discard(key)


def cached_scan(region: str = "US") -> list[dict]:
    """The Move Detector scan of one region (US by default), shared by every user (stale-while-revalidate, single build).
    RS ratings rank stocks within their own region, against its benchmark."""
    key = _scan_key(region)
    with _lock:
        hit = _scan_cache.get(key)
        if hit and time.monotonic() - hit[0] < market_data.screen_ttl(_TTL):
            return hit[1]
        if hit and hit[1] and not market_data.in_background():
            if key not in _rebuilding:
                _rebuilding.add(key)
                import threading

                threading.Thread(target=_rebuild_in_background, args=(key, region), name=f"scan-rebuild-{region}", daemon=True).start()
            return hit[1]
    with _build_lock:  # first build: concurrent requests wait for one computation
        with _lock:
            hit = _scan_cache.get(key)
            if hit and time.monotonic() - hit[0] < market_data.screen_ttl(_TTL):
                return hit[1]
    return _build_scan(key, region)


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


def pulse_map(region: str = "US") -> dict[str, dict]:
    """Confirmations / warnings over the last 10 days for every stock of a region (refreshed every 30 minutes)."""
    from engine import pulse
    from engine.data.intl import BENCHMARKS
    from engine.data.universe import stock_symbols

    def build():
        try:
            bench = market_data.stored_history(BENCHMARKS.get(region, "SPY"))
        except Exception:
            bench = None
        out = {}
        for s in stock_symbols(region):
            try:
                p = pulse.summary(market_data.stored_history(s), bench)
                out[s] = {"conf": p["conf"], "warn": p["warn"], "tone": p["tone"]}
            except Exception:
                continue
        return out

    key = f"{settings.data_provider}:pulse-map" + ("" if region == "US" else f":{region}")
    return market_data._fast(key, 1800, build, stale_ok=True)


@router.get("/scan")
def scan(
    sort: Literal["bull", "bear", "rs", "ai"] = "bull",
    min_score: float = Query(0, ge=0, le=100),
    template_only: bool = False,
    vcp_only: bool = False,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    region: Literal["US", "EU", "ASIA"] = "US",
    order: Literal["default", "ai", "bull", "bear", "rs", "tt", "change", "price", "pivot", "symbol"] = "default",
    dir: Literal["asc", "desc"] = "desc",
    user: User = Depends(current_user),
):
    """One page of the scan (50 by default). Order: vnicornAI's major-move probability by default when the plan has it
    (and the model has rated the stocks), otherwise the tab's score; any column can be chosen with `order`."""
    if not limits_for(user)["move_detector"]:
        raise HTTPException(403, "Move Detector and the scanner are available on Pro and Premium plans.")
    from .. import vnicorn_service
    from ..db import SessionLocal

    with SessionLocal() as db:
        vnicorn_service.load(db)  # makes the stored major-move probabilities available after a restart
    pm = pulse_map(region) if limits_for(user)["pulse"] else {}
    ai = limits_for(user)["ai_picks"] and region == "US"  # vnicornAI learns from US stocks
    if sort == "ai" and not ai:
        raise HTTPException(403, "vnicornAI move probabilities are part of Premium.")
    from engine.data.universe import currency_of

    rows = [{**r, "ai_prob": vnicorn_service.move_prob(r["symbol"]) if ai else None, "currency": currency_of(r["symbol"])}
            for r in cached_scan(region)]
    key = {"bull": "bull_score", "bear": "bear_score", "rs": "rs_rating", "ai": "ai_prob"}[sort]
    out = [
        r
        for r in rows
        if (r[key] or 0) >= (min_score if sort in ("bull", "bear") else 0)
        and (not template_only or r["template_passed"] == 8)
        and (not vcp_only or r["vcp"])
    ]
    col = {"ai": "ai_prob", "bull": "bull_score", "bear": "bear_score", "rs": "rs_rating", "tt": "template_passed",
           "change": "change_pct", "price": "price", "pivot": "pivot_distance_pct", "symbol": "symbol"}
    if order == "default":
        rated = ai and sum(1 for r in out if r.get("ai_prob") is not None) >= max(1, len(out) // 2)
        order, dir = ("ai" if rated else sort), "desc"
    if order == "ai" and not ai:
        order = sort
    c = col[order]
    has = [r for r in out if r.get(c) is not None]
    out_missing = [r for r in out if r.get(c) is None]  # empty values always last
    tie = lambda r: (r.get(key) or 0, r.get("rs_rating") or 0)  # noqa: E731 - ties: the tab's score, then RS
    if c == "symbol":
        has.sort(key=lambda r: r["symbol"], reverse=dir == "desc")
    else:
        has.sort(key=lambda r: (r[c], *tie(r)), reverse=dir == "desc")
    out = has + sorted(out_missing, key=tie, reverse=True)
    # Pulse and the earnings badge only for the rows on this page
    page = [{**r, "pulse": pm.get(r["symbol"]), "earnings_in": market_data.earnings_in_days(r["symbol"])} for r in out[offset:offset + limit]]
    return {"provider": settings.data_provider, "count": len(out), "offset": offset, "has_more": offset + limit < len(out),
            "results": page, "loading": market_data.loading(), "order": order, "dir": dir}


@router.get("/pulse/leaders")
def pulse_leaders(limit: int = Query(25, ge=5, le=100), region: Literal["US", "EU", "ASIA"] = "US",
                  user: User = Depends(current_user)):
    """vnicorn Pulse across a region: stocks acting best (most confirmations) and worst (most warnings) over 10 days."""
    from engine.data.universe import SYMBOLS

    if not limits_for(user)["pulse"]:
        raise HTTPException(403, "vnicorn Pulse is available on the Pro and Premium plans.")
    rows = [{"symbol": s, "name": SYMBOLS.get(s, {}).get("name", s), "sector": SYMBOLS.get(s, {}).get("sector", ""),
             "currency": SYMBOLS.get(s, {}).get("currency", "USD"), **p, "net": p["conf"] - p["warn"]} for s, p in pulse_map(region).items()]
    best = sorted(rows, key=lambda r: (-r["net"], -r["conf"]))[:limit]
    worst = sorted(rows, key=lambda r: (r["net"], -r["warn"]))[:limit]
    for r in {id(x): x for x in best + worst}.values():  # quotes only for the rows shown
        try:
            q = market_data.quote(r["symbol"])
            r["price"], r["change_pct"] = q["price"], q["change_pct"]
        except Exception:
            r["price"] = r["change_pct"] = None
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
