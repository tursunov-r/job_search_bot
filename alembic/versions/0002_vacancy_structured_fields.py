"""Add uuid + structured fields (experience/employment_type/schedule/work_format) to vacancies.

Same defensive idempotency as 0001: on a fresh DB, 0001's create_all()
already created these columns (they're in the current model), so every
statement here is a no-op (IF NOT EXISTS / SET NOT NULL on an
already-not-null column / IF NOT EXISTS index). On an existing database
that predates these fields (e.g. the already-deployed Raspberry Pi one),
this is what actually adds them — backfilling uuid for pre-existing rows
before making it NOT NULL, since Postgres won't let you add a NOT NULL
column to a non-empty table without a default.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS uuid VARCHAR")
    op.execute("ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS experience VARCHAR")
    op.execute("ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS employment_type VARCHAR")
    op.execute("ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS schedule VARCHAR")
    op.execute("ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS work_format VARCHAR")

    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("UPDATE vacancies SET uuid = gen_random_uuid()::text WHERE uuid IS NULL")
    op.execute("ALTER TABLE vacancies ALTER COLUMN uuid SET NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_vacancies_uuid ON vacancies (uuid)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vacancies_uuid")
    op.execute("ALTER TABLE vacancies DROP COLUMN IF EXISTS work_format")
    op.execute("ALTER TABLE vacancies DROP COLUMN IF EXISTS schedule")
    op.execute("ALTER TABLE vacancies DROP COLUMN IF EXISTS employment_type")
    op.execute("ALTER TABLE vacancies DROP COLUMN IF EXISTS experience")
    op.execute("ALTER TABLE vacancies DROP COLUMN IF EXISTS uuid")
