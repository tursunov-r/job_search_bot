import json
import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from jobsbot.ingestion.base import RawVacancy
from jobsbot.ingestion.normalize import clean_raw_vacancy
from jobsbot.processing.dedup import fingerprint
from jobsbot.processing.keyword_filter import is_python_vacancy
from jobsbot.storage.models import Vacancy
from jobsbot.storage.repo import get_vacancy_by_fingerprint, insert_vacancy

logger = logging.getLogger(__name__)


async def ingest(session: AsyncSession, raw: RawVacancy, source_id: int) -> Vacancy | None:
    """Normalize -> filter -> dedup -> store. Returns the new Vacancy if inserted, else None."""
    clean = clean_raw_vacancy(raw)

    if not clean.title:
        return None

    if not is_python_vacancy(clean.title, clean.description or ""):
        logger.debug("Skipping non-python vacancy: %s", clean.title)
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
        posted_at=clean.posted_at,
        is_python_relevant=True,
    )
    return await insert_vacancy(session, vacancy)
