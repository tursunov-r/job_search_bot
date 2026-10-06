import json
from datetime import datetime, timedelta, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from jobsbot.storage.models import AdCampaign, AdImpression, Source, Subscriber, Vacancy, VacancyDelivery


async def get_or_create_source(
    session: AsyncSession, type_: str, identifier: str, display_name: str | None = None
) -> Source:
    result = await session.exec(
        select(Source).where(Source.type == type_, Source.identifier == identifier)
    )
    source = result.first()
    if source:
        return source
    source = Source(type=type_, identifier=identifier, display_name=display_name)
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


async def update_source_last_message_id(session: AsyncSession, source_id: int, message_id: int) -> None:
    result = await session.exec(select(Source).where(Source.id == source_id))
    source = result.first()
    if source is None:
        return
    source.last_message_id = message_id
    source.last_polled_at = datetime.now(timezone.utc)
    session.add(source)
    await session.commit()


async def get_vacancy_by_fingerprint(session: AsyncSession, fingerprint: str) -> Vacancy | None:
    result = await session.exec(select(Vacancy).where(Vacancy.fingerprint == fingerprint))
    return result.first()


async def insert_vacancy(session: AsyncSession, vacancy: Vacancy) -> Vacancy:
    session.add(vacancy)
    await session.commit()
    await session.refresh(vacancy)
    return vacancy


async def get_cursor_for_new_subscriber(session: AsyncSession) -> int | None:
    """A new subscriber should get the last week's vacancies first (oldest to
    newest, via the normal push cursor), not the entire history. Returns the
    id of the newest vacancy older than 7 days, so the push loop's `id >
    cursor` naturally starts from there; None if there isn't one (everything
    is within the last week already, so start from the very beginning)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = await session.exec(
        select(Vacancy.id).where(Vacancy.first_seen_at < cutoff).order_by(Vacancy.id.desc()).limit(1)
    )
    return result.first()


async def get_or_create_subscriber(
    session: AsyncSession, telegram_user_id: int, username: str | None
) -> Subscriber:
    result = await session.exec(
        select(Subscriber).where(Subscriber.telegram_user_id == telegram_user_id)
    )
    subscriber = result.first()
    if subscriber:
        subscriber.status = "active"
        subscriber.last_interaction_at = datetime.now(timezone.utc)
        session.add(subscriber)
        await session.commit()
        await session.refresh(subscriber)
        return subscriber
    initial_cursor = await get_cursor_for_new_subscriber(session)
    subscriber = Subscriber(
        telegram_user_id=telegram_user_id, username=username, last_vacancy_sent_id=initial_cursor
    )
    session.add(subscriber)
    await session.commit()
    await session.refresh(subscriber)
    return subscriber


async def get_active_subscribers(session: AsyncSession) -> list[Subscriber]:
    result = await session.exec(select(Subscriber).where(Subscriber.status == "active"))
    return list(result.all())


async def get_pending_vacancies_for_subscriber(
    session: AsyncSession, subscriber: Subscriber, limit: int = 20
) -> list[Vacancy]:
    cursor_id = subscriber.last_vacancy_sent_id or 0
    result = await session.exec(
        select(Vacancy)
        .where(Vacancy.id > cursor_id, Vacancy.is_python_relevant == True)  # noqa: E712
        .order_by(Vacancy.id)
        .limit(limit)
    )
    return list(result.all())


async def mark_subscriber_cursor(session: AsyncSession, subscriber: Subscriber, vacancy_id: int) -> None:
    subscriber.last_vacancy_sent_id = vacancy_id
    session.add(subscriber)
    await session.commit()


async def record_delivery(session: AsyncSession, subscriber_id: int, vacancy_id: int) -> None:
    session.add(VacancyDelivery(subscriber_id=subscriber_id, vacancy_id=vacancy_id))
    await session.commit()


async def get_delivered_vacancy_ids(
    session: AsyncSession, subscriber_id: int, vacancy_ids: list[int]
) -> set[int]:
    if not vacancy_ids:
        return set()
    result = await session.exec(
        select(VacancyDelivery.vacancy_id).where(
            VacancyDelivery.subscriber_id == subscriber_id,
            VacancyDelivery.vacancy_id.in_(vacancy_ids),
        )
    )
    return set(result.all())


async def get_undelivered_recent_vacancies(
    session: AsyncSession, subscriber_id: int, days: int = 7, limit: int = 50
) -> list[Vacancy]:
    """For re-scanning after a /stack or /language change: recent vacancies
    this subscriber hasn't been sent yet, regardless of where their push
    cursor currently sits (it may have already moved past some of these
    because they didn't match the *old* filter)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    delivered_subquery = select(VacancyDelivery.vacancy_id).where(
        VacancyDelivery.subscriber_id == subscriber_id
    )
    result = await session.exec(
        select(Vacancy)
        .where(Vacancy.first_seen_at >= cutoff, Vacancy.id.not_in(delivered_subquery))
        .order_by(Vacancy.id)
        .limit(limit)
    )
    return list(result.all())


