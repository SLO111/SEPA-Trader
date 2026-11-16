import hashlib
import hmac
import json
import time

import pytest
import stripe

from app.config import settings
from app.db import SessionLocal
from app.models import User

SECRET = "whsec_test_secret"
PRICES = {"stripe_price_pro_monthly": "price_pro_m", "stripe_price_pro_yearly": "price_pro_y",
          "stripe_price_premium_monthly": "price_prem_m", "stripe_price_premium_yearly": "price_prem_y"}


@pytest.fixture
def stripe_on(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "app_url", "https://app.example.com")
    for k, v in PRICES.items():
        monkeypatch.setattr(settings, k, v)
    calls = {}
    def create_customer(**kw):
        calls["customer"] = kw
        calls["customer_id"] = f"cus_{kw['metadata']['user_id']}"
        return {"id": calls["customer_id"]}

    monkeypatch.setattr(stripe.Customer, "create", create_customer)
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kw: calls.setdefault("checkout", kw) and {"url": "https://checkout.stripe.com/c/abc"})
    monkeypatch.setattr(stripe.billing_portal.Session, "create", lambda **kw: calls.setdefault("portal", kw) and {"url": "https://billing.stripe.com/p/xyz"})
    return calls


def _signed(client, event: dict):
    payload = json.dumps(event)
    ts = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post("/api/billing/webhook", content=payload, headers={"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"})


def _sub_event(eid, kind, status, price="price_pro_m", interval="month", amount=2900, cancel=False, user_id=None, customer="cus_x"):
    return {"id": eid, "type": kind, "data": {"object": {
        "id": "sub_1", "customer": customer, "status": status, "cancel_at_period_end": cancel, "canceled_at": int(time.time()) if status == "canceled" else None,
        "metadata": {"user_id": str(user_id)} if user_id else {},
        "items": {"data": [{"quantity": 1, "current_period_end": int(time.time()) + 30 * 86400,
                            "price": {"id": price, "unit_amount": amount, "currency": "usd", "recurring": {"interval": interval}}}]},
    }}}


def _plan_of(email):
    with SessionLocal() as db:
        return db.query(User).filter_by(email=email).one().plan


def test_billing_disabled_without_keys(client, register):
    h, _ = register("bill-off@test.ro")
    r = client.get("/api/billing/plans", headers=h).json()
    assert r["enabled"] is False and [p["id"] for p in r["plans"]] == ["free", "pro", "premium"]
    assert client.post("/api/billing/checkout", headers=h, json={"plan": "pro"}).status_code == 503


