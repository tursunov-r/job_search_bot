import json
import logging
from collections import Counter
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
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

from jobsbot.ads.campaigns import send_broadcast_now
from jobsbot.ai.gemini_client import GeminiError, generate
from jobsbot.bot.permissions import PERMISSIONS, get_permissions, has_permission, is_super_admin
from jobsbot.config import settings
from jobsbot.processing.languages import LANGUAGES
from jobsbot.processing.work_formats import WORK_FORMATS
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import (
    add_required_channel,
    add_staff_member,
    add_telegram_channel,
    block_subscriber_by_telegram_id,
    get_broadcastable_subscribers,
    get_source_by_id,
    get_subscriber_counts_by_status,
    list_required_channels,
    list_staff_members,
    list_telegram_channels,
    remove_required_channel,
    remove_staff_member,
    remove_telegram_channel,
    unblock_subscriber_by_telegram_id,
)

logger = logging.getLogger(__name__)
router = Router()

_AD_DRAFT_PROMPT_PATH = Path(__file__).resolve().parents[4] / "docs" / "gemini_promts" / "ad_draft.md"
_AD_DRAFT_PROMPT_TEXT = _AD_DRAFT_PROMPT_PATH.read_text(encoding="utf-8")

BTN_CHANNELS = "📡 Каналы"
BTN_USERS = "🚫 Пользователи"
BTN_ADS = "📢 Реклама"
BTN_STAFF = "👥 Сотрудники"
BTN_STATS = "📊 Статистика"
BTN_GATE_CHANNELS = "🔐 Обязательные каналы"
MENU_BUTTON_TEXTS = {BTN_CHANNELS, BTN_USERS, BTN_ADS, BTN_STAFF, BTN_STATS, BTN_GATE_CHANNELS}


class AdminFSM(StatesGroup):
    add_channel = State()
    block_user = State()
    add_staff_id = State()
    add_staff_permissions = State()
    broadcast_text = State()
    broadcast_confirm = State()
    add_gate_channel = State()


async def get_admin_menu_rows(user_id: int) -> list[list[KeyboardButton]]:
    perms = await get_permissions(user_id)
    rows: list[list[KeyboardButton]] = []
    if "manage_channels" in perms and settings.telegram_enabled:
        rows.append([KeyboardButton(text=BTN_CHANNELS)])
    if "block_users" in perms:
        rows.append([KeyboardButton(text=BTN_USERS)])
    if "manage_ads" in perms:
        rows.append([KeyboardButton(text=BTN_ADS)])
    if is_super_admin(user_id):
        rows.append([KeyboardButton(text=BTN_STAFF), KeyboardButton(text=BTN_STATS)])
        rows.append([KeyboardButton(text=BTN_GATE_CHANNELS)])
    return rows


