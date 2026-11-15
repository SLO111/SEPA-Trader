"""Market-wide tools: Fear & Greed index, movers, sector rotation, leaders and the stock screener.

All functions are pure: they take price histories / scan rows / fundamentals and return plain dicts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import rsi, sma

# ------------------------------------------------------------------ Fear & Greed

FG_COMPONENTS = {
    "momentum": ("Market momentum", "S&P 500 vs. its 125-day moving average. Far above it signals greed."),
    "strength": ("Stock price strength", "Stocks at 52-week highs minus stocks at 52-week lows."),
    "breadth": ("Stock price breadth", "Share of stocks trading above their 50-day moving average."),
    "volatility": ("Market volatility", "VIX vs. its 50-day average. A spike in volatility signals fear."),
    "safe_haven": ("Safe haven demand", "Stocks vs. Treasury bonds over 20 days. Money fleeing to bonds signals fear."),
    "junk_bonds": ("Junk bond demand", "High-yield vs. investment-grade bonds over 20 days. Appetite for junk signals greed."),
}


def fg_label(score: float) -> str:
    if score < 25:
        return "Extreme Fear"
    if score < 45:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 75:
        return "Greed"
    return "Extreme Greed"


def _rank(s: pd.Series, window: int = 252) -> pd.Series:
    """Score 0-100: where today's value sits within its own trailing year."""
    return s.rolling(window, min_periods=60).rank(pct=True) * 100


def fear_greed(spy: pd.DataFrame, vix: pd.DataFrame | None, stocks: dict[str, pd.DataFrame],
               tlt: pd.DataFrame | None, hyg: pd.DataFrame | None, lqd: pd.DataFrame | None) -> dict:
    idx = spy.index
    c = spy["close"]
    raw: dict[str, pd.Series] = {"momentum": c / sma(c, 125) - 1}

    if stocks:
        highs = pd.DataFrame({s: (d["high"] >= d["high"].rolling(252, min_periods=200).max()) for s, d in stocks.items()}).reindex(idx)
        lows = pd.DataFrame({s: (d["low"] <= d["low"].rolling(252, min_periods=200).min()) for s, d in stocks.items()}).reindex(idx)
        above = pd.DataFrame({s: (d["close"] > sma(d["close"], 50)) for s, d in stocks.items()}).reindex(idx)
        n = len(stocks)
        # smooth daily counts so one noisy day does not swing the index
        raw["strength"] = ((highs.sum(axis=1) - lows.sum(axis=1)) / n).rolling(10, min_periods=1).mean()
        raw["breadth"] = (above.sum(axis=1) / n).rolling(5, min_periods=1).mean()
    if vix is not None and len(vix):
        v = vix["close"].reindex(idx).ffill()
        raw["volatility"] = -(v / sma(v, 50) - 1)  # inverted: high volatility = fear
    if tlt is not None and len(tlt):
        raw["safe_haven"] = c.pct_change(20) - tlt["close"].reindex(idx).ffill().pct_change(20)
    if hyg is not None and lqd is not None and len(hyg) and len(lqd):
        raw["junk_bonds"] = hyg["close"].reindex(idx).ffill().pct_change(20) - lqd["close"].reindex(idx).ffill().pct_change(20)

    scores = pd.DataFrame({k: _rank(v) for k, v in raw.items()})
    index = scores.mean(axis=1, skipna=True).dropna()
    if index.empty:
        return {"score": None, "label": "Insufficient data", "components": [], "history": [], "previous": {}}
    now = float(index.iloc[-1])

    def ago(n: int):
        return round(float(index.iloc[-1 - n]), 1) if len(index) > n else None

    comps = []
    for k, (label, desc) in FG_COMPONENTS.items():
        if k not in scores or pd.isna(scores[k].iloc[-1]):
            continue
        sc = float(scores[k].iloc[-1])
        comps.append({"key": k, "label": label, "description": desc, "score": round(sc, 1), "rating": fg_label(sc),
                      "value": round(float(raw[k].iloc[-1]), 4)})
    hist = index.iloc[-252:]
    return {
        "score": round(now, 1),
        "label": fg_label(now),
        "as_of": index.index[-1].strftime("%Y-%m-%d"),
        "previous": {"close": ago(1), "week": ago(5), "month": ago(21), "year": ago(251)},
        "components": comps,
        "history": [{"time": t.strftime("%Y-%m-%d"), "value": round(float(v), 1)} for t, v in hist.items()],
    }


