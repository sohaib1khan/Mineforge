"""Stream settings and sessions.

Revision ID: 0007_stream
Revises: 0006_addon_library_backups
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_stream"
down_revision: str | None = "0006_addon_library_backups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stream_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("key_hash", sa.String(length=256), nullable=True),
        sa.Column("key_rotated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "stream_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("peak_viewers", sa.Integer(), nullable=False),
        sa.Column("started_by", sa.Integer(), nullable=True),
        sa.Column("publisher_ip", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stream_sessions_started_at", "stream_sessions", ["started_at"])
    op.create_index("ix_stream_sessions_ended_at", "stream_sessions", ["ended_at"])
    op.create_index("ix_stream_sessions_started_by", "stream_sessions", ["started_by"])


def downgrade() -> None:
    op.drop_index("ix_stream_sessions_started_by", table_name="stream_sessions")
    op.drop_index("ix_stream_sessions_ended_at", table_name="stream_sessions")
    op.drop_index("ix_stream_sessions_started_at", table_name="stream_sessions")
    op.drop_table("stream_sessions")
    op.drop_table("stream_settings")
