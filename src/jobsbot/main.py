import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from jobsbot.bot.dispatcher import build_bot, build_dispatcher
from jobsbot.bot.push import push_new_vacancies
from jobsbot.config import settings
from jobsbot.ingestion.hh_adapter import fetch_vacancies
from jobsbot.ingestion.telegram_listener import TelegramChannelListener
from jobsbot.processing.pipeline import ingest
from jobsbot.storage.db import async_session, init_db
from jobsbot.storage.repo import get_or_create_source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def poll_hh() -> None:
    try:
        raw_vacancies = await fetch_vacancies()
    except Exception:
        logger.exception("HH polling failed")
        return

    async with async_session() as session:
        source = await get_or_create_source(session, "hh", "hh_search", "hh.ru search")
        inserted = 0
        for raw in raw_vacancies:
            vacancy = await ingest(session, raw, source.id)
            if vacancy:
                inserted += 1
        logger.info("HH poll: fetched %d, inserted %d new", len(raw_vacancies), inserted)


async def main() -> None:
    await init_db()

    bot = build_bot()
    dispatcher = build_dispatcher()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_hh, "interval", seconds=settings.hh_poll_interval_seconds)
    scheduler.add_job(
        push_new_vacancies,
        "interval",
        seconds=settings.vacancy_push_interval_seconds,
        args=[bot],
    )
    scheduler.start()

    await poll_hh()

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
