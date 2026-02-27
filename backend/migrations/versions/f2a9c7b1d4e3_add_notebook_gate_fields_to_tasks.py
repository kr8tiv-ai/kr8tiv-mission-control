"""add notebook gate fields to tasks

Revision ID: f2a9c7b1d4e3
Revises: d9b7c5a3e1f0
Create Date: 2026-02-27 01:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f2a9c7b1d4e3"
down_revision = "d9b7c5a3e1f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add notebook capability-gate state fields to tasks."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tasks" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("tasks")}

    if "notebook_gate_state" not in columns:
        op.add_column("tasks", sa.Column("notebook_gate_state", sa.Text(), nullable=True))
    if "notebook_gate_reason" not in columns:
        op.add_column("tasks", sa.Column("notebook_gate_reason", sa.Text(), nullable=True))
    if "notebook_gate_checked_at" not in columns:
        op.add_column("tasks", sa.Column("notebook_gate_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove notebook capability-gate state fields from tasks."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tasks" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("tasks")}

    if "notebook_gate_checked_at" in columns:
        op.drop_column("tasks", "notebook_gate_checked_at")
    if "notebook_gate_reason" in columns:
        op.drop_column("tasks", "notebook_gate_reason")
    if "notebook_gate_state" in columns:
        op.drop_column("tasks", "notebook_gate_state")
