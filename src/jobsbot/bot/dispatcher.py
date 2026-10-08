from aiogram import Bot, Dispatcher

from jobsbot.config import settings


def build_bot() -> Bot:
    return Bot(token=settings.bot_token)


def build_dispatcher() -> Dispatcher:
    from jobsbot.bot.handlers import admin, admin_menu, reports, start, subscriber_menu

    dp = Dispatcher()
    dp.include_router(admin_menu.router)
    dp.include_router(admin.router)
    dp.include_router(reports.router)
    dp.include_router(subscriber_menu.router)
    dp.include_router(start.router)
    return dp
