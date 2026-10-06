import json

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from jobsbot.bot.push import resend_matching_backlog
from jobsbot.processing.languages import LANGUAGES
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_or_create_subscriber, update_subscriber_languages

router = Router()

CALLBACK_PREFIX = "lang"


def _json_list(value: str) -> list[str]:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def build_language_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    keys = list(LANGUAGES.keys())
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(keys), 2):
        buttons = []
        for key in keys[i : i + 2]:
            lang = LANGUAGES[key]
            checked = "✅" if key in selected else "⬜"
            buttons.append(
                InlineKeyboardButton(
                    text=f"{checked} {lang.label}",
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


LANGUAGE_INTRO_TEXT = (
    "Выбери язык(и) программирования — буду присылать только вакансии по ним. "
    "Если ничего не выбрано — присылаю вакансии на всех языках.\n\n"
    "После выбора открой /stack — там появятся фреймворки под выбранный язык."
)


@router.message(Command("language"))
async def handle_language(message: Message) -> None:
    if message.from_user is None:
        return
    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        selected = _json_list(subscriber.languages)
    await message.answer(LANGUAGE_INTRO_TEXT, reply_markup=build_language_keyboard(selected))


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}:"))
async def handle_language_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.data is None:
        return

    parts = callback.data.split(":")
    action = parts[1]

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        selected = set(_json_list(subscriber.languages))

        selection_changed = False
        if action == "toggle":
            key = parts[2]
            if key in selected:
                selected.discard(key)
            else:
                selected.add(key)
            subscriber = await update_subscriber_languages(session, subscriber, list(selected))
            selection_changed = True
        elif action == "reset":
            subscriber = await update_subscriber_languages(session, subscriber, [])
            selection_changed = True

        final_selected = _json_list(subscriber.languages)

    if action == "done":
        await callback.message.edit_text("Языки сохранены. Теперь загляни в /stack за фреймворками.")
        await callback.answer()
        return

    await callback.message.edit_reply_markup(reply_markup=build_language_keyboard(final_selected))

    if selection_changed:
        sent = await resend_matching_backlog(callback.bot, subscriber)
        await callback.answer(f"Нашёл {sent} подходящих вакансий за неделю" if sent else None)
    else:
        await callback.answer()
