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
    },
}


def limits_for(user) -> dict:
    # Administrators get full access regardless of plan.
    if user.role == "admin":
        return PLANS["premium"]
    return PLANS.get(user.plan, PLANS["free"])
