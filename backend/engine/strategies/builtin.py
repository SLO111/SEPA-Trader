"""Built-in indicators and signal bots.

One configurable indicator per idea (no near-duplicates): "Moving Average" can be added several times with
different settings, like on TradingView.
"""

import pandas as pd

from .. import indicators as ind
from .base import Param, Strategy, StrategyResult, line, marker, register, t

COLORS = ["#f59e0b", "#3b82f6", "#a855f7", "#22d3ee", "#ec4899", "#22c55e", "#eab308", "#f97316"]
COLOR_OPTIONS = [[i, name] for i, name in enumerate(["Orange", "Blue", "Purple", "Cyan", "Pink", "Green", "Yellow", "Red-orange"])]
MA_TYPE = [[0, "SMA"], [1, "EMA"]]
YES_NO = [[0, "No"], [1, "Yes"]]


def _ma(c: pd.Series, kind: int, n: int) -> pd.Series:
    return ind.ema(c, n) if kind == 1 else ind.sma(c, n)


def _name(kind: int) -> str:
    return "EMA" if kind == 1 else "SMA"


@register
class MovingAverage(Strategy):
    id = "ma"
    name = "Moving Average"
    category = "Moving Averages"
    description = "A simple or exponential moving average. Add it several times for different periods."
    params = [
        Param("type", "Type", 0, 0, 1, type="select", options=MA_TYPE),
        Param("period", "Length", 50, 2, 500),
        Param("color", "Color", 0, 0, len(COLORS) - 1, type="select", options=COLOR_OPTIONS),
    ]

    def compute(self, df, p, bench=None):
        return StrategyResult(lines=[line(f"{_name(p['type'])} {p['period']}", _ma(df["close"], p["type"], p["period"]), COLORS[p["color"]])])


@register
class MovingAverageRibbon(Strategy):
    id = "ma_ribbon"
    name = "Moving Averages (3)"
    category = "Moving Averages"
    description = "Three moving averages at once. Defaults to the SEPA trend set: 50, 150 and 200 days."
    params = [
        Param("type", "Type", 0, 0, 1, type="select", options=MA_TYPE),
        Param("fast", "Fast", 50, 2, 500),
        Param("mid", "Medium", 150, 2, 500),
        Param("slow", "Slow", 200, 2, 500),
    ]

    def compute(self, df, p, bench=None):
        c = df["close"]
        return StrategyResult(lines=[line(f"{_name(p['type'])} {p[k]}", _ma(c, p["type"], p[k]), COLORS[i]) for i, k in enumerate(("fast", "mid", "slow"))])


@register
class Bollinger(Strategy):
    id = "bollinger"
    name = "Bollinger Bands"
    category = "Volatility"
    description = "A moving average with bands two standard deviations above and below it."
    params = [Param("period", "Length", 20, 5, 200), Param("k", "Std. dev.", 2.0, 0.5, 4, 0.1, "float")]

    def compute(self, df, p, bench=None):
        bb = ind.bollinger(df["close"], p["period"], p["k"])
        return StrategyResult(
            lines=[
                line("BB upper", bb["upper"], "#64748b", width=1),
                line("BB basis", bb["mid"], "#94a3b8", width=1),
                line("BB lower", bb["lower"], "#64748b", width=1),
            ]
        )


@register
class Rsi(Strategy):
    id = "rsi"
    name = "RSI"
    category = "Oscillators"
    description = "Relative Strength Index: above 70 is overbought, below 30 is oversold."
    params = [Param("period", "Length", 14, 2, 100)]

    def compute(self, df, p, bench=None):
        r = ind.rsi(df["close"], p["period"])
        flat = lambda v: pd.Series(v, index=r.dropna().index)
        return StrategyResult(
            lines=[
                line(f"RSI {p['period']}", r, "#a78bfa", pane="lower"),
                line("70", flat(70), "#ef444466", pane="lower", width=1),
                line("30", flat(30), "#22c55e66", pane="lower", width=1),
            ]
        )


@register
class Macd(Strategy):
    id = "macd"
    name = "MACD"
    category = "Oscillators"
    description = "Moving Average Convergence Divergence: trend and momentum in one oscillator."
    params = [Param("fast", "Fast", 12, 2, 100), Param("slow", "Slow", 26, 2, 200), Param("signal", "Signal", 9, 2, 50)]

    def compute(self, df, p, bench=None):
        m = ind.macd(df["close"], p["fast"], p["slow"], p["signal"]).dropna()
        hist = [{"time": t(i), "value": round(float(v), 4), "color": "#22c55e99" if v >= 0 else "#ef444499"} for i, v in m["hist"].items()]
        return StrategyResult(
            lines=[line("MACD", m["macd"], "#38bdf8", pane="lower"), line("Signal", m["signal"], "#fb923c", pane="lower")],
            histograms=[{"name": "Histogram", "pane": "lower", "data": hist}],
        )


@register
class MaCrossBot(Strategy):
    id = "ma_cross_bot"
    name = "Bot: Moving average crossover"
    category = "Signals (Bots)"
    description = "BUY when the fast MA crosses above the slow MA, SELL on the opposite cross (e.g. golden/death cross)."
    params = [
        Param("fast", "Fast", 20, 2, 200),
        Param("slow", "Slow", 50, 2, 400),
        Param("type", "Type", 0, 0, 1, type="select", options=MA_TYPE),
        Param("show", "Show averages", 0, 0, 1, type="select", options=YES_NO),
    ]

    def compute(self, df, p, bench=None):
        c = df["close"]
        kind = p.get("type", 0)
        f, s = _ma(c, kind, p["fast"]), _ma(c, kind, p["slow"])
        up, down = ind.crossovers(f, s)
        markers = [marker(ts, True, "BUY") for ts in up[up].index] + [marker(ts, False, "SELL") for ts in down[down].index]
        markers.sort(key=lambda m: m["time"])
        lines = []
        if p.get("show", 0):
            lines = [line(f"{_name(kind)} {p['fast']}", f, "#22d3ee", width=1), line(f"{_name(kind)} {p['slow']}", s, "#f472b6", width=1)]
        return StrategyResult(lines=lines, markers=markers)


@register
class RsiBot(Strategy):
    id = "rsi_bot"
    name = "Bot: RSI reversal"
    category = "Signals (Bots)"
    description = "BUY when RSI exits the oversold zone, SELL when it exits the overbought zone."
    params = [
        Param("period", "Length", 14, 2, 100),
        Param("low", "Oversold", 30, 5, 50),
        Param("high", "Overbought", 70, 50, 95),
    ]

    def compute(self, df, p, bench=None):
        r = ind.rsi(df["close"], p["period"])
        lo = pd.Series(float(p["low"]), index=r.index)
        hi = pd.Series(float(p["high"]), index=r.index)
        buy, _ = ind.crossovers(r, lo)
        _, sell = ind.crossovers(r, hi)
        markers = [marker(ts, True, "BUY") for ts in buy[buy].index] + [marker(ts, False, "SELL") for ts in sell[sell].index]
        markers.sort(key=lambda m: m["time"])
        return StrategyResult(markers=markers)
