"""Add required_channels table and subscribers.subscription_gate_passed.

Same defensive idempotency as the other migrations: on a fresh DB, 0001's
create_all() already created both (they're in the current model), so the
statements here are no-ops. On the already-existing Pi database, this both
adds them and backfills subscription_gate_passed to TRUE for every existing
subscriber — the gate is for *new* users going forward, not a retroactive
lockout of people who already use the bot.

Revision ID: 8f1d2c6a4e97
Revises: 7c3a9e4f1b02
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "8f1d2c6a4e97"
down_revision: Union[str, None] = "7c3a9e4f1b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS required_channels (
            id SERIAL PRIMARY KEY,
            username VARCHAR NOT NULL UNIQUE,
            title VARCHAR,
            added_at TIMESTAMP WITH TIME ZONE NOT NULL
        )
        """
    )
    op.execute(
        "ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS subscription_gate_passed BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute("UPDATE subscribers SET subscription_gate_passed = true")


def downgrade() -> None:
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS subscription_gate_passed")
    op.execute("DROP TABLE IF EXISTS required_channels")
