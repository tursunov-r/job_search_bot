import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from jobsbot.config import settings

_engine: AsyncEngine = create_async_engine(settings.get_db_url, echo=False)
async_session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


def _run_alembic_upgrade() -> None:
    # alembic.command.upgrade() is sync, and alembic/env.py's async template
    # does its own asyncio.run() internally — can't call that from inside
    # the app's already-running event loop, hence running it in a thread
    # with a fresh loop of its own via asyncio.to_thread in init_db().
    config = Config("alembic.ini")
    command.upgrade(config, "head")


async def init_db() -> None:
    # Replaces the old SQLModel.metadata.create_all() — that only ever
    # created missing tables, never added columns to an existing one.
    # Every startup runs whatever migrations haven't been applied yet
    # (alembic/versions/); already-applied ones are a no-op.
    await asyncio.to_thread(_run_alembic_upgrade)
