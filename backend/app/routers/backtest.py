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



# ------------------------------------------------------------------ custom rule-based strategies (Premium)

def _require_custom(user: User) -> None:
    if not limits_for(user)["custom_backtest"]:
        raise HTTPException(403, "Custom strategy backtests are part of Premium.")


@router.get("/rules/conditions")
def rule_conditions(user: User = Depends(current_user)):
    from engine.rules import CONDITIONS, DEFAULT_EXIT

    return {"conditions": [{"type": k, **v} for k, v in CONDITIONS.items()], "exit": DEFAULT_EXIT}


class RulesIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    rules: dict
    fees_pct: float = Field(default=0.05, ge=0, le=2)


@router.post("/rules")
def run_rules_backtest(body: RulesIn, user: User = Depends(current_user)):
    from engine.rules import run_rules

    _require_custom(user)
    sym = body.symbol.upper().strip()
    try:
        df = market_data.history(sym)
    except Exception:
        raise HTTPException(404, f"No data found for {sym}")
    try:
        bench = market_data.history("SPY")
    except Exception:
        bench = None
    try:
        return {"symbol": sym, **run_rules(df, body.rules, bench, body.fees_pct)}
    except ValueError as e:
        raise HTTPException(400, str(e))


class SaveRulesIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    rules: dict


@router.get("/rules/saved")
def saved_rules(user: User = Depends(current_user)):
    import json

    from ..db import SessionLocal
    from ..models import SavedStrategy

    _require_custom(user)
    with SessionLocal() as db:
        rows = db.query(SavedStrategy).filter_by(user_id=user.id).order_by(SavedStrategy.created_at.desc()).all()
        return [{"id": r.id, "name": r.name, "rules": json.loads(r.rules), "created_at": r.created_at.isoformat()} for r in rows]


@router.post("/rules/saved")
def save_rules(body: SaveRulesIn, user: User = Depends(current_user)):
    import json

    from ..db import SessionLocal
    from ..models import SavedStrategy

    _require_custom(user)
    with SessionLocal() as db:
        if db.query(SavedStrategy).filter_by(user_id=user.id).count() >= 50:
            raise HTTPException(400, "You can save up to 50 strategies.")
        r = SavedStrategy(user_id=user.id, name=body.name.strip(), rules=json.dumps(body.rules))
        db.add(r)
        db.commit()
        return {"id": r.id, "name": r.name, "rules": body.rules}


@router.delete("/rules/saved/{sid}", status_code=204)
def delete_rules(sid: int, user: User = Depends(current_user)):
    from ..db import SessionLocal
    from ..models import SavedStrategy

    with SessionLocal() as db:
        r = db.get(SavedStrategy, sid)
        if r is None or r.user_id != user.id:
            raise HTTPException(404, "Not found")
        db.delete(r)
        db.commit()
