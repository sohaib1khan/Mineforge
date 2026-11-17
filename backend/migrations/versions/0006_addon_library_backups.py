"""Add-on library backup table.

Revision ID: 0006_addon_library_backups
Revises: 0005_phase7_metrics
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_addon_library_backups"
down_revision: str | None = "0005_phase7_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "addon_library_backups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("pack_count", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_addon_library_backups_created_at",
        "addon_library_backups",
        ["created_at"],
    )
    op.create_index(
        "ix_addon_library_backups_created_by",
        "addon_library_backups",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_addon_library_backups_created_by", table_name="addon_library_backups"
    )
    op.drop_index(
        "ix_addon_library_backups_created_at", table_name="addon_library_backups"
    )
    op.drop_table("addon_library_backups")
