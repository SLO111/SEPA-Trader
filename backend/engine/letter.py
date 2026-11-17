"""Weekly market letter: a rule-written recap of the week (Premium), built from data already in the app."""

from __future__ import annotations

import json


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:+.1f}%"


def weekly_letter(week: str, indices: list[dict], exposure: dict | None, groups: list[dict], leaders: list[dict],
                  warnings: list[dict], earnings: list[dict], record: dict) -> dict:
    """indices: [{label, week_pct}], groups ranked, leaders: [{symbol, rs, bull}], warnings: [{symbol, warn}],
    earnings: [{symbol, date}], record: {"closed", "win_rate", "total_r"} for the week's closed ideas."""
    spy = next((i for i in indices if i.get("symbol") == "SPY"), None)
    tone = "a strong week" if spy and spy["week_pct"] >= 1.5 else "a weak week" if spy and spy["week_pct"] <= -1.5 else "a quiet week"
    paras = []
    paras.append(f"It was {tone} for stocks: " + ", ".join(f"{i['label']} {_pct(i['week_pct'])}" for i in indices) + ".")
    if exposure:
        paras.append(f"Our market exposure meter reads {exposure['label']} ({exposure.get('exposure', '?')}% invested). {exposure['advice']}"
                     + (f" Distribution days: {exposure.get('distribution_days')} in the last 25 sessions." if exposure.get("distribution_days") is not None else ""))
    if groups:
        top = ", ".join(f"{g['group']} (RS {g['avg_rs']})" for g in groups[:5])
        bottom = ", ".join(g["group"] for g in groups[-3:])
        paras.append(f"Leading groups: {top}. Lagging: {bottom}. Leaders tend to come from the top groups.")
    if leaders:
        paras.append("Stocks acting like leaders (RS 90+, full Trend Template): " + ", ".join(f"{x['symbol']} (RS {x['rs']})" for x in leaders[:8]) + ".")
    if warnings:
        paras.append("Flashing warnings in vnicorn Pulse: " + ", ".join(f"{w['symbol']} ({w['warn']} warnings)" for w in warnings[:6])
                     + ". If you hold them, check your stops.")
    if earnings:
        paras.append("Earnings next week: " + ", ".join(f"{e['symbol']} ({e['date'][5:]})" for e in earnings[:15])
                     + ". Reports can gap a stock past its stop: many traders reduce size before them.")
    if record.get("closed"):
        paras.append(f"Trade ideas closed this week: {record['closed']}, win rate {record['win_rate']}%, total {record['total_r']:+.1f}R.")
    title = f"Weekly letter {week}: {tone}" + (f", S&P 500 {_pct(spy['week_pct'])}" if spy else "")
    body = {"week": week, "paragraphs": paras, "indices": indices, "exposure": exposure, "groups_top": groups[:5], "groups_bottom": groups[-3:],
            "leaders": leaders[:8], "warnings": warnings[:6], "earnings": earnings[:15], "record": record}
    return {"key": f"letter:{week}", "kind": "letter", "symbol": None, "severity": "info", "title": title, "body": json.dumps(body), "url": None}


def letter_text(item: dict) -> str:
    d = json.loads(item["body"])
    return item["title"] + "\n\n" + "\n\n".join(d["paragraphs"]) + "\n\nTurn this email off in Settings > Notifications."
