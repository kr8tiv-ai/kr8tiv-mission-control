"""Add task modes and task iteration tracking.

Revision ID: c7f4d1b2a9e3
Revises: b7a1d9c3e4f5
Create Date: 2026-02-23 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c7f4d1b2a9e3"
down_revision = "b7a1d9c3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add mode-aware task columns and create task_iterations table."""
    op.add_column(
        "tasks",
        sa.Column("task_mode", sa.String(length=32), nullable=False, server_default="standard"),
    )
    op.add_column("tasks", sa.Column("arena_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "notebook_profile",
            sa.String(length=16),
            nullable=False,
            server_default="auto",
        ),
    )
    op.add_column("tasks", sa.Column("notebook_id", sa.Text(), nullable=True))
    op.add_column("tasks", sa.Column("notebook_share_url", sa.Text(), nullable=True))

    op.create_index("ix_tasks_task_mode", "tasks", ["task_mode"], unique=False)
    op.create_index("ix_tasks_notebook_profile", "tasks", ["notebook_profile"], unique=False)
    op.create_check_constraint(
        "ck_tasks_task_mode",
        "tasks",
        "task_mode IN ('standard', 'notebook', 'arena', 'arena_notebook', 'notebook_creation')",
    )
    op.create_check_constraint(
        "ck_tasks_notebook_profile",
        "tasks",
        "notebook_profile IN ('enterprise', 'personal', 'auto')",
    )

    op.create_table(
        "task_iterations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("verdict", sa.String(length=20), nullable=False),
        sa.Column(
            "round_outputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "verdict IN ('APPROVED', 'REVISE', 'ERROR')",
            name="ck_task_iterations_verdict",
        ),
    )
    op.create_index(
        "ix_task_iterations_task_id_round_number",
        "task_iterations",
        ["task_id", "round_number"],
        unique=False,
    )
    op.create_index(
        "ix_task_iterations_task_id_created_at",
        "task_iterations",
        ["task_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_task_iterations_task_id", "task_iterations", ["task_id"], unique=False)
    op.create_index("ix_task_iterations_round_number", "task_iterations", ["round_number"], unique=False)
    op.create_index("ix_task_iterations_agent_id", "task_iterations", ["agent_id"], unique=False)
    op.create_index("ix_task_iterations_created_at", "task_iterations", ["created_at"], unique=False)


def downgrade() -> None:
    """Drop mode-aware task columns and task_iterations table."""
    op.drop_index("ix_task_iterations_created_at", table_name="task_iterations")
    op.drop_index("ix_task_iterations_agent_id", table_name="task_iterations")
    op.drop_index("ix_task_iterations_round_number", table_name="task_iterations")
    op.drop_index("ix_task_iterations_task_id", table_name="task_iterations")
    op.drop_index("ix_task_iterations_task_id_created_at", table_name="task_iterations")
    op.drop_index("ix_task_iterations_task_id_round_number", table_name="task_iterations")
    op.drop_table("task_iterations")

    op.drop_constraint("ck_tasks_notebook_profile", "tasks", type_="check")
    op.drop_constraint("ck_tasks_task_mode", "tasks", type_="check")
    op.drop_index("ix_tasks_notebook_profile", table_name="tasks")
    op.drop_index("ix_tasks_task_mode", table_name="tasks")
    op.drop_column("tasks", "notebook_share_url")
    op.drop_column("tasks", "notebook_id")
    op.drop_column("tasks", "notebook_profile")
    op.drop_column("tasks", "arena_config")
    op.drop_column("tasks", "task_mode")
