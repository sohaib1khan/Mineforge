"""Stream settings and session history for the OBS → MediaMTX pipeline."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class StreamSettings(SQLModel, table=True):
    """Singleton row (id=1) for stream page config and publish key hash."""

    __tablename__ = "stream_settings"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(default="MineForge Live", max_length=128)
    description: str = Field(default="", max_length=512)
    enabled: bool = Field(default=True)
    key_hash: str | None = Field(default=None, max_length=256)
    key_rotated_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StreamSession(SQLModel, table=True):
    """One publish session from successful MediaMTX publish auth to end."""

    __tablename__ = "stream_sessions"

    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    ended_at: datetime | None = Field(default=None, index=True)
    peak_viewers: int = Field(default=0)
    started_by: int | None = Field(default=None, index=True)
    publisher_ip: str | None = Field(default=None, max_length=64)
