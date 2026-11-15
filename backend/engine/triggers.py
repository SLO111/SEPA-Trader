"""Move Detector – layer 2: triggers (the events that generate alerts).

Each trigger is evaluated on a specific bar (the latest by default) using ONLY data up to that bar.
This lets us test that an alert fires exactly on the breakout bar, never earlier.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from . import indicators as ind
from . import move_detector as md
from .sepa import rs_line
from .vcp import detect_vcp

ET = ZoneInfo("America/New_York")

EVENT_TYPES: dict[str, dict] = {
    "breakout": {"label": "Breakout above pivot", "severity": "bull", "description": "Price closes above the pivot (VCP pivot or 50-day high) on volume of at least 1.4× average."},
    "unusual_volume": {"label": "Unusual volume", "severity": "info", "description": "Volume (projected for the full day) is at least 3× the 50-day average."},
    "gap_up": {"label": "Gap up", "severity": "bull", "description": "Opens at least 4% above the previous close."},
    "gap_down": {"label": "Gap down", "severity": "bear", "description": "Opens at least 4% below the previous close."},
    "ma50_break": {"label": "50-day MA break on volume", "severity": "bear", "description": "Closes below the 50-day SMA, coming from above, on above-average volume. A warning sign."},
    "failed_breakout": {"label": "Failed breakout", "severity": "bear", "description": "After a recent breakout, price falls back more than 3% below the breakout level."},
    "ma_reclaim": {"label": "21-day EMA reclaim", "severity": "bull", "description": "In an uptrend, price closes back above the 21-day EMA. A possible re-entry point."},
    "rs_new_high": {"label": "RS line new high", "severity": "bull", "description": "The RS line hits a 52-week high ahead of price. A sign of market leadership."},
    "bull_score": {"label": "Bull Score above threshold", "severity": "bull", "description": "The Move Detector Bull Score crosses above the chosen threshold (default 70)."},
    "bear_score": {"label": "Bear Score above threshold", "severity": "bear", "description": "The Move Detector Bear Score crosses above the chosen threshold (default 70)."},
    "price_above": {"label": "Price crosses above level", "severity": "info", "description": "The close crosses above your chosen price level."},
    "price_below": {"label": "Price crosses below level", "severity": "info", "description": "The close crosses below your chosen price level (e.g. a stop-loss)."},
}

DEFAULT_EVENTS = ["breakout", "unusual_volume", "gap_up", "gap_down", "ma50_break", "failed_breakout", "bull_score", "bear_score"]


@dataclass
class Event:
    type: str
    severity: str
    title: str
    message: str
    bar_date: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def projected_volume(df: pd.DataFrame, now: datetime | None = None) -> float:
    """Volume of the latest bar; if it is today's bar and the market is open, project it to a full day."""
    vol = float(df["volume"].iloc[-1])
    now = (now or datetime.now(ET)).astimezone(ET)
    if df.index[-1].date() != now.date():
        return vol
    open_, close = datetime.combine(now.date(), time(9, 30), ET), datetime.combine(now.date(), time(16, 0), ET)
    if not (open_ < now < close):
        return vol
    elapsed = max((now - open_).total_seconds() / 60, 15)  # avoid absurd projections in the first minutes
    return vol * 390 / elapsed


def _fmt(x: float) -> str:
    return f"{x:,.2f}"


