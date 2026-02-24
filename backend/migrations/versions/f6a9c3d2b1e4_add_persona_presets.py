"""add persona presets table

Revision ID: f6a9c3d2b1e4
Revises: f0e4d1c9a2b7
Create Date: 2026-02-24 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "f6a9c3d2b1e4"
down_revision = "f0e4d1c9a2b7"
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
    if not _has_table("persona_presets"):
        op.create_table(
            "persona_presets",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column(
                "preset_mode",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default=sa.text("'team'"),
            ),
            sa.Column("identity_profile", sa.JSON(), nullable=True),
            sa.Column("identity_template", sa.Text(), nullable=True),
            sa.Column("soul_template", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organizations.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "name",
                name="uq_persona_presets_org_name",
            ),
        )

    org_idx = op.f("ix_persona_presets_organization_id")
    if not _has_index("persona_presets", org_idx):
        op.create_index(org_idx, "persona_presets", ["organization_id"], unique=False)

    mode_idx = op.f("ix_persona_presets_preset_mode")
    if not _has_index("persona_presets", mode_idx):
        op.create_index(mode_idx, "persona_presets", ["preset_mode"], unique=False)

    name_idx = op.f("ix_persona_presets_name")
    if not _has_index("persona_presets", name_idx):
        op.create_index(name_idx, "persona_presets", ["name"], unique=False)


def downgrade() -> None:
    org_idx = op.f("ix_persona_presets_organization_id")
    if _has_index("persona_presets", org_idx):
        op.drop_index(org_idx, table_name="persona_presets")

    mode_idx = op.f("ix_persona_presets_preset_mode")
    if _has_index("persona_presets", mode_idx):
        op.drop_index(mode_idx, table_name="persona_presets")

    name_idx = op.f("ix_persona_presets_name")
    if _has_index("persona_presets", name_idx):
        op.drop_index(name_idx, table_name="persona_presets")

    if _has_table("persona_presets"):
        op.drop_table("persona_presets")
