"""add users.mfa_required (admin-enforced MFA)

Revision ID: l8m9n0o1p2q3
Revises: k7l8m9n0o1p2
Create Date: 2026-06-05

Lets an admin force specific users to enroll TOTP. Super admins are always
required regardless of this flag (enforced in code), so this only needs to mark
flagged regular users.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l8m9n0o1p2q3"
down_revision: Union[str, Sequence[str], None] = "k7l8m9n0o1p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    return any(c["name"] == column for c in sa.inspect(conn).get_columns(table))


def upgrade() -> None:
    if not _column_exists("users", "mfa_required"):
        op.add_column("users", sa.Column("mfa_required", sa.Boolean(), server_default="0", nullable=False))


def downgrade() -> None:
    if _column_exists("users", "mfa_required"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("mfa_required")
