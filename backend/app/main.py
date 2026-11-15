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
from .routers import admin, alerts, auth, backtest, journal, market, markets, portfolios, sepa, stock, watchlists

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


@asynccontextmanager
async def lifespan(_: FastAPI):
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
for r in (auth.router, watchlists.router, market.router, sepa.router, alerts.router, portfolios.router, stock.router, markets.router, journal.router, backtest.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "data_provider": settings.data_provider}


# Frontend (static Next.js export), mounted last so it doesn't shadow /api routes.
_static = Path(settings.static_dir)
if _static.is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="frontend")
