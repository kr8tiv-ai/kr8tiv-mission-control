"""add change request workflow table

Revision ID: 7d4b2a9e1c6f
Revises: 6a3f1e9d2c7b
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "7d4b2a9e1c6f"
down_revision = "6a3f1e9d2c7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create change request lifecycle table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "change_requests" not in table_names:
        op.create_table(
            "change_requests",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("requested_for_agent_id", sa.Uuid(), nullable=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False, server_default="general"),
            sa.Column("priority", sa.String(), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(), nullable=False, server_default="submitted"),
            sa.Column("resolution_note", sa.String(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("applied_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["requested_for_agent_id"], ["agents.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_change_requests_organization_id", "change_requests", ["organization_id"])
        op.create_index("ix_change_requests_requested_by_user_id", "change_requests", ["requested_by_user_id"])
        op.create_index("ix_change_requests_requested_for_agent_id", "change_requests", ["requested_for_agent_id"])
        op.create_index("ix_change_requests_category", "change_requests", ["category"])
        op.create_index("ix_change_requests_priority", "change_requests", ["priority"])
        op.create_index("ix_change_requests_status", "change_requests", ["status"])
        op.create_index("ix_change_requests_reviewed_by_user_id", "change_requests", ["reviewed_by_user_id"])
    else:
        indexes = {index["name"] for index in inspector.get_indexes("change_requests")}
        if "ix_change_requests_organization_id" not in indexes:
            op.create_index("ix_change_requests_organization_id", "change_requests", ["organization_id"])
        if "ix_change_requests_requested_by_user_id" not in indexes:
            op.create_index(
                "ix_change_requests_requested_by_user_id",
                "change_requests",
                ["requested_by_user_id"],
            )
        if "ix_change_requests_requested_for_agent_id" not in indexes:
            op.create_index(
                "ix_change_requests_requested_for_agent_id",
                "change_requests",
                ["requested_for_agent_id"],
            )
        if "ix_change_requests_category" not in indexes:
            op.create_index("ix_change_requests_category", "change_requests", ["category"])
        if "ix_change_requests_priority" not in indexes:
            op.create_index("ix_change_requests_priority", "change_requests", ["priority"])
        if "ix_change_requests_status" not in indexes:
            op.create_index("ix_change_requests_status", "change_requests", ["status"])
        if "ix_change_requests_reviewed_by_user_id" not in indexes:
            op.create_index(
                "ix_change_requests_reviewed_by_user_id",
                "change_requests",
                ["reviewed_by_user_id"],
            )

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    columns = (
        {column["name"] for column in refreshed.get_columns("change_requests")}
        if "change_requests" in refreshed_tables
        else set()
    )
    if "category" in columns:
        op.alter_column("change_requests", "category", server_default=None)
    if "priority" in columns:
        op.alter_column("change_requests", "priority", server_default=None)
    if "status" in columns:
        op.alter_column("change_requests", "status", server_default=None)


def downgrade() -> None:
    """Drop change request lifecycle table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "change_requests" not in table_names:
        return
    indexes = {index["name"] for index in inspector.get_indexes("change_requests")}
    if "ix_change_requests_reviewed_by_user_id" in indexes:
        op.drop_index("ix_change_requests_reviewed_by_user_id", table_name="change_requests")
    if "ix_change_requests_status" in indexes:
        op.drop_index("ix_change_requests_status", table_name="change_requests")
    if "ix_change_requests_priority" in indexes:
        op.drop_index("ix_change_requests_priority", table_name="change_requests")
    if "ix_change_requests_category" in indexes:
        op.drop_index("ix_change_requests_category", table_name="change_requests")
    if "ix_change_requests_requested_for_agent_id" in indexes:
        op.drop_index("ix_change_requests_requested_for_agent_id", table_name="change_requests")
    if "ix_change_requests_requested_by_user_id" in indexes:
        op.drop_index("ix_change_requests_requested_by_user_id", table_name="change_requests")
    if "ix_change_requests_organization_id" in indexes:
        op.drop_index("ix_change_requests_organization_id", table_name="change_requests")
    op.drop_table("change_requests")
