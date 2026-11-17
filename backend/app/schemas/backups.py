"""Backup API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.operations import OperationResponse


class BackupResponse(BaseModel):
    id: int
    world_id: int
    world_folder: str
    kind: str
    path: str
    size_bytes: int
    sha256: str
    verified: bool
    created_at: str | None = None
    created_by: int | None = None


class BackupListResponse(BaseModel):
    backups: list[BackupResponse]
    storage: dict[str, int] = Field(default_factory=dict)


class BackupCreateResponse(BaseModel):
    operation: OperationResponse


class RestoreResponse(BaseModel):
    operation: OperationResponse