def evaluate(
    df: pd.DataFrame,
    bench: pd.DataFrame | None = None,
    events: list[str] | None = None,
    params: dict | None = None,
    i: int = -1,
    now: datetime | None = None,
) -> list[Event]:
    """Evaluate the requested triggers on bar `i` (the latest by default)."""
    events = events or DEFAULT_EVENTS
    params = params or {}
    end = len(df) + i + 1 if i < 0 else i + 1
    d = df.iloc[:end]
    if len(d) < 60:
        return []
    b = bench.loc[: d.index[-1]] if bench is not None else None

    c, o, v = d["close"], d["open"], d["volume"]
    close, prev = float(c.iloc[-1]), float(c.iloc[-2])
    date = d.index[-1].strftime("%Y-%m-%d")
    vol50 = float(v.iloc[-51:-1].mean())
    vol = projected_volume(d, now) if i == -1 else float(v.iloc[-1])
    rvol = vol / vol50 if vol50 > 0 else 0.0
    out: list[Event] = []

    def add(t: str, title: str, message: str, **data):
        out.append(Event(t, EVENT_TYPES[t]["severity"], title, message, date, {"close": round(close, 2), "rvol": round(rvol, 2), **data}))

    if "breakout" in events:
        prior = d.iloc[:-1]
        vcp = detect_vcp(prior)
        if vcp["detected"]:
            pivot, stop, source = vcp["pivot"], vcp["stop"], "the VCP pivot"
        else:
            pivot, stop, source = float(prior["high"].iloc[-50:].max()), None, "the 50-day high"
        if prev <= pivot < close and rvol >= 1.4:
            stop = stop or round(close * 0.93, 2)
            add(
                "breakout",
                f"Breakout above {source}",
                f"Closed at {_fmt(close)} above {source} ({_fmt(pivot)}) on {rvol:.1f}× average volume. Suggested stop {_fmt(stop)} ({(1 - stop / close) * 100:.1f}% risk).",
                pivot=round(pivot, 2),
                stop=round(stop, 2),
            )

    if "unusual_volume" in events and rvol >= params.get("rvol", 3.0):
        chg = (close / prev - 1) * 100
        add("unusual_volume", f"Volume {rvol:.1f}× average", f"Unusual volume ({rvol:.1f}× the 50-day average), price {chg:+.1f}%.", change_pct=round(chg, 2))

    gap = float(o.iloc[-1]) / prev - 1
    gap_pct = params.get("gap_pct", 4.0) / 100
    if "gap_up" in events and gap >= gap_pct:
        add("gap_up", f"Gap up {gap * 100:.1f}%", f"Opened at {_fmt(float(o.iloc[-1]))}, {gap * 100:.1f}% above the previous close ({_fmt(prev)}).", gap_pct=round(gap * 100, 2))
    if "gap_down" in events and gap <= -gap_pct:
        add("gap_down", f"Gap down {abs(gap) * 100:.1f}%", f"Opened at {_fmt(float(o.iloc[-1]))}, {abs(gap) * 100:.1f}% below the previous close ({_fmt(prev)}).", gap_pct=round(gap * 100, 2))

    if "ma50_break" in events:
        s50 = ind.sma(c, 50)
        if prev >= float(s50.iloc[-2]) and close < float(s50.iloc[-1]) and rvol >= 1.2:
            add("ma50_break", "Broke below the 50-day MA on volume", f"Closed at {_fmt(close)} below the 50-day SMA ({_fmt(float(s50.iloc[-1]))}) on {rvol:.1f}× average volume. Review open positions.", sma50=round(float(s50.iloc[-1]), 2))

    if "failed_breakout" in events:
        h = d["high"]
        level = None
        for k in range(len(d) - 11, len(d) - 2):  # breakout within the last 2–10 bars
            if k < 51:
                continue
            lvl = float(h.iloc[k - 50 : k].max())
            if float(c.iloc[k]) > lvl:
                level = lvl
        if level and close < level * 0.97 <= prev:
            add("failed_breakout", "Failed breakout", f"Price fell back to {_fmt(close)}, below the recent breakout level ({_fmt(level)}). Failed breakouts often precede declines.", level=round(level, 2))

    if "ma_reclaim" in events:
        e21, s200 = ind.ema(c, 21), ind.sma(c, 200)
        if prev < float(e21.iloc[-2]) and close > float(e21.iloc[-1]) and pd.notna(s200.iloc[-1]) and close > float(s200.iloc[-1]):
            add("ma_reclaim", "Reclaimed the 21-day EMA", f"Closed at {_fmt(close)} above the 21-day EMA ({_fmt(float(e21.iloc[-1]))}) while in an uptrend.")

    if "rs_new_high" in events and b is not None and len(b) > 252:
        rsl = rs_line(c, b["close"]).dropna()
        if len(rsl) > 253:
            hi_prev = float(rsl.iloc[-253:-1].max())
            price_hi = float(c.iloc[-253:-1].max())
            if float(rsl.iloc[-1]) > hi_prev and float(rsl.iloc[-2]) <= hi_prev and close < price_hi:
                add("rs_new_high", "RS line at a new high", "The RS line hit a 52-week high ahead of price: the stock is clearly outperforming the market.")

    if "bull_score" in events or "bear_score" in events:
        s = md.score_series(d.iloc[-300:], b)
        for kind in ("bull", "bear"):
            key = f"{kind}_score"
            thr = params.get(f"{kind}_threshold", 70)
            if key in events and len(s) >= 2:
                now_s, prev_s = s[kind].iloc[-1], s[kind].iloc[-2]
                if pd.notna(now_s) and pd.notna(prev_s) and prev_s < thr <= now_s:
                    word = "upside" if kind == "bull" else "downside"
                    add(key, f"{'Bull' if kind == 'bull' else 'Bear'} Score {now_s:.0f}", f"Move Detector: the score for a major {word} move crossed {thr:.0f} (now {now_s:.0f}).", score=round(float(now_s), 1))

    level = params.get("price_level")
    if level:
        if "price_above" in events and prev < level <= close:
            add("price_above", f"Above {_fmt(level)}", f"The close ({_fmt(close)}) crossed above your level of {_fmt(level)}.", level=level)
        if "price_below" in events and prev > level >= close:
            add("price_below", f"Below {_fmt(level)}", f"The close ({_fmt(close)}) crossed below your level of {_fmt(level)}.", level=level)

    return out
