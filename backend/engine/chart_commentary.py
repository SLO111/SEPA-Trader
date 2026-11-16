"""Ask vnicornAI: a plain-English read of a chart, written from the platform's own analysis (no external AI).

Covers trend and market cycle, the Structure Count, the setup (VCP / pivot / Trend Template), volume
behaviour (Pulse), the nearest support and resistance, risk, and vnicornAI's plan when the model exists.
"""

from __future__ import annotations

import pandas as pd

from . import pulse, stages, structure
from .indicators import atr, sma
from .sepa import template_frame
from .vcp import detect_vcp


def analyze(df: pd.DataFrame, bench: pd.DataFrame | None = None, ai_plan: dict | None = None, symbol: str = "") -> dict:
    c = df["close"]
    price = float(c.iloc[-1])
    a = float(atr(df, 14).iloc[-1])
    sections: list[dict] = []
    bias = 0

    st = stages.stage_now(df)
    s50, s200 = float(sma(c, 50).iloc[-1]), float(sma(c, 200).iloc[-1]) if len(c) >= 200 else float("nan")
    r3 = (price / float(c.iloc[-64]) - 1) * 100 if len(c) > 64 else None
    if st:
        msg = {1: "is basing after a decline (Stage 1). Not a buy yet; watch for a breakout above the base.",
               2: "is in an uptrend (Stage 2), the stage where the big gains happen.",
               3: "is topping (Stage 3): momentum is fading. Protect profits, avoid new buys.",
               4: "is in a downtrend (Stage 4). Avoid longs; rallies tend to fail."}[st["stage"]]
        bias += {1: 0, 2: 2, 3: -1, 4: -2}[st["stage"]]
        sections.append({"title": "Trend & cycle", "text": f"{symbol or 'The stock'} {msg} It has been in this stage for {st['weeks']} weeks; "
                         f"price is {abs(price / s50 - 1) * 100:.1f}% {'above' if price >= s50 else 'below'} the 50-day average"
                         + (f" and {abs(price / s200 - 1) * 100:.1f}% {'above' if price >= s200 else 'below'} the 200-day." if s200 == s200 else ".")
                         + (f" 3-month change: {r3:+.1f}%." if r3 is not None else "")})

    lab = structure.label(structure.analyze(df.iloc[-300:]).state)
    if lab["side"]:
        if lab["step"] == 4:
            bias += 1 if lab["side"] == "bull" else -1
            sections.append({"title": "Structure", "text": f"{lab['text']}: {'buyers' if lab['side'] == 'bull' else 'sellers'} are in control. "
                             f"The defence level is {lab['defence']:.2f}; a close beyond it would end this phase."})
        else:
            sections.append({"title": "Structure", "text": f"A {lab['side']} count is in progress ({lab['text']}). Not confirmed yet."})

    tt = template_frame(df).iloc[-1]
    passed = int(tt.sum()) if tt.notna().all() else None
    v = detect_vcp(df)
    setup = []
    if passed is not None:
        setup.append(f"It meets {passed} of 7 Trend Template price criteria.")
        bias += 1 if passed >= 6 else -1 if passed <= 2 else 0
    if v.get("detected"):
        setup.append(f"A volatility contraction (VCP) is forming with a pivot at {v['pivot']:.2f} ({(v['pivot'] / price - 1) * 100:+.1f}% away) "
                     f"and a logical stop near {v['stop']:.2f}. A close above the pivot on strong volume would be the buy signal.")
    elif v.get("pivot"):
        setup.append(f"The nearest pivot is {v['pivot']:.2f} ({(v['pivot'] / price - 1) * 100:+.1f}%), but the base isn't tight enough for a VCP yet.")
    if setup:
        sections.append({"title": "Setup", "text": " ".join(setup)})

    p = pulse.summary(df, bench)
    today = p["today"]
    txt = f"Over the last {p['days']} days: {p['conf']} confirmations vs {p['warn']} warnings ({p['tone']})."
    if today["conf"] or today["warn"]:
        txt += " Today: " + ", ".join(today["conf"] + today["warn"]) + "."
    bias += 1 if p["tone"] == "constructive" else -1 if p["tone"] == "warning" else 0
    sections.append({"title": "Behaviour & volume", "text": txt})

    from .ideas import levels

    try:
        lv = levels(df)
        sup = max([x for x in lv["support"] if x < price], default=None)
        res = min([x for x in lv["resistance"] if x > price], default=None)
    except Exception:
        sup = res = None
    lvl = []
    if sup:
        lvl.append(f"support at {sup:.2f} ({(sup / price - 1) * 100:.1f}%)")
    if res:
        lvl.append(f"resistance at {res:.2f} ({(res / price - 1) * 100:+.1f}%)")
    risk = f"Daily volatility (ATR) is {a:.2f}, about {a / price * 100:.1f}% of the price."
    sections.append({"title": "Levels & risk", "text": ("Nearest " + " and ".join(lvl) + ". " if lvl else "") + risk})

    if ai_plan:
        side = "long" if ai_plan["side"] == "long" else "short"
        sections.append({"title": "vnicornAI plan", "text": f"Best {side} plan: entry {ai_plan['entry']}, stop {ai_plan['stop']}, trim {ai_plan['trim']}, "
                         f"target {ai_plan['target']} (R/R {ai_plan['rr']}). Estimated chance to reach the target first: {ai_plan['prob'] * 100:.0f}% "
                         f"(expected value {ai_plan['ev']:+.2f}R)" + (", a vnicornAI pick." if ai_plan.get("pick") else ".")})

    verdict = "Constructive" if bias >= 3 else "Leaning positive" if bias >= 1 else "Weak" if bias <= -3 else "Leaning negative" if bias <= -1 else "Neutral"
    return {"symbol": symbol, "verdict": verdict, "bias": bias, "sections": sections, "pulse": p,
            "as_of": df.index[-1].strftime("%Y-%m-%d")}
