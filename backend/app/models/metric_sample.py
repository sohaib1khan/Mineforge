"""Periodic Docker / player metric samples for the Metrics page."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class MetricSample(SQLModel, table=True):
    __tablename__ = "metric_samples"

    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
        nullable=False,
    )
    cpu_pct: float = Field(default=0.0, nullable=False)
    mem_bytes: int = Field(default=0, nullable=False)
    mem_limit_bytes: int = Field(default=0, nullable=False)
    net_rx_bytes: int = Field(default=0, nullable=False)
    net_tx_bytes: int = Field(default=0, nullable=False)
    players_online: int = Field(default=0, nullable=False)
