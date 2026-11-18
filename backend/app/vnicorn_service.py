"""vnicornAI in the app: weekly training (stored in the database), daily ratings for the trade ideas,
its own AI ideas, and the major-move probability for the Move Detector.

Built for a free server: it trains on the most liquid stocks only, once a week, in the background job
that publishes the ideas after the close, and the model survives restarts because it is kept in the database.
"""

from __future__ import annotations

import logging
import pickle
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy.orm import Session

from engine import vnicorn_ai as ai

from .models import AIPick, ModelBlob, TradeIdea

log = logging.getLogger("sepa.vnicornai")
MODEL = "vnicornai"
RETRAIN_DAYS = 7
TRAIN_SYMBOLS = 850  # default; settings.vnicorn_train_stocks (VNICORN_TRAIN_STOCKS on Render) decides
last_error: str | None = None  # last training / rating failure, shown in /api/health
MAX_AI_IDEAS = 10

_bundle: dict | None = None
_trained_at: datetime | None = None
_move: dict[str, float] = {}


def _aware(t: datetime | None) -> datetime | None:
    return t.replace(tzinfo=timezone.utc) if t is not None and t.tzinfo is None else t


def load(db: Session) -> dict | None:
    global _bundle, _trained_at, _move
    if _bundle is not None:
        return _bundle
    row = db.get(ModelBlob, MODEL)
    if row is None:
        return None
    try:
        _bundle = pickle.loads(row.data)
        _trained_at = _aware(row.trained_at)
        _move = _bundle.get("move_preds", {})
    except Exception:
        log.exception("Could not load the stored vnicornAI model")
        return None
    return _bundle


def _save(db: Session, bundle: dict) -> None:
    global _bundle, _trained_at
    data = pickle.dumps(bundle, protocol=pickle.HIGHEST_PROTOCOL)
    row = db.get(ModelBlob, MODEL)
    now = datetime.now(timezone.utc)
    if row is None:
        db.add(ModelBlob(name=MODEL, data=data, trained_at=now))
    else:
        row.data, row.trained_at = data, now
    db.commit()
    _bundle, _trained_at = bundle, now


def _liquid(hist: dict[str, pd.DataFrame], n: int) -> dict[str, pd.DataFrame]:
    dv = {s: float((d["close"] * d["volume"]).iloc[-60:].mean()) for s, d in hist.items() if len(d) >= 320}
    keep = sorted(dv, key=lambda s: -dv[s])[:n]
    return {s: hist[s] for s in keep}


def real_trades(db: Session, hist: dict[str, pd.DataFrame]) -> list[dict]:
    """Closed real trades to learn from: daily ideas (target / stop) and Move Detector + chart trades (not copies)."""
    from sqlalchemy import select

    from .models import PaperTrade

    out = []
    for r in db.scalars(select(TradeIdea).where(TradeIdea.status.in_(("TARGET", "STOPPED")), TradeIdea.r_multiple.is_not(None))).all():
        out.append({"symbol": r.symbol, "side": r.side, "entry_date": r.batch_date, "entry": r.entry, "stop": r.stop, "target": r.target,
                    "won": r.r_multiple > 0, "r": r.r_multiple})
    from engine.paper import follow

    for t in db.scalars(select(PaperTrade).where(PaperTrade.timeframe.in_(("MD", "CH")))).all():
        df = hist.get(t.symbol)
        if df is None:
            continue
        f = follow({"side": t.side, "entry": t.entry, "stop": t.stop, "trim": t.trim, "target": t.target, "entry_date": t.entry_date,
                    "exit_date": t.exit_date, "exit_price": t.exit_price}, df)
        if f["open"]:
            continue
        out.append({"symbol": t.symbol, "side": t.side, "entry_date": t.entry_date, "entry": t.entry, "stop": t.stop, "target": t.target,
                    "won": f["r_multiple"] > 0, "r": f["r_multiple"]})
    return out


def _use_long_history() -> int:
    """Years of history to learn from: settings.vnicorn_train_years on a big server with live data, else 0 (= the stored
    ~3 years). The long history is downloaded only when training, so price refreshes stay small."""
    from . import memory
    from .config import settings

    years = settings.vnicorn_train_years
    if years <= 3 or settings.data_provider == "synthetic" or memory.limit_mb() < 4000:
        return 0
    return years


