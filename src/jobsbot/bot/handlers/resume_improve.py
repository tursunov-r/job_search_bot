"""Resume -> Gemini -> stronger wording of the *same* real experience,
sent back as a .md file. See docs/gemini_promts/resume_improve.md for the
exact rules (no invented companies/projects/tech, only illustrative,
clearly-flagged metrics where the candidate described a result without a
number) and _resume_gemini_common.py for the shared file-handling logic.
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
    BTN_RESUME_IMPROVE,
    MENU_BUTTON_TEXTS,
    current_menu_keyboard,
)
from jobsbot.config import settings

logger = logging.getLogger(__name__)
router = Router()

_PROMPT_PATH = Path(__file__).resolve().parents[4] / "docs" / "gemini_promts" / "resume_improve.md"
_PROMPT_TEXT = _PROMPT_PATH.read_text(encoding="utf-8")


class ResumeImproveFSM(StatesGroup):
    waiting_resume = State()


@router.message(F.text == BTN_RESUME_IMPROVE)
async def handle_resume_improve_button(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    if not settings.gemini_enabled:
        return
    await delete_quietly(message)
    await state.set_state(ResumeImproveFSM.waiting_resume)
    await message.answer(
        "Пришли файл резюме (PDF, TXT или MD, до 10 МБ) — усилю формулировки и добавлю "
        "ориентировочные метрики там, где это естественно, но без выдумывания новых компаний, "
        "проектов или технологий, которых у тебя нет.\n\n"
        "Файл не сохраняется на сервере — используется только для одного анализа."
    )


@router.message(ResumeImproveFSM.waiting_resume, ~F.document, F.text.not_in(MENU_BUTTON_TEXTS))
async def handle_resume_improve_non_document(message: Message) -> None:
    await message.answer("Пришли резюме как файл (PDF, TXT или MD), не текстом.")


@router.message(ResumeImproveFSM.waiting_resume, F.document)
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
        output_filename="resume_improved.md",
        caption="Готово — усиленная версия твоего резюме.",
        reply_markup=await current_menu_keyboard(message.from_user.id),
        failure_text="Не получилось обработать резюме — попробуй ещё раз немного позже.",
    )
