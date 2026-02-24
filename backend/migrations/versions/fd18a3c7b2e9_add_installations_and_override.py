"""add installations and override sessions tables

Revision ID: fd18a3c7b2e9
Revises: fc7b1e2d9a4c
Create Date: 2026-02-24 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "fd18a3c7b2e9"
down_revision = "fc7b1e2d9a4c"
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
    if not _has_table("override_sessions"):
        op.create_table(
            "override_sessions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("reason", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    override_org_idx = op.f("ix_override_sessions_organization_id")
    if not _has_index("override_sessions", override_org_idx):
        op.create_index(override_org_idx, "override_sessions", ["organization_id"], unique=False)

    override_expires_idx = op.f("ix_override_sessions_expires_at")
    if not _has_index("override_sessions", override_expires_idx):
        op.create_index(override_expires_idx, "override_sessions", ["expires_at"], unique=False)

    override_active_idx = op.f("ix_override_sessions_active")
    if not _has_index("override_sessions", override_active_idx):
        op.create_index(override_active_idx, "override_sessions", ["active"], unique=False)

    if not _has_table("installation_requests"):
        op.create_table(
            "installation_requests",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("organization_id", sa.Uuid(), nullable=False),
            sa.Column("capability_id", sa.Uuid(), nullable=True),
            sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("install_command", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column(
                "approval_mode",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default=sa.text("'ask_first'"),
            ),
            sa.Column(
                "status",
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default=sa.text("'pending_owner_approval'"),
            ),
            sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
            sa.Column("override_session_id", sa.Uuid(), nullable=True),
            sa.Column("requested_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["capability_id"], ["capabilities.id"]),
            sa.ForeignKeyConstraint(["override_session_id"], ["override_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    install_org_idx = op.f("ix_installation_requests_organization_id")
    if not _has_index("installation_requests", install_org_idx):
        op.create_index(
            install_org_idx,
            "installation_requests",
            ["organization_id"],
            unique=False,
        )

    install_cap_idx = op.f("ix_installation_requests_capability_id")
    if not _has_index("installation_requests", install_cap_idx):
        op.create_index(
            install_cap_idx,
            "installation_requests",
            ["capability_id"],
            unique=False,
        )

    install_mode_idx = op.f("ix_installation_requests_approval_mode")
    if not _has_index("installation_requests", install_mode_idx):
        op.create_index(
            install_mode_idx,
            "installation_requests",
            ["approval_mode"],
            unique=False,
        )

    install_status_idx = op.f("ix_installation_requests_status")
    if not _has_index("installation_requests", install_status_idx):
        op.create_index(
            install_status_idx,
            "installation_requests",
            ["status"],
            unique=False,
        )

    install_override_idx = op.f("ix_installation_requests_override_session_id")
    if not _has_index("installation_requests", install_override_idx):
        op.create_index(
            install_override_idx,
            "installation_requests",
            ["override_session_id"],
            unique=False,
        )


def downgrade() -> None:
    install_org_idx = op.f("ix_installation_requests_organization_id")
    if _has_index("installation_requests", install_org_idx):
        op.drop_index(install_org_idx, table_name="installation_requests")

    install_cap_idx = op.f("ix_installation_requests_capability_id")
    if _has_index("installation_requests", install_cap_idx):
        op.drop_index(install_cap_idx, table_name="installation_requests")

    install_mode_idx = op.f("ix_installation_requests_approval_mode")
    if _has_index("installation_requests", install_mode_idx):
        op.drop_index(install_mode_idx, table_name="installation_requests")

    install_status_idx = op.f("ix_installation_requests_status")
    if _has_index("installation_requests", install_status_idx):
        op.drop_index(install_status_idx, table_name="installation_requests")

    install_override_idx = op.f("ix_installation_requests_override_session_id")
    if _has_index("installation_requests", install_override_idx):
        op.drop_index(install_override_idx, table_name="installation_requests")

    if _has_table("installation_requests"):
        op.drop_table("installation_requests")

    override_org_idx = op.f("ix_override_sessions_organization_id")
    if _has_index("override_sessions", override_org_idx):
        op.drop_index(override_org_idx, table_name="override_sessions")

    override_expires_idx = op.f("ix_override_sessions_expires_at")
    if _has_index("override_sessions", override_expires_idx):
        op.drop_index(override_expires_idx, table_name="override_sessions")

    override_active_idx = op.f("ix_override_sessions_active")
    if _has_index("override_sessions", override_active_idx):
        op.drop_index(override_active_idx, table_name="override_sessions")

    if _has_table("override_sessions"):
        op.drop_table("override_sessions")
