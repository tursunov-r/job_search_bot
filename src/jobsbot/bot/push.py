import json
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from jobsbot.processing.stack_tags import matches_stack
from jobsbot.storage.db import async_session
from jobsbot.storage.models import Subscriber, Vacancy
from jobsbot.storage.repo import (
    get_active_subscribers,
    get_pending_vacancies_for_subscriber,
    mark_subscriber_cursor,
)

logger = logging.getLogger(__name__)


def format_vacancy(vacancy: Vacancy) -> str:
    lines = [f"<b>{vacancy.title}</b>"]
    if vacancy.company:
        lines.append(vacancy.company)
    if vacancy.location:
        lines.append(vacancy.location)
    if vacancy.salary_text:
        lines.append(vacancy.salary_text)
    if vacancy.url:
        lines.append(vacancy.url)
    return "\n".join(lines)


def _subscriber_skills(subscriber: Subscriber) -> list[str]:
    try:
        return json.loads(subscriber.skills)
    except (TypeError, ValueError):
        return []


async def push_new_vacancies(bot: Bot) -> None:
    async with async_session() as session:
        subscribers = await get_active_subscribers(session)
        for subscriber in subscribers:
            vacancies = await get_pending_vacancies_for_subscriber(session, subscriber)
            if not vacancies:
                continue

            selected_skills = _subscriber_skills(subscriber)
            cursor_id = subscriber.last_vacancy_sent_id

            for vacancy in vacancies:
                if not matches_stack(vacancy.title, vacancy.description, selected_skills):
                    # Skipped on purpose (doesn't match the subscriber's stack) —
                    # still advance the cursor so it isn't re-checked every cycle.
                    cursor_id = vacancy.id
                    continue

                try:
                    await bot.send_message(
                        subscriber.telegram_user_id, format_vacancy(vacancy), parse_mode="HTML"
                    )
                    cursor_id = vacancy.id
                except TelegramForbiddenError:
                    subscriber.status = "blocked"
                    session.add(subscriber)
                    await session.commit()
                    break
                except TelegramRetryAfter as exc:
                    logger.warning("Rate limited, retry after %s", exc.retry_after)
                    break
                except Exception:
                    logger.exception("Failed to push vacancy %s to %s", vacancy.id, subscriber.telegram_user_id)
                    break

            if cursor_id != subscriber.last_vacancy_sent_id:
                await mark_subscriber_cursor(session, subscriber, cursor_id)
