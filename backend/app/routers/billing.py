"""Subscriptions with Stripe: Checkout for new subscriptions, the Customer Portal for changes and cancellations,
and webhooks to keep each user's plan in sync with Stripe (the source of truth for payments)."""

import logging
from datetime import datetime, timezone
from typing import Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Payment, Subscription, User, WebhookEvent
from ..plans import CURRENCY, PLANS, PRICES, effective_plan, trial_until
from ..security import current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])
log = logging.getLogger("sepa.billing")

ACTIVE = {"active", "trialing", "past_due"}  # past_due keeps access while Stripe retries the card


def configured() -> bool:
    return bool(settings.stripe_secret_key)


def _client() -> None:
    if not configured():
        raise HTTPException(503, "Online payments are not set up yet.")
    stripe.api_key = settings.stripe_secret_key


def price_ids() -> dict[tuple[str, str], str]:
    return {
        ("pro", "monthly"): settings.stripe_price_pro_monthly,
        ("pro", "yearly"): settings.stripe_price_pro_yearly,
        ("premium", "monthly"): settings.stripe_price_premium_monthly,
        ("premium", "yearly"): settings.stripe_price_premium_yearly,
    }


def plan_for_price(price_id: str) -> str | None:
    for (plan, _), pid in price_ids().items():
        if pid and pid == price_id:
            return plan
    return None


def _plain(obj) -> dict:
    """Stripe SDK objects are not plain dicts (no .get); convert them recursively."""
    return obj.to_dict() if hasattr(obj, "to_dict") else obj


def _ts(v) -> datetime | None:
    return datetime.fromtimestamp(int(v), tz=timezone.utc) if v else None


def sub_out(s: Subscription | None) -> dict:
    if s is None or s.status == "none":
        return {"status": "none", "plan": "free"}
    return {
        "status": s.status, "plan": s.plan, "interval": s.interval, "amount": s.amount_cents / 100, "currency": s.currency,
        "current_period_end": s.current_period_end.isoformat() if s.current_period_end else None,
        "cancel_at_period_end": s.cancel_at_period_end,
    }


# ------------------------------------------------------------------ user endpoints

