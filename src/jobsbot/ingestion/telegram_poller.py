"""Polling-based ingestion from public Telegram channels/chats.

Used to be event-driven (a persistent MTProto connection reacting to
events.NewMessage instantly). Switched to polling to match the other two
sources (HH, LinkedIn) — one uniform architecture of periodic APScheduler
jobs, which is simpler and more resilient on unreliable home-network
hardware (a Raspberry Pi) than keeping a long-lived event listener alive.

Still uses a Telegram *user* account (Telethon/MTProto, not the Bot API,
since plain bots cannot join channels/groups on their own) — just calls
client.get_messages(min_id=...) on a timer instead of registering a live
event handler.
"""

import logging
import re

from telethon import TelegramClient

from jobsbot.config import settings
from jobsbot.ingestion.base import RawVacancy
from jobsbot.processing.pipeline import ingest
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import (
    get_enabled_telegram_channel_identifiers,
    get_or_create_source,
    update_source_last_message_id,
)

logger = logging.getLogger(__name__)

_LEADING_NOISE_RE = re.compile(r"^[^\w]+", re.UNICODE)

MESSAGES_PER_POLL = 100


def parse_message_text(text: str | None) -> RawVacancy | None:
    """First non-empty line (minus leading emoji/bullets) becomes the title,
    the full message becomes the description for language detection."""
    if not text or not text.strip():
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    title = _LEADING_NOISE_RE.sub("", lines[0]).strip() or lines[0]
    return RawVacancy(title=title, description=text, url=None)


def build_message_url(channel_username: str | None, message_id: int) -> str | None:
    if not channel_username:
        return None
    return f"https://t.me/{channel_username}/{message_id}"


class TelegramChannelPoller:
    """Channels to poll are configured at runtime via the bot's /admin menu
    (stored in the `sources` table, type='telegram_channel', enabled=True) —
    not a fixed list from .env. That means the Telethon client has to be
    ready to go from startup regardless of whether any channel is configured
    yet, since one could be added live without restarting the process."""

    def __init__(self) -> None:
        self.client = TelegramClient(
            settings.telegram_session_path,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

    async def start(self) -> None:
        await self.client.start()
        logger.info("Telegram channel poller connected")

    async def poll_once(self) -> None:
        async with async_session() as session:
            channels = await get_enabled_telegram_channel_identifiers(session)

        for channel in channels:
            try:
                await self._poll_channel(channel)
            except Exception:
                logger.exception("Polling channel %s failed", channel)

    async def _poll_channel(self, channel: str) -> None:
        async with async_session() as session:
            source = await get_or_create_source(session, "telegram_channel", channel, channel)
            min_id = source.last_message_id or 0
            source_id = source.id

        messages = await self.client.get_messages(channel, min_id=min_id, limit=MESSAGES_PER_POLL)
        if not messages:
            return

        # Telethon returns newest-first; ingest oldest-first for a sane id order.
        messages = list(reversed(messages))
        max_id_seen = min_id

        for message in messages:
            raw = parse_message_text(message.message)
            if raw is not None:
                raw.url = build_message_url(channel, message.id)
                raw.posted_at = message.date
                raw.source_chat_id = message.chat_id
                raw.source_message_id = message.id

                async with async_session() as session:
                    vacancy = await ingest(session, raw, source_id)
                    if vacancy:
                        logger.info("New vacancy from channel %s: %s", channel, vacancy.title)

            max_id_seen = max(max_id_seen, message.id)

        if max_id_seen > min_id:
            async with async_session() as session:
                await update_source_last_message_id(session, source_id, max_id_seen)

    async def stop(self) -> None:
        if self.client.is_connected():
            await self.client.disconnect()
