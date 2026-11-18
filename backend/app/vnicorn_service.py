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


def ensure_trained(db: Session, hist: dict[str, pd.DataFrame], bench: pd.DataFrame | None, force: bool = False) -> dict | None:
    bundle = load(db)
    fresh = _trained_at is not None and datetime.now(timezone.utc) - _trained_at < timedelta(days=RETRAIN_DAYS)
    from .config import settings

    subset = _liquid(hist, settings.vnicorn_train_stocks or TRAIN_SYMBOLS)
    # the universe grew (e.g. 36 -> 850 stocks): a model that learned from far fewer stocks than it could is retrained now
    grown = bundle is not None and (bundle.get("symbols") or 0) < 0.8 * len(subset)
    if bundle is not None and fresh and not force and not grown:
        return bundle
    if len(subset) < 10:
        return bundle
    trades = real_trades(db, hist)
    from . import regen_status

    global last_error
    samples, free = training_budget(settings.vnicorn_samples)
    if samples is None:
        last_error = f"not enough memory to retrain ({free} MB free); kept the previous model"
        log.warning("vnicornAI: %s", last_error)
        return bundle
    log.info("Training vnicornAI on %d stocks, %d samples (%d MB free), %d real trades", len(subset), samples, free, len(trades))
    regen_status.stage(f"Training vnicornAI on {len(subset)} stocks ({samples:,} samples, {free} MB free)")
    try:
        import gc

        try:  # one thread: on a shared server every extra thread keeps its own working memory
            from threadpoolctl import threadpool_limits

            limiter = threadpool_limits(1)
        except Exception:
            limiter = None
        try:
            new = ai.train(subset, bench, trades, trade_histories=hist, budget=samples)
        finally:
            if limiter is not None:
                limiter.restore_original_limits()
        gc.collect()
        last_error = None
    except Exception as e:
        log.exception("vnicornAI training failed")
        last_error = f"training: {type(e).__name__}: {str(e)[:120]}"
        return bundle
    if not new.get("models"):
        return bundle
    new["move_preds"] = _move
    _save(db, new)
    return new


SAFETY_MB = 100  # never plan to use the last 100 MB
FIXED_MB_LOADED, FIXED_MB_COLD = 50, 130  # measured: training's fixed cost with scikit-learn already loaded / not yet
PER_SAMPLE_MB = 0.015  # measured ~0.011 MB per sample date (800 stocks), with margin
MIN_SAMPLES = 500


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
    return min(wanted, fit), free


def rate_and_create(db: Session, day, hist: dict[str, pd.DataFrame], bench: pd.DataFrame | None, ideas: list[TradeIdea],
                    stage_of: dict[str, int]) -> list[TradeIdea]:
    """Rate today's ideas, publish vnicornAI's own ideas (only if the model passed its walk-forward test),
    and refresh the major-move probabilities. Returns the new AI ideas."""
    global _move
    from . import regen_status

    regen_status.stage("Checking the vnicornAI model")
    bundle = ensure_trained(db, hist, bench)
    if bundle is None:
        return []
    regen_status.stage("vnicornAI rating ideas and move probabilities")
    feats: dict[str, pd.DataFrame] = {}

    def f(sym: str) -> pd.DataFrame | None:
        if sym not in feats:
            try:
                feats[sym] = ai.features(hist[sym], bench)
            except Exception:
                feats[sym] = None
        return feats[sym]

    # 1) rate every rules-based idea, the idea's own plan included as a candidate
    for i in ideas:
        df = hist.get(i.symbol)
        if df is None or f(i.symbol) is None:
            continue
        try:  # one stock with odd data must not cancel the ratings of all the others
            a = float(f(i.symbol)["_atr"].iloc[-1])
            risk = abs(i.entry - i.stop)
            extra = [(risk / a, abs(i.target - i.entry) / risk)] if a > 0 and risk > 0 else []
            plan = ai.best_plan(bundle, df, bench, i.side, extra, f(i.symbol))
        except Exception:
            log.debug("vnicornAI could not rate %s", i.symbol, exc_info=True)
            continue
        if plan:
            db.merge(AIPick(idea_id=i.id, prob=plan["prob"], ev=plan["ev"], stop=plan["stop"], trim=plan["trim"],
                            target=plan["target"], rr=plan["rr"], pick=plan["pick"] and bundle.get("trusted", {}).get(i.side, False)))

    # 2) its own ideas: longs in Stage 2, shorts in Stage 4, best expected value first
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
            plan = ai.best_plan(bundle, df, bench, side, None, f(sym))
        except Exception:
            continue
        if plan and plan["pick"]:
            cands.append((sym, plan))
    cands.sort(key=lambda x: -x[1]["ev"])
    new = []
    for sym, p in cands[:MAX_AI_IDEAS]:
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


def move_prob(symbol: str) -> float | None:
    return _move.get(symbol)


def status(db: Session) -> dict:
    bundle = load(db)
    if bundle is None:
        return {"trained": False}
    return {"trained": True, "trained_at": _trained_at.isoformat() if _trained_at else None, "symbols": bundle.get("symbols"),
            "report": bundle.get("report", {}), "trusted": bundle.get("trusted", {}),
            "retrain_days": RETRAIN_DAYS, "min_prob": ai.MIN_PROB, "min_ev": ai.MIN_EV, "horizon_days": ai.HORIZON}
