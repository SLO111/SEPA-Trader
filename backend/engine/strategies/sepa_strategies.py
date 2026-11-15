"""Strategii SEPA si Move Detector pentru chart."""

import pandas as pd

from .. import move_detector as md
from ..sepa import template_frame
from ..trendlines import auto_trendlines
from ..vcp import detect_vcp
from .base import Param, Strategy, StrategyResult, line, register, t


@register
class TrendTemplateStrategy(Strategy):
    id = "trend_template"
    name = "Trend Template (SEPA)"
    category = "SEPA"
    description = "Mediile 50/150/200 și marcaje în zilele în care acțiunea intră sau iese din Trend Template (criteriile 1–7)."
    params = []

    def compute(self, df, p, bench=None):
        c = df["close"]
        from ..indicators import sma

        ok = template_frame(df).all(axis=1)
        enter = ok & ~ok.shift(1, fill_value=False)
        leave = ~ok & ok.shift(1, fill_value=False)
        markers = [
            {"time": t(ts), "position": "belowBar", "shape": "circle", "color": "#22c55e", "text": "TT ✓"} for ts in enter[enter].index
        ] + [{"time": t(ts), "position": "aboveBar", "shape": "circle", "color": "#f97316", "text": "TT ✗"} for ts in leave[leave].index]
        markers.sort(key=lambda m: m["time"])
        return StrategyResult(
            lines=[line(f"SMA {n}", sma(c, n), col, width=1) for n, col in ((50, "#f59e0b"), (150, "#3b82f6"), (200, "#a855f7"))],
            markers=markers,
        )


@register
class VcpStrategy(Strategy):
    id = "vcp"
    name = "VCP + pivot"
    category = "SEPA"
    description = "Detectează contracțiile de volatilitate; afișează pivotul (punctul de breakout) și stop-ul sugerat."
    params = [Param("lookback", "Fereastră (zile)", 130, 40, 300), Param("swing", "Swing %", 4, 2, 15)]

    def compute(self, df, p, bench=None):
        v = detect_vcp(df, int(p["lookback"]), p["swing"] / 100)
        res = StrategyResult()
        for i, c in enumerate(v["contractions"]):
            res.lines.append(
                {
                    "name": f"C{i + 1} −{c['depth_pct']}%",
                    "color": "#38bdf8",
                    "pane": "price",
                    "width": 1,
                    "data": [{"time": c["start"], "value": c["high"]}, {"time": c["end"], "value": c["low"]}],
                }
            )
            res.markers.append({"time": c["end"], "position": "belowBar", "shape": "circle", "color": "#38bdf8", "text": f"−{c['depth_pct']}%"})
        if v.get("pivot"):
            res.levels.append({"price": v["pivot"], "color": "#22c55e" if v["detected"] else "#64748b", "title": "Pivot" + (" VCP" if v["detected"] else "")})
            res.levels.append({"price": v["stop"], "color": "#ef4444", "title": "Stop"})
        return res


@register
class TrendlinesStrategy(Strategy):
    id = "trendlines"
    name = "Trend lines automate"
    category = "SEPA"
    description = "Linie de rezistență prin ultimele două vârfuri și de suport prin ultimele două minime."
    params = [Param("lookback", "Fereastră (zile)", 250, 60, 750), Param("swing", "Swing %", 6, 2, 20)]

    def compute(self, df, p, bench=None):
        lines = auto_trendlines(df, int(p["lookback"]), p["swing"] / 100)
        return StrategyResult(lines=[{"name": l["name"], "color": l["color"], "pane": "price", "width": 2, "data": l["data"]} for l in lines])


@register
class MoveDetectorStrategy(Strategy):
    id = "move_detector"
    name = "Move Detector (Bull / Bear Score)"
    category = "SEPA"
    description = "Scorul zilnic 0–100 pentru potențialul unei mișcări majore în sus (verde) sau în jos (roșu)."
    requires = "move_detector"
    params = []

    def compute(self, df, p, bench=None):
        s = md.score_series(df, bench)
        flat = lambda v: pd.Series(float(v), index=s["bull"].dropna().index)
        return StrategyResult(
            lines=[
                line("Bull", s["bull"], "#22c55e", pane="lower"),
                line("Bear", s["bear"], "#ef4444", pane="lower"),
                line("60", flat(60), "#94a3b855", pane="lower", width=1),
            ]
        )
