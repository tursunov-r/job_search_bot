import json
from datetime import datetime, timedelta, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from jobsbot.storage.models import (
    AdCampaign,
    AdImpression,
    Source,
    StaffMember,
    Subscriber,
    Vacancy,
    VacancyDelivery,
)


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


async def add_telegram_channel(session: AsyncSession, identifier: str) -> Source:
    source = await get_or_create_source(session, "telegram_channel", identifier, identifier)
    if not source.enabled:
        source.enabled = True
        session.add(source)
        await session.commit()
        await session.refresh(source)
    return source


async def remove_telegram_channel(session: AsyncSession, identifier: str) -> bool:
    result = await session.exec(
        select(Source).where(Source.type == "telegram_channel", Source.identifier == identifier)
    )
    source = result.first()
    if source is None or not source.enabled:
        return False
    source.enabled = False
    session.add(source)
    await session.commit()
    return True


async def list_telegram_channels(session: AsyncSession) -> list[Source]:
    result = await session.exec(
        select(Source).where(Source.type == "telegram_channel").order_by(Source.id)
    )
    return list(result.all())


async def get_source_by_id(session: AsyncSession, source_id: int) -> Source | None:
    result = await session.exec(select(Source).where(Source.id == source_id))
    return result.first()


async def get_enabled_telegram_channel_identifiers(session: AsyncSession) -> list[str]:
    result = await session.exec(
        select(Source.identifier).where(Source.type == "telegram_channel", Source.enabled == True)  # noqa: E712
    )
    return list(result.all())


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
        # Deliberately NOT touching status here — this is called at the top
        # of almost every handler, so forcing status back to "active" on
        # every interaction would silently undo a self-service pause or
        # even an admin block the moment the person pressed any button.
        subscriber.last_interaction_at = datetime.now(timezone.utc)
        session.add(subscriber)
        await session.commit()
        await session.refresh(subscriber)
        return subscriber
    initial_cursor = await get_cursor_for_new_subscriber(session)
    subscriber = Subscriber(
        telegram_user_id=telegram_user_id,
        username=username,
        last_vacancy_sent_id=initial_cursor,
        status="paused",  # vacancy delivery only starts once they press "Смотреть вакансии"
    )
    session.add(subscriber)
    await session.commit()
    await session.refresh(subscriber)
    return subscriber


async def get_active_subscribers(session: AsyncSession) -> list[Subscriber]:
    result = await session.exec(select(Subscriber).where(Subscriber.status == "active"))
    return list(result.all())


def _details_ready_clause():
    """A vacancy is safe to push once its detail-enrichment pass finished
    (details_checked), or — as a safety net in case that pass crashed
    without ever marking it — once it's old enough that the pass must have
    already had its chance to run."""
    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    return (Vacancy.details_checked == True) | (Vacancy.first_seen_at < stale_cutoff)  # noqa: E712


async def get_pending_vacancies_for_subscriber(
    session: AsyncSession, subscriber: Subscriber, limit: int = 20
) -> list[Vacancy]:
    cursor_id = subscriber.last_vacancy_sent_id or 0
    result = await session.exec(
        select(Vacancy)
        .where(
            Vacancy.id > cursor_id,
            Vacancy.is_python_relevant == True,  # noqa: E712
            _details_ready_clause(),
        )
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
    """For re-scanning after a profile change: recent vacancies
    this subscriber hasn't been sent yet, regardless of where their push
    cursor currently sits (it may have already moved past some of these
    because they didn't match the *old* filter)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    delivered_subquery = select(VacancyDelivery.vacancy_id).where(
        VacancyDelivery.subscriber_id == subscriber_id
    )
    result = await session.exec(
        select(Vacancy)
        .where(
            Vacancy.first_seen_at >= cutoff,
            Vacancy.id.not_in(delivered_subquery),
            _details_ready_clause(),
        )
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


async def update_vacancy_details(
    session: AsyncSession,
    vacancy_id: int,
    *,
    description: str | None = None,
    experience: str | None = None,
    employment_type: str | None = None,
    schedule: str | None = None,
    work_format: str | None = None,
    salary_text: str | None = None,
) -> None:
    """Always marks the vacancy's detail-enrichment pass as done (even if
    every field here is None, e.g. the detail-page fetch failed) — otherwise
    push_new_vacancies would hold it back forever waiting for a pass that
    already ran and isn't coming again. See Vacancy.details_checked."""
    result = await session.exec(select(Vacancy).where(Vacancy.id == vacancy_id))
    vacancy = result.first()
    if vacancy is None:
        return
    if description:
        vacancy.description = description
    if experience:
        vacancy.experience = experience
    if employment_type:
        vacancy.employment_type = employment_type
    if schedule:
        vacancy.schedule = schedule
    if work_format:
        vacancy.work_format = work_format
    if salary_text:
        vacancy.salary_text = salary_text
    vacancy.details_checked = True
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


