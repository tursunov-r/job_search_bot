import asyncio
import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from jobsbot.ads.scheduler import broadcast_due_campaigns
from jobsbot.bot.dispatcher import build_bot, build_dispatcher
from jobsbot.bot.push import push_new_vacancies
from jobsbot.config import settings
from jobsbot.ingestion import hh_adapter, linkedin_adapter
from jobsbot.ingestion.telegram_listener import TelegramChannelListener
from jobsbot.processing.pipeline import ingest
from jobsbot.storage.db import async_session, init_db
from jobsbot.storage.repo import get_or_create_source, update_vacancy_description

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def poll_hh() -> None:
    try:
        raw_vacancies = await hh_adapter.fetch_vacancies()
    except Exception:
        logger.exception("HH polling failed")
        return

    new_vacancies = []
    async with async_session() as session:
        source = await get_or_create_source(session, "hh", "hh_search", "hh.ru search")
        for raw in raw_vacancies:
            vacancy = await ingest(session, raw, source.id)
            if vacancy:
                new_vacancies.append(vacancy)
        logger.info("HH poll: fetched %d, inserted %d new", len(raw_vacancies), len(new_vacancies))

    if not new_vacancies:
        return

    async with httpx.AsyncClient(
        headers={"User-Agent": hh_adapter.USER_AGENT}, timeout=15.0, follow_redirects=True
    ) as client:
        for i, vacancy in enumerate(new_vacancies):
            if not vacancy.url:
                continue
            description = await hh_adapter.fetch_description(client, vacancy.url)
            if description:
                async with async_session() as session:
                    await update_vacancy_description(session, vacancy.id, description)
            if i < len(new_vacancies) - 1:
                await asyncio.sleep(hh_adapter.DETAIL_FETCH_DELAY_SECONDS)


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
            vacancy = await ingest(session, raw, source.id)
            if vacancy:
                inserted += 1
        logger.info("LinkedIn poll: fetched %d, inserted %d new", len(raw_vacancies), inserted)


async def main() -> None:
    await init_db()

    bot = build_bot()
    dispatcher = build_dispatcher()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_hh, "interval", seconds=settings.hh_poll_interval_seconds)
    if settings.linkedin_enabled:
        scheduler.add_job(poll_linkedin, "interval", seconds=settings.linkedin_poll_interval_seconds)
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

    await poll_hh()
    if settings.linkedin_enabled:
        await poll_linkedin()

    telegram_listener = TelegramChannelListener()
    await telegram_listener.start()

    tasks = [dispatcher.start_polling(bot)]
    if telegram_listener.enabled:
        tasks.append(telegram_listener.run_forever())

    try:
        await asyncio.gather(*tasks)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await telegram_listener.stop()


if __name__ == "__main__":
    asyncio.run(main())
