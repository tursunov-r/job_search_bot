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
