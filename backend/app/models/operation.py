"""Long-running job with lock, status, and streamed log."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class OperationType(StrEnum):
    SWITCH = "switch"
    BACKUP = "backup"
    RESTORE = "restore"
    ADDON_APPLY = "addon_apply"
    ADDON_TEST = "addon_test"


class OperationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Operation(SQLModel, table=True):
    __tablename__ = "operations"

    id: int | None = Field(default=None, primary_key=True)
    type: OperationType = Field(index=True)
    status: OperationStatus = Field(default=OperationStatus.QUEUED, index=True)
    params: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    started_by: int | None = Field(default=None, index=True)
    started_at: datetime | None = Field(default=None, index=True)
    finished_at: datetime | None = None
    log: str = Field(default="")
    rollback_performed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
