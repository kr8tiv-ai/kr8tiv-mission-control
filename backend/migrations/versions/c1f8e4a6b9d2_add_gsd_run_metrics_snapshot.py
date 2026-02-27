"""add metrics snapshot to gsd runs

Revision ID: c1f8e4a6b9d2
Revises: e6b7c8d9f0a1
Create Date: 2026-02-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c1f8e4a6b9d2"
down_revision = "e6b7c8d9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add metrics payload to persisted GSD run telemetry rows."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "gsd_runs" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("gsd_runs")}
    if "metrics_snapshot" in columns:
        return
    op.add_column(
        "gsd_runs",
        sa.Column(
            "metrics_snapshot",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.alter_column("gsd_runs", "metrics_snapshot", server_default=None)


def downgrade() -> None:
    """Remove metrics payload from GSD run telemetry rows."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "gsd_runs" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("gsd_runs")}
    if "metrics_snapshot" not in columns:
        return
    op.drop_column("gsd_runs", "metrics_snapshot")

