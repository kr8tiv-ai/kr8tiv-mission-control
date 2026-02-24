"""add agent persona integrity table

Revision ID: f0e4d1c9a2b7
Revises: e6b7c8d9f0a1
Create Date: 2026-02-24 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f0e4d1c9a2b7"
down_revision = "e6b7c8d9f0a1"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    if not _has_table("agent_persona_integrity"):
        op.create_table(
            "agent_persona_integrity",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("agent_id", sa.Uuid(), nullable=False),
            sa.Column("soul_sha256", sa.String(length=64), nullable=False),
            sa.Column("user_sha256", sa.String(length=64), nullable=False),
            sa.Column("identity_sha256", sa.String(length=64), nullable=False),
            sa.Column("agents_sha256", sa.String(length=64), nullable=False),
            sa.Column("drift_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("last_checked_at", sa.DateTime(), nullable=False),
            sa.Column("last_drift_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "agent_id",
                name="uq_agent_persona_integrity_agent_id",
            ),
        )

    agent_idx = op.f("ix_agent_persona_integrity_agent_id")
    if not _has_index("agent_persona_integrity", agent_idx):
        op.create_index(
            agent_idx,
            "agent_persona_integrity",
            ["agent_id"],
            unique=False,
        )


def downgrade() -> None:
    agent_idx = op.f("ix_agent_persona_integrity_agent_id")
    if _has_index("agent_persona_integrity", agent_idx):
        op.drop_index(agent_idx, table_name="agent_persona_integrity")

    if _has_table("agent_persona_integrity"):
        op.drop_table("agent_persona_integrity")
