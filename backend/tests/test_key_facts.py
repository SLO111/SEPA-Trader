import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from engine.feed import daily_summary, summary_text
from engine.key_facts import key_facts


def hist(n=300):
    idx = pd.bdate_range("2025-01-01", periods=n)
    c = pd.Series(np.linspace(100, 200, n), index=idx)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6})


def test_key_facts_from_existing_data():
    co = {
        "symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology", "stats": {"market_cap_b": 5180.0},
        "earnings": {"next_date": "2027-01-28", "history": [{"date": "2026-10-30", "eps_estimate": 1.77, "eps_actual": 1.85, "surprise_pct": 4.5}]},
        "analysts": {"rating": "Buy", "total": 49, "target_mean": 346.73, "upside_pct": -2.7},
        "news": [{"title": "Apple wins antitrust ruling", "url": "https://x", "published": datetime.now(timezone.utc).isoformat()},
                 {"title": "Apple unveils new color", "url": "https://y", "published": datetime.now(timezone.utc).isoformat()}],
    }
    r = key_facts(co, hist(), {"stage": 2, "name": "Markup", "weeks": 5}, {"trend_template": {"passed_count": 8}},
                  [{"market_cap_b": 3900.0}, {"market_cap_b": 4400.0}])
    text = " ".join(r["facts"])
    assert "$5.18 trillion" in text and "largest of 3" in text
    assert "beat EPS estimates" in text and "2027-01-28" in text
    assert "49 analysts rate it Buy" in text and "Stage 2 (Markup)" in text
    assert r["headline"]["title"] == "Apple wins antitrust ruling"
    assert len(r["facts"]) <= 5


def test_key_facts_with_missing_data():
    r = key_facts({"symbol": "XYZ", "name": "XYZ"}, hist(), None, None, [])
    assert r["facts"] and r["headline"] is None


def test_daily_summary_item_and_email_text():
    rows = [
        {"symbol": "A", "name": "A", "price": 10, "change_pct": 5.0, "new_high": True, "new_low": False},
        {"symbol": "B", "name": "B", "price": 20, "change_pct": -3.0, "new_high": False, "new_low": False},
    ]
    indices = [{"symbol": "SPY", "label": "S&P 500", "price": 600.0, "change_pct": 0.8}, {"symbol": "^VIX", "label": "VIX", "price": 15.0, "change_pct": -2}]
    ideas = [{"symbol": "A", "timeframe": "SWING", "side": "long", "entry": 10, "stop": 9, "target": 13, "rr": 3.0}]
    item = daily_summary("2026-11-16", indices, [{"label": "S&P 500", "stage": 2, "name": "Markup"}], {"score": 62, "label": "Greed"},
                         rows, ideas, [{"symbol": "NVDA"}])
    assert item["key"] == "summary:2026-11-16" and item["kind"] == "summary"
    d = json.loads(item["body"])
    assert d["breadth"]["advancing"] == 1 and d["gainers"][0]["symbol"] == "A" and d["vix"] == 15.0
    text = summary_text(item, [{"symbol": "MSFT", "price": 500, "change_pct": 1.2}])
    assert "S&P 500 higher (+0.80%)" in text and "YOUR WATCHLISTS" in text and "MSFT" in text and "NVDA" in text
