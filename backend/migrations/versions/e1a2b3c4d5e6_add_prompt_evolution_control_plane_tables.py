"""add prompt evolution control-plane tables

Revision ID: e1a2b3c4d5e6
Revises: 1a7b2c3d4e5f
Create Date: 2026-02-24 06:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5e6"
down_revision: str | None = "1a7b2c3d4e5f"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_packs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False, server_default="board"),
        sa.Column("target_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("champion_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("challenger_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.ForeignKeyConstraint(["target_agent_id"], ["agents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_prompt_packs_board_id"), "prompt_packs", ["board_id"], unique=False)
    op.create_index(
        op.f("ix_prompt_packs_target_agent_id"),
        "prompt_packs",
        ["target_agent_id"],
        unique=False,
    )
    op.create_index(op.f("ix_prompt_packs_name"), "prompt_packs", ["name"], unique=False)
    op.create_index(op.f("ix_prompt_packs_scope"), "prompt_packs", ["scope"], unique=False)

    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=False),
        sa.Column("context_payload", sa.JSON(), nullable=False),
        sa.Column("metrics_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["prompt_pack_id"], ["prompt_packs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_prompt_versions_prompt_pack_id"),
        "prompt_versions",
        ["prompt_pack_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prompt_versions_version_number"),
        "prompt_versions",
        ["version_number"],
        unique=False,
    )

    op.create_table(
        "task_eval_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evaluator_type", sa.String(), nullable=False, server_default="task_completion"),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("detail_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["prompt_versions.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_task_eval_scores_board_id"),
        "task_eval_scores",
        ["board_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_eval_scores_task_id"),
        "task_eval_scores",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_eval_scores_prompt_version_id"),
        "task_eval_scores",
        ["prompt_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_task_eval_scores_evaluator_type"),
        "task_eval_scores",
        ["evaluator_type"],
        unique=False,
    )

    op.create_table(
        "optimization_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_pack_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("budget_limit_usd", sa.Float(), nullable=True),
        sa.Column("spend_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.ForeignKeyConstraint(["prompt_pack_id"], ["prompt_packs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_optimization_runs_board_id"),
        "optimization_runs",
        ["board_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_optimization_runs_prompt_pack_id"),
        "optimization_runs",
        ["prompt_pack_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_optimization_runs_status"),
        "optimization_runs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "promotion_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("board_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_pack_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision", sa.String(), nullable=False, server_default="approved"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"]),
        sa.ForeignKeyConstraint(["from_version_id"], ["prompt_versions.id"]),
        sa.ForeignKeyConstraint(["prompt_pack_id"], ["prompt_packs.id"]),
        sa.ForeignKeyConstraint(["to_version_id"], ["prompt_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_promotion_events_board_id"),
        "promotion_events",
        ["board_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_promotion_events_prompt_pack_id"),
        "promotion_events",
        ["prompt_pack_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_promotion_events_from_version_id"),
        "promotion_events",
        ["from_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_promotion_events_to_version_id"),
        "promotion_events",
        ["to_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_promotion_events_decision"),
        "promotion_events",
        ["decision"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_promotion_events_decision"), table_name="promotion_events")
    op.drop_index(op.f("ix_promotion_events_to_version_id"), table_name="promotion_events")
    op.drop_index(op.f("ix_promotion_events_from_version_id"), table_name="promotion_events")
    op.drop_index(op.f("ix_promotion_events_prompt_pack_id"), table_name="promotion_events")
    op.drop_index(op.f("ix_promotion_events_board_id"), table_name="promotion_events")
    op.drop_table("promotion_events")

    op.drop_index(op.f("ix_optimization_runs_status"), table_name="optimization_runs")
    op.drop_index(op.f("ix_optimization_runs_prompt_pack_id"), table_name="optimization_runs")
    op.drop_index(op.f("ix_optimization_runs_board_id"), table_name="optimization_runs")
    op.drop_table("optimization_runs")

    op.drop_index(op.f("ix_task_eval_scores_evaluator_type"), table_name="task_eval_scores")
    op.drop_index(op.f("ix_task_eval_scores_prompt_version_id"), table_name="task_eval_scores")
    op.drop_index(op.f("ix_task_eval_scores_task_id"), table_name="task_eval_scores")
    op.drop_index(op.f("ix_task_eval_scores_board_id"), table_name="task_eval_scores")
    op.drop_table("task_eval_scores")

    op.drop_index(op.f("ix_prompt_versions_version_number"), table_name="prompt_versions")
    op.drop_index(op.f("ix_prompt_versions_prompt_pack_id"), table_name="prompt_versions")
    op.drop_table("prompt_versions")

    op.drop_index(op.f("ix_prompt_packs_scope"), table_name="prompt_packs")
    op.drop_index(op.f("ix_prompt_packs_name"), table_name="prompt_packs")
    op.drop_index(op.f("ix_prompt_packs_target_agent_id"), table_name="prompt_packs")
    op.drop_index(op.f("ix_prompt_packs_board_id"), table_name="prompt_packs")
    op.drop_table("prompt_packs")
