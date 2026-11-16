from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from engine.data.universe import NON_STOCK_SECTORS, SYMBOLS
from engine.report import build_pdf, period_returns, takeaways, verdict
from engine.scanner import sepa_report

from .. import market_data
from ..models import User
from ..plans import limits_for
from ..security import current_user
from .sepa import _rs_for, cached_scan

router = APIRouter(prefix="/api/stock", tags=["stock"])


def _peers(symbol: str, sector: str) -> list[dict]:
    rs = {r["symbol"]: r["rs_rating"] for r in cached_scan()}
    candidates = [s for s, m in SYMBOLS.items() if m["sector"] == sector and s != symbol and m["sector"] not in NON_STOCK_SECTORS]
    rows = []
    for s in candidates:
        try:
            q = market_data.quote(s)
            f = market_data.cached("fundamentals", s) or {"name": SYMBOLS[s]["name"]}
        except Exception:
            continue
        rows.append({"symbol": s, "name": f.get("name", s), "price": q["price"], "change_pct": q["change_pct"],
                     "market_cap_b": f.get("market_cap_b"), "pe": f.get("pe"), "dividend_yield": f.get("dividend_yield"), "rs_rating": rs.get(s)})
    rows.sort(key=lambda r: -(r["market_cap_b"] or 0))
    return rows[:6]


def _build(symbol: str, user: User) -> dict:
    symbol = symbol.upper().strip()
    market_data.watch(symbol)
    try:
        hist = market_data.history(symbol)
    except Exception:
        raise HTTPException(404, f"No data found for {symbol}")
    co = market_data.company(symbol)
    quote = market_data.quote(symbol)
    returns = period_returns(hist["close"])
    sepa = sepa_report(market_data.history, symbol, _rs_for(symbol))
    if not limits_for(user)["move_detector"]:
        sepa["move_detector"] = None
    peers = _peers(symbol, co.get("sector") or SYMBOLS.get(symbol, {}).get("sector", ""))
    items = takeaways(co, sepa, returns, [p["pe"] for p in peers] + [co.get("valuation", {}).get("pe")])
    from engine.key_facts import key_facts
    from engine.stages import stage_now

    facts = market_data._fast(f"keyfacts:{symbol}", 6 * 3600, lambda: key_facts(co, hist, stage_now(hist), sepa, peers))
    return {"company": co, "quote": quote, "returns": returns, "sepa": sepa, "peers": peers, "takeaways": items, "verdict": verdict(items),
            "key_facts": facts, "history": hist}


@router.get("/{symbol}")
def stock(symbol: str, user: User = Depends(current_user)):
    data = _build(symbol, user)
    data.pop("history")
    return data


@router.get("/{symbol}/report.pdf")
def report(symbol: str, user: User = Depends(current_user)):
    if not limits_for(user)["reports"]:
        raise HTTPException(403, "PDF reports are available on the Premium plan.")
    d = _build(symbol, user)
    pdf = build_pdf(d["company"], d["quote"], d["history"], d["sepa"], d["takeaways"], d["returns"], d["peers"])
    name = f"{d['company']['symbol']}-report-{d['quote']['date']}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/{symbol}/technicals")
def technicals(symbol: str, interval: str = "1d", user: User = Depends(current_user)):
    """Technical rating (15 moving averages + 11 oscillators) on 1 hour, 1 day or 1 week bars."""
    from engine.technicals import rating

    sym = symbol.upper().strip()
    if interval not in ("1h", "1d", "1wk"):
        raise HTTPException(400, "interval must be 1h, 1d or 1wk")

    def build():
        if interval == "1h":
            df = market_data.chart_data(sym, "1h")
            if "session" in df.columns:
                df = df[df["session"] == "regular"]
        elif interval == "1wk":
            df = market_data.history(sym, "1wk", 10)
        else:
            df = market_data.history(sym)
        return {"symbol": sym, "interval": interval, **rating(df)}

    try:
        return market_data._fast(f"tech:{sym}:{interval}", 300, build)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, f"No data for {sym} on {interval}")
