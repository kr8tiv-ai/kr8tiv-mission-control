"""add marketplace skill metadata fields

Revision ID: e7a9b1c2d3e4
Revises: d1b2c3e4f5a6
Create Date: 2026-02-14 00:00:01.000000

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "e7a9b1c2d3e4"
down_revision = "d1b2c3e4f5a6"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade() -> None:
    if not _has_column("marketplace_skills", "category"):
        op.add_column(
            "marketplace_skills",
            sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        )
    if not _has_column("marketplace_skills", "risk"):
        op.add_column(
            "marketplace_skills",
            sa.Column("risk", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        )
    if not _has_column("marketplace_skills", "source"):
        op.add_column(
            "marketplace_skills",
            sa.Column("source", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("marketplace_skills", "source"):
        op.drop_column("marketplace_skills", "source")
    if _has_column("marketplace_skills", "risk"):
        op.drop_column("marketplace_skills", "risk")
    if _has_column("marketplace_skills", "category"):
        op.drop_column("marketplace_skills", "category")
