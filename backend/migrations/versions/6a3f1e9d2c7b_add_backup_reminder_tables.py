"""add backup reminder policy table

Revision ID: 6a3f1e9d2c7b
Revises: 5e2d9b7c4a1f
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "6a3f1e9d2c7b"
down_revision = "5e2d9b7c4a1f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create backup policy reminder table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "backup_policies" not in table_names:
        op.create_table(
            "backup_policies",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("owner_user_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="unconfirmed"),
            sa.Column("destination_type", sa.String(), nullable=True),
            sa.Column("destination_label", sa.String(), nullable=True),
            sa.Column("warning_shown_at", sa.DateTime(), nullable=True),
            sa.Column("last_prompted_at", sa.DateTime(), nullable=True),
            sa.Column("next_prompt_at", sa.DateTime(), nullable=True),
            sa.Column("last_confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", name="uq_backup_policies_org"),
        )
        op.create_index("ix_backup_policies_organization_id", "backup_policies", ["organization_id"])
        op.create_index("ix_backup_policies_owner_user_id", "backup_policies", ["owner_user_id"])
        op.create_index("ix_backup_policies_status", "backup_policies", ["status"])
        op.create_index("ix_backup_policies_destination_type", "backup_policies", ["destination_type"])
    else:
        indexes = {index["name"] for index in inspector.get_indexes("backup_policies")}
        if "ix_backup_policies_organization_id" not in indexes:
            op.create_index("ix_backup_policies_organization_id", "backup_policies", ["organization_id"])
        if "ix_backup_policies_owner_user_id" not in indexes:
            op.create_index("ix_backup_policies_owner_user_id", "backup_policies", ["owner_user_id"])
        if "ix_backup_policies_status" not in indexes:
            op.create_index("ix_backup_policies_status", "backup_policies", ["status"])
        if "ix_backup_policies_destination_type" not in indexes:
            op.create_index("ix_backup_policies_destination_type", "backup_policies", ["destination_type"])

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    columns = (
        {column["name"] for column in refreshed.get_columns("backup_policies")}
        if "backup_policies" in refreshed_tables
        else set()
    )
    if "status" in columns:
        op.alter_column("backup_policies", "status", server_default=None)


def downgrade() -> None:
    """Drop backup policy reminder table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "backup_policies" not in table_names:
        return
    indexes = {index["name"] for index in inspector.get_indexes("backup_policies")}
    if "ix_backup_policies_destination_type" in indexes:
        op.drop_index("ix_backup_policies_destination_type", table_name="backup_policies")
    if "ix_backup_policies_status" in indexes:
        op.drop_index("ix_backup_policies_status", table_name="backup_policies")
    if "ix_backup_policies_owner_user_id" in indexes:
        op.drop_index("ix_backup_policies_owner_user_id", table_name="backup_policies")
    if "ix_backup_policies_organization_id" in indexes:
        op.drop_index("ix_backup_policies_organization_id", table_name="backup_policies")
    op.drop_table("backup_policies")
