from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from jobsbot.bot.handlers.subscriber_menu import BTN_ADD_STACK, BTN_VIEW, current_menu_keyboard, send_system_message
from jobsbot.bot.subscription_gate import GATE_CHECK_CALLBACK, build_gate_keyboard, build_gate_text, get_missing_channels
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_or_create_subscriber, list_required_channels, mark_subscription_gate_passed

router = Router()

WELCOME_TEXT = (
    "Привет! Я собираю вакансии по разработке с hh.ru и из Telegram-каналов.\n\n"
    f"Сначала нажми «{BTN_ADD_STACK}» — выбери язык(и) программирования и фреймворки/БД, "
    "которые тебе интересны (можно добавить несколько, по одному языку за раз).\n\n"
    f"Когда настроишь — нажми «{BTN_VIEW}», и я начну присылать подходящие вакансии "
    "(сначала то, что набралось за последнюю неделю, потом новые по мере появления). "
    "Рассылку можно остановить и включить обратно в любой момент кнопками снизу."
)


async def _send_welcome(bot, telegram_user_id: int) -> None:
    await send_system_message(bot, telegram_user_id, WELCOME_TEXT, reply_markup=await current_menu_keyboard(telegram_user_id))


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    if message.from_user is None:
        return
    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
        gate_passed = subscriber.subscription_gate_passed
        channels = [] if gate_passed else await list_required_channels(session)

    if channels:
        missing = await get_missing_channels(message.bot, channels, message.from_user.id)
        if missing:
            await send_system_message(
                message.bot, message.from_user.id, build_gate_text(missing), reply_markup=build_gate_keyboard()
            )
            return

    if not gate_passed:
        async with async_session() as session:
            subscriber = await get_or_create_subscriber(
                session, telegram_user_id=message.from_user.id, username=message.from_user.username
            )
            await mark_subscription_gate_passed(session, subscriber)

    await _send_welcome(message.bot, message.from_user.id)


@router.callback_query(F.data == GATE_CHECK_CALLBACK)
async def handle_gate_recheck(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    async with async_session() as session:
        await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        channels = await list_required_channels(session)

    missing = await get_missing_channels(callback.bot, channels, callback.from_user.id)
    if missing:
        await callback.answer("Похоже, не на все каналы подписался — проверь и попробуй снова.", show_alert=True)
        return

    async with async_session() as session:
        subscriber = await get_or_create_subscriber(
            session, telegram_user_id=callback.from_user.id, username=callback.from_user.username
        )
        await mark_subscription_gate_passed(session, subscriber)

    await callback.answer("Готово!")
    await _send_welcome(callback.bot, callback.from_user.id)
