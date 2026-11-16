"""Track record, weekly letter, academy, shared watchlists, leaderboard, simulated copy trading (Phase D)."""

import json
from datetime import date, timedelta

from app.db import SessionLocal
from app.models import PaperTrade, TradeIdea, User


def _plan(email, plan):
    with SessionLocal() as db:
        db.query(User).filter_by(email=email).one().plan = plan
        db.commit()


def _uid(email):
    with SessionLocal() as db:
        return db.query(User).filter_by(email=email).one().id


def test_public_track_record(client):
    from app import market_data
    from app.routers.community import track_record

    with SessionLocal() as db:
        d0 = date(2026, 1, 5)
        for i, (st, r) in enumerate([("TARGET", 3.0), ("STOPPED", -1.0), ("TARGET", 2.0), ("WAIT", None)]):
            db.add(TradeIdea(batch_date=d0, symbol=f"TR{i}", timeframe="SWING", side="long", entry=10, stop=9, target=13, rr=3, weight=5,
                             score=1, status=st, r_multiple=r, closed_at=d0 + timedelta(days=10 + i) if r is not None else None))
        db.commit()
        try:
            tr = track_record(db)
            assert tr["all"]["trades"] >= 3 and tr["equity"] and tr["by_month"]
            market_data._fast_cache.pop("public:track-record", None)
            r = client.get("/api/public/track-record")  # no login needed
            assert r.status_code == 200 and r.json()["all"]["trades"] >= 3
        finally:  # the fake ideas must not leak into other tests
            db.query(TradeIdea).filter(TradeIdea.symbol.like("TR%")).delete(synchronize_session=False)
            db.commit()
            market_data._fast_cache.pop("public:track-record", None)


def test_weekly_letter_gated(client, register):
    from app.ideas_service import publish_weekly_letter

    with SessionLocal() as db:
        item = publish_weekly_letter(db, today=date(2026, 11, 14))  # a Saturday
        assert item and item["kind"] == "letter" and json.loads(item["body"])["paragraphs"]
        assert publish_weekly_letter(db, today=date(2026, 11, 15)) is None  # once per week
        assert publish_weekly_letter(db, today=date(2026, 11, 18)) is None  # weekdays: no letter
    h, _ = register("letter@test.ro")
    free = client.get("/api/feed/letter", headers=h).json()
    assert free["locked"] and len(free["paragraphs"]) == 1
    _plan("letter@test.ro", "premium")
    full = client.get("/api/feed/letter", headers=h).json()
    assert not full.get("locked") and len(full["paragraphs"]) > 1
    assert all(x["kind"] != "letter" for x in client.get("/api/feed", headers=h).json())


def test_academy_progress(client, register):
    h, _ = register("academy@test.ro")
    assert client.post("/api/academy/progress/vcp", headers=h).json()["done"] == ["vcp"]
    assert client.post("/api/academy/progress/nope", headers=h).status_code == 404


def test_shared_watchlist(client, register):
    h, _ = register("share@test.ro")
    wl = client.get("/api/watchlists", headers=h).json()[0]
    slug = client.post(f"/api/watchlists/{wl['id']}/share", headers=h).json()["slug"]
    pub = client.get(f"/api/public/watchlists/{slug}")
    assert pub.status_code == 200 and pub.json()["symbols"] and pub.json()["name"] == wl["name"]
    h2, _ = register("share2@test.ro")
    assert client.post(f"/api/public/watchlists/{slug}/copy", headers=h2).status_code == 403  # Free: 1 watchlist
    _plan("share2@test.ro", "pro")
    c = client.post(f"/api/public/watchlists/{slug}/copy", headers=h2).json()
    assert c["name"].endswith("(copy)")
    client.delete(f"/api/watchlists/{wl['id']}/share", headers=h)
    assert client.get(f"/api/public/watchlists/{slug}").status_code == 404


def test_copy_trading_and_leaderboard(client, register):
    from app import market_data

    lh, _ = register("leader@test.ro")
    fh, _ = register("follower@test.ro")
    lid = _uid("leader@test.ro")
    assert client.post(f"/api/community/follow/{lid}", headers=fh).status_code == 404  # no public profile yet
    assert client.put("/api/community/profile", headers=lh, json={"display_name": "Top Trader", "public": True, "allow_copy": True}).status_code == 200
    assert client.put("/api/community/profile", headers=fh, json={"display_name": "top trader"}).status_code == 409  # names are unique
    r = client.post(f"/api/community/follow/{lid}", headers=fh).json()
    assert r["following"][0]["display_name"] == "Top Trader"
    client.post("/api/paper-trades/chart", headers=lh, json={"symbol": "AAPL", "side": "long"})
    copies = client.get("/api/paper-trades?source=copy", headers=fh).json()["trades"]
    assert len(copies) == 1 and copies[0]["symbol"] == "AAPL"
    client.post("/api/paper-trades/chart/sell", headers=lh, json={"symbol": "AAPL"})
    copies = client.get("/api/paper-trades?source=copy", headers=fh).json()["trades"]
    assert copies[0]["open"] is False  # closed together with the leader
    # leaderboard: 5 closed trades minimum
    with SessionLocal() as db:
        d = market_data.history("MSFT").index[-30].date()
        for _ in range(5):
            db.add(PaperTrade(user_id=lid, symbol="MSFT", timeframe="CH", side="long", entry_date=d, entry=100, stop=1, target=100000,
                              weight=1, exit_date=d + timedelta(days=7), exit_price=110))
        db.commit()
    market_data._fast_cache.pop("public:leaderboard:all", None)
    rows = client.get("/api/public/leaderboard?period=all").json()["rows"]
    assert rows and rows[0]["display_name"] == "Top Trader" and rows[0]["followers"] == 1
    client.delete(f"/api/community/follow/{lid}", headers=fh)
    assert client.get("/api/community/profile", headers=fh).json()["following"] == []
