"""Pack-library backup archive metadata."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class AddonLibraryBackup(SQLModel, table=True):
    __tablename__ = "addon_library_backups"

    id: int | None = Field(default=None, primary_key=True)
    path: str = Field(max_length=512)
    size_bytes: int = Field(default=0)
    sha256: str = Field(max_length=64)
    verified: bool = Field(default=False)
    pack_count: int = Field(default=0)
    note: str | None = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    created_by: int | None = Field(default=None, index=True)
