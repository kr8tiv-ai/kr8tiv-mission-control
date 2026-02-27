"""merge notebook gate rollout heads

Revision ID: d9b7c5a3e1f0
Revises: a8c1d2e3f4b5, c1f8e4a6b9d2
Create Date: 2026-02-27 00:00:01.000000
"""

from __future__ import annotations


# revision identifiers, used by Alembic.
revision = "d9b7c5a3e1f0"
down_revision = ("a8c1d2e3f4b5", "c1f8e4a6b9d2")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge migration graph heads without additional schema changes."""


def downgrade() -> None:
    """Unmerge migration graph heads without additional schema changes."""
