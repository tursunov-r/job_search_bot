"""Add index on vacancies.url.

Same defensive idempotency as the other new-index migrations: on a fresh
DB, 0001's create_all() already created this index (it's in the current
model), so the statement here is a no-op. On the already-existing Pi
database, this is what actually adds it — needed now that pipeline.ingest()
looks vacancies up by url on every single ingested row (see the url-based
dedup fallback added alongside this).

Revision ID: 497ddc68b14f
Revises: 1990e83d2c21
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "497ddc68b14f"
down_revision: Union[str, None] = "1990e83d2c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_vacancies_url ON vacancies (url)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vacancies_url")
