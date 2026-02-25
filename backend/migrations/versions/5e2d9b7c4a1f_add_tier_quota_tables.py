"""add tier quota policies table

Revision ID: 5e2d9b7c4a1f
Revises: 4b8d2a1f6c3e
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "5e2d9b7c4a1f"
down_revision = "4b8d2a1f6c3e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tenant tier quota policy table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "tier_quotas" not in table_names:
        op.create_table(
            "tier_quotas",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("tier", sa.String(), nullable=False, server_default="personal"),
            sa.Column("max_abilities", sa.Integer(), nullable=False, server_default="25"),
            sa.Column("max_storage_mb", sa.Integer(), nullable=False, server_default="1024"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", "tier", name="uq_tier_quotas_org_tier"),
        )
        op.create_index("ix_tier_quotas_organization_id", "tier_quotas", ["organization_id"])
        op.create_index("ix_tier_quotas_tier", "tier_quotas", ["tier"])
    else:
        indexes = {index["name"] for index in inspector.get_indexes("tier_quotas")}
        if "ix_tier_quotas_organization_id" not in indexes:
            op.create_index("ix_tier_quotas_organization_id", "tier_quotas", ["organization_id"])
        if "ix_tier_quotas_tier" not in indexes:
            op.create_index("ix_tier_quotas_tier", "tier_quotas", ["tier"])

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    columns = (
        {column["name"] for column in refreshed.get_columns("tier_quotas")}
        if "tier_quotas" in refreshed_tables
        else set()
    )
    if "tier" in columns:
        op.alter_column("tier_quotas", "tier", server_default=None)
    if "max_abilities" in columns:
        op.alter_column("tier_quotas", "max_abilities", server_default=None)
    if "max_storage_mb" in columns:
        op.alter_column("tier_quotas", "max_storage_mb", server_default=None)


def downgrade() -> None:
    """Drop tenant tier quota policy table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "tier_quotas" not in table_names:
        return
    indexes = {index["name"] for index in inspector.get_indexes("tier_quotas")}
    if "ix_tier_quotas_tier" in indexes:
        op.drop_index("ix_tier_quotas_tier", table_name="tier_quotas")
    if "ix_tier_quotas_organization_id" in indexes:
        op.drop_index("ix_tier_quotas_organization_id", table_name="tier_quotas")
    op.drop_table("tier_quotas")
