import asyncio
import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from jobsbot.ads.scheduler import broadcast_due_campaigns
from jobsbot.bot.dispatcher import build_bot, build_dispatcher
from jobsbot.bot.push import push_new_vacancies
from jobsbot.config import settings
from jobsbot.ingestion import habr_adapter, hh_adapter, linkedin_adapter
from jobsbot.ingestion.telegram_poller import TelegramChannelPoller
from jobsbot.processing.languages import LANGUAGES
from jobsbot.processing.pipeline import ingest
from jobsbot.storage.db import async_session, init_db
from jobsbot.storage.repo import get_or_create_source, update_vacancy_details

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def poll_hh_language(language_key: str) -> list:
    lang = LANGUAGES[language_key]
    try:
        raw_vacancies = await hh_adapter.fetch_vacancies(lang.hh_search_term)
    except Exception:
        logger.exception("HH polling failed for language %s", language_key)
        return []

    new_vacancies = []
    async with async_session() as session:
        source = await get_or_create_source(
            session, "hh", f"hh_search_{language_key}", f"hh.ru search ({lang.label})"
        )
        for raw in raw_vacancies:
            vacancy = await ingest(session, raw, source.id, language_hint=language_key, needs_details=True)
            if vacancy:
                new_vacancies.append(vacancy)
    logger.info(
        "HH poll [%s]: fetched %d, inserted %d new", language_key, len(raw_vacancies), len(new_vacancies)
    )
    return new_vacancies


async def poll_hh() -> None:
    all_new_vacancies = []
    language_keys = list(LANGUAGES.keys())
    for i, language_key in enumerate(language_keys):
        all_new_vacancies.extend(await poll_hh_language(language_key))
        if i < len(language_keys) - 1:
            await asyncio.sleep(hh_adapter.PAGE_DELAY_SECONDS)

    if not all_new_vacancies:
        return

    async with httpx.AsyncClient(
        headers={"User-Agent": hh_adapter.USER_AGENT}, timeout=15.0, follow_redirects=True
    ) as client:
        for i, vacancy in enumerate(all_new_vacancies):
            if not vacancy.url:
                continue
            details = await hh_adapter.fetch_vacancy_details(client, vacancy.url)
            async with async_session() as session:
                # Always update — even when details is None (fetch failed),
                # update_vacancy_details still marks details_checked=True so
                # push_new_vacancies doesn't hold this vacancy back forever.
                await update_vacancy_details(
                    session,
                    vacancy.id,
                    description=details.description if details else None,
                    experience=details.experience if details else None,
                    employment_type=details.employment_type if details else None,
                    schedule=details.schedule if details else None,
                    work_format=details.work_format if details else None,
                    salary_text=details.salary_text if details else None,
                )
            if i < len(all_new_vacancies) - 1:
                await asyncio.sleep(hh_adapter.DETAIL_FETCH_DELAY_SECONDS)


async def poll_habr_language(language_key: str) -> list:
    lang = LANGUAGES[language_key]
    try:
        raw_vacancies = await habr_adapter.fetch_vacancies(lang.hh_search_term)
    except Exception:
        logger.exception("Habr polling failed for language %s", language_key)
        return []

    new_vacancies = []
    async with async_session() as session:
        source = await get_or_create_source(
            session, "habr", f"habr_search_{language_key}", f"Habr Career search ({lang.label})"
        )
        for raw in raw_vacancies:
            vacancy = await ingest(session, raw, source.id, language_hint=language_key, needs_details=True)
            if vacancy:
                new_vacancies.append(vacancy)
    logger.info(
        "Habr poll [%s]: fetched %d, inserted %d new", language_key, len(raw_vacancies), len(new_vacancies)
    )
    return new_vacancies


async def poll_habr() -> None:
    all_new_vacancies = []
    language_keys = list(LANGUAGES.keys())
    for i, language_key in enumerate(language_keys):
        all_new_vacancies.extend(await poll_habr_language(language_key))
        if i < len(language_keys) - 1:
            await asyncio.sleep(habr_adapter.PAGE_DELAY_SECONDS)

    if not all_new_vacancies:
        return

    async with httpx.AsyncClient(
        headers={"User-Agent": habr_adapter.USER_AGENT}, timeout=15.0, follow_redirects=True
    ) as client:
        for i, vacancy in enumerate(all_new_vacancies):
            if not vacancy.url:
                continue
            details = await habr_adapter.fetch_vacancy_details(client, vacancy.url)
            async with async_session() as session:
                await update_vacancy_details(
                    session,
                    vacancy.id,
                    description=details.description if details else None,
                )
            if i < len(all_new_vacancies) - 1:
                await asyncio.sleep(habr_adapter.DETAIL_FETCH_DELAY_SECONDS)


async def poll_linkedin() -> None:
    try:
        raw_vacancies = await linkedin_adapter.fetch_vacancies()
    except Exception:
        logger.exception("LinkedIn polling failed")
        return

    async with async_session() as session:
        source = await get_or_create_source(session, "linkedin", "linkedin_search", "LinkedIn search")
        inserted = 0
        for raw in raw_vacancies:
            vacancy = await ingest(session, raw, source.id, language_hint="python")
            if vacancy:
                inserted += 1
        logger.info("LinkedIn poll: fetched %d, inserted %d new", len(raw_vacancies), inserted)


async def main() -> None:
    await init_db()

    bot = build_bot()
    dispatcher = build_dispatcher()

    telegram_poller = None
    if settings.telegram_enabled:
        telegram_poller = TelegramChannelPoller()
        await telegram_poller.start()
    else:
        logger.warning("TELEGRAM_API_ID/TELEGRAM_API_HASH not set — Telegram channel parsing disabled")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_hh, "interval", seconds=settings.hh_poll_interval_seconds)
    scheduler.add_job(poll_habr, "interval", seconds=settings.habr_poll_interval_seconds)
    if settings.linkedin_enabled:
        scheduler.add_job(poll_linkedin, "interval", seconds=settings.linkedin_poll_interval_seconds)
    if telegram_poller is not None:
        scheduler.add_job(
            telegram_poller.poll_once, "interval", seconds=settings.telegram_poll_interval_seconds
        )
    scheduler.add_job(
        push_new_vacancies,
        "interval",
        seconds=settings.vacancy_push_interval_seconds,
        args=[bot],
    )
    scheduler.add_job(
        broadcast_due_campaigns,
        "interval",
        seconds=settings.ad_broadcast_check_interval_seconds,
        args=[bot],
    )
    scheduler.start()

    # Run the first poll in the background instead of awaiting it here —
    # on a fresh DB this can mean hundreds of new vacancies, each with its
    # own delayed HH detail-page fetch, which took minutes. Blocking on
    # that before start_polling() meant the bot didn't respond to any
    # message (not even /start) until the whole thing finished.
    background_tasks: set[asyncio.Task] = set()

    def _track(task: asyncio.Task) -> None:
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    _track(asyncio.create_task(poll_hh()))
    _track(asyncio.create_task(poll_habr()))
    if settings.linkedin_enabled:
        _track(asyncio.create_task(poll_linkedin()))
    if telegram_poller is not None:
        _track(asyncio.create_task(telegram_poller.poll_once()))

    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        if telegram_poller is not None:
            await telegram_poller.stop()


if __name__ == "__main__":
    asyncio.run(main())
