"""add copy current_value and extended price columns

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-05-27
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "h4i5j6k7l8m9"
down_revision: Union[str, Sequence[str], None] = "g3h4i5j6k7l8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    # game_copies: per-copy baseline value for P/L calculation
    if not _column_exists("game_copies", "current_value"):
        op.add_column("game_copies", sa.Column("current_value", sa.Float()))
        # seed from games.current_value so existing items keep their baseline
        conn = op.get_bind()
        conn.execute(sa.text("""
            UPDATE game_copies
            SET current_value = (
                SELECT current_value FROM games WHERE games.id = game_copies.game_id
            )
        """))

    # price_history: extended PriceCharting condition columns
    for col in ("item_box_price", "item_manual_price", "box_only_price",
                "manual_only_price", "graded_cib_price", "graded_new_price"):
        if not _column_exists("price_history", col):
            op.add_column("price_history", sa.Column(col, sa.Float()))


def downgrade() -> None:
    price_history_drops = [c for c in (
        "item_box_price", "item_manual_price", "box_only_price",
        "manual_only_price", "graded_cib_price", "graded_new_price"
    ) if _column_exists("price_history", c)]
    if price_history_drops:
        with op.batch_alter_table("price_history") as batch_op:
            for col in price_history_drops:
                batch_op.drop_column(col)

    if _column_exists("game_copies", "current_value"):
        with op.batch_alter_table("game_copies") as batch_op:
            batch_op.drop_column("current_value")
