import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .alerts_service import check_rules
from .db import Base, SessionLocal, engine
from .routers import admin, alerts, auth, backtest, billing, journal, market, markets, portfolios, sepa, stock, watchlists

Base.metadata.create_all(engine)

log = logging.getLogger("sepa")


def _run_checks() -> int:
    with SessionLocal() as db:
        return len(check_rules(db))


async def _alert_loop(interval: int) -> None:
    """Periodically evaluate every user's alert rules in a worker thread."""
    while True:
        await asyncio.sleep(interval)
        try:
            n = await asyncio.to_thread(_run_checks)
            if n:
                log.info("Alert check created %d alerts", n)
        except Exception:
            log.exception("Alert check failed")


def _warn_missing_config() -> None:
    if settings.admin_email == "admin@sepa.local":
        log.warning("ADMIN_EMAIL is not set: nobody will become administrator")
    if settings.jwt_secret.startswith("dev-secret"):
        log.warning("JWT_SECRET is not set: using the insecure development secret")
    if settings.database_url.startswith("sqlite"):
        log.warning("DATABASE_URL is not set: using a local SQLite file (data is lost on redeploy)")


def _start_market_data() -> None:
    """Live providers: warm the store from the database and keep it updated in the background."""
    from engine.data.universe import SYMBOLS, stock_symbols

    from .data_store import get_store
    from .routers.sepa import invalidate_scan

    store = get_store()
    if store is None:
        return
    store.on_prices_refreshed(invalidate_scan)
    store.start(lambda: list(SYMBOLS), stock_symbols)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _warn_missing_config()
    _start_market_data()
    task = asyncio.create_task(_alert_loop(settings.alert_check_seconds)) if settings.alert_check_seconds > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (auth.router, watchlists.router, market.router, sepa.router, alerts.router, portfolios.router, stock.router, markets.router, journal.router, backtest.router, billing.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    from engine.data.universe import SYMBOLS

    from .data_store import get_store

    store = get_store()
    data = None
    if store is not None:
        st = store.status
        data = {"state": st["state"], "message": st["message"], "symbols_with_prices": len(store.prices),
                "prices_refreshed_at": st["prices_refreshed_at"], "live_updated_at": st.get("live_updated_at"),
                "fundamentals_loaded": f"{st['slow_done']}/{st['slow_total']}",
                "fundamentals_paused_until": store.slow_paused_until}
    config = {
        # Booleans only: never expose secrets or emails on a public endpoint.
        "data_provider": settings.data_provider,
        "database": "postgresql" if settings.database_url.startswith(("postgres", "postgresql")) else "sqlite (temporary!)",
        "admin_email_set": settings.admin_email != "admin@sepa.local",
        "jwt_secret_set": not settings.jwt_secret.startswith("dev-secret"),
        "email_configured": bool(settings.smtp_host and settings.smtp_from),
        "universe": settings.universe,
    }
    return {"status": "ok", "data_provider": settings.data_provider, "universe_size": len(SYMBOLS), "config": config, "market_data": data}


# Frontend (static Next.js export), mounted last so it doesn't shadow /api routes.
_static = Path(settings.static_dir)
if _static.is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="frontend")
