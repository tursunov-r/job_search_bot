#!/usr/bin/env python3
"""Set up (or update) which group forum topic each language posts new
vacancies into — see GroupTopic / bot/group_broadcast.py.

This is the current mapping as configured by hand (no admin-bot UI for it
yet, just a script to re-run after changing TOPICS below) — idempotent,
safe to run again after editing the mapping.

Run this on the Raspberry Pi, inside the bot's container:

    docker compose exec bot python seed_group_topics.py
"""
import asyncio
import logging

from jobsbot.storage.db import async_session, init_db
from jobsbot.storage.repo import set_group_topic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# language_key -> forum topic thread_id (from a https://t.me/c/<id>/<thread_id>
# link). More than one language can point at the same thread_id — all three
# mobile languages share one "Mobile" topic here.
TOPICS: dict[str, int] = {
    "python": 2,
    "javascript": 5,
    "java": 4,
    "kotlin": 24,
    "swift": 24,
    "dart": 24,
    "csharp": 21,
    "cpp": 22,
    "sql": 6,
    "sysadmin": 25,
    "devops": 16,
    "ruby": 88,
    "php": 90,
    "go": 91,
    "qa": 92,
}


async def main() -> None:
    await init_db()
    async with async_session() as session:
        for language_key, thread_id in TOPICS.items():
            await set_group_topic(session, language_key, thread_id)
            logger.info("%s -> thread %s", language_key, thread_id)
    logger.info("Done — %d topics configured.", len(TOPICS))


if __name__ == "__main__":
    asyncio.run(main())
