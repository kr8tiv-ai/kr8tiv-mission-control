"""add installation requests and override session tables

Revision ID: 4b8d2a1f6c3e
Revises: 3f9a1c7d5b2e
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "4b8d2a1f6c3e"
down_revision = "3f9a1c7d5b2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create installation governance and override session tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "installation_requests" not in table_names:
        op.create_table(
            "installation_requests",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("capability_id", sa.Uuid(), nullable=True),
            sa.Column("agent_id", sa.Uuid(), nullable=True),
            sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("package_class", sa.String(), nullable=False),
            sa.Column("package_key", sa.String(), nullable=False),
            sa.Column("approval_mode", sa.String(), nullable=False, server_default="ask_first"),
            sa.Column("status", sa.String(), nullable=False, server_default="pending_owner_approval"),
            sa.Column("approved_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("denied_reason", sa.String(), nullable=True),
            sa.Column("requested_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["capability_id"], ["capabilities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_installation_requests_organization_id", "installation_requests", ["organization_id"])
        op.create_index("ix_installation_requests_capability_id", "installation_requests", ["capability_id"])
        op.create_index("ix_installation_requests_agent_id", "installation_requests", ["agent_id"])
        op.create_index(
            "ix_installation_requests_requested_by_user_id",
            "installation_requests",
            ["requested_by_user_id"],
        )
        op.create_index("ix_installation_requests_package_class", "installation_requests", ["package_class"])
        op.create_index("ix_installation_requests_package_key", "installation_requests", ["package_key"])
        op.create_index("ix_installation_requests_approval_mode", "installation_requests", ["approval_mode"])
        op.create_index("ix_installation_requests_status", "installation_requests", ["status"])
        op.create_index(
            "ix_installation_requests_approved_by_user_id",
            "installation_requests",
            ["approved_by_user_id"],
        )

    if "override_sessions" not in table_names:
        op.create_table(
            "override_sessions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("started_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("reason", sa.String(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["started_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_override_sessions_organization_id", "override_sessions", ["organization_id"])
        op.create_index("ix_override_sessions_started_by_user_id", "override_sessions", ["started_by_user_id"])
        op.create_index("ix_override_sessions_active", "override_sessions", ["active"])

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    installation_columns = (
        {column["name"] for column in refreshed.get_columns("installation_requests")}
        if "installation_requests" in refreshed_tables
        else set()
    )
    if "approval_mode" in installation_columns:
        op.alter_column("installation_requests", "approval_mode", server_default=None)
    if "status" in installation_columns:
        op.alter_column("installation_requests", "status", server_default=None)

    override_columns = (
        {column["name"] for column in refreshed.get_columns("override_sessions")}
        if "override_sessions" in refreshed_tables
        else set()
    )
    if "active" in override_columns:
        op.alter_column("override_sessions", "active", server_default=None)


def downgrade() -> None:
    """Drop installation governance and override session tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "override_sessions" in table_names:
        indexes = {index["name"] for index in inspector.get_indexes("override_sessions")}
        if "ix_override_sessions_active" in indexes:
            op.drop_index("ix_override_sessions_active", table_name="override_sessions")
        if "ix_override_sessions_started_by_user_id" in indexes:
            op.drop_index(
                "ix_override_sessions_started_by_user_id",
                table_name="override_sessions",
            )
        if "ix_override_sessions_organization_id" in indexes:
            op.drop_index("ix_override_sessions_organization_id", table_name="override_sessions")
        op.drop_table("override_sessions")

    if "installation_requests" in table_names:
        indexes = {index["name"] for index in inspector.get_indexes("installation_requests")}
        if "ix_installation_requests_approved_by_user_id" in indexes:
            op.drop_index(
                "ix_installation_requests_approved_by_user_id",
                table_name="installation_requests",
            )
        if "ix_installation_requests_status" in indexes:
            op.drop_index("ix_installation_requests_status", table_name="installation_requests")
        if "ix_installation_requests_approval_mode" in indexes:
            op.drop_index("ix_installation_requests_approval_mode", table_name="installation_requests")
        if "ix_installation_requests_package_key" in indexes:
            op.drop_index("ix_installation_requests_package_key", table_name="installation_requests")
        if "ix_installation_requests_package_class" in indexes:
            op.drop_index("ix_installation_requests_package_class", table_name="installation_requests")
        if "ix_installation_requests_requested_by_user_id" in indexes:
            op.drop_index(
                "ix_installation_requests_requested_by_user_id",
                table_name="installation_requests",
            )
        if "ix_installation_requests_agent_id" in indexes:
            op.drop_index("ix_installation_requests_agent_id", table_name="installation_requests")
        if "ix_installation_requests_capability_id" in indexes:
            op.drop_index("ix_installation_requests_capability_id", table_name="installation_requests")
        if "ix_installation_requests_organization_id" in indexes:
            op.drop_index(
                "ix_installation_requests_organization_id",
                table_name="installation_requests",
            )
        op.drop_table("installation_requests")
