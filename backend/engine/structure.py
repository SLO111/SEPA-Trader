"""Price-structure count: a 4-step bar-by-bar sequence that confirms a shift in control.

Bearish count (mirror for bullish):
  1. a bar prints a lower low (low < previous low)
  2. a later bar closes below the previous bar's low
  3. two more bars print lower lows
  4. a later bar closes below the previous bar's low  -> 4/4: sellers in control

A count in progress is reset when the opposite side closes beyond the previous bar
(a close above the previous high cancels a bearish count, and vice versa).

After a 4/4 the position is defended with the previous bars' highs (bear) or lows (bull):
a trailing level that only moves in the trend's direction ("lower highs are enough").
The defence ends when price closes back through that level - step 1 of the other side.
"""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class StructureEvent:
    ts: pd.Timestamp
    side: str  # "bull" | "bear"
    step: int  # 1..4, 4 = complete
    price: float


@dataclass
class StructureResult:
    events: list[StructureEvent] = field(default_factory=list)
    # trailing defence level after each 4/4: list of (side, series of (ts, level))
    defence: list[tuple[str, list[tuple[pd.Timestamp, float]]]] = field(default_factory=list)
    state: dict = field(default_factory=dict)


def _advance(step: int, extra: int, made_extreme: bool, closed_beyond: bool) -> tuple[int, int]:
    """One bar of a count. Returns (completed step, lower-low/higher-high counter for step 3)."""
    if step == 0:
        return (1, 0) if made_extreme else (0, 0)
    if step == 1:
        return (2, 0) if closed_beyond else (1, 0)
    if step == 2:
        if made_extreme:
            extra += 1
        return (3, 0) if extra >= 2 else (2, extra)
    if step == 3:
        return (4, 0) if closed_beyond else (3, 0)
    return step, extra


def label(state: dict) -> dict:
    """Compact summary for tables: the active 4/4 side (with its defence) or the furthest count in progress."""
    if state.get("regime"):
        return {"text": f"{state['regime'].title()} 4/4", "side": state["regime"], "step": 4, "defence": state["defence_level"]}
    b, s = state.get("bull_step", 0), state.get("bear_step", 0)
    if b == 4 or s == 4:  # completed earlier, defence already broken
        b, s = (0 if b == 4 else b), (0 if s == 4 else s)
    if not b and not s:
        return {"text": "—", "side": None, "step": 0, "defence": None}
    side, step = ("bull", b) if b >= s else ("bear", s)
    return {"text": f"{side.title()} {step}/4", "side": side, "step": step, "defence": None}


def analyze(df: pd.DataFrame) -> StructureResult:
    res = StructureResult()
    if len(df) < 3:
        return res
    hi, lo, cl = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    idx = df.index
    count = {"bull": [0, 0], "bear": [0, 0]}  # [step, extra]
    regime: str | None = None
    level = 0.0
    trail: list[tuple[pd.Timestamp, float]] = []

    for i in range(1, len(df)):
        lower_low, higher_high = lo[i] < lo[i - 1], hi[i] > hi[i - 1]
        close_below, close_above = cl[i] < lo[i - 1], cl[i] > hi[i - 1]

        # Defence after a completed count.
        if regime == "bear":
            if cl[i] > level:
                res.defence.append(("bear", trail))
                regime, trail = None, []
            else:
                level = min(level, hi[i - 1])
                trail.append((idx[i], level))
        elif regime == "bull":
            if cl[i] < level:
                res.defence.append(("bull", trail))
                regime, trail = None, []
            else:
                level = max(level, lo[i - 1])
                trail.append((idx[i], level))

        # Opposite closes cancel a count in progress.
        if close_above and 0 < count["bear"][0] < 4:
            count["bear"] = [0, 0]
        if close_below and 0 < count["bull"][0] < 4:
            count["bull"] = [0, 0]

        for side, extreme, beyond in (("bear", lower_low, close_below), ("bull", higher_high, close_above)):
            step, extra = count[side]
            if step == 4:
                # a finished count re-arms once the other side starts its own count
                other = "bull" if side == "bear" else "bear"
                if count[other][0] == 0:
                    continue
                step, extra = 0, 0
            new, extra = _advance(step, extra, extreme, beyond)
            count[side] = [new, extra]
            if new != step:
                res.events.append(StructureEvent(idx[i], side, new, float(lo[i] if side == "bear" else hi[i])))
                if new == 4:
                    count["bull" if side == "bear" else "bear"] = [0, 0]
                    if regime and trail:
                        res.defence.append((regime, trail))
                    regime = side
                    level = hi[i] if side == "bear" else lo[i]
                    trail = [(idx[i], level)]

    if regime and trail:
        res.defence.append((regime, trail))
    res.state = {
        "bull_step": count["bull"][0],
        "bear_step": count["bear"][0],
        "regime": regime,
        "defence_level": round(level, 2) if regime else None,
    }
    return res
