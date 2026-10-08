"""Add work_formats to subscribers.

Same defensive idempotency as the other column-adding migrations: on a
fresh DB, 0001's create_all() already created this column, so the
statement here is a no-op. On the already-existing Pi database, this is
what actually adds it. Empty JSON array = no work-format filter.

Revision ID: 5141599345af
Revises: 93835a5084cd
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "5141599345af"
down_revision: Union[str, None] = "93835a5084cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS work_formats VARCHAR NOT NULL DEFAULT '[]'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS work_formats")
