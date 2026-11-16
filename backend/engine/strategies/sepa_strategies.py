"""SEPA and Move Detector strategies for the chart."""

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
    description = "Markers on days the stock enters or exits the Trend Template (criteria 1–7). Optionally shows the 50/150/200-day MAs."
    params = [Param("show", "Show 50/150/200 MAs", 0, 0, 1, type="select", options=[[0, "No"], [1, "Yes"]])]

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
        lines = [line(f"SMA {n}", sma(c, n), col, width=1) for n, col in ((50, "#f59e0b"), (150, "#3b82f6"), (200, "#a855f7"))] if p.get("show") else []
        return StrategyResult(lines=lines, markers=markers)


@register
class VcpStrategy(Strategy):
    id = "vcp"
    name = "VCP + pivot"
    category = "SEPA"
    description = "Detects volatility contractions and shows the pivot (breakout point) and suggested stop."
    params = [Param("lookback", "Lookback (days)", 130, 40, 300), Param("swing", "Swing %", 4, 2, 15)]

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
    name = "Automatic trend lines"
    category = "SEPA"
    description = "Resistance through the last two peaks and support through the last two troughs."
    params = [Param("lookback", "Lookback (days)", 250, 60, 750), Param("swing", "Swing %", 6, 2, 20)]

    def compute(self, df, p, bench=None):
        lines = auto_trendlines(df, int(p["lookback"]), p["swing"] / 100)
        return StrategyResult(lines=[{"name": l["name"], "color": l["color"], "pane": "price", "width": 2, "data": l["data"]} for l in lines])


@register
class MoveDetectorStrategy(Strategy):
    id = "move_detector"
    name = "Move Detector (Bull / Bear Score)"
    category = "SEPA"
    description = "Daily 0–100 score for the potential of a major move up (green) or down (red)."
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


@register
class StructureCountStrategy(Strategy):
    id = "structure_count"
    name = "Structure Count 4/4 (Bull / Bear)"
    category = "SEPA"
    description = (
        "Counts 4 steps that confirm who is in control: 1) lower low, 2) close below the previous low, "
        "3) two more lower lows, 4) close below the previous low (mirror for bulls with highs). "
        "After 4/4 it trails a defence line on the prior bars' highs (bear) or lows (bull) until price closes back through it."
    )
    params = [
        Param("steps", "Show steps 1–3", 0, 0, 1, type="select", options=[[0, "No"], [1, "Yes"]]),
        Param("defence", "Show defence line", 1, 0, 1, type="select", options=[[0, "No"], [1, "Yes"]]),
        Param("lookback", "Bars to show", 250, 50, 2000),
    ]

    def compute(self, df, p, bench=None):
        from ..structure import analyze

        r = analyze(df)
        start = df.index[max(0, len(df) - int(p["lookback"]))]
        res = StrategyResult()
        for e in r.events:
            if e.ts < start or (e.step < 4 and not p.get("steps")):
                continue
            bull = e.side == "bull"
            done = e.step == 4
            res.markers.append(
                {
                    "time": t(e.ts),
                    "position": "belowBar" if bull else "aboveBar",
                    "shape": ("arrowUp" if bull else "arrowDown") if done else "circle",
                    "color": ("#22c55e" if bull else "#ef4444") if done else ("#86efac" if bull else "#fca5a5"),
                    "text": f"{'Bull' if bull else 'Bear'} 4/4" if done else str(e.step),
                }
            )
        if p.get("defence"):
            for side, pts in r.defence:
                pts = [x for x in pts if x[0] >= start]
                if len(pts) < 2:
                    continue
                res.lines.append(
                    {
                        "name": "Defence (lower highs)" if side == "bear" else "Defence (higher lows)",
                        "color": "#f87171" if side == "bear" else "#4ade80",
                        "pane": "price",
                        "width": 1,
                        "data": [{"time": t(ts), "value": round(v, 2)} for ts, v in pts],
                    }
                )
        if r.state.get("defence_level"):
            res.levels.append({"price": r.state["defence_level"], "color": "#f87171" if r.state["regime"] == "bear" else "#4ade80", "title": "Defence"})
        res.markers.sort(key=lambda m: m["time"])
        return res
