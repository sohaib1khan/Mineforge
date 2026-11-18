"""Server, console, allowlist, and properties schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlayerOnline(BaseModel):
    gamertag: str
    xuid: str | None = None
    joined_at: str | None = None


class ContainerInfo(BaseModel):
    name: str
    exists: bool
    running: bool
    status: str
    image: str | None = None
    started_at: str | None = None
    uptime_seconds: int | None = None
    finished_at: str | None = None
    created_at: str | None = None
    exit_code: int | None = None
    pid: int | None = None
    restart_count: int = 0
    oom_killed: bool = False
    error: str | None = None
    health: str | None = None
    restart_policy: str | None = None
    platform: str | None = None


class ContainerResources(BaseModel):
    cpu_pct: float
    mem_bytes: int
    mem_limit_bytes: int
    mem_pct: float | None = None
    net_rx_bytes: int
    net_tx_bytes: int


class ContainerPortInfo(BaseModel):
    private: str
    public: str | None = None


class ContainerMountInfo(BaseModel):
    destination: str
    mode: str
    type: str


class ServerStatusResponse(BaseModel):
    container: ContainerInfo
    resources: ContainerResources | None = None
    ports: list[ContainerPortInfo] = Field(default_factory=list)
    mounts: list[ContainerMountInfo] = Field(default_factory=list)
    safe_env: dict[str, str] = Field(default_factory=dict)
    server_settings: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    level_name: str | None
    players_online: list[PlayerOnline]
    player_count: int
    properties_present: bool


class MessageResponse(BaseModel):
    detail: str


class PropertiesResponse(BaseModel):
    values: dict[str, str]
    catalog: list[dict[str, Any]]


class PropertiesUpdateRequest(BaseModel):
    updates: dict[str, str] = Field(min_length=1)


class ConsoleCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=500)


class ConsoleLinesResponse(BaseModel):
    lines: list[dict[str, str]]


class AllowlistEntry(BaseModel):
    name: str
    xuid: str | None = None
    ignoresPlayerLimit: bool | None = None


class AllowlistResponse(BaseModel):
    entries: list[dict[str, Any]]


class AllowlistAddRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    xuid: str | None = None


class PermissionEntryRequest(BaseModel):
    xuid: str = Field(min_length=1, max_length=32)
    permission: str
    name: str | None = None


class PermissionsResponse(BaseModel):
    entries: list[dict[str, Any]]
