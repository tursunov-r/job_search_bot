"""Add saved_vacancies table ("⭐ Избранное").

On a fresh DB, 0001's create_all() already created this (it's in the
current model), so the statement here is a no-op. On the already-existing
Pi database, this is what actually adds it.

Revision ID: 4f1e9b6c3a85
Revises: 6b4f8d2a7e13
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op

revision: str = "4f1e9b6c3a85"
down_revision: Union[str, None] = "6b4f8d2a7e13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_vacancies (
            id SERIAL PRIMARY KEY,
            subscriber_id INTEGER NOT NULL REFERENCES subscribers(id),
            vacancy_id INTEGER NOT NULL REFERENCES vacancies(id),
            saved_at TIMESTAMP WITH TIME ZONE NOT NULL,
            CONSTRAINT saved_vacancies_subscriber_id_vacancy_id_key UNIQUE (subscriber_id, vacancy_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_saved_vacancies_subscriber_id ON saved_vacancies (subscriber_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_saved_vacancies_vacancy_id ON saved_vacancies (vacancy_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS saved_vacancies")
