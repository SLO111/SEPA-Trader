"""Company fundamentals used by portfolio classification.

REFERENCE holds approximate, rounded values for the built-in universe. It is used as demo data by the
synthetic provider and as a fallback when the live provider has gaps. Values: market cap in $B,
trailing P/E (None = negative/no earnings), dividend yield in %, EPS growth in % (year over year),
beta vs. the S&P 500.
"""

from __future__ import annotations

REFERENCE: dict[str, dict] = {
    "AAPL": {"market_cap_b": 3500, "pe": 34, "dividend_yield": 0.4, "eps_growth": 8, "beta": 1.2},
    "MSFT": {"market_cap_b": 3600, "pe": 35, "dividend_yield": 0.7, "eps_growth": 12, "beta": 1.0},
    "NVDA": {"market_cap_b": 4300, "pe": 50, "dividend_yield": 0.03, "eps_growth": 60, "beta": 1.9},
    "GOOGL": {"market_cap_b": 3000, "pe": 25, "dividend_yield": 0.3, "eps_growth": 15, "beta": 1.05},
    "AMZN": {"market_cap_b": 2300, "pe": 35, "dividend_yield": 0.0, "eps_growth": 20, "beta": 1.3},
    "META": {"market_cap_b": 1800, "pe": 27, "dividend_yield": 0.3, "eps_growth": 20, "beta": 1.25},
    "TSLA": {"market_cap_b": 1300, "pe": 180, "dividend_yield": 0.0, "eps_growth": -20, "beta": 2.3},
    "AVGO": {"market_cap_b": 1600, "pe": 70, "dividend_yield": 0.7, "eps_growth": 30, "beta": 1.4},
    "AMD": {"market_cap_b": 380, "pe": 100, "dividend_yield": 0.0, "eps_growth": 25, "beta": 1.9},
    "NFLX": {"market_cap_b": 480, "pe": 45, "dividend_yield": 0.0, "eps_growth": 30, "beta": 1.3},
    "CRM": {"market_cap_b": 250, "pe": 38, "dividend_yield": 0.6, "eps_growth": 15, "beta": 1.3},
    "PLTR": {"market_cap_b": 400, "pe": 400, "dividend_yield": 0.0, "eps_growth": 40, "beta": 2.5},
    "CRWD": {"market_cap_b": 120, "pe": None, "dividend_yield": 0.0, "eps_growth": 30, "beta": 1.4},
    "SHOP": {"market_cap_b": 200, "pe": 90, "dividend_yield": 0.0, "eps_growth": 25, "beta": 2.2},
    "SMCI": {"market_cap_b": 30, "pe": 25, "dividend_yield": 0.0, "eps_growth": 10, "beta": 1.6},
    "JPM": {"market_cap_b": 850, "pe": 15, "dividend_yield": 2.0, "eps_growth": 8, "beta": 1.1},
    "V": {"market_cap_b": 650, "pe": 33, "dividend_yield": 0.7, "eps_growth": 11, "beta": 0.95},
    "BRK-B": {"market_cap_b": 1000, "pe": 13, "dividend_yield": 0.0, "eps_growth": 5, "beta": 0.85},
    "JNJ": {"market_cap_b": 450, "pe": 18, "dividend_yield": 2.8, "eps_growth": 4, "beta": 0.45},
    "LLY": {"market_cap_b": 800, "pe": 60, "dividend_yield": 0.7, "eps_growth": 40, "beta": 0.45},
    "UNH": {"market_cap_b": 300, "pe": 14, "dividend_yield": 2.6, "eps_growth": -15, "beta": 0.55},
    "PG": {"market_cap_b": 360, "pe": 23, "dividend_yield": 2.7, "eps_growth": 4, "beta": 0.4},
    "KO": {"market_cap_b": 300, "pe": 23, "dividend_yield": 2.9, "eps_growth": 5, "beta": 0.45},
    "PEP": {"market_cap_b": 200, "pe": 25, "dividend_yield": 3.8, "eps_growth": 2, "beta": 0.5},
    "WMT": {"market_cap_b": 800, "pe": 38, "dividend_yield": 0.9, "eps_growth": 10, "beta": 0.6},
    "COST": {"market_cap_b": 400, "pe": 50, "dividend_yield": 0.5, "eps_growth": 9, "beta": 0.85},
    "XOM": {"market_cap_b": 480, "pe": 15, "dividend_yield": 3.5, "eps_growth": -5, "beta": 0.85},
    "CVX": {"market_cap_b": 290, "pe": 17, "dividend_yield": 4.4, "eps_growth": -10, "beta": 0.9},
    "T": {"market_cap_b": 190, "pe": 16, "dividend_yield": 4.0, "eps_growth": 5, "beta": 0.6},
    "VZ": {"market_cap_b": 175, "pe": 10, "dividend_yield": 6.5, "eps_growth": 2, "beta": 0.4},
    "MO": {"market_cap_b": 100, "pe": 10, "dividend_yield": 7.0, "eps_growth": 3, "beta": 0.55},
    "O": {"market_cap_b": 50, "pe": 55, "dividend_yield": 5.6, "eps_growth": 3, "beta": 0.85},
    "NEE": {"market_cap_b": 160, "pe": 25, "dividend_yield": 2.9, "eps_growth": 7, "beta": 0.6},
    "DUK": {"market_cap_b": 95, "pe": 20, "dividend_yield": 3.5, "eps_growth": 6, "beta": 0.45},
    "CAT": {"market_cap_b": 250, "pe": 25, "dividend_yield": 1.2, "eps_growth": 0, "beta": 1.1},
    "GE": {"market_cap_b": 300, "pe": 45, "dividend_yield": 0.4, "eps_growth": 25, "beta": 1.2},
    "SPY": {"market_cap_b": None, "pe": 26, "dividend_yield": 1.2, "eps_growth": 8, "beta": 1.0, "etf": True},
    "QQQ": {"market_cap_b": None, "pe": 33, "dividend_yield": 0.5, "eps_growth": 12, "beta": 1.15, "etf": True},
}

EMPTY = {"market_cap_b": None, "pe": None, "dividend_yield": 0.0, "eps_growth": None, "beta": None}


def reference(symbol: str) -> dict:
    return dict(REFERENCE.get(symbol.upper(), EMPTY))
