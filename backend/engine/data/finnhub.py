"""Finnhub (https://finnhub.io) client for the data Yahoo refuses to serve to cloud servers: company profile,
fundamentals, earnings, analyst recommendations and news. The free plan allows 60 requests per minute, so every
request goes through a shared rate limiter."""

from __future__ import annotations

import threading
import time
from datetime import date, timedelta

import httpx

BASE = "https://finnhub.io/api/v1"
MAX_PER_MINUTE = 50  # stay below the free plan's 60/min


class RateLimiter:
    def __init__(self, per_minute: int):
        self.interval = 60.0 / per_minute
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            time.sleep(delay)


_limiter = RateLimiter(MAX_PER_MINUTE)


class Finnhub:
    def __init__(self, api_key: str, client: httpx.Client | None = None, limiter: RateLimiter | None = None):
        self.key = api_key
        self.client = client or httpx.Client(timeout=15)
        self.limiter = limiter or _limiter

    def get(self, path: str, **params):
        self.limiter.wait()
        r = self.client.get(f"{BASE}{path}", params={**params, "token": self.key})
        if r.status_code == 429:  # over the limit: wait a little and retry once
            time.sleep(2)
            self.limiter.wait()
            r = self.client.get(f"{BASE}{path}", params={**params, "token": self.key})
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------ raw endpoints
    def profile(self, symbol: str) -> dict:
        return self.get("/stock/profile2", symbol=symbol) or {}

    def metrics(self, symbol: str) -> dict:
        return (self.get("/stock/metric", symbol=symbol, metric="all") or {}).get("metric") or {}

    def earnings_history(self, symbol: str) -> list[dict]:
        return self.get("/stock/earnings", symbol=symbol) or []

    def earnings_calendar(self, symbol: str, days: int = 120) -> list[dict]:
        today = date.today()
        res = self.get("/calendar/earnings", symbol=symbol, **{"from": today.isoformat(), "to": (today + timedelta(days=days)).isoformat()})
        return (res or {}).get("earningsCalendar") or []

    def recommendations(self, symbol: str) -> list[dict]:
        return self.get("/stock/recommendation", symbol=symbol) or []

    def general_news(self) -> list[dict]:
        """Latest general market headlines."""
        return self.get("/news", category="general") or []

    def news(self, symbol: str, days: int = 10) -> list[dict]:
        today = date.today()
        return self.get("/company-news", symbol=symbol, **{"from": (today - timedelta(days=days)).isoformat(), "to": today.isoformat()}) or []

    # ------------------------------------------------------------ mapped to SEPA Trader's formats
    def fundamentals(self, symbol: str, name: str = "", sector: str = "") -> dict:
        p, m = self.profile(symbol), self.metrics(symbol)
        pe = m.get("peTTM") or m.get("peBasicExclExtraTTM")
        cap_m = p.get("marketCapitalization")
        return {
            "name": p.get("name") or name or symbol,
            "sector": sector or p.get("finnhubIndustry") or "Other",
            "industry": p.get("finnhubIndustry") or "",
            "market_cap_b": round(cap_m / 1000, 1) if cap_m else None,
            "pe": round(pe, 1) if pe and pe > 0 else None,
            "dividend_yield": round(m["dividendYieldIndicatedAnnual"], 2) if m.get("dividendYieldIndicatedAnnual") is not None else None,
            "eps_growth": round(m["epsGrowthTTMYoy"], 1) if m.get("epsGrowthTTMYoy") is not None else None,
            "beta": round(m["beta"], 2) if m.get("beta") is not None else None,
            "source": "finnhub",
        }

    def earnings(self, symbol: str) -> dict:
        hist = self.earnings_history(symbol)
        cal = sorted(self.earnings_calendar(symbol), key=lambda e: e.get("date") or "")
        nxt = cal[0] if cal else {}
        return {
            "next_date": nxt.get("date"),
            "next_eps_estimate": nxt.get("epsEstimate"),
            "history": [
                {"date": e.get("period"), "eps_estimate": e.get("estimate"), "eps_actual": e.get("actual"),
                 "surprise_pct": round(e["surprisePercent"], 1) if e.get("surprisePercent") is not None else None}
                for e in sorted(hist, key=lambda e: e.get("period") or "", reverse=True)
            ],
        }

    def enrich_company(self, co: dict) -> dict:
        """Fill the gaps of a company overview (when Yahoo's profile is blocked) with Finnhub data."""
        sym = co["symbol"]
        try:
            p, m = self.profile(sym), self.metrics(sym)
        except Exception:
            return co
        prof = co.setdefault("profile", {})
        if p:
            co["name"] = co.get("name") if co.get("name") not in (None, "", sym) else p.get("name", sym)
            co["industry"] = co.get("industry") or p.get("finnhubIndustry") or ""
            co["exchange"] = co.get("exchange") or p.get("exchange") or ""
            prof["website"] = prof.get("website") or p.get("weburl")
            prof["headquarters"] = prof.get("headquarters") or p.get("country")
            prof["logo"] = p.get("logo")
            prof["ipo"] = p.get("ipo")

        def fill(section: str, key: str, value):
            sec = co.setdefault(section, {})
            if sec.get(key) is None and value is not None:
                sec[key] = round(value, 2) if isinstance(value, float) else value

        fill("stats", "market_cap_b", round(p["marketCapitalization"] / 1000, 1) if p.get("marketCapitalization") else None)
        fill("stats", "shares_outstanding_m", p.get("shareOutstanding"))
        fill("stats", "beta", m.get("beta"))
        fill("stats", "week52_high", m.get("52WeekHigh"))
        fill("stats", "week52_low", m.get("52WeekLow"))
        fill("stats", "eps_ttm", m.get("epsTTM") or m.get("epsBasicExclExtraItemsTTM"))
        fill("valuation", "pe", m.get("peTTM") or m.get("peBasicExclExtraTTM"))
        fill("valuation", "pb", m.get("pbQuarterly") or m.get("pbAnnual"))
        fill("valuation", "ps", m.get("psTTM"))
        fill("profitability", "gross_margin", m.get("grossMarginTTM"))
        fill("profitability", "operating_margin", m.get("operatingMarginTTM"))
        fill("profitability", "net_margin", m.get("netProfitMarginTTM"))
        fill("profitability", "roe", m.get("roeTTM"))
        fill("profitability", "roa", m.get("roaTTM"))
        fill("profitability", "revenue_growth", m.get("revenueGrowthTTMYoy"))
        fill("profitability", "eps_growth", m.get("epsGrowthTTMYoy"))
        fill("health", "debt_to_equity", m.get("totalDebt/totalEquityQuarterly"))
        fill("health", "current_ratio", m.get("currentRatioQuarterly"))
        fill("dividends", "yield", m.get("dividendYieldIndicatedAnnual"))

        if not co.get("analysts") or not (co["analysts"] or {}).get("total"):
            try:
                rec = self.recommendations(sym)
                if rec:
                    r = rec[0]
                    counts = {"strong_buy": r.get("strongBuy", 0), "buy": r.get("buy", 0), "hold": r.get("hold", 0), "sell": r.get("sell", 0), "strong_sell": r.get("strongSell", 0)}
                    total = sum(counts.values())
                    score = sum(v * w for v, w in zip(counts.values(), [1, 2, 3, 4, 5])) / total if total else None
                    rating = None if score is None else "Strong Buy" if score < 1.5 else "Buy" if score < 2.5 else "Hold" if score < 3.5 else "Sell" if score < 4.5 else "Strong Sell"
                    co["analysts"] = {"rating": rating, "score": round(score, 2) if score else None, "counts": counts, "total": total,
                                      "target_mean": None, "target_high": None, "target_low": None, "upside_pct": None}
            except Exception:
                pass
        if not co.get("news"):
            try:
                co["news"] = [{"title": n["headline"], "url": n["url"], "publisher": n.get("source"),
                               "published": date.fromtimestamp(n["datetime"]).isoformat() if n.get("datetime") else None}
                              for n in self.news(sym)[:12] if n.get("headline") and n.get("url")]
            except Exception:
                pass
        if not (co.get("earnings") or {}).get("history"):
            try:
                co["earnings"] = self.earnings(sym)
            except Exception:
                pass
        return co
