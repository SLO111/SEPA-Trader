from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free | pro | premium
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    watchlists: Mapped[list["Watchlist"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="Watchlist.position"
    )


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(16), default="#3b82f6")
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped[User] = relationship(back_populates="watchlists")
    items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan", order_by="WatchlistItem.position"
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("watchlist_id", "symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer, default=0)

    watchlist: Mapped[Watchlist] = relationship(back_populates="items")


class AlertRule(Base):
    """What a user wants to be alerted about: a scope (symbol / watchlist / whole universe) and event types."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    scope: Mapped[str] = mapped_column(String(16))  # symbol | watchlist | universe
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    watchlist_id: Mapped[int | None] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=True)
    events: Mapped[str] = mapped_column(String(400))  # comma-separated event types
    price_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    bull_threshold: Mapped[float] = mapped_column(Float, default=70)
    bear_threshold: Mapped[float] = mapped_column(Float, default=70)
    channels: Mapped[str] = mapped_column(String(60), default="app")  # comma-separated: app,email,telegram
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Alert(Base):
    """A triggered alert. Unique per user/symbol/event/bar so the same event never alerts twice."""

    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("user_id", "symbol", "type", "bar_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(16))
    type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))  # bull | bear | info
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    bar_date: Mapped[str] = mapped_column(String(10))
    read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    email_enabled: Mapped[bool] = mapped_column(default=False)
    telegram_enabled: Mapped[bool] = mapped_column(default=False)
    telegram_chat_id: Mapped[str] = mapped_column(String(40), default="")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), default="")
    template_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    transactions: Mapped[list["PortfolioTxn"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", order_by="PortfolioTxn.date"
    )


class PortfolioTxn(Base):
    __tablename__ = "portfolio_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    symbol: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(4))  # buy | sell
    shares: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")


class JournalTrade(Base):
    __tablename__ = "journal_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symbol: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(5), default="long")  # long | short
    entry_date: Mapped[date] = mapped_column(Date)
    entry_price: Mapped[float] = mapped_column(Float)
    shares: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    setup: Mapped[str] = mapped_column(String(40), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Subscription(Base):
    """A user's Stripe subscription, kept in sync by webhooks."""

    __tablename__ = "subscriptions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="none")  # active | trialing | past_due | canceled | ...
    plan: Mapped[str] = mapped_column(String(20), default="free")
    interval: Mapped[str | None] = mapped_column(String(10), nullable=True)  # month | year
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="usd")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Payment(Base):
    """Paid (or failed) invoices, for revenue reporting in the admin panel."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_id: Mapped[str] = mapped_column(String(64), unique=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="usd")
    status: Mapped[str] = mapped_column(String(16))  # paid | failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class WebhookEvent(Base):
    """Processed Stripe event ids, so a retried webhook is never applied twice."""

    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MarketCache(Base):
    """Persistent market data cache (prices, fundamentals, earnings, universe) so restarts start warm."""

    __tablename__ = "market_cache"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)  # e.g. "prices:AAPL", "fundamentals:AAPL"
    payload: Mapped[bytes] = mapped_column(LargeBinary)  # gzip-compressed JSON
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class TradeIdea(Base):
    """A daily trade idea (generated after the close) and how it played out since."""

    __tablename__ = "trade_ideas"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_date: Mapped[date] = mapped_column(Date, index=True)  # trading day the idea was generated for
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))  # SWING | TRADE | INVEST | SHORT
    side: Mapped[str] = mapped_column(String(5))
    entry: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    trim: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float] = mapped_column(Float)
    rr: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="WAIT")  # WAIT BUY TRIM TARGET STOPPED CANCEL
    current: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    closed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FeedItem(Base):
    """A notification in the market feed (earnings beats, big movers, breakouts, critical news, new ideas)."""

    __tablename__ = "feed_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True)  # deduplication key
    kind: Mapped[str] = mapped_column(String(16), index=True)  # earnings | mover | breakout | high | news | idea
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(8), default="info")  # bull | bear | info
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class DailyDigest(Base):
    """Opt-in for the end-of-day summary by email."""

    __tablename__ = "daily_digest"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sent: Mapped[date | None] = mapped_column(Date, nullable=True)


class AutoAlertDone(Base):
    """Watchlists that already got their automatic alert rule (so a rule the user deleted isn't recreated)."""

    __tablename__ = "auto_alert_done"

    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"), primary_key=True)


class PaperTrade(Base):
    """A Trade Idea the user chose to take (Buy / Short button), tracked with the idea's stop / trim / target."""

    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    idea_id: Mapped[int | None] = mapped_column(ForeignKey("trade_ideas.id", ondelete="SET NULL"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(8), default="")
    side: Mapped[str] = mapped_column(String(5))
    entry_date: Mapped[date] = mapped_column(Date)
    entry: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    trim: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ModelBlob(Base):
    """A trained machine-learning model (pickled) and when it was trained, so restarts don't retrain it."""

    __tablename__ = "model_blobs"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AIPick(Base):
    """vnicornAI's rating and plan for a trade idea."""

    __tablename__ = "ai_picks"

    idea_id: Mapped[int] = mapped_column(ForeignKey("trade_ideas.id", ondelete="CASCADE"), primary_key=True)
    prob: Mapped[float] = mapped_column(Float)
    ev: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    trim: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float] = mapped_column(Float)
    rr: Mapped[float] = mapped_column(Float)
    pick: Mapped[bool] = mapped_column(Boolean, default=False)
