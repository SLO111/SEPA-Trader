import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .alerts_service import check_rules
from .db import Base, SessionLocal, engine
from .routers import admin, alerts, auth, backtest, billing, community, ideas, journal, journal_notes, market, markets, portfolios, sepa, stock, watchlists

Base.metadata.create_all(engine)

log = logging.getLogger("sepa")


def _run_checks() -> int:
    from sqlalchemy import select

    from .alerts_service import ensure_watchlist_rules
    from .models import User

    with SessionLocal() as db:
        for u in db.scalars(select(User).where(User.is_active.is_(True))).all():
            try:
                ensure_watchlist_rules(db, u)  # watchlists always come with alerts
            except Exception:
                db.rollback()
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


def _finnhub_key_present() -> bool:
    from engine.data.providers import _finnhub

    return _finnhub() is not None


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
    store.on_prices_refreshed(lambda: threading.Thread(target=_rebuild_screens, name="screens-rebuild", daemon=True).start())
    store.start(lambda: list(SYMBOLS), stock_symbols)
    threading.Thread(target=_warm_loop, name="cache-warmer", daemon=True).start()


_rebuild_lock = threading.Lock()


def _rebuild_screens() -> None:
    """New prices (or startup loading finished): rebuild the shared screens now, in dependency order, so the next
    visitor gets the full lists instead of the previous ones."""
    from . import market_data
    from .routers import markets as mk
    from .routers.sepa import cached_scan

    if not _rebuild_lock.acquire(blocking=False):
        return  # a rebuild is already running
    market_data._tls.rebuilding = True
    try:
        for fn in (cached_scan, mk._rows, mk._screen_rows):
            try:
                fn()
            except Exception:
                log.warning("Rebuilding %s failed", getattr(fn, "__name__", fn), exc_info=True)
    finally:
        market_data._tls.rebuilding = False
        _rebuild_lock.release()


def _warm_loop() -> None:
    """Keep the heavy screens precomputed (scan, movers, Fear & Greed, indexes), so pages open instantly."""
    import time

    from .data_store import get_store
    from .routers import markets as mk
    from .routers.sepa import cached_scan, pulse_map

    time.sleep(20)
    while True:
        store = get_store()
        if store is not None and store.prices:
            for fn in (cached_scan, mk._rows, mk._screen_rows, mk._fear_greed, mk._indices, mk._cycle, pulse_map):
                try:
                    fn()
                except Exception:
                    log.debug("warm-up %s failed", getattr(fn, "__name__", fn), exc_info=True)
        time.sleep(240)


def _run_ideas_tick() -> None:
    from .ideas_service import tick

    with SessionLocal() as db:
        tick(db)


async def _ideas_loop(interval: int) -> None:
    """Daily ideas after the close, idea status tracking and the market feed."""
    await asyncio.sleep(30)  # let the market data warm up first
    while True:
        try:
            await asyncio.to_thread(_run_ideas_tick)
        except Exception:
            log.exception("Ideas/feed job failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _warn_missing_config()
    _start_market_data()
    ideas_task = asyncio.create_task(_ideas_loop(settings.ideas_interval_seconds)) if settings.ideas_interval_seconds > 0 else None
    task = asyncio.create_task(_alert_loop(settings.alert_check_seconds)) if settings.alert_check_seconds > 0 else None
    yield
    if task:
        task.cancel()
    if ideas_task:
        ideas_task.cancel()


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=800)  # JSON and JS shrink 5-10x
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (auth.router, watchlists.router, market.router, sepa.router, alerts.router, portfolios.router, stock.router, markets.router, journal.router, backtest.router, billing.router, ideas.router, admin.router, journal_notes.router, community.router):
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
                "fundamentals_paused_until": store.slow_paused_until,
                "universe_source": st.get("universe_source"), "last_error": st.get("last_error"), "last_error_at": st.get("last_error_at"),
                "screens_error": __import__("app.market_data", fromlist=["cache_error"]).cache_error}
    config = {
        # Booleans only: never expose secrets or emails on a public endpoint.
        "data_provider": settings.data_provider,
        "database": "postgresql" if settings.database_url.startswith(("postgres", "postgresql")) else "sqlite (temporary!)",
        "admin_email_set": settings.admin_email != "admin@sepa.local",
        "jwt_secret_set": not settings.jwt_secret.startswith("dev-secret"),
        "email_configured": bool(settings.smtp_host and settings.smtp_from),
        "finnhub_configured": _finnhub_key_present(),
        "universe": settings.universe,
        "universe_extra": settings.universe_extra,
    }
    ideas = None
    try:
        from .ideas_service import due_for_ideas, latest_batch

        with SessionLocal() as db:
            lb = latest_batch(db)
            from . import vnicorn_service as vs

            st = vs.status(db)
            ideas = {"last_batch": lb.isoformat() if lb else None, "due": due_for_ideas(db),
                     "vnicorn": {"trained": st.get("trained"), "stocks": st.get("symbols"), "trained_at": st.get("trained_at"),
                                 "error": vs.last_error}}
            from . import regen_status

            rs = regen_status.status()
            ideas["regenerate"] = {k: rs.get(k) for k in ("running", "stage", "started_at", "finished_at", "generated", "error", "interrupted")}
    except Exception:
        ideas = None
    from . import memory

    mem = {"used_mb": memory.rss_mb(), "limit_mb": memory.limit_mb()}
    try:
        mem["breakdown_mb"] = memory.breakdown()
    except Exception:
        pass
    body = {"status": "ok", "data_provider": settings.data_provider, "universe_size": len(SYMBOLS), "config": config, "market_data": data,
            "ideas": ideas, "memory": mem}
    import json

    from fastapi import Response

    # plain-language summary first, then the details; indented so it reads well in a browser
    payload = {"summary": _health_summary(body), **body}
    return Response(json.dumps(payload, indent=2, default=str), media_type="application/json")


