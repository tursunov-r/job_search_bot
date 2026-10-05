"""Event-driven ingestion from public Telegram channels/chats.

Unlike HH polling, this does not ask "anything new?" on a timer — it opens a
persistent connection via a Telegram *user* account (Telethon/MTProto, not
the Bot API, since plain bots cannot join channels/groups on their own) and
reacts the instant a new message is posted in one of the configured
channels, pushing it straight through the same filter/dedup pipeline used
by the HH adapter.
"""

import logging
import re

from telethon import TelegramClient, events
from telethon.events import NewMessage

from jobsbot.config import settings
from jobsbot.ingestion.base import RawVacancy
from jobsbot.processing.pipeline import ingest
from jobsbot.storage.db import async_session
from jobsbot.storage.repo import get_or_create_source

logger = logging.getLogger(__name__)

_LEADING_NOISE_RE = re.compile(r"^[^\w]+", re.UNICODE)


def parse_message_text(text: str | None) -> RawVacancy | None:
    """First non-empty line (minus leading emoji/bullets) becomes the title,
    the full message becomes the description for keyword filtering."""
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


class TelegramChannelListener:
    def __init__(self) -> None:
        self.channels = settings.telegram_channel_list
        self.enabled = bool(self.channels)
        self.client = TelegramClient(
            settings.telegram_session_path,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

    async def start(self) -> None:
        if not self.enabled:
            logger.warning("TELEGRAM_CHANNELS is empty, channel listener disabled")
            return

        await self.client.start()

        for channel in self.channels:
            try:
                await self.client.get_entity(channel)
            except Exception:
                logger.exception("Could not resolve configured channel %s", channel)

        self.client.add_event_handler(self._on_new_message, events.NewMessage(chats=self.channels))
        logger.info("Telegram channel listener started for: %s", self.channels)

    async def _on_new_message(self, event: NewMessage.Event) -> None:
        raw = parse_message_text(event.message.message)
        if raw is None:
            return

        chat = await event.get_chat()
        username = getattr(chat, "username", None)
        raw.url = build_message_url(username, event.message.id)
        raw.posted_at = event.message.date

        async with async_session() as session:
            source = await get_or_create_source(
                session,
                "telegram_channel",
                username or str(event.chat_id),
                username,
            )
            vacancy = await ingest(session, raw, source.id)
            if vacancy:
                logger.info("New vacancy from channel @%s: %s", username, vacancy.title)

    async def run_forever(self) -> None:
        if not self.enabled:
            return
        await self.client.run_until_disconnected()

    async def stop(self) -> None:
        if self.client.is_connected():
            await self.client.disconnect()