# ------------------------------------------------------------------ movers

def mover_rows(histories: dict[str, pd.DataFrame], meta: dict[str, dict]) -> list[dict]:
    rows = []
    for s, d in histories.items():
        if len(d) < 60:
            continue
        c, v = d["close"], d["volume"]
        last, prev = float(c.iloc[-1]), float(c.iloc[-2])
        avg_vol = float(v.iloc[-51:-1].mean())
        hi52, lo52 = float(d["high"].iloc[-252:].max()), float(d["low"].iloc[-252:].min())
        rows.append({
            "symbol": s, "name": meta.get(s, {}).get("name", s), "sector": meta.get(s, {}).get("sector", ""),
            "price": round(last, 2), "change": round(last - prev, 2), "change_pct": round((last / prev - 1) * 100, 2),
            "volume": int(v.iloc[-1]), "rel_volume": round(float(v.iloc[-1]) / avg_vol, 2) if avg_vol else None,
            "dollar_volume": float(v.iloc[-1]) * last,
            "week52_high": round(hi52, 2), "week52_low": round(lo52, 2),
            "from_high_pct": round((last / hi52 - 1) * 100, 2), "from_low_pct": round((last / lo52 - 1) * 100, 2),
            "new_high": bool(float(d["high"].iloc[-1]) >= hi52), "new_low": bool(float(d["low"].iloc[-1]) <= lo52),
            "rsi14": round(float(rsi(c, 14).iloc[-1]), 1),
            "above_ma50": bool(last > float(sma(c, 50).iloc[-1])),
            "return_1w": round((last / float(c.iloc[-6]) - 1) * 100, 2),
            "return_1m": round((last / float(c.iloc[-22]) - 1) * 100, 2),
            "return_3m": round((last / float(c.iloc[-64]) - 1) * 100, 2) if len(c) > 64 else None,
        })
    return rows


def movers(rows: list[dict], kind: str, limit: int = 10) -> list[dict]:
    if kind == "gainers":
        out = sorted([r for r in rows if r["change_pct"] > 0], key=lambda r: -r["change_pct"])
    elif kind == "losers":
        out = sorted([r for r in rows if r["change_pct"] < 0], key=lambda r: r["change_pct"])
    elif kind == "active":
        out = sorted(rows, key=lambda r: -r["dollar_volume"])
    elif kind == "unusual_volume":
        out = sorted([r for r in rows if (r["rel_volume"] or 0) >= 1.5], key=lambda r: -(r["rel_volume"] or 0))
    elif kind == "highs":
        out = sorted(rows, key=lambda r: -r["from_high_pct"])[:limit]
        out = [r for r in out if r["from_high_pct"] >= -3]
    elif kind == "lows":
        out = sorted(rows, key=lambda r: r["from_low_pct"])[:limit]
        out = [r for r in out if r["from_low_pct"] <= 3]
    else:
        raise ValueError(kind)
    return out[:limit]


# ------------------------------------------------------------------ sectors & leaders

