"""Plugin system for strategies/indicators drawn on the chart.

A new strategy = a class that subclasses Strategy and is decorated with @register.
`compute` returns a JSON-serializable dict that the frontend draws:
  lines:      [{name, color, pane: "price"|"lower", data: [{time, value}]}]
  histograms: [{name, pane, data: [{time, value, color}]}]
  markers:    [{time, position: "aboveBar"|"belowBar", shape: "arrowUp"|"arrowDown"|"circle", color, text}]
  levels:     [{price, color, title}]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np
import pandas as pd


@dataclass
class Param:
    key: str
    label: str
    default: float
    min: float = 1
    max: float = 500
    step: float = 1
    type: str = "int"  # int | float


@dataclass
class StrategyResult:
    lines: list[dict] = field(default_factory=list)
    histograms: list[dict] = field(default_factory=list)
    markers: list[dict] = field(default_factory=list)
    levels: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"lines": self.lines, "histograms": self.histograms, "markers": self.markers, "levels": self.levels}


class Strategy:
    id: ClassVar[str]
    name: ClassVar[str]
    category: ClassVar[str]  # "Moving Averages" | "Oscillators" | "Volatility" | "Signals (Bots)" | "SEPA"
    description: ClassVar[str] = ""
    params: ClassVar[list[Param]] = []
    requires: ClassVar[str | None] = None  # required plan feature (e.g. "move_detector")

    def resolve_params(self, raw: dict[str, Any] | None) -> dict[str, float]:
        raw = raw or {}
        out = {}
        for p in self.params:
            v = raw.get(p.key, p.default)
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = p.default
            v = min(max(v, p.min), p.max)
            out[p.key] = int(v) if p.type == "int" else v
        return out

    def compute(self, df: pd.DataFrame, params: dict[str, float], bench: pd.DataFrame | None = None) -> StrategyResult:
        raise NotImplementedError

    @classmethod
    def describe(cls) -> dict:
        return {
            "id": cls.id,
            "name": cls.name,
            "category": cls.category,
            "description": cls.description,
            "params": [p.__dict__ for p in cls.params],
            "requires": cls.requires,
        }


REGISTRY: dict[str, type[Strategy]] = {}


def register(cls: type[Strategy]) -> type[Strategy]:
    if cls.id in REGISTRY:
        raise ValueError(f"Strategie duplicata: {cls.id}")
    REGISTRY[cls.id] = cls
    return cls


# ---- serialization helpers ----

def t(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d")


def series_points(s: pd.Series) -> list[dict]:
    s = s.dropna()
    return [{"time": t(i), "value": round(float(v), 4)} for i, v in s.items() if np.isfinite(v)]


def line(name: str, s: pd.Series, color: str, pane: str = "price", width: int = 2) -> dict:
    return {"name": name, "color": color, "pane": pane, "width": width, "data": series_points(s)}


def marker(ts: pd.Timestamp, buy: bool, text: str) -> dict:
    return {
        "time": t(ts),
        "position": "belowBar" if buy else "aboveBar",
        "shape": "arrowUp" if buy else "arrowDown",
        "color": "#22c55e" if buy else "#ef4444",
        "text": text,
    }
