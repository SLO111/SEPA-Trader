from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SEPA Trader"
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
    # Background alert checks: interval in seconds (0 disables the background loop).
    alert_check_seconds: int = 300
    # Email notifications (optional): any SMTP provider, e.g. Gmail, Brevo, SendGrid.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    # Telegram notifications (optional): token from @BotFather.
    telegram_bot_token: str = ""


settings = Settings()
