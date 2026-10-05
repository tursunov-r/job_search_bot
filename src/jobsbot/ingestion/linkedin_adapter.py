"""LinkedIn public job-search adapter.

Deliberately the most isolated and riskiest adapter in the system:
LinkedIn's ToS forbids scraping more aggressively than most sites, and they
do enforce against it (unlike HH, there's real precedent here). To keep the
blast radius small:

  * no login/session/cookies at all — only the public, unauthenticated
    "guest" job-search endpoint anyone can load without an account;
  * entirely behind the ``LINKEDIN_ENABLED`` flag (default ``false``) — can
    be killed instantly without touching any other adapter;
  * conservative pacing: random jittered delay between requests and
    exponential backoff on non-200 responses, so a single misbehaving run
    doesn't hammer LinkedIn.

If LinkedIn starts blocking/CAPTCHA-walling this endpoint, the right move is
to turn the flag off, not to try to work around it (e.g. no headless
browser, no login wall bypass).
"""

import asyncio
import logging
import random
from urllib.parse import urlparse

import httpx
from selectolax.lexbor import LexborHTMLParser

from jobsbot.ingestion.base import RawVacancy

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
SEARCH_KEYWORDS = "python"
SEARCH_LOCATION = "Russia"
RESULTS_PER_PAGE = 25
MAX_PAGES = 2

MIN_DELAY_SECONDS = 3.0
MAX_DELAY_SECONDS = 7.0
MAX_RETRIES = 2
BACKOFF_BASE_SECONDS = 5.0


def _canonical_url(href: str) -> str | None:
    if not href:
        return None
    parsed = urlparse(href)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _parse_page(html: str) -> list[RawVacancy]:
    tree = LexborHTMLParser(html)
    vacancies: list[RawVacancy] = []

    for card in tree.css("div.job-search-card"):
        title_node = card.css_first(".base-search-card__title")
        if title_node is None:
            continue
        title = title_node.text().strip()

        company_node = card.css_first(".base-search-card__subtitle")
        company = company_node.text().strip() if company_node else None

        location_node = card.css_first(".job-search-card__location")
        location = location_node.text().strip() if location_node else None

        link_node = card.css_first("a.base-card__full-link")
        url = _canonical_url(link_node.attributes.get("href")) if link_node else None

        vacancies.append(
            RawVacancy(
                title=title,
                description=None,
                url=url,
                company=company,
                salary_text=None,
                location=location,
                posted_at=None,
            )
        )

    return vacancies


async def _jittered_sleep() -> None:
    await asyncio.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))


async def _fetch_page(client: httpx.AsyncClient, start: int) -> str | None:
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.get(
                SEARCH_URL,
                params={"keywords": SEARCH_KEYWORDS, "location": SEARCH_LOCATION, "start": start},
            )
            if response.status_code == 200:
                return response.text
            logger.warning("LinkedIn page start=%d returned HTTP %d", start, response.status_code)
        except httpx.HTTPError as exc:
            logger.warning("LinkedIn page start=%d fetch failed: %s", start, exc)

        if attempt < MAX_RETRIES:
            backoff = BACKOFF_BASE_SECONDS * (2**attempt) + random.uniform(0, 2.0)
            await asyncio.sleep(backoff)

    return None


async def fetch_vacancies() -> list[RawVacancy]:
    results: list[RawVacancy] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=True
    ) as client:
        for page in range(MAX_PAGES):
            start = page * RESULTS_PER_PAGE
            html = await _fetch_page(client, start)
            if html is None:
                break

            page_vacancies = _parse_page(html)
            if not page_vacancies:
                break
            results.extend(page_vacancies)

            if page < MAX_PAGES - 1:
                await _jittered_sleep()

    return results
