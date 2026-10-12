"""Resume -> market-demand comparison -> honest AI gap analysis, sent back
as a .md file. Combines the static instructions from
docs/gemini_promts/skill_gap.md with a market-stats block built from
storage.repo.get_stack_cooccurrence — the exact same data the "🧩 Спрос на
навыки" button already computes, no new scraping or extra API calls for
the stats half of this.
"""

import json
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from jobsbot.bot.handlers._resume_gemini_common import (
    delete_quietly,
    run_resume_prompt,
    validate_resume_document,
)
from jobsbot.bot.handlers.subscriber_menu import (
    BTN_ADD_STACK,
    BTN_SKILL_GAP,
    MENU_BUTTON_TEXTS,
    current_menu_keyboard,
    send_system_message,
)
from jobsbot.config import settings
from jobsbot.processing.languages import LANGUAGES
from jobsbot.processing.stack_tags import STACK_TAGS
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_or_create_subscriber, get_stack_cooccurrence

logger = logging.getLogger(__name__)
router = Router()

_PROMPT_PATH = Path(__file__).resolve().parents[4] / "docs" / "gemini_promts" / "skill_gap.md"
_PROMPT_TEXT = _PROMPT_PATH.read_text(encoding="utf-8")

_LANGUAGE_CALLBACK_PREFIX = "skillgap:lang"


class SkillGapFSM(StatesGroup):
    waiting_language = State()
    waiting_resume = State()


def _json_list(value: str) -> list[str]:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def _language_label(language_key: str) -> str:
    return LANGUAGES[language_key].label if language_key in LANGUAGES else language_key


def _build_stats_block(language_label: str, co: dict) -> str:
    lines = [f"Язык/сфера: {language_label}. Всего вакансий с данными: {co['total']}."]
    if not co["tags"]:
        lines.append("Данных по конкретным технологиям пока недостаточно.")
    else:
        ranked = sorted(co["tags"].items(), key=lambda kv: kv[1], reverse=True)
        for key, count in ranked:
            label = STACK_TAGS[key].label if key in STACK_TAGS else key
            pct = round(count / co["total"] * 100)
            lines.append(f"- {label}: {pct}%")
    return "\n".join(lines)


async def _start_resume_wait(bot, telegram_user_id: int, state: FSMContext, language_key: str) -> None:
    await state.update_data(language_key=language_key)
    await state.set_state(SkillGapFSM.waiting_resume)
    await send_system_message(
        bot,
        telegram_user_id,
        "Пришли файл резюме (PDF, TXT или MD, до 10 МБ) — сравню его с текущим спросом на рынке "
        "по выбранному языку.\n\nФайл не сохраняется на сервере — используется только для одного анализа.",
    )


@router.message(F.text == BTN_SKILL_GAP)
async def handle_skill_gap_button(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    if not settings.gemini_enabled:
        return
    await delete_quietly(message)

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
    selected_languages = _json_list(subscriber.languages)

    if not selected_languages:
        await send_system_message(
            message.bot,
            message.from_user.id,
            f"Сначала выбери язык через «{BTN_ADD_STACK}» — потом сравню твоё резюме с рынком по нему.",
            reply_markup=await current_menu_keyboard(message.from_user.id),
        )
        return

    if len(selected_languages) == 1:
        await _start_resume_wait(message.bot, message.from_user.id, state, selected_languages[0])
        return

    rows = [
        [InlineKeyboardButton(text=_language_label(key), callback_data=f"{_LANGUAGE_CALLBACK_PREFIX}:{key}")]
        for key in selected_languages
    ]
    await state.set_state(SkillGapFSM.waiting_language)
    await send_system_message(
        message.bot,
        message.from_user.id,
        "У тебя выбрано несколько языков — с каким сравнить резюме?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(SkillGapFSM.waiting_language, F.data.startswith(f"{_LANGUAGE_CALLBACK_PREFIX}:"))
async def handle_skill_gap_language_pick(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return
    language_key = callback.data.split(":")[2]
    await callback.answer()
    await _start_resume_wait(callback.bot, callback.from_user.id, state, language_key)


@router.message(SkillGapFSM.waiting_resume, ~F.document, F.text.not_in(MENU_BUTTON_TEXTS))
async def handle_skill_gap_non_document(message: Message) -> None:
    if message.from_user is None:
        return
    await send_system_message(
        message.bot, message.from_user.id, "Пришли резюме как файл (PDF, TXT или MD), не текстом."
    )


@router.message(SkillGapFSM.waiting_resume, F.document)
async def handle_skill_gap_document(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.document is None:
        return

    error = validate_resume_document(message.document)
    if error:
        await send_system_message(message.bot, message.from_user.id, error)
        return

    data = await state.get_data()
    language_key = data.get("language_key")
    await state.clear()

    async with async_session() as session:
        co = await get_stack_cooccurrence(session, language_key)

    stats_block = _build_stats_block(_language_label(language_key), co)
    full_prompt = f"{_PROMPT_TEXT}\n\n{stats_block}"

    await run_resume_prompt(
        message,
        full_prompt,
        output_filename="skill_gap.md",
        caption=(
            "Готово — сравнение твоего резюме с текущим рынком.\n\n"
            "⚠️ Это аналитика на основе открытых вакансий, не гарантия — используй как ориентир, "
            "а не как точный список того, что обязательно нужно знать."
        ),
        reply_markup=await current_menu_keyboard(message.from_user.id),
        failure_text="Не получилось составить анализ — попробуй ещё раз немного позже.",
    )
