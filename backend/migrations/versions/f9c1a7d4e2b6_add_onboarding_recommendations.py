"""add onboarding recommendations table

Revision ID: f9c1a7d4e2b6
Revises: f6a9c3d2b1e4
Create Date: 2026-02-24 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "f9c1a7d4e2b6"
down_revision = "f6a9c3d2b1e4"
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
    if not _has_table("onboarding_recommendations"):
        op.create_table(
            "onboarding_recommendations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("board_id", sa.Uuid(), nullable=False),
            sa.Column("onboarding_session_id", sa.Uuid(), nullable=True),
            sa.Column(
                "deployment_mode",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default=sa.text("'team'"),
            ),
            sa.Column(
                "recommended_preset",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default=sa.text("'team_orchestrated_default'"),
            ),
            sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("voice_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("computer_automation_profile", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column(
                "supermemory_plugin_command",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default=sa.text("'openclaw plugins install @supermemory/openclaw-supermemory'"),
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
            sa.ForeignKeyConstraint(["onboarding_session_id"], ["board_onboarding_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "board_id",
                name="uq_onboarding_recommendations_board_id",
            ),
        )

    board_idx = op.f("ix_onboarding_recommendations_board_id")
    if not _has_index("onboarding_recommendations", board_idx):
        op.create_index(board_idx, "onboarding_recommendations", ["board_id"], unique=False)

    session_idx = op.f("ix_onboarding_recommendations_onboarding_session_id")
    if not _has_index("onboarding_recommendations", session_idx):
        op.create_index(
            session_idx,
            "onboarding_recommendations",
            ["onboarding_session_id"],
            unique=False,
        )

    mode_idx = op.f("ix_onboarding_recommendations_deployment_mode")
    if not _has_index("onboarding_recommendations", mode_idx):
        op.create_index(
            mode_idx,
            "onboarding_recommendations",
            ["deployment_mode"],
            unique=False,
        )


def downgrade() -> None:
    board_idx = op.f("ix_onboarding_recommendations_board_id")
    if _has_index("onboarding_recommendations", board_idx):
        op.drop_index(board_idx, table_name="onboarding_recommendations")

    session_idx = op.f("ix_onboarding_recommendations_onboarding_session_id")
    if _has_index("onboarding_recommendations", session_idx):
        op.drop_index(session_idx, table_name="onboarding_recommendations")

    mode_idx = op.f("ix_onboarding_recommendations_deployment_mode")
    if _has_index("onboarding_recommendations", mode_idx):
        op.drop_index(mode_idx, table_name="onboarding_recommendations")

    if _has_table("onboarding_recommendations"):
        op.drop_table("onboarding_recommendations")
