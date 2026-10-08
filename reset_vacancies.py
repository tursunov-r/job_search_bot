#!/usr/bin/env python3
"""Wipe all vacancies from the DB and re-parse everything from scratch.

Use this after fixing a parsing bug in one of the adapters — it replaces
whatever bad/incomplete data is already stored with freshly parsed data
using the current code, instead of waiting for old rows to drift out of
relevance on their own.

Nothing gets resent: subscriber DM cursors are advanced to "caught up"
with the freshly re-inserted vacancies, and every re-parsed vacancy is
baselined as already-posted for the group-topic broadcast (see
backfill_group_topic_baseline.py) — rather than resetting either to
zero/empty, since this is a data-quality fix, not new content.

Only re-parses the pollable sources (hh.ru, Habr Career, Geekjob.ru,
LinkedIn if enabled) — Telegram channels aren't replayed, since that
poller only ever fetches messages newer than its stored per-channel
cursor, not history; anything that came in from a channel is gone for
good once wiped here.

Run this on the Raspberry Pi, inside the bot's container:

    docker compose exec bot python reset_vacancies.py
"""
import asyncio
import logging

from sqlmodel import delete, select, update

from backfill_group_topic_baseline import BASELINE_SQL
from jobsbot.config import settings
from jobsbot.main import poll_geekjob, poll_habr, poll_hh, poll_linkedin
from jobsbot.storage.db import async_session, init_db
from jobsbot.storage.models import GroupTopicPost, Subscriber, Vacancy, VacancyDelivery, VacancyReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def wipe_vacancies() -> None:
    async with async_session() as session:
        # Children referencing vacancies.id first (no ON DELETE CASCADE),
        # then the vacancies themselves.
        await session.execute(delete(VacancyDelivery))
        await session.execute(delete(VacancyReport))
        await session.execute(delete(GroupTopicPost))
        await session.execute(update(Subscriber).values(last_vacancy_sent_id=None))
        await session.execute(delete(Vacancy))
        await session.commit()
    logger.info("Wiped all vacancies, deliveries, reports, group-topic posts, and subscriber cursors.")


async def catch_up_subscribers() -> None:
    async with async_session() as session:
        result = await session.exec(select(Vacancy.id).order_by(Vacancy.id.desc()).limit(1))
        latest_id = result.first()
        if latest_id is None:
            return
        await session.execute(update(Subscriber).values(last_vacancy_sent_id=latest_id))
        await session.commit()
    logger.info("Advanced all subscriber cursors to vacancy #%s (no resend of re-parsed data).", latest_id)


async def baseline_group_topics() -> None:
    """Same reasoning as catch_up_subscribers, but for the group-topic
    broadcast: every freshly re-parsed vacancy would otherwise look brand
    new to it and get flooded out to every mapped topic from scratch."""
    async with async_session() as session:
        result = await session.execute(BASELINE_SQL)
        await session.commit()
    logger.info("Baselined %d (vacancy, topic) rows (no resend of re-parsed data).", result.rowcount)


async def main() -> None:
    await init_db()

    logger.info("Wiping existing vacancies...")
    await wipe_vacancies()

    logger.info("Re-parsing hh.ru...")
    await poll_hh()

    logger.info("Re-parsing Habr Career...")
    await poll_habr()

    logger.info("Re-parsing Geekjob.ru...")
    await poll_geekjob()

    if settings.linkedin_enabled:
        logger.info("Re-parsing LinkedIn...")
        await poll_linkedin()

    await catch_up_subscribers()
    await baseline_group_topics()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
