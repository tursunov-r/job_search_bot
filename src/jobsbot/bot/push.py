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


def _json_list(value: str) -> list[str]:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def _vacancy_matches(vacancy: Vacancy, selected_languages: list[str], selected_skills: list[str]) -> bool:
    vacancy_languages = _json_list(vacancy.languages)
    language_ok = not selected_languages or any(lang in selected_languages for lang in vacancy_languages)
    stack_ok = matches_stack(vacancy.title, vacancy.description, selected_skills)
    return language_ok and stack_ok


async def _deliver_vacancy(bot: Bot, telegram_user_id: int, vacancy: Vacancy) -> None:
    """Telegram-sourced vacancies are forwarded as the original message
    (per product decision — no reformatting). HH/LinkedIn ones go through
    our template since there's no original Telegram message to forward."""
    if vacancy.source_chat_id and vacancy.source_message_id:
        try:
            await bot.forward_message(
                telegram_user_id, from_chat_id=vacancy.source_chat_id, message_id=vacancy.source_message_id
            )
            return
        except (TelegramForbiddenError, TelegramRetryAfter):
            raise
        except Exception:
            # The bot itself isn't a member of the source channel (only the
            # Telethon listener session is) — forwarding across accounts
            # like that commonly fails. Fall back to plain text so the
            # vacancy isn't silently lost.
            logger.warning("Forward failed for vacancy %s, falling back to plain text", vacancy.id)
            await bot.send_message(telegram_user_id, vacancy.description or vacancy.title)
            return

    await bot.send_message(telegram_user_id, format_vacancy(vacancy), parse_mode="HTML")


async def push_new_vacancies(bot: Bot) -> None:
    async with async_session() as session:
        subscribers = await get_active_subscribers(session)
        for subscriber in subscribers:
            vacancies = await get_pending_vacancies_for_subscriber(session, subscriber)
            if not vacancies:
                continue

            selected_languages = _json_list(subscriber.languages)
            selected_skills = _json_list(subscriber.skills)
            cursor_id = subscriber.last_vacancy_sent_id

            for vacancy in vacancies:
                if not _vacancy_matches(vacancy, selected_languages, selected_skills):
                    # Skipped on purpose (doesn't match the subscriber's filters) —
                    # still advance the cursor so it isn't re-checked every cycle.
                    cursor_id = vacancy.id
                    continue

                try:
                    await _deliver_vacancy(bot, subscriber.telegram_user_id, vacancy)
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
