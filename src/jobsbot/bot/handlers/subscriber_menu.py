import json
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from jobsbot.bot.push import resend_matching_backlog
from jobsbot.processing.languages import LANGUAGES
from jobsbot.processing.stack_tags import STACK_TAGS, visible_tag_keys
from jobsbot.processing.work_formats import WORK_FORMATS
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import (
    get_or_create_subscriber,
    pause_subscriber_by_telegram_id,
    resume_subscriber_by_telegram_id,
    update_subscriber_city,
    update_subscriber_languages,
    update_subscriber_skills,
    update_subscriber_work_formats,
)

logger = logging.getLogger(__name__)
router = Router()

BTN_ADD_STACK = "➕ Добавить стек"
BTN_CITY = "🏙 Город"
BTN_WORK_FORMAT = "🧭 Формат работы"
BTN_VIEW = "👀 Смотреть вакансии"
BTN_STOP = "⏸ Остановить рассылку"

CALLBACK_PREFIX = "addstack"
WORK_FORMAT_CALLBACK_PREFIX = "workformat"

CITY_CLEAR_WORDS = {"-", "везде", "все", "всё"}

# Used to keep other menu buttons from being swallowed as free-text input
# by whichever FSM state happens to be waiting (city, report comment, etc.)
MENU_BUTTON_TEXTS = {BTN_ADD_STACK, BTN_CITY, BTN_WORK_FORMAT, BTN_VIEW, BTN_STOP}


class StackFSM(StatesGroup):
    picking_tags = State()


class CityFSM(StatesGroup):
    waiting_input = State()


class WorkFormatFSM(StatesGroup):
    picking = State()


def build_menu_keyboard(extra_rows: list[list[KeyboardButton]] | None = None) -> ReplyKeyboardMarkup:
    # Telegram only ever shows one reply keyboard at a time, so staff/admin
    # rows (if any) get appended here rather than sent as a separate
    # keyboard via /admin — otherwise picking one would silently replace
    # the other instead of the two coexisting.
    rows = [
        [KeyboardButton(text=BTN_ADD_STACK), KeyboardButton(text=BTN_CITY), KeyboardButton(text=BTN_WORK_FORMAT)],
        [KeyboardButton(text=BTN_VIEW), KeyboardButton(text=BTN_STOP)],
    ]
    rows.extend(extra_rows or [])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _json_list(value: str) -> list[str]:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


