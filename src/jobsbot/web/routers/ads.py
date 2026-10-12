"""Mirrors the Telegram ad-campaign flows: the /newad + /activatead +
/canceladc + /broadcastad commands (admin.py) and the one-off "📝
Отправить всем сейчас" + "🤖 Оформить через AI" flow (admin_menu.py).
Reuses the same ads.campaigns functions either side calls — this process
has no running aiogram Dispatcher, so a throwaway Bot is created per
request that actually needs to send something, then closed.
"""

from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException

from jobsbot.ads.ai_draft import draft_ad_copy
from jobsbot.ads.campaigns import activate_campaign, cancel_campaign, get_all_campaigns, new_draft_campaign, send_broadcast_now
from jobsbot.ads.scheduler import broadcast_campaign_now
from jobsbot.ai.gemini_client import GeminiError
from jobsbot.config import settings
from jobsbot.storage.db import async_session
from jobsbot.storage.models import AdCampaign
from jobsbot.storage.repo import get_campaign
from jobsbot.web.auth import require_admin

router = APIRouter(prefix="/api/ads", tags=["ads"])


def _serialize(campaign: AdCampaign) -> dict:
    return {
        "id": campaign.id,
        "name": campaign.name,
        "message_text": campaign.message_text,
        "status": campaign.status,
        "send_interval_hours": campaign.send_interval_hours,
        "created_at": campaign.created_at.isoformat(),
    }


@router.get("")
async def get_ads(admin: str = Depends(require_admin)) -> dict:
    campaigns = await get_all_campaigns()
    return {"items": [_serialize(c) for c in campaigns]}


@router.post("")
async def create_ad(payload: dict, admin: str = Depends(require_admin)) -> dict:
    name = (payload.get("name") or "").strip()
    message_text = (payload.get("message_text") or "").strip()
    if not name or not message_text:
        raise HTTPException(status_code=400, detail="name и message_text обязательны")
    campaign = await new_draft_campaign(name, message_text, payload.get("send_interval_hours", 24))
    return _serialize(campaign)


@router.post("/draft")
async def draft_ad(payload: dict, admin: str = Depends(require_admin)) -> dict:
    tezisy = (payload.get("text") or "").strip()
    if not tezisy:
        raise HTTPException(status_code=400, detail="text обязателен")
    try:
        draft = await draft_ad_copy(tezisy)
    except GeminiError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini недоступен: {exc}") from exc
    return {"draft": draft}


@router.post("/{campaign_id}/activate")
async def activate_ad(campaign_id: int, admin: str = Depends(require_admin)) -> dict:
    campaign = await activate_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return _serialize(campaign)


@router.post("/{campaign_id}/cancel")
async def cancel_ad(campaign_id: int, admin: str = Depends(require_admin)) -> dict:
    campaign = await cancel_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")
    return _serialize(campaign)


@router.post("/{campaign_id}/broadcast")
async def broadcast_ad(campaign_id: int, admin: str = Depends(require_admin)) -> dict:
    async with async_session() as session:
        campaign = await get_campaign(session, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Кампания не найдена")

    bot = Bot(token=settings.bot_token)
    try:
        sent, total = await broadcast_campaign_now(bot, campaign)
    finally:
        await bot.session.close()
    return {"sent": sent, "total": total}


@router.post("/broadcast-now")
async def broadcast_now(payload: dict, admin: str = Depends(require_admin)) -> dict:
    """The one-off "Отправить всем сейчас" flow — creates its own
    already-"completed" campaign record, same as the Telegram button."""
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text обязателен")

    bot = Bot(token=settings.bot_token)
    try:
        campaign, sent, total = await send_broadcast_now(bot, text)
    finally:
        await bot.session.close()
    return {"campaign": _serialize(campaign), "sent": sent, "total": total}
