from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from engine.strategies import REGISTRY, list_strategies, run_strategy
from engine.strategies.base import t

from .. import market_data
from ..models import User
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/market/search")
def search_symbols(q: str = Query(min_length=1, max_length=40), user: User = Depends(current_user)):
    return market_data.search_symbols(q)


@router.get("/market/candles/{symbol}")
def candles(symbol: str, interval: str = "1d", years: int = Query(3, ge=1, le=10), user: User = Depends(current_user)):
    market_data.watch(symbol)
    try:
        df = market_data.chart_data(symbol, interval, years)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except NotImplementedError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(404, f"No data found for {symbol.upper()}")
    has_session = "session" in df.columns
    rows = [
        {
            "time": t(ts),
            "open": round(float(r.open), 4 if r.close < 1 else 2),
            "high": round(float(r.high), 4 if r.close < 1 else 2),
            "low": round(float(r.low), 4 if r.close < 1 else 2),
            "close": round(float(r.close), 4 if r.close < 1 else 2),
            "volume": int(r.volume),
            **({"session": r.session} if has_session else {}),
        }
        for ts, r in df.iterrows()
    ]
    meta = market_data.symbol_meta(symbol)
    return {
        "symbol": symbol.upper(),
        **meta,
        "quote": market_data.quote(symbol),
        "delay_minutes": limits_for(user)["data_delay_minutes"],
        "live_at": market_data.live_status(symbol),
        "candles": rows,
    }


@router.get("/market/quotes")
def quotes(symbols: str = Query(max_length=2000), user: User = Depends(current_user)):
    out = []
    wanted = [x.strip().upper() for x in symbols.split(",") if x.strip()][:200]
    market_data.watch(*wanted)
    for s in wanted:
        try:
            out.append(market_data.quote(s))
        except Exception:
            out.append({"symbol": s, "error": "no data"})
    return out


@router.get("/strategies")
def strategies(user: User = Depends(current_user)):
    return list_strategies()


class StrategyItem(BaseModel):
    id: str
    params: dict[str, float] = Field(default_factory=dict)


class RunIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    interval: str = "1d"
    strategies: list[StrategyItem] = Field(max_length=50)


@router.post("/strategies/run")
def run(body: RunIn, user: User = Depends(current_user)):
    limit = limits_for(user)["max_strategies_on_chart"]
    if len(body.strategies) > limit:
        raise HTTPException(403, f"Your plan allows up to {limit} strategies on a chart.")
    unknown = [s.id for s in body.strategies if s.id not in REGISTRY]
    if unknown:
        raise HTTPException(400, f"Unknown strategies: {', '.join(unknown)}")
    limits = limits_for(user)
    locked = [REGISTRY[s.id].name for s in body.strategies if REGISTRY[s.id].requires and not limits.get(REGISTRY[s.id].requires)]
    if locked:
        raise HTTPException(403, f"Available on Pro and Premium plans only: {', '.join(locked)}")
    try:
        df = market_data.chart_data(body.symbol, body.interval)
    except Exception:
        raise HTTPException(404, f"No data found for {body.symbol.upper()}")
    bench = None
    if body.interval in ("1d", "1wk", "1mo"):
        try:
            bench = market_data.history("SPY", body.interval)
        except Exception:
            bench = None
    # A list in request order, so the same indicator can be added several times with different settings.
    return {"results": [run_strategy(s.id, df, s.params, bench) for s in body.strategies]}


@router.get("/market/info/{symbol}")
def info(symbol: str, user: User = Depends(current_user)):
    """Everything for the chart's side panel: quote, ranges, volume, key stats, earnings, extended hours, SEPA."""
    sym = symbol.upper().strip()
    market_data.watch(sym)
    try:
        d = market_data.history(sym)
    except Exception:
        raise HTTPException(404, f"No data found for {sym}")
    last = d.iloc[-1]
    y = d.iloc[-252:]
    meta = market_data.symbol_meta(sym)
    f = market_data.fundamentals_fresh(sym) or {}
    e = market_data.cached("earnings", sym) or {}
    from .sepa import cached_scan

    scan = next((r for r in cached_scan() if r["symbol"] == sym), None)
    ext = None
    try:
        rows = market_data.extended_hours([sym])
        ext = rows[0] if rows else None
    except Exception:
        ext = None
    avg_vol = float(d["volume"].iloc[-51:-1].mean())
    return {
        "symbol": sym,
        "name": f.get("name") or meta.get("name", sym),
        "exchange": meta.get("exchange", ""),
        "sector": meta.get("sector") or f.get("sector") or "",
        "industry": f.get("industry", ""),
        "quote": market_data.quote(sym),
        "live_at": market_data.live_status(sym),
        "day": {"open": round(float(last.open), 2), "high": round(float(last.high), 2), "low": round(float(last.low), 2)},
        "week52": {"high": round(float(y["high"].max()), 2), "low": round(float(y["low"].min()), 2)},
        "volume": {"today": int(last.volume), "avg_50d": int(avg_vol), "relative": round(float(last.volume) / avg_vol, 2) if avg_vol else None},
        "stats": {k: f.get(k) for k in ("market_cap_b", "pe", "dividend_yield", "eps_growth", "beta")},
        "next_earnings": e.get("next_date"),
        "extended": ext,
        # Overnight (8 PM - 4 AM ET, e.g. Blue Ocean ATS) needs a paid feed; Yahoo and Finnhub free don't provide it.
        "overnight": None,
        "sepa": {k: scan[k] for k in ("rs_rating", "template_passed", "vcp", "pivot", "bull_score", "bear_score", "signals")} if scan else None,
    }
