from datetime import datetime, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from jobsbot.storage.models import Source, Subscriber, Vacancy


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


async def get_vacancy_by_fingerprint(session: AsyncSession, fingerprint: str) -> Vacancy | None:
    result = await session.exec(select(Vacancy).where(Vacancy.fingerprint == fingerprint))
    return result.first()


async def insert_vacancy(session: AsyncSession, vacancy: Vacancy) -> Vacancy:
    session.add(vacancy)
    await session.commit()
    await session.refresh(vacancy)
    return vacancy


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
    subscriber = Subscriber(telegram_user_id=telegram_user_id, username=username)
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
