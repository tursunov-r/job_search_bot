"""Mirrors the Telegram "👥 Сотрудники" admin flow (super-admin only on
the bot side — there's no granular-role check here yet, see web/auth.py's
module docstring on that trade-off).
"""

import json

from fastapi import APIRouter, Depends, HTTPException

from jobsbot.bot.permissions import PERMISSIONS
from jobsbot.config import settings
from jobsbot.storage.db import async_session
from jobsbot.storage.models import StaffMember
from jobsbot.storage.repo import add_staff_member, list_staff_members, remove_staff_member
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/staff", tags=["staff"])


def _serialize(staff: StaffMember) -> dict:
    try:
        permissions = json.loads(staff.permissions)
    except (TypeError, ValueError):
        permissions = []
    return {
        "id": staff.id,
        "telegram_user_id": staff.telegram_user_id,
        "username": staff.username,
        "permissions": permissions,
        "status": staff.status,
        "added_at": staff.added_at.isoformat(),
    }


@router.get("/permissions")
async def get_permission_options(admin: str = Depends(require_admin)) -> dict:
    return {"permissions": PERMISSIONS}


@router.get("")
async def get_staff(admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        staff = await list_staff_members(session)
    return {"items": [_serialize(s) for s in staff]}


@router.post("")
async def add_staff(payload: dict, admin: str = Depends(require_admin)) -> dict:
    telegram_user_id = payload.get("telegram_user_id")
    permissions = payload.get("permissions") or []
    if not isinstance(telegram_user_id, int):
        raise HTTPException(status_code=400, detail="telegram_user_id обязателен и должен быть числом")
    unknown = set(permissions) - set(PERMISSIONS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Неизвестные права: {', '.join(unknown)}")

    async with async_session() as session:
        staff = await add_staff_member(
            session,
            telegram_user_id,
            username=payload.get("username"),
            permissions=list(permissions),
            added_by_telegram_user_id=settings.super_admin_telegram_user_id,
        )
    return _serialize(staff)


@router.delete("/{staff_id}")
async def remove_staff(staff_id: int, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        staff = await remove_staff_member(session, staff_id)
    if staff is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return _serialize(staff)