@router.get("/plans")
def plans(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = price_ids()
    return {
        "enabled": configured(),
        "current_plan": user.plan,
        "effective_plan": effective_plan(user),
        "trial_until": t.isoformat() if (t := trial_until(user)) else None,
        "currency": CURRENCY,
        "subscription": sub_out(db.get(Subscription, user.id)),
        "plans": [
            {"id": k, "label": PLANS[k]["label"], "prices": PRICES.get(k, {"monthly": 0, "yearly": 0}),
             "available": {iv: bool(ids.get((k, iv))) for iv in ("monthly", "yearly")} if k != "free" else {"monthly": True, "yearly": True},
             "limits": PLANS[k]}
            for k in ("free", "pro", "premium")
        ],
    }


class CheckoutIn(BaseModel):
    plan: Literal["pro", "premium"]
    interval: Literal["monthly", "yearly"] = "monthly"


def _customer(db: Session, user: User) -> Subscription:
    sub = db.get(Subscription, user.id)
    if sub is None:
        customer = stripe.Customer.create(email=user.email, name=user.name or None, metadata={"user_id": str(user.id)})
        sub = Subscription(user_id=user.id, customer_id=customer["id"], status="none", plan="free")
        db.add(sub)
        db.commit()
    return sub


@router.post("/checkout")
def checkout(body: CheckoutIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _client()
    price = price_ids().get((body.plan, body.interval))
    if not price:
        raise HTTPException(400, f"The {body.plan} {body.interval} plan is not available yet.")
    sub = _customer(db, user)
    if sub.status in ACTIVE:
        raise HTTPException(409, "You already have an active subscription. Use Manage billing to change plans.")
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=sub.customer_id,
        line_items=[{"price": price, "quantity": 1}],
        client_reference_id=str(user.id),
        subscription_data={"metadata": {"user_id": str(user.id)}},
        allow_promotion_codes=True,
        success_url=f"{settings.app_url.rstrip('/')}/billing?status=success",
        cancel_url=f"{settings.app_url.rstrip('/')}/billing?status=canceled",
    )
    return {"url": session["url"]}


@router.post("/portal")
def portal(user: User = Depends(current_user), db: Session = Depends(get_db)):
    _client()
    sub = db.get(Subscription, user.id)
    if sub is None:
        raise HTTPException(404, "No billing account yet. Choose a plan first.")
    session = stripe.billing_portal.Session.create(customer=sub.customer_id, return_url=f"{settings.app_url.rstrip('/')}/billing")
    return {"url": session["url"]}


class CancelIn(BaseModel):
    resume: bool = False  # true = keep the subscription (undo a cancellation before the period ends)


@router.post("/cancel")
def cancel(body: CancelIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Stop paying from the next period: the subscription stays active until the end of the period already paid."""
    _client()
    sub = db.get(Subscription, user.id)
    if sub is None or not sub.subscription_id or sub.status not in ("active", "trialing", "past_due"):
        raise HTTPException(404, "You don't have an active subscription.")
    obj = _plain(stripe.Subscription.modify(sub.subscription_id, cancel_at_period_end=not body.resume))
    sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end", not body.resume))
    if obj.get("current_period_end"):
        sub.current_period_end = _ts(obj["current_period_end"])
    db.commit()
    return sub_out(sub)


# ------------------------------------------------------------------ webhooks

def _user_for(db: Session, customer_id: str | None, metadata: dict | None) -> tuple[User | None, Subscription | None]:
    sub = db.scalar(select(Subscription).where(Subscription.customer_id == customer_id)) if customer_id else None
    if sub:
        return db.get(User, sub.user_id), sub
    uid = (metadata or {}).get("user_id")
    user = db.get(User, int(uid)) if uid and str(uid).isdigit() else None
    if user and customer_id:
        sub = db.get(Subscription, user.id) or Subscription(user_id=user.id, customer_id=customer_id)
        sub.customer_id = customer_id
        db.add(sub)
    return user, sub


def apply_subscription(db: Session, obj: dict) -> None:
    """Mirror a Stripe subscription object onto our Subscription row and the user's plan."""
    user, sub = _user_for(db, obj.get("customer"), obj.get("metadata"))
    if user is None or sub is None:
        log.warning("Subscription %s for an unknown customer", obj.get("id"))
        return
    items = (obj.get("items") or {}).get("data") or [{}]
    item = items[0]
    price = item.get("price") or {}
    plan = plan_for_price(price.get("id", "")) or sub.plan
    status = obj.get("status", "none")
    sub.subscription_id = obj.get("id")
    sub.status = status
    sub.plan = plan
    sub.interval = (price.get("recurring") or {}).get("interval")
    sub.amount_cents = int(price.get("unit_amount") or 0) * int(item.get("quantity") or 1)
    sub.currency = price.get("currency") or "usd"
    # Newer Stripe API versions report the billing period on the subscription item.
    sub.current_period_end = _ts(obj.get("current_period_end") or item.get("current_period_end"))
    sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
    sub.canceled_at = _ts(obj.get("canceled_at"))
    sub.updated_at = datetime.now(timezone.utc)
    if user.role != "admin":
        user.plan = plan if status in ACTIVE else "free"
    if status in ACTIVE:
        from ..growth_service import on_paid

        on_paid(db, user)


def record_invoice(db: Session, obj: dict, status: str) -> None:
    user, _ = _user_for(db, obj.get("customer"), (obj.get("subscription_details") or {}).get("metadata"))
    if db.scalar(select(Payment).where(Payment.invoice_id == obj["id"])):
        return
    amount = obj.get("amount_paid") if status == "paid" else obj.get("amount_due")
    db.add(Payment(user_id=user.id if user else None, invoice_id=obj["id"], amount_cents=int(amount or 0),
                   currency=obj.get("currency") or "usd", status=status, created_at=_ts(obj.get("created")) or datetime.now(timezone.utc)))


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    if not settings.stripe_webhook_secret:
        raise HTTPException(503, "Webhook secret not configured")
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid signature")
    event = _plain(event)

    try:  # idempotency: Stripe retries webhooks, apply each event once
        db.add(WebhookEvent(id=event["id"]))
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"received": True, "duplicate": True}

    kind, obj = event["type"], event["data"]["object"]
    if kind in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        apply_subscription(db, obj)
    elif kind == "checkout.session.completed" and obj.get("subscription") and configured():
        stripe.api_key = settings.stripe_secret_key
        full = _plain(stripe.Subscription.retrieve(obj["subscription"], expand=["items.data.price"]))
        if not (full.get("metadata") or {}).get("user_id") and obj.get("client_reference_id"):
            full["metadata"] = {"user_id": obj["client_reference_id"]}
        apply_subscription(db, full)
    elif kind == "invoice.paid":
        record_invoice(db, obj, "paid")
    elif kind == "invoice.payment_failed":
        record_invoice(db, obj, "failed")
    db.commit()
    return {"received": True}
