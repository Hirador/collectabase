"""add game copies table

Revision ID: f2a3b4c5d6e7
Revises: e6f7a8b9c0d1
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("game_copies"):
        return

    op.create_table(
        "game_copies",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("condition", sa.String()),
        sa.Column("completeness", sa.String()),
        sa.Column("region", sa.String()),
        sa.Column("barcode", sa.String()),
        sa.Column("purchase_price", sa.Float()),
        sa.Column("purchase_date", sa.String()),
        sa.Column("location", sa.String()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.String(), server_default=sa.func.current_timestamp()),
    )
    op.create_index("idx_game_copies_game_id", "game_copies", ["game_id"])

    # Migrate existing records: one copy per existing game, preserving per-copy fields
    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO game_copies
            (game_id, condition, completeness, region, barcode, purchase_price, purchase_date, location, notes)
        SELECT
            id, condition, completeness, region, barcode, purchase_price, purchase_date, location, notes
        FROM games
    """))


def downgrade() -> None:
    if _table_exists("game_copies"):
        op.drop_index("idx_game_copies_game_id", table_name="game_copies")
        op.drop_table("game_copies")
