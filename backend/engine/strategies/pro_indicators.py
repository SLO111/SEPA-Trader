"""Higher-performance chart indicators: ATR trailing signals, Supertrend, adaptive ranges, squeeze, ADX,
the RS line, pocket pivots, Donchian channels and an anchored VWAP.

Each has a rating (1-5: how much it can help in practice, our assessment), a level (Beginner / Intermediate /
Advanced) and what it is best used for, shown in the Indicators dialog.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ind
from .base import Param, Strategy, StrategyResult, colored_line, line, marker, register, t

UP, DOWN, NEUTRAL = "#22c55e", "#ef4444", "#3b82f6"
YES_NO = [[0, "No"], [1, "Yes"]]


def _heikin_ashi_close(df: pd.DataFrame) -> pd.Series:
    return (df["open"] + df["high"] + df["low"] + df["close"]) / 4


def ut_bot(src: pd.Series, atr: pd.Series, key: float) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """ATR trailing stop that ratchets with price and flips when price closes through it.
    Returns (trailing stop, position 1/-1, buy signals, sell signals)."""
    s = src.to_numpy(dtype=float)
    loss = (atr * key).to_numpy(dtype=float)
    n = len(s)
    stop = np.full(n, np.nan)
    pos = np.zeros(n)
    prev_stop, prev_pos = 0.0, 0.0
    for i in range(n):
        if not np.isfinite(loss[i]) or i == 0:
            continue
        x, x1, p = s[i], s[i - 1], prev_stop
        if x > p and x1 > p:
            cur = max(p, x - loss[i])
        elif x < p and x1 < p:
            cur = min(p, x + loss[i])
        elif x > p:
            cur = x - loss[i]
        else:
            cur = x + loss[i]
        if x1 < p and x > p:
            prev_pos = 1
        elif x1 > p and x < p:
            prev_pos = -1
        stop[i], pos[i] = cur, prev_pos
        prev_stop = cur
    st = pd.Series(stop, index=src.index)
    ps = pd.Series(pos, index=src.index)
    above = src > st
    buy = above & ~(src.shift() > st.shift()).fillna(False).astype(bool) & st.notna() & st.shift().notna()
    below = src < st
    sell = below & ~(src.shift() < st.shift()).fillna(False).astype(bool) & st.notna() & st.shift().notna()
    return st, ps, buy, sell


@register
class UtBotSignals(Strategy):
    id = "ut_bot"
    name = "UT Bot: ATR trailing Buy / Sell"
    category = "Signals (Bots)"
    description = ("An ATR trailing stop that follows price and flips on a close through it: Buy / Sell labels, coloured candles. "
                   "Lower 'Key value' = more signals; higher = fewer, longer trends.")
    params = [
        Param("key", "Key value (sensitivity)", 1.0, 0.1, 10, 0.1, "float"),
        Param("atr", "ATR period", 10, 1, 100),
        Param("ha", "Signals from Heikin Ashi", 0, 0, 1, type="select", options=YES_NO),
        Param("bars", "Colour the candles", 1, 0, 1, type="select", options=YES_NO),
    ]
    rating, level = 4, "Beginner"
    best_for = "Clear entries and exits in trending stocks. Whipsaws in sideways markets: confirm with the trend (above the 50/200-day)."

    def compute(self, df, p, bench=None):
        src = _heikin_ashi_close(df) if p["ha"] else df["close"]
        st, pos, buy, sell = ut_bot(src, ind.atr(df, p["atr"]), p["key"])
        colors = pd.Series(np.where(pos > 0, UP, np.where(pos < 0, DOWN, NEUTRAL)), index=df.index)
        markers = [marker(ts, True, "Buy") for ts in buy[buy].index] + [marker(ts, False, "Sell") for ts in sell[sell].index]
        markers.sort(key=lambda m: str(m["time"]))
        bars = []
        if p["bars"]:
            ok = st.notna()
            bars = [{"time": t(i), "color": UP if src[i] > st[i] else DOWN} for i in st[ok].index]
        return StrategyResult(lines=[colored_line("UT trailing stop", st, colors, width=2, step=True)], markers=markers, bar_colors=bars)


def supertrend(df: pd.DataFrame, n: int, mult: float) -> tuple[pd.Series, pd.Series]:
    """(line, direction 1 up / -1 down)."""
    hl2 = (df["high"] + df["low"]) / 2
    a = ind.atr(df, n)
    up_b = (hl2 - mult * a).to_numpy()
    dn_b = (hl2 + mult * a).to_numpy()
    c = df["close"].to_numpy()
    size = len(c)
    up, dn, d = up_b.copy(), dn_b.copy(), np.ones(size)
    out = np.full(size, np.nan)
    for i in range(1, size):
        if not np.isfinite(up_b[i]):
            continue
        if np.isfinite(up[i - 1]) and c[i - 1] > up[i - 1]:
            up[i] = max(up_b[i], up[i - 1])
        if np.isfinite(dn[i - 1]) and c[i - 1] < dn[i - 1]:
            dn[i] = min(dn_b[i], dn[i - 1])
        d[i] = d[i - 1]
        if d[i - 1] < 0 and c[i] > dn[i - 1]:
            d[i] = 1
        elif d[i - 1] > 0 and c[i] < up[i - 1]:
            d[i] = -1
        out[i] = up[i] if d[i] > 0 else dn[i]
    return pd.Series(out, index=df.index), pd.Series(d, index=df.index)


@register
class Supertrend(Strategy):
    id = "supertrend"
    name = "Supertrend"
    category = "Volatility"
    description = "A trend line set a multiple of ATR away from price: green below price in uptrends, red above it in downtrends. Doubles as a trailing stop."
    params = [Param("atr", "ATR period", 10, 2, 100), Param("mult", "Multiplier", 3.0, 0.5, 10, 0.1, "float")]
    rating, level = 4, "Beginner"
    best_for = "Staying in a trend and placing a trailing stop. Late at turns and noisy in ranges."

    def compute(self, df, p, bench=None):
        st, d = supertrend(df, p["atr"], p["mult"])
        colors = pd.Series(np.where(d > 0, UP, DOWN), index=df.index)
        flip_up = (d > 0) & (d.shift() < 0) & st.notna()
        flip_dn = (d < 0) & (d.shift() > 0) & st.notna()
        markers = [marker(ts, True, "Up") for ts in flip_up[flip_up].index] + [marker(ts, False, "Down") for ts in flip_dn[flip_dn].index]
        markers.sort(key=lambda m: str(m["time"]))
        return StrategyResult(lines=[colored_line("Supertrend", st, colors, step=True)], markers=markers)


def adaptive_ranges(df: pd.DataFrame, n: int, mult: float) -> pd.DataFrame:
    """A centre that only moves when price travels a full ATR step away from it, with ranges at ½ and 1 step."""
    step = (ind.atr(df, n) * mult).to_numpy()
    c = df["close"].to_numpy()
    size = len(c)
    avg = np.full(size, np.nan)
    hold = np.full(size, np.nan)
    cur, h = np.nan, np.nan
    for i in range(size):
        if not np.isfinite(step[i]):
            continue
        if not np.isfinite(cur):
            cur, h = c[i], step[i] / 2
        elif c[i] - cur > step[i]:
            cur, h = cur + step[i], step[i] / 2
        elif cur - c[i] > step[i]:
            cur, h = cur - step[i], step[i] / 2
        avg[i], hold[i] = cur, h
    a, hh = pd.Series(avg, index=df.index), pd.Series(hold, index=df.index)
    return pd.DataFrame({"avg": a, "r1": a + hh, "r2": a + 2 * hh, "s1": a - hh, "s2": a - 2 * hh})


@register
class AdaptiveRanges(Strategy):
    id = "adaptive_ranges"
    name = "Adaptive Ranges (predictive)"
    category = "Volatility"
    description = ("Projects where price is likely to range: a centre that steps only after a big move, with resistance (R1, R2) and "
                   "support (S1, S2) bands. Inspired by the 'predictive ranges' idea.")
    params = [Param("atr", "ATR length", 200, 10, 500), Param("mult", "Step (× ATR)", 6.0, 1, 20, 0.5, "float")]
    rating, level = 3, "Intermediate"
    best_for = "Mean-reversion targets and stops in ranges; a break and hold above R2 / below S2 often starts a new leg."

    def compute(self, df, p, bench=None):
        r = adaptive_ranges(df, p["atr"], p["mult"])
        return StrategyResult(lines=[
            line("R2", r["r2"], "#ef4444", width=1) | {"step": True},
            line("R1", r["r1"], "#f87171", width=1) | {"step": True, "style": "dashed"},
            line("Centre", r["avg"], "#eab308", width=2) | {"step": True},
            line("S1", r["s1"], "#4ade80", width=1) | {"step": True, "style": "dashed"},
            line("S2", r["s2"], "#22c55e", width=1) | {"step": True},
        ])


def _linreg_last(s: pd.Series, n: int) -> pd.Series:
    """Value of the least-squares line at the last bar of each window (Pine's linreg(src, n, 0))."""
    x = np.arange(n, dtype=float)
    xm = x.mean()
    denom = ((x - xm) ** 2).sum()

    def f(w):
        slope = ((x - xm) * (w - w.mean())).sum() / denom
        return w.mean() + slope * (n - 1 - xm)

    return s.rolling(n, min_periods=n).apply(f, raw=True)


@register
class SqueezeMomentum(Strategy):
    id = "squeeze"
    name = "Squeeze Momentum"
    category = "Oscillators"
    description = ("Volatility squeeze (Bollinger Bands inside Keltner Channels) and momentum. Dark-blue dots = squeeze on; "
                   "'Fired' marks the release. Bars: momentum up / down.")
    params = [Param("n", "Length", 20, 5, 100), Param("bb", "BB multiplier", 2.0, 0.5, 4, 0.1, "float"), Param("kc", "KC multiplier", 1.5, 0.5, 4, 0.1, "float")]
    rating, level = 4, "Intermediate"
    best_for = "Timing breakouts after quiet periods (pairs well with VCP bases). Says when, not which way: use the trend."

    def compute(self, df, p, bench=None):
        n = int(p["n"])
        c = df["close"]
        basis = ind.sma(c, n)
        sd = c.rolling(n, min_periods=n).std(ddof=0)
        rng = ind.sma(ind.true_range(df), n)
        sq_on = ((basis - p["bb"] * sd) > (basis - p["kc"] * rng)) & ((basis + p["bb"] * sd) < (basis + p["kc"] * rng))
        mid = ((df["high"].rolling(n).max() + df["low"].rolling(n).min()) / 2 + basis) / 2
        mom = _linreg_last(c - mid, n).dropna()
        prev = mom.shift()
        col = np.where(mom >= 0, np.where(mom >= prev, "#22c55e", "#15803d"), np.where(mom <= prev, "#ef4444", "#991b1b"))
        hist = [{"time": t(i), "value": round(float(v), 4), "color": cc} for (i, v), cc in zip(mom.items(), col)]
        dots = pd.Series(0.0, index=mom.index)
        dot_colors = pd.Series(np.where(sq_on.reindex(mom.index).fillna(False).astype(bool), "#1e3a8a", "#64748b"), index=mom.index)
        fired = (~sq_on) & sq_on.shift().fillna(False).astype(bool)
        fired = fired.reindex(mom.index).fillna(False).astype(bool)
        markers = [{"time": t(ts), "position": "aboveBar" if mom[ts] < 0 else "belowBar", "shape": "circle",
                    "color": UP if mom[ts] >= 0 else DOWN, "text": "Fired"} for ts in fired[fired].index[-30:]]
        return StrategyResult(lines=[colored_line("Squeeze", dots, dot_colors, pane="lower", width=3)],
                              histograms=[{"name": "Momentum", "pane": "lower", "data": hist}], markers=markers)


def adx(df: pd.DataFrame, n: int) -> pd.DataFrame:
    h, l = df["high"], df["low"]
    up, dn = h.diff(), -l.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    tr = ind.true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return pd.DataFrame({"adx": dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean(), "pdi": pdi, "mdi": mdi})


@register
class AdxDmi(Strategy):
    id = "adx"
    name = "ADX / DMI (trend strength)"
    category = "Oscillators"
    description = "ADX above 25 = a strong trend (either way); +DI above −DI = buyers in control. Below 20 = no trend: avoid trend signals."
    params = [Param("n", "Length", 14, 2, 100)]
    rating, level = 3, "Intermediate"
    best_for = "Filtering: use trend tools only when ADX is rising above 20-25."

    def compute(self, df, p, bench=None):
        a = adx(df, int(p["n"]))
        flat = pd.Series(25.0, index=a["adx"].dropna().index)
        return StrategyResult(lines=[
            line("ADX", a["adx"], "#eab308", pane="lower"),
            line("+DI", a["pdi"], UP, pane="lower", width=1),
            line("−DI", a["mdi"], DOWN, pane="lower", width=1),
            line("25", flat, "#94a3b866", pane="lower", width=1) | {"style": "dashed"},
        ])


@register
class RsLine(Strategy):
    id = "rs_line"
    name = "RS line vs S&P 500"
    category = "SEPA"
    description = ("Price ÷ S&P 500: rising = outperforming the market. Blue dots = RS line at a 52-week high; "
                   "'RS↑ first' = it got there before price, a classic sign of a leader.")
    params = [Param("lookback", "New-high lookback (bars)", 252, 20, 500)]
    rating, level = 5, "Intermediate"
    best_for = "Picking leaders: the best stocks make RS highs before price highs, especially in corrections."

    def compute(self, df, p, bench=None):
        if bench is None or bench.empty:
            return StrategyResult()
        b = bench["close"].reindex(df.index).ffill()
        rs = (df["close"] / b)
        rs = rs / rs.dropna().iloc[0] * 100 if rs.notna().any() else rs
        n = int(p["lookback"])
        hi = rs >= rs.rolling(n, min_periods=min(n, 60)).max()
        price_hi = df["close"] >= df["close"].rolling(n, min_periods=min(n, 60)).max()
        colors = pd.Series(np.where(hi, "#3b82f6", "#a78bfa"), index=df.index)
        lead = hi & ~price_hi & ~hi.shift().fillna(False).astype(bool)
        markers = [{"time": t(ts), "position": "aboveBar", "shape": "circle", "color": "#3b82f6", "text": "RS↑ first"} for ts in lead[lead].index[-20:]]
        return StrategyResult(lines=[colored_line("RS line", rs, colors, pane="lower")], markers=markers)


@register
class PocketPivots(Strategy):
    id = "pocket_pivot"
    name = "Pocket Pivots"
    category = "SEPA"
    description = "Up days on volume larger than any down day of the last 10 sessions, near the 10/50-day average: institutional buying inside a base."
    params = [Param("days", "Down-volume lookback", 10, 5, 30)]
    rating, level = 4, "Advanced"
    best_for = "Early entries in a base before the breakout, in stocks already in an uptrend."

    def compute(self, df, p, bench=None):
        c, v = df["close"], df["volume"]
        down_vol = v.where(c < c.shift(), 0.0)
        max_down = down_vol.shift().rolling(int(p["days"]), min_periods=int(p["days"])).max()
        ma10, ma50 = ind.sma(c, 10), ind.sma(c, 50)
        pp = (c > c.shift()) & (v > max_down) & (c > ma50) & ((c / ma10 - 1).abs() < 0.04) & (ma50 > ma50.shift(20))
        markers = [{"time": t(ts), "position": "belowBar", "shape": "circle", "color": "#22d3ee", "text": "PP"} for ts in pp[pp].index[-60:]]
        return StrategyResult(markers=markers)


@register
class Donchian(Strategy):
    id = "donchian"
    name = "Donchian Channel (breakouts)"
    category = "Volatility"
    description = "Highest high and lowest low of the last N bars. A close above the top = a new N-day high breakout (the Turtle rule)."
    params = [Param("n", "Length", 20, 5, 300), Param("signals", "Breakout labels", 1, 0, 1, type="select", options=YES_NO)]
    rating, level = 3, "Beginner"
    best_for = "Simple breakout entries and a trailing exit at the lower band (e.g. 10 days)."

    def compute(self, df, p, bench=None):
        n = int(p["n"])
        hi, lo = df["high"].rolling(n).max(), df["low"].rolling(n).min()
        markers = []
        if p["signals"]:
            brk = (df["close"] > hi.shift()) & ~(df["close"].shift() > hi.shift(2)).fillna(False).astype(bool)
            markers = [marker(ts, True, f"{n}d high") for ts in brk[brk].index[-40:]]
        return StrategyResult(lines=[
            line(f"{n}d high", hi, "#22c55e99", width=1) | {"step": True},
            line("Mid", (hi + lo) / 2, "#94a3b866", width=1) | {"style": "dotted"},
            line(f"{n}d low", lo, "#ef444499", width=1) | {"step": True},
        ], markers=markers)


@register
class AnchoredVwap(Strategy):
    id = "avwap"
    name = "Anchored VWAP (from the swing low / high)"
    category = "Moving Averages"
    description = "Average price paid, weighted by volume, since the lowest low (and highest high) of the lookback. Above it, buyers since that point are in profit."
    params = [Param("lookback", "Anchor lookback (bars)", 126, 20, 500), Param("high", "Also from the high", 1, 0, 1, type="select", options=YES_NO)]
    rating, level = 4, "Advanced"
    best_for = "Support / resistance that institutions watch; pullbacks to the AVWAP from a key low are common entries."

    def compute(self, df, p, bench=None):
        d = df.iloc[-int(p["lookback"]):]
        tp = (d["high"] + d["low"] + d["close"]) / 3

        def from_(ts):
            x = d.loc[ts:]
            w = tp.loc[ts:] * x["volume"]
            return w.cumsum() / x["volume"].cumsum().replace(0, np.nan)

        lines = [line("AVWAP (low)", from_(d["low"].idxmin()), "#22d3ee")]
        if p["high"]:
            lines.append(line("AVWAP (high)", from_(d["high"].idxmax()), "#f472b6"))
        return StrategyResult(lines=lines)


# Ratings for the earlier indicators: (rating 1-5, level, best for)
RATINGS = {
    "ma": (4, "Beginner", "The trend at a glance: price above a rising 50/200-day = uptrend."),
    "ma_ribbon": (4, "Beginner", "SEPA trend check: 50 > 150 > 200, all rising."),
    "bollinger": (3, "Intermediate", "Spotting volatility contraction (narrow bands) and stretched moves."),
    "rsi": (3, "Beginner", "Momentum; in strong uptrends RSI stays 40-80, so 'overbought' is not a sell by itself."),
    "macd": (3, "Intermediate", "Momentum shifts and divergences on daily / weekly charts."),
    "ma_cross_bot": (2, "Beginner", "Slow, big-picture trend changes (golden / death cross). Late for entries."),
    "rsi_bot": (2, "Beginner", "Bounces in ranges; dangerous against a strong trend."),
    "trend_template": (5, "Beginner", "Only buying stocks in a confirmed Stage 2 uptrend."),
    "vcp": (5, "Advanced", "The exact buy point (pivot) and a tight stop in a base."),
    "trendlines": (3, "Beginner", "Drawing support / resistance automatically."),
    "move_detector": (4, "Intermediate", "Ranking setups by how ready they are for a big move up or down."),
    "structure_count": (4, "Intermediate", "Confirming a trend from highs and lows (4/4 = clean trend)."),
    "market_stage": (5, "Beginner", "Knowing the cycle stage: buy in Stage 2, avoid Stage 3-4."),
    "pulse": (4, "Intermediate", "Seeing confirmations vs warnings after you buy."),
}


def apply_ratings(registry: dict) -> None:
    for sid, (r, lvl, best) in RATINGS.items():
        cls = registry.get(sid)
        if cls is not None and "rating" not in cls.__dict__:
            cls.rating, cls.level, cls.best_for = r, lvl, best
