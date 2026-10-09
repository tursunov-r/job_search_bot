"""Checks whether a user is subscribed to every RequiredChannel before
letting them past /start — see start.py for where this is enforced.
"""

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from jobsbot.storage.models import RequiredChannel

logger = logging.getLogger(__name__)

_SUBSCRIBED_STATUSES = {"creator", "administrator", "member", "restricted"}

GATE_CHECK_CALLBACK = "subgate:check"


async def get_missing_channels(
    bot: Bot, channels: list[RequiredChannel], telegram_user_id: int
) -> list[RequiredChannel]:
    missing = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(f"@{channel.username}", telegram_user_id)
            if member.status not in _SUBSCRIBED_STATUSES:
                missing.append(channel)
        except Exception:
            # The bot isn't a member/admin of this channel, the username is
            # wrong, etc. — fail open on a single misconfigured channel
            # rather than locking out every new user because of it; logged
            # loudly so the admin notices and fixes it.
            logger.warning(
                "Could not check membership for @%s (telegram_user_id=%s)",
                channel.username,
                telegram_user_id,
                exc_info=True,
            )
    return missing


def build_gate_text(missing: list[RequiredChannel]) -> str:
    lines = ["Чтобы начать пользоваться ботом, подпишись на:"]
    for channel in missing:
        label = channel.title or channel.username
        lines.append(f"• {label} — https://t.me/{channel.username}")
    lines.append("\nПосле подписки нажми кнопку ниже.")
    return "\n".join(lines)


def build_gate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Я подписался, проверить", callback_data=GATE_CHECK_CALLBACK)]]
    )
