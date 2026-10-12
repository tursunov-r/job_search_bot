"""Mirrors the Telegram "📡 Каналы" admin flow — add/remove/list the
Telegram channels the bot polls for vacancies (Source rows, type
'telegram_channel'). Channel parsing itself still only actually runs if
settings.telegram_enabled (TELEGRAM_API_ID/HASH set) — included in the
list response so the UI can warn if it's off, same as the Telegram side.
"""

from fastapi import APIRouter, Depends, HTTPException

from jobsbot.config import settings
from jobsbot.storage.db import async_session
from jobsbot.storage.models import Source
from jobsbot.storage.repo import (
    add_telegram_channel,
    get_source_by_id,
    list_telegram_channels,
    remove_telegram_channel,
)
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _serialize(source: Source) -> dict:
    return {"id": source.id, "identifier": source.identifier, "enabled": source.enabled}


@router.get("")
async def get_channels(admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        channels = await list_telegram_channels(session)
    return {"telegram_enabled": settings.telegram_enabled, "items": [_serialize(c) for c in channels]}


@router.post("")
async def add_channel(payload: dict, admin: str = Depends(require_admin)) -> dict:
    identifier = (payload.get("identifier") or "").strip().lstrip("@")
    if not identifier:
        raise HTTPException(status_code=400, detail="identifier обязателен")
    async with async_session() as session:
        source = await add_telegram_channel(session, identifier)
    return _serialize(source)


@router.delete("/{source_id}")
async def remove_channel(source_id: int, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        source = await get_source_by_id(session, source_id)
        if source is None or source.type != "telegram_channel":
            raise HTTPException(status_code=404, detail="Канал не найден")
        removed = await remove_telegram_channel(session, source.identifier)
    if not removed:
        raise HTTPException(status_code=404, detail="Канал уже удалён")
    return {"removed": True}
