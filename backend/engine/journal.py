"""Trading journal analytics: per-trade metrics and performance statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass
class Trade:
    id: int
    symbol: str
    side: str  # long | short
    entry_date: date
    entry_price: float
    shares: float
    stop_price: float | None = None
    target_price: float | None = None
    exit_date: date | None = None
    exit_price: float | None = None
    fees: float = 0.0
    setup: str = ""

    @property
    def closed(self) -> bool:
        return self.exit_price is not None and self.exit_date is not None


def trade_metrics(t: Trade, last_price: float | None = None) -> dict:
    """P/L, return, R-multiple and holding period. Open trades use `last_price` (unrealized)."""
    sign = 1 if t.side == "long" else -1
    price = t.exit_price if t.closed else last_price
    risk_per_share = abs(t.entry_price - t.stop_price) if t.stop_price else None
    out = {
        "risk_pct": round(risk_per_share / t.entry_price * 100, 2) if risk_per_share else None,
        "risk_amount": round(risk_per_share * t.shares, 2) if risk_per_share else None,
        "reward_risk": round(abs(t.target_price - t.entry_price) / risk_per_share, 2) if risk_per_share and t.target_price else None,
        "pnl": None, "return_pct": None, "r_multiple": None, "hold_days": None, "status": "closed" if t.closed else "open",
    }
    if price is None:
        return out
    gross = sign * (price - t.entry_price) * t.shares
    out["pnl"] = round(gross - t.fees, 2)
    out["return_pct"] = round(sign * (price / t.entry_price - 1) * 100, 2)
    if risk_per_share:
        out["r_multiple"] = round(sign * (price - t.entry_price) / risk_per_share, 2)
    end = t.exit_date if t.closed else date.today()
    out["hold_days"] = (end - t.entry_date).days
    return out


def _streaks(wins: list[bool]) -> tuple[int, int]:
    best_w = best_l = cur = 0
    last = None
    for w in wins:
        cur = cur + 1 if w == last else 1
        last = w
        if w:
            best_w = max(best_w, cur)
        else:
            best_l = max(best_l, cur)
    return best_w, best_l


def statistics(trades: list[Trade]) -> dict:
    closed = sorted([t for t in trades if t.closed], key=lambda t: (t.exit_date, t.id))
    if not closed:
        return {"closed_trades": 0, "open_trades": sum(not t.closed for t in trades)}
    m = [trade_metrics(t) for t in closed]
    pnl = np.array([x["pnl"] for x in m])
    ret = np.array([x["return_pct"] for x in m])
    wins = pnl > 0
    win_ret, loss_ret = ret[wins], ret[~wins]
    rs = np.array([x["r_multiple"] for x in m if x["r_multiple"] is not None])
    gross_win, gross_loss = pnl[wins].sum(), -pnl[~wins].sum()
    hold = np.array([x["hold_days"] for x in m])
    win_rate = wins.mean()
    avg_win = float(win_ret.mean()) if len(win_ret) else 0.0
    avg_loss = float(loss_ret.mean()) if len(loss_ret) else 0.0

    equity = pd.Series(pnl, index=pd.DatetimeIndex([t.exit_date for t in closed])).groupby(level=0).sum().cumsum()
    peak = equity.cummax().clip(lower=0)  # the account starts at 0 P/L, so an early loss is a drawdown
    dd = (equity - peak).clip(upper=0)
    monthly = pd.Series(pnl, index=pd.DatetimeIndex([t.exit_date for t in closed])).resample("ME").sum()
    best_w, best_l = _streaks(list(wins))

    by_setup: dict[str, dict] = {}
    for t, x in zip(closed, m):
        k = t.setup or "Unlabeled"
        b = by_setup.setdefault(k, {"setup": k, "trades": 0, "wins": 0, "pnl": 0.0, "r": []})
        b["trades"] += 1
        b["wins"] += x["pnl"] > 0
        b["pnl"] += x["pnl"]
        if x["r_multiple"] is not None:
            b["r"].append(x["r_multiple"])
    setups = [{"setup": b["setup"], "trades": b["trades"], "win_rate": round(b["wins"] / b["trades"] * 100, 1), "pnl": round(b["pnl"], 2),
               "avg_r": round(float(np.mean(b["r"])), 2) if b["r"] else None} for b in by_setup.values()]

    return {
        "closed_trades": len(closed),
        "open_trades": sum(not t.closed for t in trades),
        "wins": int(wins.sum()), "losses": int((~wins).sum()),
        "win_rate": round(float(win_rate) * 100, 1),
        "avg_win_pct": round(avg_win, 2), "avg_loss_pct": round(avg_loss, 2),
        "win_loss_ratio": round(avg_win / abs(avg_loss), 2) if avg_loss else None,
        # Expectancy: what you make on average per trade, in % and in R.
        "expectancy_pct": round(float(win_rate * avg_win + (1 - win_rate) * avg_loss), 2),
        "expectancy_r": round(float(rs.mean()), 2) if len(rs) else None,
        "expectancy_usd": round(float(pnl.mean()), 2),
        "profit_factor": round(float(gross_win / gross_loss), 2) if gross_loss > 0 else None,
        "total_pnl": round(float(pnl.sum()), 2),
        "largest_win": round(float(pnl.max()), 2), "largest_loss": round(float(pnl.min()), 2),
        "avg_hold_win": round(float(hold[wins].mean()), 1) if wins.any() else None,
        "avg_hold_loss": round(float(hold[~wins].mean()), 1) if (~wins).any() else None,
        "max_win_streak": best_w, "max_loss_streak": best_l,
        "max_drawdown": round(float(dd.min()), 2),
        "r_std": round(float(rs.std()), 2) if len(rs) > 1 else None,
        "profitable_months_pct": round(float((monthly > 0).mean() * 100), 1) if len(monthly) else None,
        "equity_curve": [{"time": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)} for d, v in equity.items()],
        "monthly": [{"month": d.strftime("%Y-%m"), "pnl": round(float(v), 2)} for d, v in monthly.items()],
        "r_distribution": [round(float(x), 2) for x in rs],
        "by_setup": sorted(setups, key=lambda s: -s["trades"]),
    }
