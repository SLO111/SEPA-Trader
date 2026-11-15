from app.config import settings
from app.db import SessionLocal
from app.models import User
from engine.data.providers import SyntheticProvider


def _set_plan(email: str, plan: str):
    with SessionLocal() as db:
        u = db.query(User).filter_by(email=email).one()
        u.plan = plan
        db.commit()


def _crossing_rule(symbol: str) -> dict:
    """A price rule guaranteed to fire on the latest synthetic bar."""
    c = SyntheticProvider().history(symbol)["close"]
    last, prev = float(c.iloc[-1]), float(c.iloc[-2])
    level = round((last + prev) / 2, 4)
    event = "price_above" if last > prev else "price_below"
    return {"name": f"{symbol} level", "scope": "symbol", "symbol": symbol, "events": [event], "price_level": level}


def test_free_plan_cannot_create_rules(client, register):
    h, _ = register("alerts-free@test.ro")
    assert client.post("/api/alert-rules", headers=h, json=_crossing_rule("AAPL")).status_code == 403
    assert client.post("/api/alerts/check-now", headers=h).status_code == 403
    assert client.get("/api/alerts", headers=h).json() == []


def test_rule_check_dedupe_and_read(client, register):
    h, _ = register("alerts-pro@test.ro")
    _set_plan("alerts-pro@test.ro", "pro")
    r = client.post("/api/alert-rules", headers=h, json=_crossing_rule("MSFT"))
    assert r.status_code == 200, r.text
    first = client.post("/api/alerts/check-now", headers=h).json()
    assert first["created"] == 1 and first["alerts"][0]["symbol"] == "MSFT"
    assert client.post("/api/alerts/check-now", headers=h).json()["created"] == 0  # deduplicated
    assert client.get("/api/alerts/unread-count", headers=h).json()["count"] == 1
    assert client.get("/api/alerts?filter=unread", headers=h).json()[0]["type"].startswith("price_")
    client.post("/api/alerts/read-all", headers=h)
    assert client.get("/api/alerts/unread-count", headers=h).json()["count"] == 0


def test_rule_validation_and_isolation(client, register):
    h1, _ = register("alerts-a@test.ro")
    h2, _ = register("alerts-b@test.ro")
    _set_plan("alerts-a@test.ro", "pro")
    _set_plan("alerts-b@test.ro", "pro")
    # price events need a level
    bad = {"name": "x", "scope": "symbol", "symbol": "AAPL", "events": ["price_above"]}
    assert client.post("/api/alert-rules", headers=h1, json=bad).status_code == 422
    # unknown event
    assert client.post("/api/alert-rules", headers=h1, json={**bad, "events": ["moon"], "price_level": 1}).status_code == 422
    # someone else's watchlist
    other_wl = client.get("/api/watchlists", headers=h2).json()[0]["id"]
    wl_rule = {"name": "wl", "scope": "watchlist", "watchlist_id": other_wl, "events": ["breakout"]}
    assert client.post("/api/alert-rules", headers=h1, json=wl_rule).status_code == 404
    # own watchlist + universe scope are fine on Pro
    own_wl = client.get("/api/watchlists", headers=h1).json()[0]["id"]
    assert client.post("/api/alert-rules", headers=h1, json={**wl_rule, "watchlist_id": own_wl}).status_code == 200
    uni = client.post("/api/alert-rules", headers=h1, json={"name": "All", "scope": "universe", "events": ["bull_score"], "channels": ["telegram"]})
    assert uni.status_code == 200 and uni.json()["channels"] == ["app", "telegram"]
    # user B cannot delete user A's rule
    assert client.delete(f"/api/alert-rules/{uni.json()['id']}", headers=h2).status_code == 404


def test_notification_settings(client, register):
    h, _ = register("alerts-notify@test.ro")
    s = client.get("/api/notifications/settings", headers=h).json()
    assert s["email_enabled"] is False and s["telegram_available"] is False
    r = client.put("/api/notifications/settings", headers=h, json={"email_enabled": True, "telegram_enabled": True, "telegram_chat_id": "12345"})
    assert r.json()["telegram_chat_id"] == "12345"
    assert client.put("/api/notifications/settings", headers=h, json={"telegram_chat_id": "abc"}).status_code == 422
    # not configured on the server -> nothing is sent, no crash
    assert client.post("/api/notifications/test", headers=h).json() == {"email": False, "telegram": False}


def test_admin_email_promoted_on_login(client, register, monkeypatch):
    h, user = register("late-admin@test.ro")
    assert user["role"] == "user"
    monkeypatch.setattr(settings, "admin_email", "late-admin@test.ro")
    assert client.get("/api/auth/me", headers=h).json()["role"] == "admin"
