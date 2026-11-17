"""In-game player join/leave sessions parsed from Bedrock logs."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class PlayerSession(SQLModel, table=True):
    __tablename__ = "player_sessions"

    id: int | None = Field(default=None, primary_key=True)
    gamertag: str = Field(index=True, max_length=128)
    xuid: str | None = Field(default=None, index=True, max_length=32)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    left_at: datetime | None = Field(default=None, index=True)
    world_id: int | None = Field(default=None, index=True)
