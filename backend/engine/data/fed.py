"""Federal Reserve rate monitor.

Live data comes from FRED (Federal Reserve Bank of St. Louis), which offers free CSV downloads without an API key:
  DFEDTARU / DFEDTARL  fed funds target range (upper / lower)
  EFFR                 effective fed funds rate
  DTB3                 3-month Treasury bill
  DGS2, DGS10          2- and 10-year Treasury yields

The market-implied outlook is an estimate from the 3-month T-bill vs. the effective rate. It is not CME FedWatch
(which uses fed funds futures); it is labeled as an estimate in the app.
"""

from __future__ import annotations

import io
from datetime import date

import httpx
import numpy as np
import pandas as pd

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}"

# Published FOMC meeting schedule (decision on the second day). Update when the Fed publishes the next year's dates.
FOMC_MEETINGS = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]


def fred_series(series: str, start: str = "2015-01-01", timeout: float = 15) -> pd.Series:
    r = httpx.get(FRED_CSV.format(series=series, start=start), timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().set_index(pd.to_datetime(df.dropna()["date"]))["value"]


def _decisions(upper: pd.Series, lower: pd.Series) -> list[dict]:
    u = upper.dropna()
    changes = u[u.diff().fillna(0) != 0]
    out = []
    for d, val in changes.items():
        prev = float(u[u.index < d].iloc[-1])
        lo = float(lower.reindex([d], method="ffill").iloc[0]) if len(lower) else val - 0.25
        bp = round((float(val) - prev) * 100)
        out.append({"date": d.strftime("%Y-%m-%d"), "upper": float(val), "lower": lo, "change_bp": bp,
                    "action": "Hike" if bp > 0 else "Cut"})
    return list(reversed(out))[:20]


def summarize(upper: pd.Series, lower: pd.Series, effr: pd.Series, tbill: pd.Series, y2: pd.Series, y10: pd.Series,
              today: date, demo: bool) -> dict:
    up, lo = float(upper.iloc[-1]), float(lower.iloc[-1])
    eff = float(effr.iloc[-1]) if len(effr) else (up + lo) / 2
    tb = float(tbill.iloc[-1]) if len(tbill) else None
    upcoming = [m for m in FOMC_MEETINGS if m >= today.isoformat()]
    implied_bp = round((tb - eff) * 100) if tb is not None else None
    outlook = None
    if implied_bp is not None:
        # Over ~3 months the bill rate averages the expected policy path; scale to the next meeting.
        p = float(np.clip(abs(implied_bp) / 25, 0, 1))
        direction = "cut" if implied_bp < -5 else "hike" if implied_bp > 5 else "hold"
        outlook = {
            "implied_change_bp": implied_bp,
            "direction": direction,
            "probabilities": {
                "cut": round(p * 100) if direction == "cut" else 0,
                "hike": round(p * 100) if direction == "hike" else 0,
                "hold": round((1 - p) * 100) if direction != "hold" else 100,
            },
            "method": "Estimate from the 3-month Treasury bill vs. the effective fed funds rate (not CME FedWatch).",
        }
    hist = lambda s: [{"time": d.strftime("%Y-%m-%d"), "value": round(float(v), 3)} for d, v in s[s.index >= pd.Timestamp(today) - pd.Timedelta(days=5 * 365)].resample("W").last().dropna().items()]
    return {
        "demo": demo,
        "as_of": upper.index[-1].strftime("%Y-%m-%d"),
        "target_range": {"lower": lo, "upper": up},
        "effective_rate": round(eff, 2),
        "treasury": {"bill_3m": tb, "note_2y": float(y2.iloc[-1]) if len(y2) else None, "note_10y": float(y10.iloc[-1]) if len(y10) else None},
        "curve_2s10s_bp": round((float(y10.iloc[-1]) - float(y2.iloc[-1])) * 100) if len(y2) and len(y10) else None,
        "next_meeting": upcoming[0] if upcoming else None,
        "meetings": [{"date": m, "past": m < today.isoformat()} for m in FOMC_MEETINGS],
        "outlook": outlook,
        "decisions": _decisions(upper, lower),
        "history": {"upper": hist(upper), "effective": hist(effr) if len(effr) else [], "note_2y": hist(y2) if len(y2) else []},
    }


def live(today: date | None = None) -> dict:
    today = today or date.today()
    get = lambda s: fred_series(s)
    upper, lower = get("DFEDTARU"), get("DFEDTARL")
    opt = {}
    for k, s in (("effr", "EFFR"), ("tbill", "DTB3"), ("y2", "DGS2"), ("y10", "DGS10")):
        try:
            opt[k] = get(s)
        except Exception:
            opt[k] = pd.Series(dtype=float)
    return summarize(upper, lower, opt["effr"], opt["tbill"], opt["y2"], opt["y10"], today, demo=False)


def demo(today: date | None = None) -> dict:
    """Deterministic demo rate path for offline development. Not real Fed data."""
    today = today or date.today()
    days = pd.date_range(end=pd.Timestamp(today), periods=6 * 365, freq="D")
    steps = [(0, 0.25), (500, 0.50), (560, 1.25), (620, 2.50), (700, 4.00), (780, 5.00), (850, 5.50),
             (1500, 5.00), (1560, 4.75), (1620, 4.50), (1900, 4.25), (1990, 4.00), (2050, 3.75)]
    upper = pd.Series(np.nan, index=days)
    for i, v in steps:
        if i < len(days):
            upper.iloc[i] = v
    upper = upper.ffill()
    lower = upper - 0.25
    effr = upper - 0.17
    tbill = effr.shift(-60).ffill() - 0.05
    y2 = effr.shift(-200).ffill() - 0.1
    y10 = y2 * 0.6 + 1.8
    return summarize(upper, lower, effr, tbill, y2, y10, today, demo=True)
