import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter

from jobsbot.bot.push import build_vacancy_keyboard, format_vacancy
from jobsbot.config import settings
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import (
    get_topics_by_thread,
    get_vacancies_pending_group_post,
    record_group_topic_post,
)

logger = logging.getLogger(__name__)

# All topics post into the same group chat_id, so Telegram's per-chat rate
# limit (roughly 20 msg/min) applies across every topic combined, not per
# topic — without pacing, one topic's backlog burns through the whole
# budget and every other topic's very first send instantly hits
# TelegramRetryAfter, every single cycle.
POST_DELAY_SECONDS = 2.0


async def post_new_vacancies_to_topics(bot: Bot) -> None:
    """Every new vacancy gets posted into the forum topic mapped to each of
    its languages — independent of any subscriber's personal filters (city,
    stack, work format, etc.), since this is a shared group feed, not a
    per-person one."""
    if not settings.group_chat_id:
        return

    async with async_session() as session:
        topics_by_thread = await get_topics_by_thread(session)
    if not topics_by_thread:
        return

    for thread_id, language_keys in topics_by_thread.items():
        try:
            async with async_session() as session:
                vacancies = await get_vacancies_pending_group_post(session, thread_id, language_keys)
                for vacancy in vacancies:
                    try:
                        await bot.send_message(
                            settings.group_chat_id,
                            format_vacancy(vacancy),
                            message_thread_id=thread_id,
                            parse_mode="HTML",
                            reply_markup=build_vacancy_keyboard(vacancy),
                        )
                        await record_group_topic_post(session, vacancy.id, thread_id)
                    except TelegramRetryAfter as exc:
                        # The limit is per-chat, shared by every topic — moving
                        # on to the next topic would just hit the same wall
                        # immediately, so stop the whole cycle here instead of
                        # burning through every remaining topic for nothing.
                        # The next scheduled run picks up right where this
                        # left off (get_vacancies_pending_group_post skips
                        # whatever already got recorded).
                        logger.warning(
                            "Rate limited posting to group topic %s, retry after %s — stopping this cycle",
                            thread_id,
                            exc.retry_after,
                        )
                        return
                    except Exception:
                        # Covers a failed record (e.g. a unique-constraint race
                        # from a concurrent run) — one bad vacancy must not
                        # abort every other topic. Roll back so the session is
                        # still usable for the rest of this topic's vacancies.
                        await session.rollback()
                        logger.exception("Failed to post vacancy %s to topic %s", vacancy.id, thread_id)
                        continue
                    await asyncio.sleep(POST_DELAY_SECONDS)
        except Exception:
            logger.exception("Failed to process group topic %s", thread_id)
            continue
