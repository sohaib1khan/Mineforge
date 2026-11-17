"""Audit log entries for admin actions and operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
    )
    user_id: int | None = Field(default=None, index=True, foreign_key="users.id")
    action: str = Field(index=True, max_length=128)
    target: str | None = Field(default=None, max_length=256)
    details: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON),
    )
    ip: str | None = None