def _health_summary(h: dict) -> list[str]:
    """The status in a few plain sentences."""
    out = []
    md = h.get("market_data") or {}
    state = md.get("state")
    if md:
        label = {"loading": "Starting up: loading saved prices", "refreshing": "Running (updating data in the background)",
                 "ready": "Running", "error": "Running, with errors in the last data update"}.get(state, state or "Running")
        out.append(f"{label}: {h.get('universe_size')} stocks in the universe, {md.get('symbols_with_prices')} with prices, "
                   f"fundamentals {md.get('fundamentals_loaded')}.")
    else:
        out.append(f"Running on {h.get('data_provider')} data: {h.get('universe_size')} symbols.")
    m = h.get("memory") or {}
    if m.get("used_mb") and m.get("limit_mb"):
        pct = round(m["used_mb"] / m["limit_mb"] * 100)
        level = "OK" if pct < 75 else "high" if pct < 90 else "very high: the server may restart"
        top = list((m.get("breakdown_mb") or {}).items())[:3]
        detail = f" Biggest: {', '.join(f'{k} {v} MB' for k, v in top)}." if top else ""
        out.append(f"Memory {m['used_mb']} / {m['limit_mb']} MB ({pct}%): {level}.{detail}")
    ideas = h.get("ideas") or {}
    if ideas:
        out.append(f"Last trade ideas: {ideas.get('last_batch') or 'none yet'} close" + (" (a new batch is due)." if ideas.get("due") else "."))
        v = ideas.get("vnicorn") or {}
        if v.get("trained"):
            out.append(f"vnicornAI: learned from {v.get('stocks')} stocks, trained {str(v.get('trained_at'))[:10]}."
                       + (f" Note: {v['error']}." if v.get("error") else ""))
        else:
            out.append("vnicornAI: not trained yet.")
        r = ideas.get("regenerate") or {}
        if r.get("running"):
            out.append(f"Regeneration running: {r.get('stage')}.")
        elif r.get("interrupted"):
            out.append(f"Last regeneration was interrupted at '{r.get('stage')}' (the server restarted).")
        elif r.get("finished_at"):
            out.append(f"Last regeneration: {'failed: ' + r['error'] if r.get('error') else str(r.get('generated')) + ' new ideas'} "
                       f"({str(r['finished_at'])[:16].replace('T', ' ')} UTC).")
    errors = [f"{k.replace('_', ' ')}: {md[k]}" for k in ("last_error", "screens_error") if md.get(k)]
    out.append("Errors: " + "; ".join(errors) if errors else "No errors.")
    return out


# Frontend (static Next.js export), mounted last so it doesn't shadow /api routes.
class _CachedStatic(StaticFiles):
    """Next.js build files have content hashes in their names, so browsers can keep them for a year."""

    async def get_response(self, path, scope):
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        # A browser that lands on a page's navigation data (".../index.txt", e.g. an old tab after a deploy)
        # is sent to the page itself instead of seeing raw data.
        if path.endswith("index.txt") and "rsc" not in headers and "text/html" in headers.get("accept", ""):
            from urllib.parse import parse_qsl, urlencode

            from starlette.responses import RedirectResponse

            query = urlencode([(k, v) for k, v in parse_qsl(scope.get("query_string", b"").decode()) if k != "_rsc"])
            target = "/" + path[: -len("index.txt")]
            return RedirectResponse(target + (f"?{query}" if query else ""), status_code=302)
        resp = await super().get_response(path, scope)
        if path.startswith("_next/static/"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.endswith((".webp", ".png", ".svg", ".ico", ".jpg")):
            resp.headers["Cache-Control"] = "public, max-age=86400"
        else:
            # pages and their navigation data: always check with the server (cheap 304), so a deploy shows up at once
            resp.headers["Cache-Control"] = "no-cache"
        return resp


_static = Path(settings.static_dir)
if _static.is_dir():
    app.mount("/", _CachedStatic(directory=_static, html=True), name="frontend")
