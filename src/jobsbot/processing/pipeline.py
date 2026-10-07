import json
import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from jobsbot.ingestion.base import RawVacancy
from jobsbot.ingestion.normalize import clean_raw_vacancy
from jobsbot.processing.dedup import fingerprint
from jobsbot.processing.languages import detect_languages
from jobsbot.storage.models import Vacancy
from jobsbot.storage.repo import get_vacancy_by_fingerprint, insert_vacancy

logger = logging.getLogger(__name__)


async def ingest(
    session: AsyncSession, raw: RawVacancy, source_id: int, language_hint: str | None = None
) -> Vacancy | None:
    """Normalize -> filter -> dedup -> store. Returns the new Vacancy if inserted, else None.

    language_hint: pass the language a source was queried for (HH/LinkedIn —
    trusted, no re-detection needed). Leave None for mixed-topic sources
    (Telegram channels), where relevance is decided by detect_languages.
    """
    clean = clean_raw_vacancy(raw)

    if not clean.title:
        return None

    if language_hint:
        languages_found = [language_hint]
    else:
        languages_found = detect_languages(clean.title, clean.description or "")
        if not languages_found:
            logger.debug("Skipping vacancy not matching any supported language: %s", clean.title)
            return None

    fp = fingerprint(clean.title, clean.company, clean.description)
    existing = await get_vacancy_by_fingerprint(session, fp)
    if existing:
        source_ids = set(json.loads(existing.raw_source_ids))
        if source_id not in source_ids:
            source_ids.add(source_id)
            existing.raw_source_ids = json.dumps(sorted(source_ids))
            session.add(existing)
            await session.commit()
        return None

    vacancy = Vacancy(
        fingerprint=fp,
        title=clean.title,
        company=clean.company,
        description=clean.description,
        url=clean.url,
        source_id=source_id,
        raw_source_ids=json.dumps([source_id]),
        salary_text=clean.salary_text,
        location=clean.location,
        work_format=clean.work_format,
        experience=clean.experience,
        employment_type=clean.employment_type,
        schedule=clean.schedule,
        posted_at=clean.posted_at,
        is_python_relevant=True,
        languages=json.dumps(languages_found),
        source_chat_id=clean.source_chat_id,
        source_message_id=clean.source_message_id,
    )
    return await insert_vacancy(session, vacancy)
