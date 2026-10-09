import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from jobsbot.storage.db import async_session
from jobsbot.storage.models import AdCampaign
from jobsbot.storage.repo import (
    get_active_campaigns,
    get_broadcastable_subscribers,
    get_last_impression_sent_at,
    record_ad_impression,
)

logger = logging.getLogger(__name__)


def _is_due(campaign: AdCampaign, last_sent_at: datetime | None) -> bool:
    if last_sent_at is None:
        return True
    if not campaign.send_interval_hours:
        return False
    return datetime.now(timezone.utc) >= last_sent_at + timedelta(hours=campaign.send_interval_hours)


async def broadcast_campaign_now(bot: Bot, campaign: AdCampaign) -> tuple[int, int]:
    """Returns (sent, total) — total is everyone who hasn't blocked the bot,
    sent is how many of those actually got the message this round."""
    async with async_session() as session:
        subscribers = await get_broadcastable_subscribers(session)
        sent = 0
        for subscriber in subscribers:
            try:
                await bot.send_message(subscriber.telegram_user_id, campaign.message_text)
                await record_ad_impression(session, campaign.id, subscriber.id, "sent")
                sent += 1
            except TelegramForbiddenError:
                await record_ad_impression(session, campaign.id, subscriber.id, "blocked")
                subscriber.status = "blocked"
                session.add(subscriber)
                await session.commit()
            except TelegramRetryAfter as exc:
                logger.warning("Ad broadcast rate limited, retry after %s", exc.retry_after)
                break
            except Exception:
                logger.exception("Failed to send ad campaign %s to %s", campaign.id, subscriber.telegram_user_id)
                await record_ad_impression(session, campaign.id, subscriber.id, "failed")
        logger.info("Ad campaign '%s' broadcast to %d/%d subscribers", campaign.name, sent, len(subscribers))
        return sent, len(subscribers)


async def broadcast_due_campaigns(bot: Bot) -> None:
    async with async_session() as session:
        campaigns = await get_active_campaigns(session)
        due_campaigns = []
        for campaign in campaigns:
            last_sent_at = await get_last_impression_sent_at(session, campaign.id)
            if _is_due(campaign, last_sent_at):
                due_campaigns.append(campaign)

    for campaign in due_campaigns:
        await broadcast_campaign_now(bot, campaign)
