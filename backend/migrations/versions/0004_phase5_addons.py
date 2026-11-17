"""Phase 5 addons and world_addons tables.

Revision ID: 0004_phase5_addons
Revises: 0003_phase3_ops
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_phase5_addons"
down_revision: str | None = "0003_phase3_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "addons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("pack_uuid", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("pair_addon_id", sa.Integer(), nullable=True),
        sa.Column("source_filename", sa.String(length=256), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("missing_pair", sa.Boolean(), nullable=False),
        sa.Column("encrypted", sa.Boolean(), nullable=False),
        sa.Column("needs_beta_apis", sa.Boolean(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(length=1024), nullable=True),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_addons_name", "addons", ["name"])
    op.create_index("ix_addons_pack_uuid", "addons", ["pack_uuid"])
    op.create_index("ix_addons_kind", "addons", ["kind"])
    op.create_index("ix_addons_pair_addon_id", "addons", ["pair_addon_id"])
    op.create_index("ix_addons_sha256", "addons", ["sha256"])
    op.create_index("ix_addons_uploaded_by", "addons", ["uploaded_by"])

    op.create_table(
        "world_addons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("world_id", sa.Integer(), nullable=False),
        sa.Column("addon_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("load_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["addon_id"], ["addons.id"]),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_world_addons_world_id", "world_addons", ["world_id"])
    op.create_index("ix_world_addons_addon_id", "world_addons", ["addon_id"])


def downgrade() -> None:
    op.drop_index("ix_world_addons_addon_id", table_name="world_addons")
    op.drop_index("ix_world_addons_world_id", table_name="world_addons")
    op.drop_table("world_addons")
    op.drop_index("ix_addons_uploaded_by", table_name="addons")
    op.drop_index("ix_addons_sha256", table_name="addons")
    op.drop_index("ix_addons_pair_addon_id", table_name="addons")
    op.drop_index("ix_addons_kind", table_name="addons")
    op.drop_index("ix_addons_pack_uuid", table_name="addons")
    op.drop_index("ix_addons_name", table_name="addons")
    op.drop_table("addons")
