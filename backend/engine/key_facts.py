"""Key facts: 3-5 short, plain-English sentences about a company, built only from data we already have
(company overview, price history, market cycle stage, SEPA report, peers) plus the most important recent headline.
No AI service and no extra API calls."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from .feed import CRITICAL


def _cap(b: float) -> str:
    return f"${b / 1000:.2f} trillion" if b >= 1000 else f"${b:.1f} billion" if b >= 1 else f"${b * 1000:.0f} million"


def _headline(news: list[dict], days: int = 7) -> dict | None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for n in news or []:
        title = n.get("title") or ""
        when = n.get("published") or n.get("date")
        try:
            ts = pd.Timestamp(when)
            ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
            if ts < cutoff:
                continue
        except Exception:
            pass
        if CRITICAL.search(title):
            return {"title": title, "url": n.get("url"), "publisher": n.get("publisher")}
    return None


def key_facts(co: dict, history: pd.DataFrame, stage: dict | None, sepa: dict | None, peers: list[dict]) -> dict:
    name = co.get("name") or co.get("symbol", "")
    short = name.replace(" Inc.", "").replace(", Inc.", "").replace(" Corporation", "").replace(" Corp.", "").strip() or name
    facts: list[str] = []

    cap = (co.get("stats") or {}).get("market_cap_b")
    if cap:
        caps = sorted([p["market_cap_b"] for p in peers if p.get("market_cap_b")] + [cap], reverse=True)
        rank = caps.index(cap) + 1
        where = f"the largest of {len(caps)} tracked {co.get('sector') or 'sector'} peers" if rank == 1 and len(caps) > 1 else (
            f"#{rank} of {len(caps)} tracked {co.get('sector') or 'sector'} peers" if len(caps) > 1 else "")
        facts.append(f"{short} is valued at {_cap(cap)}" + (f", {where}." if where else "."))

    if len(history) >= 30:
        c = history["close"]
        last = float(c.iloc[-1])
        hi = float(history["high"].iloc[-252:].max())
        off = (last / hi - 1) * 100
        r3m = (last / float(c.iloc[-64]) - 1) * 100 if len(c) > 64 else None
        if off >= -1:
            s = f"The stock is at a 52-week high ({hi:,.2f})"
        else:
            s = f"The stock trades {abs(off):.1f}% below its 52-week high of {hi:,.2f}"
        facts.append(s + (f" and is {'up' if r3m >= 0 else 'down'} {abs(r3m):.1f}% over 3 months." if r3m is not None else "."))

    hist = sorted((co.get("earnings") or {}).get("history") or [], key=lambda e: e.get("date") or "", reverse=True)
    last_e = next((e for e in hist if e.get("eps_actual") is not None and e.get("eps_estimate") is not None), None)
    nxt = (co.get("earnings") or {}).get("next_date")
    if last_e:
        est, act = last_e["eps_estimate"], last_e["eps_actual"]
        surprise = last_e.get("surprise_pct")
        if surprise is None and est:
            surprise = (act / est - 1) * 100 if est > 0 else None
        verb = "beat" if act >= est else "missed"
        s = f"Last quarter it {verb} EPS estimates (${act:.2f} vs ${est:.2f}" + (f", {surprise:+.1f}%" if surprise is not None else "") + ")"
        facts.append(s + (f"; next report {nxt}." if nxt else "."))
    elif nxt:
        facts.append(f"Next earnings report: {nxt}.")

    a = co.get("analysts") or {}
    if a.get("rating") and a.get("total"):
        s = f"{a['total']} analysts rate it {a['rating']}"
        if a.get("target_mean") and a.get("upside_pct") is not None:
            s += f", with an average 1-year target of ${a['target_mean']:,.2f} ({a['upside_pct']:+.1f}%)"
        facts.append(s + ".")

    tt = (sepa or {}).get("trend_template") or {}
    if stage:
        s = f"Market cycle: Stage {stage['stage']} ({stage['name']}) for {stage['weeks']} week{'s' if stage['weeks'] != 1 else ''}"
        if tt.get("passed_count") is not None:
            s += f"; {tt['passed_count']}/8 Trend Template criteria met"
        facts.append(s + ".")

    return {"facts": facts[:5], "headline": _headline(co.get("news") or [])}