async def build_admin_keyboard(user_id: int) -> ReplyKeyboardMarkup | None:
    rows = await get_admin_menu_rows(user_id)
    if not rows:
        return None
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@router.message(Command("admin"))
async def handle_admin(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.clear()
    keyboard = await build_admin_keyboard(message.from_user.id)
    if keyboard is None:
        await message.answer("У тебя нет прав администратора.")
        return
    await message.answer("Меню администратора:", reply_markup=keyboard)


# ---- Channels ----


async def _show_channels(message: Message) -> None:
    async with async_session() as session:
        channels = await list_telegram_channels(session)

    lines = [f"{'🟢' if c.enabled else '⚪️'} {c.identifier}" for c in channels] or ["Пока нет каналов."]
    rows = [[InlineKeyboardButton(text="➕ Добавить", callback_data="chan:add")]]
    for c in channels:
        if c.enabled:
            rows.append([InlineKeyboardButton(text=f"🗑 {c.identifier}", callback_data=f"chan:rm:{c.id}")])
    await message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.message(F.text == BTN_CHANNELS)
async def handle_channels_button(message: Message) -> None:
    if message.from_user is None or not await has_permission(message.from_user.id, "manage_channels"):
        return
    if not settings.telegram_enabled:
        await message.answer(
            "Telegram-парсинг отключён (нет TELEGRAM_API_ID/TELEGRAM_API_HASH в .env)."
        )
        return
    await _show_channels(message)


@router.callback_query(F.data == "chan:add")
async def handle_add_channel_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not await has_permission(callback.from_user.id, "manage_channels"):
        await callback.answer()
        return
    await state.set_state(AdminFSM.add_channel)
    await callback.message.answer("Пришли юзернейм канала (без @) или ссылку t.me/...")
    await callback.answer()


@router.callback_query(F.data.startswith("chan:rm:"))
async def handle_remove_channel(callback: CallbackQuery) -> None:
    if callback.from_user is None or not await has_permission(callback.from_user.id, "manage_channels"):
        await callback.answer()
        return
    source_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        source = await get_source_by_id(session, source_id)
        if source:
            await remove_telegram_channel(session, source.identifier)
    await callback.answer("Удалено")
    await _show_channels(callback.message)


def _extract_channel_username(text: str) -> str | None:
    text = text.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.split("?")[0].strip("/").strip()
    return text or None


@router.message(AdminFSM.add_channel)
async def handle_channel_username_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not await has_permission(message.from_user.id, "manage_channels"):
        await state.clear()
        return
    if message.text in MENU_BUTTON_TEXTS:
        await state.clear()
        await message.answer("Отменено. Нажми кнопку меню ещё раз.")
        return

    username = _extract_channel_username(message.text or "")
    if not username:
        await message.answer("Не понял. Пришли юзернейм канала или ссылку t.me/...")
        return

    async with async_session() as session:
        await add_telegram_channel(session, username)
    await state.clear()
    await message.answer(f"Канал @{username} добавлен.")


# ---- Users (block / unblock) ----


@router.message(F.text == BTN_USERS)
async def handle_users_button(message: Message) -> None:
    if message.from_user is None or not await has_permission(message.from_user.id, "block_users"):
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Заблокировать", callback_data="user:block")],
            [InlineKeyboardButton(text="✅ Разблокировать", callback_data="user:unblock")],
        ]
    )
    await message.answer("Выбери действие:", reply_markup=keyboard)


@router.callback_query(F.data.in_({"user:block", "user:unblock"}))
async def handle_user_action_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not await has_permission(callback.from_user.id, "block_users"):
        await callback.answer()
        return
    action = callback.data.split(":")[1]
    await state.set_state(AdminFSM.block_user)
    await state.update_data(action=action)
    prompt = (
        "Пришли Telegram ID пользователя для блокировки."
        if action == "block"
        else "Пришли Telegram ID пользователя для разблокировки."
    )
    await callback.message.answer(prompt)
    await callback.answer()


@router.message(AdminFSM.block_user)
async def handle_block_user_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not await has_permission(message.from_user.id, "block_users"):
        await state.clear()
        return
    if message.text in MENU_BUTTON_TEXTS:
        await state.clear()
        await message.answer("Отменено. Нажми кнопку меню ещё раз.")
        return

    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer("Нужно число — Telegram ID пользователя.")
        return

    data = await state.get_data()
    action = data.get("action", "block")
    target_id = int(text)

    async with async_session() as session:
        if action == "block":
            subscriber = await block_subscriber_by_telegram_id(session, target_id)
        else:
            subscriber = await unblock_subscriber_by_telegram_id(session, target_id)

    await state.clear()
    if subscriber is None:
        await message.answer("Подписчик с таким ID не найден.")
        return
    verb = "заблокирован" if action == "block" else "разблокирован"
    await message.answer(f"Пользователь {target_id} {verb}.")


# ---- Ads (shortcut to existing commands, not reimplemented here) ----


