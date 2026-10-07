from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from jobsbot.bot.handlers.subscriber_menu import BTN_ADD_STACK, BTN_VIEW, build_menu_keyboard
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_or_create_subscriber

router = Router()

WELCOME_TEXT = (
    "Привет! Я собираю вакансии по разработке с hh.ru и из Telegram-каналов.\n\n"
    f"Сначала нажми «{BTN_ADD_STACK}» — выбери язык(и) программирования и фреймворки/БД, "
    "которые тебе интересны (можно добавить несколько, по одному языку за раз).\n\n"
    f"Когда настроишь — нажми «{BTN_VIEW}», и я начну присылать подходящие вакансии "
    "(сначала то, что набралось за последнюю неделю, потом новые по мере появления). "
    "Рассылку можно остановить и включить обратно в любой момент кнопками снизу."
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    if message.from_user is None:
        return
    async with async_session() as session:
        await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
    await message.answer(WELCOME_TEXT, reply_markup=build_menu_keyboard())
