"""World library entry (minimal for Phase 3 backups; full CRUD in Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class World(SQLModel, table=True):
    __tablename__ = "worlds"

    id: int | None = Field(default=None, primary_key=True)
    display_name: str = Field(max_length=128)
    folder_name: str = Field(index=True, unique=True, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    gamemode: str | None = Field(default=None, max_length=32)
    difficulty: str | None = Field(default=None, max_length=32)
    seed: str | None = Field(default=None, max_length=64)
    size_bytes: int = Field(default=0)
    is_active: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_played_at: datetime | None = None
    needs_experiments: bool = Field(default=False)
