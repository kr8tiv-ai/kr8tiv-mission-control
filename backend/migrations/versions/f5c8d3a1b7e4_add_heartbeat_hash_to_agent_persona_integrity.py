"""add heartbeat hash to agent persona integrity

Revision ID: f5c8d3a1b7e4
Revises: f2a9c7b1d4e3
Create Date: 2026-03-02 12:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f5c8d3a1b7e4"
down_revision = "f2a9c7b1d4e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add heartbeat checksum column for four-file persona drift detection."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "agent_persona_integrity" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("agent_persona_integrity")}
    if "heartbeat_sha256" not in columns:
        op.add_column(
            "agent_persona_integrity",
            sa.Column(
                "heartbeat_sha256",
                sa.Text(),
                nullable=False,
                server_default="",
            ),
        )

    op.execute(
        "UPDATE agent_persona_integrity "
        "SET heartbeat_sha256 = COALESCE(NULLIF(heartbeat_sha256, ''), user_sha256, '')"
    )



def downgrade() -> None:
    """Drop heartbeat checksum column."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "agent_persona_integrity" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("agent_persona_integrity")}
    if "heartbeat_sha256" in columns:
        op.drop_column("agent_persona_integrity", "heartbeat_sha256")
