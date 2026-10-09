from datetime import datetime, timezone

from aiogram import Bot

from jobsbot.ads.scheduler import broadcast_campaign_now
from jobsbot.storage.db import async_session
from jobsbot.storage.models import AdCampaign
from jobsbot.storage.repo import (
    create_campaign as _create_campaign,
    get_campaign,
    list_campaigns,
    set_campaign_status,
)


async def new_draft_campaign(name: str, message_text: str, send_interval_hours: int = 24) -> AdCampaign:
    async with async_session() as session:
        return await _create_campaign(
            session,
            name=name,
            message_text=message_text,
            send_interval_hours=send_interval_hours,
            status="draft",
        )


async def activate_campaign(campaign_id: int) -> AdCampaign | None:
    async with async_session() as session:
        campaign = await get_campaign(session, campaign_id)
        if campaign is None:
            return None
        return await set_campaign_status(session, campaign, "active")


async def cancel_campaign(campaign_id: int) -> AdCampaign | None:
    async with async_session() as session:
        campaign = await get_campaign(session, campaign_id)
        if campaign is None:
            return None
        return await set_campaign_status(session, campaign, "cancelled")


async def get_all_campaigns() -> list[AdCampaign]:
    async with async_session() as session:
        return await list_campaigns(session)


async def send_broadcast_now(bot: Bot, message_text: str) -> tuple[AdCampaign, int, int]:
    """One-off ad blast to every reachable subscriber, kicked off straight
    from the admin menu rather than through /newad + /activatead +
    /broadcastad. No send_interval_hours (never due again on its own) and
    the campaign is immediately marked "completed" right after sending, so
    the recurring broadcast_due_campaigns job never picks it up a second
    time. Still recorded as a normal AdCampaign — shows up in /ads and
    tracks impressions the same way as any other campaign.
    """
    name = f"Разовая рассылка {datetime.now(timezone.utc):%Y-%m-%d %H:%M}"
    async with async_session() as session:
        campaign = await _create_campaign(session, name=name, message_text=message_text, status="active")

    sent, total = await broadcast_campaign_now(bot, campaign)

    async with async_session() as session:
        campaign = await get_campaign(session, campaign.id)
        await set_campaign_status(session, campaign, "completed")

    return campaign, sent, total
