"""Trials, referrals, monthly quotas and terms (Phase A)."""

from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import PlanTrial, Referral, User


def _plan(email, plan):
    with SessionLocal() as db:
        db.query(User).filter_by(email=email).one().plan = plan
        db.commit()


def test_signup_trial_gives_premium_then_expires(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "trial_days", 14)
    r = client.post("/api/auth/register", json={"email": "trial@test.ro", "password": "parola123", "accept_terms": True}).json()
    u = r["user"]
    assert u["plan"] == "free" and u["effective_plan"] == "premium" and u["trial_until"]
    assert u["limits"]["ai_picks"] and u["limits"]["ideas_limit"] == 50
    h = {"Authorization": f"Bearer {r['token']}"}
    me = client.get("/api/auth/me", headers=h).json()
    assert me["terms_accepted"] is True
    with SessionLocal() as db:
        uid = db.query(User).filter_by(email="trial@test.ro").one().id
        db.get(PlanTrial, uid).ends_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    me = client.get("/api/auth/me", headers=h).json()
    assert me["effective_plan"] == "free" and me["trial_until"] is None and not me["limits"]["move_detector"]


def test_referral_bonus_and_reward(client, register, monkeypatch):
    from app import growth_service
    from app.config import settings

    h, _ = register("inviter@test.ro")  # trial off for the inviter: the reward is the only Premium time
    monkeypatch.setattr(settings, "trial_days", 14)
    code = client.get("/api/auth/referral", headers=h).json()["code"]
    r = client.post("/api/auth/register", json={"email": "invited@test.ro", "password": "parola123", "ref": code.lower()}).json()
    end = datetime.fromisoformat(r["user"]["trial_until"])
    assert end - datetime.now(timezone.utc) > timedelta(days=20)  # 14 + 7 bonus days
    with SessionLocal() as db:
        invited = db.query(User).filter_by(email="invited@test.ro").one()
        assert db.get(Referral, invited.id).owner_id == db.query(User).filter_by(email="inviter@test.ro").one().id
        growth_service.on_paid(db, invited)
        growth_service.on_paid(db, invited)  # rewarded once
        db.commit()
    stats = client.get("/api/auth/referral", headers=h).json()
    assert stats["invited"] == 1 and stats["rewarded"] == 1
    me = client.get("/api/auth/me", headers=h).json()
    left = datetime.fromisoformat(me["trial_until"]) - datetime.now(timezone.utc)
    assert timedelta(days=29) < left <= timedelta(days=30) and me["effective_plan"] == "premium"


def test_ask_ai_monthly_quota(client, register):
    from app.plans import PLANS

    h, _ = register("quota@test.ro")
    _plan("quota@test.ro", "pro")
    n = PLANS["pro"]["ask_ai_monthly"]
    last = None
    for _ in range(n):
        last = client.get("/api/market/analysis/AAPL", headers=h)
    assert last.status_code == 200 and last.json()["quota_left"] == 0
    over = client.get("/api/market/analysis/AAPL", headers=h)
    assert over.status_code == 429 and "Premium is unlimited" in over.json()["detail"]
    _plan("quota@test.ro", "premium")
    ok = client.get("/api/market/analysis/AAPL", headers=h)
    assert ok.status_code == 200 and ok.json()["quota_left"] is None


def test_plan_matrix_and_prices():
    from app.plans import CURRENCY, PLANS, PRICES

    assert CURRENCY == "EUR" and PRICES["pro"]["monthly"] < PRICES["premium"]["monthly"]
    pro, prem = PLANS["pro"], PLANS["premium"]
    for k in ("ai_picks", "industry_groups", "weekly_letter", "custom_backtest", "csv_export", "instant_alerts", "ideas_shorts"):
        assert not pro[k] and prem[k], k
    assert pro["ask_ai_monthly"] < prem["ask_ai_monthly"] and pro["ideas_limit"] < prem["ideas_limit"]
    assert set(PLANS["free"]) == set(pro) == set(prem)  # every plan defines every flag


def test_billing_plans_show_trial_and_currency(client, register):
    h, _ = register("billing-eur@test.ro")
    r = client.get("/api/billing/plans", headers=h).json()
    assert r["currency"] == "EUR" and r["effective_plan"] == "free" and r["trial_until"] is None
