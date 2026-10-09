"""Resume -> Gemini -> honest interview-prep notes, sent back as a .md file.

Nothing touches disk: the resume bytes are downloaded straight into
memory, sent to Gemini, and the generated .md goes back to the user via
an in-memory BufferedInputFile — both are garbage-collected the moment
this handler returns. No DB storage, no temp files, nothing to clean up
after the fact because nothing was ever written anywhere persistent.
"""

import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, Message

from jobsbot.ai.gemini_client import GeminiError, generate
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

_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
_MIME_TYPES = {".pdf": "application/pdf"}
_TEXT_EXTENSIONS = {".txt", ".md"}
_ALLOWED_EXTENSIONS = set(_MIME_TYPES) | _TEXT_EXTENSIONS


class InterviewPrepFSM(StatesGroup):
    waiting_resume = State()


async def _delete_quietly(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        logger.debug("Could not delete message %s (probably harmless)", message.message_id)


@router.message(F.text == BTN_INTERVIEW_PREP)
async def handle_interview_prep_button(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    if not settings.gemini_enabled:
        return
    await _delete_quietly(message)
    await state.set_state(InterviewPrepFSM.waiting_resume)
    await message.answer(
        "Пришли файл резюме (PDF, TXT или MD, до 10 МБ) — подготовлю материалы для подготовки "
        "к интервью на основе твоего реального опыта: разложу реальные достижения по STAR и "
        "подскажу, какие уточняющие вопросы могут задать по технологиям из резюме.\n\n"
        "Файл не сохраняется на сервере — используется только для одного запроса к Gemini."
    )


@router.message(InterviewPrepFSM.waiting_resume, ~F.document, F.text.not_in(MENU_BUTTON_TEXTS))
async def handle_interview_prep_non_document(message: Message) -> None:
    await message.answer("Пришли резюме как файл (PDF, TXT или MD), не текстом.")


@router.message(InterviewPrepFSM.waiting_resume, F.document)
async def handle_resume_document(message: Message, state: FSMContext) -> None:
    if message.from_user is None or message.document is None:
        return

    doc = message.document
    filename = doc.file_name or ""
    ext = Path(filename).suffix.lower()

    if ext not in _ALLOWED_EXTENSIONS:
        await message.answer("Поддерживаются только PDF, TXT и MD. Пришли файл в одном из этих форматов.")
        return
    if doc.file_size and doc.file_size > _MAX_FILE_SIZE_BYTES:
        await message.answer("Файл слишком большой (лимит 10 МБ).")
        return

    await state.clear()
    status = await message.answer("Читаю резюме и готовлю материалы — это может занять минуту...")

    buffer = await message.bot.download(doc.file_id)
    file_bytes = buffer.read()

    try:
        if ext in _TEXT_EXTENSIONS:
            resume_text = file_bytes.decode("utf-8", errors="replace")
            result_text = await generate(f"{_PROMPT_TEXT}\n\n{resume_text}")
        else:
            result_text = await generate(_PROMPT_TEXT, file_bytes=file_bytes, mime_type=_MIME_TYPES[ext])
    except GeminiError:
        logger.exception("Gemini interview-prep failed")
        await status.edit_text("Не получилось подготовить материалы — попробуй ещё раз немного позже.")
        return
    finally:
        del file_bytes, buffer

    output = BufferedInputFile(result_text.encode("utf-8"), filename="interview_prep.md")
    await message.answer_document(
        output,
        caption="Готово — материалы для подготовки к интервью на основе твоего резюме.",
        reply_markup=await current_menu_keyboard(message.from_user.id),
    )
    await status.delete()
