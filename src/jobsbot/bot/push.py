import html as html_lib
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from jobsbot.config import settings
from jobsbot.processing.city_timezones import resolve_city_timezone
from jobsbot.processing.stack_tags import matches_stack
from jobsbot.processing.work_formats import categorize as categorize_work_format
from jobsbot.storage.db import async_session
from jobsbot.storage.models import Subscriber, Vacancy
from jobsbot.storage.repo import (
    count_deliveries_since,
    get_active_subscribers,
    get_broadcastable_subscribers,
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


def build_vacancy_keyboard(vacancy: Vacancy, saved: bool = False) -> InlineKeyboardMarkup:
    row = []
    if vacancy.url:
        row.append(InlineKeyboardButton(text="🔗 Подробнее", url=vacancy.url))
    row.append(InlineKeyboardButton(text="🚩 Пожаловаться", callback_data=f"report:{vacancy.id}"))
    save_button = (
        InlineKeyboardButton(text="🗑 Убрать из избранного", callback_data=f"unsave:{vacancy.id}")
        if saved
        else InlineKeyboardButton(text="⭐ Сохранить", callback_data=f"save:{vacancy.id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[row, [save_button]])


def _json_list(value: str) -> list[str]:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def _matches_city(vacancy: Vacancy, cities: list[str]) -> bool:
    if not cities:
        return True
    if "remote" in categorize_work_format(vacancy.work_format):
        # Remote-ish vacancies bypass the city filter entirely — some have
        # no location at all (Habr's "Можно удалённо" chip), others keep
        # the employer's city even though the role itself is remote (HH),
        # so matching location literally would wrongly exclude genuinely
        # remote postings.
        return True
    if not vacancy.location:
        return False
    location = vacancy.location.strip().lower()
    return any(location == city.strip().lower() for city in cities)


def _matches_work_format(vacancy: Vacancy, selected_formats: list[str]) -> bool:
    if not selected_formats:
        return True
    return bool(categorize_work_format(vacancy.work_format) & set(selected_formats))


def _matches_salary(vacancy: Vacancy, min_salary: int | None) -> bool:
    if not min_salary:
        return True
    if vacancy.salary_min_rub is None:
        # Non-RUB currency, no stated floor ("до Y"), or no salary at all —
        # unknown, not "below threshold", so don't exclude it.
        return True
    return vacancy.salary_min_rub >= min_salary


def _matches_keywords(vacancy: Vacancy, keywords: list[str]) -> bool:
    """A free-text keyword match *widens* delivery — it never excludes
    anything on its own (see _vacancy_matches), only adds vacancies that
    wouldn't have matched the subscriber's language/stack selection at
    all, so a framework/tool mentioned in the text can be found even if
    it's not modeled as its own language or stack tag."""
    if not keywords:
        return False
    text = f"{vacancy.title or ''} {vacancy.description or ''}".lower()
    return any(keyword.lower() in text for keyword in keywords)


def _vacancy_matches(
    vacancy: Vacancy,
    selected_languages: list[str],
    selected_skills: list[str],
    cities: list[str] | None = None,
    work_formats: list[str] | None = None,
    min_salary: int | None = None,
    keywords: list[str] | None = None,
) -> bool:
    vacancy_languages = _json_list(vacancy.languages)
    language_ok = not selected_languages or any(lang in selected_languages for lang in vacancy_languages)
    stack_ok = matches_stack(vacancy.title, vacancy.description, selected_skills)
    relevance_ok = (language_ok and stack_ok) or _matches_keywords(vacancy, keywords or [])
    return (
        relevance_ok
        and _matches_city(vacancy, cities or [])
        and _matches_work_format(vacancy, work_formats or [])
        and _matches_salary(vacancy, min_salary)
    )


async def _deliver_vacancy(bot: Bot, telegram_user_id: int, vacancy: Vacancy) -> None:
    """Telegram-sourced vacancies are forwarded as the original message
    (per product decision — no reformatting). HH/LinkedIn ones go through
    our template since there's no original Telegram message to forward."""
    if vacancy.source_chat_id and vacancy.source_message_id:
        try:
            await bot.forward_message(
                telegram_user_id, from_chat_id=vacancy.source_chat_id, message_id=vacancy.source_message_id
            )
            # forward_message doesn't support reply_markup, so the report
            # button has to ride along on a tiny separate follow-up instead.
            await bot.send_message(
                telegram_user_id,
                "Если с вакансией выше что-то не так:",
                reply_markup=build_vacancy_keyboard(vacancy),
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


def _subscriber_timezone(subscriber: Subscriber) -> ZoneInfo:
    """Telegram's Bot API doesn't expose a client timezone at all, so this
    infers it from whatever city the subscriber already typed into the
    "🏙 Города" filter (see processing/city_timezones.py) — no extra
    prompt needed. Falls back to settings.bot_timezone if no city is set
    or none is recognized."""
    tz_name = resolve_city_timezone(_json_list(subscriber.cities)) or settings.bot_timezone
    return ZoneInfo(tz_name)


def _is_quiet_now(subscriber: Subscriber) -> bool:
    if subscriber.quiet_hours_start is None or subscriber.quiet_hours_end is None:
        return False
    hour = datetime.now(_subscriber_timezone(subscriber)).hour
    start, end = subscriber.quiet_hours_start, subscriber.quiet_hours_end
    if start < end:
        return start <= hour < end
    if start > end:
        # Wraps past midnight, e.g. 23 -> 8.
        return hour >= start or hour < end
    return False  # start == end — degenerate, treat as "no quiet hours"


async def push_new_vacancies(bot: Bot) -> None:
    async with async_session() as session:
        subscribers = await get_active_subscribers(session)
        for subscriber in subscribers:
            if _is_quiet_now(subscriber):
                # Cursor untouched on purpose — everything queued delivers
                # normally, in the usual stream, once the window ends.
                continue

            vacancies = await get_pending_vacancies_for_subscriber(session, subscriber)
            if not vacancies:
                continue

            selected_languages = _json_list(subscriber.languages)
            selected_skills = _json_list(subscriber.skills)
            selected_cities = _json_list(subscriber.cities)
            selected_work_formats = _json_list(subscriber.work_formats)
            selected_keywords = _json_list(subscriber.keywords)
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

                if not _vacancy_matches(
                    vacancy,
                    selected_languages,
                    selected_skills,
                    selected_cities,
                    selected_work_formats,
                    subscriber.min_salary,
                    selected_keywords,
                ):
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
        selected_cities = _json_list(subscriber.cities)
        selected_work_formats = _json_list(subscriber.work_formats)
        selected_keywords = _json_list(subscriber.keywords)

        sent = 0
        for vacancy in candidates:
            if not _vacancy_matches(
                vacancy,
                selected_languages,
                selected_skills,
                selected_cities,
                selected_work_formats,
                subscriber.min_salary,
                selected_keywords,
            ):
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


def _matching_candidate_count(subscriber: Subscriber, candidates: list[Vacancy]) -> int:
    selected_languages = _json_list(subscriber.languages)
    selected_skills = _json_list(subscriber.skills)
    selected_cities = _json_list(subscriber.cities)
    selected_work_formats = _json_list(subscriber.work_formats)
    selected_keywords = _json_list(subscriber.keywords)
    return sum(
        1
        for vacancy in candidates
        if _vacancy_matches(
            vacancy,
            selected_languages,
            selected_skills,
            selected_cities,
            selected_work_formats,
            subscriber.min_salary,
            selected_keywords,
        )
    )


async def send_weekly_digest(bot: Bot) -> None:
    """A once-a-week touchpoint — a plain background push, not a reply to
    any menu action, so it deliberately does NOT go through
    send_system_message (that would risk deleting some other system
    message the subscriber happens to have open at the time).

    Active subscribers get a simple recap of how much they were actually
    sent; paused ones get a nudge showing how much *would* have matched
    their filters this week, to pull dormant accounts back — the main
    point of this feature. Anyone with a zero count is skipped entirely
    rather than sent an empty, discouraging digest.
    """
    from jobsbot.bot.handlers.subscriber_menu import BTN_VIEW

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    async with async_session() as session:
        subscribers = await get_broadcastable_subscribers(session)

    for subscriber in subscribers:
        if _is_quiet_now(subscriber):
            continue

        async with async_session() as session:
            if subscriber.status == "active":
                count = await count_deliveries_since(session, subscriber.id, cutoff)
                if not count:
                    continue
                text = f"📊 За последнюю неделю тебе пришло {count} подходящих вакансий."
            else:
                candidates = await get_undelivered_recent_vacancies(session, subscriber.id, days=7)
                count = _matching_candidate_count(subscriber, candidates)
                if not count:
                    continue
                text = (
                    f"📊 Рассылка на паузе, но за последнюю неделю нашлось {count} вакансий, "
                    f"подходящих под твои фильтры. Нажми «{BTN_VIEW}», чтобы их получить."
                )

        try:
            await bot.send_message(subscriber.telegram_user_id, text)
        except TelegramForbiddenError:
            async with async_session() as session:
                subscriber.status = "blocked"
                session.add(subscriber)
                await session.commit()
        except Exception:
            logger.exception("Failed to send weekly digest to %s", subscriber.telegram_user_id)
