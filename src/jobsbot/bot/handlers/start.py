from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_or_create_subscriber

router = Router()

WELCOME_TEXT = (
    "Привет! Я собираю вакансии по Python с hh.ru и из Telegram-каналов "
    "и присылаю новые по мере появления.\n\n"
    "Ты подписан — просто жди новых вакансий.\n\n"
    "Команда /stack — укажи свой стек (Django, Redis, Kafka и т.п.), и буду "
    "присылать только вакансии, где он упоминается."
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    if message.from_user is None:
        return
    async with async_session() as session:
        await get_or_create_subscriber(
            session, telegram_user_id=message.from_user.id, username=message.from_user.username
        )
    await message.answer(WELCOME_TEXT)
