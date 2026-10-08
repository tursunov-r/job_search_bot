"""HH.ru search-results HTML parser.

HH.ru's official API now requires a paid/approved commercial subscription for
this kind of aggregation use case, so this adapter instead parses the public
search-results page (``hh.ru/search/vacancy``) directly, the same way the
LinkedIn adapter parses public search pages: no login, conservative request
pacing, and isolated behind its own module so it can be swapped out easily.

The search-results page does not render a job description snippet (HH moved
that into the per-vacancy detail page), so the listing parser leaves
``description`` as ``None`` — fetching it for every search result would be
too heavy for a polling MVP. Instead, ``fetch_vacancy_details`` is called
once per vacancy, but only for vacancies that already passed the relevance
filter and dedup and got inserted as genuinely new rows (see
``main.py::poll_hh``), so the extra per-item request only happens for real
new postings, not the whole search result set. That same detail-page request
also picks up structured fields (experience, employment type, schedule, work
format) that aren't present on the listing page at all.
"""

import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.lexbor import LexborHTMLParser

from jobsbot.config import settings
from jobsbot.ingestion.base import RawVacancy

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

MAX_PAGES = 2
PAGE_DELAY_SECONDS = 2.0
DETAIL_FETCH_DELAY_SECONDS = 1.5


def _canonical_url(href: str) -> str:
    parsed = urlparse(href)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _normalize_whitespace(text: str) -> str:
    # HH uses nbsp/narrow-nbsp as thousand separators and word spacing in
    # salary text -- collapse all whitespace variants to plain spaces.
    return " ".join(text.split())


def _parse_salary(article) -> str | None:
    """The listing page renders salary as <data value="..."> tags inside a
    plain <span> next to the title — no data-qa attribute to hook onto, so
    we walk up from the first <data> tag to its nearest <span> ancestor and
    take that span's full text."""
    data_node = article.css_first("data")
    if data_node is None:
        return None
    node = data_node.parent
    while node is not None and node.tag != "span":
        node = node.parent
    if node is None:
        return None
    text = _normalize_whitespace(node.text(deep=True))
    return text or None


def _parse_page(html: str) -> list[RawVacancy]:
    tree = LexborHTMLParser(html)
    vacancies: list[RawVacancy] = []

    for article in tree.css('article[data-qa="vacancy-serp__vacancy"]'):
        title_link = article.css_first('a[data-qa="serp-item__title"]')
        if title_link is None:
            continue

        href = title_link.attributes.get("href") or ""
        title_text_node = article.css_first('[data-qa="serp-item__title-text"]')
        title = (title_text_node.text() if title_text_node else title_link.text()).strip()

        employer_node = article.css_first('[data-qa="vacancy-serp__vacancy-employer-text"]')
        company = employer_node.text().strip() if employer_node else None

        address_node = article.css_first('[data-qa="vacancy-serp__vacancy-address"]')
        location = address_node.text().strip() if address_node else None

        salary_text = _parse_salary(article)

        vacancies.append(
            RawVacancy(
                title=title,
                description=None,
                url=_canonical_url(urljoin("https://hh.ru", href)) if href else None,
                company=company,
                salary_text=salary_text,
                location=location,
                posted_at=None,
            )
        )

    return vacancies


@dataclass
class VacancyDetails:
    description: str | None = None
    experience: str | None = None
    employment_type: str | None = None
    schedule: str | None = None
    work_format: str | None = None
    salary_text: str | None = None


def _text_or_none(tree: LexborHTMLParser, selector: str) -> str | None:
    node = tree.css_first(selector)
    if node is None:
        return None
    text = _normalize_whitespace(node.text(separator=" "))
    return text or None


def _parse_vacancy_details(html: str) -> VacancyDetails:
    tree = LexborHTMLParser(html)

    schedule_text = _text_or_none(tree, '[data-qa="work-schedule-by-days-text"]')
    if schedule_text:
        # "График: 5/2" -> "5/2"; append working hours if present ("8" -> "5/2, 8 часов")
        schedule_text = schedule_text.split(":", 1)[-1].strip()
        hours_text = _text_or_none(tree, '[data-qa="working-hours-text"]')
        if hours_text:
            hours = hours_text.split(":", 1)[-1].strip()
            schedule_text = f"{schedule_text}, {hours} часов"

    work_format = _text_or_none(tree, '[data-qa="work-formats-text"]')
    if work_format:
        work_format = work_format.split(":", 1)[-1].strip()

    return VacancyDetails(
        description=_text_or_none(tree, '[data-qa="vacancy-description"]'),
        experience=_text_or_none(tree, '[data-qa="vacancy-experience"]'),
        employment_type=_text_or_none(tree, '[data-qa="common-employment-text"]'),
        schedule=schedule_text,
        work_format=work_format,
        # Fallback for listing cards without a salary — the detail page has
        # its own stable selector, unlike the listing's data-tag walk-up.
        salary_text=_text_or_none(tree, '[data-qa="vacancy-salary"]'),
    )


async def fetch_vacancy_details(client: httpx.AsyncClient, url: str) -> VacancyDetails | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("HH vacancy detail fetch failed for %s: %s", url, exc)
        return None
    return _parse_vacancy_details(response.text)


async def fetch_vacancies(search_term: str) -> list[RawVacancy]:
    results: list[RawVacancy] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=True
    ) as client:
        for page in range(MAX_PAGES):
            try:
                response = await client.get(
                    settings.hh_search_url,
                    # No "area" param — without it HH searches all countries
                    # (Russia, Kazakhstan, Belarus, etc.), not just Russia.
                    params={"text": search_term, "page": page},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("HH page %d fetch failed: %s", page, exc)
                break

            page_vacancies = _parse_page(response.text)
            if not page_vacancies:
                break
            results.extend(page_vacancies)

            if page < MAX_PAGES - 1:
                await asyncio.sleep(PAGE_DELAY_SECONDS)

    return results
