"""Backtesting.

1. Move Detector validation (layer 1): do high Bull/Bear scores precede major moves more often than chance?
2. Machine-learning layer (layer 3): a gradient-boosting model on the same factors, trained walk-forward
   (always on the past, tested on the following, unseen period).
3. Strategy backtests for chart strategies that emit BUY/SELL signals.

Labels use the triple-barrier method: a "major up move" means +UP% is reached within HORIZON trading days
before -STOP% is hit. A "major down move" means -DOWN% within HORIZON days.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import move_detector as md
from .strategies import run_strategy

UP, STOP, DOWN, HORIZON = 0.20, 0.07, 0.15, 20
BUCKETS = [(0, 40), (40, 60), (60, 75), (75, 101)]


def triple_barrier(df: pd.DataFrame, up: float = UP, stop: float = STOP, horizon: int = HORIZON) -> pd.Series:
    """1.0 if price rises `up` before falling `stop` within `horizon` bars, else 0.0; NaN where the future is unknown."""
    c, h, lo = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
    n = len(c)
    out = np.full(n, np.nan)
    for i in range(n - horizon):
        top, bottom = c[i] * (1 + up), c[i] * (1 - stop)
        res = 0.0
        for j in range(i + 1, i + horizon + 1):
            if lo[j] <= bottom:
                break
            if h[j] >= top:
                res = 1.0
                break
        out[i] = res
    return pd.Series(out, index=df.index)


def down_move(df: pd.DataFrame, down: float = DOWN, horizon: int = HORIZON) -> pd.Series:
    lo = df["low"]
    fut_min = lo[::-1].rolling(horizon, min_periods=horizon).min()[::-1].shift(-1)
    hit = (fut_min <= df["close"] * (1 - down)).astype(float)
    return hit.where(fut_min.notna())


def build_dataset(histories: dict[str, pd.DataFrame], bench: pd.DataFrame | None, step: int = 5) -> pd.DataFrame:
    """One row per (stock, sample date): factors, scores, labels and forward returns."""
    frames = []
    for sym, df in histories.items():
        if len(df) < 300:
            continue
        bull_f, bear_f = md.compute_factors(df, bench)
        scores = md.score_series(df, bench)
        c = df["close"]
        d = pd.concat([bull_f.add_prefix("bull_"), bear_f.add_prefix("bear_"), scores], axis=1)
        d["up_label"] = triple_barrier(df)
        d["down_label"] = down_move(df)
        for k in (5, 10, 20):
            d[f"fwd_{k}"] = (c.shift(-k) / c - 1) * 100
        d["symbol"] = sym
        d = d.iloc[::step].dropna(subset=["bull", "bear", "up_label", "down_label", "fwd_20"])
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).sort_index()


def _bucket_table(data: pd.DataFrame, score: str, label: str, fwd_sign: int) -> list[dict]:
    rows = []
    for lo, hi in BUCKETS:
        s = data[(data[score] >= lo) & (data[score] < hi)]
        if s.empty:
            continue
        rows.append({
            "bucket": f"{lo}–{min(hi, 100)}", "samples": len(s),
            "hit_rate": round(float(s[label].mean()) * 100, 1),
            "avg_fwd_5": round(float(s["fwd_5"].mean()) * fwd_sign, 2),
            "avg_fwd_10": round(float(s["fwd_10"].mean()) * fwd_sign, 2),
            "avg_fwd_20": round(float(s["fwd_20"].mean()) * fwd_sign, 2),
        })
    return rows


def _top_precision(data: pd.DataFrame, score: str, label: str, top: int = 10) -> float | None:
    """Average hit rate of the `top` highest-scored stocks on each sample date."""
    if data.empty:
        return None
    picks = data.groupby(level=0, group_keys=False).apply(lambda g: g.nlargest(min(top, len(g)), score))
    return round(float(picks[label].mean()) * 100, 1)


def validate_move_detector(data: pd.DataFrame) -> dict:
    if data.empty:
        return {"samples": 0}
    base_up = float(data["up_label"].mean()) * 100
    base_dn = float(data["down_label"].mean()) * 100
    top_up = _top_precision(data, "bull", "up_label")
    top_dn = _top_precision(data, "bear", "down_label")
    return {
        "samples": len(data), "stocks": int(data["symbol"].nunique()),
        "start": data.index.min().strftime("%Y-%m-%d"), "end": data.index.max().strftime("%Y-%m-%d"),
        "definition": {"up": f"+{UP:.0%} within {HORIZON} trading days before -{STOP:.0%}", "down": f"-{DOWN:.0%} within {HORIZON} trading days"},
        "bull": {"base_rate": round(base_up, 1), "top10_hit_rate": top_up, "lift": round(top_up / base_up, 2) if base_up and top_up is not None else None,
                 "buckets": _bucket_table(data, "bull", "up_label", 1)},
        "bear": {"base_rate": round(base_dn, 1), "top10_hit_rate": top_dn, "lift": round(top_dn / base_dn, 2) if base_dn and top_dn is not None else None,
                 "buckets": _bucket_table(data, "bear", "down_label", -1)},
    }


# ------------------------------------------------------------------ ML (layer 3)

FEATURES = [f"bull_{k}" for k in md.BULL_WEIGHTS] + [f"bear_{k}" for k in md.BEAR_WEIGHTS]


def walk_forward(data: pd.DataFrame, folds: int = 4, label: str = "up_label", score: str = "bull") -> dict:
    """Train on everything before each test window, test on the window; compare the model with the rule score."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    data = data.dropna(subset=FEATURES + [label])
    dates = np.array(sorted(data.index.unique()))
    if len(dates) < folds + 2 or data[label].nunique() < 2:
        return {"available": False, "reason": "Not enough data for walk-forward testing."}
    edges = np.linspace(len(dates) * 0.4, len(dates), folds + 1).astype(int)
    results, all_test = [], []
    for k in range(folds):
        train_end, test_end = dates[edges[k] - 1], dates[min(edges[k + 1], len(dates)) - 1]
        # leave a gap of HORIZON days so training labels never peek into the test period
        gap_end = train_end - pd.Timedelta(days=int(HORIZON * 1.5))
        train = data[data.index <= gap_end]
        test = data[(data.index > train_end) & (data.index <= test_end)]
        if train[label].nunique() < 2 or test.empty or test[label].nunique() < 2:
            continue
        model = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, l2_regularization=1.0, random_state=0)
        model.fit(train[FEATURES], train[label])
        test = test.assign(ml_prob=model.predict_proba(test[FEATURES])[:, 1])
        all_test.append(test)
        results.append({
            "train_until": pd.Timestamp(gap_end).strftime("%Y-%m-%d"), "test_from": pd.Timestamp(test.index.min()).strftime("%Y-%m-%d"),
            "test_to": pd.Timestamp(test_end).strftime("%Y-%m-%d"), "test_samples": len(test),
            "base_rate": round(float(test[label].mean()) * 100, 1),
            "auc_model": round(float(roc_auc_score(test[label], test["ml_prob"])), 3),
            "auc_rules": round(float(roc_auc_score(test[label], test[score])), 3),
            "top10_model": _top_precision(test, "ml_prob", label),
            "top10_rules": _top_precision(test, score, label),
        })
    if not results:
        return {"available": False, "reason": "Not enough positive examples in the test windows."}
    t = pd.concat(all_test)
    auc_m = float(np.mean([r["auc_model"] for r in results]))
    auc_r = float(np.mean([r["auc_rules"] for r in results]))
    verdict = (
        "No reliable edge yet: the model is close to random on unseen data." if auc_m < 0.55 and auc_r < 0.55
        else "The machine-learning model ranks future movers better than the rule score." if auc_m > auc_r + 0.02
        else "The rule score is as good as or better than the model."
    )
    return {
        "available": True, "label": label, "folds": results,
        "avg_auc_model": round(auc_m, 3), "avg_auc_rules": round(auc_r, 3),
        "base_rate": round(float(t[label].mean()) * 100, 1),
        "top10_model": _top_precision(t, "ml_prob", label), "top10_rules": _top_precision(t, score, label),
        "verdict": verdict,
        "note": "AUC 0.5 = random, 1.0 = perfect. Each fold trains only on data that ends before its test window.",
    }