def sector_rotation(rows: list[dict], scan: list[dict]) -> list[dict]:
    rs = {r["symbol"]: r["rs_rating"] for r in scan}
    by: dict[str, list[dict]] = {}
    for r in rows:
        if r["sector"]:
            by.setdefault(r["sector"], []).append(r)
    out = []
    for sector, items in by.items():
        mean = lambda k: round(float(np.mean([i[k] for i in items if i[k] is not None])), 2) if any(i[k] is not None for i in items) else None
        rss = [rs[i["symbol"]] for i in items if rs.get(i["symbol"]) is not None]
        out.append({
            "sector": sector, "stocks": len(items), "change_pct": mean("change_pct"),
            "return_1w": mean("return_1w"), "return_1m": mean("return_1m"), "return_3m": mean("return_3m"),
            "avg_rs": round(float(np.mean(rss))) if rss else None,
            "pct_above_ma50": round(100 * sum(i["above_ma50"] for i in items) / len(items)),
            "leaders": [i["symbol"] for i in sorted(items, key=lambda i: -(rs.get(i["symbol"]) or 0))[:3]],
        })
    rank = lambda k: {s["sector"]: i for i, s in enumerate(sorted(out, key=lambda s: -(s[k] or -1e9)))}
    r1, r3 = rank("return_1m"), rank("return_3m")
    n = len(out)
    for s in out:
        delta = r3[s["sector"]] - r1[s["sector"]]  # positive: climbing the ranks recently
        s["rank_1m"], s["rank_3m"] = r1[s["sector"]] + 1, r3[s["sector"]] + 1
        s["trend"] = "Improving" if delta >= 2 else "Weakening" if delta <= -2 else "Steady"
        s["emerging"] = bool(r1[s["sector"]] < max(3, n // 3) and r3[s["sector"]] >= max(3, n // 3))
    return sorted(out, key=lambda s: s["rank_1m"])


def leaders(scan: list[dict], limit: int = 10) -> list[dict]:
    """Market leaders: relative strength first, then Move Detector setup and trend quality."""
    out = []
    for r in scan:
        if r["rs_rating"] is None:
            continue
        score = 0.5 * r["rs_rating"] + 0.3 * (r["bull_score"] or 0) + 0.2 * r["template_passed"] / 8 * 100
        out.append({**r, "leadership": round(score, 1)})
    return sorted(out, key=lambda r: -r["leadership"])[:limit]


# ------------------------------------------------------------------ screener

PRESETS: dict[str, dict] = {
    "undervalued": {"label": "Undervalued", "description": "Profitable, with a P/E of 15 or less, or up to 25 and at least 25% below its sector's median P/E."},
    "garp": {"label": "Growth at a reasonable price", "description": "Earnings growth of 15%+ with a P/E of 30 or less."},
    "dividend": {"label": "High dividend", "description": "Dividend yield of 3% or more."},
    "sepa_leaders": {"label": "SEPA leaders", "description": "Pass all 8 Trend Template criteria with an RS Rating of 80+."},
    "near_highs": {"label": "Near 52-week highs", "description": "Within 5% of the 52-week high."},
    "oversold": {"label": "Oversold", "description": "14-day RSI of 35 or less."},
    "momentum": {"label": "Momentum", "description": "RS Rating of 90+ and above the 50-day moving average."},
}


def screen_rows(movers_: list[dict], scan: list[dict], fundamentals: dict[str, dict]) -> list[dict]:
    sc = {r["symbol"]: r for r in scan}
    by_sector: dict[str, list[float]] = {}
    for m in movers_:
        pe = fundamentals.get(m["symbol"], {}).get("pe")
        if pe and pe > 0:
            by_sector.setdefault(m["sector"], []).append(pe)
    medians = {k: float(np.median(v)) for k, v in by_sector.items()}
    out = []
    for m in movers_:
        f = fundamentals.get(m["symbol"], {})
        s = sc.get(m["symbol"], {})
        pe, g = f.get("pe"), f.get("eps_growth")
        out.append({
            **{k: m[k] for k in ("symbol", "name", "sector", "price", "change_pct", "from_high_pct", "rsi14", "above_ma50", "return_1m", "return_3m")},
            "market_cap_b": f.get("market_cap_b"), "pe": pe, "eps_growth": g,
            "peg": round(pe / g, 2) if pe and g and g > 0 else None,
            "sector_pe": round(medians[m["sector"]], 1) if m["sector"] in medians else None,
            "pe_vs_sector_pct": round((pe / medians[m["sector"]] - 1) * 100, 1) if pe and pe > 0 and m["sector"] in medians else None,
            "dividend_yield": f.get("dividend_yield"), "beta": f.get("beta"),
            "rs_rating": s.get("rs_rating"), "template_passed": s.get("template_passed"),
            "bull_score": s.get("bull_score"), "bear_score": s.get("bear_score"), "vcp": s.get("vcp"),
        })
    return out


def screen(rows: list[dict], preset: str | None = None, sector: str | None = None, min_cap_b: float | None = None,
           max_pe: float | None = None, min_yield: float | None = None, min_rs: float | None = None,
           min_growth: float | None = None, template_only: bool = False, above_ma50: bool = False) -> list[dict]:
    def ok(r: dict) -> bool:
        pe, g, y, rs = r["pe"], r["eps_growth"], r["dividend_yield"] or 0, r["rs_rating"] or 0
        if preset == "undervalued" and not (pe and pe > 0 and (pe <= 15 or (pe <= 25 and r["pe_vs_sector_pct"] is not None and r["pe_vs_sector_pct"] <= -25))):
            return False
        if preset == "garp" and not (pe and 0 < pe <= 30 and g and g >= 15):
            return False
        if preset == "dividend" and y < 3:
            return False
        if preset == "sepa_leaders" and not (r["template_passed"] == 8 and rs >= 80):
            return False
        if preset == "near_highs" and r["from_high_pct"] < -5:
            return False
        if preset == "oversold" and r["rsi14"] > 35:
            return False
        if preset == "momentum" and not (rs >= 90 and r["above_ma50"]):
            return False
        if sector and r["sector"] != sector:
            return False
        if min_cap_b is not None and (r["market_cap_b"] or 0) < min_cap_b:
            return False
        if max_pe is not None and not (pe and 0 < pe <= max_pe):
            return False
        if min_yield is not None and y < min_yield:
            return False
        if min_rs is not None and rs < min_rs:
            return False
        if min_growth is not None and (g is None or g < min_growth):
            return False
        if template_only and r["template_passed"] != 8:
            return False
        if above_ma50 and not r["above_ma50"]:
            return False
        return True

    sort_key = {
        "undervalued": lambda r: r["pe_vs_sector_pct"] if r["pe_vs_sector_pct"] is not None else 0, "garp": lambda r: -(r["eps_growth"] or 0), "dividend": lambda r: -(r["dividend_yield"] or 0),
        "oversold": lambda r: r["rsi14"], "near_highs": lambda r: -r["from_high_pct"],
    }.get(preset or "", lambda r: -(r["rs_rating"] or 0))
    return sorted([r for r in rows if ok(r)], key=sort_key)


# ------------------------------------------------------------------ earnings calendar

def earnings_calendar(entries: dict[str, dict], histories: dict[str, pd.DataFrame], meta: dict[str, dict], today: pd.Timestamp,
                      ahead_days: int = 90, back_days: int = 30) -> dict:
    upcoming, recent = [], []
    for s, e in entries.items():
        name = meta.get(s, {}).get("name", s)
        nd = e.get("next_date")
        if nd and today <= pd.Timestamp(nd) <= today + pd.Timedelta(days=ahead_days):
            last = (e.get("history") or [{}])[0]
            upcoming.append({"symbol": s, "name": name, "date": nd, "days_until": (pd.Timestamp(nd) - today).days,
                             "eps_estimate": e.get("next_eps_estimate"), "last_surprise_pct": last.get("surprise_pct")})
        for h in e.get("history") or []:
            d = pd.Timestamp(h["date"])
            if today - pd.Timedelta(days=back_days) <= d <= today:
                reaction = None
                c = histories.get(s, pd.DataFrame()).get("close")
                if c is not None and len(c):
                    before, after = c[c.index < d], c[c.index > d]
                    if len(before) and len(after):
                        reaction = round((float(after.iloc[0]) / float(before.iloc[-1]) - 1) * 100, 2)
                recent.append({"symbol": s, "name": name, "date": h["date"], "eps_estimate": h.get("eps_estimate"),
                               "eps_actual": h.get("eps_actual"), "surprise_pct": h.get("surprise_pct"), "reaction_pct": reaction})
    return {"upcoming": sorted(upcoming, key=lambda r: r["date"]), "recent": sorted(recent, key=lambda r: r["date"], reverse=True)}
