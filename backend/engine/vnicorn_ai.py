"""vnicornAI: a machine-learning model that builds trade plans (stop / trim / target) and rates them.

How it works
1. Features for every stock and day, from what the platform already computes: Move Detector factors,
   market cycle stage, Structure Count regime, distance to the 52-week high and the moving averages,
   momentum, volatility (ATR) and volume.
2. Candidate plans: a stop at 1-2.5 ATR from the entry and a target at 2R, 3R or 4R (R = the risk).
   The plan itself is part of the input, so the model can rate any plan, including a rules-based one.
3. Label: did the target come before the stop within HORIZON trading days? (stop counts first if both
   are touched in the same bar, to stay conservative.)
4. Model: gradient boosting (scikit-learn HistGradientBoosting), one for longs and one for shorts,
   validated walk-forward: trained on the past, scored on a later period it never saw, with a gap
   so labels of the training period can't peek into the test period.
5. For each setup the plan with the best expected value wins: EV = p * reward_R - (1 - p) * 1R.

A third model estimates the chance of a major move (+20% before -10% within 3 months) for the Move Detector.
Everything is small on purpose: it trains in about a minute on a free server and predicts in seconds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import move_detector as md
from . import stages, structure
from .indicators import atr, rsi, sma

HORIZON = 40
STOP_ATR = (1.0, 1.5, 2.0, 2.5)
TARGET_R = (2.0, 3.0, 4.0)
MOVE_UP, MOVE_STOP, MOVE_HORIZON = 0.20, 0.10, 63
MIN_PROB, MIN_EV = 0.45, 0.3
MARKET_FEATURES = ["bull_compression", "bull_volume", "bull_trend", "bull_rs", "bull_pivot", "bull_market",
                   "bear_breakdown", "bear_distribution", "bear_rs_weak", "bear_climax", "bear_failed_breakout",
                   "stage", "regime", "atr_pct", "from_high", "ret_21", "ret_63", "rvol", "dist_50", "dist_200", "rsi"]
PLAN_FEATURES = ["stop_atr", "target_r"]


# ------------------------------------------------------------------ features

def _regime_series(df: pd.DataFrame) -> pd.Series:
    """+1 while a Bull 4/4 is being defended, -1 for a Bear 4/4, 0 otherwise (known at each bar's close)."""
    out = pd.Series(0.0, index=df.index)
    for side, pts in structure.analyze(df).defence:
        for ts, _ in pts:
            out.loc[ts] = 1.0 if side == "bull" else -1.0
    return out


def features(df: pd.DataFrame, bench: pd.DataFrame | None) -> pd.DataFrame:
    bull, bear = md.compute_factors(df, bench)
    c, v = df["close"], df["volume"]
    a = atr(df, 14)
    f = pd.concat([bull.add_prefix("bull_"), bear.drop(columns=["market"]).add_prefix("bear_")], axis=1)
    f["stage"] = stages.daily_stages(df).astype(float)
    f["regime"] = _regime_series(df)
    f["atr_pct"] = a / c * 100
    f["from_high"] = (c / df["high"].rolling(252, min_periods=120).max() - 1) * 100
    f["ret_21"] = (c / c.shift(21) - 1) * 100
    f["ret_63"] = (c / c.shift(63) - 1) * 100
    f["rvol"] = v / sma(v, 50)
    f["dist_50"] = (c / sma(c, 50) - 1) * 100
    f["dist_200"] = (c / sma(c, 200) - 1) * 100
    f["rsi"] = rsi(c, 14)
    f["_atr"] = a
    return f


# ------------------------------------------------------------------ labels

def plan_outcomes(df: pd.DataFrame, starts: np.ndarray, atr_v: np.ndarray, side: str, horizon: int = HORIZON):
    """For each start bar and each (stop_atr, target_r): (won 1/0, realized R). Vectorized over the horizon."""
    from numpy.lib.stride_tricks import sliding_window_view

    c, h, lo = (df[k].to_numpy(dtype=float) for k in ("close", "high", "low"))
    hw, lw = sliding_window_view(h[1:], horizon), sliding_window_view(lo[1:], horizon)  # window i = bars i+1 .. i+horizon
    long = side == "long"
    rows = []
    for k in STOP_ATR:
        for tr in TARGET_R:
            risk = k * atr_v
            entry = c[starts]
            stop = entry - risk if long else entry + risk
            target = entry + tr * risk if long else entry - tr * risk
            H, L = hw[starts], lw[starts]
            hit_t = (H >= target[:, None]) if long else (L <= target[:, None])
            hit_s = (L <= stop[:, None]) if long else (H >= stop[:, None])
            t_idx = np.where(hit_t.any(1), hit_t.argmax(1), horizon)
            s_idx = np.where(hit_s.any(1), hit_s.argmax(1), horizon)
            won = (t_idx < s_idx).astype(np.float32)
            last = c[starts + horizon]
            timeout_r = (last - entry) * (1 if long else -1) / risk
            realized = np.where(won == 1, tr, np.where(s_idx < horizon, -1.0, np.clip(timeout_r, -1, tr)))
            rows.append((k, tr, won, realized.astype(np.float32)))
    return rows


def _move_label(df: pd.DataFrame, starts: np.ndarray) -> np.ndarray:
    from numpy.lib.stride_tricks import sliding_window_view

    c, h, lo = (df[k].to_numpy(dtype=float) for k in ("close", "high", "low"))
    hw, lw = sliding_window_view(h[1:], MOVE_HORIZON), sliding_window_view(lo[1:], MOVE_HORIZON)
    ok = starts + MOVE_HORIZON < len(c)
    out = np.full(len(starts), np.nan, dtype=np.float32)
    s = starts[ok]
    hit_t = hw[s] >= c[s, None] * (1 + MOVE_UP)
    hit_s = lw[s] <= c[s, None] * (1 - MOVE_STOP)
    t_idx = np.where(hit_t.any(1), hit_t.argmax(1), MOVE_HORIZON)
    s_idx = np.where(hit_s.any(1), hit_s.argmax(1), MOVE_HORIZON)
    out[ok] = (t_idx < s_idx).astype(np.float32)
    return out


def build_dataset(histories: dict[str, pd.DataFrame], bench: pd.DataFrame | None, step: int = 5) -> dict[str, pd.DataFrame]:
    """Training rows for the long, short and move models (one row per stock, sample date and plan)."""
    plans = {"long": [], "short": []}
    moves = []
    for sym, df in histories.items():
        if len(df) < 320:
            continue
        f = features(df, bench)
        valid = f[MARKET_FEATURES].notna().all(axis=1).to_numpy() & (f["_atr"] > 0).to_numpy()
        idx = np.arange(len(df))
        starts = idx[(idx >= 200) & (idx < len(df) - HORIZON - 1) & valid][::step]
        if not len(starts):
            continue
        X = f[MARKET_FEATURES].to_numpy(dtype=np.float32)[starts]
        dates = df.index[starts]
        atr_v = f["_atr"].to_numpy(dtype=float)[starts]
        for side in ("long", "short"):
            for k, tr, won, realized in plan_outcomes(df, starts, atr_v, side):
                d = pd.DataFrame(X, columns=MARKET_FEATURES)
                d["stop_atr"], d["target_r"] = np.float32(k), np.float32(tr)
                d["y"], d["realized_r"], d["date"], d["symbol"] = won, realized, dates, sym
                plans[side].append(d)
        m = pd.DataFrame(X, columns=MARKET_FEATURES)
        m["y"], m["date"], m["symbol"] = _move_label(df, starts), dates, sym
        moves.append(m.dropna(subset=["y"]))
    out = {side: pd.concat(v, ignore_index=True) if v else pd.DataFrame() for side, v in plans.items()}
    out["move"] = pd.concat(moves, ignore_index=True) if moves else pd.DataFrame()
    return out


REAL_WIN_WEIGHT, REAL_LOSS_WEIGHT = 3.0, 2.0  # real trades count more than market samples; winners the most


def trade_examples(trades: list[dict], histories: dict[str, pd.DataFrame], bench: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    """Training rows from real closed trades (ideas, Move Detector, chart trades).
    trades: [{symbol, side long|short, entry_date, entry, stop, target, won bool, r}]. Winners are the examples to follow."""
    rows: dict[str, list] = {"long": [], "short": []}
    feats: dict[str, pd.DataFrame] = {}
    for t in trades:
        sym, side = t["symbol"], "short" if t.get("side") == "short" else "long"
        df = histories.get(sym)
        if df is None or len(df) < 220:
            continue
        if sym not in feats:
            feats[sym] = features(df, bench)
        f = feats[sym]
        pos = f.index.searchsorted(pd.Timestamp(t["entry_date"]), side="right") - 1
        if pos < 200:
            continue
        row = f.iloc[pos]
        a = float(row["_atr"]) if row["_atr"] > 0 else None
        risk = abs(float(t["entry"]) - float(t["stop"]))
        if not a or not risk or row[MARKET_FEATURES].isna().any():
            continue
        won = bool(t["won"])
        rows[side].append({**{c: float(row[c]) for c in MARKET_FEATURES}, "stop_atr": risk / a,
                           "target_r": abs(float(t["target"]) - float(t["entry"])) / risk, "y": int(won),
                           "realized_r": float(t.get("r") or 0.0), "date": f.index[pos], "symbol": sym,
                           "w": REAL_WIN_WEIGHT if won else REAL_LOSS_WEIGHT, "real": True})
    return {s: pd.DataFrame(v) for s, v in rows.items()}


# ------------------------------------------------------------------ training

def _model():
    from sklearn.ensemble import HistGradientBoostingClassifier

    return HistGradientBoostingClassifier(max_iter=160, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
                                          l2_regularization=1.0, random_state=7)


def _validate(d: pd.DataFrame, cols: list[str], plan: bool) -> dict:
    """Walk-forward check: train on the first 75% of dates, test on the rest (after a gap)."""
    from sklearn.metrics import roc_auc_score

    dates = np.sort(d["date"].unique())
    if len(dates) < 20 or d["y"].nunique() < 2:
        return {}
    split = dates[int(len(dates) * 0.75)]
    gap = pd.Timedelta(days=int(HORIZON * 1.5))
    train, test = d[d["date"] < split - gap], d[d["date"] >= split]
    if train["y"].nunique() < 2 or test["y"].nunique() < 2 or len(test) < 50:
        return {}
    m = _model().fit(train[cols], train["y"], sample_weight=train["w"] if "w" in train else None)
    p = m.predict_proba(test[cols])[:, 1]
    out = {"auc": round(float(roc_auc_score(test["y"], p)), 3), "test_rows": int(len(test)),
           "test_from": pd.Timestamp(split).strftime("%Y-%m-%d"), "base_rate": round(float(test["y"].mean()) * 100, 1)}
    if plan:
        ev = p * test["target_r"].to_numpy() - (1 - p)
        picks = (ev >= MIN_EV) & (p >= MIN_PROB)
        out.update({
            "all_avg_r": round(float(test["realized_r"].mean()), 3),
            "picks": int(picks.sum()),
            "picks_win_rate": round(float(test["y"][picks].mean()) * 100, 1) if picks.any() else None,
            "picks_avg_r": round(float(test["realized_r"][picks].mean()), 3) if picks.any() else None,
        })
    else:
        top = p >= np.quantile(p, 0.9)
        out.update({"top10_hit_rate": round(float(test["y"][top].mean()) * 100, 1)})
    return out


def train(histories: dict[str, pd.DataFrame], bench: pd.DataFrame | None, trades: list[dict] | None = None,
          trade_histories: dict[str, pd.DataFrame] | None = None) -> dict:
    """Train the three models and return them with their walk-forward report.
    Real closed trades (if given) are added to the plan models with a higher weight: winners 3x, losers 2x."""
    data = build_dataset(histories, bench)
    real = trade_examples(trades or [], trade_histories or histories, bench) if trades else {}
    real_n = {s: int(len(v)) for s, v in real.items()}
    real_w = {s: int(v["y"].sum()) if len(v) else 0 for s, v in real.items()}
    for side in ("long", "short"):
        d = data.get(side, pd.DataFrame())
        if not d.empty:
            d["w"], d["real"] = 1.0, False
        if side in real and len(real[side]):
            data[side] = pd.concat([d, real[side]], ignore_index=True) if not d.empty else real[side]
    cols = MARKET_FEATURES + PLAN_FEATURES
    bundle: dict = {"models": {}, "report": {}, "features": MARKET_FEATURES}
    for name, d in data.items():
        if d.empty or d["y"].nunique() < 2:
            continue
        use = cols if name != "move" else MARKET_FEATURES
        bundle["report"][name] = {"rows": int(len(d)), "symbols": int(d["symbol"].nunique()), **_validate(d, use, name != "move")}
        w = d["w"].to_numpy(dtype=float) if "w" in d else None
        bundle["models"][name] = _model().fit(d[use], d["y"], sample_weight=w)
        if name in real_n:
            bundle["report"][name].update({"real_trades": real_n[name], "real_winners": real_w[name]})
    # Trust a plan model only if, on the unseen period, its picks beat taking every setup (and are positive).
    bundle["trusted"] = {
        side: bool(r.get("picks_avg_r") is not None and r["picks_avg_r"] > max(0.0, r.get("all_avg_r", 0.0)) and r.get("picks", 0) >= 30)
        for side, r in bundle["report"].items() if side != "move"
    }
    bundle["symbols"] = len(histories)
    return bundle


# ------------------------------------------------------------------ prediction

def _levels(df: pd.DataFrame) -> dict:
    from .ideas import levels

    try:
        return levels(df)
    except Exception:
        return {"support": [], "resistance": []}


def best_plan(bundle: dict, df: pd.DataFrame, bench: pd.DataFrame | None, side: str,
              extra: list[tuple[float, float]] | None = None, feats: pd.DataFrame | None = None) -> dict | None:
    """Rate every candidate plan for today's setup and return the one with the highest expected value."""
    model = bundle.get("models", {}).get(side)
    if model is None or len(df) < 220:
        return None
    f = feats if feats is not None else features(df, bench)
    row = f.iloc[-1]
    if row[MARKET_FEATURES].isna().any() or not row["_atr"] > 0:
        return None
    a, price = float(row["_atr"]), float(df["close"].iloc[-1])
    cands = [(k, tr) for k in STOP_ATR for tr in TARGET_R] + [(k, tr) for k, tr in (extra or []) if 0.3 <= k <= 6 and 1 <= tr <= 8]
    X = pd.DataFrame([[*row[MARKET_FEATURES].to_numpy(dtype=float), k, tr] for k, tr in cands], columns=MARKET_FEATURES + PLAN_FEATURES)
    p = model.predict_proba(X)[:, 1]
    ev = p * X["target_r"].to_numpy() - (1 - p)
    i = int(np.argmax(ev))
    k, tr = cands[i]
    long = side == "long"
    risk = k * a
    stop = price - risk if long else price + risk
    target = price + tr * risk if long else price - tr * risk
    # trim: the first resistance (support for shorts) between 1R and the target, else 1.5R
    lv = _levels(df)
    if long:
        zone = [x for x in lv.get("resistance", []) if price + risk <= x < target]
        trim = min(zone) if zone else price + 1.5 * risk
    else:
        zone = [x for x in lv.get("support", []) if target < x <= price - risk]
        trim = max(zone) if zone else price - 1.5 * risk
    return {"side": side, "prob": round(float(p[i]), 3), "ev": round(float(ev[i]), 2), "entry": round(price, 2),
            "stop": round(stop, 2), "trim": round(trim, 2), "target": round(target, 2), "rr": round(tr, 1),
            "stop_atr": round(k, 2), "pick": bool(p[i] >= MIN_PROB and ev[i] >= MIN_EV)}


def move_probability(bundle: dict, feats: pd.DataFrame) -> float | None:
    model = bundle.get("models", {}).get("move")
    row = feats.iloc[[-1]][MARKET_FEATURES]
    if model is None or row.isna().any(axis=None):
        return None
    return round(float(model.predict_proba(row)[:, 1][0]), 3)
