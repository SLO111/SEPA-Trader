from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from engine.strategies import REGISTRY, list_strategies, run_strategy
from engine.strategies.base import t

from .. import market_data
from ..models import User
from ..plans import limits_for
from ..security import current_user

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/market/search")
def search_symbols(q: str = Query(min_length=1, max_length=40), user: User = Depends(current_user)):
    return market_data.search_symbols(q)


@router.get("/market/candles/{symbol}")
def candles(symbol: str, interval: str = "1d", years: int = Query(3, ge=1, le=10), user: User = Depends(current_user)):
    market_data.watch(symbol)
    try:
        df = market_data.chart_data(symbol, interval, years)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except NotImplementedError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(404, f"No data found for {symbol.upper()}")
    has_session = "session" in df.columns
    rows = [
        {
            "time": t(ts),
            "open": round(float(r.open), 4 if r.close < 1 else 2),
            "high": round(float(r.high), 4 if r.close < 1 else 2),
            "low": round(float(r.low), 4 if r.close < 1 else 2),
            "close": round(float(r.close), 4 if r.close < 1 else 2),
            "volume": int(r.volume),
            **({"session": r.session} if has_session else {}),
        }
        for ts, r in df.iterrows()
    ]
    meta = market_data.symbol_meta(symbol)
    return {
        "symbol": symbol.upper(),
        **meta,
        "quote": market_data.quote(symbol),
        "delay_minutes": limits_for(user)["data_delay_minutes"],
        "live_at": market_data.live_status(symbol),
        "candles": rows,
    }


@router.get("/market/quotes")
def quotes(symbols: str = Query(max_length=2000), user: User = Depends(current_user)):
    out = []
    wanted = [x.strip().upper() for x in symbols.split(",") if x.strip()][:200]
    market_data.watch(*wanted)
    for s in wanted:
        try:
            out.append(market_data.quote(s))
        except Exception:
            out.append({"symbol": s, "error": "no data"})
    return out


@router.get("/strategies")
def strategies(user: User = Depends(current_user)):
    return list_strategies()


class StrategyItem(BaseModel):
    id: str
    params: dict[str, float] = Field(default_factory=dict)


class RunIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    interval: str = "1d"
    strategies: list[StrategyItem] = Field(max_length=50)


@router.post("/strategies/run")
def run(body: RunIn, user: User = Depends(current_user)):
    limit = limits_for(user)["max_strategies_on_chart"]
    if len(body.strategies) > limit:
        raise HTTPException(403, f"Your plan allows up to {limit} strategies on a chart.")
    unknown = [s.id for s in body.strategies if s.id not in REGISTRY]
    if unknown:
        raise HTTPException(400, f"Unknown strategies: {', '.join(unknown)}")
    limits = limits_for(user)
    locked = [REGISTRY[s.id].name for s in body.strategies if REGISTRY[s.id].requires and not limits.get(REGISTRY[s.id].requires)]
    if locked:
        raise HTTPException(403, f"Available on Pro and Premium plans only: {', '.join(locked)}")
    try:
        df = market_data.chart_data(body.symbol, body.interval)
    except Exception:
        raise HTTPException(404, f"No data found for {body.symbol.upper()}")
    bench = None
    if body.interval in ("1d", "1wk", "1mo"):
        try:
            bench = market_data.history("SPY", body.interval)
        except Exception:
            bench = None
    # A list in request order, so the same indicator can be added several times with different settings.
    return {"results": [run_strategy(s.id, df, s.params, bench) for s in body.strategies]}


