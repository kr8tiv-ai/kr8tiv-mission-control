"""add agent persona integrity baseline table

Revision ID: f9a1c6d2e4b7
Revises: e6b7c8d9f0a1, f1a2b3c4d5e6
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f9a1c6d2e4b7"
down_revision = ("e6b7c8d9f0a1", "f1a2b3c4d5e6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create persona integrity baseline table and indexes."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "agent_persona_integrity" not in table_names:
        op.create_table(
            "agent_persona_integrity",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("agent_id", sa.Uuid(), nullable=False),
            sa.Column("soul_sha256", sa.String(), nullable=False),
            sa.Column("user_sha256", sa.String(), nullable=False),
            sa.Column("identity_sha256", sa.String(), nullable=False),
            sa.Column("agents_sha256", sa.String(), nullable=False),
            sa.Column("drift_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_checked_at", sa.DateTime(), nullable=False),
            sa.Column("last_drift_at", sa.DateTime(), nullable=True),
            sa.Column("last_drift_fields", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("agent_id", name="uq_agent_persona_integrity_agent_id"),
        )
        op.create_index(
            "ix_agent_persona_integrity_agent_id",
            "agent_persona_integrity",
            ["agent_id"],
            unique=False,
        )
        op.create_index(
            "ix_agent_persona_integrity_last_checked_at",
            "agent_persona_integrity",
            ["last_checked_at"],
            unique=False,
        )
    else:
        indexes = {index["name"] for index in inspector.get_indexes("agent_persona_integrity")}
        if "ix_agent_persona_integrity_agent_id" not in indexes:
            op.create_index(
                "ix_agent_persona_integrity_agent_id",
                "agent_persona_integrity",
                ["agent_id"],
                unique=False,
            )
        if "ix_agent_persona_integrity_last_checked_at" not in indexes:
            op.create_index(
                "ix_agent_persona_integrity_last_checked_at",
                "agent_persona_integrity",
                ["last_checked_at"],
                unique=False,
            )

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    columns = (
        {column["name"] for column in refreshed.get_columns("agent_persona_integrity")}
        if "agent_persona_integrity" in refreshed_tables
        else set()
    )
    if "drift_count" in columns:
        op.alter_column("agent_persona_integrity", "drift_count", server_default=None)


def downgrade() -> None:
    """Drop persona integrity baseline table and indexes."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "agent_persona_integrity" not in set(inspector.get_table_names()):
        return

    indexes = {index["name"] for index in inspector.get_indexes("agent_persona_integrity")}
    if "ix_agent_persona_integrity_last_checked_at" in indexes:
        op.drop_index(
            "ix_agent_persona_integrity_last_checked_at",
            table_name="agent_persona_integrity",
        )
    if "ix_agent_persona_integrity_agent_id" in indexes:
        op.drop_index(
            "ix_agent_persona_integrity_agent_id",
            table_name="agent_persona_integrity",
        )
    op.drop_table("agent_persona_integrity")
