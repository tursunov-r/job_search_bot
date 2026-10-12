"""Mirrors the Telegram "🔐 Обязательные каналы" admin flow (the
subscription gate new subscribers must pass — see bot/subscription_gate.py).

Unlike the Telegram side, this has no bot instance to call get_chat() with,
so title isn't auto-fetched here — pass one in the request if you want a
display name, otherwise it falls back to the username (same as the
Telegram flow when that lookup fails there too).
"""

from fastapi import APIRouter, Depends, HTTPException

from jobsbot.storage.db import async_session
from jobsbot.storage.models import RequiredChannel
from jobsbot.storage.repo import add_required_channel, list_required_channels, remove_required_channel
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/required-channels", tags=["required-channels"])


def _serialize(channel: RequiredChannel) -> dict:
    return {
        "id": channel.id,
        "username": channel.username,
        "title": channel.title,
        "added_at": channel.added_at.isoformat(),
    }


@router.get("")
async def get_required_channels(admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        channels = await list_required_channels(session)
    return {"items": [_serialize(c) for c in channels]}


@router.post("")
async def add_required_channel_endpoint(payload: dict, admin: str = Depends(require_admin)) -> dict:
    username = (payload.get("username") or "").strip().lstrip("@")
    if not username:
        raise HTTPException(status_code=400, detail="username обязателен")
    async with async_session() as session:
        try:
            channel = await add_required_channel(session, username, payload.get("title"))
        except Exception as exc:
            raise HTTPException(status_code=409, detail=f"@{username} уже в списке") from exc
    return _serialize(channel)


@router.delete("/{channel_id}")
async def remove_required_channel_endpoint(channel_id: int, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        removed = await remove_required_channel(session, channel_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Канал не найден")
    return {"removed": True}
