"""Operation API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OperationResponse(BaseModel):
    id: int
    type: str
    status: str
    params: dict[str, Any] | None = None
    started_by: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    log: str = ""
    rollback_performed: bool = False
    created_at: str | None = None


class OperationListResponse(BaseModel):
    operations: list[OperationResponse]
    active_id: int | None = None


class MessageResponse(BaseModel):
    detail: str = Field(examples=["ok"])
