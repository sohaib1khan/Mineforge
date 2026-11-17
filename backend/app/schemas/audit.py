"""Audit log schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogPublic(BaseModel):
    id: int
    ts: datetime
    user_id: int | None
    action: str
    target: str | None
    details: dict[str, Any] | None
    ip: str | None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogPublic]
