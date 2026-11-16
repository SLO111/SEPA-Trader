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


def daily_summary(day: str, indices: list[dict], cycle: list[dict], fear_greed: dict, rows: list[dict],
                  ideas: list[dict], earnings_next: list[dict], scan: list[dict] | None = None, pulse: dict[str, dict] | None = None) -> dict:
    """One end-of-day recap (feed item of kind "summary"); `body` holds the sections as JSON."""
    import json

    adv = sum(r["change_pct"] > 0 for r in rows)
    dec = sum(r["change_pct"] < 0 for r in rows)
    gainers = sorted([r for r in rows if r["change_pct"] > 0], key=lambda r: -r["change_pct"])[:3]
    losers = sorted([r for r in rows if r["change_pct"] < 0], key=lambda r: r["change_pct"])[:3]
    spy = next((i for i in indices if i["symbol"] == "SPY"), None)
    pick = lambda r: {"symbol": r["symbol"], "name": r.get("name", ""), "price": r["price"], "change_pct": r["change_pct"]}
    data = {
        "indices": [{k: i[k] for k in ("symbol", "label", "price", "change_pct")} for i in indices if i["symbol"] != "^VIX"][:4],
        "vix": next((i["price"] for i in indices if i["symbol"] == "^VIX"), None),
        "cycle": [{k: c[k] for k in ("label", "stage", "name")} for c in cycle],
        "fear_greed": {"score": fear_greed.get("score"), "label": fear_greed.get("label")},
        "breadth": {"advancing": adv, "declining": dec, "new_highs": sum(r["new_high"] for r in rows), "new_lows": sum(r["new_low"] for r in rows)},
        "gainers": [pick(r) for r in gainers],
        "losers": [pick(r) for r in losers],
        "ideas": {"count": len(ideas), "top": [{k: i[k] for k in ("symbol", "timeframe", "side", "entry", "stop", "target", "rr")} for i in ideas[:5]]},
        "earnings_next": earnings_next[:10],
        "move_detector": _md_section(scan or []),
        "pulse": _pulse_section(pulse or {}),
    }
    tone = "higher" if spy and spy["change_pct"] > 0 else "lower" if spy and spy["change_pct"] < 0 else "flat"
    title = f"Daily summary {day}: S&P 500 {tone}" + (f" ({spy['change_pct']:+.2f}%)" if spy else "") + f", {adv} up / {dec} down"
    return {"key": f"summary:{day}", "kind": "summary", "symbol": None, "severity": "info", "title": title, "body": json.dumps(data), "url": None}


def _md_section(scan: list[dict], n: int = 5) -> dict:
    """Top Bull and Bear scores from the Move Detector scan."""
    row = lambda r, k: {"symbol": r["symbol"], "score": r.get(k), "price": r.get("price"), "change_pct": r.get("change_pct")}
    bull = sorted([r for r in scan if (r.get("bull_score") or 0) >= 60], key=lambda r: -(r.get("bull_score") or 0))[:n]
    bear = sorted([r for r in scan if (r.get("bear_score") or 0) >= 60], key=lambda r: -(r.get("bear_score") or 0))[:n]
    return {"bull": [row(r, "bull_score") for r in bull], "bear": [row(r, "bear_score") for r in bear]}


def _pulse_section(pulse: dict[str, dict], n: int = 5) -> dict:
    """vnicorn Pulse: stocks acting best (confirmations) and those flashing warnings over the last 10 days."""
    items = [{"symbol": s, "conf": p.get("conf", 0), "warn": p.get("warn", 0)} for s, p in pulse.items()]
    best = sorted([x for x in items if x["conf"] > x["warn"]], key=lambda x: (-(x["conf"] - x["warn"]), -x["conf"]))[:n]
    warn = sorted([x for x in items if x["warn"] > x["conf"]], key=lambda x: (-(x["warn"] - x["conf"]), -x["warn"]))[:n]
    return {"best": best, "warning": warn}


