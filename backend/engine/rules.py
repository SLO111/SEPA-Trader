"""Custom rule-based strategies: entry conditions (all must hold) and exit rules, backtested on daily bars.

Rules JSON:
{
  "entry": [{"type": "price_above_sma", "n": 50}, {"type": "rsi_below", "n": 14, "value": 40}, ...],
  "exit": {"stop_pct": 7, "target_r": 3, "atr_trail": 0, "below_sma": 0, "max_days": 0, "ut_sell": false}
}
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind
from .backtest import report_trades

CONDITIONS: dict[str, dict] = {
    "price_above_sma": {"label": "Price above its N-day average", "params": {"n": 50}},
    "sma_stack": {"label": "50 > 150 > 200-day averages (uptrend)", "params": {}},
    "trend_template": {"label": "Trend Template: all 8 criteria (RS vs the S&P 500 for criterion 8)", "params": {}},
    "stage2": {"label": "Market cycle Stage 2 (markup)", "params": {}},
    "rs_vs_spy": {"label": "Outperforms the S&P 500 by at least X% over N months", "params": {"months": 3, "value": 0}},
    "rsi_below": {"label": "RSI below X (pullback)", "params": {"n": 14, "value": 40}},
    "rsi_above": {"label": "RSI above X (momentum)", "params": {"n": 14, "value": 60}},
    "breakout": {"label": "Close above the prior N-day high", "params": {"n": 20}},
    "volume_surge": {"label": "Volume at least X × its 50-day average", "params": {"value": 1.5}},
    "tight_base_breakout": {"label": "Breakout from a tight base (VCP-style): N-day range under X%", "params": {"n": 20, "value": 15}},
    "ut_bot_buy": {"label": "UT Bot buy signal", "params": {"key": 1, "atr": 10}},
    "supertrend_up": {"label": "Supertrend is up", "params": {"atr": 10, "mult": 3}},
}

DEFAULT_EXIT = {"stop_pct": 7.0, "target_r": 3.0, "atr_trail": 0.0, "below_sma": 0, "max_days": 0, "ut_sell": False}


def _p(c: dict, key: str, default):
    try:
        return type(default)(c.get(key, default))
    except (TypeError, ValueError):
        return default


def condition(df: pd.DataFrame, c: dict, bench: pd.DataFrame | None = None) -> pd.Series:
    t = c.get("type")
    close = df["close"]
    if t == "price_above_sma":
        return close > ind.sma(close, max(2, _p(c, "n", 50)))
    if t == "sma_stack":
        m50, m150, m200 = ind.sma(close, 50), ind.sma(close, 150), ind.sma(close, 200)
        return (m50 > m150) & (m150 > m200) & (close > m50)
    if t == "trend_template":
        from .sepa import template_frame

        ok = template_frame(df).all(axis=1)
        if bench is not None:
            b = bench["close"].reindex(df.index).ffill()
            ok &= (close / close.shift(126)) > (b / b.shift(126))
        return ok
    if t == "stage2":
        from .stages import weekly_stages

        w = weekly_stages(df)["stage"]
        return (w.reindex(df.index, method="ffill") == 2).fillna(False)
    if t == "rs_vs_spy":
        if bench is None:
            return pd.Series(False, index=df.index)
        n = int(_p(c, "months", 3) * 21)
        b = bench["close"].reindex(df.index).ffill()
        return ((close / close.shift(n)) / (b / b.shift(n)) - 1) * 100 >= _p(c, "value", 0.0)
    if t == "rsi_below":
        return ind.rsi(close, max(2, _p(c, "n", 14))) < _p(c, "value", 40.0)
    if t == "rsi_above":
        return ind.rsi(close, max(2, _p(c, "n", 14))) > _p(c, "value", 60.0)
    if t == "breakout":
        return close > df["high"].shift().rolling(max(2, _p(c, "n", 20))).max()
    if t == "volume_surge":
        return df["volume"] >= _p(c, "value", 1.5) * df["volume"].shift().rolling(50).mean()
    if t == "tight_base_breakout":
        n = max(5, _p(c, "n", 20))
        hi, lo = df["high"].shift().rolling(n).max(), df["low"].shift().rolling(n).min()
        return (close > hi) & ((hi / lo - 1) * 100 <= _p(c, "value", 15.0))
    if t == "ut_bot_buy":
        from .strategies.pro_indicators import ut_bot

        _, _, buy, _ = ut_bot(close, ind.atr(df, max(1, _p(c, "atr", 10))), _p(c, "key", 1.0))
        return buy
    if t == "supertrend_up":
        from .strategies.pro_indicators import supertrend

        _, d = supertrend(df, max(2, _p(c, "atr", 10)), _p(c, "mult", 3.0))
        return d > 0
    raise ValueError(f"Unknown condition: {t}")


def run_rules(df: pd.DataFrame, rules: dict, bench: pd.DataFrame | None = None, fees_pct: float = 0.05) -> dict:
    entry = rules.get("entry") or []
    if not entry:
        raise ValueError("Add at least one entry condition.")
    sig = pd.Series(True, index=df.index)
    for c in entry:
        sig &= condition(df, c, bench).reindex(df.index).fillna(False).astype(bool)
    ex = {**DEFAULT_EXIT, **(rules.get("exit") or {})}
    stop_pct, target_r = float(ex["stop_pct"] or 0), float(ex["target_r"] or 0)
    trail, below_n, max_days = float(ex["atr_trail"] or 0), int(ex["below_sma"] or 0), int(ex["max_days"] or 0)
    if stop_pct <= 0 and not trail and not below_n and not max_days and not ex.get("ut_sell"):
        raise ValueError("Add at least one exit rule (a stop, a trailing stop, an average or a time limit).")
    atr = ind.atr(df, 14).to_numpy()
    ma = ind.sma(df["close"], below_n).to_numpy() if below_n else None
    ut_sell = None
    if ex.get("ut_sell"):
        from .strategies.pro_indicators import ut_bot

        ut_sell = ut_bot(df["close"], ind.atr(df, 10), 1.0)[3].to_numpy()
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    s = sig.to_numpy()
    idx = df.index
    trades, reasons = [], []
    i, n = 0, len(df)
    open_last = False
    while i < n:
        if not s[i]:
            i += 1
            continue
        en_i, en_p = i, c[i]
        stop = en_p * (1 - stop_pct / 100) if stop_pct > 0 else -np.inf
        target = en_p + target_r * (en_p - stop) if target_r > 0 and np.isfinite(stop) else np.inf
        j, ex_p, why = i + 1, None, ""
        while j < n:
            if trail and np.isfinite(atr[j - 1]):
                stop = max(stop, c[j - 1] - trail * atr[j - 1])
            if lo[j] <= stop:
                ex_p, why = min(o[j], stop), "stop"
            elif h[j] >= target:
                ex_p, why = max(o[j], target), "target"
            elif ma is not None and np.isfinite(ma[j]) and c[j] < ma[j]:
                ex_p, why = c[j], f"below {below_n}-day"
            elif ut_sell is not None and ut_sell[j]:
                ex_p, why = c[j], "UT Bot sell"
            elif max_days and j - en_i >= max_days:
                ex_p, why = c[j], "time"
            if ex_p is not None:
                break
            j += 1
        if ex_p is None:
            j, ex_p, why, open_last = n - 1, c[-1], "open", True
        trades.append((idx[en_i], float(en_p), idx[j], float(ex_p)))
        reasons.append(why)
        i = j + 1
    out = report_trades(df, trades, fees_pct, open_last=open_last, reasons=reasons)
    if trades:
        wins = [t for t in out["trades"] if t["return_pct"] > 0]
        out["stats"]["exits"] = {r: reasons.count(r) for r in sorted(set(reasons))}
        out["stats"]["profit_factor"] = (round(sum(t["return_pct"] for t in wins) / abs(sum(t["return_pct"] for t in out["trades"] if t["return_pct"] <= 0)), 2)
                                         if any(t["return_pct"] <= 0 for t in out["trades"]) else None)
    return out
