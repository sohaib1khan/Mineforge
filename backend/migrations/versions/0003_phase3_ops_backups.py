"""Phase 3 worlds, operations, and backups tables.

Revision ID: 0003_phase3_ops
Revises: 0002_phase2_players
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_phase3_ops"
down_revision: str | None = "0002_phase2_players"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worlds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("folder_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("gamemode", sa.String(length=32), nullable=True),
        sa.Column("difficulty", sa.String(length=32), nullable=True),
        sa.Column("seed", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_played_at", sa.DateTime(), nullable=True),
        sa.Column("needs_experiments", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("folder_name"),
    )
    op.create_index("ix_worlds_folder_name", "worlds", ["folder_name"])
    op.create_index("ix_worlds_is_active", "worlds", ["is_active"])

    op.create_table(
        "operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("started_by", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("log", sa.Text(), nullable=False),
        sa.Column("rollback_performed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operations_type", "operations", ["type"])
    op.create_index("ix_operations_status", "operations", ["status"])
    op.create_index("ix_operations_started_by", "operations", ["started_by"])
    op.create_index("ix_operations_started_at", "operations", ["started_at"])

    op.create_table(
        "backups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("world_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("world_folder", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backups_world_id", "backups", ["world_id"])
    op.create_index("ix_backups_kind", "backups", ["kind"])
    op.create_index("ix_backups_created_at", "backups", ["created_at"])
    op.create_index("ix_backups_created_by", "backups", ["created_by"])
    op.create_index("ix_backups_world_folder", "backups", ["world_folder"])


def downgrade() -> None:
    op.drop_index("ix_backups_world_folder", table_name="backups")
    op.drop_index("ix_backups_created_by", table_name="backups")
    op.drop_index("ix_backups_created_at", table_name="backups")
    op.drop_index("ix_backups_kind", table_name="backups")
    op.drop_index("ix_backups_world_id", table_name="backups")
    op.drop_table("backups")

    op.drop_index("ix_operations_started_at", table_name="operations")
    op.drop_index("ix_operations_started_by", table_name="operations")
    op.drop_index("ix_operations_status", table_name="operations")
    op.drop_index("ix_operations_type", table_name="operations")
    op.drop_table("operations")

    op.drop_index("ix_worlds_is_active", table_name="worlds")
    op.drop_index("ix_worlds_folder_name", table_name="worlds")
    op.drop_table("worlds")
