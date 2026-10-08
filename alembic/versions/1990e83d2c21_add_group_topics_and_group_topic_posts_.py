"""Add group_topics and group_topic_posts tables.

Same defensive idempotency as the other new-table migrations: on a fresh
DB, 0001's create_all() already created both (they're in the current
model), so these statements are no-ops there. On the already-existing Pi
database, this is what actually adds them.

Revision ID: 1990e83d2c21
Revises: 5141599345af
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "1990e83d2c21"
down_revision: Union[str, None] = "5141599345af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS group_topics (
            language_key VARCHAR PRIMARY KEY,
            thread_id INTEGER NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS group_topic_posts (
            id SERIAL PRIMARY KEY,
            vacancy_id INTEGER NOT NULL REFERENCES vacancies(id),
            thread_id INTEGER NOT NULL,
            posted_at TIMESTAMP WITH TIME ZONE NOT NULL,
            CONSTRAINT uq_group_topic_posts_vacancy_thread UNIQUE (vacancy_id, thread_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_group_topic_posts_vacancy_id ON group_topic_posts (vacancy_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS group_topic_posts")
    op.execute("DROP TABLE IF EXISTS group_topics")
