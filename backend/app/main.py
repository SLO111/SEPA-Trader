from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Base, engine
from .routers import admin, auth, market, sepa, watchlists

Base.metadata.create_all(engine)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (auth.router, watchlists.router, market.router, sepa.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "data_provider": settings.data_provider}


# Frontend-ul (export static Next.js), montat ultimul ca sa nu acopere rutele /api.
_static = Path(settings.static_dir)
if _static.is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="frontend")