async def get_staff_member(session: AsyncSession, telegram_user_id: int) -> StaffMember | None:
    result = await session.exec(
        select(StaffMember).where(StaffMember.telegram_user_id == telegram_user_id)
    )
    return result.first()


async def list_staff_members(session: AsyncSession) -> list[StaffMember]:
    result = await session.exec(select(StaffMember).order_by(StaffMember.id))
    return list(result.all())


async def add_staff_member(
    session: AsyncSession,
    telegram_user_id: int,
    username: str | None,
    permissions: list[str],
    added_by_telegram_user_id: int,
) -> StaffMember:
    """Upsert: if this person was staff before and got removed, reactivate
    them with the new permission set instead of erroring on the unique
    constraint."""
    existing = await get_staff_member(session, telegram_user_id)
    if existing:
        existing.username = username
        existing.permissions = json.dumps(sorted(set(permissions)))
        existing.added_by_telegram_user_id = added_by_telegram_user_id
        existing.status = "active"
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing

    staff = StaffMember(
        telegram_user_id=telegram_user_id,
        username=username,
        permissions=json.dumps(sorted(set(permissions))),
        added_by_telegram_user_id=added_by_telegram_user_id,
    )
    session.add(staff)
    await session.commit()
    await session.refresh(staff)
    return staff


async def remove_staff_member(session: AsyncSession, staff_id: int) -> StaffMember | None:
    result = await session.exec(select(StaffMember).where(StaffMember.id == staff_id))
    staff = result.first()
    if staff is None:
        return None
    staff.status = "removed"
    session.add(staff)
    await session.commit()
    await session.refresh(staff)
    return staff


async def _set_subscriber_status_by_telegram_id(
    session: AsyncSession, telegram_user_id: int, status: str, *, skip_if_blocked: bool = False
) -> Subscriber | None:
    result = await session.exec(
        select(Subscriber).where(Subscriber.telegram_user_id == telegram_user_id)
    )
    subscriber = result.first()
    if subscriber is None:
        return None
    if skip_if_blocked and subscriber.status == "blocked":
        return subscriber
    subscriber.status = status
    session.add(subscriber)
    await session.commit()
    await session.refresh(subscriber)
    return subscriber


async def block_subscriber_by_telegram_id(session: AsyncSession, telegram_user_id: int) -> Subscriber | None:
    return await _set_subscriber_status_by_telegram_id(session, telegram_user_id, "blocked")


async def unblock_subscriber_by_telegram_id(session: AsyncSession, telegram_user_id: int) -> Subscriber | None:
    return await _set_subscriber_status_by_telegram_id(session, telegram_user_id, "active")


async def pause_subscriber_by_telegram_id(session: AsyncSession, telegram_user_id: int) -> Subscriber | None:
    """Self-service stop — unlike admin block/unblock, this never overrides
    an existing "blocked" status (a paused self-service toggle shouldn't be
    able to undo an admin's block)."""
    return await _set_subscriber_status_by_telegram_id(
        session, telegram_user_id, "paused", skip_if_blocked=True
    )


async def resume_subscriber_by_telegram_id(session: AsyncSession, telegram_user_id: int) -> Subscriber | None:
    return await _set_subscriber_status_by_telegram_id(
        session, telegram_user_id, "active", skip_if_blocked=True
    )
