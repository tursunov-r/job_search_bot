"""Replace subscribers.city (single free-text city) with subscribers.cities
(a JSON array of city names), so a subscriber can filter on more than one
city at once.

On a fresh DB, 0001's create_all() already created `cities` matching the
current model, so the ADD COLUMN here is a no-op. On the already-existing
Pi database, this both adds the new column and migrates any existing
single-city value into it before dropping the old column.

Revision ID: 7c3a9e4f1b02
Revises: 2b7f6d91a8c4
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op

revision: str = "7c3a9e4f1b02"
down_revision: Union[str, None] = "2b7f6d91a8c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS cities VARCHAR NOT NULL DEFAULT '[]'")
    op.execute(
        """
        UPDATE subscribers
        SET cities = ('["' || replace(city, '"', '\\"') || '"]')
        WHERE city IS NOT NULL AND city <> ''
        """
    )
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS city")


def downgrade() -> None:
    op.execute("ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS city VARCHAR")
    op.execute("ALTER TABLE subscribers DROP COLUMN IF EXISTS cities")
