from datetime import date
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from engine import market_tools as mt
from engine.data.universe import SYMBOLS, stock_symbols

from .. import market_data
from ..config import settings
from ..models import User
from ..plans import gate_rows, limits_for
from ..security import current_user
from .sepa import cached_scan

router = APIRouter(prefix="/api/markets", tags=["markets"])

INDICES = [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("DIA", "Dow Jones"), ("IWM", "Russell 2000"), ("^VIX", "VIX")]


def _histories(symbols: list[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for s in symbols:
        try:
            out[s] = market_data.stored_history(s)
        except Exception:
            continue
    return out


def _opt(symbol: str) -> pd.DataFrame | None:
    try:
        return market_data.history(symbol)
    except Exception:
        return None


def _rows(region: str = "US") -> list[dict]:
    """Price / change / volume rows for one region's stocks (US by default)."""
    key = f"{settings.data_provider}:movers" + ("" if region == "US" else f":{region}")
    return market_data._fast(key, market_data.screen_ttl(300), lambda: mt.mover_rows(_histories(stock_symbols(region)), SYMBOLS), stale_ok=True)


def _fear_greed() -> dict:
    def build():
        spy = market_data.history("SPY")
        return mt.fear_greed(spy, _opt("^VIX"), _histories(stock_symbols()), _opt("TLT"), _opt("HYG"), _opt("LQD"))

    return market_data._fast(f"{settings.data_provider}:fg", 300, build, stale_ok=True)


def _indices() -> list[dict]:
    return market_data._fast(f"{settings.data_provider}:indices", 60, _build_indices, stale_ok=True)


def _build_indices() -> list[dict]:
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
        "cycle": _cycle(),
        "gainers": mt.movers(rows, "gainers", 5),
        "losers": mt.movers(rows, "losers", 5),
        "active": mt.movers(rows, "active", 5),
        "sectors": mt.sector_rotation(rows, cached_scan()),
        "leaders": gate_rows(mt.leaders(cached_scan(), 8), limits_for(user)),
        "exposure": _gate_exposure(_exposure(), limits_for(user)),
        "breadth": {
            "advancing": sum(r["change_pct"] > 0 for r in rows), "declining": sum(r["change_pct"] < 0 for r in rows),
            "new_highs": sum(r["new_high"] for r in rows), "new_lows": sum(r["new_low"] for r in rows),
            "pct_above_ma50": round(100 * sum(r["above_ma50"] for r in rows) / len(rows)) if rows else None,
        },
    }


def _cycle() -> list[dict]:
    """Market cycle stage (Accumulation / Markup / Distribution / Markdown) of the main indexes."""
    return market_data._fast(f"{settings.data_provider}:cycle", 1800, _build_cycle, stale_ok=True)


def _build_cycle() -> list[dict]:
    from engine.stages import stage_now

    out = []
    for sym, label in (("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("IWM", "Russell 2000")):
        try:
            st = stage_now(market_data.history(sym))
        except Exception:
            st = None
        if st:
            out.append({"symbol": sym, "label": label, **st})
    return out


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
    return gate_rows(mt.leaders(cached_scan(), limit), limits_for(user))


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

    return {"demo": settings.data_provider == "synthetic", **market_data._fast(f"{settings.data_provider}:earnings", 900, build, stale_ok=True)}


@router.get("/fed")
def fed(user: User = Depends(current_user)):
    try:
        return market_data.fed()
    except Exception:
        raise HTTPException(503, "Federal Reserve data is temporarily unavailable")


@router.get("/screener/presets")
def screener_presets(user: User = Depends(current_user)):
    stocks = set(stock_symbols(None))
    sectors = sorted({m["sector"] for s, m in SYMBOLS.items() if s in stocks})
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
    q: str | None = Query(None, max_length=40),
    region: Literal["US", "EU", "ASIA"] = "US",
    sort: str = "market_cap_b",
    dir: Literal["asc", "desc"] = "desc",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(current_user),
):
    """One page of the screen (50 rows by default), largest companies first unless another column is chosen."""
    paid = limits_for(user)["move_detector"]
    if preset and preset not in mt.PRESETS:
        raise HTTPException(400, f"Unknown preset: {preset}")
    if not paid and (preset or sector or min_cap_b or max_pe or min_yield or min_rs or min_growth is not None or template_only or above_ma50):
        raise HTTPException(403, "Screens and filters are available on the Pro and Premium plans.")
    out = mt.screen(_screen_rows(region), preset, sector, min_cap_b, max_pe, min_yield, min_rs, min_growth, template_only, above_ma50)
    if q and q.strip():  # search by ticker or company name (every plan)
        needle = q.strip().upper()
        out = [r for r in out if needle in r["symbol"].upper() or needle in (r.get("name") or "").upper()]
    groups = limits_for(user)["industry_groups"]
    if groups:
        from engine.industry import symbol_ranks

        ranks = symbol_ranks(groups_ranked())
        out = [{**r, "group": ranks.get(r["symbol"], {}).get("group"), "group_rank": ranks.get(r["symbol"], {}).get("rank")} for r in out]
    allowed = SCREEN_SORT_FREE | (SCREEN_SORT_PAID if paid else set()) | ({"group_rank"} if groups else set())
    key = sort if sort in allowed else "market_cap_b"
    present = [r for r in out if r.get(key) is not None]
    missing = [r for r in out if r.get(key) is None]  # empty values always last
    present.sort(key=lambda r: (str(r[key]).upper() if key == "symbol" else r[key]), reverse=dir == "desc")
    out = present + missing
    if q and q.strip():  # the exact ticker first, then tickers starting with the search, then name matches
        needle = q.strip().upper()
        out.sort(key=lambda r: (r["symbol"].upper() != needle, not r["symbol"].upper().startswith(needle)))
    page = out[offset:offset + limit]
    if not paid:  # Free: the general information only (price, market cap, valuation, dividend)
        page = [{k: v for k, v in r.items() if k not in mt.PAID_SCREEN_FIELDS} for r in page]
    return {"count": len(out), "offset": offset, "has_more": offset + limit < len(out), "results": page, "locked": not paid,
            "sort": key, "dir": dir, "loading": market_data.loading()}


SCREEN_SORT_FREE = {"symbol", "price", "change_pct", "market_cap_b", "pe", "pe_vs_sector_pct", "eps_growth", "dividend_yield"}
SCREEN_SORT_PAID = {"rsi14", "rs_rating", "template_passed", "from_ath_pct", "bull_score"}


def _screen_rows(region: str = "US") -> list[dict]:
    """The screener table for one region, shared by every user (refreshed in the background every 2 minutes)."""
    def build():
        syms = stock_symbols(region)
        fundamentals = {s: market_data.cached("fundamentals", s) or {} for s in syms}
        aths = {s: market_data.cached("ath", s) for s in syms}
        rows = mt.screen_rows(_rows(region), cached_scan(region), fundamentals, aths)
        return [{**r, "currency": SYMBOLS.get(r["symbol"], {}).get("currency", "USD"),
                 "country": SYMBOLS.get(r["symbol"], {}).get("country", "")} for r in rows]

    key = f"{settings.data_provider}:screen-rows" + ("" if region == "US" else f":{region}")
    return market_data._fast(key, market_data.screen_ttl(120), build, stale_ok=True)


@router.get("/regions")
def regions(user: User = Depends(current_user)):
    """The regions this server scans (US always; Europe / Asia when INTL_MARKETS is set)."""
    from engine.data.intl import REGION_NAMES, enabled_regions

    return {"regions": [{"id": r, "name": REGION_NAMES[r], "stocks": len(stock_symbols(r))} for r in enabled_regions(settings.intl_markets)]}


# ------------------------------------------------------------------ exposure meter & industry groups

def _exposure() -> dict | None:
    def build():
        from engine.exposure import exposure

        spy = _opt("SPY")
        if spy is None or len(spy) < 200:
            return None
        try:
            fg = _fear_greed().get("score")
        except Exception:
            fg = None
        return exposure(spy, _opt("QQQ"), _rows(), fg)

    return market_data._fast(f"{settings.data_provider}:exposure", 300, build, stale_ok=True)


def _gate_exposure(e: dict | None, lim: dict) -> dict | None:
    """Free: the label and the advice; Pro / Premium: the percentage and the reasons too."""
    if e is None or lim["exposure_details"]:
        return e
    return {"label": e["label"], "advice": e["advice"], "locked": True}


@router.get("/exposure")
def exposure_meter(user: User = Depends(current_user)):
    e = _exposure()
    if e is None:
        raise HTTPException(503, "Not enough index history yet")
    return _gate_exposure(e, limits_for(user))


def groups_ranked() -> list[dict]:
    def build():
        from engine.industry import rank_groups

        inds = {s: (market_data.cached("fundamentals", s) or {}).get("industry", "") for s in stock_symbols()}
        return rank_groups(_rows(), cached_scan(), inds)

    return market_data._fast(f"{settings.data_provider}:groups", 1800, build, stale_ok=True)


@router.get("/groups")
def industry_groups(user: User = Depends(current_user)):
    if not limits_for(user)["industry_groups"]:
        raise HTTPException(403, "Industry group rankings are part of Premium.")
    g = groups_ranked()
    return {"count": len(g), "groups": g}
