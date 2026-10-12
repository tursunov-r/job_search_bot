"""Admin web API — a separate FastAPI service (own container, see
docker-compose.yml's "web" service) reusing the same storage.repo
functions the Telegram admin handlers already call, so there's exactly
one place business logic for each admin action lives. Endpoints are added
incrementally, one admin feature at a time; the actual web pages (HTML,
design) come once the API surface covers everything the Telegram /admin
menu does.
"""

import logging

from fastapi import Depends, FastAPI

from jobsbot.storage.db import init_db
from jobsbot.web.auth import require_admin
from jobsbot.web.routers import channels, required_channels, staff, stats, subscribers

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Jobsbot Admin API")
app.include_router(stats.router)
app.include_router(subscribers.router)
app.include_router(channels.router)
app.include_router(staff.router)
app.include_router(required_channels.router)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict:
    """Unauthenticated — for docker/monitoring, not an admin action."""
    return {"status": "ok"}


@app.get("/api/ping")
async def ping(admin: str = Depends(require_admin)) -> dict:
    """Proves the auth wiring works end-to-end before any real endpoints
    are added on top of it."""
    return {"status": "ok", "admin": admin}
