"""add recovery alert dedupe seconds policy column

Revision ID: a8c1d2e3f4b5
Revises: 9a7d4c1e2f5b
Create Date: 2026-02-26 00:00:01.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "a8c1d2e3f4b5"
down_revision = "9a7d4c1e2f5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add alert dedupe window control to recovery policies."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("recovery_policies")}
    if "alert_dedupe_seconds" not in columns:
        op.add_column(
            "recovery_policies",
            sa.Column(
                "alert_dedupe_seconds",
                sa.Integer(),
                nullable=False,
                server_default="900",
            ),
        )
        op.alter_column(
            "recovery_policies",
            "alert_dedupe_seconds",
            server_default=None,
        )


def downgrade() -> None:
    """Remove alert dedupe window control from recovery policies."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("recovery_policies")}
    if "alert_dedupe_seconds" in columns:
        op.drop_column("recovery_policies", "alert_dedupe_seconds")
