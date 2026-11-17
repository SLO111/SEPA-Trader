"""vnicornAI portfolio insights: risk checks on each position, and stocks to consider (Pro)."""

from __future__ import annotations


def checks(positions: list[dict], stops: dict[str, float], targets: dict[str, dict], scan: dict[str, dict], pulse: dict[str, dict],
           earnings_in: dict[str, int | None], extension: dict[str, float | None], stages: dict[str, int | None]) -> list[dict]:
    """positions: [{symbol, price, avg_cost, shares, value, weight, sector, pnl_pct}]. Returns suggestions, most important first."""
    out: list[dict] = []

    def add(level: str, symbol: str | None, title: str, detail: str, action: str | None = None):
        out.append({"level": level, "symbol": symbol, "title": title, "detail": detail, "action": action})

    total = sum(p["value"] for p in positions) or 1
    sectors: dict[str, float] = {}
    for p in positions:
        sectors[p.get("sector") or "Other"] = sectors.get(p.get("sector") or "Other", 0) + p["value"]
        sym, price, cost = p["symbol"], p["price"], p["avg_cost"]
        stop, tg = stops.get(sym), targets.get(sym) or {}
        sc = scan.get(sym, {})
        if stop is None:
            add("high", sym, f"No stop on {sym}", "Without a stop the risk on this position is open-ended. A common choice: under the last swing low, or 7-8% below your cost.", "stop")
        elif price > cost and stop < cost and (price - cost) >= 2 * (cost - stop) > 0:
            add("medium", sym, f"{sym} is up 2R+: raise the stop", f"Up {((price / cost) - 1) * 100:.1f}% from your cost. Moving the stop to break-even ({cost:.2f}) turns it into a risk-free trade.", "stop")
        if not tg.get("target") and not tg.get("trim"):
            add("low", sym, f"No trim or target on {sym}", "Decide in advance where you take profits: e.g. sell part at 2R and let the rest run.", "target")
        elif tg.get("trim") and price >= tg["trim"]:
            add("medium", sym, f"{sym} reached your trim ({tg['trim']:.2f})", "Consider selling part of the position as planned.", "sell")
        if tg.get("target") and price >= tg["target"]:
            add("medium", sym, f"{sym} reached your target ({tg['target']:.2f})", "Take profits or raise the target and the stop.", "sell")
        w = p.get("weight") or p["value"] / total * 100
        if w > 25:
            add("medium", sym, f"{sym} is {w:.0f}% of the portfolio", "A single position above 20-25% makes the portfolio depend on one stock. Consider trimming.", None)
        ext = extension.get(sym)
        if ext is not None and ext > 25:
            add("low", sym, f"{sym} is extended: {ext:.0f}% above its 50-day average", "Stocks this stretched often pull back. Selling part into strength locks in gains.", "sell")
        st = stages.get(sym)
        if st in (3, 4):
            add("high" if st == 4 else "medium", sym, f"{sym} is in Stage {st} ({'markdown' if st == 4 else 'distribution'})",
                "The long-term trend has turned. Leaders are owned in Stage 2; tighten the stop or reduce.", "stop")
        elif ext is not None and ext < 0 and (sc.get("bear_score") or 0) >= 60:
            add("medium", sym, f"{sym} broke below its 50-day average with a high Bear score", f"Bear score {sc.get('bear_score'):.0f}: the risk of a bigger drop is rising.", "stop")
        e = earnings_in.get(sym)
        if e is not None:
            add("medium", sym, f"{sym} reports earnings in {e} trading day{'s' if e != 1 else ''}", "Earnings can gap the price past your stop. Many traders reduce size before the report.", None)
        pl = pulse.get(sym)
        if pl and pl.get("warn", 0) >= pl.get("conf", 0) + 3:
            add("medium", sym, f"vnicorn Pulse warnings on {sym}", f"{pl['warn']} warnings vs {pl['conf']} confirmations in 10 days: the stock is acting weak.", None)
    for sec, v in sectors.items():
        if v / total > 0.4 and len(positions) > 2:
            add("medium", None, f"{v / total * 100:.0f}% of the portfolio is in {sec}", "A sector selloff would hit most of your holdings at once. Diversify across groups.", None)
    rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda x: rank[x["level"]])


def suggestions(held: set[str], profile: dict, fits: dict[str, float], scan: list[dict], meta: dict[str, dict], ideas: list[dict], n: int = 6) -> list[dict]:
    """Stocks that fit the portfolio's own profile (e.g. Aggressive Growth, Dividend Income) and are acting well.
    profile: {"key", "label"}; fits: symbol -> how well the stock matches that profile (0-1, same scoring as the profile)."""
    label = profile.get("label") or "your portfolio"
    by = {r["symbol"]: r for r in scan}
    cands = []
    for s, fit in fits.items():
        r = by.get(s, {})
        if s in held or fit < 0.6 or (r.get("bear_score") or 0) >= 60 or (r.get("template_passed") or 0) < 5:
            continue
        rs, bull = r.get("rs_rating") or 0, r.get("bull_score") or 0
        score = fit * 60 + rs * 0.25 + bull * 0.15
        reason = f"Fits your {label} profile ({round(fit * 100)}% match) · RS {rs} · Trend Template {r.get('template_passed')}/8"
        cands.append({"symbol": s, "name": meta.get(s, {}).get("name", s), "sector": meta.get(s, {}).get("sector", ""), "reason": reason,
                      "score": score, "source": label})
    for i in ideas:
        fit = fits.get(i["symbol"], 0)
        if i["symbol"] not in held and i.get("side") != "short" and fit >= 0.5:
            cands.append({"symbol": i["symbol"], "name": meta.get(i["symbol"], {}).get("name", i["symbol"]), "sector": meta.get(i["symbol"], {}).get("sector", ""),
                          "reason": f"Open trade idea that fits your {label} profile: entry {i['entry']}, stop {i['stop']}, target {i['target']} (R/R {i['rr']})",
                          "score": 75 + fit * 20, "source": "Trade idea"})
    seen, out = set(), []
    for c in sorted(cands, key=lambda c: -c["score"]):
        if c["symbol"] in seen:
            continue
        seen.add(c["symbol"])
        out.append({k: c[k] for k in ("symbol", "name", "sector", "reason", "source")})
        if len(out) >= n:
            break
    return out
