"""fix price_history condition columns: remove non-existent PC fields, add graded_price

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-05-27

PriceCharting has 6 real condition tiers:
  used_price, complete_price, new_price, graded_price, box_only_price, manual_only_price
The previous migration added item_box_price, item_manual_price, graded_cib_price, graded_new_price
which do not exist on PriceCharting. Drop those and add the correct graded_price.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "i5j6k7l8m9n0"
down_revision: Union[str, Sequence[str], None] = "h4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    wrong_cols = [c for c in (
        "item_box_price", "item_manual_price", "graded_cib_price", "graded_new_price"
    ) if _column_exists("price_history", c)]

    if wrong_cols or not _column_exists("price_history", "graded_price"):
        with op.batch_alter_table("price_history") as batch_op:
            for col in wrong_cols:
                batch_op.drop_column(col)
            if not _column_exists("price_history", "graded_price"):
                batch_op.add_column(sa.Column("graded_price", sa.Float()))


def downgrade() -> None:
    with op.batch_alter_table("price_history") as batch_op:
        if _column_exists("price_history", "graded_price"):
            batch_op.drop_column("graded_price")
        for col in ("item_box_price", "item_manual_price", "graded_cib_price", "graded_new_price"):
            if not _column_exists("price_history", col):
                batch_op.add_column(sa.Column(col, sa.Float()))
