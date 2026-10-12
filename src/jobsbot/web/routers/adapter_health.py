"""Read-only view of scraper health (see storage.models.AdapterHealth and
main.py::_check_adapter_health) — the Telegram side only ever pushes an
alert/recovery message to the super admin when the empty-streak crosses
the threshold, there's no "check status anytime" view there.
"""

from fastapi import APIRouter, Depends

from jobsbot.config import settings
from jobsbot.storage.db import async_session
from jobsbot.storage.models import AdapterHealth
from jobsbot.storage.repo import list_adapter_health
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/adapter-health", tags=["adapter-health"])


def _serialize(health: AdapterHealth) -> dict:
    return {
        "adapter": health.adapter,
        "consecutive_empty_polls": health.consecutive_empty_polls,
        "alert_sent": health.alert_sent,
        "last_polled_at": health.last_polled_at.isoformat() if health.last_polled_at else None,
        "failure_threshold": settings.adapter_failure_threshold,
    }


@router.get("")
async def get_adapter_health(admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        rows = await list_adapter_health(session)
    return {"items": [_serialize(r) for r in rows]}
