#!/usr/bin/env python3
"""One-time baseline for the group-topic broadcast feature.

Marks every *currently existing* vacancy as already posted to its mapped
topic(s), without actually sending anything — so bot/group_broadcast.py's
"pending" query only ever picks up genuinely new vacancies from here on,
instead of working through the entire historical backlog (which, run
unthrottled against Telegram's per-chat rate limit, would take ages and
flood the group with hundreds of old, stale postings).

Safe to run again later (ON CONFLICT DO NOTHING) — e.g. after adding a
new topic mapping, to skip its backlog the same way.

Run this on the Raspberry Pi, inside the bot's container:

    docker compose exec bot python backfill_group_topic_baseline.py
"""
import asyncio
import logging

from sqlalchemy import text

from jobsbot.storage.db import async_session, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASELINE_SQL = text(
    """
    INSERT INTO group_topic_posts (vacancy_id, thread_id, posted_at)
    SELECT DISTINCT v.id, gt.thread_id, now()
    FROM vacancies v
    JOIN group_topics gt ON v.languages LIKE '%"' || gt.language_key || '"%'
    WHERE v.hidden = false
    ON CONFLICT (vacancy_id, thread_id) DO NOTHING
    """
)


async def main() -> None:
    await init_db()
    async with async_session() as session:
        result = await session.execute(BASELINE_SQL)
        await session.commit()
    logger.info("Baseline set — %d (vacancy, topic) rows marked as already posted.", result.rowcount)


if __name__ == "__main__":
    asyncio.run(main())
