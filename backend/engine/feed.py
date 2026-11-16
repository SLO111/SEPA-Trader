"""Market feed (TrendSpider-style notifications): earnings beats and misses, upcoming reports, big movers,
breakouts and breakdowns, new 52-week highs, new trade ideas and critical news headlines.

Every builder returns plain dicts with a stable `key`, so the same event is stored only once.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import pandas as pd

from .triggers import evaluate

CRITICAL = re.compile(
    r"\b(FDA|SEC|DOJ|antitrust|lawsuit|sued|investigation|probe|recall|bankrupt\w*|chapter 11|delist\w*|halt\w*|"
    r"acquir\w*|acquisition|merger|buyout|takeover|spin-?off|guidance|outlook|warns?|layoffs?|job cuts|"
    r"CEO|CFO|resign\w*|steps down|upgrade\w*|downgrade\w*|beats?|miss(es|ed)?|record|tariffs?|"
    r"Fed|FOMC|rate (cut|hike)s?|CPI|inflation|jobs report|payrolls|recession|default|stock split|buyback)\b",
    re.IGNORECASE,
)


def _money(x) -> str:
    return "—" if x is None else f"${x:,.2f}"


def earnings_items(entries: dict[str, dict], histories: dict[str, pd.DataFrame], today: date) -> list[dict]:
    out = []
    for sym, e in entries.items():
        hist = e.get("history") or []
        if hist:
            last = hist[0]
            d = pd.Timestamp(last["date"]).date() if last.get("date") else None
            est, act = last.get("eps_estimate"), last.get("eps_actual")
            if d and today - timedelta(days=4) <= d <= today and act is not None and est is not None:
                beat = act >= est
                surprise = last.get("surprise_pct")
                reaction = ""
                c = histories.get(sym, pd.DataFrame()).get("close")
                if c is not None and len(c):
                    before, after = c[c.index < pd.Timestamp(d)], c[c.index >= pd.Timestamp(d)]
                    if len(before) and len(after):
                        reaction = f" Stock {((float(after.iloc[-1]) / float(before.iloc[-1])) - 1) * 100:+.1f}% since the report."
                out.append({
                    "key": f"earn:{sym}:{d}", "kind": "earnings", "symbol": sym, "severity": "bull" if beat else "bear",
                    "title": f"${sym} {'beats' if beat else 'misses'} EPS estimates" + (f" by {abs(surprise):.1f}%" if surprise is not None else ""),
                    "body": f"Reported EPS {_money(act)} vs. {_money(est)} expected.{reaction}",
                })
        nd = e.get("next_date")
        if nd:
            d = pd.Timestamp(nd).date()
            if d in (today, today + timedelta(days=1)):
                when = "today" if d == today else "tomorrow"
                est = e.get("next_eps_estimate")
                out.append({
                    "key": f"earn-soon:{sym}:{d}", "kind": "earnings", "symbol": sym, "severity": "info",
                    "title": f"${sym} reports earnings {when}",
                    "body": f"EPS estimate {_money(est)}." if est is not None else "Watch for volatility around the report.",
                })
    return out


def mover_items(rows: list[dict], scan: dict[str, dict], day: str) -> list[dict]:
    out = []
    for r in rows:
        chg, rvol, sym = r["change_pct"], r.get("rel_volume") or 0, r["symbol"]
        if abs(chg) >= 5 or (abs(chg) >= 3 and rvol >= 3):
            up = chg > 0
            out.append({
                "key": f"move:{sym}:{day}", "kind": "mover", "symbol": sym, "severity": "bull" if up else "bear",
                "title": f"${sym} {'surges' if up else 'drops'} {abs(chg):.1f}%" + (f" on {rvol:.1f}× volume" if rvol >= 1.5 else ""),
                "body": f"{r['name']} closed at {_money(r['price'])}.",
            })
        rs = (scan.get(sym) or {}).get("rs_rating") or 0
        if r.get("new_high") and rs >= 80:
            out.append({
                "key": f"high:{sym}:{day}", "kind": "high", "symbol": sym, "severity": "bull",
                "title": f"${sym} hits a new 52-week high",
                "body": f"RS Rating {rs}: one of the market's leaders. Closed at {_money(r['price'])}.",
            })
    return out


BREAKOUT_EVENTS = ["breakout", "gap_up", "gap_down", "ma50_break", "failed_breakout"]


def breakout_items(histories: dict[str, pd.DataFrame], bench: pd.DataFrame | None) -> list[dict]:
    out = []
    for sym, df in histories.items():
        try:
            events = evaluate(df, bench, BREAKOUT_EVENTS)
        except Exception:
            continue
        for e in events:
            out.append({"key": f"trig:{sym}:{e.type}:{e.bar_date}", "kind": "breakout", "symbol": sym, "severity": e.severity,
                        "title": f"${sym}: {e.title}", "body": e.message})
    return out


def news_items(news: list[dict]) -> list[dict]:
    """Keep only market-moving headlines (FDA, M&A, guidance, rating changes, the Fed...)."""
    out = []
    for n in news:
        title = (n.get("headline") or n.get("title") or "").strip()
        if not title or not CRITICAL.search(title):
            continue
        related = [s for s in (n.get("related") or "").split(",") if s and s.isupper() and len(s) <= 6]
        sym = related[0] if related else None
        nid = n.get("id") or abs(hash(title))
        out.append({"key": f"news:{nid}", "kind": "news", "symbol": sym, "severity": "info", "title": title,
                    "body": (n.get("summary") or "")[:400], "url": n.get("url")})
    return out


def idea_items(ideas: list[dict], day: str) -> list[dict]:
    out = []
    for i in ideas:
        verb = "short" if i["side"] == "short" else "buy"
        out.append({
            "key": f"idea:{i['symbol']}:{i['timeframe']}:{day}", "kind": "idea", "symbol": i["symbol"],
            "severity": "bear" if i["side"] == "short" else "bull",
            "title": f"New {i['timeframe']} idea: {verb} ${i['symbol']} near {_money(i['entry'])}",
            "body": f"Stop {_money(i['stop'])} · target {_money(i['target'])} · R/R {i['rr']}. {i['reason']}",
        })
    return out
