"""Habr Career (career.habr.com) public search-results HTML parser.

Same spirit as hh_adapter.py: no login, no API, just the public search page
anyone can load in a browser. robots.txt disallows only a handful of
sub-paths (/vacancies/*/responses, /vacancies/*/suitable_users, etc.) —
/vacancies itself (listing and detail pages) is not disallowed, so the risk
profile here is comparable to HH.ru, not LinkedIn.

The listing page gives title/company/url plus three optional chips
(experience grade, location, work format) and a salary that's either a real
stated figure (.basic-salary) or Habr's own algorithmic guess
(.predicted-salary, with "Зарплата не указана, похожие специалисты
получают..."). Only the real one is used — showing an algorithmic estimate
as if it were the stated salary would be misleading.

Employment type / schedule aren't exposed anywhere as a structured field on
Habr (only buried in an SEO <meta name="description"> string on the detail
page) — left None, same as LinkedIn.
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

BASE_URL = "https://career.habr.com"
SEARCH_URL = f"{BASE_URL}/vacancies"
MAX_PAGES = 3
PAGE_DELAY_SECONDS = 2.0
DETAIL_FETCH_DELAY_SECONDS = 1.5


def _canonical_url(href: str) -> str:
    parsed = urlparse(urljoin(BASE_URL, href))
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _clean_text(text: str) -> str | None:
    text = " ".join(text.split())
    return text or None


def _parse_salary(card) -> str | None:
    # Deliberately only .basic-salary (a real stated figure) — Habr's
    # .predicted-salary is an algorithmic guess shown when no real salary
    # was given, and presenting that as if it were stated would mislead.
    node = card.css_first(".basic-salary")
    if node is None:
        return None
    return _clean_text(node.text(separator=" "))


def _parse_meta_chips(card) -> tuple[str | None, str | None, str | None]:
    """Returns (experience, location, work_format) — distinguished by the
    chip's icon (icon-grade / icon-placemark / icon-format), not position,
    since not every card has all three."""
    experience = location = work_format = None
    for chip in card.css(".vacancy-meta .basic-chip"):
        icon = chip.css_first("svg")
        text_node = chip.css_first(".chip-with-icon__text")
        if icon is None or text_node is None:
            continue
        icon_class = icon.attributes.get("class") or ""
        text = _clean_text(text_node.text())
        if "icon-grade" in icon_class:
            experience = text
        elif "icon-format" in icon_class:
            work_format = text
        elif "icon-placemark" in icon_class:
            location = text
    return experience, location, work_format


def _parse_page(html: str) -> list[RawVacancy]:
    tree = LexborHTMLParser(html)
    vacancies: list[RawVacancy] = []

    for card in tree.css("div.vacancy-card"):
        title_link = card.css_first("a.vacancy-card__title-link")
        if title_link is None:
            continue

        href = title_link.attributes.get("href") or ""
        title = _clean_text(title_link.text()) or ""

        company_node = card.css_first(".vacancy-card__company a")
        company = _clean_text(company_node.text()) if company_node else None

        salary_text = _parse_salary(card)
        experience, location, work_format = _parse_meta_chips(card)

        vacancies.append(
            RawVacancy(
                title=title,
                description=None,
                url=_canonical_url(href) if href else None,
                company=company,
                salary_text=salary_text,
                location=location,
                work_format=work_format,
                experience=experience,
                employment_type=None,
                schedule=None,
                posted_at=None,
            )
        )

    return vacancies


@dataclass
class HabrVacancyDetails:
    description: str | None = None


def _parse_vacancy_details(html: str) -> HabrVacancyDetails:
    tree = LexborHTMLParser(html)
    node = tree.css_first(".vacancy-description__text")
    if node is None:
        return HabrVacancyDetails()
    return HabrVacancyDetails(description=_clean_text(node.text(separator=" ")))


async def fetch_vacancy_details(client: httpx.AsyncClient, url: str) -> HabrVacancyDetails | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Habr vacancy detail fetch failed for %s: %s", url, exc)
        return None
    return _parse_vacancy_details(response.text)


async def fetch_vacancies(search_term: str) -> list[RawVacancy]:
    results: list[RawVacancy] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=True
    ) as client:
        for page in range(1, MAX_PAGES + 1):
            try:
                response = await client.get(
                    SEARCH_URL, params={"q": search_term, "type": "all", "page": page}
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("Habr page %d fetch failed: %s", page, exc)
                break

            page_vacancies = _parse_page(response.text)
            if not page_vacancies:
                break
            results.extend(page_vacancies)

            if page < MAX_PAGES:
                await asyncio.sleep(PAGE_DELAY_SECONDS)

    return results
