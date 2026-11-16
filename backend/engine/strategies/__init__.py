from . import builtin, pro_indicators, sepa_strategies  # noqa: F401  (registers the strategies)
from .base import REGISTRY, Strategy, StrategyResult

pro_indicators.apply_ratings(REGISTRY)


def list_strategies() -> list[dict]:
    return [cls.describe() for cls in REGISTRY.values()]


def run_strategy(strategy_id: str, df, params: dict | None = None, bench=None) -> dict:
    cls = REGISTRY.get(strategy_id)
    if cls is None:
        raise KeyError(strategy_id)
    s = cls()
    return s.compute(df, s.resolve_params(params), bench).to_dict()


__all__ = ["REGISTRY", "Strategy", "StrategyResult", "list_strategies", "run_strategy"]
