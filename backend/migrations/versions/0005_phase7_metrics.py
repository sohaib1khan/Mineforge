"""Phase 7 metric_samples table.

Revision ID: 0005_phase7_metrics
Revises: 0004_phase5_addons
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_phase7_metrics"
down_revision: str | None = "0004_phase5_addons"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_samples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("cpu_pct", sa.Float(), nullable=False),
        sa.Column("mem_bytes", sa.Integer(), nullable=False),
        sa.Column("mem_limit_bytes", sa.Integer(), nullable=False),
        sa.Column("net_rx_bytes", sa.Integer(), nullable=False),
        sa.Column("net_tx_bytes", sa.Integer(), nullable=False),
        sa.Column("players_online", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("metric_samples", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_metric_samples_ts"), ["ts"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("metric_samples", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_metric_samples_ts"))
    op.drop_table("metric_samples")
