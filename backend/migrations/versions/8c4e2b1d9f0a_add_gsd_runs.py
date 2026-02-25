"""add gsd run telemetry table

Revision ID: 8c4e2b1d9f0a
Revises: 7d4b2a9e1c6f
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "8c4e2b1d9f0a"
down_revision = "7d4b2a9e1c6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create stage-level GSD run telemetry table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "gsd_runs" not in table_names:
        op.create_table(
            "gsd_runs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("board_id", sa.Uuid(), nullable=True),
            sa.Column("task_id", sa.Uuid(), nullable=True),
            sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("run_name", sa.String(), nullable=False, server_default=""),
            sa.Column("iteration_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("stage", sa.String(), nullable=False, server_default="planning"),
            sa.Column("status", sa.String(), nullable=False, server_default="in_progress"),
            sa.Column("owner_approval_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("owner_approval_status", sa.String(), nullable=False, server_default="not_required"),
            sa.Column("owner_approval_note", sa.String(), nullable=True),
            sa.Column("owner_approved_at", sa.DateTime(), nullable=True),
            sa.Column(
                "rollout_evidence_links",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_gsd_runs_organization_id", "gsd_runs", ["organization_id"])
        op.create_index("ix_gsd_runs_board_id", "gsd_runs", ["board_id"])
        op.create_index("ix_gsd_runs_task_id", "gsd_runs", ["task_id"])
        op.create_index("ix_gsd_runs_created_by_user_id", "gsd_runs", ["created_by_user_id"])
        op.create_index("ix_gsd_runs_run_name", "gsd_runs", ["run_name"])
        op.create_index("ix_gsd_runs_iteration_number", "gsd_runs", ["iteration_number"])
        op.create_index("ix_gsd_runs_stage", "gsd_runs", ["stage"])
        op.create_index("ix_gsd_runs_status", "gsd_runs", ["status"])
        op.create_index("ix_gsd_runs_owner_approval_status", "gsd_runs", ["owner_approval_status"])
        op.create_index("ix_gsd_runs_created_at", "gsd_runs", ["created_at"])
        op.create_index("ix_gsd_runs_updated_at", "gsd_runs", ["updated_at"])
    else:
        indexes = {index["name"] for index in inspector.get_indexes("gsd_runs")}
        if "ix_gsd_runs_organization_id" not in indexes:
            op.create_index("ix_gsd_runs_organization_id", "gsd_runs", ["organization_id"])
        if "ix_gsd_runs_board_id" not in indexes:
            op.create_index("ix_gsd_runs_board_id", "gsd_runs", ["board_id"])
        if "ix_gsd_runs_task_id" not in indexes:
            op.create_index("ix_gsd_runs_task_id", "gsd_runs", ["task_id"])
        if "ix_gsd_runs_created_by_user_id" not in indexes:
            op.create_index("ix_gsd_runs_created_by_user_id", "gsd_runs", ["created_by_user_id"])
        if "ix_gsd_runs_run_name" not in indexes:
            op.create_index("ix_gsd_runs_run_name", "gsd_runs", ["run_name"])
        if "ix_gsd_runs_iteration_number" not in indexes:
            op.create_index("ix_gsd_runs_iteration_number", "gsd_runs", ["iteration_number"])
        if "ix_gsd_runs_stage" not in indexes:
            op.create_index("ix_gsd_runs_stage", "gsd_runs", ["stage"])
        if "ix_gsd_runs_status" not in indexes:
            op.create_index("ix_gsd_runs_status", "gsd_runs", ["status"])
        if "ix_gsd_runs_owner_approval_status" not in indexes:
            op.create_index("ix_gsd_runs_owner_approval_status", "gsd_runs", ["owner_approval_status"])
        if "ix_gsd_runs_created_at" not in indexes:
            op.create_index("ix_gsd_runs_created_at", "gsd_runs", ["created_at"])
        if "ix_gsd_runs_updated_at" not in indexes:
            op.create_index("ix_gsd_runs_updated_at", "gsd_runs", ["updated_at"])

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    columns = (
        {column["name"] for column in refreshed.get_columns("gsd_runs")}
        if "gsd_runs" in refreshed_tables
        else set()
    )
    if "run_name" in columns:
        op.alter_column("gsd_runs", "run_name", server_default=None)
    if "iteration_number" in columns:
        op.alter_column("gsd_runs", "iteration_number", server_default=None)
    if "stage" in columns:
        op.alter_column("gsd_runs", "stage", server_default=None)
    if "status" in columns:
        op.alter_column("gsd_runs", "status", server_default=None)
    if "owner_approval_required" in columns:
        op.alter_column("gsd_runs", "owner_approval_required", server_default=None)
    if "owner_approval_status" in columns:
        op.alter_column("gsd_runs", "owner_approval_status", server_default=None)
    if "rollout_evidence_links" in columns:
        op.alter_column("gsd_runs", "rollout_evidence_links", server_default=None)


def downgrade() -> None:
    """Drop stage-level GSD run telemetry table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "gsd_runs" not in table_names:
        return
    indexes = {index["name"] for index in inspector.get_indexes("gsd_runs")}
    if "ix_gsd_runs_updated_at" in indexes:
        op.drop_index("ix_gsd_runs_updated_at", table_name="gsd_runs")
    if "ix_gsd_runs_created_at" in indexes:
        op.drop_index("ix_gsd_runs_created_at", table_name="gsd_runs")
    if "ix_gsd_runs_owner_approval_status" in indexes:
        op.drop_index("ix_gsd_runs_owner_approval_status", table_name="gsd_runs")
    if "ix_gsd_runs_status" in indexes:
        op.drop_index("ix_gsd_runs_status", table_name="gsd_runs")
    if "ix_gsd_runs_stage" in indexes:
        op.drop_index("ix_gsd_runs_stage", table_name="gsd_runs")
    if "ix_gsd_runs_iteration_number" in indexes:
        op.drop_index("ix_gsd_runs_iteration_number", table_name="gsd_runs")
    if "ix_gsd_runs_run_name" in indexes:
        op.drop_index("ix_gsd_runs_run_name", table_name="gsd_runs")
    if "ix_gsd_runs_created_by_user_id" in indexes:
        op.drop_index("ix_gsd_runs_created_by_user_id", table_name="gsd_runs")
    if "ix_gsd_runs_task_id" in indexes:
        op.drop_index("ix_gsd_runs_task_id", table_name="gsd_runs")
    if "ix_gsd_runs_board_id" in indexes:
        op.drop_index("ix_gsd_runs_board_id", table_name="gsd_runs")
    if "ix_gsd_runs_organization_id" in indexes:
        op.drop_index("ix_gsd_runs_organization_id", table_name="gsd_runs")
    op.drop_table("gsd_runs")

