import html
import re

from jobsbot.ingestion.base import RawVacancy

_WHITESPACE_RE = re.compile(r"\s+")


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text or None


def clean_raw_vacancy(raw: RawVacancy) -> RawVacancy:
    return RawVacancy(
        title=_clean(raw.title) or "",
        description=_clean(raw.description),
        url=raw.url,
        company=_clean(raw.company),
        salary_text=_clean(raw.salary_text),
        location=_clean(raw.location),
        work_format=_clean(raw.work_format),
        experience=_clean(raw.experience),
        employment_type=_clean(raw.employment_type),
        schedule=_clean(raw.schedule),
        posted_at=raw.posted_at,
        source_chat_id=raw.source_chat_id,
        source_message_id=raw.source_message_id,
    )
