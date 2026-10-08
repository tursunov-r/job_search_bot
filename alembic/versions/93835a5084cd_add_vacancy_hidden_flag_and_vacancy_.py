"""Add vacancy hidden flag and vacancy_reports table.

Same defensive idempotency as the other column-adding migrations: on a
fresh DB, 0001's create_all() already created both (they're in the
current model), so these statements are no-ops there. On the
already-existing Pi database, this is what actually adds them.

Revision ID: 93835a5084cd
Revises: 6770e761e3a6
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "93835a5084cd"
down_revision: Union[str, None] = "6770e761e3a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS hidden BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS vacancy_reports (
            id SERIAL PRIMARY KEY,
            vacancy_id INTEGER NOT NULL REFERENCES vacancies(id),
            subscriber_id INTEGER NOT NULL REFERENCES subscribers(id),
            comment VARCHAR NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL,
            resolved_by_telegram_user_id BIGINT,
            resolved_at TIMESTAMP WITH TIME ZONE
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vacancy_reports_vacancy_id ON vacancy_reports (vacancy_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vacancy_reports")
    op.execute("ALTER TABLE vacancies DROP COLUMN IF EXISTS hidden")
