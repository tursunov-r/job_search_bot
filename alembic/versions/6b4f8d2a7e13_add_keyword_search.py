"""Add subscribers.keywords (free-text keyword search).

Same defensive idempotency as the other added-column migrations: on a
fresh DB, 0001's create_all() already created this column (it's in the
current model), so the statement here is a no-op. On the already-existing
Pi database, this is what actually adds it.

Revision ID: 6b4f8d2a7e13
Revises: 9a2e4c7b1f06
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op

revision: str = "6b4f8d2a7e13"
down_revision: Union[str, None] = "9a2e4c7b1f06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS keywords VARCHAR NOT NULL DEFAULT '[]'")


def downgrade() -> None:
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS keywords")
