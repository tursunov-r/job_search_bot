import json

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from jobsbot.processing.stack_tags import STACK_TAG_ROWS, STACK_TAGS
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_or_create_subscriber, update_subscriber_skills

router = Router()

CALLBACK_PREFIX = "stack"


def _get_selected(subscriber) -> list[str]:
    try:
        return json.loads(subscriber.skills)
    except (TypeError, ValueError):
        return []


def build_stack_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for tag_row in STACK_TAG_ROWS:
        buttons = []
        for key in tag_row:
            tag = STACK_TAGS[key]
            checked = "✅" if key in selected else "⬜"
            buttons.append(
                InlineKeyboardButton(
                    text=f"{checked} {tag.label}",
                    callback_data=f"{CALLBACK_PREFIX}:toggle:{key}",
                )
            )
        rows.append(buttons)

    rows.append(
        [
            InlineKeyboardButton(text="Сбросить", callback_data=f"{CALLBACK_PREFIX}:reset"),
            InlineKeyboardButton(text="Готово", callback_data=f"{CALLBACK_PREFIX}:done"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


STACK_INTRO_TEXT = (
    "Выбери свой стек — буду присылать вакансии, где упоминается хотя бы одна "
    "из выбранных технологий. Если ничего не выбрано — присылаю все python-вакансии."
)


@router.message(Command("stack"))
async def handle_stack(message: Message) -> None:
    if message.from_user is None:
        return
    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        selected = _get_selected(subscriber)
    await message.answer(STACK_INTRO_TEXT, reply_markup=build_stack_keyboard(selected))


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}:"))
async def handle_stack_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return

    parts = callback.data.split(":")
    action = parts[1]

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        selected = set(_get_selected(subscriber))

        if action == "toggle":
            key = parts[2]
            if key in selected:
                selected.discard(key)
            else:
                selected.add(key)
            subscriber = await update_subscriber_skills(session, subscriber, list(selected))
        elif action == "reset":
            selected = set()
            subscriber = await update_subscriber_skills(session, subscriber, [])

        final_selected = _get_selected(subscriber)

    if action == "done":
        await callback.message.edit_text("Стек сохранён. Присылаю вакансии по твоим настройкам.")
        await callback.answer()
        return

    await callback.message.edit_reply_markup(reply_markup=build_stack_keyboard(final_selected))
    await callback.answer()
