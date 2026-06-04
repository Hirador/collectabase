"""add catalog fields to games (serial, revision, languages, edition, source)

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-06-04

Supports the Redump/No-Intro/GameDB catalog lookup flow: when a user picks a
catalog match, these fields capture the precise disc/cart identity, while
`edition` is the physical-packaging distinction the serial alone can't express.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "j6k7l8m9n0o1"
down_revision: Union[str, Sequence[str], None] = "i5j6k7l8m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_COLUMNS = ("serial", "disc_revision", "languages", "edition", "catalog_source")


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    for col in _NEW_COLUMNS:
        if not _column_exists("games", col):
            op.add_column("games", sa.Column(col, sa.String()))


def downgrade() -> None:
    drops = [c for c in _NEW_COLUMNS if _column_exists("games", c)]
    if drops:
        with op.batch_alter_table("games") as batch_op:
            for col in drops:
                batch_op.drop_column(col)
