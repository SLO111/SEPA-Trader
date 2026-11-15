from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from engine import backtest as bt
from engine.data.universe import stock_symbols
from engine.strategies import REGISTRY

from .. import market_data
from ..config import settings
from ..models import User
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


def _require(user: User) -> None:
    if not limits_for(user)["backtesting"]:
        raise HTTPException(403, "Backtesting is available on the Premium plan.")


def _dataset():
    def build():
        hist = {}
        # Large universes: test on the 150 largest companies to keep the run fast.
        syms = stock_symbols()
        if len(syms) > 150:
            caps = {s: (market_data.cached("fundamentals", s) or {}).get("market_cap_b") or 0 for s in syms}
            syms = sorted(syms, key=lambda s: -caps[s])[:150]
        for s in syms:
            try:
                hist[s] = market_data.history(s)
            except Exception:
                continue
        try:
            bench = market_data.history("SPY")
        except Exception:
            bench = None
        return bt.build_dataset(hist, bench)

    return market_data._fast(f"{settings.data_provider}:bt-dataset", 3600, build)


@router.get("/move-detector")
def move_detector(user: User = Depends(current_user)):
    """Layer 1 validation plus the layer 3 walk-forward model, cached for an hour."""
    _require(user)

    def build():
        data = _dataset()
        return {
            "demo": settings.data_provider == "synthetic",
            "validation": bt.validate_move_detector(data),
            "ml_up": bt.walk_forward(data, label="up_label", score="bull"),
            "ml_down": bt.walk_forward(data, label="down_label", score="bear"),
        }

    return market_data._fast(f"{settings.data_provider}:bt-md", 3600, build)


class StrategyIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    strategy: str
    params: dict[str, float] = Field(default_factory=dict)
    fees_pct: float = Field(default=0.05, ge=0, le=2)


@router.get("/strategies")
def signal_strategies(user: User = Depends(current_user)):
    """Strategies that produce BUY/SELL signals and can be backtested."""
    return [cls.describe() for cls in REGISTRY.values() if cls.category == "Signals (Bots)"]


@router.post("/strategy")
def strategy(body: StrategyIn, user: User = Depends(current_user)):
    _require(user)
    if body.strategy not in REGISTRY:
        raise HTTPException(400, f"Unknown strategy: {body.strategy}")
    try:
        df = market_data.history(body.symbol.upper())
    except Exception:
        raise HTTPException(404, f"No data found for {body.symbol.upper()}")
    try:
        bench = market_data.history("SPY")
    except Exception:
        bench = None
    return {"symbol": body.symbol.upper(), "strategy": REGISTRY[body.strategy].name, **bt.strategy_backtest(df, body.strategy, body.params, bench, body.fees_pct)}
