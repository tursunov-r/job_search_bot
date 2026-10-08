"""Add details_checked to vacancies.

Same defensive idempotency as 0002: on a fresh DB, 0001's create_all()
already created this column (it's in the current model), so the statement
here is a no-op (IF NOT EXISTS). On an already-existing database (the Pi),
this is what actually adds it. Existing rows default to true — they're
already-delivered old data, not pending enrichment; only newly inserted
HH/Habr vacancies get false until their detail-page fetch completes.

Revision ID: 94c27a5c0db0
Revises: 0002
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "94c27a5c0db0"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS details_checked BOOLEAN NOT NULL DEFAULT TRUE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE vacancies DROP COLUMN IF EXISTS details_checked")
