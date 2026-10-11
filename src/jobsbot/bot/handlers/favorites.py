"""The "⭐ Избранное" bookmark feature — save/unsave toggle on any vacancy
message's inline keyboard, plus a menu button to re-list everything saved.
See storage.models.SavedVacancy and repo.py::cleanup_old_vacancies (saved
vacancies are excluded from the normal retention cleanup).
"""

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from jobsbot.bot.handlers.subscriber_menu import (
    BTN_FAVORITES,
    current_menu_keyboard,
    send_system_message,
)
from jobsbot.bot.push import build_vacancy_keyboard, format_vacancy
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import (
    get_or_create_subscriber,
    get_vacancy_by_id,
    list_saved_vacancies,
    save_vacancy,
    unsave_vacancy,
)

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("save:"))
async def handle_save_vacancy(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    vacancy_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        await save_vacancy(session, subscriber.id, vacancy_id)
        vacancy = await get_vacancy_by_id(session, vacancy_id)

    if vacancy is None:
        await callback.answer("Вакансия не найдена (возможно, уже удалена).")
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=build_vacancy_keyboard(vacancy, saved=True))
    except Exception:
        logger.debug("Could not update save button (probably harmless)")
    await callback.answer("Сохранено в избранное ⭐")


@router.callback_query(F.data.startswith("unsave:"))
async def handle_unsave_vacancy(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    vacancy_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        await unsave_vacancy(session, subscriber.id, vacancy_id)
        vacancy = await get_vacancy_by_id(session, vacancy_id)

    if vacancy is None:
        await callback.answer("Вакансия не найдена (возможно, уже удалена).")
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=build_vacancy_keyboard(vacancy, saved=False))
    except Exception:
        logger.debug("Could not update save button (probably harmless)")
    await callback.answer("Убрано из избранного")


@router.message(F.text == BTN_FAVORITES)
async def handle_favorites_button(message: Message) -> None:
    if message.from_user is None:
        return

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        saved = await list_saved_vacancies(session, subscriber.id)

    keyboard = await current_menu_keyboard(message.from_user.id)
    if not saved:
        await send_system_message(
            message.bot,
            message.from_user.id,
            "Пока нет сохранённых вакансий — жми «⭐ Сохранить» под вакансией, чтобы она попала сюда.",
            reply_markup=keyboard,
        )
        return

    await send_system_message(
        message.bot, message.from_user.id, f"⭐ Сохранённые вакансии ({len(saved)}):", reply_markup=keyboard
    )
    # Each one is real content, same as a live vacancy push — sent as a
    # plain message, never tracked for the system-message clean-up.
    for vacancy in saved:
        await message.bot.send_message(
            message.from_user.id,
            format_vacancy(vacancy),
            parse_mode="HTML",
            reply_markup=build_vacancy_keyboard(vacancy, saved=True),
        )
