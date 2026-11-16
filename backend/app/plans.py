"""Subscription plan limits (feature flags). Single source of truth."""

UNLIMITED = 10**9

PLANS: dict[str, dict] = {
    "free": {
        "label": "Free",
        "max_watchlists": 1,
        "max_symbols_per_watchlist": 10,
        "max_strategies_on_chart": 3,
        "max_portfolios": 1,
        "realtime_data": False,
        "data_delay_minutes": 15,
        "alerts": False,
        "max_alert_rules": 0,
        "reports": False,
        "move_detector": False,
        "backtesting": False,
        "trade_review": False,
        "max_journal_trades": 20,
        # paid features: flip these to open or close the paywall
        "pulse": False,  # vnicorn Pulse: daily confirmations / warnings
        "sepa_details": False,  # full Trend Template criteria + VCP (free sees the score and the chart-readable criteria)
        "ask_ai": False,  # Ask vnicornAI chart analysis
        "ask_ai_monthly": 0,
        "ideas_limit": 0,  # trade ideas per day
        "ideas_shorts": False,
        "ai_picks": False,  # vnicornAI picks and major-move probabilities
        "instant_alerts": False,  # Telegram
        "industry_groups": False,
        "weekly_letter": False,
        "custom_backtest": False,
        "csv_export": False,
        "eps_history": False,  # quarterly EPS / sales acceleration table
        "exposure_details": False,  # market exposure % and reasons (free sees the label)
        "max_copy_follows": 1,  # traders you can copy (simulated)
    },
    "pro": {
        "label": "Pro",
        "max_watchlists": 25,
        "max_symbols_per_watchlist": 200,
        "max_strategies_on_chart": 15,
        "max_portfolios": 5,
        "realtime_data": False,
        "data_delay_minutes": 15,
        "alerts": True,
        "max_alert_rules": 50,
        "reports": False,
        "move_detector": True,
        "backtesting": True,
        "trade_review": False,
        "max_journal_trades": UNLIMITED,
        "pulse": True,
        "sepa_details": True,
        "ask_ai": True,
        "ask_ai_monthly": 20,
        "ideas_limit": 10,
        "ideas_shorts": False,
        "ai_picks": False,
        "instant_alerts": False,
        "industry_groups": False,
        "weekly_letter": False,
        "custom_backtest": False,
        "csv_export": False,
        "eps_history": True,
        "exposure_details": True,
        "max_copy_follows": 5,
    },
    "premium": {
        "label": "Premium",
        "max_watchlists": UNLIMITED,
        "max_symbols_per_watchlist": UNLIMITED,
        "max_strategies_on_chart": UNLIMITED,
        "max_portfolios": UNLIMITED,
        "realtime_data": True,
        "data_delay_minutes": 0,
        "alerts": True,
        "max_alert_rules": UNLIMITED,
        "reports": True,
        "move_detector": True,
        "backtesting": True,
        "trade_review": True,
        "max_journal_trades": UNLIMITED,
        "pulse": True,
        "sepa_details": True,
        "ask_ai": True,
        "ask_ai_monthly": UNLIMITED,
        "ideas_limit": 50,
        "ideas_shorts": True,
        "ai_picks": True,
        "instant_alerts": True,
        "industry_groups": True,
        "weekly_letter": True,
        "custom_backtest": True,
        "csv_export": True,
        "eps_history": True,
        "exposure_details": True,
        "max_copy_follows": UNLIMITED,
    },
}


# List prices shown in the app (USD). The amount actually charged is the Stripe price configured for each plan.
CURRENCY = "EUR"
PRICES = {
    "pro": {"monthly": 19, "yearly": 190},
    "premium": {"monthly": 49, "yearly": 490},
}


def trial_until(user):
    """End of an active Premium trial (only for accounts on Free), else None."""
    from datetime import datetime, timezone

    t = getattr(user, "trial", None)
    if not t or user.plan != "free":
        return None
    end = t.ends_at if t.ends_at.tzinfo else t.ends_at.replace(tzinfo=timezone.utc)
    return end if end > datetime.now(timezone.utc) else None


def effective_plan(user) -> str:
    return "premium" if trial_until(user) else (user.plan if user.plan in PLANS else "free")


def limits_for(user) -> dict:
    # Everyone, administrators included, gets the limits of their own plan: an admin can switch their plan in the
    # Admin panel to test exactly what Free / Pro / Premium users see. Admin access depends only on the role.
    # A Free account with an active trial gets Premium.
    return PLANS[effective_plan(user)]


# Trend Template criteria a free user sees: the ones anyone can read off the chart (price vs. the moving averages).
FREE_TEMPLATE_CRITERIA = {0, 3, 4}


def gate_sepa(rep: dict, limits: dict) -> dict:
    """Free plan: only the chart-readable Trend Template criteria (scored out of those); the others and the VCP stay hidden."""
    if limits.get("sepa_details"):
        tt = rep.get("trend_template")
        return {**rep, "trend_template": {**tt, "total": len(tt.get("criteria", []))}} if tt else rep
    tt = rep.get("trend_template") or {}
    crit = [c for i, c in enumerate(tt.get("criteria", [])) if i in FREE_TEMPLATE_CRITERIA]
    passed = sum(bool(c.get("passed")) for c in crit)
    return {**rep, "trend_template": {"criteria": crit, "passed_count": passed, "total": len(crit), "all_passed": passed == len(crit),
                                      "locked": True}, "vcp": {"locked": True, "detected": None, "contractions": []}}


def gate_rows(rows: list[dict], limits: dict) -> list[dict]:
    """Scan-derived rows (leaders, symbol info): on Free the Trend Template count covers only the chart-readable criteria."""
    if limits.get("sepa_details"):
        return [{**r, "template_total": 8} for r in rows]
    return [{**r, "template_passed": r.get("template_free"), "template_total": len(FREE_TEMPLATE_CRITERIA), "vcp": None} for r in rows]
