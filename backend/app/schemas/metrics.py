"""Pydantic schemas for metrics endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetricSampleResponse(BaseModel):
    id: int
    ts: str
    cpu_pct: float
    mem_bytes: int
    mem_limit_bytes: int
    net_rx_bytes: int
    net_tx_bytes: int
    players_online: int


class PlaytimeEntry(BaseModel):
    gamertag: str
    seconds: int
    hours: float


class JoinsDayEntry(BaseModel):
    day: str
    joins: int


class WorldDiskEntry(BaseModel):
    id: int | None
    display_name: str
    folder_name: str
    size_bytes: int
    is_active: bool
    last_played_at: str | None = None
    gamemode: str | None = None
    difficulty: str | None = None


class DiskSummaryResponse(BaseModel):
    worlds: list[WorldDiskEntry] = Field(default_factory=list)
    worlds_bytes: int = 0
    backups_bytes: int = 0
    backup_count: int = 0


class BackupHistoryEntry(BaseModel):
    id: int | None
    world_folder: str
    kind: str
    size_bytes: int
    verified: bool
    created_at: str | None


class MetricsOverviewResponse(BaseModel):
    samples: list[MetricSampleResponse] = Field(default_factory=list)
    playtime: list[PlaytimeEntry] = Field(default_factory=list)
    joins: list[JoinsDayEntry] = Field(default_factory=list)
    disk: DiskSummaryResponse
    backups: list[BackupHistoryEntry] = Field(default_factory=list)
    sample_interval_seconds: int
    retention_days: int


class MetricsDashboardResponse(BaseModel):
    latest: MetricSampleResponse | None = None
    playtime_week: list[PlaytimeEntry] = Field(default_factory=list)
    disk: dict[str, int] = Field(default_factory=dict)
    players_online: int = 0
