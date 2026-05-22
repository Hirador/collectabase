"""drop region and barcode from game_copies (global fields)

Revision ID: g3h4i5j6k7l8
Revises: f2a3b4c5d6e7
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g3h4i5j6k7l8"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    cols_to_drop = [c for c in ("region", "barcode") if _column_exists("game_copies", c)]
    if not cols_to_drop:
        return
    with op.batch_alter_table("game_copies") as batch_op:
        for col in cols_to_drop:
            batch_op.drop_column(col)


def downgrade() -> None:
    with op.batch_alter_table("game_copies") as batch_op:
        if not _column_exists("game_copies", "region"):
            batch_op.add_column(sa.Column("region", sa.String()))
        if not _column_exists("game_copies", "barcode"):
            batch_op.add_column(sa.Column("barcode", sa.String()))
