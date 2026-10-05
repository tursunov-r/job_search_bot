from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from jobsbot.config import settings

_engine: AsyncEngine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    db_path = settings.database_url.split("///")[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
