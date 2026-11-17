"""Pydantic schemas for metrics endpoints."""

from __future__ import annotations

from typing import Any

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


class LoginEventEntry(BaseModel):
    ts: str
    user_id: int | None = None
    username: str
    ip: str | None = None


class LoginsDayEntry(BaseModel):
    day: str
    logins: int


class PanelUserLoginEntry(BaseModel):
    id: int | None = None
    username: str
    role: str
    is_active: bool
    last_login_at: str | None = None
    created_at: str | None = None


class LoginActivityResponse(BaseModel):
    recent: list[LoginEventEntry] = Field(default_factory=list)
    logins_by_day: list[LoginsDayEntry] = Field(default_factory=list)
    users: list[PanelUserLoginEntry] = Field(default_factory=list)
    login_count_window: int = 0
    users_total: int = 0
    users_active: int = 0
    users_never_logged_in: int = 0


class WorldInsightPackEntry(BaseModel):
    name: str
    kind: str
    pack_uuid: str
    folder: str
    category: str
    size_bytes: int = 0
    counts: dict[str, int] = Field(default_factory=dict)
    weapon_like_items: int = 0
    structure_files: int = 0


class WorldInsightResponse(BaseModel):
    available: bool = False
    reason: str | None = None
    world: dict[str, Any] | None = None
    level: dict[str, Any] | None = None
    packs: list[WorldInsightPackEntry] = Field(default_factory=list)
    all_pack_names: list[str] = Field(default_factory=list)
    totals: dict[str, int] = Field(default_factory=dict)
    categories: dict[str, int] = Field(default_factory=dict)


class MetricsOverviewResponse(BaseModel):
    samples: list[MetricSampleResponse] = Field(default_factory=list)
    playtime: list[PlaytimeEntry] = Field(default_factory=list)
    joins: list[JoinsDayEntry] = Field(default_factory=list)
    disk: DiskSummaryResponse
    backups: list[BackupHistoryEntry] = Field(default_factory=list)
    sample_interval_seconds: int
    retention_days: int
    world_insight: WorldInsightResponse | None = None
    login_activity: LoginActivityResponse | None = None


class MetricsDashboardResponse(BaseModel):
    latest: MetricSampleResponse | None = None
    playtime_week: list[PlaytimeEntry] = Field(default_factory=list)
    disk: dict[str, int] = Field(default_factory=dict)
    players_online: int = 0
    world_insight: WorldInsightResponse | None = None
    login_activity: LoginActivityResponse | None = None
