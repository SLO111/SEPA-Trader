"""Trade ideas, generated once a day after the close (TheAlgo-style idea list).

Each idea comes from a multi-timeframe read of the price history:
  * trend on the daily, weekly and monthly charts must agree;
  * support and resistance come from historical swing points, and "supply zones" are swing highs that were
    followed by a sell-off of 15% or more (the boxes traders draw by hand);
  * the stop sits just below support (above resistance for shorts), the trim at the first resistance and the
    target at the next one / the 52-week high, giving a reward-to-risk ratio (R/R).

Timeframes:
  SWING  - uptrend on daily + weekly, pullback to support or a tight base near a pivot; holds days to weeks.
  TRADE  - fresh breakout above the 20-day high on strong volume; holds days.
  INVEST - uptrend on weekly + monthly, near long-term support (30-week / 10-month average); holds months.
  SHORT  - downtrend on daily + weekly, price rallying back into resistance; Move Detector Bear Score elevated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .indicators import atr, ema, sma
from . import stages, structure
from .swings import zigzag

MAX_RISK = 0.09  # reject setups that need a stop further than 9% away
MIN_RR = 2.0


@dataclass
class Idea:
    symbol: str
    timeframe: str  # SWING | TRADE | INVEST | SHORT
    side: str  # long | short
    entry: float
    stop: float
    trim: float | None
    target: float
    rr: float
    weight: float  # suggested % of the account (risk 1% of the account at the stop)
    score: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def levels(df: pd.DataFrame, lookback: int = 500, pct: float = 0.06) -> dict:
    """Support / resistance prices from swing points, plus supply zones (highs followed by a 15%+ sell-off)."""
    d = df.iloc[-lookback:]
    swings, _, _ = zigzag(d["high"].to_numpy(), d["low"].to_numpy(), pct)
    highs = [s.price for s in swings if s.kind == "H"]
    lows = [s.price for s in swings if s.kind == "L"]
    supply = []
    for a, b in zip(swings, swings[1:]):
        if a.kind == "H" and b.kind == "L" and (a.price - b.price) / a.price >= 0.15:
            supply.append(a.price)
    return {"resistance": sorted(set(highs + supply)), "support": sorted(set(lows)), "supply": supply}


def trends(df: pd.DataFrame) -> dict[str, int]:
    """+1 uptrend, -1 downtrend, 0 mixed, on the daily, weekly and monthly charts."""
    c = df["close"]
    w = df["close"].resample("W-FRI").last().dropna()
    m = df["close"].resample("ME").last().dropna()

    def state(price, fast, slow):
        if pd.isna(fast) or pd.isna(slow):
            return 0
        if price > fast > slow:
            return 1
        if price < fast < slow:
            return -1
        return 0

    return {
        "daily": state(c.iloc[-1], ema(c, 21).iloc[-1], sma(c, 50).iloc[-1]),
        "weekly": state(w.iloc[-1], sma(w, 10).iloc[-1], sma(w, 30).iloc[-1]),
        "monthly": state(m.iloc[-1], sma(m, 6).iloc[-1], sma(m, 10).iloc[-1]),
    }


def _above(xs: list[float], price: float, gap: float = 0.01) -> list[float]:
    return [x for x in xs if x > price * (1 + gap)]


def _below(xs: list[float], price: float, gap: float = 0.005) -> list[float]:
    return [x for x in xs if x < price * (1 - gap)]


def _weight(entry: float, stop: float) -> float:
    risk = abs(entry - stop) / entry
    return round(min(20.0, 1.0 / risk) if risk > 0 else 0.0, 1)  # 1% account risk / % distance to stop, max 20%


def _long(sym, tf, entry, stop, lv, hi52, score, reason) -> Idea | None:
    risk = entry - stop
    if risk <= 0 or risk / entry > MAX_RISK:
        return None
    res = _above(lv["resistance"] + ([hi52] if hi52 > entry * 1.01 else []), entry)
    if tf == "INVEST":
        target = max(hi52 * 1.1, entry * 1.3)
    else:
        # The first historical resistance worth at least 2R is the natural target; at all-time highs ("blue sky")
        # there is no overhead resistance, so aim for 3R.
        far_enough = [x for x in res if (x - entry) / risk >= MIN_RR]
        target = far_enough[0] if far_enough else entry + 3 * risk
    # Trim (take partial profits) at the first resistance between 1R and the target, else at 1.5R.
    trims = [x for x in res if entry + risk <= x < target]
    trim = trims[0] if trims else entry + 1.5 * risk
    rr = (target - entry) / risk
    if rr < MIN_RR:
        return None
    return Idea(sym, tf, "long", round(entry, 2), round(stop, 2), round(trim, 2) if trim else None, round(target, 2), round(rr, 1), _weight(entry, stop), round(score, 1), reason)


PER_INDUSTRY = 3  # among the top ideas, at most this many from one industry (the rest move down the list)


def diversify(items: list, industry_of: dict[str, str] | None, per: int = PER_INDUSTRY) -> list:
    """Keep the ranking, but move the 4th+ idea of an industry behind the others, so the top of the list spans
    several industries instead of one hot group. Items need a `.symbol`; unknown industries are not limited."""
    if not industry_of:
        return list(items)
    first, rest, seen = [], [], {}
    for it in items:
        k = industry_of.get(it.symbol) or ""
        if k and seen.get(k, 0) >= per:
            rest.append(it)
            continue
        seen[k] = seen.get(k, 0) + 1
        first.append(it)
    return first + rest


def generate(histories: dict[str, pd.DataFrame], scan: dict[str, dict], max_long: int | None = 12, max_short: int | None = 5,
             industry_of: dict[str, str] | None = None) -> list[Idea]:
    """Daily idea list from price history and the Move Detector scan (rs_rating, template_passed, bull/bear scores, vcp)."""
    longs: list[Idea] = []
    shorts: list[Idea] = []
    for sym, df in histories.items():
        if len(df) < 260:
            continue
        s = scan.get(sym, {})
        c, h, v = df["close"], df["high"], df["volume"]
        price = float(c.iloc[-1])
        if price < 5 or float((c * v).iloc[-50:].mean()) < 5e6:  # skip illiquid / penny stocks
            continue
        tr = trends(df)
        lv = levels(df)
        hi52 = float(h.iloc[-252:].max())
        a = float(atr(df, 14).iloc[-1])
        e21, s50 = float(ema(c, 21).iloc[-1]), float(sma(c, 50).iloc[-1])
        rs = s.get("rs_rating") or 50
        bull, bear = s.get("bull_score") or 0, s.get("bear_score") or 0
        tt = s.get("template_passed") or 0
        st = structure.analyze(df.iloc[-300:]).state
        # Structure count: no longs while sellers defend lower highs after a Bear 4/4, no shorts during a Bull 4/4.
        long_ok, short_ok = st["regime"] != "bear", st["regime"] != "bull"
        # Market cycle: own stocks only in Stage 2 (INVEST may start in a late Stage 1 base); short only in Stage 3-4.
        sn = stages.stage_now(df)
        stage = sn["stage"] if sn else 0
        trade_ok = long_ok and stage == 2
        invest_ok = long_ok and stage in (1, 2)
        short_ok = short_ok and stage in (3, 4)
        bull += 8 if st["regime"] == "bull" else 0
        bear += 8 if st["regime"] == "bear" else 0
        supports = _below(lv["support"] + [e21, s50], price)
        near_support = max(supports) if supports else price - 2 * a

        # TRADE: fresh breakout above the 20-day high on volume
        prior_high = float(h.iloc[-21:-1].max())
        rvol = float(v.iloc[-1]) / float(v.iloc[-51:-1].mean())
        if trade_ok and price > prior_high and rvol >= 1.5 and tr["daily"] >= 0 and bull >= 55:
            stop = max(float(df["low"].iloc[-1]), price - 1.5 * a)
            idea = _long(sym, "TRADE", price, stop, lv, hi52, bull + rs / 4 + rvol * 5, f"Broke out above the 20-day high ({prior_high:.2f}) on {rvol:.1f}× volume.")
            if idea:
                longs.append(idea)
                continue

        # SWING: daily + weekly uptrend, leader, pullback to support or tight base near the pivot
        if trade_ok and tr["daily"] >= 0 and tr["weekly"] == 1 and tt >= 6 and rs >= 70:
            pullback = (price - near_support) / price <= 0.05
            base = bool(s.get("vcp")) and s.get("pivot") and 0 <= (s["pivot"] - price) / price <= 0.04
            if pullback or base:
                entry = float(s["pivot"]) if base else price
                stop = min(near_support * 0.99, entry - a)
                why = (f"Tight base (VCP) just below the pivot {s['pivot']:.2f}; buy on a breakout." if base
                       else f"Uptrend on the daily and weekly; pulling back to support near {near_support:.2f}.")
                idea = _long(sym, "SWING", entry, stop, lv, hi52, bull + rs / 3 + tt * 2, why)
                if idea:
                    longs.append(idea)
                    continue

        # INVEST: weekly + monthly uptrend, near long-term support
        w = c.resample("W-FRI").last().dropna()
        sma30w = float(sma(w, 30).iloc[-1]) if len(w) >= 30 else np.nan
        if invest_ok and tr["weekly"] == 1 and tr["monthly"] == 1 and rs >= 60 and not np.isnan(sma30w) and 0 <= (price - sma30w) / price <= 0.08:
            stop = sma30w * 0.95
            idea = _long(sym, "INVEST", price, stop, {"resistance": []}, hi52, rs + tr["daily"] * 5 + bull / 4,
                         f"Long-term uptrend; near the 30-week average ({sma30w:.2f}), a historical support.")
            if idea:
                longs.append(idea)
                continue

        # SHORT: daily + weekly downtrend, rallying into resistance, Bear Score elevated
        if short_ok and tr["daily"] <= 0 and tr["weekly"] == -1 and bear >= 55:
            res = _above(lv["resistance"] + [s50, e21], price, 0.0)
            ceiling = min(res) if res else price + 2 * a
            if (ceiling - price) / price <= 0.04:
                stop = max(ceiling * 1.01, price + a)
                risk = stop - price
                sup = _below(lv["support"], price)
                target = min(max(sup) if sup else price - 3 * risk, price - 3 * risk)
                rr = (price - target) / risk if risk > 0 else 0
                if 0 < risk / price <= MAX_RISK and rr >= MIN_RR and target > 0:
                    trim = round(price - 1.5 * risk, 2)
                    shorts.append(Idea(sym, "SHORT", "short", round(price, 2), round(stop, 2), trim, round(target, 2), round(rr, 1),
                                       _weight(price, stop), round(bear + (100 - rs) / 3, 1),
                                       f"Downtrend on the daily and weekly; rallying into resistance near {ceiling:.2f}."))

    longs.sort(key=lambda i: -(i.score + i.rr * 5))
    shorts.sort(key=lambda i: -(i.score + i.rr * 5))
    return _with_quotas(diversify(longs, industry_of), max_long) + diversify(shorts, industry_of)[:max_short]


SETUP_SHARE = {"SWING": 0.5, "TRADE": 0.25, "INVEST": 0.25}  # of the daily long slots


def _with_quotas(longs: list, max_long: int | None) -> list:
    """Each setup gets its share of the slots first (SWING scores run higher, so with a large universe it would take
    every slot and TRADE / INVEST ideas would never show); unused slots go to the best remaining ideas.
    max_long None = keep them all (only the order changes)."""
    if max_long is None:
        max_long = len(longs)
    quota = {k: max(1, int(max_long * v)) for k, v in SETUP_SHARE.items()}
    first, rest, used = [], [], {}
    for i in longs:
        if used.get(i.timeframe, 0) < quota.get(i.timeframe, max_long):
            used[i.timeframe] = used.get(i.timeframe, 0) + 1
            first.append(i)
        else:
            rest.append(i)
    return (first + rest)[:max_long]


MIN_RR_SIGNALS = 1.5  # below this remaining reward/risk an idea is no longer offered in Signals


def rr_now(idea: dict, price: float | None, status: str = "WAIT") -> float | None:
    """Reward / risk left from the current price. A waiting idea keeps its planned R/R (entry, stop and target don't move)."""
    if status == "WAIT" or price is None:
        return idea.get("rr")
    long = idea["side"] != "short"
    risk = (price - idea["stop"]) if long else (idea["stop"] - price)
    reward = (idea["target"] - price) if long else (price - idea["target"])
    if risk <= 0:
        return 0.0
    return round(max(reward, 0.0) / risk, 2)


def update_status(idea: dict, df: pd.DataFrame, created: pd.Timestamp, max_wait_days: int = 10) -> dict:
    """Follow an idea after it was published: WAIT -> BUY -> TRIM -> TARGET, or STOPPED / CANCEL."""
    after = df[df.index > created]
    long = idea["side"] == "long"
    status, entered, exit_price, exit_date = "WAIT", False, None, None
    trimmed = False
    for ts, bar in after.iterrows():
        hi, lo = float(bar["high"]), float(bar["low"])
        if not entered:
            triggered = (hi >= idea["entry"]) if long else (lo <= idea["entry"])
            invalid = (lo <= idea["stop"]) if long else (hi >= idea["stop"])
            if invalid and not triggered:
                status, exit_date = "CANCEL", ts
                break
            if triggered:
                entered, status = True, "BUY"
            elif (ts - created).days > max_wait_days:
                status, exit_date = "CANCEL", ts
                break
            if not entered:
                continue
        if (lo <= idea["stop"]) if long else (hi >= idea["stop"]):
            status, exit_price, exit_date = "STOPPED", idea["stop"], ts
            break
        if (hi >= idea["target"]) if long else (lo <= idea["target"]):
            status, exit_price, exit_date = "TARGET", idea["target"], ts
            break
        if idea.get("trim") and ((hi >= idea["trim"]) if long else (lo <= idea["trim"])):
            trimmed, status = True, "TRIM"
    current = float(df["close"].iloc[-1])
    ref = exit_price if exit_price is not None else current
    pnl = ((ref / idea["entry"] - 1) * (1 if long else -1) * 100) if entered else None
    r = ((ref - idea["entry"]) * (1 if long else -1) / abs(idea["entry"] - idea["stop"])) if entered else None
    return {"status": status, "trimmed": trimmed, "current": round(current, 2), "pnl_pct": round(pnl, 2) if pnl is not None else None,
            "r_multiple": round(r, 2) if r is not None else None, "closed_at": exit_date.strftime("%Y-%m-%d") if exit_date is not None else None,
            "open": status in ("WAIT", "BUY", "TRIM")}
