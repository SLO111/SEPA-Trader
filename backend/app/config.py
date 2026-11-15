from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SEPA Trader"
    database_url: str = "sqlite:///./sepa.db"
    jwt_secret: str = "dev-secret-schimba-in-productie-cu-o-cheie-lunga"
    jwt_expire_minutes: int = 60 * 24 * 7
    # Contul cu acest email devine administrator la inregistrare.
    admin_email: str = "admin@sepa.local"
    # "synthetic" (date demo, fara internet) sau "yfinance" (date reale gratuite, cu intarziere)
    data_provider: str = "synthetic"
    cors_origins: str = "http://localhost:3000"
    # Folderul cu frontend-ul exportat static (in Docker). Daca exista, e servit la "/".
    static_dir: str = "static"


settings = Settings()
