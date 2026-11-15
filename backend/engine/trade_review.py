"""Trade Review: grades a closed trade A–F and explains what went right and wrong.

The review replays the market as it was on the entry date (no hindsight for entry checks):
trend, relative setup, entry vs. pivot, planned risk, stop discipline and exit quality.
"""

from __future__ import annotations

import pandas as pd

from . import move_detector as md
from .indicators import sma
from .journal import Trade, trade_metrics
from .sepa import template_frame
from .vcp import detect_vcp

GRADES = [(85, "A"), (70, "B"), (55, "C"), (40, "D"), (0, "F")]


def _grade(score: float) -> str:
    return next(g for cut, g in GRADES if score >= cut)


def review(t: Trade, df: pd.DataFrame, bench: pd.DataFrame | None = None) -> dict:
    if not t.closed:
        return {"grade": None, "score": None, "checks": [], "summary": "Close the trade to get a review."}
    entry_ts, exit_ts = pd.Timestamp(t.entry_date), pd.Timestamp(t.exit_date)
    before = df[df.index < entry_ts]
    during = df[(df.index >= entry_ts) & (df.index <= exit_ts)]
    after = df[df.index > exit_ts]
    if len(before) < 220 or during.empty:
        return {"grade": None, "score": None, "checks": [], "summary": "Not enough price history around this trade to review it."}

    # Sanity check: the recorded prices must be close to where the stock actually traded on those days.
    for label, day, price in (("entry", entry_ts, t.entry_price), ("exit", exit_ts, t.exit_price)):
        bar = df[df.index >= day].iloc[:1]
        if bar.empty:
            continue
        lo, hi = float(bar["low"].iloc[0]), float(bar["high"].iloc[0])
        if not (lo * 0.97 <= price <= hi * 1.03):
            return {"grade": None, "score": None, "checks": [], "strengths": [], "mistakes": [], "notes": [],
                    "summary": f"The {label} price ({price:,.2f}) is far from where {t.symbol} traded on {bar.index[0].date()} "
                               f"({lo:,.2f}–{hi:,.2f}). Check the date and price so the review can be accurate."}

    long = t.side == "long"
    m = trade_metrics(t)
    checks: list[dict] = []
    points = 0.0
    total = 0.0

    def check(category: str, weight: float, status: str, text: str):
        nonlocal points, total
        total += weight
        points += weight * {"pass": 1.0, "warn": 0.5, "fail": 0.0}[status]
        checks.append({"category": category, "status": status, "text": text, "weight": weight})

    # ---- Setup quality (as of the day before entry)
    tt = int(template_frame(before).iloc[-1].sum())
    if long:
        check("Setup", 15, "pass" if tt >= 6 else "warn" if tt >= 4 else "fail",
              f"Trend Template at entry: {tt}/7 price criteria met." + ("" if tt >= 6 else " Buying stocks outside a strong uptrend lowers the odds."))
        bull = md.score_series(before.iloc[-300:], bench.loc[: before.index[-1]] if bench is not None else None)["bull"].iloc[-1]
        if pd.notna(bull):
            check("Setup", 10, "pass" if bull >= 60 else "warn" if bull >= 45 else "fail", f"Move Detector Bull Score at entry: {bull:.0f}/100.")
    if bench is not None:
        b = bench["close"][bench.index < entry_ts]
        if len(b) > 50:
            up = float(b.iloc[-1]) > float(sma(b, 50).iloc[-1])
            ok = up if long else not up
            check("Setup", 5, "pass" if ok else "warn", f"Market (S&P 500) was {'above' if up else 'below'} its 50-day average at entry.")

    # ---- Entry quality
    if long:
        v = detect_vcp(before)
        pivot = v.get("pivot")
        if pivot:
            ext = (t.entry_price / pivot - 1) * 100
            if 0 <= ext <= 5:
                check("Entry", 15, "pass", f"Bought {ext:.1f}% above the pivot ({pivot:.2f}): a proper breakout entry.")
            elif ext > 5:
                check("Entry", 15, "fail" if ext > 10 else "warn", f"Bought {ext:.1f}% above the pivot ({pivot:.2f}): the entry was extended (chasing).")
            else:
                check("Entry", 15, "warn", f"Bought {abs(ext):.1f}% below the pivot ({pivot:.2f}), before a breakout was confirmed.")
        if not pivot:
            # No active base: compare with the top of the base before the latest run-up (10-60 bars back).
            base_high = float(before["high"].iloc[-60:-10].max())
            ext = (t.entry_price / base_high - 1) * 100
            status = "pass" if -3 <= ext <= 5 else "fail" if ext > 10 else "warn"
            text = f"Entry was {ext:+.1f}% from the recent base high ({base_high:.2f})"
            text += ": the entry was extended (chasing)." if ext > 10 else "."
            check("Entry", 15, status, text)

    # ---- Risk plan
    if t.stop_price:
        r = m["risk_pct"]
        check("Risk", 15, "pass" if r <= 8 else "warn" if r <= 10 else "fail", f"Planned risk {r:.1f}% from entry to stop." + (" Keep it at 8% or less." if r > 8 else ""))
    else:
        check("Risk", 15, "fail", "No stop-loss recorded. Define your exit before you enter.")

    # ---- Stop discipline
    if t.stop_price:
        breached = during[(during["low"] <= t.stop_price)] if long else during[(during["high"] >= t.stop_price)]
        exit_vs_stop = (t.exit_price / t.stop_price - 1) * 100 * (1 if long else -1)
        if len(breached) and breached.index[0] < exit_ts and exit_vs_stop < -1:
            check("Discipline", 20, "fail", f"Price hit your stop on {breached.index[0].date()} but you held on and exited {abs(exit_vs_stop):.1f}% beyond it.")
        elif exit_vs_stop < -3:
            check("Discipline", 20, "warn", f"Exited {abs(exit_vs_stop):.1f}% beyond the stop (slippage or a gap).")
        else:
            check("Discipline", 20, "pass", "The stop was respected: the loss stayed within plan." if m["pnl"] <= 0 else "Stop never threatened or respected.")
    else:
        check("Discipline", 20, "fail" if m["pnl"] <= 0 else "warn", "Without a stop there was no exit plan to follow.")

    # ---- Exit quality
    if m["pnl"] > 0:
        best = float(during["high"].max()) if long else float(during["low"].min())
        max_gain = (best / t.entry_price - 1) * (1 if long else -1)
        got = (t.exit_price / t.entry_price - 1) * (1 if long else -1)
        kept = got / max_gain if max_gain > 0 else 1
        check("Exit", 20, "pass" if kept >= 0.6 else "warn" if kept >= 0.35 else "fail",
              f"Kept {kept * 100:.0f}% of the maximum open gain ({max_gain * 100:.1f}%)." + (" You gave back most of the move." if kept < 0.35 else ""))
    else:
        if m["r_multiple"] is not None:
            r = m["r_multiple"]
            check("Exit", 20, "pass" if r >= -1.1 else "warn" if r >= -1.5 else "fail", f"Loss of {abs(r):.2f}R." + (" Losses bigger than 1R hurt expectancy." if r < -1.1 else " Small, controlled loss."))
        else:
            check("Exit", 20, "warn" if m["return_pct"] > -8 else "fail", f"Loss of {abs(m['return_pct']):.1f}%.")

    # ---- Hindsight notes (informational, not graded)
    notes = []
    if len(after) >= 5:
        nxt = after.iloc[:20]
        move = (float(nxt["high"].max()) / t.exit_price - 1) * 100 if long else (1 - float(nxt["low"].min()) / t.exit_price) * 100
        if m["pnl"] > 0 and move >= 20:
            notes.append(f"After you sold, the stock moved another {move:.0f}% within 20 trading days. Consider holding a partial position to let winners run.")
        if m["pnl"] <= 0 and long and float(nxt["low"].min()) < t.exit_price * 0.9:
            notes.append("After your exit the stock fell more than 10% further: cutting the loss saved you money.")

    score = round(points / total * 100) if total else None
    strengths = [c["text"] for c in checks if c["status"] == "pass"]
    mistakes = [c["text"] for c in checks if c["status"] == "fail"]
    grade = _grade(score) if score is not None else None
    summary = {
        "A": "Textbook trade: good setup, disciplined risk and a solid exit.",
        "B": "Good trade with minor issues.",
        "C": "Average execution. Review the warnings below.",
        "D": "Several rules were broken.",
        "F": "Poor execution. Focus on the mistakes below.",
    }.get(grade, "")
    return {"grade": grade, "score": score, "summary": summary, "checks": checks, "strengths": strengths, "mistakes": mistakes, "notes": notes}
