"""Add subscribers.quiet_hours_start/quiet_hours_end ("🌙 Тихие часы").

Same defensive idempotency as the other added-column migrations: on a
fresh DB, 0001's create_all() already created both columns (they're in
the current model), so the statements here are no-ops. On the
already-existing Pi database, this is what actually adds them.

Revision ID: 2e8a7f4c9d31
Revises: 4f1e9b6c3a85
Create Date: 2026-10-12

"""
from typing import Sequence, Union

from alembic import op

revision: str = "2e8a7f4c9d31"
down_revision: Union[str, None] = "4f1e9b6c3a85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS quiet_hours_start INTEGER")
    op.execute("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS quiet_hours_end INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS quiet_hours_end")
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS quiet_hours_start")
