"""multi-user: users, collections, memberships, invitations + collection_id

Revision ID: k7l8m9n0o1p2
Revises: j6k7l8m9n0o1
Create Date: 2026-06-05

Turns the single-tenant app multi-user. Adds the auth/sharing tables and a
`collection_id` foreign key on the collection-scoped data (games, lots,
value_history). All pre-existing rows are backfilled into a default collection
(#1). That collection starts ownerless; the first-run bootstrap (creating the
super admin) claims it and adds an owner membership, so nothing is lost and the
current collection simply becomes shareable.

Purely additive: no existing column is dropped or renamed, so the app keeps
working before the route-level auth/scoping switch is flipped.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k7l8m9n0o1p2"
down_revision: Union[str, Sequence[str], None] = "j6k7l8m9n0o1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_COLLECTION_ID = 1
DEFAULT_COLLECTION_NAME = "My Collection"
_SCOPED_TABLES = ("games", "lots", "value_history")


def _has_table(name: str) -> bool:
    conn = op.get_bind()
    return sa.inspect(conn).has_table(name)


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("display_name", sa.String()),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("is_super_admin", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("mfa_enabled", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("mfa_secret", sa.String()),
            sa.Column("mfa_recovery_codes", sa.Text()),
            sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
            sa.Column("last_login_at", sa.String()),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )

    if not _has_table("collections"):
        op.create_table(
            "collections",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("is_personal", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.String(), server_default=sa.func.current_timestamp()),
        )

    if not _has_table("collection_members"):
        op.create_table(
            "collection_members",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("collection_id", sa.Integer(), sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(), server_default="viewer", nullable=False),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("collection_id", "user_id", name="uq_collection_member"),
        )
        op.create_index("idx_collection_members_user", "collection_members", ["user_id"])

    if not _has_table("invitations"):
        op.create_table(
            "invitations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("collection_id", sa.Integer(), sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("role", sa.String(), server_default="editor", nullable=False),
            sa.Column("token", sa.String(), nullable=False),
            sa.Column("invited_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("accepted_at", sa.String()),
            sa.Column("created_at", sa.String(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("token", name="uq_invitations_token"),
        )
        op.create_index("idx_invitations_email", "invitations", ["email"])

    # Add the scoping FK to each data table.
    for table in _SCOPED_TABLES:
        if _has_table(table) and not _column_exists(table, "collection_id"):
            op.add_column(table, sa.Column("collection_id", sa.Integer()))
            op.create_index(f"idx_{table}_collection_id", table, ["collection_id"])

    # Seed the default collection (ownerless until bootstrap) and backfill rows.
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM collections WHERE id = :cid"),
        {"cid": DEFAULT_COLLECTION_ID},
    ).fetchone()
    if not existing:
        conn.execute(
            sa.text("INSERT INTO collections (id, name, is_personal) VALUES (:cid, :name, 0)"),
            {"cid": DEFAULT_COLLECTION_ID, "name": DEFAULT_COLLECTION_NAME},
        )
    for table in _SCOPED_TABLES:
        if _has_table(table):
            conn.execute(
                sa.text(f"UPDATE {table} SET collection_id = :cid WHERE collection_id IS NULL"),
                {"cid": DEFAULT_COLLECTION_ID},
            )


def downgrade() -> None:
    for table in _SCOPED_TABLES:
        if _has_table(table) and _column_exists(table, "collection_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_column("collection_id")
    for tbl in ("invitations", "collection_members", "collections", "users"):
        if _has_table(tbl):
            op.drop_table(tbl)
