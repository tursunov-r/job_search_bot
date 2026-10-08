"""Geekjob.ru public HTML listing parser.

Unlike HH.ru/Habr, the "qs" keyword search box is client-side only (a Vue
app — see /app/filters/vacancies/app.js — backed by /json/ and /rest/
endpoints that robots.txt explicitly disallows): fetching
/vacancies?qs=python plain returns the exact same unfiltered page every
time. So there's no per-language search term to loop over here — this
adapter just pages through the single unfiltered listing (same as a
Telegram channel) and leaves relevance detection to
processing/languages.py::detect_languages() against title+description,
instead of trusting a search-term language_hint.

The listing page gives title/company/url/salary/location plus an English
remote/office badge; the detail page repeats work format and experience
in Russian (consistent with HH/Habr's own wording) and is always fetched
anyway for the description, so that's used as the final work_format/
experience value — the listing's badge is just an immediate best-guess
available before that fetch happens.
"""

import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.lexbor import LexborHTMLParser

from jobsbot.ingestion.base import RawVacancy

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

BASE_URL = "https://geekjob.ru"
MAX_PAGES = 3
PAGE_DELAY_SECONDS = 2.0
DETAIL_FETCH_DELAY_SECONDS = 1.5


def _canonical_url(href: str) -> str:
    parsed = urlparse(urljoin(BASE_URL, href))
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _clean_text(text: str) -> str | None:
    text = " ".join(text.split())
    return text or None


def _listing_work_format(card) -> str | None:
    labels = {s.attributes.get("class") for s in card.css('span[class$="-label"]')}
    remote = "remote-label" in labels
    inhouse = "inhouse-label" in labels
    if remote and inhouse:
        return "на месте работодателя или удалённо"
    if remote:
        return "удалённо"
    if inhouse:
        return "на месте работодателя"
    return None


def _parse_page(html: str) -> list[RawVacancy]:
    tree = LexborHTMLParser(html)
    vacancies: list[RawVacancy] = []

    for card in tree.css("ul.serp-list li.collection-item"):
        title_link = card.css_first("p.vacancy-name a.title")
        if title_link is None:
            continue

        href = title_link.attributes.get("href") or ""
        title = _clean_text(title_link.text()) or ""

        company_node = card.css_first("p.company-name a")
        company = _clean_text(company_node.text()) if company_node else None

        info_link = card.css_first("div.info a")
        location = _clean_text(info_link.text(deep=False)) if info_link else None
        salary_node = card.css_first("div.info span.salary")
        salary_text = _clean_text(salary_node.text()) if salary_node else None

        vacancies.append(
            RawVacancy(
                title=title,
                description=None,
                url=_canonical_url(href) if href else None,
                company=company,
                salary_text=salary_text,
                location=location,
                work_format=_listing_work_format(card),
                experience=None,
                employment_type=None,
                schedule=None,
                posted_at=None,
            )
        )

    return vacancies


@dataclass
class GeekjobVacancyDetails:
    description: str | None = None
    work_format: str | None = None
    experience: str | None = None


def _parse_vacancy_details(html: str) -> GeekjobVacancyDetails:
    tree = LexborHTMLParser(html)

    desc_node = tree.css_first("#vacancy-description")
    description = _clean_text(desc_node.text(separator=" ")) if desc_node else None

    work_format = experience = None
    jobformat_node = tree.css_first(".jobformat")
    if jobformat_node is not None:
        lines = [line.strip() for line in jobformat_node.text(deep=True).split("\n") if line.strip()]
        if lines:
            work_format = lines[0]
        if len(lines) > 1:
            experience = lines[1]

    return GeekjobVacancyDetails(description=description, work_format=work_format, experience=experience)


async def fetch_vacancy_details(client: httpx.AsyncClient, url: str) -> GeekjobVacancyDetails | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Geekjob vacancy detail fetch failed for %s: %s", url, exc)
        return None
    return _parse_vacancy_details(response.text)


async def fetch_vacancies() -> list[RawVacancy]:
    results: list[RawVacancy] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=True
    ) as client:
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE_URL}/vacancies" if page == 1 else f"{BASE_URL}/vacancies/{page}"
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Geekjob page %d fetch failed: %s", page, exc)
                break

            page_vacancies = _parse_page(response.text)
            if not page_vacancies:
                break
            results.extend(page_vacancies)

            if page < MAX_PAGES:
                await asyncio.sleep(PAGE_DELAY_SECONDS)

    return results
