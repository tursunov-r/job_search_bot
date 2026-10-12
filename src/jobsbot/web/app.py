"""Admin web API + static UI — a separate FastAPI service (own container,
see docker-compose.yml's "web" service) reusing the same storage.repo
functions the Telegram admin handlers already call, so there's exactly
one place business logic for each admin action lives.

The UI (static/index.html + app.js + style.css) is a single-page vanilla-
JS app with hash-based routing — no build step, no framework. It's
mounted last, after every /api/* route, so it only ever catches paths
nothing more specific already matched (see the app.mount() call at the
bottom of this file).
"""

import logging
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from jobsbot.storage.db import init_db
from jobsbot.web.auth import require_admin
from jobsbot.web.routers import (
    adapter_health,
    ads,
    channels,
    group_topics,
    reports,
    required_channels,
    staff,
    stats,
    subscribers,
    vacancies,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Jobsbot Admin API")
app.include_router(stats.router)
app.include_router(subscribers.router)
app.include_router(channels.router)
app.include_router(staff.router)
app.include_router(required_channels.router)
app.include_router(ads.router)
app.include_router(reports.router)
app.include_router(group_topics.router)
app.include_router(adapter_health.router)
app.include_router(vacancies.router)


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


_STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/")
async def index() -> FileResponse:
    """Unauthenticated, same reasoning as /health — it's just the static
    shell (nav + empty content area); every actual admin action goes
    through an /api/* call, which auth.require_admin does gate."""
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
