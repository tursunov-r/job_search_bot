"""Baseline schema — create any table that doesn't exist yet.

This is the first Alembic migration ever added to a project that already
had tables created by hand via SQLModel.metadata.create_all() (no
alembic_version tracking). Rather than hand-writing CREATE TABLE statements
that risk drifting from the real models, upgrade() just calls the exact
same create_all() the app always used, with checkfirst=True (the default) —
on a fresh database this creates every table in its current (full) shape;
on an already-existing database it's a safe no-op for tables that are
already there. Either way, running this never errors and never duplicates
work — which is the point: alembic upgrade head has to work unattended on
both a brand-new DB and the already-existing Raspberry Pi one.

Revision ID: 0001
Revises:
Create Date: 2026-10-08

"""
from typing import Sequence, Union

from sqlmodel import SQLModel

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Deliberately not implemented — this baseline represents "however the
    # database already looked before Alembic existed"; tearing it down
    # isn't a meaningful operation here.
    pass
