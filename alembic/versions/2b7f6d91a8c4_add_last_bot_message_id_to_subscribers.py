"""Add last_bot_message_id to subscribers.

Same defensive idempotency as the other added-column migrations: on a
fresh DB, 0001's create_all() already created this column (it's in the
current model), so the statement here is a no-op. On the already-existing
Pi database, this is what actually adds it — needed for the chat-clutter
cleanup, which tracks the subscriber's last "system" message so it can be
deleted right before sending the next one.

Revision ID: 2b7f6d91a8c4
Revises: 497ddc68b14f
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "2b7f6d91a8c4"
down_revision: Union[str, None] = "497ddc68b14f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS last_bot_message_id INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS last_bot_message_id")
