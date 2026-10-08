"""Widen Telegram id columns to bigint.

These were plain int columns, which SQLModel/SQLAlchemy map to a Postgres
INTEGER (32-bit, max ~2.1 billion) by default. Modern Telegram user ids
routinely exceed that (e.g. 8419696219), and channel/supergroup chat ids
are always large negative numbers already past int32 — so most real users
could never even get a Subscriber row inserted; the INSERT/SELECT would
raise asyncpg.exceptions.DataError and the bot would silently drop their
message. ALTER COLUMN ... TYPE BIGINT on an already-bigint column (fresh
DB via 0001's create_all, which uses the current, already-fixed models) is
a harmless no-op, so this is safe to run unconditionally either way.

Revision ID: b28c5e41a6d3
Revises: 94c27a5c0db0
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b28c5e41a6d3"
down_revision: Union[str, None] = "94c27a5c0db0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE subscribers ALTER COLUMN telegram_user_id TYPE BIGINT")
    op.execute("ALTER TABLE staff_members ALTER COLUMN telegram_user_id TYPE BIGINT")
    op.execute("ALTER TABLE staff_members ALTER COLUMN added_by_telegram_user_id TYPE BIGINT")
    op.execute("ALTER TABLE vacancies ALTER COLUMN source_chat_id TYPE BIGINT")


def downgrade() -> None:
    op.execute("ALTER TABLE subscribers ALTER COLUMN telegram_user_id TYPE INTEGER")
    op.execute("ALTER TABLE staff_members ALTER COLUMN telegram_user_id TYPE INTEGER")
    op.execute("ALTER TABLE staff_members ALTER COLUMN added_by_telegram_user_id TYPE INTEGER")
    op.execute("ALTER TABLE vacancies ALTER COLUMN source_chat_id TYPE INTEGER")