# ------------------------------------------------------------------ strategy backtest

def strategy_backtest(df: pd.DataFrame, strategy_id: str, params: dict | None = None, bench: pd.DataFrame | None = None,
                      fees_pct: float = 0.05) -> dict:
    """Long-only: enter at the close of a BUY signal, exit at the close of the next SELL signal."""
    res = run_strategy(strategy_id, df, params, bench)
    markers = sorted(res.get("markers", []), key=lambda m: m["time"])
    if not any(m["text"] == "BUY" for m in markers):
        return {"trades": [], "stats": {"trades": 0}, "equity": [], "buy_hold": [], "reason": "This strategy produced no BUY signals."}
    close = df["close"]
    trades, pos = [], None
    for m in markers:
        ts = pd.Timestamp(m["time"])
        if m["text"] == "BUY" and pos is None:
            pos = (ts, float(close.loc[ts]))
        elif m["text"] == "SELL" and pos is not None:
            trades.append((pos[0], pos[1], ts, float(close.loc[ts])))
            pos = None
    if pos is not None:  # mark the open trade to the last close
        trades.append((pos[0], pos[1], close.index[-1], float(close.iloc[-1])))

    equity = pd.Series(1.0, index=df.index)
    in_mkt = pd.Series(False, index=df.index)
    rows = []
    for en_t, en_p, ex_t, ex_p in trades:
        r = ex_p / en_p - 1 - 2 * fees_pct / 100
        rows.append({"entry_date": en_t.strftime("%Y-%m-%d"), "entry": round(en_p, 2), "exit_date": ex_t.strftime("%Y-%m-%d"), "exit": round(ex_p, 2),
                     "return_pct": round(r * 100, 2), "days": int((ex_t - en_t).days), "open": bool(ex_t == close.index[-1] and pos is not None)})
        in_mkt[(df.index > en_t) & (df.index <= ex_t)] = True
    daily = close.pct_change().fillna(0).where(in_mkt, 0.0)
    for en_t, _, ex_t, _ in trades:  # fees on each entry and exit day
        daily.loc[en_t] -= fees_pct / 100
        daily.loc[ex_t] -= fees_pct / 100
    equity = (1 + daily).cumprod()
    bh = close / close.iloc[0]
    years = max((df.index[-1] - df.index[0]).days / 365.25, 1e-9)
    rets = np.array([t["return_pct"] for t in rows])
    dd = (equity / equity.cummax() - 1).min()
    bh_dd = (bh / bh.cummax() - 1).min()
    stats = {
        "trades": len(rows), "win_rate": round(float((rets > 0).mean() * 100), 1),
        "avg_return_pct": round(float(rets.mean()), 2),
        "total_return_pct": round(float(equity.iloc[-1] - 1) * 100, 2), "buy_hold_return_pct": round(float(bh.iloc[-1] - 1) * 100, 2),
        "cagr_pct": round(float(equity.iloc[-1] ** (1 / years) - 1) * 100, 2), "buy_hold_cagr_pct": round(float(bh.iloc[-1] ** (1 / years) - 1) * 100, 2),
        "max_drawdown_pct": round(float(dd) * 100, 2), "buy_hold_max_drawdown_pct": round(float(bh_dd) * 100, 2),
        "time_in_market_pct": round(float(in_mkt.mean() * 100), 1),
        "avg_days": round(float(np.mean([t["days"] for t in rows])), 1),
    }
    pts = lambda s: [{"time": t.strftime("%Y-%m-%d"), "value": round((float(v) - 1) * 100, 2)} for t, v in s.items()]
    return {"trades": rows, "stats": stats, "equity": pts(equity), "buy_hold": pts(bh)}