def _long_histories(symbols: list[str], years: int) -> dict[str, pd.DataFrame]:
    """Long daily histories for training, in chunks; symbols that fail are simply missing (the caller keeps the stored ones)."""
    from engine.data.providers import get_provider

    from . import regen_status
    from .config import settings

    provider = get_provider(settings.data_provider)
    out: dict[str, pd.DataFrame] = {}
    for i in range(0, len(symbols), 200):
        chunk = symbols[i : i + 200]
        regen_status.stage(f"Downloading {years} years of prices for vnicornAI ({i + len(chunk)}/{len(symbols)})")
        try:
            got = provider.bulk_history(chunk, years=years)
        except Exception:
            log.warning("vnicornAI: long history download failed for a chunk", exc_info=True)
            continue
        from .data_store import clean_prices

        for s, df in got.items():
            try:
                df = clean_prices(df[["open", "high", "low", "close", "volume"]].astype(float))
            except Exception:
                continue
            if len(df):
                out[s] = df
    return out


def ensure_trained(db: Session, hist: dict[str, pd.DataFrame], bench: pd.DataFrame | None, force: bool = False) -> dict | None:
    bundle = load(db)
    fresh = _trained_at is not None and datetime.now(timezone.utc) - _trained_at < timedelta(days=RETRAIN_DAYS)
    from .config import settings

    subset = _liquid(hist, settings.vnicorn_train_stocks or len(hist))  # 0 = every stock with enough history
    # the universe grew (e.g. 36 -> 850 stocks): a model that learned from far fewer stocks than it could is retrained now
    grown = bundle is not None and (bundle.get("symbols") or 0) < 0.8 * len(subset)
    global last_error
    samples, free = training_budget(settings.vnicorn_samples)
    years = _use_long_history()
    # the server can now learn from far more data than the stored model did (more samples, longer history): retrain now
    cfg = (bundle or {}).get("train_config") or {}
    starved = bundle is not None and samples is not None and (
        (cfg.get("budget") or 0) < 0.5 * samples or (cfg.get("years") or 3) < (years or 3))
    if bundle is not None and fresh and not force and not grown and not starved:
        return bundle
    if len(subset) < 10:
        return bundle
    trades = real_trades(db, hist)
    from . import regen_status

    if samples is None:
        last_error = f"not enough memory to retrain ({free} MB free); kept the previous model"
        log.warning("vnicornAI: %s", last_error)
        return bundle
    train_on, train_bench = subset, bench
    if years:
        long = _long_histories([*subset, "SPY"], years)
        train_bench = long.pop("SPY", None)
        if train_bench is None:  # without a long benchmark the features would not line up: stay with the stored years
            years = 0
            train_bench = bench
        else:
            train_on = {s: (long[s] if s in long and len(long[s]) > len(df) else df) for s, df in subset.items()}
        del long
    log.info("Training vnicornAI on %d stocks, %d samples, %s (%d MB free), %d real trades", len(train_on), samples,
             f"{years} years" if years else "stored prices", free, len(trades))
    regen_status.stage(f"Training vnicornAI on {len(train_on)} stocks ({samples:,} samples, {years or 3} years, {free} MB free)")
    try:
        import gc
        import os

        try:  # one thread on a small server (every extra thread keeps its own working memory); all cores on a big one
            from threadpoolctl import threadpool_limits

            limiter = threadpool_limits((os.cpu_count() or 1) if free > 4000 else 1)
        except Exception:
            limiter = None
        try:
            new = ai.train(train_on, train_bench, trades, trade_histories=hist, budget=samples)
        finally:
            if limiter is not None:
                limiter.restore_original_limits()
        del train_on
        gc.collect()
        last_error = None
    except Exception as e:
        log.exception("vnicornAI training failed")
        last_error = f"training: {type(e).__name__}: {str(e)[:120]}"
        return bundle
    if not new.get("models"):
        return bundle
    new["move_preds"] = _move
    plans = len(ai.STOP_ATR) * len(ai.TARGET_R)  # each sample day is tried with every candidate plan
    used = int(((new.get("report") or {}).get("long") or {}).get("rows", 0) // plans) or None
    new["train_config"] = {"budget": samples, "samples": used, "years": years or 3}
    _save(db, new)
    return new


SAFETY_MB = 100  # never plan to use the last 100 MB
LOW_MEMORY_MB = 40  # below this, rating covers the day's ideas only
FIXED_MB_LOADED, FIXED_MB_COLD = 50, 130  # measured: training's fixed cost with scikit-learn already loaded / not yet
PER_SAMPLE_MB = 0.015  # measured ~0.011 MB per sample date (800 stocks), with margin
MIN_SAMPLES = 500


MAX_AUTO_SAMPLES = 120_000  # with VNICORN_SAMPLES=0: the most sample dates memory may be planned for (~1.8 GB)


def training_budget(wanted: int) -> tuple[int | None, int]:
    """Samples that fit in the memory left (None = too little to train now) and the free MB, measured right now."""
    import gc
    import sys

    from . import memory

    gc.collect()
    free = memory.free_mb()
    fixed = FIXED_MB_LOADED if "sklearn" in sys.modules else FIXED_MB_COLD
    fit = int((free - SAFETY_MB - fixed) / PER_SAMPLE_MB)
    if fit < MIN_SAMPLES:
        return None, free
    return min(wanted or MAX_AUTO_SAMPLES, fit), free


def rate_and_create(db: Session, day, hist: dict[str, pd.DataFrame], bench: pd.DataFrame | None, ideas: list[TradeIdea],
                    stage_of: dict[str, int], train_hist: dict[str, pd.DataFrame] | None = None, bench_of=None) -> list[TradeIdea]:
    """Rate today's ideas, publish vnicornAI's own ideas (only if the model passed its walk-forward test),
    and refresh the major-move probabilities. Returns the new AI ideas.
    hist: every stock to rate (all regions); train_hist: the stocks it learns from (US; default = hist);
    bench_of(symbol): each stock's own index (default: `bench` for all)."""
    global _move
    from . import regen_status
    from engine.data.universe import region_of

    bench_of = bench_of or (lambda _s: bench)
    train_hist = train_hist if train_hist is not None else hist
    regen_status.stage("Checking the vnicornAI model")
    bundle = ensure_trained(db, train_hist, bench)
    if bundle is None:
        return []
    regen_status.stage(f"vnicornAI rating {len(ideas)} ideas and {len(hist)} stocks")
    feats: dict[str, pd.DataFrame] = {}

    def f(sym: str) -> pd.DataFrame | None:
        # only today's row is needed to rate a stock: keep that (a 1-row frame), not the whole feature table
        # (~0.16 MB per stock, ~135 MB for the universe on a 512 MB server)
        if sym not in feats:
            try:
                feats[sym] = ai.features(hist[sym], bench_of(sym)).iloc[[-1]].copy()
            except Exception:
                feats[sym] = None
            if len(feats) % 100 == 0:
                import gc

                gc.collect()
        return feats[sym]

    from . import memory

    low_memory = memory.free_mb() < LOW_MEMORY_MB

    # 1) rate every rules-based idea, the idea's own plan included as a candidate
    for i in ideas:
        df = hist.get(i.symbol)
        if df is None or f(i.symbol) is None:
            continue
        try:  # one stock with odd data must not cancel the ratings of all the others
            a = float(f(i.symbol)["_atr"].iloc[-1])
            risk = abs(i.entry - i.stop)
            extra = [(risk / a, abs(i.target - i.entry) / risk)] if a > 0 and risk > 0 else []
            plan = ai.best_plan(bundle, df, bench_of(i.symbol), i.side, extra, f(i.symbol))
        except Exception:
            log.debug("vnicornAI could not rate %s", i.symbol, exc_info=True)
            continue
        if plan:
            db.merge(AIPick(idea_id=i.id, prob=plan["prob"], ev=plan["ev"], stop=plan["stop"], trim=plan["trim"],
                            target=plan["target"], rr=plan["rr"], pick=plan["pick"] and bundle.get("trusted", {}).get(i.side, False)))

    # 2) its own ideas: longs in Stage 2, shorts in Stage 4, best expected value first
    global last_error
    if low_memory:  # not enough memory to look at the whole universe this time: the day's ideas are rated, that's all
        last_error = f"low memory ({memory.free_mb()} MB free): rated today's ideas only, no new AI ideas or move probabilities"
        log.warning("vnicornAI: %s", last_error)
        db.commit()
        return []
    taken = {i.symbol for i in ideas}
    cands = []
    for sym, df in hist.items():
        if sym in taken or len(df) < 260:
            continue
        price = float(df["close"].iloc[-1])
        if price < 5 or float((df["close"] * df["volume"]).iloc[-50:].mean()) < 5e6:
            continue
        side = "long" if stage_of.get(sym) == 2 else "short" if stage_of.get(sym) == 4 else None
        if side is None or not bundle.get("trusted", {}).get(side):
            continue
        if f(sym) is None:
            continue
        try:
            plan = ai.best_plan(bundle, df, bench_of(sym), side, None, f(sym))
        except Exception:
            continue
        if plan and plan["pick"]:
            cands.append((sym, plan))
    cands.sort(key=lambda x: -x[1]["ev"])
    per_region: dict[str, int] = {}
    chosen = []
    for sym, p in cands:  # the best of each region, so the US doesn't crowd out Europe / Asia
        r = region_of(sym)
        if per_region.get(r, 0) < MAX_AI_IDEAS:
            per_region[r] = per_region.get(r, 0) + 1
            chosen.append((sym, p))
    new = []
    for sym, p in chosen:
        risk = abs(p["entry"] - p["stop"])
        row = TradeIdea(batch_date=day, symbol=sym, timeframe="AI", side=p["side"], entry=p["entry"], stop=p["stop"], trim=p["trim"],
                        target=p["target"], rr=p["rr"], weight=round(min(20.0, 1 / (risk / p["entry"])), 1) if risk else 0.0,
                        score=round(p["prob"] * 100, 1),
                        reason=f"vnicornAI: {p['prob'] * 100:.0f}% estimated chance to reach the target before the stop "
                               f"(expected value {p['ev']:+.2f}R), stop at {p['stop_atr']}× ATR, learned from similar setups in the past.",
                        status="WAIT", current=p["entry"])
        db.add(row)
        new.append((row, p))
    db.flush()
    for row, p in new:
        db.merge(AIPick(idea_id=row.id, prob=p["prob"], ev=p["ev"], stop=p["stop"], trim=p["trim"], target=p["target"], rr=p["rr"], pick=True))

    # 3) chance of a major move (+20% before -10% within 3 months) for the Move Detector
    preds = {}
    for sym in hist:
        if f(sym) is not None:
            pr = ai.move_probability(bundle, f(sym))
            if pr is not None:
                preds[sym] = pr
    _move = preds
    bundle["move_preds"] = preds
    try:
        row = db.get(ModelBlob, MODEL)
        if row is not None:
            row.data = pickle.dumps(bundle, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        log.exception("Could not store the move predictions")
    db.commit()
    log.info("vnicornAI: rated %d ideas, %d AI ideas, %d move probabilities", len(ideas), len(new), len(preds))
    return [r for r, _ in new]


def bench_for(symbol: str) -> pd.DataFrame | None:
    """The index a stock is measured against: SPY for US stocks, Euro Stoxx 50 / Asia ex Japan for Europe / Asia
    (vnicornAI learned from US stocks against SPY; each other stock is compared with its own market the same way)."""
    from engine.data.intl import BENCHMARKS
    from engine.data.universe import region_of

    from . import market_data

    sym = BENCHMARKS.get(region_of(symbol), "SPY")
    for s in dict.fromkeys((sym, "SPY")):
        try:
            return market_data._fast(f"bench:{s}", 1800, lambda s=s: market_data.stored_history(s))
        except Exception:
            try:
                return market_data.history(s)
            except Exception:
                continue
    return None


def move_prob(symbol: str) -> float | None:
    return _move.get(symbol)


def status(db: Session) -> dict:
    bundle = load(db)
    if bundle is None:
        return {"trained": False}
    from engine.data.universe import region_of

    preds = bundle.get("move_preds") or _move
    by_region: dict[str, int] = {}
    for s in preds:
        by_region[region_of(s)] = by_region.get(region_of(s), 0) + 1
    return {"trained": True, "trained_at": _trained_at.isoformat() if _trained_at else None, "symbols": bundle.get("symbols"),
            "rated": len(preds), "rated_by_region": by_region,
            "samples": (bundle.get("train_config") or {}).get("samples"), "years": (bundle.get("train_config") or {}).get("years"),
            "report": bundle.get("report", {}), "trusted": bundle.get("trusted", {}),
            "retrain_days": RETRAIN_DAYS, "min_prob": ai.MIN_PROB, "min_ev": ai.MIN_EV, "horizon_days": ai.HORIZON}