def gate_summary(d: dict, limits: dict) -> dict:
    """Free plan: Trade ideas, Move Detector and vnicorn Pulse sections are replaced by a lock."""
    out = dict(d)
    if not limits.get("move_detector"):
        out["ideas"] = {"locked": True, "count": (d.get("ideas") or {}).get("count")}
        out["move_detector"] = {"locked": True}
    if not limits.get("pulse"):
        out["pulse"] = {"locked": True}
    return out


def summary_text(item: dict, watch: list[dict] | None = None, limits: dict | None = None) -> str:
    """Plain-text email version of a daily summary, optionally with the reader's watchlist moves."""
    import json

    d = json.loads(item["body"])
    if limits is not None:
        d = gate_summary(d, limits)
    pct = lambda x: f"{x:+.2f}%"
    lines = [item["title"], ""]
    lines += ["MARKETS"] + [f"  {i['label']}: {i['price']:,.2f} ({pct(i['change_pct'])})" for i in d["indices"]]
    if d.get("vix") is not None:
        lines.append(f"  VIX: {d['vix']:.2f}")
    if d["fear_greed"].get("score") is not None:
        lines.append(f"  Fear & Greed: {round(d['fear_greed']['score'])} ({d['fear_greed']['label']})")
    if d["cycle"]:
        lines.append("  Cycle: " + ", ".join(f"{c['label']} Stage {c['stage']} {c['name']}" for c in d["cycle"]))
    b = d["breadth"]
    lines += [f"  Breadth: {b['advancing']} up / {b['declining']} down, {b['new_highs']} new highs, {b['new_lows']} new lows", ""]
    if watch:
        lines += ["YOUR WATCHLISTS"] + [f"  {w['symbol']}: {w['price']:,.2f} ({pct(w['change_pct'])})" for w in watch] + [""]
    lines += ["TOP GAINERS"] + [f"  {r['symbol']} {pct(r['change_pct'])}" for r in d["gainers"]]
    lines += ["TOP LOSERS"] + [f"  {r['symbol']} {pct(r['change_pct'])}" for r in d["losers"]] + [""]
    locked = []
    if d["ideas"].get("locked"):
        locked.append("Trade ideas")
    else:
        lines.append(f"NEW TRADE IDEAS: {d['ideas']['count']}")
        lines += [f"  {i['timeframe']} {i['symbol']}: {'short' if i['side'] == 'short' else 'buy'} {i['entry']}, stop {i['stop']}, target {i['target']} (R/R {i['rr']})"
                  for i in d["ideas"]["top"]]
    md = d.get("move_detector") or {}
    if md.get("locked"):
        locked.append("Move Detector")
    elif md.get("bull") or md.get("bear"):
        lines += ["", "MOVE DETECTOR"]
        lines += ["  Bull: " + ", ".join(f"{r['symbol']} {r['score']:.0f}" for r in md.get("bull", []))] if md.get("bull") else []
        lines += ["  Bear: " + ", ".join(f"{r['symbol']} {r['score']:.0f}" for r in md.get("bear", []))] if md.get("bear") else []
    pu = d.get("pulse") or {}
    if pu.get("locked"):
        locked.append("vnicorn Pulse")
    elif pu.get("best") or pu.get("warning"):
        lines += ["", "VNICORN PULSE (10 DAYS)"]
        lines += ["  Acting best: " + ", ".join(f"{x['symbol']} +{x['conf']}/-{x['warn']}" for x in pu.get("best", []))] if pu.get("best") else []
        lines += ["  Warnings: " + ", ".join(f"{x['symbol']} +{x['conf']}/-{x['warn']}" for x in pu.get("warning", []))] if pu.get("warning") else []
    if locked:
        lines += ["", f"Upgrade to Pro to see {', '.join(locked)} in your daily summary."]
    if d["earnings_next"]:
        lines += ["", "EARNINGS NEXT TRADING DAY: " + ", ".join(e["symbol"] for e in d["earnings_next"])]
    lines += ["", "For educational purposes only. Not financial advice.", "Turn this email off in the app: Alerts > Feed."]
    return "\n".join(lines)
