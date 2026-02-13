"""add skill packs table

Revision ID: d1b2c3e4f5a6
Revises: c9d7e9b6a4f2
Create Date: 2026-02-14 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "d1b2c3e4f5a6"
down_revision = "c9d7e9b6a4f2"
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
    if not _has_table("skill_packs"):
        op.create_table(
            "skill_packs",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("source_url", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organizations.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "source_url",
                name="uq_skill_packs_org_source_url",
            ),
        )

    org_idx = op.f("ix_skill_packs_organization_id")
    if not _has_index("skill_packs", org_idx):
        op.create_index(
            org_idx,
            "skill_packs",
            ["organization_id"],
            unique=False,
        )


def downgrade() -> None:
    org_idx = op.f("ix_skill_packs_organization_id")
    if _has_index("skill_packs", org_idx):
        op.drop_index(
            org_idx,
            table_name="skill_packs",
        )

    if _has_table("skill_packs"):
        op.drop_table("skill_packs")
