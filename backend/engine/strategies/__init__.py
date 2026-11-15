from . import builtin  # noqa: F401  (inregistreaza strategiile)
from .base import REGISTRY, Strategy, StrategyResult


def list_strategies() -> list[dict]:
    return [cls.describe() for cls in REGISTRY.values()]


def run_strategy(strategy_id: str, df, params: dict | None = None) -> dict:
    cls = REGISTRY.get(strategy_id)
    if cls is None:
        raise KeyError(strategy_id)
    s = cls()
    return s.compute(df, s.resolve_params(params)).to_dict()


__all__ = ["REGISTRY", "Strategy", "StrategyResult", "list_strategies", "run_strategy"]