def test_full_subscription_lifecycle(client, register, stripe_on):
    h, user = register("bill-on@test.ro")
    plans = client.get("/api/billing/plans", headers=h).json()
    assert plans["enabled"] and plans["plans"][1]["available"] == {"monthly": True, "yearly": True}

    r = client.post("/api/billing/checkout", headers=h, json={"plan": "pro", "interval": "monthly"})
    assert r.status_code == 200 and r.json()["url"].startswith("https://checkout.stripe.com")
    co = stripe_on["checkout"]
    assert co["mode"] == "subscription" and co["line_items"] == [{"price": "price_pro_m", "quantity": 1}]
    assert co["customer"] == stripe_on["customer_id"] and co["success_url"] == "https://app.example.com/billing?status=success"
    assert stripe_on["customer"]["email"] == "bill-on@test.ro"

    # Stripe confirms the subscription -> user becomes Pro
    assert _signed(client, _sub_event("evt_1", "customer.subscription.created", "active", user_id=user["id"], customer=stripe_on["customer_id"])).status_code == 200
    assert _plan_of("bill-on@test.ro") == "pro"
    sub = client.get("/api/billing/plans", headers=h).json()["subscription"]
    assert sub["status"] == "active" and sub["amount"] == 29 and sub["interval"] == "month"

    # a second checkout is refused while subscribed; the portal is used instead
    assert client.post("/api/billing/checkout", headers=h, json={"plan": "premium"}).status_code == 409
    assert client.post("/api/billing/portal", headers=h).json()["url"].startswith("https://billing.stripe.com")

    # cancel from Settings: no charge next period, access until the period end; then resume
    import stripe as _stripe

    calls = []
    _stripe_modify = _stripe.Subscription.modify
    _stripe.Subscription.modify = lambda sid, **kw: calls.append((sid, kw)) or {"id": sid, "cancel_at_period_end": kw["cancel_at_period_end"]}
    try:
        c = client.post("/api/billing/cancel", headers=h, json={}).json()
        assert c["cancel_at_period_end"] is True and calls[-1][1] == {"cancel_at_period_end": True} and _plan_of("bill-on@test.ro") == "pro"
        assert client.post("/api/billing/cancel", headers=h, json={"resume": True}).json()["cancel_at_period_end"] is False
    finally:
        _stripe.Subscription.modify = _stripe_modify

    # upgrade to Premium yearly in the portal
    _signed(client, _sub_event("evt_2", "customer.subscription.updated", "active", price="price_prem_y", interval="year", amount=59000, customer=stripe_on["customer_id"]))
    assert _plan_of("bill-on@test.ro") == "premium"

    # card fails: past_due keeps access while Stripe retries
    _signed(client, _sub_event("evt_3", "customer.subscription.updated", "past_due", price="price_prem_y", interval="year", amount=59000, customer=stripe_on["customer_id"]))
    assert _plan_of("bill-on@test.ro") == "premium"

    # subscription ends -> back to Free
    _signed(client, _sub_event("evt_4", "customer.subscription.deleted", "canceled", price="price_prem_y", interval="year", amount=59000, customer=stripe_on["customer_id"]))
    assert _plan_of("bill-on@test.ro") == "free"


def test_webhook_security_and_idempotency(client, register, stripe_on):
    _, user = register("bill-sec@test.ro")
    ev = _sub_event("evt_dup", "customer.subscription.created", "active", user_id=user["id"], customer="cus_sec")
    # wrong signature is rejected
    bad = client.post("/api/billing/webhook", content=json.dumps(ev), headers={"stripe-signature": f"t={int(time.time())},v1=deadbeef"})
    assert bad.status_code == 400
    assert _signed(client, ev).json() == {"received": True}
    assert _plan_of("bill-sec@test.ro") == "pro"  # linked through metadata.user_id
    assert _signed(client, ev).json()["duplicate"] is True  # Stripe retry is ignored


def test_admin_revenue_stats(client, register, stripe_on):
    h, user = register("bill-admin@test.ro")
    with SessionLocal() as db:
        u = db.query(User).filter_by(email="bill-admin@test.ro").one()
        u.role = "admin"
        db.commit()
    other_h, other = register("bill-payer@test.ro")
    client.post("/api/billing/checkout", headers=other_h, json={"plan": "premium", "interval": "yearly"})
    cus = stripe_on["customer_id"]
    _signed(client, _sub_event("evt_a1", "customer.subscription.created", "active", price="price_prem_y", interval="year", amount=59000, user_id=other["id"], customer=cus))
    _signed(client, {"id": "evt_a2", "type": "invoice.paid", "data": {"object": {"id": "in_1", "customer": cus, "amount_paid": 59000, "currency": "usd", "created": int(time.time())}}})
    _signed(client, {"id": "evt_a3", "type": "invoice.payment_failed", "data": {"object": {"id": "in_2", "customer": cus, "amount_due": 59000, "currency": "usd", "created": int(time.time())}}})
    st = client.get("/api/admin/stats", headers=h).json()
    assert st["mrr"] >= 49.16 and st["active_subscriptions"] >= 1  # 590 / 12
    assert st["revenue_30d"] >= 590 and st["failed_payments_30d"] >= 1
    assert any(p["email"] == "bill-payer@test.ro" and p["status"] == "paid" for p in st["recent_payments"])
