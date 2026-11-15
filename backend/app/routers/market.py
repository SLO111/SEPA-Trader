from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from engine.data.universe import SYMBOLS, search
from engine.strategies import REGISTRY, list_strategies, run_strategy

from .. import market_data
from ..models import User
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/market/search")
def search_symbols(q: str = Query(min_length=1, max_length=40), user: User = Depends(current_user)):
    return search(q)


@router.get("/market/candles/{symbol}")
def candles(symbol: str, interval: str = "1d", years: int = Query(3, ge=1, le=10), user: User = Depends(current_user)):
    try:
        df = market_data.history(symbol, interval, years)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(404, f"Nu am gasit date pentru {symbol.upper()}")
    rows = [
        {
            "time": ts.strftime("%Y-%m-%d"),
            "open": round(float(r.open), 2),
            "high": round(float(r.high), 2),
            "low": round(float(r.low), 2),
            "close": round(float(r.close), 2),
            "volume": int(r.volume),
        }
        for ts, r in df.iterrows()
    ]
    meta = SYMBOLS.get(symbol.upper(), {"name": symbol.upper(), "sector": "", "exchange": ""})
    return {
        "symbol": symbol.upper(),
        **meta,
        "quote": market_data.quote(symbol),
        "delay_minutes": limits_for(user)["data_delay_minutes"],
        "candles": rows,
    }


@router.get("/market/quotes")
def quotes(symbols: str = Query(max_length=2000), user: User = Depends(current_user)):
    out = []
    for s in [x.strip().upper() for x in symbols.split(",") if x.strip()][:200]:
        try:
            out.append(market_data.quote(s))
        except Exception:
            out.append({"symbol": s, "error": "fara date"})
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
        raise HTTPException(403, f"Planul tau permite maximum {limit} strategii pe chart.")
    unknown = [s.id for s in body.strategies if s.id not in REGISTRY]
    if unknown:
        raise HTTPException(400, f"Strategii necunoscute: {', '.join(unknown)}")
    try:
        df = market_data.history(body.symbol, body.interval)
    except Exception:
        raise HTTPException(404, f"Nu am gasit date pentru {body.symbol.upper()}")
    return {s.id: run_strategy(s.id, df, s.params) for s in body.strategies}
