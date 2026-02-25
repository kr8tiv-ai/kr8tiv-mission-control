"""add persona presets table

Revision ID: 0d7a4b9c2e1f
Revises: f9a1c6d2e4b7
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "0d7a4b9c2e1f"
down_revision = "f9a1c6d2e4b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create persona preset catalog table and indexes."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "persona_presets" not in table_names:
        op.create_table(
            "persona_presets",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("deployment_mode", sa.String(), nullable=False, server_default="team"),
            sa.Column("identity_profile", sa.JSON(), nullable=True),
            sa.Column("identity_template", sa.Text(), nullable=True),
            sa.Column("soul_template", sa.Text(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", "key", name="uq_persona_presets_org_key"),
        )
        op.create_index("ix_persona_presets_organization_id", "persona_presets", ["organization_id"])
        op.create_index("ix_persona_presets_key", "persona_presets", ["key"])
        op.create_index("ix_persona_presets_deployment_mode", "persona_presets", ["deployment_mode"])
    else:
        indexes = {index["name"] for index in inspector.get_indexes("persona_presets")}
        if "ix_persona_presets_organization_id" not in indexes:
            op.create_index(
                "ix_persona_presets_organization_id",
                "persona_presets",
                ["organization_id"],
            )
        if "ix_persona_presets_key" not in indexes:
            op.create_index("ix_persona_presets_key", "persona_presets", ["key"])
        if "ix_persona_presets_deployment_mode" not in indexes:
            op.create_index(
                "ix_persona_presets_deployment_mode",
                "persona_presets",
                ["deployment_mode"],
            )

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    columns = (
        {column["name"] for column in refreshed.get_columns("persona_presets")}
        if "persona_presets" in refreshed_tables
        else set()
    )
    if "deployment_mode" in columns:
        op.alter_column("persona_presets", "deployment_mode", server_default=None)


def downgrade() -> None:
    """Drop persona preset catalog table and indexes."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "persona_presets" not in table_names:
        return

    indexes = {index["name"] for index in inspector.get_indexes("persona_presets")}
    if "ix_persona_presets_deployment_mode" in indexes:
        op.drop_index("ix_persona_presets_deployment_mode", table_name="persona_presets")
    if "ix_persona_presets_key" in indexes:
        op.drop_index("ix_persona_presets_key", table_name="persona_presets")
    if "ix_persona_presets_organization_id" in indexes:
        op.drop_index("ix_persona_presets_organization_id", table_name="persona_presets")
    op.drop_table("persona_presets")
