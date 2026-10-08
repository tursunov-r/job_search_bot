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
                except TelegramRetryAfter as exc:
                    logger.warning("Rate limited posting to group topic %s, retry after %s", thread_id, exc.retry_after)
                    break
                except Exception:
                    logger.exception("Failed to post vacancy %s to topic %s", vacancy.id, thread_id)
                    continue
                await record_group_topic_post(session, vacancy.id, thread_id)
