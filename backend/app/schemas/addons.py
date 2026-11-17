"""Add-on API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.operations import OperationResponse


class AddonResponse(BaseModel):
    id: int
    name: str
    pack_uuid: str
    version: str
    kind: str
    pair_addon_id: int | None = None
    pair_name: str | None = None
    source_filename: str
    sha256: str
    size_bytes: int
    missing_pair: bool = False
    encrypted: bool = False
    needs_beta_apis: bool = False
    flags: list[str] = Field(default_factory=list)
    uploaded_by: int | None = None
    created_at: str | None = None
    notes: str | None = None
    used_by_world_ids: list[int] = Field(default_factory=list)


class AddonListResponse(BaseModel):
    addons: list[AddonResponse]


class AddonUploadResponse(BaseModel):
    addons: list[AddonResponse]


class WorldAddonEntry(BaseModel):
    world_addon_id: int | None = None
    addon_id: int
    enabled: bool = True
    load_order: int = 0
    addon: AddonResponse | None = None


class WorldProfileResponse(BaseModel):
    world_id: int
    entries: list[WorldAddonEntry]
    download_size: dict[str, int] = Field(default_factory=dict)


class WorldProfileUpdateRequest(BaseModel):
    entries: list[WorldAddonEntry]


class AddonApplyRequest(BaseModel):
    test_mode: bool = False


class AddonApplyResponse(BaseModel):
    operation: OperationResponse


class PendingTestsResponse(BaseModel):
    pending: list[dict[str, object]]


class TexturepackRequiredRequest(BaseModel):
    required: bool