async def update_subscriber_skills(session: AsyncSession, subscriber: Subscriber, skills: list[str]) -> Subscriber:
    subscriber.skills = json.dumps(sorted(set(skills)))
    session.add(subscriber)
    await session.commit()
    await session.refresh(subscriber)
    return subscriber


async def update_subscriber_languages(
    session: AsyncSession, subscriber: Subscriber, languages: list[str]
) -> Subscriber:
    subscriber.languages = json.dumps(sorted(set(languages)))
    session.add(subscriber)
    await session.commit()
    await session.refresh(subscriber)
    return subscriber


async def update_vacancy_description(session: AsyncSession, vacancy_id: int, description: str) -> None:
    result = await session.exec(select(Vacancy).where(Vacancy.id == vacancy_id))
    vacancy = result.first()
    if vacancy is None:
        return
    vacancy.description = description
    session.add(vacancy)
    await session.commit()


async def record_ad_impression(
    session: AsyncSession, campaign_id: int, subscriber_id: int, delivery_status: str = "sent"
) -> None:
    session.add(
        AdImpression(campaign_id=campaign_id, subscriber_id=subscriber_id, delivery_status=delivery_status)
    )
    await session.commit()


async def get_active_campaigns(session: AsyncSession) -> list[AdCampaign]:
    now = datetime.now(timezone.utc)
    result = await session.exec(
        select(AdCampaign).where(
            AdCampaign.status == "active",
            (AdCampaign.starts_at == None) | (AdCampaign.starts_at <= now),  # noqa: E711
            (AdCampaign.ends_at == None) | (AdCampaign.ends_at >= now),  # noqa: E711
        )
    )
    return list(result.all())


async def create_campaign(
    session: AsyncSession,
    name: str,
    message_text: str,
    media_file_id: str | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    send_interval_hours: int | None = None,
    status: str = "draft",
) -> AdCampaign:
    campaign = AdCampaign(
        name=name,
        message_text=message_text,
        media_file_id=media_file_id,
        starts_at=starts_at,
        ends_at=ends_at,
        send_interval_hours=send_interval_hours,
        status=status,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def get_campaign(session: AsyncSession, campaign_id: int) -> AdCampaign | None:
    result = await session.exec(select(AdCampaign).where(AdCampaign.id == campaign_id))
    return result.first()


async def list_campaigns(session: AsyncSession) -> list[AdCampaign]:
    result = await session.exec(select(AdCampaign).order_by(AdCampaign.id))
    return list(result.all())


async def set_campaign_status(session: AsyncSession, campaign: AdCampaign, status: str) -> AdCampaign:
    campaign.status = status
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return campaign


async def get_last_impression_sent_at(session: AsyncSession, campaign_id: int) -> datetime | None:
    result = await session.exec(
        select(AdImpression.sent_at)
        .where(AdImpression.campaign_id == campaign_id)
        .order_by(AdImpression.sent_at.desc())
        .limit(1)
    )
    return result.first()
