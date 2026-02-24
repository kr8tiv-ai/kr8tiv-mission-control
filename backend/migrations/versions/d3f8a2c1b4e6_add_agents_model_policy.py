"""add agents model_policy json column

Revision ID: d3f8a2c1b4e6
Revises: c7f4d1b2a9e3
Create Date: 2026-02-23 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d3f8a2c1b4e6"
down_revision = "c7f4d1b2a9e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    agent_columns = {column["name"] for column in inspector.get_columns("agents")}
    if "model_policy" not in agent_columns:
        op.add_column("agents", sa.Column("model_policy", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    agent_columns = {column["name"] for column in inspector.get_columns("agents")}
    if "model_policy" in agent_columns:
        op.drop_column("agents", "model_policy")
