import html as html_lib
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from jobsbot.bot.handlers.subscriber_menu import MENU_BUTTON_TEXTS, current_menu_keyboard
from jobsbot.bot.permissions import has_permission, is_super_admin
from jobsbot.config import settings
from jobsbot.storage.db import async_session
from jobsbot.storage.models import Vacancy, VacancyReport
from jobsbot.storage.repo import (
    create_vacancy_report,
    get_or_create_subscriber,
    get_staff_telegram_ids_with_permission,
    get_vacancy_by_id,
    get_vacancy_report,
    resolve_vacancy_report,
    set_vacancy_hidden,
)

logger = logging.getLogger(__name__)
router = Router()

REPORT_CALLBACK_PREFIX = "report"
MODERATE_CALLBACK_PREFIX = "modreport"


class ReportFSM(StatesGroup):
    waiting_comment = State()


def _vacancy_summary(vacancy: Vacancy) -> str:
    lines = [f"<b>{html_lib.escape(vacancy.title)}</b>"]
    if vacancy.company:
        lines.append(f"🏢 {html_lib.escape(vacancy.company)}")
    if vacancy.url:
        lines.append(vacancy.url)
    return "\n".join(lines)


def _resolution_keyboard(report_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить вакансию", callback_data=f"{MODERATE_CALLBACK_PREFIX}:remove:{report_id}"
                ),
                InlineKeyboardButton(
                    text="✅ Оставить", callback_data=f"{MODERATE_CALLBACK_PREFIX}:keep:{report_id}"
                ),
            ]
        ]
    )


async def _notify_admins(bot: Bot, report: VacancyReport, vacancy: Vacancy, reporter_username: str | None) -> None:
    async with async_session() as session:
        staff_ids = await get_staff_telegram_ids_with_permission(session, "moderate_vacancies")
    recipients = set(staff_ids) | {settings.super_admin_telegram_user_id}

    reporter = f"@{reporter_username}" if reporter_username else "без username"
    text = (
        f"🚩 Жалоба на вакансию (#{report.id})\n\n"
        f"{_vacancy_summary(vacancy)}\n\n"
        f"От: {reporter}\n"
        f"Комментарий: {html_lib.escape(report.comment)}"
    )
    for telegram_user_id in recipients:
        try:
            await bot.send_message(
                telegram_user_id, text, parse_mode="HTML", reply_markup=_resolution_keyboard(report.id)
            )
        except Exception:
            logger.warning("Failed to notify admin %s about report %s", telegram_user_id, report.id)


@router.callback_query(F.data.startswith(f"{REPORT_CALLBACK_PREFIX}:"))
async def handle_report_button(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    vacancy_id = int(callback.data.split(":")[1])
    await state.set_state(ReportFSM.waiting_comment)
    await state.update_data(vacancy_id=vacancy_id)
    await callback.answer()
    await callback.message.answer(
        "Напиши, что не так с этой вакансией (без комментария пожаловаться нельзя):"
    )


@router.message(ReportFSM.waiting_comment, F.text.not_in(MENU_BUTTON_TEXTS))
async def handle_report_comment(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    comment = (message.text or "").strip()
    if not comment:
        await message.answer("Комментарий не может быть пустым — напиши, что не так с вакансией:")
        return

    data = await state.get_data()
    vacancy_id = data.get("vacancy_id")
    await state.clear()

    async with async_session() as session:
        vacancy = await get_vacancy_by_id(session, vacancy_id)
        if vacancy is None:
            await message.answer("Вакансия не найдена (возможно, уже удалена).")
            return

        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        report = await create_vacancy_report(session, vacancy_id, subscriber.id, comment)
        await set_vacancy_hidden(session, vacancy_id, True)

    await message.answer(
        "Спасибо, жалоба отправлена на проверку — пока админ не разберётся, эту вакансию никому не покажем.",
        reply_markup=await current_menu_keyboard(message.from_user.id),
    )
    await _notify_admins(message.bot, report, vacancy, message.from_user.username)


@router.callback_query(F.data.startswith(f"{MODERATE_CALLBACK_PREFIX}:"))
async def handle_moderate_report(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    _, action, report_id_str = callback.data.split(":")
    report_id = int(report_id_str)

    async with async_session() as session:
        allowed = is_super_admin(callback.from_user.id) or await has_permission(
            callback.from_user.id, "moderate_vacancies"
        )
        if not allowed:
            await callback.answer("Нет прав.", show_alert=True)
            return

        report = await get_vacancy_report(session, report_id)
        if report is None:
            await callback.answer("Жалоба не найдена.", show_alert=True)
            return
        if report.status != "pending":
            await callback.answer("Уже обработано другим админом.", show_alert=True)
            return

        keep = action == "keep"
        await set_vacancy_hidden(session, report.vacancy_id, not keep)
        await resolve_vacancy_report(
            session, report, "resolved_kept" if keep else "resolved_removed", callback.from_user.id
        )

    resolution_text = "оставлена (жалоба отклонена)" if keep else "удалена из рассылки"
    await callback.message.edit_text(f"{callback.message.text}\n\n✅ Решение: вакансия {resolution_text}.")
    await callback.answer()
