"""Add control-plane prompt packs, bindings, telemetry, evals, and promotion events.

Revision ID: f1a2b3c4d5e6
Revises: d3f8a2c1b4e6
Create Date: 2026-02-24 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "d3f8a2c1b4e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create control-plane persistence tables and indexes."""
    op.create_table(
        "prompt_packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default="organization"),
        sa.Column("scope_ref", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("tier", sa.String(length=32), nullable=False, server_default="personal"),
        sa.Column("pack_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_packs_organization_id", "prompt_packs", ["organization_id"], unique=False)
    op.create_index("ix_prompt_packs_created_by_user_id", "prompt_packs", ["created_by_user_id"], unique=False)
    op.create_index("ix_prompt_packs_scope", "prompt_packs", ["scope"], unique=False)
    op.create_index("ix_prompt_packs_scope_ref", "prompt_packs", ["scope_ref"], unique=False)
    op.create_index("ix_prompt_packs_tier", "prompt_packs", ["tier"], unique=False)
    op.create_index("ix_prompt_packs_pack_key", "prompt_packs", ["pack_key"], unique=False)

    op.create_table(
        "pack_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default="organization"),
        sa.Column("scope_ref", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("tier", sa.String(length=32), nullable=False, server_default="personal"),
        sa.Column("pack_key", sa.String(length=255), nullable=False),
        sa.Column("champion_pack_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["champion_pack_id"], ["prompt_packs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pack_bindings_organization_id", "pack_bindings", ["organization_id"], unique=False)
    op.create_index("ix_pack_bindings_created_by_user_id", "pack_bindings", ["created_by_user_id"], unique=False)
    op.create_index("ix_pack_bindings_scope", "pack_bindings", ["scope"], unique=False)
    op.create_index("ix_pack_bindings_scope_ref", "pack_bindings", ["scope_ref"], unique=False)
    op.create_index("ix_pack_bindings_tier", "pack_bindings", ["tier"], unique=False)
    op.create_index("ix_pack_bindings_pack_key", "pack_bindings", ["pack_key"], unique=False)
    op.create_index("ix_pack_bindings_champion_pack_id", "pack_bindings", ["champion_pack_id"], unique=False)

    op.create_table(
        "run_telemetry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("board_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("pack_id", sa.Uuid(), nullable=True),
        sa.Column("pack_key", sa.String(length=255), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False, server_default="personal"),
        sa.Column("domain", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("run_ref", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("success_bool", sa.Boolean(), nullable=False),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("format_contract_passed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approval_gate_passed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["board_id"], ["boards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pack_id"], ["prompt_packs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_run_telemetry_organization_id", "run_telemetry", ["organization_id"], unique=False)
    op.create_index("ix_run_telemetry_board_id", "run_telemetry", ["board_id"], unique=False)
    op.create_index("ix_run_telemetry_user_id", "run_telemetry", ["user_id"], unique=False)
    op.create_index("ix_run_telemetry_agent_id", "run_telemetry", ["agent_id"], unique=False)
    op.create_index("ix_run_telemetry_task_id", "run_telemetry", ["task_id"], unique=False)
    op.create_index("ix_run_telemetry_pack_id", "run_telemetry", ["pack_id"], unique=False)
    op.create_index("ix_run_telemetry_pack_key", "run_telemetry", ["pack_key"], unique=False)
    op.create_index("ix_run_telemetry_tier", "run_telemetry", ["tier"], unique=False)
    op.create_index("ix_run_telemetry_domain", "run_telemetry", ["domain"], unique=False)
    op.create_index("ix_run_telemetry_run_ref", "run_telemetry", ["run_ref"], unique=False)
    op.create_index("ix_run_telemetry_created_at", "run_telemetry", ["created_at"], unique=False)

    op.create_table(
        "deterministic_evals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_telemetry_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("pack_id", sa.Uuid(), nullable=True),
        sa.Column("pack_key", sa.String(length=255), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False, server_default="personal"),
        sa.Column("success_bool", sa.Boolean(), nullable=False),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_regression_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("format_contract_compliance", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approval_gate_compliance", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("hard_regression", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_telemetry_id"], ["run_telemetry.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pack_id"], ["prompt_packs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deterministic_evals_run_telemetry_id", "deterministic_evals", ["run_telemetry_id"], unique=False)
    op.create_index("ix_deterministic_evals_organization_id", "deterministic_evals", ["organization_id"], unique=False)
    op.create_index("ix_deterministic_evals_pack_id", "deterministic_evals", ["pack_id"], unique=False)
    op.create_index("ix_deterministic_evals_pack_key", "deterministic_evals", ["pack_key"], unique=False)
    op.create_index("ix_deterministic_evals_tier", "deterministic_evals", ["tier"], unique=False)
    op.create_index("ix_deterministic_evals_created_at", "deterministic_evals", ["created_at"], unique=False)

    op.create_table(
        "promotion_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False, server_default="promote"),
        sa.Column("from_pack_id", sa.Uuid(), nullable=True),
        sa.Column("to_pack_id", sa.Uuid(), nullable=False),
        sa.Column("triggered_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["binding_id"], ["pack_bindings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_pack_id"], ["prompt_packs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["to_pack_id"], ["prompt_packs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promotion_events_organization_id", "promotion_events", ["organization_id"], unique=False)
    op.create_index("ix_promotion_events_binding_id", "promotion_events", ["binding_id"], unique=False)
    op.create_index("ix_promotion_events_event_type", "promotion_events", ["event_type"], unique=False)
    op.create_index("ix_promotion_events_from_pack_id", "promotion_events", ["from_pack_id"], unique=False)
    op.create_index("ix_promotion_events_to_pack_id", "promotion_events", ["to_pack_id"], unique=False)
    op.create_index("ix_promotion_events_triggered_by_user_id", "promotion_events", ["triggered_by_user_id"], unique=False)
    op.create_index("ix_promotion_events_created_at", "promotion_events", ["created_at"], unique=False)


def downgrade() -> None:
    """Drop control-plane persistence tables and indexes."""
    op.drop_index("ix_promotion_events_created_at", table_name="promotion_events")
    op.drop_index("ix_promotion_events_triggered_by_user_id", table_name="promotion_events")
    op.drop_index("ix_promotion_events_to_pack_id", table_name="promotion_events")
    op.drop_index("ix_promotion_events_from_pack_id", table_name="promotion_events")
    op.drop_index("ix_promotion_events_event_type", table_name="promotion_events")
    op.drop_index("ix_promotion_events_binding_id", table_name="promotion_events")
    op.drop_index("ix_promotion_events_organization_id", table_name="promotion_events")
    op.drop_table("promotion_events")

    op.drop_index("ix_deterministic_evals_created_at", table_name="deterministic_evals")
    op.drop_index("ix_deterministic_evals_tier", table_name="deterministic_evals")
    op.drop_index("ix_deterministic_evals_pack_key", table_name="deterministic_evals")
    op.drop_index("ix_deterministic_evals_pack_id", table_name="deterministic_evals")
    op.drop_index("ix_deterministic_evals_organization_id", table_name="deterministic_evals")
    op.drop_index("ix_deterministic_evals_run_telemetry_id", table_name="deterministic_evals")
    op.drop_table("deterministic_evals")

    op.drop_index("ix_run_telemetry_created_at", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_run_ref", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_domain", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_tier", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_pack_key", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_pack_id", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_task_id", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_agent_id", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_user_id", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_board_id", table_name="run_telemetry")
    op.drop_index("ix_run_telemetry_organization_id", table_name="run_telemetry")
    op.drop_table("run_telemetry")

    op.drop_index("ix_pack_bindings_champion_pack_id", table_name="pack_bindings")
    op.drop_index("ix_pack_bindings_pack_key", table_name="pack_bindings")
    op.drop_index("ix_pack_bindings_tier", table_name="pack_bindings")
    op.drop_index("ix_pack_bindings_scope_ref", table_name="pack_bindings")
    op.drop_index("ix_pack_bindings_scope", table_name="pack_bindings")
    op.drop_index("ix_pack_bindings_created_by_user_id", table_name="pack_bindings")
    op.drop_index("ix_pack_bindings_organization_id", table_name="pack_bindings")
    op.drop_table("pack_bindings")

    op.drop_index("ix_prompt_packs_pack_key", table_name="prompt_packs")
    op.drop_index("ix_prompt_packs_tier", table_name="prompt_packs")
    op.drop_index("ix_prompt_packs_scope_ref", table_name="prompt_packs")
    op.drop_index("ix_prompt_packs_scope", table_name="prompt_packs")
    op.drop_index("ix_prompt_packs_created_by_user_id", table_name="prompt_packs")
    op.drop_index("ix_prompt_packs_organization_id", table_name="prompt_packs")
    op.drop_table("prompt_packs")
