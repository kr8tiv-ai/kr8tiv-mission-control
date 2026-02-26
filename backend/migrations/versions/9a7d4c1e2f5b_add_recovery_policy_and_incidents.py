"""add recovery policy and incident tracking tables

Revision ID: 9a7d4c1e2f5b
Revises: 8c4e2b1d9f0a
Create Date: 2026-02-26 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "9a7d4c1e2f5b"
down_revision = "8c4e2b1d9f0a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create recovery policy and incident persistence tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "recovery_policies" not in table_names:
        op.create_table(
            "recovery_policies",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("stale_after_seconds", sa.Integer(), nullable=False, server_default="900"),
            sa.Column("max_restarts_per_hour", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="300"),
            sa.Column("alert_telegram", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("alert_whatsapp", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("alert_ui", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", name="uq_recovery_policies_org"),
        )
        op.create_index("ix_recovery_policies_organization_id", "recovery_policies", ["organization_id"])
        op.create_index("ix_recovery_policies_enabled", "recovery_policies", ["enabled"])

    if "recovery_incidents" not in table_names:
        op.create_table(
            "recovery_incidents",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("board_id", sa.Uuid(), nullable=True),
            sa.Column("agent_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="detected"),
            sa.Column("reason", sa.String(), nullable=False),
            sa.Column("action", sa.String(), nullable=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.String(), nullable=True),
            sa.Column("detected_at", sa.DateTime(), nullable=False),
            sa.Column("recovered_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_recovery_incidents_organization_id", "recovery_incidents", ["organization_id"])
        op.create_index("ix_recovery_incidents_board_id", "recovery_incidents", ["board_id"])
        op.create_index("ix_recovery_incidents_agent_id", "recovery_incidents", ["agent_id"])
        op.create_index("ix_recovery_incidents_status", "recovery_incidents", ["status"])
        op.create_index("ix_recovery_incidents_reason", "recovery_incidents", ["reason"])
        op.create_index("ix_recovery_incidents_detected_at", "recovery_incidents", ["detected_at"])

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    if "recovery_policies" in refreshed_tables:
        op.alter_column("recovery_policies", "enabled", server_default=None)
        op.alter_column("recovery_policies", "stale_after_seconds", server_default=None)
        op.alter_column("recovery_policies", "max_restarts_per_hour", server_default=None)
        op.alter_column("recovery_policies", "cooldown_seconds", server_default=None)
        op.alter_column("recovery_policies", "alert_telegram", server_default=None)
        op.alter_column("recovery_policies", "alert_whatsapp", server_default=None)
        op.alter_column("recovery_policies", "alert_ui", server_default=None)
    if "recovery_incidents" in refreshed_tables:
        op.alter_column("recovery_incidents", "status", server_default=None)
        op.alter_column("recovery_incidents", "attempts", server_default=None)


def downgrade() -> None:
    """Drop recovery policy and incident persistence tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "recovery_incidents" in table_names:
        indexes = {index["name"] for index in inspector.get_indexes("recovery_incidents")}
        if "ix_recovery_incidents_detected_at" in indexes:
            op.drop_index("ix_recovery_incidents_detected_at", table_name="recovery_incidents")
        if "ix_recovery_incidents_reason" in indexes:
            op.drop_index("ix_recovery_incidents_reason", table_name="recovery_incidents")
        if "ix_recovery_incidents_status" in indexes:
            op.drop_index("ix_recovery_incidents_status", table_name="recovery_incidents")
        if "ix_recovery_incidents_agent_id" in indexes:
            op.drop_index("ix_recovery_incidents_agent_id", table_name="recovery_incidents")
        if "ix_recovery_incidents_board_id" in indexes:
            op.drop_index("ix_recovery_incidents_board_id", table_name="recovery_incidents")
        if "ix_recovery_incidents_organization_id" in indexes:
            op.drop_index("ix_recovery_incidents_organization_id", table_name="recovery_incidents")
        op.drop_table("recovery_incidents")

    if "recovery_policies" in table_names:
        indexes = {index["name"] for index in inspector.get_indexes("recovery_policies")}
        if "ix_recovery_policies_enabled" in indexes:
            op.drop_index("ix_recovery_policies_enabled", table_name="recovery_policies")
        if "ix_recovery_policies_organization_id" in indexes:
            op.drop_index("ix_recovery_policies_organization_id", table_name="recovery_policies")
        op.drop_table("recovery_policies")
