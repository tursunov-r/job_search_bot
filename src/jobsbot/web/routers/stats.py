"""Mirrors the Telegram "📊 Статистика" button — same underlying data
(storage.repo.get_subscriber_filter_stats), just as JSON instead of a
formatted message.
"""

from fastapi import APIRouter, Depends

from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_subscriber_filter_stats
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats(admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        return await get_subscriber_filter_stats(session)
