from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from jobsbot.ads.campaigns import activate_campaign, cancel_campaign, get_all_campaigns, new_draft_campaign
from jobsbot.ads.scheduler import broadcast_campaign_now
from jobsbot.config import settings
from jobsbot.storage.repo import get_campaign
from jobsbot.storage.db import async_session

router = Router()


def _is_admin(message: Message) -> bool:
    return message.from_user is not None and message.from_user.id in settings.admin_ids


@router.message(Command("newad"))
async def handle_newad(message: Message) -> None:
    if not _is_admin(message):
        return
    payload = message.text.split(maxsplit=1)[1] if message.text and " " in message.text else ""
    if "|" not in payload:
        await message.answer("Формат: /newad Название | Текст объявления")
        return
    name, text = (part.strip() for part in payload.split("|", maxsplit=1))
    campaign = await new_draft_campaign(name, text)
    await message.answer(f"Кампания создана (draft), id={campaign.id}. Активировать: /activatead {campaign.id}")


@router.message(Command("ads"))
async def handle_list_ads(message: Message) -> None:
    if not _is_admin(message):
        return
    campaigns = await get_all_campaigns()
    if not campaigns:
        await message.answer("Кампаний пока нет.")
        return
    lines = [f"#{c.id} [{c.status}] {c.name} (интервал: {c.send_interval_hours}ч)" for c in campaigns]
    await message.answer("\n".join(lines))


@router.message(Command("activatead"))
async def handle_activate_ad(message: Message) -> None:
    if not _is_admin(message):
        return
    campaign_id = _parse_id_arg(message.text)
    if campaign_id is None:
        await message.answer("Формат: /activatead <id>")
        return
    campaign = await activate_campaign(campaign_id)
    await message.answer(f"Кампания #{campaign_id} активирована." if campaign else "Кампания не найдена.")


@router.message(Command("canceladc"))
async def handle_cancel_ad(message: Message) -> None:
    if not _is_admin(message):
        return
    campaign_id = _parse_id_arg(message.text)
    if campaign_id is None:
        await message.answer("Формат: /canceladc <id>")
        return
    campaign = await cancel_campaign(campaign_id)
    await message.answer(f"Кампания #{campaign_id} отменена." if campaign else "Кампания не найдена.")


@router.message(Command("broadcastad"))
async def handle_broadcast_now(message: Message) -> None:
    if not _is_admin(message):
        return
    campaign_id = _parse_id_arg(message.text)
    if campaign_id is None:
        await message.answer("Формат: /broadcastad <id>")
        return
    async with async_session() as session:
        campaign = await get_campaign(session, campaign_id)
    if campaign is None:
        await message.answer("Кампания не найдена.")
        return
    await broadcast_campaign_now(message.bot, campaign)
    await message.answer(f"Кампания #{campaign_id} разослана вручную.")


def _parse_id_arg(text: str | None) -> int | None:
    if not text or " " not in text:
        return None
    arg = text.split(maxsplit=1)[1].strip()
    return int(arg) if arg.isdigit() else None
