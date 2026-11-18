from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Vnicorn Investments"
    # Free Premium days for new accounts (0 disables the trial)
    trial_days: int = 14
    database_url: str = "sqlite:///./sepa.db"
    jwt_secret: str = "dev-secret-change-me-in-production-use-a-long-key"
    jwt_expire_minutes: int = 60 * 24 * 7
    # The account registered with this email becomes an administrator.
    admin_email: str = "admin@sepa.local"
    # "synthetic" (offline demo data) or "yfinance" (free real data, delayed)
    data_provider: str = "synthetic"
    cors_origins: str = "http://localhost:3000"
    # Folder with the statically exported frontend (in Docker). Served at "/" if present.
    static_dir: str = "static"
    # Universe of stocks in live mode: "sp500+" (S&P 500 + Nasdaq-100 + the built-in list), "sp500", or "core" (built-in only).
    universe: str = "sp500+"  # core | sp500 | sp500+ | sp500+r1000
    universe_extra: int = 300  # with sp500+r1000: how many extra Russell 1000 stocks (largest first)
    # Keep a persistent market-data cache and refresh it in the background (live providers only).
    data_refresh: bool = True
    # Background alert checks: interval in seconds (0 disables the background loop).
    alert_check_seconds: int = 300
    # Trade ideas + market feed background job interval in seconds (0 disables).
    ideas_interval_seconds: int = 600
    vnicorn_train_stocks: int = 800  # vnicornAI learns from this many of the most liquid stocks
    vnicorn_samples: int = 3000  # upper bound of sample dates; the server lowers it to what its free memory allows
    # Email notifications (optional): any SMTP provider, e.g. Gmail, Brevo, SendGrid.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    # Telegram notifications (optional): token from @BotFather.
    telegram_bot_token: str = ""
    # Finnhub API key (free plan works): fundamentals, earnings, profiles and news when Yahoo blocks them.
    finnhub_api_key: str = ""
    # Payments (Stripe). Billing is disabled until STRIPE_SECRET_KEY is set.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_pro_yearly: str = ""
    stripe_price_premium_monthly: str = ""
    stripe_price_premium_yearly: str = ""
    # Public URL of the app, used for Stripe redirect links.
    app_url: str = "http://localhost:3000"


settings = Settings()
