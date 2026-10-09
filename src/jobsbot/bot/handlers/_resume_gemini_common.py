"""Shared resume-file handling for Gemini-based features (interview prep,
resume improvement) — validate the uploaded file, send it to Gemini with
a given prompt, and reply with the generated text as a .md file.

Nothing touches disk: the resume bytes are downloaded straight into
memory, sent to Gemini, and the generated .md goes back to the user via
an in-memory BufferedInputFile — both are garbage-collected the moment
the handler returns. No DB storage, no temp files, nothing to clean up
after the fact because nothing was ever written anywhere persistent.
"""

import logging
from pathlib import Path

from aiogram.types import BufferedInputFile, Document, Message
from aiogram.types import ReplyKeyboardMarkup

from jobsbot.ai.gemini_client import GeminiError, generate

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MIME_TYPES = {".pdf": "application/pdf"}
TEXT_EXTENSIONS = {".txt", ".md"}
ALLOWED_EXTENSIONS = set(MIME_TYPES) | TEXT_EXTENSIONS


async def delete_quietly(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        logger.debug("Could not delete message %s (probably harmless)", message.message_id)


def validate_resume_document(doc: Document) -> str | None:
    """Returns an error message to show the user, or None if the file is fine."""
    ext = Path(doc.file_name or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return "Поддерживаются только PDF, TXT и MD. Пришли файл в одном из этих форматов."
    if doc.file_size and doc.file_size > MAX_FILE_SIZE_BYTES:
        return "Файл слишком большой (лимит 10 МБ)."
    return None


async def run_resume_prompt(
    message: Message,
    prompt_text: str,
    *,
    output_filename: str,
    caption: str,
    reply_markup: ReplyKeyboardMarkup,
    failure_text: str,
) -> None:
    doc = message.document
    status = await message.answer("Читаю резюме — это может занять минуту...")

    buffer = await message.bot.download(doc.file_id)
    file_bytes = buffer.read()
    ext = Path(doc.file_name or "").suffix.lower()

    try:
        if ext in TEXT_EXTENSIONS:
            resume_text = file_bytes.decode("utf-8", errors="replace")
            result_text = await generate(f"{prompt_text}\n\n{resume_text}")
        else:
            result_text = await generate(prompt_text, file_bytes=file_bytes, mime_type=MIME_TYPES[ext])
    except GeminiError:
        logger.exception("Gemini resume flow failed")
        await status.edit_text(failure_text)
        return
    finally:
        del file_bytes, buffer

    output = BufferedInputFile(result_text.encode("utf-8"), filename=output_filename)
    await message.answer_document(output, caption=caption, reply_markup=reply_markup)
    await status.delete()
