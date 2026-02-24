"""add gsd lifecycle and deployment mode fields to tasks

Revision ID: e6b7c8d9f0a1
Revises: d3f8a2c1b4e6
Create Date: 2026-02-24 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "e6b7c8d9f0a1"
down_revision = "d3f8a2c1b4e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    task_columns = {column["name"] for column in inspector.get_columns("tasks")}

    if "gsd_stage" not in task_columns:
        op.add_column("tasks", sa.Column("gsd_stage", sa.String(), nullable=False, server_default="spec"))
        op.create_index("ix_tasks_gsd_stage", "tasks", ["gsd_stage"])
    if "spec_doc_ref" not in task_columns:
        op.add_column("tasks", sa.Column("spec_doc_ref", sa.Text(), nullable=True))
    if "plan_doc_ref" not in task_columns:
        op.add_column("tasks", sa.Column("plan_doc_ref", sa.Text(), nullable=True))
    if "verification_ref" not in task_columns:
        op.add_column("tasks", sa.Column("verification_ref", sa.Text(), nullable=True))
    if "deployment_mode" not in task_columns:
        op.add_column(
            "tasks",
            sa.Column("deployment_mode", sa.String(), nullable=False, server_default="team"),
        )
        op.create_index("ix_tasks_deployment_mode", "tasks", ["deployment_mode"])
    if "owner_approval_required" not in task_columns:
        op.add_column(
            "tasks",
            sa.Column("owner_approval_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "owner_approved_at" not in task_columns:
        op.add_column("tasks", sa.Column("owner_approved_at", sa.DateTime(), nullable=True))

    # Remove server defaults after backfilling existing rows.
    refreshed = sa.inspect(bind)
    refreshed_columns = {column["name"] for column in refreshed.get_columns("tasks")}
    if "gsd_stage" in refreshed_columns:
        op.alter_column("tasks", "gsd_stage", server_default=None)
    if "deployment_mode" in refreshed_columns:
        op.alter_column("tasks", "deployment_mode", server_default=None)
    if "owner_approval_required" in refreshed_columns:
        op.alter_column("tasks", "owner_approval_required", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    task_columns = {column["name"] for column in inspector.get_columns("tasks")}
    indexes = {index["name"] for index in inspector.get_indexes("tasks")}

    if "ix_tasks_gsd_stage" in indexes:
        op.drop_index("ix_tasks_gsd_stage", table_name="tasks")
    if "ix_tasks_deployment_mode" in indexes:
        op.drop_index("ix_tasks_deployment_mode", table_name="tasks")

    if "owner_approved_at" in task_columns:
        op.drop_column("tasks", "owner_approved_at")
    if "owner_approval_required" in task_columns:
        op.drop_column("tasks", "owner_approval_required")
    if "deployment_mode" in task_columns:
        op.drop_column("tasks", "deployment_mode")
    if "verification_ref" in task_columns:
        op.drop_column("tasks", "verification_ref")
    if "plan_doc_ref" in task_columns:
        op.drop_column("tasks", "plan_doc_ref")
    if "spec_doc_ref" in task_columns:
        op.drop_column("tasks", "spec_doc_ref")
    if "gsd_stage" in task_columns:
        op.drop_column("tasks", "gsd_stage")
