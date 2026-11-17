"""Phase 2 player_sessions table.

Revision ID: 0002_phase2_players
Revises: 0001_phase1_auth
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_phase2_players"
down_revision: str | None = "0001_phase1_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("gamertag", sa.String(length=128), nullable=False),
        sa.Column("xuid", sa.String(length=32), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("left_at", sa.DateTime(), nullable=True),
        sa.Column("world_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_player_sessions_gamertag", "player_sessions", ["gamertag"])
    op.create_index("ix_player_sessions_xuid", "player_sessions", ["xuid"])
    op.create_index("ix_player_sessions_joined_at", "player_sessions", ["joined_at"])
    op.create_index("ix_player_sessions_left_at", "player_sessions", ["left_at"])
    op.create_index("ix_player_sessions_world_id", "player_sessions", ["world_id"])


def downgrade() -> None:
    op.drop_index("ix_player_sessions_world_id", table_name="player_sessions")
    op.drop_index("ix_player_sessions_left_at", table_name="player_sessions")
    op.drop_index("ix_player_sessions_joined_at", table_name="player_sessions")
    op.drop_index("ix_player_sessions_xuid", table_name="player_sessions")
    op.drop_index("ix_player_sessions_gamertag", table_name="player_sessions")
    op.drop_table("player_sessions")
