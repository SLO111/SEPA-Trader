"""Company scorecard: financial health (1-5) and fair value, from the company data the app already has."""

from __future__ import annotations

import statistics

LABELS = [(1.8, "Weak"), (2.5, "Fair"), (3.2, "Good"), (4.0, "Great"), (9, "Excellent")]


def _scale(v: float | None, lo: float, hi: float) -> float | None:
    """Map v linearly from [lo, hi] to [1, 5] (clipped). lo > hi means lower is better."""
    if v is None:
        return None
    x = (v - lo) / (hi - lo)
    return round(1 + 4 * max(0.0, min(1.0, x)), 2)


def _avg(xs: list[float | None]) -> float | None:
    v = [x for x in xs if x is not None]
    return round(sum(v) / len(v), 2) if v else None


def health(co: dict, sepa: dict | None = None, stage: int | None = None) -> dict:
    """Score 1-5 from five categories, like a credit-style scorecard."""
    p, h = co.get("profitability") or {}, co.get("health") or {}
    annual = (co.get("financials") or {}).get("annual") or []
    last = annual[0] if annual else {}
    fcf_margin = (last.get("free_cash_flow") / last["revenue"] * 100) if last.get("revenue") and last.get("free_cash_flow") is not None else None
    fcf_growth = None
    if len(annual) >= 2 and annual[1].get("free_cash_flow"):
        a, b = last.get("free_cash_flow"), annual[1]["free_cash_flow"]
        fcf_growth = (a / b - 1) * 100 if a is not None and b and b > 0 else None
    cats = {
        "Profitability": _avg([_scale(p.get("net_margin"), -5, 25), _scale(p.get("operating_margin"), 0, 35), _scale(p.get("roe"), 0, 30)]),
        "Growth": _avg([_scale(p.get("revenue_growth"), -5, 30), _scale(p.get("eps_growth"), -10, 40)]),
        "Cash flow": _avg([_scale(fcf_margin, -5, 25), _scale(fcf_growth, -20, 30)]),
        "Financial strength": _avg([_scale(h.get("debt_to_equity"), 2.5, 0.0), _scale(h.get("current_ratio"), 0.6, 2.0),
                                    _scale((h.get("cash_b") or 0) / h["debt_b"] if h.get("debt_b") else None, 0.1, 1.5)]),
        "Price momentum": None,
    }
    if sepa:
        tt = (sepa.get("trend_template") or {})
        rs = sepa.get("rs_rating")
        mom = [_scale(rs, 20, 95)]
        if tt.get("passed_count") is not None and (tt.get("total") or 8) == 8:
            mom.append(_scale(tt["passed_count"], 2, 8))
        if stage:
            mom.append({1: 2.5, 2: 4.5, 3: 2.0, 4: 1.0}.get(stage))
        cats["Price momentum"] = _avg(mom)
    score = _avg(list(cats.values()))
    label = next(lbl for lim, lbl in LABELS if (score or 0) < lim) if score is not None else None
    return {"score": score, "label": label, "categories": [{"name": k, "score": v} for k, v in cats.items()]}


def fair_value(co: dict, price: float, sector_pe: float | None = None) -> dict:
    """Median of the available models: 2-stage DCF on free cash flow, sector P/E, PEG-adjusted P/E, analyst target."""
    stats, val, p = co.get("stats") or {}, co.get("valuation") or {}, co.get("profitability") or {}
    annual = (co.get("financials") or {}).get("annual") or []
    shares = (stats.get("shares_outstanding_m") or 0) * 1e6
    eps = stats.get("eps_ttm")
    models = []

    fcfs = [a.get("free_cash_flow") for a in annual if a.get("free_cash_flow") is not None]
    if fcfs and fcfs[0] > 0 and shares:
        g_hist = (fcfs[0] / fcfs[-1]) ** (1 / max(len(fcfs) - 1, 1)) - 1 if len(fcfs) > 1 and fcfs[-1] > 0 else 0.05
        g = max(0.0, min(0.25, g_hist))
        r, tg = 0.10, 0.03
        cash, debt = (co.get("health") or {}).get("cash_b"), (co.get("health") or {}).get("debt_b")
        pv, f = 0.0, fcfs[0]
        for year in range(1, 11):
            growth = g if year <= 5 else g + (tg - g) * (year - 5) / 5
            f *= 1 + growth
            pv += f / (1 + r) ** year
        terminal = f * (1 + tg) / (r - tg) / (1 + r) ** 10
        equity = pv + terminal + ((cash or 0) - (debt or 0)) * 1e9
        models.append({"name": "DCF (free cash flow)", "value": round(equity / shares, 2)})
    if eps and eps > 0 and sector_pe:
        models.append({"name": "Sector P/E", "value": round(eps * sector_pe, 2)})
    g = p.get("eps_growth")
    if eps and eps > 0 and g and g > 0:
        fair_pe = max(8.0, min(g, 40.0))  # PEG = 1: a P/E equal to the growth rate
        models.append({"name": "Growth-adjusted P/E (PEG 1)", "value": round(eps * fair_pe, 2)})
    tgt = (co.get("analysts") or {}).get("target_mean")
    if tgt:
        models.append({"name": "Analyst target", "value": round(float(tgt), 2)})
    models = [m for m in models if m["value"] and m["value"] > 0]
    if not models or not price:
        return {"fair": None, "upside_pct": None, "label": None, "models": []}
    fair = round(statistics.median(m["value"] for m in models), 2)
    up = round((fair / price - 1) * 100, 1)
    label = "Undervalued" if up > 15 else "Overvalued" if up < -15 else "Fairly valued"
    _ = val
    return {"fair": fair, "upside_pct": up, "label": label, "models": models}
