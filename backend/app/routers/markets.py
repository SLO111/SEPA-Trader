from datetime import date
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from engine import market_tools as mt
from engine.data.universe import SYMBOLS, stock_symbols

from .. import market_data
from ..config import settings
from ..models import User
from ..plans import limits_for
from ..security import current_user
from .sepa import cached_scan

router = APIRouter(prefix="/api/markets", tags=["markets"])

INDICES = [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("DIA", "Dow Jones"), ("IWM", "Russell 2000"), ("^VIX", "VIX")]


def _histories(symbols: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for s in symbols:
        try:
            out[s] = market_data.history(s)
        except Exception:
            continue
    return out


def _opt(symbol: str) -> pd.DataFrame | None:
    try:
        return market_data.history(symbol)
    except Exception:
        return None


def _rows() -> list[dict]:
    return market_data._fast(f"{settings.data_provider}:movers", 300, lambda: mt.mover_rows(_histories(stock_symbols()), SYMBOLS))


def _fear_greed() -> dict:
    def build():
        spy = market_data.history("SPY")
        return mt.fear_greed(spy, _opt("^VIX"), _histories(stock_symbols()), _opt("TLT"), _opt("HYG"), _opt("LQD"))

    return market_data._fast(f"{settings.data_provider}:fg", 300, build)


def _indices() -> list[dict]:
    out = []
    for sym, label in INDICES:
        d = _opt(sym)
        if d is None or len(d) < 2:
            continue
        c = d["close"]
        out.append({"symbol": sym, "label": label, "price": round(float(c.iloc[-1]), 2),
                    "change": round(float(c.iloc[-1] - c.iloc[-2]), 2), "change_pct": round(float(c.iloc[-1] / c.iloc[-2] - 1) * 100, 2),
                    "spark": [round(float(v), 2) for v in c.iloc[-60:]]})
    return out


@router.get("/overview")
def overview(user: User = Depends(current_user)):
    rows = _rows()
    fg = _fear_greed()
    return {
        "demo": settings.data_provider == "synthetic",
        "indices": _indices(),
        "fear_greed": {k: fg.get(k) for k in ("score", "label", "previous", "as_of")},
        "gainers": mt.movers(rows, "gainers", 5),
        "losers": mt.movers(rows, "losers", 5),
        "active": mt.movers(rows, "active", 5),
        "sectors": mt.sector_rotation(rows, cached_scan()),
        "leaders": mt.leaders(cached_scan(), 8),
        "breadth": {
            "advancing": sum(r["change_pct"] > 0 for r in rows), "declining": sum(r["change_pct"] < 0 for r in rows),
            "new_highs": sum(r["new_high"] for r in rows), "new_lows": sum(r["new_low"] for r in rows),
            "pct_above_ma50": round(100 * sum(r["above_ma50"] for r in rows) / len(rows)) if rows else None,
        },
    }


@router.get("/fear-greed")
def fear_greed(user: User = Depends(current_user)):
    return _fear_greed()


@router.get("/movers")
def movers(kind: Literal["gainers", "losers", "active", "unusual_volume", "highs", "lows"] = "gainers", limit: int = Query(20, ge=1, le=100),
           user: User = Depends(current_user)):
    return mt.movers(_rows(), kind, limit)


@router.get("/sectors")
def sectors(user: User = Depends(current_user)):
    return mt.sector_rotation(_rows(), cached_scan())


@router.get("/leaders")
def leaders(limit: int = Query(15, ge=1, le=50), user: User = Depends(current_user)):
    return mt.leaders(cached_scan(), limit)


@router.get("/extended-hours")
def extended_hours(user: User = Depends(current_user)):
    if settings.data_provider == "synthetic":
        return {"available": False, "reason": "Pre-market and after-hours quotes require a live data provider.", "pre_market": [], "after_hours": []}
    try:
        rows = market_data.extended_hours(stock_symbols())
    except Exception:
        raise HTTPException(503, "Extended-hours data is temporarily unavailable")
    names = {s: m["name"] for s, m in SYMBOLS.items()}
    for r in rows:
        r["name"] = names.get(r["symbol"], r["symbol"])
    by = lambda sess: sorted([r for r in rows if r["session"] == sess], key=lambda r: -abs(r["change_pct"]))
    return {"available": True, "reason": None if rows else "The regular session is open, or no extended-hours trades yet.",
            "pre_market": by("pre_market"), "after_hours": by("after_hours")}


@router.get("/earnings")
def earnings(user: User = Depends(current_user)):
    def build():
        entries = {}
        for s in stock_symbols():
            e = market_data.cached("earnings", s)
            if e:
                entries[s] = e
        return mt.earnings_calendar(entries, _histories(list(entries)), SYMBOLS, pd.Timestamp(date.today()))

    return {"demo": settings.data_provider == "synthetic", **market_data._fast(f"{settings.data_provider}:earnings", 900, build)}


@router.get("/fed")
def fed(user: User = Depends(current_user)):
    try:
        return market_data.fed()
    except Exception:
        raise HTTPException(503, "Federal Reserve data is temporarily unavailable")


@router.get("/screener/presets")
def screener_presets(user: User = Depends(current_user)):
    sectors = sorted({m["sector"] for s, m in SYMBOLS.items() if s in stock_symbols()})
    return {"presets": [{"id": k, **v} for k, v in mt.PRESETS.items()], "sectors": sectors}


@router.get("/screener")
def screener(
    preset: str | None = None,
    sector: str | None = None,
    min_cap_b: float | None = Query(None, ge=0),
    max_pe: float | None = Query(None, gt=0),
    min_yield: float | None = Query(None, ge=0),
    min_rs: float | None = Query(None, ge=1, le=99),
    min_growth: float | None = None,
    template_only: bool = False,
    above_ma50: bool = False,
    user: User = Depends(current_user),
):
    if not limits_for(user)["move_detector"]:
        raise HTTPException(403, "The screener is available on the Pro and Premium plans.")
    if preset and preset not in mt.PRESETS:
        raise HTTPException(400, f"Unknown preset: {preset}")
    fundamentals = {s: market_data.cached("fundamentals", s) or {} for s in stock_symbols()}
    rows = mt.screen_rows(_rows(), cached_scan(), fundamentals)
    out = mt.screen(rows, preset, sector, min_cap_b, max_pe, min_yield, min_rs, min_growth, template_only, above_ma50)
    return {"count": len(out), "results": out}
