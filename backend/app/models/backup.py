"""World backup archive metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class BackupKind(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    PRE_SWITCH = "pre_switch"
    PRE_RESTORE = "pre_restore"
    PRE_RESET = "pre_reset"
    PRE_ADDON = "pre_addon"
    # First import / capture; used by Reset and never auto-deleted.
    ORIGINAL = "original"


class Backup(SQLModel, table=True):
    __tablename__ = "backups"

    id: int | None = Field(default=None, primary_key=True)
    world_id: int = Field(index=True, foreign_key="worlds.id")
    kind: BackupKind = Field(index=True)
    path: str = Field(max_length=512)
    size_bytes: int = Field(default=0)
    sha256: str = Field(max_length=64)
    verified: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    created_by: int | None = Field(default=None, index=True)
    world_folder: str = Field(max_length=128, index=True)
