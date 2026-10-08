"""Delegable staff permissions. Staff *management* (add/remove) is not a
permission in this registry — it's always super-admin-only, checked via
is_super_admin() directly, never delegated."""

import json

from jobsbot.config import settings
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_staff_member

PERMISSIONS: dict[str, str] = {
    "manage_channels": "Каналы",
    "block_users": "Блокировка пользователей",
    "manage_ads": "Реклама",
    "moderate_vacancies": "Жалобы на вакансии",
}


def is_super_admin(telegram_user_id: int) -> bool:
    return telegram_user_id == settings.super_admin_telegram_user_id


async def get_permissions(telegram_user_id: int) -> set[str]:
    if is_super_admin(telegram_user_id):
        return set(PERMISSIONS.keys())

    async with async_session() as session:
        staff = await get_staff_member(session, telegram_user_id)

    if staff is None or staff.status != "active":
        return set()

    try:
        return set(json.loads(staff.permissions))
    except (TypeError, ValueError):
        return set()


async def has_permission(telegram_user_id: int, key: str) -> bool:
    return key in await get_permissions(telegram_user_id)
