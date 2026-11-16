"""Technical rating: 15 moving averages + 11 oscillators, each voting Buy / Sell / Neutral, summarised as
Strong sell ... Strong buy (the same family of rules popular charting sites use for their rating).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import atr, ema, rsi, sma


def _wma(s: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n).apply(lambda x: float(np.dot(x, w) / w.sum()), raw=True)


def _vote(buy: bool, sell: bool) -> str:
    return "Buy" if buy else "Sell" if sell else "Neutral"


def _label(score: float) -> str:
    return "Strong buy" if score > 0.5 else "Buy" if score > 0.1 else "Strong sell" if score < -0.5 else "Sell" if score < -0.1 else "Neutral"


def _block(items: list[dict]) -> dict:
    valid = [i for i in items if i["value"] is not None]
    b = sum(i["action"] == "Buy" for i in valid)
    s = sum(i["action"] == "Sell" for i in valid)
    n = len(valid) - b - s
    score = (b - s) / len(valid) if valid else 0.0
    return {"label": _label(score), "score": round(score, 3), "buy": b, "sell": s, "neutral": n, "items": items}


def rating(df: pd.DataFrame) -> dict:
    c, h, lo, v = df["close"], df["high"], df["low"], df["volume"]
    price = float(c.iloc[-1])
    last = lambda s: (None if pd.isna(s.iloc[-1]) else float(s.iloc[-1]))
    prev = lambda s: (None if len(s) < 2 or pd.isna(s.iloc[-2]) else float(s.iloc[-2]))

    # ---- moving averages: price above = Buy, below = Sell
    mas = []
    for n in (10, 20, 30, 50, 100, 200):
        for kind, fn in (("EMA", ema), ("SMA", sma)):
            val = last(fn(c, n)) if len(c) >= n else None
            mas.append({"name": f"{kind} ({n})", "value": val, "action": _vote(val is not None and price > val, val is not None and price < val)})
    tenkan = (h.rolling(9).max() + lo.rolling(9).min()) / 2
    kijun = (h.rolling(26).max() + lo.rolling(26).min()) / 2
    vwma = (c * v).rolling(20).sum() / v.rolling(20).sum()
    hma = _wma(2 * _wma(c, 4) - _wma(c, 9), 3) if len(c) >= 12 else pd.Series([np.nan])
    for name, s in (("Ichimoku base line (9, 26)", kijun), ("VWMA (20)", vwma), ("Hull MA (9)", hma)):
        val = last(s)
        if name.startswith("Ichimoku"):
            t = last(tenkan)
            act = _vote(val is not None and t is not None and t > val and price > val, val is not None and t is not None and t < val and price < val)
        else:
            act = _vote(val is not None and price > val, val is not None and price < val)
        mas.append({"name": name, "value": val, "action": act})

    # ---- oscillators
    osc = []
    r = rsi(c, 14)
    rv, rp = last(r), prev(r)
    osc.append({"name": "RSI (14)", "value": rv, "action": _vote(rv is not None and rv < 30 and rv > (rp or rv), rv is not None and rv > 70 and rv < (rp or rv))})

    ll, hh = lo.rolling(14).min(), h.rolling(14).max()
    k = (100 * (c - ll) / (hh - ll)).rolling(3).mean()
    d = k.rolling(3).mean()
    kv, dv = last(k), last(d)
    osc.append({"name": "Stochastic %K (14, 3, 3)", "value": kv, "action": _vote(kv is not None and dv is not None and kv < 20 and kv > dv, kv is not None and dv is not None and kv > 80 and kv < dv)})

    tp = (h + lo + c) / 3
    md = tp.rolling(20).apply(lambda x: float(np.mean(np.abs(x - x.mean()))), raw=True)
    cci = (tp - tp.rolling(20).mean()) / (0.015 * md)
    cv, cp = last(cci), prev(cci)
    osc.append({"name": "Commodity Channel Index (20)", "value": cv, "action": _vote(cv is not None and cv < -100 and cv > (cp or cv), cv is not None and cv > 100 and cv < (cp or cv))})

    up, dn = h.diff(), -lo.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    tr = atr(df, 14)
    pdi = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / tr
    mdi = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / tr
    adx = (100 * (pdi - mdi).abs() / (pdi + mdi)).ewm(alpha=1 / 14, adjust=False).mean()
    av, ap = last(adx), prev(adx)
    rising = av is not None and ap is not None and av > ap
    osc.append({"name": "Average Directional Index (14)", "value": av,
                "action": _vote(av is not None and av > 20 and rising and last(pdi) > last(mdi), av is not None and av > 20 and rising and last(pdi) < last(mdi))})

    mid = (h + lo) / 2
    ao = sma(mid, 5) - sma(mid, 34)
    aov, aop = last(ao), prev(ao)
    osc.append({"name": "Awesome Oscillator", "value": aov, "action": _vote(aov is not None and aov > 0 and aov > (aop or aov), aov is not None and aov < 0 and aov < (aop or aov))})

    mom = c - c.shift(10)
    mv, mp = last(mom), prev(mom)
    osc.append({"name": "Momentum (10)", "value": mv, "action": _vote(mv is not None and mp is not None and mv > mp, mv is not None and mp is not None and mv < mp)})

    macd = ema(c, 12) - ema(c, 26)
    sig = macd.ewm(span=9, adjust=False).mean()
    m, sg = last(macd), last(sig)
    osc.append({"name": "MACD level (12, 26)", "value": m, "action": _vote(m is not None and sg is not None and m > sg, m is not None and sg is not None and m < sg)})

    rmin, rmax = r.rolling(14).min(), r.rolling(14).max()
    srsi_k = (100 * (r - rmin) / (rmax - rmin)).rolling(3).mean()
    srsi_d = srsi_k.rolling(3).mean()
    sk, sd = last(srsi_k), last(srsi_d)
    osc.append({"name": "Stochastic RSI fast (3, 3, 14, 14)", "value": sk, "action": _vote(sk is not None and sd is not None and sk < 20 and sk > sd, sk is not None and sd is not None and sk > 80 and sk < sd)})

    wr = -100 * (hh - c) / (hh - ll)
    wv, wp = last(wr), prev(wr)
    osc.append({"name": "Williams %R (14)", "value": wv, "action": _vote(wv is not None and wv < -80 and wv > (wp or wv), wv is not None and wv > -20 and wv < (wp or wv))})

    e13 = ema(c, 13)
    bbp = (h - e13) + (lo - e13)
    bv, bp = last(bbp), prev(bbp)
    trend_up = last(e13) is not None and prev(e13) is not None and last(e13) > prev(e13)
    osc.append({"name": "Bull Bear Power", "value": bv, "action": _vote(bv is not None and bp is not None and trend_up and bv > bp and bv < 0 or (bv or 0) > 0 and bv > (bp or 0) and trend_up,
                                                                        bv is not None and bp is not None and not trend_up and bv < bp)})

    bpu = c - pd.concat([lo, c.shift()], axis=1).min(axis=1)
    trr = pd.concat([h, c.shift()], axis=1).max(axis=1) - pd.concat([lo, c.shift()], axis=1).min(axis=1)
    avg = lambda n: bpu.rolling(n).sum() / trr.rolling(n).sum()
    uo = 100 * (4 * avg(7) + 2 * avg(14) + avg(28)) / 7
    uv = last(uo)
    osc.append({"name": "Ultimate Oscillator (7, 14, 28)", "value": uv, "action": _vote(uv is not None and uv > 70, uv is not None and uv < 30)})

    for i in mas + osc:
        if i["value"] is not None:
            i["value"] = round(i["value"], 2)
    om, mm = _block(osc), _block(mas)
    allv = [i for i in osc + mas if i["value"] is not None]
    b = sum(i["action"] == "Buy" for i in allv)
    s = sum(i["action"] == "Sell" for i in allv)
    score = (b - s) / len(allv) if allv else 0.0
    return {
        "summary": {"label": _label(score), "score": round(score, 3), "buy": b, "sell": s, "neutral": len(allv) - b - s},
        "oscillators": om, "moving_averages": mm, "as_of": str(df.index[-1])[:16],
    }
