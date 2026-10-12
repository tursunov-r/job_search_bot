"""Manages the language -> forum-topic thread_id mapping for the group
broadcast (bot/group_broadcast.py). There's no Telegram admin UI for this
at all — it's only ever been set via the one-off seed_group_topics.py
script — so this is genuinely new admin functionality, not a port of an
existing Telegram flow.
"""

from fastapi import APIRouter, Depends, HTTPException

from jobsbot.config import settings
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_group_topic_map, remove_group_topic, set_group_topic
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/group-topics", tags=["group-topics"])


@router.get("")
async def get_group_topics(admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        topic_map = await get_group_topic_map(session)
    return {
        "group_chat_id": settings.group_chat_id,
        "items": [{"language_key": key, "thread_id": thread_id} for key, thread_id in topic_map.items()],
    }


@router.put("/{language_key}")
async def put_group_topic(language_key: str, payload: dict, admin: str = Depends(require_admin)) -> dict:
    thread_id = payload.get("thread_id")
    if not isinstance(thread_id, int):
        raise HTTPException(status_code=400, detail="thread_id обязателен и должен быть числом")
    async with async_session() as session:
        topic = await set_group_topic(session, language_key, thread_id)
    return {"language_key": topic.language_key, "thread_id": topic.thread_id}


@router.delete("/{language_key}")
async def delete_group_topic(language_key: str, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        removed = await remove_group_topic(session, language_key)
    if not removed:
        raise HTTPException(status_code=404, detail="Маппинг не найден")
    return {"removed": True}
