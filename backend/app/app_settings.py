"""App-wide settings the admin can change at runtime (stored in the app_settings table)."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from .models import AppSetting

# How much news the feed collects. Fewer headlines = less work for the server (fetching, tagging, storing).
NEWS_LEVELS: dict[str, dict] = {
    "off": {"label": "Off", "every_min": 0, "per_pass": 0, "company": 0, "finnhub": False, "keep_days": 3,
            "help": "No headlines in the feed (earnings, movers, breakouts and ideas still appear)."},
    "low": {"label": "Low", "every_min": 60, "per_pass": 15, "company": 0, "finnhub": False, "keep_days": 3,
            "help": "Up to 15 new headlines an hour from the main publishers."},
    "medium": {"label": "Medium", "every_min": 30, "per_pass": 40, "company": 5, "finnhub": True, "keep_days": 5,
               "help": "Up to 40 new headlines every 30 minutes, plus market-wide and some company news."},
    "high": {"label": "High", "every_min": 10, "per_pass": 100, "company": 20, "finnhub": True, "keep_days": 7,
             "help": "Up to 100 new headlines every 10 minutes, with company news for 20 stocks per pass. Heaviest."},
}
DEFAULTS = {"news_level": "medium"}


def get(db: Session, key: str):
    row = db.get(AppSetting, key)
    if row is None:
        return DEFAULTS.get(key)
    try:
        return json.loads(row.value)
    except ValueError:
        return DEFAULTS.get(key)


def put(db: Session, key: str, value) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=json.dumps(value)))
    else:
        row.value = json.dumps(value)
    db.commit()


def news_config(db: Session) -> tuple[str, dict]:
    level = get(db, "news_level")
    if level not in NEWS_LEVELS:
        level = DEFAULTS["news_level"]
    return level, NEWS_LEVELS[level]