@router.get("/market/info/{symbol}")
def info(symbol: str, user: User = Depends(current_user)):
    """Everything for the chart's side panel: quote, ranges, volume, key stats, earnings, extended hours, SEPA."""
    sym = symbol.upper().strip()
    market_data.watch(sym)
    try:
        d = market_data.history(sym)
    except Exception:
        raise HTTPException(404, f"No data found for {sym}")
    last = d.iloc[-1]
    y = d.iloc[-252:]
    meta = market_data.symbol_meta(sym)
    f = market_data.fundamentals_fresh(sym) or {}
    e = market_data.cached("earnings", sym) or {}
    from .sepa import cached_scan

    scan = next((r for r in cached_scan() if r["symbol"] == sym), None)
    ext = None
    try:
        rows = market_data.extended_hours([sym])
        ext = rows[0] if rows else None
    except Exception:
        ext = None
    stats = {k: f.get(k) for k in ("market_cap_b", "pe", "dividend_yield", "eps_growth", "beta")}
    if any(v is None for v in stats.values()):
        try:
            co = market_data.company(sym)
            sources = {**co.get("stats", {}), **co.get("valuation", {}), **co.get("profitability", {}), **co.get("dividends", {})}
            for k in stats:
                if stats[k] is None:
                    stats[k] = sources.get(k if k != "dividend_yield" else "yield", sources.get(k))
        except Exception:
            pass
    try:
        from engine import pulse as pulse_mod

        if not limits_for(user)["pulse"]:
            raise PermissionError
        pulse_info = market_data._fast(f"pulse1:{sym}", 300, lambda: pulse_mod.summary(d, market_data.history("SPY")))
    except PermissionError:
        pulse_info = {"locked": True}
    except Exception:
        pulse_info = None
    avg_vol = float(d["volume"].iloc[-51:-1].mean())
    return {
        "symbol": sym,
        "name": f.get("name") or meta.get("name", sym),
        "exchange": meta.get("exchange", ""),
        "sector": meta.get("sector") or f.get("sector") or "",
        "industry": f.get("industry", ""),
        "quote": market_data.quote(sym),
        "live_at": market_data.live_status(sym),
        "day": {"open": round(float(last.open), 2), "high": round(float(last.high), 2), "low": round(float(last.low), 2)},
        "week52": {"high": round(float(y["high"].max()), 2), "low": round(float(y["low"].min()), 2)},
        "volume": {"today": int(last.volume), "avg_50d": int(avg_vol), "relative": round(float(last.volume) / avg_vol, 2) if avg_vol else None},
        "stats": stats,
        "next_earnings": e.get("next_date"),
        "pulse": pulse_info,
        "extended": ext,
        # Overnight (8 PM - 4 AM ET, e.g. Blue Ocean ATS) needs a paid feed; Yahoo and Finnhub free don't provide it.
        "overnight": None,
        "sepa": ({k: scan[k] for k in ("rs_rating", "template_passed", "vcp", "pivot", "bull_score", "bear_score", "signals")}
                 if limits_for(user)["sepa_details"] else {**{k: scan[k] for k in ("rs_rating", "bull_score", "bear_score")},
                                                           "template_passed": scan.get("template_free"), "template_total": 3,
                                                           "vcp": None, "pivot": None, "signals": [], "locked": True}) if scan else None,
    }


@router.get("/market/analysis/{symbol}")
def analysis(symbol: str, user: User = Depends(current_user)):
    """Ask vnicornAI: a plain-English read of the chart, plus vnicornAI's best long and short plans."""
    from engine import chart_commentary, vnicorn_ai
    from engine.stages import stage_now

    from .. import vnicorn_service
    from ..db import SessionLocal

    if not limits_for(user)["ask_ai"]:
        raise HTTPException(403, "Ask vnicornAI is available on the Pro and Premium plans.")
    sym = symbol.upper().strip()
    market_data.watch(sym)
    try:
        df = market_data.history(sym)
    except Exception:
        raise HTTPException(404, f"No data found for {sym}")

    def build():
        try:
            bench = market_data.history("SPY")
        except Exception:
            bench = None
        with SessionLocal() as db:
            bundle = vnicorn_service.load(db)
        plans = {}
        if bundle is not None:
            feats = vnicorn_ai.features(df, bench)
            for side in ("long", "short"):
                plans[side] = vnicorn_ai.best_plan(bundle, df, bench, side, feats=feats)
        st = stage_now(df)
        preferred = "short" if st and st["stage"] == 4 else "long"
        best = plans.get(preferred)
        if plans.get("long") and plans.get("short") and plans["short"]["ev"] > plans["long"]["ev"] + 0.2:
            best = plans["short"]
        out = chart_commentary.analyze(df, bench, best, sym)
        out["plans"] = plans
        out["name"] = market_data.symbol_meta(sym).get("name", sym)
        return out

    return market_data._fast(f"analysis:{sym}", 600, build)


@router.get("/market/levels/{symbol}")
def trade_levels(symbol: str, side: Literal["long", "short"] = "long", user: User = Depends(current_user)):
    """Order-ticket helpers: ATR, nearest support / resistance and (Pro) the VCP pivot stop and vnicornAI's plan."""
    from engine.ideas import levels
    from engine.indicators import atr

    sym = symbol.upper().strip()
    try:
        df = market_data.history(sym)
    except Exception:
        raise HTTPException(404, f"No data found for {sym}")
    lim = limits_for(user)
    price = float(df["close"].iloc[-1])
    try:
        lv = levels(df)
    except Exception:
        lv = {"support": [], "resistance": []}
    out = {"symbol": sym, "price": round(price, 2), "atr": round(float(atr(df, 14).iloc[-1]), 2),
           "resistance": sorted(x for x in lv.get("resistance", []) if x > price * 1.005)[:3],
           "support": sorted((x for x in lv.get("support", []) if x < price * 0.995), reverse=True)[:3]}
    if lim["sepa_details"]:
        from engine.vcp import detect_vcp

        v = detect_vcp(df)
        out["vcp"] = {"pivot": v.get("pivot"), "stop": v.get("stop")} if v.get("detected") else None
    if lim["ask_ai"]:
        def plan():
            from .. import vnicorn_service
            from ..db import SessionLocal
            from engine import vnicorn_ai

            with SessionLocal() as db:
                bundle = vnicorn_service.load(db)
            if bundle is None:
                return None
            try:
                bench = market_data.history("SPY")
            except Exception:
                bench = None
            return vnicorn_ai.best_plan(bundle, df, bench, side)

        try:
            out["ai_plan"] = market_data._fast(f"tktplan:{sym}:{side}", 600, plan)
        except Exception:
            out["ai_plan"] = None
    return out
