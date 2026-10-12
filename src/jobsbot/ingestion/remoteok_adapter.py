"""RemoteOK public JSON API adapter.

Officially permitted, not just "robots.txt doesn't forbid it" — the API's
own response includes an explicit terms notice: "API Terms of Service:
Please link back... and mention Remote OK as a source", which the
"🔗 Подробнее" link already attached to every vacancy satisfies.

Much simpler than the HTML-scraping adapters: one JSON request per
language, no listing/detail split (everything needed is already in the
response), no pagination — confirmed live that `page=` has no effect, the
tag-filtered endpoint always returns the same ~100 most recent matches.

RemoteOK's own tag vocabulary doesn't map 1:1 onto languages.py keys
(e.g. "go" -> "golang", "qa" -> "testing") and some have no real tag at
all there (csharp, cpp, kotlin) — confirmed each mapping live by checking
every returned job's own tags array actually contains the queried tag
(unrecognized/too-short tags like "c" or "net" silently fall back to the
generic latest-jobs feed instead of erroring, which would otherwise look
like a real match if not checked). Languages with no verified tag are
simply not queried here.
"""

import logging
import re
from datetime import datetime

import httpx

from jobsbot.ingestion.base import RawVacancy

logger = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

REMOTEOK_TAG_BY_LANGUAGE: dict[str, str] = {
    "python": "python",
    "javascript": "javascript",
    "go": "golang",
    "java": "java",
    "php": "php",
    "ruby": "ruby",
    "sql": "sql",
    "swift": "swift",
    "dart": "flutter",
    "devops": "devops",
    "sysadmin": "sys-admin",
    "qa": "testing",
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html_text: str | None) -> str | None:
    if not html_text:
        return None
    return " ".join(_HTML_TAG_RE.sub(" ", html_text).split()) or None


def _format_salary(salary_min, salary_max) -> str | None:
    salary_min = int(salary_min) if salary_min else None
    salary_max = int(salary_max) if salary_max else None
    if not salary_min and not salary_max:
        return None
    if salary_min and salary_max and salary_min != salary_max:
        return f"${salary_min:,}–${salary_max:,} / год"
    return f"${salary_min or salary_max:,} / год"


def _parse_entry(entry: dict) -> RawVacancy | None:
    if "id" not in entry:
        return None  # the first array element is always the ToS/legal notice, not a job

    posted_at = None
    if entry.get("date"):
        try:
            posted_at = datetime.fromisoformat(entry["date"])
        except ValueError:
            pass

    return RawVacancy(
        title=entry.get("position") or "",
        description=_strip_html(entry.get("description")),
        url=entry.get("url") or entry.get("apply_url"),
        company=entry.get("company"),
        salary_text=_format_salary(entry.get("salary_min"), entry.get("salary_max")),
        location=entry.get("location") or None,
        work_format="удалённо",  # every RemoteOK posting is remote by definition
        posted_at=posted_at,
    )


async def fetch_vacancies(language_key: str) -> list[RawVacancy]:
    tag = REMOTEOK_TAG_BY_LANGUAGE.get(language_key)
    if tag is None:
        return []

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=15.0) as client:
        try:
            response = await client.get(API_URL, params={"tags": tag})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("RemoteOK fetch failed for tag %s: %s", tag, exc)
            return []

    try:
        data = response.json()
    except ValueError:
        logger.warning("RemoteOK returned non-JSON response for tag %s", tag)
        return []

    return [v for entry in data if (v := _parse_entry(entry)) is not None]
