"""Add adapter_health table.

Tracks consecutive zero-result polling cycles per scraper adapter (hh,
habr, geekjob) so the bot can alert the super admin if one silently
breaks (e.g. the source site changes its HTML and the parser stops
finding anything). On a fresh DB, 0001's create_all() already created
this (it's in the current model), so the statement here is a no-op; on
the already-existing Pi database, this is what actually adds it.

Revision ID: 3d7b5f0a9c21
Revises: 8f1d2c6a4e97
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op

revision: str = "3d7b5f0a9c21"
down_revision: Union[str, None] = "8f1d2c6a4e97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS adapter_health (
            adapter VARCHAR PRIMARY KEY,
            consecutive_empty_polls INTEGER NOT NULL DEFAULT 0,
            alert_sent BOOLEAN NOT NULL DEFAULT false,
            last_polled_at TIMESTAMP WITH TIME ZONE
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS adapter_health")
