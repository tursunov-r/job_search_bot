"""HH.ru search-results HTML parser.

HH.ru's official API now requires a paid/approved commercial subscription for
this kind of aggregation use case, so this adapter instead parses the public
search-results page (``hh.ru/search/vacancy``) directly, the same way the
LinkedIn adapter parses public search pages: no login, conservative request
pacing, and isolated behind its own module so it can be swapped out easily.

The search-results page does not render a job description snippet (HH moved
that into the per-vacancy detail page), so the listing parser leaves
``description`` as ``None`` — fetching it for every search result would be
too heavy for a polling MVP. Instead, ``fetch_description`` is called once
per vacancy, but only for vacancies that already passed the keyword filter
and dedup and got inserted as genuinely new rows (see ``main.py::poll_hh``),
so the extra per-item request only happens for real new postings, not the
whole search result set.
"""

import asyncio
import logging
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

SEARCH_QUERY = "python"
AREA_RUSSIA = "113"
MAX_PAGES = 2
PAGE_DELAY_SECONDS = 2.0
DETAIL_FETCH_DELAY_SECONDS = 1.5


def _canonical_url(href: str) -> str:
    parsed = urlparse(href)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


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

        vacancies.append(
            RawVacancy(
                title=title,
                description=None,
                url=_canonical_url(urljoin("https://hh.ru", href)) if href else None,
                company=company,
                salary_text=None,
                location=location,
                posted_at=None,
            )
        )

    return vacancies


def _parse_description(html: str) -> str | None:
    tree = LexborHTMLParser(html)
    node = tree.css_first('[data-qa="vacancy-description"]')
    if node is None:
        return None
    text = node.text(separator=" ").strip()
    return text or None


async def fetch_description(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("HH vacancy detail fetch failed for %s: %s", url, exc)
        return None
    return _parse_description(response.text)


async def fetch_vacancies() -> list[RawVacancy]:
    results: list[RawVacancy] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=True
    ) as client:
        for page in range(MAX_PAGES):
            try:
                response = await client.get(
                    settings.hh_search_url,
                    params={"text": SEARCH_QUERY, "area": AREA_RUSSIA, "page": page},
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
