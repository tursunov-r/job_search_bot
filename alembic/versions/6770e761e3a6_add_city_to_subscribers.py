"""Add city to subscribers.

Same defensive idempotency as 0002/94c27a5c0db0: on a fresh DB, 0001's
create_all() already created this column, so the statement here is a
no-op (IF NOT EXISTS). On an already-existing database (the Pi), this is
what actually adds it. NULL (the default for all existing rows) means "no
city filter" — matches the product decision exactly.

Revision ID: 6770e761e3a6
Revises: b28c5e41a6d3
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "6770e761e3a6"
down_revision: Union[str, None] = "b28c5e41a6d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS city VARCHAR")


def downgrade() -> None:
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS city")
