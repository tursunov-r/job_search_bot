#!/usr/bin/env python3
"""Wipe all vacancies from the DB and re-parse everything from scratch.

Use this after fixing a parsing bug in one of the adapters — it replaces
whatever bad/incomplete data is already stored with freshly parsed data
using the current code, instead of waiting for old rows to drift out of
relevance on their own.

Subscribers are NOT resent anything: their delivery cursor is advanced to
"caught up" with the freshly re-inserted vacancies rather than reset to
zero, since this is a data-quality fix, not new content — resetting the
cursor to zero would re-flood every active subscriber with the entire
history.

Only re-parses the pollable sources (hh.ru, Habr Career, LinkedIn if
enabled) — Telegram channels aren't replayed, since that poller only ever
fetches messages newer than its stored per-channel cursor, not history;
anything that came in from a channel is gone for good once wiped here.

Run this on the Raspberry Pi, inside the bot's container:

    docker compose exec bot python reset_vacancies.py
"""
import asyncio
import logging

from sqlmodel import delete, select, update

from jobsbot.config import settings
from jobsbot.main import poll_habr, poll_hh, poll_linkedin
from jobsbot.storage.db import async_session, init_db
from jobsbot.storage.models import Subscriber, Vacancy, VacancyDelivery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def wipe_vacancies() -> None:
    async with async_session() as session:
        # Children referencing vacancies.id first (no ON DELETE CASCADE),
        # then the vacancies themselves.
        await session.execute(delete(VacancyDelivery))
        await session.execute(update(Subscriber).values(last_vacancy_sent_id=None))
        await session.execute(delete(Vacancy))
        await session.commit()
    logger.info("Wiped all vacancies, deliveries, and subscriber cursors.")


async def catch_up_subscribers() -> None:
    async with async_session() as session:
        result = await session.exec(select(Vacancy.id).order_by(Vacancy.id.desc()).limit(1))
        latest_id = result.first()
        if latest_id is None:
            return
        await session.execute(update(Subscriber).values(last_vacancy_sent_id=latest_id))
        await session.commit()
    logger.info("Advanced all subscriber cursors to vacancy #%s (no resend of re-parsed data).", latest_id)


async def main() -> None:
    await init_db()

    logger.info("Wiping existing vacancies...")
    await wipe_vacancies()

    logger.info("Re-parsing hh.ru...")
    await poll_hh()

    logger.info("Re-parsing Habr Career...")
    await poll_habr()

    if settings.linkedin_enabled:
        logger.info("Re-parsing LinkedIn...")
        await poll_linkedin()

    await catch_up_subscribers()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
