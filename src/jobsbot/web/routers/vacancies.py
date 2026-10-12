"""Vacancy browser — no Telegram equivalent exists; admins there only
ever see a vacancy via a subscriber's report (see web/routers/reports.py),
never by browsing/searching the whole set. hide/unhide here reuses the
same set_vacancy_hidden the report-resolution flow calls, as a direct
moderation action independent of any report being filed.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from jobsbot.storage.db import async_session
from jobsbot.storage.models import Source, Vacancy
from jobsbot.storage.repo import (
    count_vacancies,
    get_vacancy_by_id,
    list_sources,
    list_vacancies,
    set_vacancy_hidden,
)
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/vacancies", tags=["vacancies"])


def _json_list(value: str) -> list[str]:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def _serialize(vacancy: Vacancy, source_by_id: dict[int, Source]) -> dict:
    source = source_by_id.get(vacancy.source_id)
    return {
        "id": vacancy.id,
        "uuid": vacancy.uuid,
        "title": vacancy.title,
        "company": vacancy.company,
        "url": vacancy.url,
        "source_type": source.type if source else None,
        "source_identifier": source.identifier if source else None,
        "salary_text": vacancy.salary_text,
        "salary_min_rub": vacancy.salary_min_rub,
        "location": vacancy.location,
        "work_format": vacancy.work_format,
        "experience": vacancy.experience,
        "languages": _json_list(vacancy.languages),
        "hidden": vacancy.hidden,
        "posted_at": vacancy.posted_at.isoformat() if vacancy.posted_at else None,
        "first_seen_at": vacancy.first_seen_at.isoformat(),
    }


def _serialize_detail(vacancy: Vacancy, source_by_id: dict[int, Source]) -> dict:
    return {**_serialize(vacancy, source_by_id), "description": vacancy.description}


@router.get("")
async def get_vacancies(
    q: str | None = None,
    language: str | None = None,
    source_type: str | None = None,
    hidden: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: str = Depends(require_admin),
) -> dict:
    async with async_session() as session:
        vacancies = await list_vacancies(
            session, query=q, language=language, source_type=source_type, hidden=hidden, limit=limit, offset=offset
        )
        total = await count_vacancies(session, query=q, language=language, source_type=source_type, hidden=hidden)
        sources = await list_sources(session)

    source_by_id = {s.id: s for s in sources}
    return {"total": total, "items": [_serialize(v, source_by_id) for v in vacancies]}


@router.get("/{vacancy_id}")
async def get_vacancy(vacancy_id: int, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        vacancy = await get_vacancy_by_id(session, vacancy_id)
        if vacancy is None:
            raise HTTPException(status_code=404, detail="Вакансия не найдена")
        sources = await list_sources(session)
    return _serialize_detail(vacancy, {s.id: s for s in sources})


@router.post("/{vacancy_id}/hide")
async def hide_vacancy(vacancy_id: int, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        vacancy = await get_vacancy_by_id(session, vacancy_id)
        if vacancy is None:
            raise HTTPException(status_code=404, detail="Вакансия не найдена")
        await set_vacancy_hidden(session, vacancy_id, True)
    return {"id": vacancy_id, "hidden": True}


@router.post("/{vacancy_id}/unhide")
async def unhide_vacancy(vacancy_id: int, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        vacancy = await get_vacancy_by_id(session, vacancy_id)
        if vacancy is None:
            raise HTTPException(status_code=404, detail="Вакансия не найдена")
        await set_vacancy_hidden(session, vacancy_id, False)
    return {"id": vacancy_id, "hidden": False}
