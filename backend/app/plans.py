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
    },
    "pro": {
        "label": "Pro",
        "max_watchlists": 25,
        "max_symbols_per_watchlist": 200,
        "max_strategies_on_chart": 15,
        "max_portfolios": 10,
        "realtime_data": True,
        "data_delay_minutes": 0,
        "alerts": True,
        "max_alert_rules": 50,
        "reports": False,
        "move_detector": True,
        "backtesting": False,
        "trade_review": False,
        "max_journal_trades": UNLIMITED,
        "pulse": True,
        "sepa_details": True,
        "ask_ai": True,
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
    },
}


# List prices shown in the app (USD). The amount actually charged is the Stripe price configured for each plan.
PRICES = {
    "pro": {"monthly": 29, "yearly": 290},
    "premium": {"monthly": 59, "yearly": 590},
}


def limits_for(user) -> dict:
    # Everyone, administrators included, gets the limits of their own plan: an admin can switch their plan in the
    # Admin panel to test exactly what Free / Pro / Premium users see. Admin access depends only on the role.
    return PLANS.get(user.plan, PLANS["free"])


# Trend Template criteria a free user sees: the ones anyone can read off the chart (price vs. the moving averages).
FREE_TEMPLATE_CRITERIA = {0, 3, 4}


def gate_sepa(rep: dict, limits: dict) -> dict:
    """Free plan: Trend Template score + the chart-readable criteria; the other criteria and the VCP are locked."""
    if limits.get("sepa_details"):
        return rep
    tt = rep.get("trend_template") or {}
    crit = [c if i in FREE_TEMPLATE_CRITERIA else {"label": c["label"], "passed": None, "locked": True} for i, c in enumerate(tt.get("criteria", []))]
    return {**rep, "trend_template": {**tt, "criteria": crit, "locked": True}, "vcp": {"locked": True, "detected": None, "contractions": []}}
