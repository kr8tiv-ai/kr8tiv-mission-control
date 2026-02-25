"""add capabilities catalog table

Revision ID: 3f9a1c7d5b2e
Revises: 2e6c1f4a9b7d
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "3f9a1c7d5b2e"
down_revision = "2e6c1f4a9b7d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create capability catalog persistence table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "capabilities" not in table_names:
        op.create_table(
            "capabilities",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("capability_type", sa.String(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("version", sa.String(), nullable=True),
            sa.Column("risk_level", sa.String(), nullable=False, server_default="low"),
            sa.Column("access_scope", sa.String(), nullable=False, server_default="tenant"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "capability_type",
                "key",
                name="uq_capabilities_org_type_key",
            ),
        )
        op.create_index("ix_capabilities_organization_id", "capabilities", ["organization_id"])
        op.create_index("ix_capabilities_capability_type", "capabilities", ["capability_type"])
        op.create_index("ix_capabilities_key", "capabilities", ["key"])
    else:
        indexes = {index["name"] for index in inspector.get_indexes("capabilities")}
        if "ix_capabilities_organization_id" not in indexes:
            op.create_index("ix_capabilities_organization_id", "capabilities", ["organization_id"])
        if "ix_capabilities_capability_type" not in indexes:
            op.create_index("ix_capabilities_capability_type", "capabilities", ["capability_type"])
        if "ix_capabilities_key" not in indexes:
            op.create_index("ix_capabilities_key", "capabilities", ["key"])

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    columns = (
        {column["name"] for column in refreshed.get_columns("capabilities")}
        if "capabilities" in refreshed_tables
        else set()
    )
    if "risk_level" in columns:
        op.alter_column("capabilities", "risk_level", server_default=None)
    if "access_scope" in columns:
        op.alter_column("capabilities", "access_scope", server_default=None)
    if "enabled" in columns:
        op.alter_column("capabilities", "enabled", server_default=None)


def downgrade() -> None:
    """Drop capability catalog table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "capabilities" not in table_names:
        return
    indexes = {index["name"] for index in inspector.get_indexes("capabilities")}
    if "ix_capabilities_key" in indexes:
        op.drop_index("ix_capabilities_key", table_name="capabilities")
    if "ix_capabilities_capability_type" in indexes:
        op.drop_index("ix_capabilities_capability_type", table_name="capabilities")
    if "ix_capabilities_organization_id" in indexes:
        op.drop_index("ix_capabilities_organization_id", table_name="capabilities")
    op.drop_table("capabilities")
