"""Strategiile si indicatorii incluse implicit."""

import pandas as pd

from .. import indicators as ind
from .base import Param, Strategy, StrategyResult, line, marker, register, t

MA_COLORS = ["#f59e0b", "#3b82f6", "#a855f7", "#ec4899", "#14b8a6"]


@register
class SmaTrio(Strategy):
    id = "sma_trio"
    name = "SMA 50 / 100 / 200"
    category = "Medii mobile"
    description = "Cele trei medii mobile simple clasice pentru trendul pe termen mediu și lung."
    params = [
        Param("fast", "Rapidă", 50, 2, 400),
        Param("mid", "Medie", 100, 2, 400),
        Param("slow", "Lentă", 200, 2, 400),
    ]

    def compute(self, df, p):
        c = df["close"]
        return StrategyResult(
            lines=[line(f"SMA {p[k]}", ind.sma(c, p[k]), MA_COLORS[i]) for i, k in enumerate(("fast", "mid", "slow"))]
        )


@register
class SepaMas(Strategy):
    id = "sepa_mas"
    name = "SMA 50 / 150 / 200 (SEPA)"
    category = "Medii mobile"
    description = "Mediile folosite de Trend Template: 50, 150 și 200 de zile."
    params = []

    def compute(self, df, p):
        c = df["close"]
        return StrategyResult(
            lines=[line(f"SMA {n}", ind.sma(c, n), MA_COLORS[i]) for i, n in enumerate((50, 150, 200))]
        )


@register
class SingleSma(Strategy):
    id = "sma"
    name = "SMA (perioadă la alegere)"
    category = "Medii mobile"
    params = [Param("period", "Perioadă", 20, 2, 400)]

    def compute(self, df, p):
        return StrategyResult(lines=[line(f"SMA {p['period']}", ind.sma(df["close"], p["period"]), "#eab308")])


@register
class EmaPair(Strategy):
    id = "ema_pair"
    name = "EMA 10 / 21"
    category = "Medii mobile"
    description = "Medii exponențiale rapide, folosite pentru trailing stop și puncte de reintrare."
    params = [Param("fast", "Rapidă", 10, 2, 200), Param("slow", "Lentă", 21, 2, 200)]

    def compute(self, df, p):
        c = df["close"]
        return StrategyResult(
            lines=[
                line(f"EMA {p['fast']}", ind.ema(c, p["fast"]), "#22d3ee", width=1),
                line(f"EMA {p['slow']}", ind.ema(c, p["slow"]), "#f472b6", width=1),
            ]
        )


@register
class Bollinger(Strategy):
    id = "bollinger"
    name = "Bollinger Bands"
    category = "Volatilitate"
    params = [Param("period", "Perioadă", 20, 5, 200), Param("k", "Deviații", 2.0, 0.5, 4, 0.1, "float")]

    def compute(self, df, p):
        bb = ind.bollinger(df["close"], p["period"], p["k"])
        return StrategyResult(
            lines=[
                line("BB sus", bb["upper"], "#64748b", width=1),
                line("BB mijloc", bb["mid"], "#94a3b8", width=1),
                line("BB jos", bb["lower"], "#64748b", width=1),
            ]
        )


@register
class Rsi(Strategy):
    id = "rsi"
    name = "RSI"
    category = "Oscilatoare"
    description = "Relative Strength Index; peste 70 supracumpărat, sub 30 supravândut."
    params = [Param("period", "Perioadă", 14, 2, 100)]

    def compute(self, df, p):
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
    category = "Oscilatoare"
    params = [Param("fast", "Rapidă", 12, 2, 100), Param("slow", "Lentă", 26, 2, 200), Param("signal", "Semnal", 9, 2, 50)]

    def compute(self, df, p):
        m = ind.macd(df["close"], p["fast"], p["slow"], p["signal"]).dropna()
        hist = [
            {"time": t(i), "value": round(float(v), 4), "color": "#22c55e99" if v >= 0 else "#ef444499"}
            for i, v in m["hist"].items()
        ]
        return StrategyResult(
            lines=[line("MACD", m["macd"], "#38bdf8", pane="lower"), line("Semnal", m["signal"], "#fb923c", pane="lower")],
            histograms=[{"name": "Histogramă", "pane": "lower", "data": hist}],
        )


@register
class MaCrossBot(Strategy):
    id = "ma_cross_bot"
    name = "Bot: Crossover medii mobile"
    category = "Semnale (boți)"
    description = "BUY când media rapidă trece peste cea lentă, SELL la trecerea inversă (ex. golden/death cross)."
    params = [Param("fast", "Rapidă", 20, 2, 200), Param("slow", "Lentă", 50, 2, 400)]

    def compute(self, df, p):
        c = df["close"]
        f, s = ind.sma(c, p["fast"]), ind.sma(c, p["slow"])
        up, down = ind.crossovers(f, s)
        markers = [marker(ts, True, "BUY") for ts in up[up].index] + [marker(ts, False, "SELL") for ts in down[down].index]
        markers.sort(key=lambda m: m["time"])
        return StrategyResult(
            lines=[line(f"SMA {p['fast']}", f, "#22d3ee", width=1), line(f"SMA {p['slow']}", s, "#f472b6", width=1)],
            markers=markers,
        )


@register
class RsiBot(Strategy):
    id = "rsi_bot"
    name = "Bot: Revenire RSI"
    category = "Semnale (boți)"
    description = "BUY când RSI iese din zona de supravândut, SELL când iese din zona de supracumpărat."
    params = [
        Param("period", "Perioadă", 14, 2, 100),
        Param("low", "Supravândut", 30, 5, 50),
        Param("high", "Supracumpărat", 70, 50, 95),
    ]

    def compute(self, df, p):
        r = ind.rsi(df["close"], p["period"])
        lo = pd.Series(float(p["low"]), index=r.index)
        hi = pd.Series(float(p["high"]), index=r.index)
        buy, _ = ind.crossovers(r, lo)
        _, sell = ind.crossovers(r, hi)
        markers = [marker(ts, True, "BUY") for ts in buy[buy].index] + [marker(ts, False, "SELL") for ts in sell[sell].index]
        markers.sort(key=lambda m: m["time"])
        return StrategyResult(markers=markers)
