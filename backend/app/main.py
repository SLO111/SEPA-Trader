from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routers import admin, auth, market, watchlists

Base.metadata.create_all(engine)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (auth.router, watchlists.router, market.router, admin.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "data_provider": settings.data_provider}
