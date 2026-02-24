"""add tier quota table

Revision ID: fe27b1c4d8a6
Revises: fd18a3c7b2e9
Create Date: 2026-02-24 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "fe27b1c4d8a6"
down_revision = "fd18a3c7b2e9"
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
    if not _has_table("tier_quotas"):
        op.create_table(
            "tier_quotas",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column(
                "tier_name",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default=sa.text("'hatchling'"),
            ),
            sa.Column("max_abilities", sa.Integer(), nullable=False, server_default=sa.text("5")),
            sa.Column("max_storage_mb", sa.Integer(), nullable=False, server_default=sa.text("2048")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("organization_id", name="uq_tier_quotas_organization_id"),
        )

    org_idx = op.f("ix_tier_quotas_organization_id")
    if not _has_index("tier_quotas", org_idx):
        op.create_index(org_idx, "tier_quotas", ["organization_id"], unique=False)


def downgrade() -> None:
    org_idx = op.f("ix_tier_quotas_organization_id")
    if _has_index("tier_quotas", org_idx):
        op.drop_index(org_idx, table_name="tier_quotas")

    if _has_table("tier_quotas"):
        op.drop_table("tier_quotas")
