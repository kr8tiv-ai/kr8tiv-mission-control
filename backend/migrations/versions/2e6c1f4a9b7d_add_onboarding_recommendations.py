"""add onboarding recommendations table

Revision ID: 2e6c1f4a9b7d
Revises: 0d7a4b9c2e1f
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "2e6c1f4a9b7d"
down_revision = "0d7a4b9c2e1f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create onboarding recommendation persistence table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "onboarding_recommendations" not in table_names:
        op.create_table(
            "onboarding_recommendations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("board_id", sa.Uuid(), nullable=False),
            sa.Column("onboarding_session_id", sa.Uuid(), nullable=True),
            sa.Column("deployment_mode", sa.String(), nullable=False, server_default="team"),
            sa.Column("persona_preset_key", sa.String(), nullable=False, server_default="team-operator"),
            sa.Column("ability_bundle", sa.JSON(), nullable=False),
            sa.Column("voice_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("backup_options_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("notebooklm_optional", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("recommendation_notes", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["onboarding_session_id"],
                ["board_onboarding_sessions.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_onboarding_recommendations_board_id",
            "onboarding_recommendations",
            ["board_id"],
        )
        op.create_index(
            "ix_onboarding_recommendations_onboarding_session_id",
            "onboarding_recommendations",
            ["onboarding_session_id"],
        )
        op.create_index(
            "ix_onboarding_recommendations_deployment_mode",
            "onboarding_recommendations",
            ["deployment_mode"],
        )
        op.create_index(
            "ix_onboarding_recommendations_persona_preset_key",
            "onboarding_recommendations",
            ["persona_preset_key"],
        )
    else:
        indexes = {index["name"] for index in inspector.get_indexes("onboarding_recommendations")}
        if "ix_onboarding_recommendations_board_id" not in indexes:
            op.create_index(
                "ix_onboarding_recommendations_board_id",
                "onboarding_recommendations",
                ["board_id"],
            )
        if "ix_onboarding_recommendations_onboarding_session_id" not in indexes:
            op.create_index(
                "ix_onboarding_recommendations_onboarding_session_id",
                "onboarding_recommendations",
                ["onboarding_session_id"],
            )
        if "ix_onboarding_recommendations_deployment_mode" not in indexes:
            op.create_index(
                "ix_onboarding_recommendations_deployment_mode",
                "onboarding_recommendations",
                ["deployment_mode"],
            )
        if "ix_onboarding_recommendations_persona_preset_key" not in indexes:
            op.create_index(
                "ix_onboarding_recommendations_persona_preset_key",
                "onboarding_recommendations",
                ["persona_preset_key"],
            )

    refreshed = sa.inspect(bind)
    refreshed_tables = set(refreshed.get_table_names())
    columns = (
        {column["name"] for column in refreshed.get_columns("onboarding_recommendations")}
        if "onboarding_recommendations" in refreshed_tables
        else set()
    )
    if "deployment_mode" in columns:
        op.alter_column("onboarding_recommendations", "deployment_mode", server_default=None)
    if "persona_preset_key" in columns:
        op.alter_column("onboarding_recommendations", "persona_preset_key", server_default=None)
    if "voice_enabled" in columns:
        op.alter_column("onboarding_recommendations", "voice_enabled", server_default=None)
    if "backup_options_enabled" in columns:
        op.alter_column("onboarding_recommendations", "backup_options_enabled", server_default=None)
    if "notebooklm_optional" in columns:
        op.alter_column("onboarding_recommendations", "notebooklm_optional", server_default=None)


def downgrade() -> None:
    """Drop onboarding recommendation persistence table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "onboarding_recommendations" not in table_names:
        return
    indexes = {index["name"] for index in inspector.get_indexes("onboarding_recommendations")}
    if "ix_onboarding_recommendations_persona_preset_key" in indexes:
        op.drop_index(
            "ix_onboarding_recommendations_persona_preset_key",
            table_name="onboarding_recommendations",
        )
    if "ix_onboarding_recommendations_deployment_mode" in indexes:
        op.drop_index(
            "ix_onboarding_recommendations_deployment_mode",
            table_name="onboarding_recommendations",
        )
    if "ix_onboarding_recommendations_onboarding_session_id" in indexes:
        op.drop_index(
            "ix_onboarding_recommendations_onboarding_session_id",
            table_name="onboarding_recommendations",
        )
    if "ix_onboarding_recommendations_board_id" in indexes:
        op.drop_index("ix_onboarding_recommendations_board_id", table_name="onboarding_recommendations")
    op.drop_table("onboarding_recommendations")
