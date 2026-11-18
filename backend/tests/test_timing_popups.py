from app.routers.ideas import popup_worthy
from engine.ideas import timing

LONG = {"side": "long", "entry": 100.0, "stop": 90.0, "target": 130.0, "rr": 3.0}
SHORT = {"side": "short", "entry": 100.0, "stop": 110.0, "target": 70.0, "rr": 3.0}


def label(idea, price, status, days=0):
    t = timing(idea, price, status, days)
    return t and t["label"]


def test_waiting_and_entry_zone():
    assert label(LONG, 95.0, "WAIT") == "Waiting · 5.0% to entry"
    assert label(LONG, 99.5, "WAIT") == "On time · entry zone"
    assert label(SHORT, 105.0, "WAIT") == "Waiting · 5.0% to entry"


def test_on_time_late_and_expiring():
    assert label(LONG, 101.0, "BUY") == "On time"
    assert label(LONG, 108.0, "BUY").startswith("Late entry · R/R now 1.2")
    assert label(LONG, 95.0, "WAIT", days=9) == "Expires in 1 day"
    assert label(LONG, 95.0, "WAIT", days=10) == "Expires today"


def test_near_stop_and_target_take_priority():
    assert label(LONG, 91.5, "BUY") == "Near stop"
    assert label(LONG, 91.5, "WAIT", days=9) == "Near stop"
    assert label(LONG, 128.0, "BUY") == "Near target"
    assert label(SHORT, 72.0, "BUY") == "Near target"
    assert timing(LONG, 120.0, "TARGET", 3) is None


def test_popup_filter():
    mine = {"NVDA"}
    assert popup_worthy("breakout", "NVDA", "NVDA breaks out", "important", mine)
    assert not popup_worthy("breakout", "XYZ", "XYZ breaks out", "important", mine)
    assert popup_worthy("news", "XYZ", "XYZ gets FDA approval", "important", mine)
    assert popup_worthy("summary", None, "Daily summary", "important", mine)
    assert not popup_worthy("summary", None, "Daily summary", "watchlist", mine)
    assert popup_worthy("mover", "XYZ", "XYZ +12%", "all", mine)
    assert not popup_worthy("breakout", "NVDA", "NVDA breaks out", "off", mine)


def test_popups_endpoint(client, register):
    h, _ = register("popups@test.ro")
    first = client.get("/api/notifications/popups", headers=h).json()
    assert first["feed"] == [] and first["alerts"] == [] and "feed_last" in first
    r = client.get(f"/api/notifications/popups?feed_after=0&alert_after=0", headers=h).json()
    assert isinstance(r["feed"], list) and len(r["feed"]) <= 20
    client.put("/api/auth/prefs", headers=h, json={"popup_feed": "off", "popup_alerts": False})
    r = client.get(f"/api/notifications/popups?feed_after=0&alert_after=0", headers=h).json()
    assert r["feed"] == [] and r["alerts"] == []