async def _delete_quietly(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        logger.debug("Could not delete message %s (probably harmless)", message.message_id)


def _build_language_keyboard(selected_languages: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for lang in LANGUAGES.values():
        if lang.key in selected_languages:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"✅ {lang.label}", callback_data=f"{CALLBACK_PREFIX}:lang:{lang.key}"
                    ),
                    InlineKeyboardButton(
                        text="🗑", callback_data=f"{CALLBACK_PREFIX}:remove:{lang.key}"
                    ),
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=lang.label, callback_data=f"{CALLBACK_PREFIX}:lang:{lang.key}"
                    )
                ]
            )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_tags_keyboard(chosen: list[str], tag_keys: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(tag_keys), 2):
        buttons = []
        for key in tag_keys[i : i + 2]:
            tag = STACK_TAGS[key]
            checked = "✅" if key in chosen else "⬜"
            buttons.append(
                InlineKeyboardButton(
                    text=f"{checked} {tag.label}", callback_data=f"{CALLBACK_PREFIX}:tag:toggle:{key}"
                )
            )
        rows.append(buttons)
    rows.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}:back"),
            InlineKeyboardButton(text="✅ Применить", callback_data=f"{CALLBACK_PREFIX}:apply"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


LANGUAGE_PICKER_TEXT = "Выбери язык — дальше покажу фреймворки/БД для него:"


@router.message(F.text == BTN_ADD_STACK)
async def handle_add_stack_button(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await _delete_quietly(message)
    await state.clear()

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        selected_languages = _json_list(subscriber.languages)

    await message.answer(
        LANGUAGE_PICKER_TEXT, reply_markup=_build_language_keyboard(selected_languages)
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}:lang:"))
async def handle_pick_language(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    language_key = callback.data.split(":")[2]
    tag_keys = visible_tag_keys([language_key])

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        current_skills = set(_json_list(subscriber.skills))

    chosen = [key for key in tag_keys if key in current_skills]

    await state.set_state(StackFSM.picking_tags)
    await state.update_data(language=language_key, chosen=chosen)

    lang_label = LANGUAGES[language_key].label
    await callback.message.edit_text(
        f"{lang_label} — отметь, что нужно (можно несколько), потом «Применить»:",
        reply_markup=_build_tags_keyboard(chosen, tag_keys),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}:remove:"))
async def handle_remove_language(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or callback.data is None:
        await callback.answer()
        return

    language_key = callback.data.split(":")[2]
    await state.clear()

    # Only this language's own tags — universal infra tags (Redis, Docker,
    # etc.) stay, since they may still be relevant to other languages the
    # subscriber kept.
    language_tag_keys = {key for key, tag in STACK_TAGS.items() if tag.language == language_key}

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        new_languages = set(_json_list(subscriber.languages)) - {language_key}
        new_skills = set(_json_list(subscriber.skills)) - language_tag_keys

        await update_subscriber_languages(session, subscriber, list(new_languages))
        await update_subscriber_skills(session, subscriber, list(new_skills))

    lang_label = LANGUAGES[language_key].label
    await callback.message.edit_text(
        LANGUAGE_PICKER_TEXT, reply_markup=_build_language_keyboard(list(new_languages))
    )
    await callback.answer(f"{lang_label} удалён из профиля.")


@router.callback_query(StackFSM.picking_tags, F.data.startswith(f"{CALLBACK_PREFIX}:tag:toggle:"))
async def handle_toggle_tag(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
        return

    tag_key = callback.data.split(":")[3]
    data = await state.get_data()
    language_key = data.get("language")
    chosen = set(data.get("chosen", []))

    if tag_key in chosen:
        chosen.discard(tag_key)
    else:
        chosen.add(tag_key)
    await state.update_data(chosen=list(chosen))

    tag_keys = visible_tag_keys([language_key])
    await callback.message.edit_reply_markup(reply_markup=_build_tags_keyboard(list(chosen), tag_keys))
    await callback.answer()


@router.callback_query(StackFSM.picking_tags, F.data == f"{CALLBACK_PREFIX}:back")
async def handle_back_to_languages(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    await state.clear()

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        selected_languages = _json_list(subscriber.languages)

    await callback.message.edit_text(
        LANGUAGE_PICKER_TEXT, reply_markup=_build_language_keyboard(selected_languages)
    )
    await callback.answer()


@router.callback_query(StackFSM.picking_tags, F.data == f"{CALLBACK_PREFIX}:apply")
async def handle_apply_stack(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    data = await state.get_data()
    language_key = data.get("language")
    chosen = set(data.get("chosen", []))
    await state.clear()

    language_tag_keys = set(visible_tag_keys([language_key]))

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        current_languages = set(_json_list(subscriber.languages))
        current_skills = set(_json_list(subscriber.skills))

        # Only touch this language's own tags (+ universal ones) — tags
        # belonging to other languages added in earlier rounds stay as-is.
        new_skills = (current_skills - language_tag_keys) | chosen
        new_languages = current_languages | {language_key}

        await update_subscriber_languages(session, subscriber, list(new_languages))
        await update_subscriber_skills(session, subscriber, list(new_skills))

    lang_label = LANGUAGES[language_key].label
    await callback.message.edit_text(
        f"Готово — {lang_label} добавлен в твой профиль. Нажми «{BTN_ADD_STACK}» ещё раз, "
        f"чтобы добавить другой язык, или «{BTN_VIEW}», чтобы начать получать вакансии."
    )
    await callback.answer()


@router.message(F.text == BTN_CITY)
async def handle_city_button(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await _delete_quietly(message)
    await state.set_state(CityFSM.waiting_input)

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        current_city = subscriber.city

    if current_city:
        text = (
            f"Сейчас фильтр по городу: «{current_city}».\n"
            f"Напиши новый город, или «-», чтобы убрать фильтр (будут приходить вакансии из всех городов)."
        )
    else:
        text = (
            "Фильтр по городу не задан — приходят вакансии из всех городов.\n"
            "Напиши город, чтобы получать только вакансии из него "
            "(удалённые вакансии приходят всегда, независимо от города)."
        )
    await message.answer(text)


@router.message(CityFSM.waiting_input, F.text.not_in(MENU_BUTTON_TEXTS))
async def handle_city_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text:
        return
    await _delete_quietly(message)
    await state.clear()

    text = message.text.strip()
    city = None if text.lower() in CITY_CLEAR_WORDS else text

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        await update_subscriber_city(session, subscriber, city)

    if city:
        await message.answer(f"Готово — буду присылать вакансии из города «{city}» (плюс удалённые).")
    else:
        await message.answer("Готово — фильтр по городу убран, присылаю вакансии из всех городов.")


def _build_work_format_keyboard(chosen: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for key, label in WORK_FORMATS.items():
        checked = "✅" if key in chosen else "⬜"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{checked} {label}", callback_data=f"{WORK_FORMAT_CALLBACK_PREFIX}:toggle:{key}"
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="✅ Применить", callback_data=f"{WORK_FORMAT_CALLBACK_PREFIX}:apply")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == BTN_WORK_FORMAT)
async def handle_work_format_button(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await _delete_quietly(message)

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        chosen = _json_list(subscriber.work_formats)

    await state.set_state(WorkFormatFSM.picking)
    await state.update_data(chosen=chosen)
    await message.answer(
        "Выбери желаемый формат работы (можно несколько, или ничего — тогда без фильтра):",
        reply_markup=_build_work_format_keyboard(chosen),
    )


@router.callback_query(WorkFormatFSM.picking, F.data.startswith(f"{WORK_FORMAT_CALLBACK_PREFIX}:toggle:"))
async def handle_toggle_work_format(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None:
        await callback.answer()
        return

    key = callback.data.split(":")[2]
    data = await state.get_data()
    chosen = set(data.get("chosen", []))
    if key in chosen:
        chosen.discard(key)
    else:
        chosen.add(key)
    await state.update_data(chosen=list(chosen))

    await callback.message.edit_reply_markup(reply_markup=_build_work_format_keyboard(list(chosen)))
    await callback.answer()


@router.callback_query(WorkFormatFSM.picking, F.data == f"{WORK_FORMAT_CALLBACK_PREFIX}:apply")
async def handle_apply_work_format(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    data = await state.get_data()
    chosen = list(set(data.get("chosen", [])))
    await state.clear()

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        await update_subscriber_work_formats(session, subscriber, chosen)

    if chosen:
        labels = ", ".join(WORK_FORMATS[key] for key in chosen)
        text = f"Готово — буду присылать вакансии с форматом: {labels}."
    else:
        text = "Готово — фильтр по формату работы убран, присылаю вакансии любого формата."
    await callback.message.edit_text(text)
    await callback.answer()


@router.message(F.text == BTN_VIEW)
async def handle_view_vacancies(message: Message) -> None:
    if message.from_user is None:
        return
    await _delete_quietly(message)

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        subscriber = await resume_subscriber_by_telegram_id(session, message.from_user.id)

    if subscriber is None:
        await message.answer("Сначала напиши /start")
        return
    if subscriber.status == "blocked":
        await message.answer("Доступ ограничен администратором.")
        return

    sent = await resend_matching_backlog(message.bot, subscriber)
    if sent:
        await message.answer(f"Рассылка включена. Нашёл и отправил {sent} подходящих вакансий за неделю.")
    else:
        await message.answer(
            "Рассылка включена. Подходящих вакансий за последнюю неделю пока нет — "
            "пришлю, как только появятся новые."
        )


@router.message(F.text == BTN_STOP)
async def handle_stop_broadcast(message: Message) -> None:
    if message.from_user is None:
        return
    await _delete_quietly(message)

    async with async_session() as session:
        await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        await pause_subscriber_by_telegram_id(session, message.from_user.id)

    await message.answer(f"Рассылка остановлена. Включить снова — кнопка «{BTN_VIEW}».")
