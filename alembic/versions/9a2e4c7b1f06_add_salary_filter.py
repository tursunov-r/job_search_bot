"""Add vacancies.salary_min_rub and subscribers.min_salary (salary filter).

On a fresh DB, 0001's create_all() already created both columns (they're
in the current model) and there are no rows yet, so the backfill loop
below finds nothing and is a no-op. On the already-existing Pi database,
this adds the columns AND backfills salary_min_rub for every existing
vacancy by re-parsing its already-stored salary_text with the same
parser the app uses at runtime — no re-scraping needed, the source text
was never lost.

Revision ID: 9a2e4c7b1f06
Revises: 3d7b5f0a9c21
Create Date: 2026-10-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a2e4c7b1f06"
down_revision: Union[str, None] = "3d7b5f0a9c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS salary_min_rub INTEGER")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vacancies_salary_min_rub ON vacancies (salary_min_rub)")
    op.execute("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS min_salary INTEGER")

    from jobsbot.processing.salary import parse_salary_min_rub

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, salary_text FROM vacancies WHERE salary_text IS NOT NULL AND salary_min_rub IS NULL")
    ).fetchall()
    for row in rows:
        parsed = parse_salary_min_rub(row.salary_text)
        if parsed is not None:
            bind.execute(sa.text("UPDATE vacancies SET salary_min_rub = :v WHERE id = :id"), {"v": parsed, "id": row.id})


def downgrade() -> None:
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS min_salary")
    op.execute("ALTER TABLE vacancies DROP COLUMN IF EXISTS salary_min_rub")
