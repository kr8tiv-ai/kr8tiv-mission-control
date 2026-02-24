"""add capabilities table

Revision ID: fc7b1e2d9a4c
Revises: f9c1a7d4e2b6
Create Date: 2026-02-24 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "fc7b1e2d9a4c"
down_revision = "f9c1a7d4e2b6"
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
    if not _has_table("capabilities"):
        op.create_table(
            "capabilities",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column(
                "risk_level",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default=sa.text("'medium'"),
            ),
            sa.Column(
                "scope",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default=sa.text("'team'"),
            ),
            sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "organization_id",
                "kind",
                "name",
                name="uq_capabilities_org_kind_name",
            ),
        )

    org_idx = op.f("ix_capabilities_organization_id")
    if not _has_index("capabilities", org_idx):
        op.create_index(org_idx, "capabilities", ["organization_id"], unique=False)

    kind_idx = op.f("ix_capabilities_kind")
    if not _has_index("capabilities", kind_idx):
        op.create_index(kind_idx, "capabilities", ["kind"], unique=False)

    name_idx = op.f("ix_capabilities_name")
    if not _has_index("capabilities", name_idx):
        op.create_index(name_idx, "capabilities", ["name"], unique=False)

    risk_idx = op.f("ix_capabilities_risk_level")
    if not _has_index("capabilities", risk_idx):
        op.create_index(risk_idx, "capabilities", ["risk_level"], unique=False)

    scope_idx = op.f("ix_capabilities_scope")
    if not _has_index("capabilities", scope_idx):
        op.create_index(scope_idx, "capabilities", ["scope"], unique=False)


def downgrade() -> None:
    org_idx = op.f("ix_capabilities_organization_id")
    if _has_index("capabilities", org_idx):
        op.drop_index(org_idx, table_name="capabilities")

    kind_idx = op.f("ix_capabilities_kind")
    if _has_index("capabilities", kind_idx):
        op.drop_index(kind_idx, table_name="capabilities")

    name_idx = op.f("ix_capabilities_name")
    if _has_index("capabilities", name_idx):
        op.drop_index(name_idx, table_name="capabilities")

    risk_idx = op.f("ix_capabilities_risk_level")
    if _has_index("capabilities", risk_idx):
        op.drop_index(risk_idx, table_name="capabilities")

    scope_idx = op.f("ix_capabilities_scope")
    if _has_index("capabilities", scope_idx):
        op.drop_index(scope_idx, table_name="capabilities")

    if _has_table("capabilities"):
        op.drop_table("capabilities")
