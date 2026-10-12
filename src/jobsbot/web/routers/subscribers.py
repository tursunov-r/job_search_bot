"""Mirrors the Telegram "🚫 Пользователи" admin flow (block/unblock), plus
a paginated list — the Telegram side never needed a list view since it
blocks by typing a known telegram_user_id, not browsing.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from jobsbot.storage.db import async_session
from jobsbot.storage.models import Subscriber
from jobsbot.storage.repo import (
    block_subscriber_by_telegram_id,
    count_subscribers,
    list_subscribers,
    unblock_subscriber_by_telegram_id,
)
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/subscribers", tags=["subscribers"])


def _serialize(subscriber: Subscriber) -> dict:
    def _json_list(value: str) -> list[str]:
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return []

    return {
        "id": subscriber.id,
        "telegram_user_id": subscriber.telegram_user_id,
        "username": subscriber.username,
        "status": subscriber.status,
        "subscribed_at": subscriber.subscribed_at.isoformat(),
        "last_interaction_at": subscriber.last_interaction_at.isoformat() if subscriber.last_interaction_at else None,
        "languages": _json_list(subscriber.languages),
        "skills": _json_list(subscriber.skills),
        "cities": _json_list(subscriber.cities),
        "work_formats": _json_list(subscriber.work_formats),
        "keywords": _json_list(subscriber.keywords),
        "min_salary": subscriber.min_salary,
    }


@router.get("")
async def get_subscribers(
    status: str | None = Query(default=None, pattern="^(active|paused|blocked)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: str = Depends(require_admin),
) -> dict:
    async with async_session() as session:
        subscribers = await list_subscribers(session, status=status, limit=limit, offset=offset)
        total = await count_subscribers(session, status=status)
    return {"total": total, "items": [_serialize(s) for s in subscribers]}


@router.post("/{telegram_user_id}/block")
async def block_subscriber(telegram_user_id: int, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        subscriber = await block_subscriber_by_telegram_id(session, telegram_user_id)
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Подписчик не найден")
    return _serialize(subscriber)


@router.post("/{telegram_user_id}/unblock")
async def unblock_subscriber(telegram_user_id: int, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        subscriber = await unblock_subscriber_by_telegram_id(session, telegram_user_id)
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Подписчик не найден")
    return _serialize(subscriber)