@router.message(F.text == BTN_ADS)
async def handle_ads_button(message: Message) -> None:
    if message.from_user is None or not await has_permission(message.from_user.id, "manage_ads"):
        return
    text = (
        "Команды для рекламных кампаний:\n"
        "/newad Название | Текст — создать\n"
        "/ads — список\n"
        "/activatead <id> — запустить\n"
        "/canceladc <id> — отменить\n"
        "/broadcastad <id> — разослать сейчас"
    )
    keyboard = None
    if is_super_admin(message.from_user.id):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="📝 Отправить всем сейчас", callback_data="ad:start")]]
        )
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "ad:start")
async def handle_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(AdminFSM.broadcast_text)
    await callback.message.answer(
        "Пришли текст рекламного сообщения — он уйдёт всем пользователям, которые не блокировали бота "
        "(включая тех, у кого рассылка вакансий на паузе)."
    )
    await callback.answer()


def _broadcast_preview_keyboard(offer_ai_draft: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="✅ Отправить всем", callback_data="ad:confirm")]]
    if offer_ai_draft:
        rows.append([InlineKeyboardButton(text="🤖 Оформить через AI", callback_data="ad:ai_draft")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="ad:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(AdminFSM.broadcast_text)
async def handle_broadcast_text_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not is_super_admin(message.from_user.id):
        await state.clear()
        return
    if message.text in MENU_BUTTON_TEXTS:
        await state.clear()
        await message.answer("Отменено. Нажми кнопку меню ещё раз.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым — пришли текст объявления.")
        return

    # broadcast_text_original never changes once set — "↩️ Свой текст"
    # always restores exactly what was typed here, even after any number
    # of AI redrafts.
    await state.update_data(broadcast_text=text, broadcast_text_original=text)
    await state.set_state(AdminFSM.broadcast_confirm)
    await message.answer(
        f"Предпросмотр:\n\n{text}\n\nОтправить это всем пользователям?",
        reply_markup=_broadcast_preview_keyboard(offer_ai_draft=settings.gemini_enabled),
    )


@router.callback_query(AdminFSM.broadcast_confirm, F.data == "ad:ai_draft")
async def handle_broadcast_ai_draft(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return
    if not settings.gemini_enabled:
        await callback.answer()
        return

    data = await state.get_data()
    original = data.get("broadcast_text_original", "")
    await callback.answer("Составляю черновик...")
    await callback.message.edit_text("⏳ Составляю черновик через AI...")

    try:
        draft = await generate(f"{_AD_DRAFT_PROMPT_TEXT}\n{original}")
    except GeminiError:
        logger.exception("Ad draft generation failed")
        await state.set_state(AdminFSM.broadcast_confirm)
        await callback.message.edit_text(
            f"Не получилось составить черновик — попробуй ещё раз позже.\n\nПредпросмотр:\n\n{original}",
            reply_markup=_broadcast_preview_keyboard(offer_ai_draft=True),
        )
        return

    await state.update_data(broadcast_text=draft)
    await state.set_state(AdminFSM.broadcast_confirm)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить всем", callback_data="ad:confirm")],
            [
                InlineKeyboardButton(text="🔄 Другой вариант", callback_data="ad:ai_draft"),
                InlineKeyboardButton(text="↩️ Свой текст", callback_data="ad:use_raw"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="ad:cancel")],
        ]
    )
    await callback.message.edit_text(f"Черновик от AI:\n\n{draft}\n\nОтправить это всем пользователям?", reply_markup=keyboard)


@router.callback_query(AdminFSM.broadcast_confirm, F.data == "ad:use_raw")
async def handle_broadcast_use_raw(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return
    data = await state.get_data()
    original = data.get("broadcast_text_original", "")
    await state.update_data(broadcast_text=original)
    await callback.message.edit_text(
        f"Предпросмотр:\n\n{original}\n\nОтправить это всем пользователям?",
        reply_markup=_broadcast_preview_keyboard(offer_ai_draft=settings.gemini_enabled),
    )
    await callback.answer()


@router.callback_query(AdminFSM.broadcast_confirm, F.data == "ad:cancel")
async def handle_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await callback.message.edit_text("Отменено, рассылка не отправлена.")
    await callback.answer()


@router.callback_query(AdminFSM.broadcast_confirm, F.data == "ad:confirm")
async def handle_broadcast_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return
    data = await state.get_data()
    text = data.get("broadcast_text")
    await state.clear()
    await callback.message.edit_text("Отправляю...")
    await callback.answer()

    campaign, sent, total = await send_broadcast_now(callback.bot, text)
    await callback.message.edit_text(f"Готово — отправлено {sent} из {total} пользователей (кампания #{campaign.id}).")


# ---- Required channels / subscription gate (super admin only) ----


async def _show_gate_channels(message: Message) -> None:
    async with async_session() as session:
        channels = await list_required_channels(session)

    lines = [f"🔒 {c.title or c.username} (@{c.username})" for c in channels] or [
        "Пока нет обязательных каналов — новые пользователи проходят без проверки."
    ]
    rows = [[InlineKeyboardButton(text="➕ Добавить", callback_data="gatechan:add")]]
    for c in channels:
        rows.append([InlineKeyboardButton(text=f"🗑 {c.username}", callback_data=f"gatechan:rm:{c.id}")])
    await message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.message(F.text == BTN_GATE_CHANNELS)
async def handle_gate_channels_button(message: Message) -> None:
    if message.from_user is None or not is_super_admin(message.from_user.id):
        return
    await _show_gate_channels(message)


@router.callback_query(F.data == "gatechan:add")
async def handle_add_gate_channel_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(AdminFSM.add_gate_channel)
    await callback.message.answer(
        "Пришли @username публичного канала или группы (бот должен быть туда добавлен, "
        "желательно админом, иначе проверка подписки не сработает)."
    )
    await callback.answer()


@router.message(AdminFSM.add_gate_channel)
async def handle_gate_channel_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not is_super_admin(message.from_user.id):
        await state.clear()
        return
    if message.text in MENU_BUTTON_TEXTS:
        await state.clear()
        await message.answer("Отменено. Нажми кнопку меню ещё раз.")
        return

    username = _extract_channel_username(message.text or "")
    if not username:
        await message.answer("Не понял. Пришли юзернейм канала или ссылку t.me/...")
        return

    title = None
    try:
        chat = await message.bot.get_chat(f"@{username}")
        title = chat.title
    except Exception:
        pass

    async with async_session() as session:
        try:
            await add_required_channel(session, username, title)
        except Exception:
            await state.clear()
            await message.answer(f"@{username} уже в списке или произошла ошибка.")
            return

    await state.clear()
    await message.answer(f"Готово — @{username} добавлен в обязательные каналы.")


@router.callback_query(F.data.startswith("gatechan:rm:"))
async def handle_remove_gate_channel(callback: CallbackQuery) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return
    channel_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        await remove_required_channel(session, channel_id)
    await callback.answer("Удалено")
    await _show_gate_channels(callback.message)


# ---- Staff (super admin only) ----


def _build_permission_keyboard(chosen: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{'✅' if key in chosen else '⬜'} {label}", callback_data=f"staffperm:toggle:{key}")]
        for key, label in PERMISSIONS.items()
    ]
    rows.append([InlineKeyboardButton(text="Готово", callback_data="staffperm:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_staff(message: Message) -> None:
    async with async_session() as session:
        staff = await list_staff_members(session)

    lines = []
    for s in staff:
        perms = ", ".join(json.loads(s.permissions)) or "—"
        status_icon = "🟢" if s.status == "active" else "⚪️"
        lines.append(f"{status_icon} {s.telegram_user_id} (@{s.username or '?'}) — {perms}")
    text = "\n".join(lines) or "Пока нет сотрудников."

    rows = [[InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="staff:add")]]
    for s in staff:
        if s.status == "active":
            rows.append([InlineKeyboardButton(text=f"🗑 {s.telegram_user_id}", callback_data=f"staff:rm:{s.id}")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.message(F.text == BTN_STAFF)
async def handle_staff_button(message: Message) -> None:
    if message.from_user is None or not is_super_admin(message.from_user.id):
        return
    await _show_staff(message)


@router.callback_query(F.data == "staff:add")
async def handle_add_staff_start(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(AdminFSM.add_staff_id)
    await callback.message.answer("Пришли Telegram ID нового сотрудника.")
    await callback.answer()


@router.message(AdminFSM.add_staff_id)
async def handle_staff_id_input(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not is_super_admin(message.from_user.id):
        await state.clear()
        return
    if message.text in MENU_BUTTON_TEXTS:
        await state.clear()
        await message.answer("Отменено. Нажми кнопку меню ещё раз.")
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужно число — Telegram ID.")
        return

    await state.update_data(new_staff_id=int(text), chosen_permissions=[])
    await state.set_state(AdminFSM.add_staff_permissions)
    await message.answer("Выбери права:", reply_markup=_build_permission_keyboard([]))


@router.callback_query(F.data.startswith("staffperm:"))
async def handle_staff_permission_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return

    parts = callback.data.split(":")
    action = parts[1]
    data = await state.get_data()
    chosen = set(data.get("chosen_permissions", []))

    if action == "toggle":
        key = parts[2]
        if key in chosen:
            chosen.discard(key)
        else:
            chosen.add(key)
        await state.update_data(chosen_permissions=list(chosen))
        await callback.message.edit_reply_markup(reply_markup=_build_permission_keyboard(list(chosen)))
        await callback.answer()
        return

    new_staff_id = data.get("new_staff_id")
    async with async_session() as session:
        await add_staff_member(
            session,
            new_staff_id,
            username=None,
            permissions=list(chosen),
            added_by_telegram_user_id=callback.from_user.id,
        )
    await state.clear()
    await callback.message.edit_text(f"Сотрудник {new_staff_id} добавлен с правами: {', '.join(chosen) or '—'}.")
    await callback.answer()


@router.callback_query(F.data.startswith("staff:rm:"))
async def handle_remove_staff(callback: CallbackQuery) -> None:
    if callback.from_user is None or not is_super_admin(callback.from_user.id):
        await callback.answer()
        return
    staff_id = int(callback.data.split(":")[2])
    async with async_session() as session:
        await remove_staff_member(session, staff_id)
    await callback.answer("Удалён")
    await _show_staff(callback.message)


# ---- Stats (super admin only) ----

_STATUS_LABELS = {"active": "активных", "paused": "на паузе", "blocked": "заблокированных"}


def _json_list(value: str) -> list[str]:
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def _format_top(counts: Counter, label_for: callable, limit: int = 15) -> list[str]:
    if not counts:
        return ["  (пока никто не выбрал)"]
    return [f"  {label_for(key)}: {count}" for key, count in counts.most_common(limit)]


@router.message(F.text == BTN_STATS)
async def handle_stats_button(message: Message) -> None:
    if message.from_user is None or not is_super_admin(message.from_user.id):
        return

    async with async_session() as session:
        counts = await get_subscriber_counts_by_status(session)
        # Status breakdown is cheap (grouped in SQL); language/city/format
        # popularity needs the actual filter values, which only live as
        # JSON-in-text columns — fine to aggregate in Python at this scale
        # (subscriber count, not vacancy count).
        reachable_subscribers = await get_broadcastable_subscribers(session)

    language_counts = Counter()
    city_counts = Counter()
    work_format_counts = Counter()
    for subscriber in reachable_subscribers:
        language_counts.update(_json_list(subscriber.languages))
        city_counts.update(_json_list(subscriber.cities))
        work_format_counts.update(_json_list(subscriber.work_formats))

    total = sum(counts.values())
    lines = [f"👤 Всего зарегистрировано: {total}"]
    for status, label in _STATUS_LABELS.items():
        lines.append(f"— {label}: {counts.get(status, 0)}")

    lines.append("\n💻 Топ языков/сфер (по выбору в фильтрах):")
    lines.extend(_format_top(language_counts, lambda key: LANGUAGES[key].label if key in LANGUAGES else key))

    lines.append("\n🏙 Топ городов (по фильтру подписчиков):")
    lines.extend(_format_top(city_counts, lambda key: key))

    lines.append("\n🧭 Форматы работы (по фильтру подписчиков):")
    lines.extend(_format_top(work_format_counts, lambda key: WORK_FORMATS.get(key, key)))

    await message.answer("\n".join(lines))
