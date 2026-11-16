"""Company overview data for the ticker page and PDF report.

`synthetic_company` builds deterministic demo data consistent with the reference fundamentals.
It deliberately leaves out news, named holders and insider trades: those cannot be faked honestly.
`yfinance_company` maps Yahoo Finance data, section by section, tolerating missing pieces.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from .fundamentals import reference
from .universe import SYMBOLS

SECTOR_PS = {  # typical price/sales by sector, used to size demo revenue
    "Technology": 9, "Communication Services": 5, "Consumer Discretionary": 2.5, "Consumer Staples": 2,
    "Financials": 3, "Health Care": 4, "Energy": 1.4, "Utilities": 3, "Industrials": 2.5, "Real Estate": 9, "ETF": 1,
}
SECTOR_GROSS = {
    "Technology": 0.65, "Communication Services": 0.58, "Consumer Discretionary": 0.35, "Consumer Staples": 0.40,
    "Financials": 0.60, "Health Care": 0.68, "Energy": 0.30, "Utilities": 0.45, "Industrials": 0.32, "Real Estate": 0.70, "ETF": 0.5,
}


def empty_company(symbol: str) -> dict:
    meta = SYMBOLS.get(symbol, {})  # names for non-universe symbols come from Yahoo's profile when available
    return {
        "symbol": symbol, "name": meta.get("name", symbol), "sector": meta.get("sector", ""), "industry": "",
        "exchange": meta.get("exchange", ""), "currency": "USD", "demo": False,
        "profile": {"description": "", "website": None, "employees": None, "headquarters": None},
        "stats": {}, "valuation": {}, "profitability": {}, "health": {},
        "dividends": {"yield": None, "annual": None, "payout_ratio": None, "ex_date": None, "history": []},
        "financials": {"annual": [], "quarterly": []},
        "earnings": {"next_date": None, "history": []},
        "analysts": None,
        "ownership": {"institutional_pct": None, "insider_pct": None, "top_holders": [], "insider_transactions": []},
        "news": [],
    }


# ------------------------------------------------------------------ synthetic

def synthetic_company(symbol: str, history: pd.DataFrame, dividends: pd.Series) -> dict:
    symbol = symbol.upper()
    out = empty_company(symbol)
    ref = reference(symbol)
    meta = SYMBOLS.get(symbol, {"name": symbol, "sector": "Other", "exchange": ""})
    sector = meta.get("sector", "Other")
    rng = np.random.default_rng(int(hashlib.sha256(f"co:{symbol}".encode()).hexdigest()[:8], 16))
    price = float(history["close"].iloc[-1])
    cap_b = ref.get("market_cap_b") or 50.0
    pe = ref.get("pe")
    growth = (ref.get("eps_growth") or 5) / 100
    shares = cap_b * 1e9 / price

    ps = SECTOR_PS.get(sector, 3) * rng.uniform(0.8, 1.2)
    revenue_ttm = cap_b * 1e9 / ps
    net_ttm = cap_b * 1e9 / pe if pe else -revenue_ttm * rng.uniform(0.02, 0.08)
    gross_m = SECTOR_GROSS.get(sector, 0.45) * rng.uniform(0.9, 1.1)
    op_m = max(min(net_ttm / revenue_ttm * 1.25, gross_m - 0.05), -0.3)
    rev_growth = max(min(growth * 0.6 + rng.normal(0.04, 0.02), 0.6), -0.2)

    annual, quarterly = [], []
    year = date.today().year - 1
    for i in range(4):  # most recent first
        k = (1 + rev_growth) ** -i
        rev = revenue_ttm * k
        ni = net_ttm * k * rng.uniform(0.92, 1.08)
        assets = rev * rng.uniform(1.2, 2.2)
        equity = assets * rng.uniform(0.3, 0.6)
        debt = assets * rng.uniform(0.1, 0.35)
        ocf = ni * rng.uniform(1.1, 1.4) if ni > 0 else ni * 0.5
        capex = -rev * rng.uniform(0.03, 0.09)
        annual.append({
            "period": str(year - i), "revenue": rev, "gross_profit": rev * gross_m, "operating_income": rev * op_m,
            "net_income": ni, "eps": ni / shares, "total_assets": assets, "total_liabilities": assets - equity,
            "equity": equity, "cash": assets * rng.uniform(0.05, 0.2), "debt": debt,
            "operating_cash_flow": ocf, "capex": capex, "free_cash_flow": ocf + capex,
        })
    q_growth = (1 + rev_growth) ** 0.25 - 1
    last_q_end = pd.Timestamp(date.today()) - pd.offsets.QuarterEnd(1)
    for i in range(8):
        rev = revenue_ttm / 4 * (1 + q_growth) ** -i * rng.uniform(0.95, 1.05)
        ni = net_ttm / 4 * (1 + q_growth) ** -i * rng.uniform(0.88, 1.12)
        quarterly.append({
            "period": (last_q_end - pd.offsets.QuarterEnd(i)).strftime("%Y-%m-%d"), "revenue": rev,
            "gross_profit": rev * gross_m, "operating_income": rev * op_m, "net_income": ni, "eps": ni / shares,
        })
    for row in annual + quarterly:
        for k, v in row.items():
            if isinstance(v, float):
                row[k] = round(v, 4 if k == "eps" else 0)
    out["financials"] = {"annual": annual, "quarterly": quarterly}

    # Companies report 3-6 weeks after the quarter ends.
    report_lag = int(rng.integers(21, 42))
    hist = []
    for q in quarterly[:8]:
        reported = pd.Timestamp(q["period"]) + pd.Timedelta(days=report_lag)
        if reported > pd.Timestamp(date.today()):
            continue
        est = q["eps"] * rng.uniform(0.9, 1.02)
        hist.append({"date": reported.strftime("%Y-%m-%d"), "eps_estimate": round(est, 2), "eps_actual": round(q["eps"], 2),
                     "surprise_pct": round((q["eps"] / est - 1) * 100, 1) if est else None})
    next_q_end = last_q_end + pd.offsets.QuarterEnd(1)
    next_report = next_q_end + pd.Timedelta(days=report_lag)
    if next_report <= pd.Timestamp(date.today()):
        next_report = pd.Timestamp(date.today()) + pd.Timedelta(days=int(rng.integers(3, 20)))
    next_date = next_report.strftime("%Y-%m-%d")
    out["earnings"] = {"next_date": next_date, "history": hist}

    last = annual[0]
    hi52, lo52 = float(history["high"].iloc[-252:].max()), float(history["low"].iloc[-252:].min())
    y = ref.get("dividend_yield") or 0
    out.update({
        "name": meta["name"], "sector": sector, "industry": sector, "exchange": meta.get("exchange", ""), "demo": True,
        "profile": {
            "description": f"{meta['name']} is a {sector.lower()} company listed on the {meta.get('exchange', 'US')} exchange. "
                           "This is demo data; connect a live data provider for the full company profile.",
            "website": None, "employees": None, "headquarters": None,
        },
        "stats": {
            "market_cap_b": cap_b, "shares_outstanding_m": round(shares / 1e6, 1), "beta": ref.get("beta"),
            "week52_high": round(hi52, 2), "week52_low": round(lo52, 2),
            "avg_volume": int(history["volume"].iloc[-50:].mean()), "eps_ttm": round(net_ttm / shares, 2),
        },
        "valuation": {
            "pe": pe, "forward_pe": round(pe / (1 + max(growth, -0.5)), 1) if pe else None,
            "peg": round(pe / (growth * 100), 2) if pe and growth > 0 else None,
            "ps": round(ps, 1), "pb": round(cap_b * 1e9 / last["equity"], 1),
            "ev_ebitda": round((cap_b * 1e9 + last["debt"] - last["cash"]) / max(last["operating_income"] * 1.15, 1), 1) if last["operating_income"] > 0 else None,
        },
        "profitability": {
            "gross_margin": round(gross_m * 100, 1), "operating_margin": round(op_m * 100, 1),
            "net_margin": round(net_ttm / revenue_ttm * 100, 1),
            "roe": round(last["net_income"] / last["equity"] * 100, 1), "roa": round(last["net_income"] / last["total_assets"] * 100, 1),
            "revenue_growth": round(rev_growth * 100, 1), "eps_growth": ref.get("eps_growth"),
        },
        "health": {
            "cash_b": round(last["cash"] / 1e9, 2), "debt_b": round(last["debt"] / 1e9, 2),
            "debt_to_equity": round(last["debt"] / last["equity"], 2), "current_ratio": round(rng.uniform(0.8, 2.5), 2),
        },
        "dividends": {
            "yield": y, "annual": round(price * y / 100, 2) if y else None,
            "payout_ratio": round(min(y / 100 * pe * 100, 150), 1) if y and pe else None,
            "ex_date": dividends.index[-1].strftime("%Y-%m-%d") if len(dividends) else None,
            "history": [{"date": d.strftime("%Y-%m-%d"), "amount": round(float(a), 4)} for d, a in dividends.items()][-12:],
        },
    })

    score = 2.2 - growth * 2 + rng.normal(0, 0.25)  # 1 = strong buy ... 5 = strong sell
    score = float(min(max(score, 1.3), 3.8))
    n = int(rng.integers(12, 45))
    weights = np.array([max(0.1, 2.6 - score), max(0.1, 3 - abs(score - 2)), max(0.1, 3 - abs(score - 3) * 1.5), max(0.05, score - 2.5), max(0.02, score - 3.2)])
    counts = np.round(weights / weights.sum() * n).astype(int)
    target = price * (1 + rng.uniform(0.03, 0.25) * (3.2 - score))
    out["analysts"] = _analysts(
        dict(zip(["strong_buy", "buy", "hold", "sell", "strong_sell"], map(int, counts))), score,
        target, target * rng.uniform(1.15, 1.4), target * rng.uniform(0.6, 0.85), price,
    )
    out["ownership"]["institutional_pct"] = round(float(rng.uniform(55, 85)), 1)
    out["ownership"]["insider_pct"] = round(float(rng.uniform(0.1, 3)), 2)
    return out


def _analysts(counts: dict, score: float | None, mean: float | None, high: float | None, low: float | None, price: float) -> dict:
    total = sum(counts.values())
    if score is None and total:
        score = sum(v * w for v, w in zip(counts.values(), [1, 2, 3, 4, 5])) / total
    rating = None
    if score is not None:
        rating = "Strong Buy" if score < 1.5 else "Buy" if score < 2.5 else "Hold" if score < 3.5 else "Sell" if score < 4.5 else "Strong Sell"
    return {
        "rating": rating, "score": round(score, 2) if score is not None else None, "counts": counts, "total": total,
        "target_mean": round(mean, 2) if mean else None, "target_high": round(high, 2) if high else None,
        "target_low": round(low, 2) if low else None,
        "upside_pct": round((mean / price - 1) * 100, 1) if mean and price else None,
    }


# ------------------------------------------------------------------ yfinance

def _num(v):
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _row(df: pd.DataFrame | None, *names: str):
    if df is None or df.empty:
        return {}
    for n in names:
        if n in df.index:
            return {c: _num(v) for c, v in df.loc[n].items()}
    return {}


def _statements(income: pd.DataFrame, balance: pd.DataFrame | None, cash: pd.DataFrame | None, quarterly: bool) -> list[dict]:
    if income is None or income.empty:
        return []
    rows = {
        "revenue": _row(income, "Total Revenue", "Operating Revenue"),
        "gross_profit": _row(income, "Gross Profit"),
        "operating_income": _row(income, "Operating Income", "EBIT"),
        "net_income": _row(income, "Net Income", "Net Income Common Stockholders"),
        "eps": _row(income, "Diluted EPS", "Basic EPS"),
    }
    if not quarterly:
        rows |= {
            "total_assets": _row(balance, "Total Assets"),
            "total_liabilities": _row(balance, "Total Liabilities Net Minority Interest", "Total Liabilities"),
            "equity": _row(balance, "Stockholders Equity", "Common Stock Equity"),
            "cash": _row(balance, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"),
            "debt": _row(balance, "Total Debt"),
            "operating_cash_flow": _row(cash, "Operating Cash Flow"),
            "capex": _row(cash, "Capital Expenditure"),
            "free_cash_flow": _row(cash, "Free Cash Flow"),
        }
    out = []
    for col in list(income.columns)[: 8 if quarterly else 4]:
        period = col.strftime("%Y-%m-%d") if quarterly else str(col.year)
        out.append({"period": period, **{k: v.get(col) for k, v in rows.items()}})
    return out


def _epoch_date(v) -> str | None:
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return None


def yfinance_company(symbol: str, history: pd.DataFrame, dividends: pd.Series) -> dict:
    import yfinance as yf

    symbol = symbol.upper()
    out = empty_company(symbol)
    t = yf.Ticker(symbol)
    try:
        info = t.info or {}
    except Exception:
        info = {}
    price = float(history["close"].iloc[-1])
    pct = lambda k: round(info[k] * 100, 2) if _num(info.get(k)) is not None else None
    r = lambda k, d=2: round(info[k], d) if _num(info.get(k)) is not None else None
    hq = ", ".join(x for x in (info.get("city"), info.get("state"), info.get("country")) if x) or None
    out.update({
        "name": info.get("longName") or info.get("shortName") or out["name"],
        "sector": info.get("sector") or out["sector"], "industry": info.get("industry") or "",
        "exchange": info.get("fullExchangeName") or info.get("exchange") or out["exchange"],
        "currency": info.get("currency") or "USD",
        "profile": {"description": info.get("longBusinessSummary") or "", "website": info.get("website"),
                    "employees": info.get("fullTimeEmployees"), "headquarters": hq},
        "stats": {
            "market_cap_b": round(info["marketCap"] / 1e9, 1) if info.get("marketCap") else None,
            "shares_outstanding_m": round(info["sharesOutstanding"] / 1e6, 1) if info.get("sharesOutstanding") else None,
            "beta": r("beta"), "week52_high": r("fiftyTwoWeekHigh"), "week52_low": r("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"), "eps_ttm": r("trailingEps"),
        },
        "valuation": {"pe": r("trailingPE", 1), "forward_pe": r("forwardPE", 1), "peg": r("trailingPegRatio"),
                      "ps": r("priceToSalesTrailing12Months", 1), "pb": r("priceToBook", 1), "ev_ebitda": r("enterpriseToEbitda", 1)},
        "profitability": {"gross_margin": pct("grossMargins"), "operating_margin": pct("operatingMargins"),
                          "net_margin": pct("profitMargins"), "roe": pct("returnOnEquity"), "roa": pct("returnOnAssets"),
                          "revenue_growth": pct("revenueGrowth"), "eps_growth": pct("earningsGrowth")},
        "health": {"cash_b": round(info["totalCash"] / 1e9, 2) if info.get("totalCash") else None,
                   "debt_b": round(info["totalDebt"] / 1e9, 2) if info.get("totalDebt") else None,
                   "debt_to_equity": round(info["debtToEquity"] / 100, 2) if _num(info.get("debtToEquity")) is not None else None,
                   "current_ratio": r("currentRatio")},
        "dividends": {
            "yield": pct("trailingAnnualDividendYield"), "annual": r("dividendRate"), "payout_ratio": pct("payoutRatio"),
            "ex_date": _epoch_date(info.get("exDividendDate")),
            "history": [{"date": d.strftime("%Y-%m-%d"), "amount": round(float(a), 4)} for d, a in dividends.items()][-12:],
        },
    })
    try:
        out["financials"] = {
            "annual": _statements(t.income_stmt, t.balance_sheet, t.cashflow, quarterly=False),
            "quarterly": _statements(t.quarterly_income_stmt, None, None, quarterly=True),
        }
    except Exception:
        pass
    try:
        ed = t.earnings_dates
        if ed is not None and not ed.empty:
            ed = ed.copy()
            ed.index = ed.index.tz_localize(None) if ed.index.tz else ed.index
            future = ed[ed.index > pd.Timestamp.now()]
            past = ed[ed["Reported EPS"].notna()].head(8)
            out["earnings"] = {
                "next_date": future.index.min().strftime("%Y-%m-%d") if len(future) else None,
                "history": [{"date": i.strftime("%Y-%m-%d"), "eps_estimate": _num(row.get("EPS Estimate")),
                             "eps_actual": _num(row.get("Reported EPS")), "surprise_pct": _num(row.get("Surprise(%)"))} for i, row in past.iterrows()],
            }
    except Exception:
        pass
    try:
        rec = t.recommendations
        counts = {}
        if rec is not None and not rec.empty:
            row = rec.iloc[0]
            counts = {"strong_buy": int(row.get("strongBuy", 0)), "buy": int(row.get("buy", 0)), "hold": int(row.get("hold", 0)),
                      "sell": int(row.get("sell", 0)), "strong_sell": int(row.get("strongSell", 0))}
        out["analysts"] = _analysts(counts, _num(info.get("recommendationMean")), _num(info.get("targetMeanPrice")),
                                    _num(info.get("targetHighPrice")), _num(info.get("targetLowPrice")), price)
    except Exception:
        pass
    own = out["ownership"]
    own["institutional_pct"], own["insider_pct"] = pct("heldPercentInstitutions"), pct("heldPercentInsiders")
    try:
        ih = t.institutional_holders
        if ih is not None and not ih.empty:
            own["top_holders"] = [{"name": str(x.get("Holder")), "pct": round(_num(x.get("pctHeld")) * 100, 2) if _num(x.get("pctHeld")) else None,
                                   "shares": _num(x.get("Shares")), "value": _num(x.get("Value"))} for _, x in ih.head(10).iterrows()]
    except Exception:
        pass
    try:
        it = t.insider_transactions
        if it is not None and not it.empty:
            own["insider_transactions"] = [{
                "date": pd.Timestamp(x.get("Start Date")).strftime("%Y-%m-%d") if x.get("Start Date") is not None else None,
                "insider": str(x.get("Insider") or ""), "position": str(x.get("Position") or ""),
                "transaction": str(x.get("Text") or x.get("Transaction") or ""), "shares": _num(x.get("Shares")), "value": _num(x.get("Value")),
            } for _, x in it.head(15).iterrows()]
    except Exception:
        pass
    try:
        news = []
        for n in (t.news or [])[:12]:
            c = n.get("content", n)
            url = (c.get("canonicalUrl") or {}).get("url") or c.get("link")
            pub = c.get("pubDate") or _epoch_date(c.get("providerPublishTime"))
            title = c.get("title")
            if title and url:
                news.append({"title": title, "url": url, "publisher": (c.get("provider") or {}).get("displayName") or c.get("publisher"), "published": pub})
        out["news"] = news
    except Exception:
        pass
    return out
