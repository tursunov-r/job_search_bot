"""Mirrors the Telegram vacancy-report moderation flow (reports.py's
handle_moderate_report) — resolve a subscriber's "🚩 Пожаловаться" report
by either hiding the vacancy for good or keeping it (rejecting the
report). The list view itself is new: on the Telegram side each report is
pushed to admins individually as its own message when filed, no browsing
needed there.
"""

from fastapi import APIRouter, Depends, HTTPException

from jobsbot.config import settings
from jobsbot.storage.db import async_session
from jobsbot.storage.models import VacancyReport
from jobsbot.storage.repo import (
    get_vacancy_by_id,
    get_vacancy_report,
    list_vacancy_reports,
    resolve_vacancy_report,
    set_vacancy_hidden,
)
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/reports", tags=["reports"])


async def _serialize(report: VacancyReport) -> dict:
    async with async_session() as session:
        vacancy = await get_vacancy_by_id(session, report.vacancy_id)
    return {
        "id": report.id,
        "vacancy_id": report.vacancy_id,
        "vacancy_title": vacancy.title if vacancy else None,
        "vacancy_url": vacancy.url if vacancy else None,
        "comment": report.comment,
        "status": report.status,
        "created_at": report.created_at.isoformat(),
        "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
    }


@router.get("")
async def get_reports(
    status: str | None = "pending", admin: str = Depends(require_admin)
) -> dict:
    async with async_session() as session:
        reports = await list_vacancy_reports(session, status=status)
    return {"items": [await _serialize(r) for r in reports]}


@router.post("/{report_id}/resolve")
async def resolve_report(report_id: int, payload: dict, admin: str = Depends(require_admin)) -> dict:
    action = payload.get("action")
    if action not in ("keep", "remove"):
        raise HTTPException(status_code=400, detail="action должен быть 'keep' или 'remove'")

    async with async_session() as session:
        report = await get_vacancy_report(session, report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Жалоба не найдена")
        if report.status != "pending":
            raise HTTPException(status_code=409, detail="Жалоба уже обработана")

        keep = action == "keep"
        await set_vacancy_hidden(session, report.vacancy_id, not keep)
        await resolve_vacancy_report(
            session, report, "resolved_kept" if keep else "resolved_removed", settings.super_admin_telegram_user_id
        )

    return await _serialize(report)
