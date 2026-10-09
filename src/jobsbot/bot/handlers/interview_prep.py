"""Resume -> Gemini -> honest interview-prep notes, sent back as a .md file.

See _resume_gemini_common.py for the shared file-handling logic.
"""

import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from jobsbot.bot.handlers._resume_gemini_common import (
    delete_quietly,
    run_resume_prompt,
    validate_resume_document,
)
from jobsbot.bot.handlers.subscriber_menu import (
    BTN_INTERVIEW_PREP,
    MENU_BUTTON_TEXTS,
    current_menu_keyboard,
)
from jobsbot.config import settings

logger = logging.getLogger(__name__)
router = Router()

_PROMPT_PATH = Path(__file__).resolve().parents[4] / "docs" / "gemini_promts" / "interview_prep.md"
_PROMPT_TEXT = _PROMPT_PATH.read_text(encoding="utf-8")


class InterviewPrepFSM(StatesGroup):
    waiting_resume = State()


@router.message(F.text == BTN_INTERVIEW_PREP)
async def handle_interview_prep_button(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    if not settings.gemini_enabled:
        return
    await delete_quietly(message)
    await state.set_state(InterviewPrepFSM.waiting_resume)
    await message.answer(
        "Пришли файл резюме (PDF, TXT или MD, до 10 МБ) — подготовлю материалы для подготовки "
        "к интервью на основе твоего реального опыта: разложу реальные достижения по STAR и "
        "подскажу, какие уточняющие вопросы могут задать по технологиям из резюме.\n\n"
        "Файл не сохраняется на сервере — используется только для одного анализа."
    )


@router.message(InterviewPrepFSM.waiting_resume, ~F.document, F.text.not_in(MENU_BUTTON_TEXTS))
async def handle_interview_prep_non_document(message: Message) -> None:
    await message.answer("Пришли резюме как файл (PDF, TXT или MD), не текстом.")


@router.message(InterviewPrepFSM.waiting_resume, F.document)
async def handle_resume_document(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.document is None:
        return

    error = validate_resume_document(message.document)
    if error:
        await message.answer(error)
        return

    await state.clear()
    await run_resume_prompt(
        message,
        _PROMPT_TEXT,
        output_filename="interview_prep.md",
        caption=(
            "Готово — материалы для подготовки к интервью на основе твоего резюме.\n\n"
            "⚠️ Прочитай файл целиком перед собеседованием — там есть пункты, где явно указано, "
            "что у тебя не хватает опыта или данных. Если на интервью всплывёт что-то из этих "
            "пунктов без подготовки, будет сразу понятно, что готовил не ты."
        ),
        reply_markup=await current_menu_keyboard(message.from_user.id),
        failure_text="Не получилось подготовить материалы — попробуй ещё раз немного позже.",
    )
