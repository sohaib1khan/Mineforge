"""Add-on (behavior/resource pack) library and per-world enablement."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class AddonKind(StrEnum):
    BEHAVIOR = "behavior"
    RESOURCE = "resource"


class Addon(SQLModel, table=True):
    __tablename__ = "addons"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=256, index=True)
    pack_uuid: str = Field(max_length=64, index=True)
    version: str = Field(max_length=64)
    kind: AddonKind = Field(index=True)
    pair_addon_id: int | None = Field(default=None, index=True)
    source_filename: str = Field(max_length=256)
    sha256: str = Field(max_length=64, index=True)
    size_bytes: int = Field(default=0)
    missing_pair: bool = Field(default=False)
    encrypted: bool = Field(default=False)
    needs_beta_apis: bool = Field(default=False)
    uploaded_by: int | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = Field(default=None, max_length=1024)
    # Relative path under app-data/packs/
    storage_path: str = Field(max_length=512)


class WorldAddon(SQLModel, table=True):
    __tablename__ = "world_addons"

    id: int | None = Field(default=None, primary_key=True)
    world_id: int = Field(index=True, foreign_key="worlds.id")
    addon_id: int = Field(index=True, foreign_key="addons.id")
    enabled: bool = Field(default=True)
    load_order: int = Field(default=0)
