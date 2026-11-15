"""Portfolio math: holdings from a transaction ledger (average-cost method), daily value series,
time-weighted performance, dividends received, and automatic profile classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass
class Txn:
    date: date
    symbol: str
    side: str  # buy | sell
    shares: float
    price: float
    fees: float = 0.0


class LedgerError(ValueError):
    pass


# ---------------------------------------------------------------- holdings

def holdings(txns: list[Txn]) -> dict[str, dict]:
    """Current positions with average cost, plus realized P/L, using the average-cost method."""
    pos: dict[str, dict] = {}
    for t in sorted(txns, key=lambda t: (t.date, 0 if t.side == "buy" else 1)):
        p = pos.setdefault(t.symbol, {"shares": 0.0, "cost": 0.0, "realized": 0.0, "first_buy": t.date})
        if t.side == "buy":
            p["shares"] += t.shares
            p["cost"] += t.shares * t.price + t.fees
        else:
            if t.shares > p["shares"] + 1e-9:
                raise LedgerError(f"Cannot sell {t.shares:g} {t.symbol}: only {p['shares']:g} held on {t.date}")
            avg = p["cost"] / p["shares"] if p["shares"] else 0.0
            p["realized"] += t.shares * (t.price - avg) - t.fees
            p["cost"] -= avg * t.shares
            p["shares"] -= t.shares
    for p in pos.values():
        if p["shares"] < 1e-9:
            p["shares"], p["cost"] = 0.0, 0.0
        p["avg_cost"] = p["cost"] / p["shares"] if p["shares"] else 0.0
    return pos


def validate(txns: list[Txn]) -> None:
    holdings(txns)  # raises LedgerError on overselling


# ---------------------------------------------------------------- value series & performance

def value_series(txns: list[Txn], closes: dict[str, pd.Series]) -> pd.DataFrame:
    """Daily market value and net external cash flow (buys +, sells -) from the first trade onward."""
    if not txns:
        return pd.DataFrame(columns=["value", "flow"])
    start = pd.Timestamp(min(t.date for t in txns))
    idx = sorted(set().union(*[s.index[s.index >= start] for s in closes.values() if len(s)]))
    if not idx:
        return pd.DataFrame(columns=["value", "flow"])
    idx = pd.DatetimeIndex(idx)
    value = pd.Series(0.0, index=idx)
    flow = pd.Series(0.0, index=idx)
    for sym in {t.symbol for t in txns}:
        delta = pd.Series(0.0, index=idx)
        for t in txns:
            if t.symbol != sym:
                continue
            day = idx[idx.searchsorted(pd.Timestamp(t.date))] if pd.Timestamp(t.date) <= idx[-1] else None
            if day is None:
                continue
            signed = t.shares if t.side == "buy" else -t.shares
            delta[day] += signed
            flow[day] += signed * t.price + (t.fees if t.side == "buy" else -t.fees)
        shares = delta.cumsum()
        px = closes.get(sym, pd.Series(dtype=float)).reindex(idx).ffill()
        value += (shares * px).fillna(0.0)
    return pd.DataFrame({"value": value, "flow": flow})


def twr_index(vs: pd.DataFrame) -> pd.Series:
    """Time-weighted return index (starts at 1.0); neutral to deposits and withdrawals."""
    if vs.empty:
        return pd.Series(dtype=float)
    v, f = vs["value"].to_numpy(), vs["flow"].to_numpy()
    out = np.ones(len(v))
    for i in range(1, len(v)):
        r = (v[i] - f[i]) / v[i - 1] - 1 if v[i - 1] > 0 else 0.0
        out[i] = out[i - 1] * (1 + r)
    return pd.Series(out, index=vs.index)


PERIODS = {"1D": 1, "1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}


def period_start(index: pd.DatetimeIndex, period: str) -> pd.Timestamp:
    if period == "ALL" or len(index) == 0:
        return index[0]
    if period == "YTD":
        jan1 = pd.Timestamp(year=index[-1].year, month=1, day=1)
        prior = index[index < jan1]
        return prior[-1] if len(prior) else index[0]
    n = PERIODS[period]
    return index[max(0, len(index) - 1 - n)]


def dividends_received(txns: list[Txn], dividends: dict[str, pd.Series]) -> list[dict]:
    """Cash dividends paid on shares held before each ex-dividend date."""
    out = []
    for sym, divs in dividends.items():
        sym_txns = [t for t in txns if t.symbol == sym]
        for ex, amount in divs.items():
            held = sum((t.shares if t.side == "buy" else -t.shares) for t in sym_txns if pd.Timestamp(t.date) < ex)
            if held > 1e-9:
                out.append({"date": ex.strftime("%Y-%m-%d"), "symbol": sym, "per_share": round(float(amount), 4), "shares": held, "amount": round(held * float(amount), 2)})
    return sorted(out, key=lambda d: d["date"])


# ---------------------------------------------------------------- classification

DEFENSIVE_SECTORS = {"Consumer Staples", "Utilities", "Health Care", "Real Estate"}

PROFILES: dict[str, dict] = {
    "aggressive": {"label": "Aggressive Growth", "description": "High-beta, high-volatility growth stocks: big upside, big drawdowns."},
    "growth": {"label": "Growth", "description": "Companies growing earnings fast, with solid price performance."},
    "momentum": {"label": "Momentum", "description": "Stocks with strong recent price performance and market leadership."},
    "conservative": {"label": "Conservative", "description": "Low-beta, low-volatility large companies. Smaller swings."},
    "dividend": {"label": "Dividend Income", "description": "High dividend yield for passive income."},
    "value": {"label": "Value", "description": "Low valuations (P/E) relative to earnings."},
    "blue_chip": {"label": "Blue Chip", "description": "The largest, most established companies."},
    "defensive": {"label": "Defensive", "description": "Sectors that hold up in downturns: staples, utilities, healthcare, real estate."},
    "small_cap": {"label": "Small & Mid Cap", "description": "Smaller companies with more room to grow and more risk."},
    "speculative": {"label": "Speculative", "description": "Very volatile or unprofitable companies."},
    "balanced": {"label": "Balanced", "description": "Diversified across sectors with no single dominant style."},
    "concentrated": {"label": "Concentrated", "description": "Most of the money sits in a single sector."},
}


def _clip(x: float) -> float:
    return float(min(max(x, 0.0), 1.0))


def stock_metrics(close: pd.Series, bench_close: pd.Series | None, beta_hint: float | None = None) -> dict:
    """Risk metrics from prices. A published beta (`beta_hint`) is preferred over one estimated from one year of prices."""
    r = close.pct_change().dropna().iloc[-252:]
    vol = float(r.std() * np.sqrt(252)) if len(r) > 20 else None
    beta = None
    if bench_close is not None and len(r) > 20:
        b = bench_close.pct_change().reindex(r.index).dropna()
        rr = r.reindex(b.index)
        if b.var() > 0:
            beta = float(np.cov(rr, b)[0, 1] / b.var())
    if beta_hint is not None:
        beta = float(beta_hint)
    ret = lambda n: float(close.iloc[-1] / close.iloc[-1 - n] - 1) if len(close) > n else None
    return {"volatility": vol, "beta": beta, "return_6m": ret(126), "return_12m": ret(252)}


def stock_scores(f: dict, m: dict) -> dict[str, float]:
    beta = m.get("beta") if m.get("beta") is not None else 1.0
    vol = m.get("volatility") if m.get("volatility") is not None else 0.3
    y = f.get("dividend_yield") or 0.0
    pe = f.get("pe")
    cap = f.get("market_cap_b")
    g = f.get("eps_growth") or 0.0
    r6, r12 = m.get("return_6m") or 0.0, m.get("return_12m") or 0.0
    defensive = f.get("sector") in DEFENSIVE_SECTORS
    return {
        "aggressive": 0.4 * _clip((beta - 1.0) / 0.6) + 0.3 * _clip((vol - 0.25) / 0.25) + 0.2 * _clip(g / 40) + 0.1 * (y < 0.5),
        "growth": 0.7 * _clip(g / 25) + 0.3 * _clip(r12 / 0.5),
        "momentum": 0.6 * _clip(r6 / 0.35) + 0.4 * _clip(r12 / 0.6),
        "conservative": 0.4 * _clip((1.1 - beta) / 0.5) + 0.3 * _clip((0.32 - vol) / 0.15) + 0.2 * (cap is not None and cap >= 100) + 0.1 * defensive,
        "dividend": _clip((y - 1.0) / 3.0),
        "value": _clip((25 - pe) / 12) if pe and pe > 0 else 0.0,
        # Large AND established: very volatile mega caps are not "blue chips". Capped below 1 because it is a
        # general attribute; a clear investing style should win over it.
        "blue_chip": 0.9 * _clip((cap - 100) / 400) * (1 - _clip((vol - 0.35) / 0.25)) if cap else 0.0,
        "defensive": 1.0 if defensive else 0.0,
        "small_cap": (1.0 if cap < 2 else 0.6 if cap < 10 else 0.0) if cap else 0.0,
        "speculative": _clip(_clip((vol - 0.5) / 0.3) + 0.3 * (pe is None or pe > 150)),
    }


# Tie-break order: more specific styles win over generic ones.
PRIORITY = ["aggressive", "speculative", "dividend", "value", "momentum", "growth", "conservative",
            "defensive", "small_cap", "balanced", "blue_chip", "concentrated"]
# Pairs that say the same thing twice ("Aggressive Growth + Growth").
REDUNDANT = {frozenset(("aggressive", "growth")), frozenset(("conservative", "defensive"))}
ATTRIBUTES = {"blue_chip", "balanced", "concentrated"}


def classify(positions: list[dict]) -> dict:
    """positions: [{symbol, value, sector, fundamentals, metrics}] -> portfolio profile."""
    positions = [p for p in positions if p["value"] > 0]
    total = sum(p["value"] for p in positions)
    if total <= 0:
        return {"primary": None, "label": "Empty", "secondary": [], "scores": [], "risk_level": None, "insights": [], "sectors": []}

    w = {p["symbol"]: p["value"] / total for p in positions}
    scores = {k: 0.0 for k in PROFILES}
    for p in positions:
        for k, v in stock_scores({**p["fundamentals"], "sector": p["sector"]}, p["metrics"]).items():
            scores[k] += w[p["symbol"]] * v

    sectors: dict[str, float] = {}
    for p in positions:
        sectors[p["sector"]] = sectors.get(p["sector"], 0.0) + w[p["symbol"]]
    top_sector, top_w = max(sectors.items(), key=lambda kv: kv[1])
    real_sectors = [s for s in sectors if s not in ("ETF", "Other")]
    # Diversification attributes are capped below 1 so that a clear style (e.g. Aggressive) stays primary.
    scores["concentrated"] = 0.8 * _clip((top_w - 0.4) / 0.4) if len(positions) > 1 or top_w > 0.5 else 0.0
    scores["balanced"] = 0.85 * (0.5 * _clip((len(real_sectors) - 2) / 4) + 0.5 * _clip((0.5 - top_w) / 0.25))

    def wavg(key: str, src: str) -> float | None:
        vals = [(w[p["symbol"]], p[src].get(key)) for p in positions if p[src].get(key) is not None]
        tw = sum(a for a, _ in vals)
        return sum(a * b for a, b in vals) / tw if tw else None

    beta, vol = wavg("beta", "metrics"), wavg("volatility", "metrics")
    yld, pe = wavg("dividend_yield", "fundamentals"), wavg("pe", "fundamentals")
    risk_raw = 0.5 * _clip(((beta or 1.0) - 0.6) / 1.0) + 0.5 * _clip(((vol or 0.25) - 0.15) / 0.45)
    risk_level = 1 + int(round(risk_raw * 4))

    ranked = sorted(scores.items(), key=lambda kv: (-round(kv[1], 3), PRIORITY.index(kv[0])))
    # A clear investing style is the headline; general attributes (blue chip, balanced, concentrated) only lead
    # when no style is strong.
    styles = [(k, v) for k, v in ranked if k not in ATTRIBUTES]
    primary, top = styles[0] if styles[0][1] >= 0.6 else ranked[0]
    secondary: list[str] = []
    for k, v in ranked:
        if k == primary or v < 0.5 or v < top - 0.3 or len(secondary) == 2:
            continue
        if any(frozenset((k, x)) in REDUNDANT for x in [primary, *secondary]):
            continue
        secondary.append(k)
    label = PROFILES[primary]["label"] if primary != "concentrated" else f"{top_sector}-heavy"
    if secondary:
        label += " + " + " + ".join(PROFILES[k]["label"] if k != "concentrated" else f"{top_sector}-heavy" for k in secondary)

    insights = []
    if beta is not None:
        insights.append(f"Weighted beta {beta:.2f} (the market is 1.00): {'more' if beta > 1.05 else 'less' if beta < 0.95 else 'about as'} volatile than the market.")
    if vol is not None:
        insights.append(f"Annualized volatility {vol * 100:.0f}%.")
    if yld is not None:
        insights.append(f"Average dividend yield {yld:.2f}%.")
    if pe is not None:
        insights.append(f"Weighted P/E {pe:.0f}.")
    insights.append(f"{top_w * 100:.0f}% in {top_sector}; {len(sectors)} sector{'s' if len(sectors) != 1 else ''} in total.")

    return {
        "primary": primary,
        "label": label,
        "secondary": secondary,
        "risk_level": risk_level,
        "scores": [{"key": k, "label": PROFILES[k]["label"], "description": PROFILES[k]["description"], "score": round(v * 100)} for k, v in ranked],
        "insights": insights,
        "sectors": [{"sector": s, "weight": round(v * 100, 1)} for s, v in sorted(sectors.items(), key=lambda kv: -kv[1])],
        "weighted": {"beta": beta, "volatility": vol, "dividend_yield": yld, "pe": pe},
    }


# ---------------------------------------------------------------- model portfolios

TEMPLATES: list[dict] = [
    {"id": "aggressive_growth", "name": "Aggressive Growth", "profile": "aggressive", "risk": 5,
     "description": "High-growth tech and disruptors. Highest upside potential with large swings.",
     "symbols": ["NVDA", "AMD", "PLTR", "CRWD", "SHOP", "TSLA", "SMCI"]},
    {"id": "tech_innovation", "name": "Tech Innovation", "profile": "growth", "risk": 4,
     "description": "Profitable technology leaders in AI, cloud and semiconductors.",
     "symbols": ["MSFT", "NVDA", "AVGO", "GOOGL", "META", "CRM", "AMD"]},
    {"id": "momentum_leaders", "name": "Momentum Leaders", "profile": "momentum", "risk": 4,
     "description": "The eight strongest stocks by RS Rating right now. Refreshed from the live scanner.",
     "symbols": [], "dynamic": "rs_leaders"},
    {"id": "quality_growth", "name": "Quality Growth", "profile": "growth", "risk": 3,
     "description": "Profitable compounders with durable earnings growth and small but rising dividends.",
     "symbols": ["AVGO", "MSFT", "COST", "LLY", "V", "AAPL"]},
    {"id": "blue_chip", "name": "Blue Chip Core", "profile": "blue_chip", "risk": 3,
     "description": "America's largest, most established companies across sectors.",
     "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "V", "WMT", "JNJ"]},
    {"id": "balanced", "name": "Balanced", "profile": "balanced", "risk": 3,
     "description": "One or two leaders from each major sector for broad diversification.",
     "symbols": ["AAPL", "MSFT", "AMZN", "JPM", "JNJ", "PG", "XOM", "NEE", "CAT", "V"]},
    {"id": "value", "name": "Value", "profile": "value", "risk": 3,
     "description": "Solid businesses trading at low price-to-earnings multiples.",
     "symbols": ["JPM", "BRK-B", "CVX", "XOM", "VZ", "UNH", "CAT"]},
    {"id": "dividend_income", "name": "Dividend Income", "profile": "dividend", "risk": 2,
     "description": "High-yield payers for passive income: telecom, energy, REITs and staples.",
     "symbols": ["VZ", "MO", "O", "PEP", "CVX", "T", "KO", "JNJ"]},
    {"id": "defensive", "name": "Defensive", "profile": "defensive", "risk": 2,
     "description": "Staples, utilities and healthcare that tend to hold up in downturns.",
     "symbols": ["KO", "PG", "DUK", "NEE", "JNJ", "WMT", "O"]},
    {"id": "conservative", "name": "Conservative", "profile": "conservative", "risk": 1,
     "description": "Low-volatility, large, steady companies for capital preservation.",
     "symbols": ["JNJ", "PG", "KO", "WMT", "BRK-B", "DUK", "V"]},
]
