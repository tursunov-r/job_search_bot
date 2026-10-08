import html as html_lib
import json
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from jobsbot.processing.stack_tags import matches_stack
from jobsbot.storage.db import async_session
from jobsbot.storage.models import Subscriber, Vacancy
from jobsbot.storage.repo import (
    get_active_subscribers,
    get_delivered_vacancy_ids,
    get_pending_vacancies_for_subscriber,
    get_undelivered_recent_vacancies,
    mark_subscriber_cursor,
    record_delivery,
)

logger = logging.getLogger(__name__)

DESCRIPTION_PREVIEW_LIMIT = 400


def _truncate(text: str, limit: int = DESCRIPTION_PREVIEW_LIMIT) -> str:
    if len(text) <= limit:
        return text
    truncated = text[:limit].rsplit(" ", 1)[0]
    return f"{truncated}…"


def format_vacancy(vacancy: Vacancy) -> str:
    details = []
    if vacancy.salary_text:
        details.append(f"💰 {html_lib.escape(vacancy.salary_text)}")
    if vacancy.company:
        details.append(f"🏢 {html_lib.escape(vacancy.company)}")

    location_bits = [part for part in (vacancy.location, vacancy.work_format) if part]
    if location_bits:
        details.append(f"📍 {html_lib.escape(' · '.join(location_bits))}")

    if vacancy.experience:
        details.append(f"🧑‍💻 Опыт: {html_lib.escape(vacancy.experience)}")
    if vacancy.employment_type:
        details.append(f"📋 {html_lib.escape(vacancy.employment_type)}")
    if vacancy.schedule:
        details.append(f"🗓 {html_lib.escape(vacancy.schedule)}")

    blocks = [f"<b>{html_lib.escape(vacancy.title)}</b>"]
    if details:
        blocks.append("\n".join(details))
    if vacancy.description:
        blocks.append(html_lib.escape(_truncate(vacancy.description)))
    blocks.append(f"ID: <code>{vacancy.uuid}</code>")

    return "\n\n".join(blocks)


def build_vacancy_keyboard(vacancy: Vacancy) -> InlineKeyboardMarkup | None:
    if not vacancy.url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔗 Подробнее", url=vacancy.url)]]
    )


def _json_list(value: str) -> list[str]:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def _is_remote_friendly(vacancy: Vacancy) -> bool:
    """Remote-ish vacancies bypass the city filter entirely — some have no
    location at all (Habr's "Можно удалённо" chip), others keep the
    employer's city even though the role itself is remote (HH), so matching
    location literally would wrongly exclude genuinely remote postings."""
    return bool(vacancy.work_format and "удал" in vacancy.work_format.lower())


def _matches_city(vacancy: Vacancy, city: str | None) -> bool:
    if not city:
        return True
    if _is_remote_friendly(vacancy):
        return True
    return bool(vacancy.location) and vacancy.location.strip().lower() == city.strip().lower()


def _vacancy_matches(
    vacancy: Vacancy, selected_languages: list[str], selected_skills: list[str], city: str | None = None
) -> bool:
    vacancy_languages = _json_list(vacancy.languages)
    language_ok = not selected_languages or any(lang in selected_languages for lang in vacancy_languages)
    stack_ok = matches_stack(vacancy.title, vacancy.description, selected_skills)
    return language_ok and stack_ok and _matches_city(vacancy, city)


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
            # vacancy isn't silently lost. forward_message doesn't support
            # reply_markup anyway, but a plain send_message does, so this
            # fallback still gets the "Подробнее" button if there's a URL.
            logger.warning("Forward failed for vacancy %s, falling back to plain text", vacancy.id)
            await bot.send_message(
                telegram_user_id,
                vacancy.description or vacancy.title,
                reply_markup=build_vacancy_keyboard(vacancy),
            )
            return

    await bot.send_message(
        telegram_user_id,
        format_vacancy(vacancy),
        parse_mode="HTML",
        reply_markup=build_vacancy_keyboard(vacancy),
    )


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
            delivered_ids = await get_delivered_vacancy_ids(
                session, subscriber.id, [v.id for v in vacancies]
            )

            for vacancy in vacancies:
                if vacancy.id in delivered_ids:
                    # Already sent via a profile-change re-scan before the
                    # cursor walk reached it — don't send it twice.
                    cursor_id = vacancy.id
                    continue

                if not _vacancy_matches(vacancy, selected_languages, selected_skills, subscriber.city):
                    # Skipped on purpose (doesn't match the subscriber's filters) —
                    # still advance the cursor so it isn't re-checked every cycle.
                    cursor_id = vacancy.id
                    continue

                try:
                    await _deliver_vacancy(bot, subscriber.telegram_user_id, vacancy)
                    await record_delivery(session, subscriber.id, vacancy.id)
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


async def resend_matching_backlog(bot: Bot, subscriber: Subscriber) -> int:
    """Called when the subscriber presses "Смотреть вакансии": re-scan the
    last 7 days for vacancies this subscriber hasn't been sent yet that
    match their *current* profile — the normal cursor walk already moved past
    anything that didn't match the *old* filter and won't reconsider it.
    Returns how many were sent."""
    async with async_session() as session:
        candidates = await get_undelivered_recent_vacancies(session, subscriber.id)
        selected_languages = _json_list(subscriber.languages)
        selected_skills = _json_list(subscriber.skills)

        sent = 0
        for vacancy in candidates:
            if not _vacancy_matches(vacancy, selected_languages, selected_skills, subscriber.city):
                continue
            try:
                await _deliver_vacancy(bot, subscriber.telegram_user_id, vacancy)
                await record_delivery(session, subscriber.id, vacancy.id)
                sent += 1
            except TelegramForbiddenError:
                subscriber.status = "blocked"
                session.add(subscriber)
                await session.commit()
                break
            except TelegramRetryAfter as exc:
                logger.warning("Rate limited during resend, retry after %s", exc.retry_after)
                break
            except Exception:
                logger.exception("Failed to resend vacancy %s to %s", vacancy.id, subscriber.telegram_user_id)
                continue

        return sent
