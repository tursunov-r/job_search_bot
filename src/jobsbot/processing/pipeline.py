import json
import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from jobsbot.ingestion.base import RawVacancy
from jobsbot.ingestion.normalize import clean_raw_vacancy
from jobsbot.processing.dedup import fingerprint
from jobsbot.processing.languages import detect_languages, language_matches
from jobsbot.storage.models import Vacancy
from jobsbot.storage.repo import get_vacancy_by_fingerprint, get_vacancy_by_url, insert_vacancy

logger = logging.getLogger(__name__)


async def ingest(
    session: AsyncSession,
    raw: RawVacancy,
    source_id: int,
    language_hint: str | None = None,
    needs_details: bool = False,
) -> Vacancy | None:
    """Normalize -> filter -> dedup -> store. Returns the new Vacancy if inserted, else None.

    language_hint: pass the language a source was queried for (HH/LinkedIn —
    trusted, no re-detection needed). Leave None for mixed-topic sources
    (Telegram channels), where relevance is decided by detect_languages.

    needs_details: True for sources that enrich the vacancy with a later,
    separate detail-page fetch (HH, Habr) — keeps it out of push_new_vacancies
    until that pass completes (see Vacancy.details_checked).
    """
    clean = clean_raw_vacancy(raw)

    if not clean.title:
        return None

    if language_hint:
        if language_matches(language_hint, clean.title, clean.description):
            languages_found = [language_hint]
        else:
            # HH/Habr sometimes pad a sparse search term with unrelated
            # postings past the first page once genuine matches run out —
            # don't blindly trust the hint if the vacancy's own text never
            # actually mentions it; fall back to general detection instead.
            languages_found = detect_languages(clean.title, clean.description or "")
            if not languages_found:
                logger.debug(
                    "Dropping vacancy — search hint %r not actually mentioned: %s", language_hint, clean.title
                )
                return None
    else:
        languages_found = detect_languages(clean.title, clean.description or "")
        if not languages_found:
            logger.debug("Skipping vacancy not matching any supported language: %s", clean.title)
            return None

    fp = fingerprint(clean.title, clean.company, clean.description)
    existing = await get_vacancy_by_fingerprint(session, fp)
    if existing is None and clean.url:
        # The fingerprint hashes title+company+description together, but a
        # source can re-render the exact same posting (same URL) with the
        # employer's display name/brand changed between scrapes — confirmed
        # live on HH (e.g. "ИнфоТех / ЗАО ЦТО ККМ СПб..." vs "Кассир.Ру (ООО
        # ИнфоТех)" for the same vacancy a few hours apart), which shifts the
        # fingerprint enough to slip past that check alone and get resent to
        # subscribers who already got the original. The URL doesn't drift.
        existing = await get_vacancy_by_url(session, clean.url)
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
        details_checked=not needs_details,
    )
    return await insert_vacancy(session, vacancy)
